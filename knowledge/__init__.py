"""Claude SEO Pro knowledge layer: persistent client memory + computed-data cache.

Modules:
  store  - KnowledgeStore: per-client business understanding, learned facts, audit history.
           Survives model switches AND sessions (unlike the ephemeral prompt cache).
  cache  - DataCache: caches expensive API results on disk with TTL + provenance.
  fsutil - shared owner-only filesystem helpers (paths, perms, atomic writes).
"""

__all__ = ["store", "cache", "fsutil"]
__version__ = "1.0.0"
