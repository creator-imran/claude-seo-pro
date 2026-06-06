#!/usr/bin/env bash
set -euo pipefail

# Claude SEO Pro - Self-contained installer (macOS / Linux)
# Installs vendored skills, agents, scripts, and the onboarding wizard from THIS repo
# into ~/.claude, then offers guided API onboarding.
#
# Usage:
#   bash install.sh
#   bash install.sh --no-onboard   # skip the wizard

main() {
  local NO_ONBOARD=0
  [[ "${1:-}" == "--no-onboard" ]] && NO_ONBOARD=1

  local REPO_ROOT
  REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

  echo "========================================"
  echo "|  Claude SEO Pro - Installer          |"
  echo "|  Evidence-verified SEO for Claude    |"
  echo "========================================"
  echo

  # Resolve Python
  local PY=""
  if command -v python3 >/dev/null 2>&1; then PY="python3";
  elif command -v python >/dev/null 2>&1; then PY="python";
  else echo "[x] Python 3.10+ is required but was not found."; exit 1; fi
  echo "[+] $($PY --version) detected"

  if command -v node >/dev/null 2>&1; then
    echo "[+] Node.js detected (MCP servers available)"
  else
    echo "[!] Node.js not found - DataForSEO/Firecrawl/Exa MCP servers need it (https://nodejs.org)"
  fi

  local SKILLS_ROOT="$HOME/.claude/skills"
  local SKILL_DIR="$SKILLS_ROOT/seo"
  local AGENT_DIR="$HOME/.claude/agents"
  mkdir -p "$SKILL_DIR" "$AGENT_DIR"

  echo "=> Installing skills..."
  for d in "$REPO_ROOT"/skills/*/; do
    [ -d "$d" ] || continue
    local name; name="$(basename "$d")"
    mkdir -p "$SKILLS_ROOT/$name"
    cp -R "$d"* "$SKILLS_ROOT/$name/"
  done

  echo "=> Installing agents..."
  [ -d "$REPO_ROOT/agents" ] && cp -f "$REPO_ROOT"/agents/*.md "$AGENT_DIR/" 2>/dev/null || true

  echo "=> Installing shared scripts and resources..."
  for d in scripts hooks schema pdf; do
    if [ -d "$REPO_ROOT/$d" ]; then
      mkdir -p "$SKILL_DIR/$d"; cp -R "$REPO_ROOT/$d/"* "$SKILL_DIR/$d/"
    fi
  done

  echo "=> Installing onboarding wizard..."
  mkdir -p "$SKILL_DIR/onboarding"
  cp -R "$REPO_ROOT/onboarding/"* "$SKILL_DIR/onboarding/"

  echo "=> Installing knowledge layer..."
  mkdir -p "$SKILL_DIR/knowledge"
  cp -R "$REPO_ROOT/knowledge/"* "$SKILL_DIR/knowledge/"

  echo "=> Installing routing layer..."
  mkdir -p "$SKILL_DIR/routing"
  cp -R "$REPO_ROOT/routing/"* "$SKILL_DIR/routing/"

  echo "=> Installing connector..."
  mkdir -p "$SKILL_DIR/connector"
  cp -R "$REPO_ROOT/connector/"* "$SKILL_DIR/connector/"

  if [ -d "$REPO_ROOT/extensions" ]; then
    echo "=> Installing extensions..."
    for ext in "$REPO_ROOT"/extensions/*/; do
      [ -d "$ext" ] || continue
      local extName; extName="$(basename "$ext")"
      if [ -d "$ext/skills" ]; then
        for s in "$ext"/skills/*/; do
          [ -d "$s" ] || continue
          local sn; sn="$(basename "$s")"; mkdir -p "$SKILLS_ROOT/$sn"; cp -R "$s"* "$SKILLS_ROOT/$sn/"
        done
      fi
      [ -d "$ext/agents" ] && cp -f "$ext"/agents/*.md "$AGENT_DIR/" 2>/dev/null || true
      for sub in references scripts; do
        if [ -d "$ext/$sub" ]; then
          mkdir -p "$SKILL_DIR/extensions/$extName/$sub"; cp -R "$ext/$sub/"* "$SKILL_DIR/extensions/$extName/$sub/"
        fi
      done
    done
  fi

  # --- Install manifest (version stamp for drift detection) ---
  VER="$("$PY" -c "import json;print(json.load(open('$REPO_ROOT/system-version.json')).get('version','unknown'))" 2>/dev/null || echo unknown)"
  mkdir -p "$HOME/.config/claude-seo"
  printf '{\n  "pro_version": "%s",\n  "installed_utc": "%s",\n  "source": "%s"\n}\n' \
    "$VER" "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$REPO_ROOT" > "$HOME/.config/claude-seo/install-manifest.json"
  echo "=> Stamped install manifest (v$VER)"

  if [ -f "$REPO_ROOT/requirements.txt" ]; then
    echo "=> Installing Python dependencies..."
    cp -f "$REPO_ROOT/requirements.txt" "$SKILL_DIR/requirements.txt"
    "$PY" -m pip install -q -r "$REPO_ROOT/requirements.txt" || \
      echo "  [!] Could not auto-install. Run: $PY -m pip install -r \"$SKILL_DIR/requirements.txt\""
  fi

  echo
  echo "[+] Claude SEO Pro installed."
  echo

  if [ "$NO_ONBOARD" -eq 1 ]; then
    echo "Onboarding skipped. Run it any time:"
    echo "  $PY \"$SKILL_DIR/onboarding/setup_wizard.py\""
  else
    echo "Next: configure your API keys (DataForSEO, Google, Firecrawl, Exa)."
    read -r -p "Run the guided onboarding wizard now? [Y/n] " ans
    if [[ ! "$ans" =~ ^([nN][oO]?)$ ]]; then
      "$PY" "$SKILL_DIR/onboarding/setup_wizard.py"
    else
      echo "  Run later with:  $PY \"$SKILL_DIR/onboarding/setup_wizard.py\""
      echo "  Or inside Claude Code:  /seo-setup"
    fi
  fi

  echo
  echo "Then start Claude Code and run:"
  echo "  /seo-setup verify              # confirm everything is wired"
  echo "  /seo audit https://example.com # first audit"
  echo
}

main "$@"
