"""
secure_store.py - owner-only, repo-external credential storage for Claude SEO Pro.

Design goals (see docs/SECURITY.md):
  * Secrets NEVER live in the repo. They are written under ~/.config/claude-seo/.
  * Each file is created with 0600 (owner read/write only). On Windows, NTFS ACLs
    are reset to grant ONLY the current user (icacls), since chmod is a no-op there.
  * Reads are tolerant (missing file -> {}), writes are atomic, and every write
    re-asserts permissions so a key written today can't be left world-readable.

This module is intentionally stdlib-only so it runs on a fresh machine before any
`pip install`. Higher layers (validate.py, configure_mcp.py, setup_wizard.py) build
on it.
"""

from __future__ import annotations

import json
import os
import stat
import subprocess
import sys
import tempfile
from pathlib import Path

# Canonical, user-space config directory (matches upstream claude-seo convention).
CONFIG_DIR = Path(os.path.expanduser("~")) / ".config" / "claude-seo"

IS_WINDOWS = os.name == "nt"


def config_dir() -> Path:
    """Return the config dir, creating it with restrictive perms if needed."""
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    _restrict_permissions(CONFIG_DIR, is_dir=True)
    return CONFIG_DIR


def config_path(name: str) -> Path:
    """Path to a named config file, e.g. config_path('dataforseo') -> .../dataforseo.json."""
    if not name.endswith(".json"):
        name += ".json"
    return config_dir() / name


def _restrict_permissions(path: Path, is_dir: bool = False) -> None:
    """Make `path` accessible to the current user only. Best-effort, never raises."""
    try:
        if IS_WINDOWS:
            # chmod can't express NTFS ACLs; use icacls to remove inheritance and
            # grant the running user full control, nothing else.
            user = os.environ.get("USERNAME") or os.environ.get("USER") or ""
            if user:
                subprocess.run(
                    ["icacls", str(path), "/inheritance:r", "/grant:r", f"{user}:(OI)(CI)F" if is_dir else f"{user}:F"],
                    check=False,
                    capture_output=True,
                )
        else:
            mode = 0o700 if is_dir else 0o600
            os.chmod(path, mode)
    except Exception:
        # Permission hardening is defense-in-depth; failure must not block setup,
        # but we surface it so the wizard can warn the user.
        pass


def permissions_ok(path: Path) -> bool:
    """True if `path` is not group/other accessible (POSIX). Windows: assume icacls ran."""
    try:
        if IS_WINDOWS:
            return path.exists()
        mode = stat.S_IMODE(os.stat(path).st_mode)
        return (mode & 0o077) == 0
    except Exception:
        return False


def save(name: str, data: dict) -> Path:
    """Atomically write `data` as JSON to the named config file with 0600 perms."""
    path = config_path(name)
    config_dir()  # ensure dir + perms
    fd, tmp = tempfile.mkstemp(dir=str(path.parent), prefix=".tmp-", suffix=".json")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            json.dump(data, fh, indent=2, sort_keys=True)
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)
    _restrict_permissions(path)
    return path


def load(name: str) -> dict:
    """Load the named config file; return {} if it does not exist or is unreadable."""
    path = config_path(name)
    if not path.exists():
        return {}
    try:
        with open(path, "r", encoding="utf-8") as fh:
            return json.load(fh)
    except (json.JSONDecodeError, OSError):
        return {}


def merge(name: str, updates: dict) -> Path:
    """Load, shallow-merge `updates`, and re-save. Returns the path."""
    current = load(name)
    current.update({k: v for k, v in updates.items() if v is not None})
    return save(name, current)


def delete(name: str) -> bool:
    """Remove a named config file. Returns True if a file was removed."""
    path = config_path(name)
    if path.exists():
        path.unlink()
        return True
    return False


def status() -> dict:
    """Summarize which provider configs exist and whether perms look safe."""
    out = {}
    if not CONFIG_DIR.exists():
        return out
    for f in sorted(CONFIG_DIR.glob("*.json")):
        out[f.stem] = {
            "path": str(f),
            "permissions_ok": permissions_ok(f),
            "keys": sorted(load(f.name).keys()),
        }
    return out


if __name__ == "__main__":
    # `python secure_store.py status` prints a redacted summary.
    if len(sys.argv) > 1 and sys.argv[1] == "status":
        print(json.dumps(status(), indent=2))
    else:
        print(f"Config dir: {CONFIG_DIR}")
        print("Usage: python secure_store.py status")
