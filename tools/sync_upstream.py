#!/usr/bin/env python3
"""
sync_upstream.py - pull a new upstream Claude SEO version into this fork.

What it does:
  1. Reads upstream.json (repo + pinned tag), or --tag to override.
  2. Downloads that ref's tarball from GitHub and extracts it.
  3. Copies UPSTREAM-OWNED files over the repo, SKIPPING our overlay (the files we
     own outright - onboarding/, skills/seo-setup/, docs we wrote, installers, etc.).
  4. Re-applies our in-place overlay (tools/apply_overlay.py) so the seo-audit
     Evidence Integrity Protocol + fetch-path fix survive the refresh.
  5. Updates upstream.json with the new tag.

It does NOT commit or push - run it, review `git diff`, then commit. In CI the
workflow runs this and opens a PR (see .github/workflows/sync-upstream.yml).

Stdlib only. Usage:
  python tools/sync_upstream.py                 # sync to the pinned tag
  python tools/sync_upstream.py --tag v2.1.0    # sync to a specific tag
  python tools/sync_upstream.py --tag main      # track the upstream main branch
  python tools/sync_upstream.py --dry-run       # show what would change, write nothing
"""

from __future__ import annotations

import argparse
import datetime
import json
import os
import shutil
import sys
import tarfile
import tempfile
import urllib.request

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Files/dirs we OWN. Upstream must never overwrite these. Paths are repo-relative,
# forward-slash; a trailing "/" means "this directory and everything under it".
OVERLAY_PROTECTED = [
    "onboarding/",
    "knowledge/",
    "routing/",
    "connector/",
    "skills/seo-setup/",
    "skills/seo-knowledge/",
    "skills/seo-learn/",
    "skills/seo-models/",
    "skills/seo-connect/",
    "tools/",
    ".github/",
    "manual/",
    "docs/CONNECTOR.md",
    # New owned files that live inside upstream-owned dirs (protect by exact path):
    "agents/seo-learn.md",
    "scripts/keyword_research.py",
    "skills/seo-audit/references/business-intelligence.md",
    "skills/seo-audit/references/audit-playbook.md",
    "skills/seo-audit/references/keyword-research.md",
    "skills/seo-audit/references/local-gbp-audit.md",
    "skills/seo-audit/references/report-template.md",
    "skills/seo-audit/assets/",
    "docs/ONBOARDING.md",
    "docs/SECURITY.md",
    "docs/WHATS-DIFFERENT.md",
    "docs/PUBLISH.md",
    "README.md",
    "NOTICE",
    "CHANGELOG.md",
    "CLAUDE.md",
    ".gitignore",
    "install.ps1",
    "install.sh",
    "publish-to-github.ps1",
    ".claude-plugin/plugin.json",
    "upstream.json",
    "VERSION.md",
    "system-version.json",
    # Upstream org-specific files we intentionally drop from this fork; protecting
    # them keeps sync from re-introducing them.
    "CODEOWNERS",
    "CITATION.cff",
    ".devcontainer/",
]


def _is_protected(rel: str) -> bool:
    rel = rel.replace("\\", "/")
    for p in OVERLAY_PROTECTED:
        if p.endswith("/"):
            if rel == p[:-1] or rel.startswith(p):
                return True
        elif rel == p:
            return True
    return False


def _load_upstream() -> dict:
    with open(os.path.join(REPO_ROOT, "upstream.json"), "r", encoding="utf-8") as fh:
        return json.load(fh)


def _download_tarball(repo: str, tag: str, dest_dir: str) -> str:
    last_err = None
    for ref in (f"refs/tags/{tag}", f"refs/heads/{tag}", tag):
        url = f"https://codeload.github.com/{repo}/tar.gz/{ref}"
        out = os.path.join(dest_dir, "upstream.tar.gz")
        try:
            urllib.request.urlretrieve(url, out)
            if os.path.getsize(out) > 1000:
                return out
        except Exception as e:  # noqa: BLE001
            last_err = e
    raise RuntimeError(f"could not download {repo}@{tag}: {last_err}")


def _extract(tar_path: str, dest_dir: str) -> str:
    with tarfile.open(tar_path, "r:gz") as tf:
        tf.extractall(dest_dir)  # noqa: S202 - trusted GitHub source archive
    tops = [d for d in os.listdir(dest_dir) if os.path.isdir(os.path.join(dest_dir, d))]
    if len(tops) != 1:
        raise RuntimeError(f"unexpected archive layout: {tops}")
    return os.path.join(dest_dir, tops[0])


def sync(tag: str | None, dry_run: bool) -> int:
    meta = _load_upstream()
    repo = meta["repo"]
    tag = tag or meta["tag"]
    print(f"==> Syncing {repo}@{tag}  (dry-run={dry_run})")

    with tempfile.TemporaryDirectory() as tmp:
        src_root = _extract(_download_tarball(repo, tag, tmp), tmp)

        updated, added, skipped = [], [], 0
        for dirpath, _dirs, files in os.walk(src_root):
            for name in files:
                src = os.path.join(dirpath, name)
                rel = os.path.relpath(src, src_root).replace("\\", "/")
                if _is_protected(rel):
                    skipped += 1
                    continue
                dst = os.path.join(REPO_ROOT, rel)
                exists = os.path.exists(dst)
                if exists:
                    with open(src, "rb") as a, open(dst, "rb") as b:
                        if a.read() == b.read():
                            continue
                    updated.append(rel)
                else:
                    added.append(rel)
                if not dry_run:
                    os.makedirs(os.path.dirname(dst), exist_ok=True)
                    shutil.copy2(src, dst)

        print(f"  upstream files: {len(updated)} changed, {len(added)} new, {skipped} protected (skipped)")
        for rel in sorted(added)[:40]:
            print(f"    + {rel}")
        for rel in sorted(updated)[:40]:
            print(f"    ~ {rel}")
        if len(added) + len(updated) > 80:
            print("    ... (truncated)")

    print("==> Re-applying overlay (Evidence Integrity Protocol + fetch-path fix)")
    import importlib.util
    spec = importlib.util.spec_from_file_location("apply_overlay", os.path.join(REPO_ROOT, "tools", "apply_overlay.py"))
    overlay = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(overlay)
    rc = overlay.apply(REPO_ROOT, check_only=dry_run)

    if not dry_run:
        meta["tag"] = tag
        meta["synced_utc"] = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d")
        with open(os.path.join(REPO_ROOT, "upstream.json"), "w", encoding="utf-8") as fh:
            json.dump(meta, fh, indent=2)
            fh.write("\n")
        print(f"==> upstream.json pinned to {tag}")

    if rc != 0:
        print("[!] Overlay reported a problem - review before committing.")
        return rc
    print("==> Done. Review `git diff`, run tests, then commit.")
    return 0


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="Sync this fork to an upstream Claude SEO version")
    ap.add_argument("--tag", help="upstream tag or branch (default: pinned tag in upstream.json)")
    ap.add_argument("--dry-run", action="store_true", help="show changes, write nothing")
    args = ap.parse_args()
    raise SystemExit(sync(args.tag, args.dry_run))
