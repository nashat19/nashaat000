from __future__ import annotations

import argparse
import asyncio
import logging
import sys
from pathlib import Path

from . import analyze
from .callscript import build as build_script
from .config import load
from .engine import run_scan
from .phone import parse
from .report import write
from .storage import Storage
from .utils import jdump, mask_number

def _setup_logging(verbose: bool) -> None:
    logging.basicConfig(
        level=logging.DEBUG if verbose else logging.INFO,
        format="%(asctime)s %(levelname)-7s %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )

def _print_report(report) -> None:
    print(f"\n═══ {report.e164 or report.target} ═══")
    print(f"الدرجة: {report.score()} · النتائج: {len(report.findings)}\n")
    for result in report.results:
        if result.skipped:
            print(f"  ⊘ {result.provider}: {result.error}")
            continue
        if not result.ok:
            print(f"  ✗ {result.provider}: {result.error}")
            continue
        print(f"  ✓ {result.provider} ({result.elapsed_ms}ms)")
        for finding in result.findings:
            note = f"  — {finding.note}" if finding.note else ""
            print(f"      {finding.key} = {finding.value} [{finding.confidence}]{note}")

def cmd_scan(args) -> int:
    config = load(args.config)
    phone = parse(args.number, args.region or config.default_region)
    if not phone.e164:
        print("رقم غير صالح", file=sys.stderr)
        return 2
    if not phone.valid:
        print(f"تحذير: الرقم غير مؤكد الصلاحية ({phone.e164})", file=sys.stderr)

    report = asyncio.run(run_scan(phone, config, args.providers))
    _print_report(report)

    if args.output:
        paths = write(report, args.output, config.output.formats)
        for path in paths:
            print(f"\n→ {path}")
    if args.json:
        print(jdump(report.to_dict(), indent=2))
    return 0

def cmd_serve(args) -> int:
    import uvicorn

    from .capture.server import create_app

    config = load(args.config)
    if args.host:
        config.capture.host = args.host
    if args.port:
        config.capture.port = args.port
    if args.public_base:
        config.capture.public_base = args.public_base

    app = create_app(config)
    print(f"لوحة التحكم: http://{config.capture.host}:{config.capture.port}/?k={config.capture.dashboard_token}")
    print(f"القاعدة العامة: {config.capture.public_base}")
    uvicorn.run(app, host=config.capture.host, port=config.capture.port, log_level="info")
    return 0

def cmd_call(args) -> int:
    config = load(args.config)
    phone = parse(args.number, args.region or config.default_region)
    if not phone.e164:
        print("رقم غير صالح", file=sys.stderr)
        return 2

    storage = Storage(config.capture.db_path)
    try:
        token = storage.create_session(phone.e164, args.label, config.capture.session_ttl)
    finally:
        storage.close()

    url = f"{config.capture.public_base.rstrip('/')}/c/{token}"
    script = build_script(phone.e164, url, config.capture.brand, args.caller)

    print(script)
    print(f"\n**التوكن:** `{token}`")
    print(f"**اللوحة:** {config.capture.public_base.rstrip('/')}/?k={config.capture.dashboard_token}")

    if args.output:
        path = Path(args.output)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(script, encoding="utf-8")
        print(f"\n→ {path}")
    return 0

def cmd_sessions(args) -> int:
    config = load(args.config)
    storage = Storage(config.capture.db_path)
    try:
        for session in storage.list_sessions(args.limit):
            print(f"{session['token']}  {session['number']}  hits={session['hits']}  {session['created_at']}")
    finally:
        storage.close()
    return 0

def cmd_show(args) -> int:
    config = load(args.config)
    storage = Storage(config.capture.db_path)
    try:
        bundle = storage.bundle(args.token)
    finally:
        storage.close()
    if bundle["session"] is None:
        print("جلسة غير موجودة", file=sys.stderr)
        return 2
    print(jdump(bundle, indent=2))
    return 0

def cmd_analyze(args) -> int:
    config = load(args.config)
    storage = Storage(config.capture.db_path)
    try:
        if storage.get_session(args.token) is None:
            print("جلسة غير موجودة", file=sys.stderr)
            return 2
        fingerprints = storage.list_fingerprints(args.token)
        locations = storage.list_locations(args.token)
        events = storage.list_events(args.token)
        ip_geo = {}
        for event in reversed(events):
            if event["kind"] == "ip_geo" and isinstance(event["data"], dict):
                ip_geo = event["data"]
                break
        latest = fingerprints[-1]["data"] if fingerprints else {}
        dossier = analyze.dossier(latest, ip_geo, locations)
        dossier["stage"] = analyze.stage_of(events)
        dossier["fp_count"] = len(fingerprints)
        dossier["loc_count"] = len(locations)
    finally:
        storage.close()

    print(analyze.summary_line(dossier))
    print()
    print(jdump(dossier, indent=2))
    if dossier["mismatches"]:
        print("\nتعارضات:")
        for flag in dossier["mismatches"]:
            print(f"  ⚠ {flag}")
    return 0

def cmd_export(args) -> int:
    config = load(args.config)
    storage = Storage(config.capture.db_path)
    try:
        bundle = storage.bundle(args.token)
    finally:
        storage.close()
    if bundle["session"] is None:
        print("جلسة غير موجودة", file=sys.stderr)
        return 2
    path = Path(args.output or f"out/{args.token}.json")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(jdump(bundle, indent=2), encoding="utf-8")
    print(f"→ {path}")
    return 0

def cmd_purge(args) -> int:
    config = load(args.config)
    storage = Storage(config.capture.db_path)
    try:
        count = storage.purge_expired()
    finally:
        storage.close()
    print(f"حُذفت {count} جلسة منتهية")
    return 0

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="phonex", description="PhoneX — استخبارات أرقام والتقاط جهاز/موقع")
    parser.add_argument("-c", "--config", help="مسار ملف الإعدادات")
    parser.add_argument("-v", "--verbose", action="store_true")
    sub = parser.add_subparsers(dest="command", required=True)

    scan = sub.add_parser("scan", help="استخبارات سلبية من الرقم")
    scan.add_argument("number")
    scan.add_argument("-r", "--region")
    scan.add_argument("-p", "--providers", nargs="*")
    scan.add_argument("-o", "--output")
    scan.add_argument("--json", action="store_true")
    scan.set_defaults(func=cmd_scan)

    serve = sub.add_parser("serve", help="تشغيل سيرفر الالتقاط واللوحة")
    serve.add_argument("--host")
    serve.add_argument("--port", type=int)
    serve.add_argument("--public-base")
    serve.set_defaults(func=cmd_serve)

    call = sub.add_parser("call", help="إنشاء جلسة وسكربت مكالمة")
    call.add_argument("number")
    call.add_argument("-r", "--region")
    call.add_argument("-l", "--label", default="")
    call.add_argument("--caller", default="فريق التحقق")
    call.add_argument("-o", "--output")
    call.set_defaults(func=cmd_call)

    sessions = sub.add_parser("sessions", help="سرد الجلسات")
    sessions.add_argument("--limit", type=int, default=50)
    sessions.set_defaults(func=cmd_sessions)

    show = sub.add_parser("show", help="عرض حزمة جلسة كاملة")
    show.add_argument("token")
    show.set_defaults(func=cmd_show)

    analyze_cmd = sub.add_parser("analyze", help="حساب ملف الهدف لجلسة")
    analyze_cmd.add_argument("token")
    analyze_cmd.set_defaults(func=cmd_analyze)

    export = sub.add_parser("export", help="تصدير حزمة جلسة")
    export.add_argument("token")
    export.add_argument("-o", "--output")
    export.set_defaults(func=cmd_export)

    purge = sub.add_parser("purge", help="حذف الجلسات المنتهية")
    purge.set_defaults(func=cmd_purge)

    return parser

def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    _setup_logging(args.verbose)
    try:
        return int(args.func(args) or 0)
    except KeyboardInterrupt:
        print("\nمقاطعة", file=sys.stderr)
        return 130

if __name__ == "__main__":
    sys.exit(main())