#!/usr/bin/env python3
"""
branding.py - white-label configuration for client-facing reports.

Agencies reselling Claude SEO Pro can rebrand every audit report (cover, colors, footer,
preparer line, logo) WITHOUT editing the report template. Settings live in
~/.config/claude-seo/branding.json. If the file is absent, neutral product defaults apply.

    python branding.py show                      # current effective branding (JSON)
    python branding.py set --preparer "Acme SEO" --primary "#0b3d91" --accent "#c8102e"
    python branding.py set --logo "C:/path/logo.png" --footer "Acme Digital - confidential"
    python branding.py reset                      # back to defaults

Report generation reads this (or the JSON directly) and substitutes the {{BRAND_*}} /
{{PREPARER}} / {{LOGO}} / {{FOOTER}} tokens in assets/report-template.html.
"""
import sys, os, json, argparse

CONFIG_DIR = os.path.join(os.path.expanduser("~"), ".config", "claude-seo")
PATH = os.path.join(CONFIG_DIR, "branding.json")

DEFAULTS = {
    "brand_name": "Claude SEO Pro",
    "preparer": "Claude SEO Pro",          # the "Prepared by" line
    "primary_color": "#0b3d91",            # headings, score ring (CSS --brand)
    "accent_color": "#c8102e",             # eyebrow / critical accent (CSS --accent)
    "secondary_color": "#1466d6",          # links / gradient (CSS --brand2)
    "logo_path": "",                       # optional absolute path to a cover logo image
    "footer": "",                          # optional extra footer line (e.g. "Acme - confidential")
    "contact": "",                         # optional contact line under preparer
}

HEX = lambda s: isinstance(s, str) and s.startswith("#") and len(s) in (4, 7)

def load():
    """Effective branding = defaults overlaid with the user's file (validated)."""
    cfg = dict(DEFAULTS)
    if os.path.exists(PATH):
        try:
            user = json.load(open(PATH, encoding="utf-8"))
            for k in DEFAULTS:
                if k in user and user[k] not in (None, ""):
                    cfg[k] = user[k]
        except (OSError, json.JSONDecodeError):
            pass  # corrupt file → fall back to defaults silently (never break a report)
    # color sanity — bad hex falls back to default rather than breaking CSS
    for ck in ("primary_color", "accent_color", "secondary_color"):
        if not HEX(cfg[ck]):
            cfg[ck] = DEFAULTS[ck]
    return cfg

def save(updates):
    os.makedirs(CONFIG_DIR, exist_ok=True)
    current = {}
    if os.path.exists(PATH):
        try:
            current = json.load(open(PATH, encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            current = {}
    current.update({k: v for k, v in updates.items() if v is not None})
    with open(PATH, "w", encoding="utf-8") as f:
        json.dump(current, f, indent=2)
    return current

def main():
    ap = argparse.ArgumentParser(description="White-label branding for reports")
    sub = ap.add_subparsers(dest="cmd")
    sub.add_parser("show")
    s = sub.add_parser("set")
    s.add_argument("--brand-name"); s.add_argument("--preparer")
    s.add_argument("--primary"); s.add_argument("--accent"); s.add_argument("--secondary")
    s.add_argument("--logo"); s.add_argument("--footer"); s.add_argument("--contact")
    sub.add_parser("reset")
    args = ap.parse_args()

    if args.cmd == "set":
        upd = {"brand_name": args.brand_name, "preparer": args.preparer,
               "primary_color": args.primary, "accent_color": args.accent,
               "secondary_color": args.secondary, "logo_path": args.logo,
               "footer": args.footer, "contact": args.contact}
        save(upd)
        print(json.dumps(load(), indent=2))
    elif args.cmd == "reset":
        if os.path.exists(PATH):
            os.remove(PATH)
        print("[branding reset to defaults]")
        print(json.dumps(load(), indent=2))
    else:  # show / default
        eff = load()
        eff["_source"] = PATH if os.path.exists(PATH) else "defaults (no branding.json)"
        print(json.dumps(eff, indent=2))

if __name__ == "__main__":
    main()
