"""Fail-closed summary: missing cases cannot become a green report."""
from __future__ import annotations
from collections import Counter
import html
import json
from pathlib import Path
import xml.etree.ElementTree as ET
from ci.common import ROOT
from ci.plan import plan

def render(rows, output):
    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    expected = {r["id"]: r for r in plan()}
    actual_ids = [r["id"] for r in rows]
    inventory_errors = []
    missing = sorted(set(expected) - set(actual_ids))
    extra = sorted(set(actual_ids) - set(expected))
    if missing: inventory_errors.append(f"Missing required report rows: {len(missing)}")
    if extra: inventory_errors.append(f"Unknown report rows: {len(extra)}")
    if len(set(actual_ids)) != len(actual_ids): inventory_errors.append("Duplicate report rows")
    for r in rows:
        exp = expected.get(r["id"])
        if exp and ((exp["status"] == "EXCLUDED") != (r["status"] == "EXCLUDED")):
            inventory_errors.append(f"Changed exclusion policy: {r['id']}")
    counts = Counter(r["status"] for r in rows)
    failing = sum(v for k, v in counts.items() if k not in ("PASS", "EXCLUDED"))
    ok = bool(rows) and failing == 0 and counts["PASS"] > 0 and not inventory_errors
    title = "PASS" if ok else "FAILED / INCOMPLETE"
    lines = [f"# mysqlclient-static — {title}", "",
             f"PASS: {counts['PASS']} | FAIL: {counts['FAIL']} | NOT_RUN: {counts['NOT_RUN']} | "
             f"EXCLUDED: {counts['EXCLUDED']} (not counted as passed)", "",
             "Every tested cell uses real MySQL. No SQLite, protocol mocks, eager Celery, or source-build fallback.", "",
             "| Suite | Python | Django/profile | MySQL | Authentication | Status | Detail |",
             "|---|---|---|---|---|---|---|"]
    for r in rows:
        detail = str(r.get("reason", "")).replace("|", "\\|").replace("\n", " ")[:400]
        lines.append(f"| {r['suite']} | {r['python']} | {r['django']} | {r['mysql']} | {r['auth']} | {r['status']} | {detail} |")
    if inventory_errors:
        lines += ["", "## Report inventory errors", "", *inventory_errors]
    markdown = "\n".join(lines) + "\n"
    (output / "summary.md").write_text(markdown)
    columns = ("suite", "python", "django", "mysql", "auth", "status", "reason")
    body = "".join("<tr>" + "".join(f"<td>{html.escape(str(r.get(k, '')))}</td>" for k in columns) + "</tr>" for r in rows)
    (output / "index.html").write_text("<!doctype html><meta charset='utf-8'><title>mysqlclient-static E2E</title>"
        "<style>body{font:14px system-ui;margin:32px}table{border-collapse:collapse;width:100%}"
        "td,th{padding:8px;border:1px solid #bbb;text-align:left}td:last-child{max-width:500px;overflow-wrap:anywhere}</style>"
        f"<h1>{title}</h1><p>{html.escape(lines[2])}</p><p>{html.escape('; '.join(inventory_errors))}</p><table><thead><tr>" +
        "".join(f"<th>{k}</th>" for k in columns) + "</tr></thead><tbody>" + body + "</tbody></table>")
    root = ET.Element("testsuite", name="mysqlclient-static-real-e2e", tests=str(len(rows) + len(inventory_errors)),
                      failures=str(failing + len(inventory_errors)), skipped=str(counts["EXCLUDED"]))
    for r in rows:
        node = ET.SubElement(root, "testcase", classname=r["suite"], name=r["id"], time=str(r.get("seconds", 0)))
        if r["status"] == "EXCLUDED":
            ET.SubElement(node, "skipped", message=r.get("reason", ""))
        elif r["status"] != "PASS":
            ET.SubElement(node, "failure", message=r.get("reason", r["status"])).text = r.get("log_tail", "")
    for error in inventory_errors:
        node = ET.SubElement(root, "testcase", classname="report-inventory", name=error)
        ET.SubElement(node, "failure", message=error)
    ET.ElementTree(root).write(output / "junit.xml", encoding="utf-8", xml_declaration=True)
    return ok

if __name__ == "__main__":
    p = ROOT / "reports/results.json"
    if p.exists():
        render(json.loads(p.read_text()), ROOT / "reports")
    else:
        rows = plan()
        for row in rows:
            if row["status"] == "NOT_RUN":
                row["reason"] = "Build or setup stopped before E2E results were created."
        from ci.common import write_json
        write_json(p, rows)
        render(rows, ROOT / "reports")
