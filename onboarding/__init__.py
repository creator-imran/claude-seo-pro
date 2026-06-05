"""Claude SEO Pro onboarding package: guided, secure API setup.

Modules:
  secure_store  - owner-only credential storage under ~/.config/claude-seo/
  providers     - registry of onboarded API providers
  validate      - live connectivity checks per provider
  configure_mcp - safe-merge MCP servers into ~/.claude/settings.json
  setup_wizard  - the guided CLI (entry point)
"""

__all__ = ["secure_store", "providers", "validate", "configure_mcp", "setup_wizard"]
__version__ = "1.0.0"
