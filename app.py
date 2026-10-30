#!/usr/bin/env python3
"""PSI Sprint Status Reporter
Turns raw sprint metrics (JSON) into a leadership-ready weekly status report
(Markdown + HTML). Health (RAG) is computed from explicit, transparent rules.
Optional: add an AI-written executive narrative with the Claude API.

Usage:
    python app.py sample_data.json                 # writes report.md + report.html
    python app.py sample_data.json --ai            # adds AI narrative (needs ANTHROPIC_API_KEY)
"""
import argparse
import html
import json
import os
import sys
import urllib.request


def compute_health(d):
    """Return (status, reasons). Rules are deliberately simple and explainable."""
    s = d["sprint"]
    expected = s["committed_points"] * s["day"] / s["total_days"]
    pace = s["completed_points"] / expected if expected else 1.0
    reasons, score = [], 0
    if pace < 0.7:
        score += 2; reasons.append(f"Delivery pace is {pace:.0%} of plan (red < 70%)")
    elif pace < 0.9:
        score += 1; reasons.append(f"Delivery pace is {pace:.0%} of plan (amber < 90%)")
    high = [r for r in d["risks"] if r["severity"] >= 15 and r["status"] == "Open"]
    if len(high) >= 3:
        score += 2; reasons.append(f"{len(high)} open high-severity risks")
    elif high:
        score += 1; reasons.append(f"{len(high)} open high-severity risk(s)")
    crit = d["bugs"].get("critical_open", 0)
    if crit:
        score += 2; reasons.append(f"{crit} open critical bug(s)")
    blockers = [b for b in d["blockers"] if not b.get("resolved")]
    if len(blockers) >= 3:
        score += 1; reasons.append(f"{len(blockers)} unresolved blockers")
    late = [m for m in d["milestones"] if m["status"] == "At Risk"]
    if late:
        score += 1; reasons.append(f"{len(late)} milestone(s) at risk")
    status = "RED" if score >= 4 else "AMBER" if score >= 2 else "GREEN"
    return status, reasons or ["All indicators within thresholds"], pace


def ai_narrative(d, status, reasons):
    key = os.environ.get("ANTHROPIC_API_KEY")
    if not key:
        return "(AI narrative skipped: set ANTHROPIC_API_KEY to enable.)"
    prompt = (
        "You are a technical project manager. Write a 90-word executive summary for "
        "leadership from this sprint data. Be factual; end with one clear ask.\n\n"
        f"Health: {status}. Reasons: {reasons}\nData: {json.dumps(d)}"
    )
    body = json.dumps({
        "model": os.environ.get("ANTHROPIC_MODEL", "claude-sonnet-5-5"),
        "max_tokens": 400,
        "messages": [{"role": "user", "content": prompt}],
    }).encode()
    req = urllib.request.Request(
        "https://api.anthropic.com/v1/messages", data=body,
        headers={"x-api-key": key, "anthropic-version": "2023-06-01",
                 "content-type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return json.load(r)["content"][0]["text"]
    except Exception as e:  # keep the tool usable offline
        return f"(AI narrative failed: {e})"


def build_markdown(d, status, reasons, pace, narrative):
    s, b = d["sprint"], d["bugs"]
    L = [f"# Weekly Status Report: {d['project']}",
         f"**Sprint {s['number']}**  |  Day {s['day']} of {s['total_days']}  |  Overall health: **{status}**", ""]
    if narrative:
        L += ["## Executive summary", narrative, ""]
    L += ["## Why this status", *[f"- {r}" for r in reasons], "",
          "## Sprint progress",
          f"- Committed: {s['committed_points']} SP | Completed: {s['completed_points']} SP | Pace vs plan: {pace:.0%}",
          f"- Velocity (last sprints): {', '.join(map(str, d['velocity_history']))}", "",
          "## Quality",
          f"- Open bugs: {b['open']} (critical {b['critical_open']}) | Closed this week: {b['closed_this_week']}", "",
          "## Milestones", "| Milestone | Date | Status |", "|---|---|---|"]
    L += [f"| {m['name']} | {m['date']} | {m['status']} |" for m in d["milestones"]]
    L += ["", "## Top risks", "| Risk | Severity | Owner | Mitigation |", "|---|---|---|---|"]
    L += [f"| {r['name']} | {r['severity']} | {r['owner']} | {r['mitigation']} |"
          for r in sorted(d["risks"], key=lambda r: -r["severity"])[:5] if r["status"] == "Open"]
    L += ["", "## Blockers"]
    L += [f"- {x['text']} (owner: {x['owner']})" for x in d["blockers"] if not x.get("resolved")] or ["- None"]
    L += ["", "## Budget", f"- Spent {d['budget']['spent_pct']}% vs {d['budget']['planned_pct']}% planned"]
    L += ["", "## Decisions needed", *[f"- {x}" for x in d.get("decisions_needed", [])]]
    return "\n".join(L)


def md_to_html(md, status):
    colour = {"GREEN": "#1b8a3b", "AMBER": "#d98a00", "RED": "#c62828"}[status]
    out, in_ul, in_tbl = [], False, False
    for line in md.split("\n"):
        e = html.escape(line)
        e = e.replace("**", "\u0001")
        parts = e.split("\u0001")
        e = "".join(p if i % 2 == 0 else f"<b>{p}</b>" for i, p in enumerate(parts))
        if in_ul and not line.startswith("- "):
            out.append("</ul>"); in_ul = False
        if in_tbl and not line.startswith("|"):
            out.append("</table>"); in_tbl = False
        if line.startswith("# "):
            out.append(f"<h1>{e[2:]}</h1>")
        elif line.startswith("## "):
            out.append(f"<h2>{e[3:]}</h2>")
        elif line.startswith("- "):
            if not in_ul:
                out.append("<ul>"); in_ul = True
            out.append(f"<li>{e[2:]}</li>")
        elif line.startswith("|"):
            if set(line.replace("|", "").strip()) <= {"-"}:
                continue
            cells = [c.strip() for c in e.strip("|").split("|")]
            if not in_tbl:
                out.append("<table>"); in_tbl = True
                out.append("<tr>" + "".join(f"<th>{c}</th>" for c in cells) + "</tr>")
            else:
                out.append("<tr>" + "".join(f"<td>{c}</td>" for c in cells) + "</tr>")
        elif line.strip():
            out.append(f"<p>{e}</p>")
    if in_ul: out.append("</ul>")
    if in_tbl: out.append("</table>")
    css = (f"body{{font-family:Arial,sans-serif;max-width:860px;margin:30px auto;color:#222}}"
           f"h1{{border-bottom:4px solid {colour}}}table{{border-collapse:collapse;width:100%}}"
           f"td,th{{border:1px solid #ccc;padding:6px;text-align:left;font-size:13px}}th{{background:#f0f0f0}}")
    return f"<html><head><meta charset='utf-8'><style>{css}</style></head><body>{''.join(out)}</body></html>"


def main():
    ap = argparse.ArgumentParser(description="Generate a weekly sprint status report")
    ap.add_argument("data", help="path to sprint JSON")
    ap.add_argument("--ai", action="store_true", help="add AI executive narrative")
    ap.add_argument("--out", default="report", help="output file prefix")
    a = ap.parse_args()
    with open(a.data) as f:
        d = json.load(f)
    status, reasons, pace = compute_health(d)
    narrative = ai_narrative(d, status, reasons) if a.ai else None
    md = build_markdown(d, status, reasons, pace, narrative)
    with open(a.out + ".md", "w") as f:
        f.write(md)
    with open(a.out + ".html", "w") as f:
        f.write(md_to_html(md, status))
    print(f"Health: {status} | wrote {a.out}.md and {a.out}.html")


if __name__ == "__main__":
    sys.exit(main())