#!/usr/bin/env python3
"""
check_install.py - detect drift between the REPO and what's actually installed under
~/.claude. Run this from the repo after pulling changes.

Why this exists: a real audit once ran against a STALE installed skill because the
installer was never re-run after the repo gained new Pro features. The orchestrator
"knew" the new flow conceptually but the on-disk skill was old. This makes that
condition visible instead of silent.

It hashes the Pro-owned files in the repo and compares them to the corresponding files
under ~/.claude/skills/ and ~/.claude/agents/, reporting:
  ok       — installed matches the repo
  DRIFTED  — installed differs from the repo (re-run install to refresh)
  MISSING  — in the repo but not installed (re-run install)

Exit code: 0 if everything matches, 1 if any drift/missing — so it can gate.

    python tools/check_install.py            # human report
    python tools/check_install.py --json     # machine-readable
"""
import sys, os, json, hashlib, argparse

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HOME = os.path.expanduser("~")
SKILLS_ROOT = os.path.join(HOME, ".claude", "skills")
AGENTS_ROOT = os.path.join(HOME, ".claude", "agents")
SEO_SKILL = os.path.join(SKILLS_ROOT, "seo")   # shared engines install here

def h(path):
    try:
        with open(path, "rb") as f:
            return hashlib.md5(f.read()).hexdigest()
    except OSError:
        return None

def norm_hash(path):
    """Hash with line-endings normalized — installer copies may differ only by CRLF."""
    try:
        t = open(path, "rb").read().replace(b"\r\n", b"\n").replace(b"\r", b"\n").rstrip()
        return hashlib.md5(t).hexdigest()
    except OSError:
        return None

# (repo-relative-path, installed-absolute-path) for the Pro-owned surface
def pairs():
    out = []
    # skill dirs install to ~/.claude/skills/<name>/
    for name in ("seo-setup", "seo-knowledge", "seo-learn", "seo-models", "seo-connect", "seo-provider"):
        out.append((f"skills/{name}/SKILL.md", os.path.join(SKILLS_ROOT, name, "SKILL.md")))
    # the patched audit skill + its Pro references/assets
    out.append(("skills/seo-audit/SKILL.md", os.path.join(SKILLS_ROOT, "seo-audit", "SKILL.md")))
    for ref in ("business-intelligence.md", "audit-playbook.md", "keyword-research.md",
                "local-gbp-audit.md", "report-template.md"):
        out.append((f"skills/seo-audit/references/{ref}",
                    os.path.join(SKILLS_ROOT, "seo-audit", "references", ref)))
    out.append(("skills/seo-audit/assets/report-template.html",
                os.path.join(SKILLS_ROOT, "seo-audit", "assets", "report-template.html")))
    # owned agent
    out.append(("agents/seo-learn.md", os.path.join(AGENTS_ROOT, "seo-learn.md")))
    # engines install under ~/.claude/skills/seo/<pkg>/
    engines = {
        "onboarding": ["secure_store.py", "providers.py", "validate.py", "configure_mcp.py",
                       "setup_wizard.py", "gbp_auth.py", "branding.py"],
        "knowledge": ["fsutil.py", "store.py", "cache.py", "learn.py"],
        "routing": ["model_router.py"],
        "connector": ["config.py", "auth.py", "commands.py", "runner.py", "slack_bridge.py"],
    }
    for pkg, files in engines.items():
        for f in files:
            out.append((f"{pkg}/{f}", os.path.join(SEO_SKILL, pkg, f)))
    out.append(("scripts/keyword_research.py", os.path.join(SEO_SKILL, "scripts", "keyword_research.py")))
    # switcher installs from tools/ into the seo skill's scripts dir
    out.append(("tools/switch_provider.py", os.path.join(SEO_SKILL, "scripts", "switch_provider.py")))
    return out

def repo_version():
    try:
        return json.load(open(os.path.join(REPO, "system-version.json"), encoding="utf-8")).get("version")
    except Exception:
        return None

def run(as_json=False):
    ok = drifted = missing = 0
    details = []
    if not os.path.isdir(SKILLS_ROOT):
        msg = f"Nothing installed under {SKILLS_ROOT} — run install.ps1 / install.sh."
        print(json.dumps({"status": "not-installed", "message": msg}) if as_json else f"[NOT INSTALLED] {msg}")
        return 1
    for rel, inst in pairs():
        rp = os.path.join(REPO, rel)
        if not os.path.exists(rp):
            continue  # repo doesn't have it (shouldn't happen) — skip
        if not os.path.exists(inst):
            missing += 1; details.append(("MISSING", rel)); continue
        if norm_hash(rp) == norm_hash(inst):
            ok += 1
        else:
            drifted += 1; details.append(("DRIFTED", rel))
    status = "ok" if (drifted == 0 and missing == 0) else "drift"
    if as_json:
        print(json.dumps({"status": status, "repo_version": repo_version(),
                          "ok": ok, "drifted": drifted, "missing": missing,
                          "issues": [{"state": s, "file": f} for s, f in details]}, indent=2))
    else:
        print(f"Install check vs repo v{repo_version()}:  ok={ok}  DRIFTED={drifted}  MISSING={missing}")
        for s, f in details:
            print(f"  [{s}] {f}")
        if status == "ok":
            print("[INSTALL FRESH] installed skills match the repo.")
        else:
            print("[INSTALL STALE] re-run install.ps1 / install.sh to refresh ~/.claude.")
    return 0 if status == "ok" else 1

if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="Detect repo-vs-installed skill drift")
    ap.add_argument("--json", action="store_true")
    sys.exit(run(as_json=ap.parse_args().json))
