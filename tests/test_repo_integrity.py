#!/usr/bin/env python3
"""
Repo integrity gate for CI (and local pre-push). Cross-platform, stdlib only.
  1. Every .py compiles (ours + vendored upstream)
  2. Every .json parses
  3. No real-secret patterns in any tracked-ish file
  4. No client-data / credential files committed in the tree
Exits non-zero on any failure.
    python tests/test_repo_integrity.py
"""
import sys, os, json, re, py_compile

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FAILS = []

SKIP_DIRS = {".git", "__pycache__", ".github", "node_modules", ".venv", "venv"}
# Real-key shapes only (not placeholders/regex-source). Tuned to avoid false positives
# in doc/code that *describes* these patterns.
SECRET_PATTERNS = [
    (re.compile(r"\bAIzaSy[0-9A-Za-z_\-]{33}\b"), "Google API key"),
    (re.compile(r"\bxoxb-[0-9]{8,}-[0-9A-Za-z]+"), "Slack bot token"),
    (re.compile(r"\bsk-ant-[a-zA-Z0-9]{20,}"), "Anthropic key"),
    (re.compile(r"\bghp_[0-9A-Za-z]{36}\b"), "GitHub PAT"),
]
# files allowed to contain pattern-like strings (they document/scan for them)
SECRET_ALLOWLIST = {
    "knowledge/learn.py", "tests/test_owned_components.py", "tests/test_repo_integrity.py",
    "onboarding/validate.py", "docs/WHATS-DIFFERENT.md", "VERSION.md",
}
CLIENT_DATA_NAMES = re.compile(
    r"^(slack|connector|model-policy|dataforseo|firecrawl|exa|google-api|gbp|backlinks-api)\.json$"
    r"|^(facts|history)\.jsonl$")
TEXT_EXT = {".py", ".md", ".json", ".txt", ".yml", ".yaml", ".html", ".sh", ".ps1", ".js"}

def walk():
    for root, dirs, files in os.walk(REPO):
        dirs[:] = [d for d in dirs if d not in SKIP_DIRS]
        for f in files:
            full = os.path.join(root, f)
            rel = os.path.relpath(full, REPO).replace("\\", "/")
            yield full, rel, f

py = jsonf = scanned = 0
for full, rel, name in walk():
    ext = os.path.splitext(name)[1].lower()
    if ext == ".py":
        py += 1
        try:
            py_compile.compile(full, doraise=True)
        except py_compile.PyCompileError as e:
            FAILS.append(f"compile: {rel}: {e}")
    if ext == ".json":
        jsonf += 1
        try:
            with open(full, encoding="utf-8") as fh:
                json.load(fh)
        except Exception as e:
            FAILS.append(f"json: {rel}: {e}")
    if CLIENT_DATA_NAMES.match(name) and "clients/" not in rel and "cache/" not in rel:
        # any client-data / credential file physically committed is a hard fail
        FAILS.append(f"client-data file committed: {rel}")
    if ("/clients/" in "/" + rel) or ("/cache/" in "/" + rel):
        FAILS.append(f"client-data dir committed: {rel}")
    if ext in TEXT_EXT and rel not in SECRET_ALLOWLIST:
        scanned += 1
        try:
            text = open(full, encoding="utf-8", errors="replace").read()
        except OSError:
            continue
        for pat, label in SECRET_PATTERNS:
            if pat.search(text):
                FAILS.append(f"secret ({label}) in {rel}")

print(f"compiled {py} .py | validated {jsonf} .json | secret-scanned {scanned} files")
if FAILS:
    print(f"\n[INTEGRITY FAIL] {len(FAILS)} issue(s):")
    for f in FAILS:
        print("  - " + f)
    sys.exit(1)
print("[INTEGRITY OK]")
sys.exit(0)
