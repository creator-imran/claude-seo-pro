"""Claude SEO Pro chat connector: run SEO tasks from Slack (and, later, WhatsApp).

A separate bridge service (NOT a Claude Code skill): a chat webhook verifies + authorizes
the request, maps it to a /seo command, runs it headlessly (claude -p, reusing the same
skills), and posts the result back. The runner is transport-agnostic so a WhatsApp adapter
can reuse it.

Modules:
  config        - loads slack.json (secrets) + connector.json (operating config)
  auth          - Slack HMAC signature verification + deny-by-default authorization
  commands      - parse a chat command -> skill + headless prompt
  runner        - execute headlessly (claude -p), with a testable dry-run plan
  slack_bridge  - the webhook (pure handle_slash() + thin HTTP server)
"""

__all__ = ["config", "auth", "commands", "runner", "slack_bridge"]
__version__ = "1.0.0"
