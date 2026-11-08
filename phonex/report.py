from __future__ import annotations

import html
from pathlib import Path

from .models import Report
from .utils import jdump, slugify, utcnow

CONFIDENCE_CLASS = {"high": "hi", "medium": "md", "low": "lo"}


def to_json(report: Report) -> str:
    return jdump(report.to_dict(), indent=2)


def to_markdown(report: Report) -> str:
    lines = [
        f"# تقرير PhoneX — {report.e164 or report.target}",
        "",
        f"- الهدف: `{report.target}`",
        f"- E.164: `{report.e164}`",
        f"- البدء: {report.started_at}",
        f"- الانتهاء: {report.finished_at}",
        f"- الدرجة: {report.score()}",
        "",
        "## بيانات الرقم",
        "",
    ]
    for key, value in report.phone.items():
        if value in ("", None, [], {}):
            continue
        lines.append(f"- **{key}**: `{value}`")

    lines += ["", "## النتائج", ""]
    for result in report.results:
        status = "تخطّي" if result.skipped else ("خطأ" if not result.ok else "تم")
        lines.append(f"### {result.provider} — {status} ({result.elapsed_ms}ms)")
        if result.error:
            lines.append(f"> {result.error}")
        for finding in result.findings:
            note = f" — {finding.note}" if finding.note else ""
            lines.append(
                f"- `{finding.key}` = `{finding.value}` "
                f"[{finding.confidence}]{note}"
            )
        lines.append("")

    lines.append(f"_تم التوليد: {utcnow()}_")
    return "\n".join(lines)


def to_html(report: Report) -> str:
    rows = []
    for result in report.results:
        for finding in result.findings:
            cls = CONFIDENCE_CLASS.get(finding.confidence, "lo")
            value = html.escape(str(finding.value))
            if finding.url:
                value = f'<a href="{html.escape(finding.url)}" target="_blank" rel="noopener">{value}</a>'
            rows.append(
                f"<tr><td>{html.escape(result.provider)}</td>"
                f"<td>{html.escape(finding.key)}</td>"
                f"<td>{value}</td>"
                f'<td><span class="c {cls}">{finding.confidence}</span></td></tr>'
            )

    return f"""<!doctype html>
<html lang="ar" dir="rtl"><head><meta charset="utf-8">
<title>PhoneX — {html.escape(report.e164)}</title>
<style>
body{{font-family:system-ui,Segoe UI,Tahoma,sans-serif;background:#0b1020;color:#e6ecff;margin:0;padding:32px}}
h1{{font-size:22px}} .meta{{color:#8fa3c8;font-size:13px;margin-bottom:20px}}
table{{width:100%;border-collapse:collapse;font-size:13px}}
th,td{{padding:8px 10px;border-bottom:1px solid #1e2a44;text-align:right;vertical-align:top}}
th{{color:#8fa3c8;font-weight:600}}
a{{color:#5eead4;word-break:break-all}}
.c{{padding:2px 8px;border-radius:99px;font-size:11px}}
.hi{{background:#0f3d2e;color:#5eead4}} .md{{background:#3d3410;color:#fbbf24}} .lo{{background:#2a2f45;color:#94a3b8}}
</style></head><body>
<h1>تقرير PhoneX — {html.escape(report.e164 or report.target)}</h1>
<div class="meta">الهدف: {html.escape(report.target)} · الدرجة: {report.score()} · {html.escape(report.started_at)}</div>
<table><thead><tr><th>المزوّد</th><th>المفتاح</th><th>القيمة</th><th>الثقة</th></tr></thead>
<tbody>{''.join(rows)}</tbody></table>
</body></html>"""


def write(report: Report, out_dir: str, formats: list[str]) -> list[Path]:
    directory = Path(out_dir)
    directory.mkdir(parents=True, exist_ok=True)
    stem = f"{slugify(report.e164 or report.target)}-{utcnow().replace(':', '')}"
    written: list[Path] = []
    writers = {"json": to_json, "md": to_markdown, "html": to_html}
    for fmt in formats:
        writer = writers.get(fmt)
        if writer is None:
            continue
        path = directory / f"{stem}.{fmt}"
        path.write_text(writer(report), encoding="utf-8")
        written.append(path)
    return written