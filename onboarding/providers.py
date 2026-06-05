"""
providers.py - registry of the API providers Claude SEO Pro onboards.

Each provider declares:
  id          : stable key, also the <id>.json config filename
  label       : human name shown in the wizard
  why         : one line on what it unlocks in the SEO system
  signup_url  : where the SEO manager creates the account / finds the key
  docs_url    : provider API docs
  fields      : ordered credentials to collect. Each field:
                  key     -> stored JSON key
                  prompt  -> wizard question
                  secret  -> mask input + treat as sensitive
                  env     -> environment variable for --from-env / non-interactive
  mcp         : optional MCP server spec to register in ~/.claude/settings.json
                (name + a builder that maps the stored config to an mcpServers entry)
  notes       : free-form caveats surfaced after configuration (e.g. IP whitelist)

This is data, not logic. validate.py and configure_mcp.py consume it.
"""

from __future__ import annotations


def _dataforseo_mcp(cfg: dict) -> dict:
    return {
        "command": "npx",
        "args": ["-y", "dataforseo-mcp-server"],
        "env": {
            "DATAFORSEO_USERNAME": cfg.get("username", ""),
            "DATAFORSEO_PASSWORD": cfg.get("password", ""),
            "ENABLED_MODULES": (
                "SERP,KEYWORDS_DATA,ONPAGE,DATAFORSEO_LABS,BACKLINKS,"
                "DOMAIN_ANALYTICS,BUSINESS_DATA,CONTENT_ANALYSIS,AI_OPTIMIZATION"
            ),
        },
    }


def _firecrawl_mcp(cfg: dict) -> dict:
    return {
        "command": "npx",
        "args": ["-y", "firecrawl-mcp"],
        "env": {"FIRECRAWL_API_KEY": cfg.get("api_key", "")},
    }


def _exa_mcp(cfg: dict) -> dict:
    return {
        "command": "npx",
        "args": ["-y", "exa-mcp-server"],
        "env": {"EXA_API_KEY": cfg.get("api_key", "")},
    }


PROVIDERS = [
    {
        "id": "dataforseo",
        "label": "DataForSEO",
        "why": "Off-site engine: live SERP positions, backlinks/DR, business listings, AI-mention tracking.",
        "signup_url": "https://app.dataforseo.com/register",
        "docs_url": "https://docs.dataforseo.com/v3/",
        "fields": [
            {"key": "username", "prompt": "DataForSEO login email", "secret": False, "env": "DATAFORSEO_USERNAME"},
            {"key": "password", "prompt": "DataForSEO API password", "secret": True, "env": "DATAFORSEO_PASSWORD"},
        ],
        "mcp": {"name": "dataforseo", "builder": _dataforseo_mcp},
        "notes": [
            "If data endpoints return 40207 'IP not whitelisted', add this machine's "
            "public IP at https://app.dataforseo.com/api-access (or disable the whitelist).",
            "Account-status calls work without whitelisting; data calls do not.",
        ],
    },
    {
        "id": "google-api",
        "label": "Google APIs (PSI / CrUX / GSC / GA4)",
        "why": "Real Core Web Vitals field data, indexation status, and organic traffic. Tier 0 = API key only.",
        "signup_url": "https://console.cloud.google.com/apis/credentials",
        "docs_url": "https://developers.google.com/speed/docs/insights/v5/get-started",
        "fields": [
            {"key": "api_key", "prompt": "Google API key (PageSpeed Insights + CrUX enabled)", "secret": True, "env": "GOOGLE_API_KEY"},
        ],
        # No MCP: Google APIs are called by the bundled scripts/*.py (pagespeed_check.py etc.)
        "mcp": None,
        "notes": [
            "Tier 0 (API key) unlocks PageSpeed Insights, CrUX, and CrUX History.",
            "Higher tiers (Search Console, Indexing, GA4) need OAuth/Service Account; "
            "run `/seo google setup` after onboarding to add them.",
            "Enable 'PageSpeed Insights API' and 'Chrome UX Report API' on the key's project.",
        ],
    },
    {
        "id": "firecrawl",
        "label": "Firecrawl",
        "why": "Full-site crawling, JS rendering, and large-site URL discovery beyond the built-in fetcher.",
        "signup_url": "https://www.firecrawl.dev/app/api-keys",
        "docs_url": "https://docs.firecrawl.dev/",
        "fields": [
            {"key": "api_key", "prompt": "Firecrawl API key (starts with fc-)", "secret": True, "env": "FIRECRAWL_API_KEY"},
        ],
        "mcp": {"name": "firecrawl", "builder": _firecrawl_mcp},
        "notes": [
            "Crawls consume Firecrawl credits; large sites can be costly. The audit "
            "honors the existing 30-page warning / 50-page hard-stop guardrails.",
        ],
    },
    {
        "id": "exa",
        "label": "Exa",
        "why": "Neural/semantic web search for competitor discovery, entity research, and citation sourcing.",
        "signup_url": "https://dashboard.exa.ai/api-keys",
        "docs_url": "https://docs.exa.ai/",
        "fields": [
            {"key": "api_key", "prompt": "Exa API key", "secret": True, "env": "EXA_API_KEY"},
        ],
        "mcp": {"name": "exa", "builder": _exa_mcp},
        "notes": [
            "Exa search calls are metered per request; the wizard validation uses a "
            "single 1-result query.",
        ],
    },
]


def by_id(provider_id: str) -> dict | None:
    for p in PROVIDERS:
        if p["id"] == provider_id:
            return p
    return None


def ids() -> list[str]:
    return [p["id"] for p in PROVIDERS]
