#!/usr/bin/env python3
"""
cache.py - computed-data cache for Claude SEO Pro.

Caches the RESULTS of expensive operations (DataForSEO pulls, fetched HTML, PSI/CrUX,
keyword datasets) on disk so repeat audits don't re-pay for data that hasn't changed.
This is a genuine "long-term cache engine" — for DATA, distinct from (and complementary
to) Anthropic's ephemeral, model-scoped prompt cache.

Evidence Integrity: every entry stores PROVENANCE — provider, operation, params,
fetched_at, ttl, and the raw response. Cached data is still real API data with a
citable source; it is never a substitute for a live call that failed. An expired entry
is a MISS (the caller re-fetches), not a silent stale read.

Layout: ~/.config/claude-seo/cache/<provider>/<hash>.json

Usage (CLI, for inspection):
  python cache.py stats
  python cache.py purge --older-than-days 30
  python cache.py get --provider dataforseo --op ranked_keywords --params '{"target":"x.com"}'
"""

from __future__ import annotations

import argparse
import datetime
import hashlib
import json

try:
    from . import fsutil as _io
except ImportError:
    import fsutil as _io


def _now_ts() -> float:
    # epoch seconds; datetime.utcnow avoids Date.now-style nondeterminism concerns here
    return (datetime.datetime.utcnow() - datetime.datetime(1970, 1, 1)).total_seconds()


def _iso(ts: float) -> str:
    return datetime.datetime.utcfromtimestamp(ts).strftime("%Y-%m-%dT%H:%M:%SZ")


class DataCache:
    def __init__(self, provider: str):
        self.provider = _io.slugify(provider)
        self.dir = _io.cache_dir(self.provider)

    def _key(self, op: str, params: dict) -> str:
        blob = json.dumps({"op": op, "params": params or {}}, sort_keys=True)
        return hashlib.sha256(blob.encode("utf-8")).hexdigest()[:24]

    def _path(self, key: str):
        return self.dir / f"{key}.json"

    def get(self, op: str, params: dict, max_age_seconds: float | None = None) -> dict | None:
        """Return {data, meta} if a fresh entry exists, else None (a MISS)."""
        path = self._path(self._key(op, params))
        entry = _io.read_json(path)
        if not entry:
            return None
        meta = entry.get("meta", {})
        if max_age_seconds is not None:
            age = _now_ts() - float(meta.get("fetched_ts", 0))
            if age > max_age_seconds:
                return None  # expired -> miss; caller re-fetches (no stale reads)
        ttl = meta.get("ttl_seconds")
        if ttl is not None and (_now_ts() - float(meta.get("fetched_ts", 0))) > float(ttl):
            return None
        return entry

    def put(self, op: str, params: dict, data, ttl_seconds: float | None = None,
            extra_meta: dict = None) -> str:
        key = self._key(op, params)
        ts = _now_ts()
        meta = {
            "provider": self.provider, "op": op, "params": params or {},
            "fetched_ts": ts, "fetched_utc": _iso(ts), "ttl_seconds": ttl_seconds,
        }
        if extra_meta:
            meta.update(extra_meta)
        _io.write_json(self._path(key), {"meta": meta, "data": data})
        return key

    def get_or_call(self, op: str, params: dict, fn, max_age_seconds: float | None = None,
                    ttl_seconds: float | None = None) -> tuple:
        """Return (data, hit). On miss, call fn() to fetch, store with provenance, return it.
        fn must return the raw response; if fn returns None, nothing is cached."""
        cached = self.get(op, params, max_age_seconds=max_age_seconds)
        if cached is not None:
            return cached["data"], True
        fresh = fn()
        if fresh is not None:
            self.put(op, params, fresh, ttl_seconds=ttl_seconds)
        return fresh, False

    def provenance(self, op: str, params: dict) -> dict | None:
        """The citable source line for a cached entry (for report Evidence sections)."""
        entry = self.get(op, params)
        if not entry:
            return None
        m = entry["meta"]
        return {"source": f"{m['provider']}/{m['op']}", "fetched_utc": m.get("fetched_utc"),
                "cached": True}


def stats() -> dict:
    out = {"providers": {}, "total_entries": 0, "total_bytes": 0}
    if not _io.CACHE_ROOT.exists():
        return out
    for pdir in sorted(_io.CACHE_ROOT.iterdir()):
        if not pdir.is_dir():
            continue
        files = list(pdir.glob("*.json"))
        size = sum(f.stat().st_size for f in files)
        out["providers"][pdir.name] = {"entries": len(files), "bytes": size}
        out["total_entries"] += len(files)
        out["total_bytes"] += size
    return out


def purge(older_than_days: float) -> int:
    cutoff = _now_ts() - older_than_days * 86400
    removed = 0
    if not _io.CACHE_ROOT.exists():
        return 0
    for pdir in _io.CACHE_ROOT.iterdir():
        if not pdir.is_dir():
            continue
        for f in pdir.glob("*.json"):
            entry = _io.read_json(f)
            ts = (entry or {}).get("meta", {}).get("fetched_ts", 0)
            if float(ts) < cutoff:
                try:
                    f.unlink(); removed += 1
                except OSError:
                    pass
    return removed


def main(argv=None):
    ap = argparse.ArgumentParser(description="Claude SEO Pro data cache")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("stats")
    pg = sub.add_parser("purge"); pg.add_argument("--older-than-days", type=float, default=30)
    g = sub.add_parser("get"); g.add_argument("--provider", required=True); g.add_argument("--op", required=True)
    g.add_argument("--params", default="{}")
    args = ap.parse_args(argv)

    if args.cmd == "stats":
        print(json.dumps(stats(), indent=2))
    elif args.cmd == "purge":
        print(f"[+] purged {purge(args.older_than_days)} entries older than {args.older_than_days}d")
    elif args.cmd == "get":
        c = DataCache(args.provider)
        entry = c.get(args.op, json.loads(args.params))
        print(json.dumps(entry, indent=2) if entry else "MISS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
