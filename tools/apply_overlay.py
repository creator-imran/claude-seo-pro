#!/usr/bin/env python3
"""
apply_overlay.py - re-apply Claude SEO Pro's in-place customizations to upstream files.

Our additive files (onboarding/, skills/seo-setup/, docs we added, etc.) never
conflict with upstream, so they need no overlay. The ONLY upstream file we modify in
place is skills/seo-audit/SKILL.md. This module re-applies those modifications using
anchored string operations that are:

  * idempotent  - running twice is a no-op (it detects its own markers)
  * preserving  - it injects our content without discarding upstream's other edits
                  to the same file
  * loud        - if upstream moves/renames an anchor, it reports FAILED for that
                  change instead of silently doing nothing, so you review by hand

Run standalone:   python tools/apply_overlay.py [--repo-root .] [--check]
Returns nonzero exit if any change FAILED (useful in CI).
"""

from __future__ import annotations

import argparse
import os
import sys

# ----- our customizations, kept here as the single source of truth -----

FETCH_OLD = "1. **Fetch homepage**: use `scripts/fetch_page.py` to retrieve HTML"
FETCH_NEW = (
    "1. **Pre-fetch ALL pages FIRST (main session, not subagents)**: use "
    "`~/.claude/skills/seo/scripts/fetch_page.py` (NOTE: shared scripts live in the "
    "`seo` skill directory, not this one). Save every fetched HTML to disk and pass "
    "the **file paths** to subagents. Subagents may have no network access — they "
    "must read local files, never fetch live and never guess. Log each URL's HTTP "
    "status to a `manifest.csv`. See **Evidence Integrity Protocol** below — this "
    "step is mandatory."
)
FETCH_MARKER = "Pre-fetch ALL pages FIRST"

PROTOCOL_MARKER = "## Evidence Integrity Protocol (MANDATORY)"
PROTOCOL_ANCHOR = "## Crawl Configuration"
PROTOCOL_BLOCK = '''## Evidence Integrity Protocol (MANDATORY)

> This protocol exists because an early audit (the "v1 incident") shipped fabricated
> findings: subagents that could not fetch the site silently substituted "typical
> patterns," and the orchestrator stripped their `[VERIFY]`/`[INFERRED]` caveats when
> compiling the report — promoting guesses to definitive "Critical Issues." Every rule
> below is a direct countermeasure. **No finding ships unless it traces to evidence.**

1. **Pre-fetch in the main session.** The orchestrator fetches all pages with
   `fetch_page.py` (full Chrome UA defeats most WAFs) and writes HTML to disk BEFORE
   any subagent runs. Subagents receive **file paths** and use `Read`/`Grep` only.
2. **A failed fetch is reported, never substituted.** If a page can't be retrieved,
   the report says so for that page. "Typical patterns for sites like this" is banned.
3. **Every finding cites its evidence** — source file + line, or the exact API field
   and response file. A claim with no citable source does not appear in the report.
4. **Never strip subagent caveats.** `[VERIFY]`, `[INFERRED]`, `[ASSUMPTION]`, and
   confidence tags are carried verbatim into the report, or the claim is verified
   before publishing. Aggregation must not upgrade a hedge into a fact.
5. **No score without backing data.** A category is only scored when live evidence
   supports it. Categories needing external data that is unavailable (e.g. backlinks
   without an API) are marked **"Data pending"** and excluded from the score — not
   estimated.
6. **Core Web Vitals use real field data** (CrUX via PageSpeed/`seo-google`), never
   lab estimates presented as field truth. Lab artifacts (e.g. throttled CLS) are
   labelled as such.
7. **Schema is read from raw HTML, not rendered/stripped HTML.** `WebFetch` removes
   `<script>` tags, hiding JSON-LD; some generators (e.g. Rank Math) emit an UNQUOTED
   `type=application/ld+json` attribute. Always `Grep` the raw HTML for both
   `application/ld+json` and `ld+json`.
8. **Report what was NOT covered.** If the crawl was capped, a page failed, or a
   section is pending data, say so explicitly. Silent truncation reads as full
   coverage when it isn't.

Subagent prompts MUST restate rules 2-4 and instruct the subagent to write
"NOT FOUND IN EVIDENCE" rather than infer.

## Crawl Configuration'''

ERR_OLD = (
    "| URL unreachable (DNS failure, connection refused) | Report the error clearly. "
    "Do not guess site content. Suggest the user verify the URL and try again. |"
)
ERR_NEW = (
    "| URL unreachable (DNS failure, connection refused) | Report the error clearly. "
    "Do not guess site content (see Evidence Integrity Protocol rule 2). Suggest the "
    "user verify the URL and try again. |\n"
    "| WAF blocks the fetch (403 to bare clients) | Retry with the full Chrome UA via "
    "`fetch_page.py` / `curl.exe`. If still blocked, report the block — do not "
    "substitute assumed content. |\n"
    "| Subagent reports it could not read a file | Treat as a failed evidence source: "
    "re-fetch in the main session and re-dispatch, or mark the affected findings "
    '"Data pending". Never accept inferred content in its place. |'
)
ERR_MARKER = "WAF blocks the fetch (403 to bare clients)"

TARGET = os.path.join("skills", "seo-audit", "SKILL.md")


def _apply_changes(text: str) -> tuple[str, list[tuple[str, str]]]:
    """Return (new_text, [(change_name, status)]). status in {applied, present, FAILED}."""
    results = []

    # Change 1: fetch line -> pre-fetch mandate
    if FETCH_MARKER in text:
        results.append(("fetch-path", "present"))
    elif FETCH_OLD in text:
        text = text.replace(FETCH_OLD, FETCH_NEW, 1)
        results.append(("fetch-path", "applied"))
    else:
        results.append(("fetch-path", "FAILED"))

    # Change 2: insert Evidence Integrity Protocol before Crawl Configuration
    if PROTOCOL_MARKER in text:
        results.append(("evidence-protocol", "present"))
    elif PROTOCOL_ANCHOR in text:
        text = text.replace(PROTOCOL_ANCHOR, PROTOCOL_BLOCK, 1)
        results.append(("evidence-protocol", "applied"))
    else:
        results.append(("evidence-protocol", "FAILED"))

    # Change 3: expand error-handling rows (non-fatal if upstream rewrote the table)
    if ERR_MARKER in text:
        results.append(("error-rows", "present"))
    elif ERR_OLD in text:
        text = text.replace(ERR_OLD, ERR_NEW, 1)
        results.append(("error-rows", "applied"))
    else:
        results.append(("error-rows", "FAILED"))

    return text, results


def apply(repo_root: str, check_only: bool = False) -> int:
    path = os.path.join(repo_root, TARGET)
    if not os.path.exists(path):
        print(f"[x] target not found: {path}")
        return 2
    with open(path, "r", encoding="utf-8") as fh:
        original = fh.read()
    new_text, results = _apply_changes(original)

    failed = [n for n, s in results if s == "FAILED"]
    for name, status in results:
        mark = {"applied": "[+]", "present": "[=]", "FAILED": "[x]"}[status]
        print(f"  {mark} {name}: {status}")

    if check_only:
        if new_text != original:
            print("  -> overlay NOT fully applied (would change the file)")
            return 1
    elif new_text != original:
        with open(path, "w", encoding="utf-8", newline="\n") as fh:
            fh.write(new_text)
        print(f"  wrote {path}")

    if failed:
        print(f"[x] {len(failed)} overlay change(s) FAILED - upstream likely moved an "
              f"anchor in {TARGET}. Review and update tools/apply_overlay.py.")
        return 1
    return 0


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="Re-apply Claude SEO Pro overlay to upstream files")
    ap.add_argument("--repo-root", default=os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    ap.add_argument("--check", action="store_true", help="report whether overlay is applied; make no changes")
    args = ap.parse_args()
    raise SystemExit(apply(args.repo_root, check_only=args.check))
