#!/usr/bin/env python3
"""
store.py - the persistent, model-independent client knowledge store for Claude SEO Pro.

This is the "long-term memory" that survives BOTH model switches and new sessions
(unlike the Anthropic prompt cache, which is ephemeral, model-scoped, and cannot be
ported across models). Any model, any session, reads the same client knowledge here to
start fully informed.

Three artifacts per client (under ~/.config/claude-seo/clients/<slug>/):
  profile.json   - stable business understanding (model, country, markets, ICPs, seeds,
                   is_local_business). Seeded from Phase-0 business-profile.json; merge-updated.
  facts.jsonl    - append-only learned facts (deduped by key). Written by the audit and,
                   later, the client-learning agent.
  history.jsonl  - append-only audit/score timeline.

Every learned fact carries evidence + confidence + source (Evidence Integrity Protocol):
a fact with no citable source is recorded as low-confidence and flagged, never asserted.

Usage:
  python store.py recall <domain>                 # human-readable summary for an agent to read
  python store.py recall <domain> --json
  python store.py set-profile <domain> --file business-profile.json
  python store.py add-fact <domain> --text "..." --evidence "..." --confidence high --source audit-2026-06
  python store.py add-history <domain> --score 61 --note "v3 audit"
  python store.py list                            # all known clients
"""

from __future__ import annotations

import argparse
import datetime
import hashlib
import json
import sys

try:
    from . import fsutil as _io
except ImportError:
    import fsutil as _io


def _now() -> str:
    return datetime.datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")


class KnowledgeStore:
    def __init__(self, identifier: str):
        self.slug = _io.slugify(identifier)
        self.dir = _io.client_dir(self.slug)
        self.profile_path = self.dir / "profile.json"
        self.facts_path = self.dir / "facts.jsonl"
        self.history_path = self.dir / "history.jsonl"

    # ---- profile ----
    def load_profile(self) -> dict:
        return _io.read_json(self.profile_path, default={}) or {}

    def set_profile(self, profile: dict, merge: bool = True) -> dict:
        """Merge-update the business understanding. Stamps updated_utc and tracks slug."""
        current = self.load_profile() if merge else {}
        for k, v in (profile or {}).items():
            if v is not None:
                current[k] = v
        current["slug"] = self.slug
        current["updated_utc"] = _now()
        _io.write_json(self.profile_path, current)
        return current

    # ---- facts ----
    @staticmethod
    def _fact_key(text: str) -> str:
        return hashlib.md5(text.strip().lower().encode("utf-8")).hexdigest()[:12]

    def add_fact(self, text: str, evidence: str = "", confidence: str = "low",
                 source: str = "", tags=None, supersedes=None) -> dict:
        """Append a learned fact, deduped by normalized text. Unsourced -> forced low.
        `supersedes` = list of prior fact keys to retire (correcting a stale belief)."""
        text = (text or "").strip()
        if not text:
            raise ValueError("fact text is required")
        if not evidence and confidence != "low":
            confidence = "low"  # Evidence Integrity: no source -> not high-confidence
        if supersedes:
            self.supersede(supersedes, reason=f"replaced by: {text[:60]}")
        key = self._fact_key(text)
        existing = {f.get("key") for f in self.facts()}
        rec = {"key": key, "text": text, "evidence": evidence or "",
               "confidence": confidence, "source": source or "", "tags": tags or [],
               "added_utc": _now()}
        if key in existing:
            rec["duplicate_of"] = key  # keep the trail but don't re-assert
            return rec
        _io.append_jsonl(self.facts_path, rec)
        return rec

    def supersede(self, keys, reason: str = "") -> None:
        """Retire prior facts by key (e.g. when a new fact corrects them)."""
        keys = [k for k in (keys or []) if k]
        if keys:
            _io.append_jsonl(self.facts_path,
                             {"op": "supersede", "keys": keys, "reason": reason, "at_utc": _now()})

    def _superseded_keys(self) -> set:
        out = set()
        for r in _io.read_jsonl(self.facts_path):
            if r.get("op") == "supersede":
                out.update(r.get("keys", []))
        return out

    def facts(self) -> list:
        """Latest unique facts by key, excluding duplicates and superseded ones."""
        retired = self._superseded_keys()
        seen = {}
        for f in _io.read_jsonl(self.facts_path):
            if f.get("op") == "supersede":
                continue
            k = f.get("key")
            if k and "duplicate_of" not in f and k not in retired:
                seen[k] = f
        return list(seen.values())

    def facts_with_tag(self, tag: str) -> list:
        return [f for f in self.facts() if tag in (f.get("tags") or [])]

    # ---- history ----
    def add_history(self, score=None, note: str = "", extra: dict = None) -> dict:
        rec = {"at_utc": _now(), "score": score, "note": note or ""}
        if extra:
            rec.update(extra)
        _io.append_jsonl(self.history_path, rec)
        return rec

    def history(self) -> list:
        return _io.read_jsonl(self.history_path)

    # ---- recall ----
    def exists(self) -> bool:
        return self.profile_path.exists() or self.facts_path.exists()

    def summary(self) -> dict:
        return {
            "slug": self.slug,
            "profile": self.load_profile(),
            "facts": self.facts(),
            "history": self.history(),
        }

    def recall_text(self) -> str:
        """A compact briefing an agent reads at the START of any work on this client."""
        p = self.load_profile()
        if not p and not self.facts():
            return f"No prior knowledge stored for '{self.slug}'. This is a first engagement."
        lines = [f"# What we know about {p.get('brand', self.slug)} ({self.slug})"]
        if p.get("one_line"):
            lines.append(p["one_line"])
        if p.get("business_model"):
            lines.append(f"- Model: {p['business_model']}")
        coo = p.get("country_of_origin") or {}
        if coo:
            lines.append(f"- Country of origin: {coo.get('name') or coo}")
        markets = p.get("target_markets") or []
        if markets:
            names = ", ".join(m.get("name", str(m)) if isinstance(m, dict) else str(m) for m in markets)
            lines.append(f"- Target markets: {names}")
        if p.get("is_local_business") is not None:
            lines.append(f"- Local business: {p['is_local_business']}")
        seeds = p.get("seed_keyword_themes") or []
        if seeds:
            lines.append(f"- Seed keyword themes: {', '.join(seeds[:12])}")
        f = self.facts()
        if f:
            lines.append(f"\n## Learned facts ({len(f)})")
            for fact in sorted(f, key=lambda x: x.get("confidence", ""), reverse=True)[:25]:
                tag = f"[{fact.get('confidence', '?')}]"
                src = f" (src: {fact['source']})" if fact.get("source") else ""
                lines.append(f"- {tag} {fact['text']}{src}")
        h = self.history()
        if h:
            lines.append(f"\n## Audit history ({len(h)})")
            for ev in h[-6:]:
                lines.append(f"- {ev.get('at_utc', '?')}: score={ev.get('score')} {ev.get('note', '')}")
        lines.append("\n(Start from this; verify anything time-sensitive before re-asserting it.)")
        return "\n".join(lines)


def list_clients() -> list:
    if not _io.CLIENTS_ROOT.exists():
        return []
    return sorted(d.name for d in _io.CLIENTS_ROOT.iterdir() if d.is_dir())


def main(argv=None):
    ap = argparse.ArgumentParser(description="Claude SEO Pro client knowledge store")
    sub = ap.add_subparsers(dest="cmd", required=True)

    r = sub.add_parser("recall"); r.add_argument("domain"); r.add_argument("--json", action="store_true")
    sp = sub.add_parser("set-profile"); sp.add_argument("domain"); sp.add_argument("--file", required=True)
    af = sub.add_parser("add-fact"); af.add_argument("domain"); af.add_argument("--text", required=True)
    af.add_argument("--evidence", default=""); af.add_argument("--confidence", default="low",
                    choices=["low", "medium", "high"]); af.add_argument("--source", default="")
    ah = sub.add_parser("add-history"); ah.add_argument("domain"); ah.add_argument("--score", type=float)
    ah.add_argument("--note", default="")
    sub.add_parser("list")
    args = ap.parse_args(argv)

    if args.cmd == "list":
        print(json.dumps(list_clients(), indent=2)); return 0

    ks = KnowledgeStore(args.domain)
    if args.cmd == "recall":
        if args.json:
            print(json.dumps(ks.summary(), indent=2))
        else:
            print(ks.recall_text())
    elif args.cmd == "set-profile":
        prof = _io.read_json(__import__("pathlib").Path(args.file))
        if prof is None:
            print(f"[x] could not read {args.file}"); return 1
        ks.set_profile(prof)
        print(f"[+] profile stored for {ks.slug}")
    elif args.cmd == "add-fact":
        rec = ks.add_fact(args.text, evidence=args.evidence, confidence=args.confidence, source=args.source)
        print(f"[+] fact {'(duplicate, skipped)' if rec.get('duplicate_of') else 'added'}: {rec['key']}")
    elif args.cmd == "add-history":
        ks.add_history(score=args.score, note=args.note)
        print(f"[+] history event added for {ks.slug}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
