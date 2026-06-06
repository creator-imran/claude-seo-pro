"""
fsutil.py - shared, owner-only filesystem helpers for the Claude SEO Pro knowledge layer.

Client knowledge and the data cache are CLIENT DATA, not code — they live OUTSIDE the
repo under ~/.config/claude-seo/ (the same owner-only space as credentials), and are
never committed. This module centralizes the path layout, permission hardening, atomic
writes, and the JSON/JSONL primitives both store.py and cache.py build on.

(Named fsutil, not _io: `_io` is a reserved Python built-in module name.)

Stdlib only — runs on a fresh machine before any pip install.

Layout:
  ~/.config/claude-seo/
    clients/<slug>/profile.json     # stable business understanding (merge-updated)
    clients/<slug>/facts.jsonl      # append-only learned facts (deduped by key)
    clients/<slug>/history.jsonl    # append-only audit/score timeline
    cache/<provider>/<hash>.json    # computed-data cache entries (with provenance)
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import tempfile
from pathlib import Path

CONFIG_ROOT = Path(os.path.expanduser("~")) / ".config" / "claude-seo"
CLIENTS_ROOT = CONFIG_ROOT / "clients"
CACHE_ROOT = CONFIG_ROOT / "cache"
IS_WINDOWS = os.name == "nt"


def slugify(value: str) -> str:
    """Turn a domain or brand into a stable directory-safe slug."""
    v = (value or "").strip().lower()
    v = re.sub(r"^https?://", "", v)
    v = re.sub(r"^www\.", "", v)
    v = v.split("/")[0]
    v = re.sub(r"[^a-z0-9]+", "-", v).strip("-")
    return v or "unknown"


def restrict_perms(path: Path, is_dir: bool = False) -> None:
    """Owner-only access. Best-effort, never raises (matches onboarding/secure_store)."""
    try:
        if IS_WINDOWS:
            user = os.environ.get("USERNAME") or os.environ.get("USER") or ""
            if user:
                grant = f"{user}:(OI)(CI)F" if is_dir else f"{user}:F"
                subprocess.run(["icacls", str(path), "/inheritance:r", "/grant:r", grant],
                               check=False, capture_output=True)
        else:
            os.chmod(path, 0o700 if is_dir else 0o600)
    except Exception:
        pass


def _ensure_dir(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    restrict_perms(path, is_dir=True)
    return path


def client_dir(slug: str) -> Path:
    return _ensure_dir(CLIENTS_ROOT / slug)


def cache_dir(provider: str = "") -> Path:
    return _ensure_dir(CACHE_ROOT / provider) if provider else _ensure_dir(CACHE_ROOT)


def write_json(path: Path, data) -> Path:
    """Atomic, owner-only JSON write."""
    _ensure_dir(path.parent)
    fd, tmp = tempfile.mkstemp(dir=str(path.parent), prefix=".tmp-", suffix=".json")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            json.dump(data, fh, indent=2, sort_keys=True)
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)
    restrict_perms(path)
    return path


def read_json(path: Path, default=None):
    if not path.exists():
        return default
    try:
        with open(path, "r", encoding="utf-8") as fh:
            return json.load(fh)
    except (json.JSONDecodeError, OSError):
        return default


def append_jsonl(path: Path, record: dict) -> None:
    _ensure_dir(path.parent)
    with open(path, "a", encoding="utf-8") as fh:
        fh.write(json.dumps(record, sort_keys=True) + "\n")
    restrict_perms(path)


def read_jsonl(path: Path) -> list:
    if not path.exists():
        return []
    out = []
    try:
        with open(path, "r", encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if line:
                    try:
                        out.append(json.loads(line))
                    except json.JSONDecodeError:
                        continue
    except OSError:
        return out
    return out
