#!/usr/bin/env python3
"""
learn.py - batch-ingest learned facts into the client knowledge store (Feature 2).

The client-learning agent (agents/seo-learn.md) reads audit evidence, reasons about
what is a DURABLE business fact (vs a transient metric or a guess), and emits a JSON
array of candidate facts. This module validates, guards, dedups, optionally supersedes
stale facts, and writes the survivors to the store via KnowledgeStore.

A candidate fact:
  {
    "text": "Strokes targets KSA as a secondary market",
    "evidence": "Riyadh/Jeddah service pages; ranked_keywords.json",   # file:line or API field
    "confidence": "high|medium|low",
    "source": "audit-2026-06",
    "tags": ["market"],
    "replace_tag": "primary-market"        # optional: retire existing facts with this tag
  }

Guards (Evidence Integrity + memory hygiene):
  * Unsourced facts are forced to low confidence (handled by the store).
  * TRANSIENT metrics ("score is 61", "today", bare numbers/dates) are REJECTED — those
    belong in history.jsonl (add-history), not durable facts.
  * SECRET-looking strings (api keys, tokens, passwords) are REJECTED outright.
  * Near-duplicate text collapses (store dedups by normalized text).

Usage:
  python learn.py preview --domain <d> --file candidates.json   # dry-run, writes nothing
  python learn.py ingest  --domain <d> --file candidates.json   # validate + write
  echo '[{...}]' | python learn.py ingest --domain <d> --stdin
"""

from __future__ import annotations

import argparse
import json
import re
import sys

try:
    from . import store as store_mod
except ImportError:
    import store as store_mod

# A durable fact should not be a transient metric / dated snapshot.
TRANSIENT = re.compile(
    r"\b(score is|scored|today|currently \d|as of \d{4}-\d{2}|this (week|month)|"
    r"\bnow ranks?\b.*\bposition\b)", re.I)
# Reject anything that looks like a credential.
SECRET = re.compile(r"(api[_-]?key|secret|password|token|bearer|AIza[0-9A-Za-z_\-]{20}|"
                    r"\bfc-[a-zA-Z0-9]{16}|[a-f0-9]{32,})", re.I)


def classify(cand: dict) -> tuple:
    """Return (verdict, reason). verdict in {ok, reject, downgrade}."""
    text = (cand.get("text") or "").strip()
    if not text:
        return "reject", "empty text"
    if len(text) < 8:
        return "reject", "too short to be a durable fact"
    if SECRET.search(text) or SECRET.search(cand.get("evidence", "")):
        return "reject", "looks like a secret — not stored"
    if TRANSIENT.search(text):
        return "reject", "transient metric — record via add-history, not as a durable fact"
    if not cand.get("evidence") and cand.get("confidence") in ("high", "medium"):
        return "downgrade", "no evidence — confidence forced to low"
    return "ok", ""


def process(domain: str, candidates: list, write: bool) -> dict:
    ks = store_mod.KnowledgeStore(domain)
    summary = {"domain": ks.slug, "written": write, "added": [], "downgraded": [],
               "rejected": [], "superseded_tags": []}
    for cand in candidates:
        verdict, reason = classify(cand)
        text = (cand.get("text") or "").strip()
        if verdict == "reject":
            summary["rejected"].append({"text": text[:80], "reason": reason})
            continue
        conf = cand.get("confidence", "low")
        if verdict == "downgrade":
            conf = "low"
            summary["downgraded"].append({"text": text[:80], "reason": reason})
        supersedes = None
        rtag = cand.get("replace_tag")
        if rtag:
            prior = ks.facts_with_tag(rtag)
            supersedes = [f["key"] for f in prior]
            if supersedes and write:
                summary["superseded_tags"].append({"tag": rtag, "retired": len(supersedes)})
        if write:
            rec = ks.add_fact(text, evidence=cand.get("evidence", ""), confidence=conf,
                              source=cand.get("source", ""), tags=cand.get("tags") or [],
                              supersedes=supersedes)
            label = "duplicate" if rec.get("duplicate_of") else "added"
        else:
            label = "would-add"
        summary["added"].append({"text": text[:80], "confidence": conf, "status": label})
    summary["counts"] = {"added_or_would": len(summary["added"]),
                         "downgraded": len(summary["downgraded"]),
                         "rejected": len(summary["rejected"])}
    return summary


def _load(args) -> list:
    raw = sys.stdin.read() if args.stdin else open(args.file, encoding="utf-8").read()
    data = json.loads(raw)
    if isinstance(data, dict) and "facts" in data:
        data = data["facts"]
    if not isinstance(data, list):
        raise ValueError("expected a JSON array of candidate facts")
    return data


def main(argv=None):
    ap = argparse.ArgumentParser(description="Ingest learned facts into the knowledge store")
    sub = ap.add_subparsers(dest="cmd", required=True)
    for name in ("preview", "ingest"):
        p = sub.add_parser(name)
        p.add_argument("--domain", required=True)
        g = p.add_mutually_exclusive_group(required=True)
        g.add_argument("--file")
        g.add_argument("--stdin", action="store_true")
    args = ap.parse_args(argv)

    candidates = _load(args)
    summary = process(args.domain, candidates, write=(args.cmd == "ingest"))
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
