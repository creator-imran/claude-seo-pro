#!/usr/bin/env python3
"""
lint_report.py - deterministic linter for generated audit reports.

Machine-checks a report HTML against the 14-section depth contract
(skills/seo-audit/references/report-template.md). This is the deterministic half of
the audit-quality eval harness — it catches structural contract violations (missing
sections, leftover template placeholders, summary-only compression) that the
"self-check before delivering" rule relies on. The LLM-judge half (semantic quality)
is deliberately NOT here; it ships separately once calibrated (see ROADMAP-7-to-9).

FAIL = hard contract violation (report must not ship).
WARN = depth floor / heuristic shortfall (review before shipping).

    python tools/lint_report.py <report.html> [--json]

Exit codes: 0 = pass (warnings allowed), 1 = contract FAIL, 2 = usage/file error.
"""
import sys, os, re, json, argparse

# (key, human name, regex over the WHOLE html, required?)
SECTIONS = [
    ("cover",        "Cover page",                       r'class="cover"', True),
    ("integrity",    "Data Integrity & Methodology",     r"<h2[^>]*>\s*Data Integrity", True),
    ("exec",         "Executive Summary",                r"<h2[^>]*>\s*Executive Summary", True),
    ("priority",     "Priority Issues",                  r"<h2[^>]*>\s*Priority Issues", True),
    ("strengths",    "What's Genuinely Strong",          r"<h2[^>]*>\s*What['’]s Genuinely Strong", True),
    ("organic",      "Organic Search Visibility",        r"<h2[^>]*>\s*Organic Search Visibility", True),
    ("keywords",     "Keyword Research",                 r"<h2[^>]*>\s*Keyword Research", True),
    ("local",        "Local SEO & GBP (or skip note)",   r"<h2[^>]*>\s*Local SEO|Local SEO/GBP skipped|skipped by design", True),
    ("competitive",  "Competitive Landscape",            r"<h2[^>]*>\s*Competitive Landscape", True),
    ("onpage",       "On-Page Detail",                   r"<h2[^>]*>\s*On-Page Detail", True),
    ("performance",  "Performance Detail (field vs lab)", r"<h2[^>]*>\s*Performance Detail", True),
    ("content",      "Content & E-E-A-T detail",         r"<h2[^>]*>\s*Content (&amp;|&) E-E-A-T", True),
    ("schema",       "Schema detail",                    r"<h2[^>]*>\s*Schema", True),
    ("ai",           "AI Search Readiness detail",       r"<h2[^>]*>\s*AI (Search )?Read", True),
    ("plan",         "Prioritised Action Plan",          r"<h2[^>]*>\s*Prioriti[sz]ed Action Plan", True),
    ("appendix",     "Appendix (sources & integrity)",   r"<h2[^>]*>\s*Appendix", True),
]

# depth floors: (name, regex counted, minimum, level-if-below)
FLOORS = [
    ("KPI cards",            r'class="kpi"',      4, "WARN"),
    ("scorecard categories", r'class="scard"',    6, "WARN"),
    ("finding cards",        r'class="finding"',  4, "WARN"),
    ("evidence/source cites", r'class="src"|Source:', 6, "WARN"),
    ("tables",               r"<table",           8, "WARN"),
]

def lint(path):
    html = open(path, encoding="utf-8", errors="replace").read()
    fails, warns = [], []

    # 1) leftover template placeholders = the report was not actually filled in
    leftovers = sorted(set(re.findall(r"\{\{[A-Z0-9_|: #\-]{2,60}\}\}", html)))
    if leftovers:
        fails.append(f"unfilled template placeholders: {leftovers[:8]}"
                     + (f" (+{len(leftovers)-8} more)" if len(leftovers) > 8 else ""))

    # 2) required sections
    for key, name, pat, required in SECTIONS:
        if not re.search(pat, html, re.I):
            (fails if required else warns).append(f"missing section: {name}")

    # 3) depth floors
    for name, pat, floor, level in FLOORS:
        n = len(re.findall(pat, html, re.I))
        if n < floor:
            (warns if level == "WARN" else fails).append(
                f"depth floor: {name} = {n} (< {floor})")

    # 4) pending-data discipline: prose 'Data pending' markers need a cause nearby.
    # (Scorecard PENDING cells are exempt — their cause lives in the Data Integrity
    # section, which check 2 already requires.)
    for m in re.finditer(r"Data pending", html, re.I):
        ctx = html[m.start():m.start() + 600]
        if not re.search(r"\b(4\d{4}|not connected|subscription|OAuth|whitelist|requires|skipped|pending data|unreachable|exact cause|estimated)\b", ctx, re.I):
            warns.append("a 'Data pending' marker has no visible cause/unlock within its block")
            break

    # 5) footer with score + version present
    if not re.search(r'class="footer"', html):
        warns.append("no footer block (client · version · date · score)")

    # 5b) model-backend provenance line (mandatory per contract §2; warn-level)
    if not re.search(r"Model backend", html, re.I):
        warns.append("no 'Model backend:' provenance line in Data Integrity "
                     "(state Anthropic first-party or the OpenRouter model map)")

    # 6) summary-only compression heuristic: a contract report has substantial body
    if len(html) < 18_000:
        warns.append(f"report HTML is only {len(html)//1000}KB — likely summary-only "
                     "(gold standard runs 30KB+); check per-page tables exist")

    return fails, warns

def main():
    ap = argparse.ArgumentParser(description="Lint an audit report against the 14-section depth contract")
    ap.add_argument("report", help="path to the generated report .html")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()
    if not os.path.exists(args.report):
        print(f"[x] no such file: {args.report}")
        return 2
    fails, warns = lint(args.report)
    status = "FAIL" if fails else ("WARN" if warns else "PASS")
    if args.json:
        print(json.dumps({"status": status, "fails": fails, "warns": warns,
                          "file": args.report}, indent=2))
    else:
        print(f"[{status}] {os.path.basename(args.report)} vs 14-section depth contract")
        for f in fails:
            print(f"  FAIL  {f}")
        for w in warns:
            print(f"  warn  {w}")
        if status == "PASS":
            print("  all required sections present, no leftover placeholders, floors met")
        elif status == "FAIL":
            print("  -> contract violation: do NOT deliver this report; fix and re-lint")
    return 1 if fails else 0

if __name__ == "__main__":
    raise SystemExit(main())
