"""Claude SEO Pro routing layer: dispatch-time model-routing policy.

model_router - assigns the cheapest capable model per task tier (Haiku extraction,
Sonnet reasoning/verification, Opus synthesis/orchestration). A policy the orchestrator
consults per dispatch — NOT a daemon. Keeps the main loop fixed to preserve the prompt
cache; routes only sub-work to cheaper tiers.
"""

__all__ = ["model_router"]
__version__ = "1.0.0"
