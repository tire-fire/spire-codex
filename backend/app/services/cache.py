"""Fail-safe Redis application cache.

A thin JSON get/set layer in front of the hot read endpoints (issue #388).
The cache is always an optimization, never load-bearing:

- `REDIS_URL` unset -> every call no-ops without importing redis at all,
  so bare-metal dev keeps working with zero new dependencies in play.
- Redis down, slow, or throwing -> `get_json` returns None (a miss) and
  writes no-op. Socket timeouts are short (250ms) so a *hung* Redis
  degrades exactly like a *down* one instead of adding latency.
- Values are JSON: everything cached here is already a JSON-serializable
  API response.

Keys are namespaced as "<namespace>:<rest>" (e.g. "run:<hash>",
"entity_scores:relics:act2"); the namespace becomes the Prometheus label on
the hit/miss/error counters.

Connections are per-process (uvicorn workers each hold one client), pooled
by redis-py internally.
"""

from __future__ import annotations

import json
import logging
import os
from typing import Any

from ..metrics import cache_errors, cache_hits, cache_misses

logger = logging.getLogger(__name__)

_REDIS_URL = os.environ.get("REDIS_URL", "").strip()
# Short enough that a wedged Redis costs ~250ms once per call site, not
# request-queue pileups. redis-py raises TimeoutError, which we treat as
# any other error: count it and miss.
_SOCKET_TIMEOUT_SECONDS = 0.25

_client: Any = None
_client_init_failed = False


def _namespace(key: str) -> str:
    return key.split(":", 1)[0]


def _get_client() -> Any:
    """Lazy per-process client; None when disabled or construction failed."""
    global _client, _client_init_failed
    if not _REDIS_URL or _client_init_failed:
        return None
    if _client is None:
        try:
            import redis

            _client = redis.Redis.from_url(
                _REDIS_URL,
                socket_timeout=_SOCKET_TIMEOUT_SECONDS,
                socket_connect_timeout=_SOCKET_TIMEOUT_SECONDS,
                decode_responses=True,
            )
        except Exception:
            # Bad URL or redis-py missing: disable for this process rather
            # than retrying (and logging) on every request.
            logger.warning(
                "app cache disabled: redis client init failed", exc_info=True
            )
            _client_init_failed = True
            return None
    return _client


def enabled() -> bool:
    """True when a cache backend is configured (not necessarily reachable)."""
    return bool(_REDIS_URL) and not _client_init_failed


def get_json(key: str) -> Any:
    """Cached value for `key`, or None on miss/disabled/error."""
    client = _get_client()
    if client is None:
        return None
    ns = _namespace(key)
    try:
        raw = client.get(key)
    except Exception:
        cache_errors.labels(namespace=ns, operation="get").inc()
        return None
    if raw is None:
        cache_misses.labels(namespace=ns).inc()
        return None
    try:
        value = json.loads(raw)
    except ValueError:
        cache_errors.labels(namespace=ns, operation="decode").inc()
        return None
    cache_hits.labels(namespace=ns).inc()
    return value


def set_json(key: str, value: Any, ttl_seconds: int) -> None:
    """Store `value` under `key` for `ttl_seconds`. No-ops on any failure."""
    client = _get_client()
    if client is None:
        return
    try:
        client.set(key, json.dumps(value), ex=ttl_seconds)
    except Exception:
        cache_errors.labels(namespace=_namespace(key), operation="set").inc()


def delete(key: str) -> None:
    """Drop one key. No-ops on any failure."""
    client = _get_client()
    if client is None:
        return
    try:
        client.delete(key)
    except Exception:
        cache_errors.labels(namespace=_namespace(key), operation="delete").inc()


def delete_pattern(pattern: str) -> int:
    """Drop every key matching a glob pattern (SCAN-based, non-blocking).

    For deploy-time invalidation of long-TTL namespaces, e.g.
    delete_pattern("entity_scores:*"). Returns keys deleted (0 on failure).
    """
    client = _get_client()
    if client is None:
        return 0
    deleted = 0
    try:
        for batch_key in client.scan_iter(match=pattern, count=500):
            client.delete(batch_key)
            deleted += 1
    except Exception:
        cache_errors.labels(
            namespace=_namespace(pattern), operation="delete_pattern"
        ).inc()
    return deleted
