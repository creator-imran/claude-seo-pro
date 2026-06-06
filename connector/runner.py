"""
runner.py - execute a parsed command as a HEADLESS SEO run, reusing the same /seo skills.

Default backend = "claude-cli": shell out to Claude Code in non-interactive print mode
(`claude -p "<prompt>"`), so the connector runs the exact same skills a manager uses in
the terminal — no agent loop to reimplement, no SDK signatures to guess. The model can
be pinned (the orchestration tier is Opus by the Feature-3 router); permissions run in a
non-interactive mode so the headless run doesn't block on prompts.

`build_cli_command()` is pure and unit-testable. `run()` actually executes; `plan()` (or
dry_run=True) returns the exact command + env expectations WITHOUT executing — so the
plumbing is verifiable here even though a live headless run needs Claude Code installed,
an API key, and network (which is why the live path is a documented integration point,
not asserted as validated).

Stdlib only.
"""

from __future__ import annotations

import json
import shlex
import subprocess

try:
    from . import config
except ImportError:
    import config


def build_cli_command(parsed: dict, cfg: dict = None) -> list:
    """Construct the headless Claude Code invocation. Pure — no execution."""
    cfg = cfg or config.connector()
    cmd = [cfg.get("claude_bin", "claude"), "-p", parsed["prompt"],
           "--output-format", "json"]
    if cfg.get("model"):
        cmd += ["--model", cfg["model"]]
    # Non-interactive: the headless run must not block waiting for permission prompts.
    # Operator chooses the posture in connector.json (default: acceptEdits is safe-ish;
    # bypassPermissions only if they trust the command surface).
    mode = cfg.get("permission_mode", "acceptEdits")
    if mode:
        cmd += ["--permission-mode", mode]
    return cmd


def plan(parsed: dict, cfg: dict = None) -> dict:
    """What run() would do, without doing it (testable, no execution)."""
    cfg = cfg or config.connector()
    cmd = build_cli_command(parsed, cfg)
    return {
        "action": parsed["action"], "skill": parsed["skill"], "target": parsed["target"],
        "backend": cfg.get("run_backend", "claude-cli"),
        "command": cmd, "command_str": " ".join(shlex.quote(c) for c in cmd),
        "timeout_seconds": cfg.get("timeout_seconds", 1800),
        "note": "Live execution requires Claude Code installed + an API key. This is the plan only.",
    }


def run(parsed: dict, cfg: dict = None, dry_run: bool = False) -> dict:
    """Execute the headless run. Returns {ok, action, summary, raw, error}."""
    cfg = cfg or config.connector()
    if dry_run:
        return {"ok": True, "dry_run": True, "plan": plan(parsed, cfg)}
    backend = cfg.get("run_backend", "claude-cli")
    if backend != "claude-cli":
        return {"ok": False, "error": f"unsupported run_backend '{backend}'"}
    cmd = build_cli_command(parsed, cfg)
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True,
                              timeout=cfg.get("timeout_seconds", 1800))
    except FileNotFoundError:
        return {"ok": False, "error": f"'{cmd[0]}' not found — install Claude Code on the connector host"}
    except subprocess.TimeoutExpired:
        return {"ok": False, "error": f"run timed out after {cfg.get('timeout_seconds', 1800)}s"}
    if proc.returncode != 0:
        return {"ok": False, "error": (proc.stderr or "non-zero exit")[:500]}
    out = proc.stdout.strip()
    summary = out
    try:
        parsed_out = json.loads(out)
        summary = parsed_out.get("result") or parsed_out.get("text") or out
    except json.JSONDecodeError:
        pass
    return {"ok": True, "action": parsed["action"], "summary": summary[:3000], "raw_len": len(out)}


def format_for_chat(result: dict, parsed: dict) -> str:
    """Render a run result as a chat message."""
    if result.get("dry_run"):
        p = result["plan"]
        return f":mag: *Plan* for `{p['action']} {p['target']}`\n```{p['command_str']}```\n_{p['note']}_"
    if not result.get("ok"):
        return f":x: `{parsed['action']} {parsed['target']}` failed: {result.get('error', 'unknown error')}"
    return (f":white_check_mark: *{parsed['action']}* complete for `{parsed['target']}`\n\n"
            f"{result.get('summary', '(no summary)')}")
