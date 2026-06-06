"""
commands.py - map a chat command to a headless SEO run.

A Slack slash command arrives as `command="/seo"` + `text="audit https://x.com"`.
We parse the first word as the action and the rest as the target, validate it against
the operator's enabled_commands, and produce a natural-language PROMPT that reliably
triggers the right skill in a headless `claude -p` run (more robust than relying on
slash-command parsing inside print mode).

Stdlib only — fully unit-testable.
"""

from __future__ import annotations

import re

# action -> (skill, needs_target, prompt template). {target} is the URL/keyword.
ACTIONS = {
    "audit":   ("seo-audit",   True,  "Run a full SEO audit on {target} using the seo-audit skill. "
                                      "Read the client knowledge store first, follow the 4-phase Pro "
                                      "pipeline, and produce the report and action plan."),
    "page":    ("seo-page",    True,  "Run a deep single-page SEO analysis on {target}."),
    "schema":  ("seo-schema",  True,  "Detect, validate, and report Schema.org structured data on {target}."),
    "geo":     ("seo-geo",     True,  "Assess AI-search / GEO readiness for {target}."),
    "local":   ("seo-local",   True,  "Run a local SEO analysis for {target} (GBP, NAP, reviews, local schema)."),
    "keyword": ("seo-audit",   True,  "Run the multi-locale keyword research for {target} "
                                      "(seed expansion, volume/CPC/KD/intent, opportunity tiers)."),
    "technical": ("seo-technical", True, "Run a technical SEO audit on {target}."),
    "content": ("seo-content", True,  "Run a content quality / E-E-A-T analysis on {target}."),
    "recall":  ("seo-knowledge", True, "Recall what we know about the client {target} from the knowledge store."),
}

URL_RE = re.compile(r"^(https?://)?([a-z0-9-]+\.)+[a-z]{2,}(/\S*)?$", re.I)


def parse_command(text: str, enabled=None):
    """Return (parsed, error). parsed = {action, skill, target, prompt} or None on error."""
    text = (text or "").strip()
    if not text:
        return None, "empty command — try: audit https://example.com"
    parts = text.split(None, 1)
    action = parts[0].lower().lstrip("/")
    target = parts[1].strip() if len(parts) > 1 else ""

    if action not in ACTIONS:
        return None, f"unknown command '{action}'. Known: {', '.join(sorted(ACTIONS))}"
    if enabled is not None and action not in enabled:
        return None, f"command '{action}' is not enabled by the operator"

    skill, needs_target, template = ACTIONS[action]
    if needs_target and not target:
        return None, f"'{action}' needs a target, e.g. {action} https://example.com"
    # light validation for URL-style targets (recall/keyword may take a name)
    if needs_target and action in ("audit", "page", "schema", "geo", "local", "technical", "content"):
        if not URL_RE.match(target):
            return None, f"'{target}' doesn't look like a URL/domain"

    prompt = template.format(target=target) if needs_target else template
    return {"action": action, "skill": skill, "target": target, "prompt": prompt}, None
