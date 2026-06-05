"""
providers.py - registry of the API providers Claude SEO Pro onboards.

Each provider declares:
  id          : stable key, also the <id>.json config filename (unless config_file set)
  label       : human name shown in the wizard
  kind        : "secret" (default; prompt+validate+store keys, optional MCP)
                "google_oauth" (GSC/Indexing/GA4 via scripts/google_auth.py OAuth/SA)
                "gbp_oauth"   (Google Business Profile, business.manage, via onboarding/gbp_auth.py)
  deferrable  : True if the user may skip now and "attach later" (stores a pending marker)
  why         : one line on what it unlocks in the SEO system
  signup_url  : where the SEO manager creates the account / finds the key
  docs_url    : provider API docs
  fields      : ordered values to collect. Each field:
                  key      -> stored JSON key
                  prompt   -> wizard question
                  secret   -> mask input + treat as sensitive
                  env      -> environment variable for --from-env / non-interactive
                  optional -> blank is allowed (used by OAuth providers / property ids)
  config_file : optional filename override (e.g. google-oauth merges into google-api.json
                so scripts/google_auth.py reads default_property / ga4_property_id)
  oauth       : for kind in {google_oauth, gbp_oauth}: the auth + check commands to guide
  mcp         : optional MCP server spec to register in ~/.claude/settings.json
  notes       : free-form caveats surfaced after configuration

This is data, not logic. validate.py, configure_mcp.py, and setup_wizard.py consume it.
"""

from __future__ import annotations

GOOGLE_AUTH = "~/.claude/skills/seo/scripts/google_auth.py"
GBP_AUTH = "~/.claude/skills/seo/onboarding/gbp_auth.py"


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
        "kind": "secret",
        "why": "Off-site engine: live SERP, keyword research suite, backlinks/DR, business listings, AI mentions.",
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
        "label": "Google API key (PSI / CrUX)",
        "kind": "secret",
        "why": "Real Core Web Vitals field data (CrUX) + PageSpeed. Tier 0 = API key only.",
        "signup_url": "https://console.cloud.google.com/apis/credentials",
        "docs_url": "https://developers.google.com/speed/docs/insights/v5/get-started",
        "fields": [
            {"key": "api_key", "prompt": "Google API key (PageSpeed Insights + CrUX enabled)", "secret": True, "env": "GOOGLE_API_KEY"},
        ],
        "mcp": None,
        "notes": [
            "Tier 0 (API key) unlocks PageSpeed Insights, CrUX, and CrUX History.",
            "For Search Console / GA4, configure the 'Google Search Console + GA4' provider next.",
            "Enable 'PageSpeed Insights API' and 'Chrome UX Report API' on the key's project.",
        ],
    },
    {
        "id": "google-oauth",
        "label": "Google Search Console + Indexing + GA4 (OAuth)",
        "kind": "google_oauth",
        "deferrable": True,
        "config_file": "google-api",   # merge into the file scripts/google_auth.py reads
        "why": "Indexation status, search performance (clicks/impressions/CTR/position), and GA4 organic traffic.",
        "signup_url": "https://console.cloud.google.com/apis/credentials",
        "docs_url": "https://developers.google.com/webmaster-tools/v1/getting_started",
        "fields": [
            {"key": "client_secret_path", "prompt": "Path to Google OAuth client_secret.json (blank = attach later)", "secret": False, "env": "GOOGLE_CLIENT_SECRET", "optional": True},
            {"key": "default_property", "prompt": "GSC property, e.g. sc-domain:example.com (optional)", "secret": False, "env": "GSC_PROPERTY", "optional": True},
            {"key": "ga4_property_id", "prompt": "GA4 property id, e.g. properties/123456789 (optional)", "secret": False, "env": "GA4_PROPERTY_ID", "optional": True},
        ],
        "oauth": {
            "scopes": "webmasters.readonly + indexing + analytics.readonly",
            "auth_cmd": f"python {GOOGLE_AUTH} --auth --creds <client_secret.json>",
            "check_cmd": f"python {GOOGLE_AUTH} --check --json",
        },
        "mcp": None,
        "notes": [
            "Create an OAuth 'Desktop app' client in Google Cloud, download its client_secret.json.",
            "Grant the Google account access to the GSC property and GA4 property first.",
            "Alternatively use a service account: set service_account_path in google-api.json and "
            "grant it on the GSC/GA4 property.",
            "You can skip this now and run the auth step later; the audit degrades gracefully "
            "(CWV still uses CrUX field data; indexation/traffic sections are marked 'Data pending').",
        ],
    },
    {
        "id": "gbp",
        "label": "Google Business Profile API (OAuth, owner access)",
        "kind": "gbp_oauth",
        "deferrable": True,
        "why": "First-party local insights: profile completeness, searches/calls/direction-requests, posts, reviews.",
        "signup_url": "https://console.cloud.google.com/apis/credentials",
        "docs_url": "https://developers.google.com/my-business/content/overview",
        "fields": [
            {"key": "client_secret_path", "prompt": "Path to GBP OAuth client_secret.json (blank = attach later)", "secret": False, "env": "GBP_CLIENT_SECRET", "optional": True},
            {"key": "location", "prompt": "GBP location resource, e.g. locations/123 (optional)", "secret": False, "env": "GBP_LOCATION", "optional": True},
        ],
        "oauth": {
            "scopes": "https://www.googleapis.com/auth/business.manage",
            "auth_cmd": f"python {GBP_AUTH} --auth --creds <client_secret.json>",
            "check_cmd": f"python {GBP_AUTH} --check --json",
        },
        "mcp": None,
        "notes": [
            "Requires the 'Google Business Profile API' enabled on the project AND the OAuth "
            "account to have access to the business location (owner/manager).",
            "FALLBACK: if you can't grant owner access, skip this. Local SEO still runs via "
            "DataForSEO (the seo-maps skill) using public GBP/map-pack data.",
            "Attach later any time with:  python " + GBP_AUTH + " --auth --creds <client_secret.json>",
        ],
    },
    {
        "id": "firecrawl",
        "label": "Firecrawl",
        "kind": "secret",
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
        "kind": "secret",
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


def config_name(prov: dict) -> str:
    """The config filename a provider writes to (config_file override or id)."""
    return prov.get("config_file", prov["id"])


def kind(prov: dict) -> str:
    return prov.get("kind", "secret")
