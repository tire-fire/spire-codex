"""Admin-tunable rate limits, per API-key tier.

The API's blanket cap normally falls back to a hardcoded ``300/minute`` per IP.
This makes that number, the on/off switch, and the per-tier caps editable at
runtime (no redeploy). Requests are bucketed by ``rate_limit_key``: a valid
``X-API-Key`` buckets by the key and uses its tier's cap; anything else buckets
by IP and uses the ``default_limit`` browse cap. Config lives in one Mongo doc so
all workers converge on it (each caches a few seconds); the counters stay
slowapi's per-worker in-memory ones, so this tunes the *limit*, not where the
counts live.

Endpoints with their own tighter ``@limiter.limit(...)`` (auth, feedback, guide
submission) keep those — those stay per-IP so a key can't buy past them.
"""

import logging
import os
import time

logger = logging.getLogger("spire-codex")

_COLLECTION = "app_config"
_DOC_ID = "rate_limit"
# Un-keyed browsing (the website + anonymous traffic), per IP.
_DEFAULT_LIMIT = "300/minute"
# Per API-key tier. Editable via /admin/rate-limits; keys default to registered.
_DEFAULT_TIERS = {
    "general": "15/minute",
    "registered": "60/minute",
    "academia": "100/minute",
    "paid": "120/minute",
}
# Effectively unlimited: what caps become when an operator toggles limiting off
# (per-endpoint limits still apply).
_DISABLED_LIMIT = "1000000/minute"
_CACHE_TTL_SECONDS = 15.0

_cache: dict = {"at": 0.0, "cfg": None}


def _coll():
    from .runs_db_mongo import _get_collection

    return _get_collection().database[_COLLECTION]


def _fallback() -> dict:
    return {
        "default_limit": _DEFAULT_LIMIT,
        "tiers": dict(_DEFAULT_TIERS),
        "enabled": True,
    }


def get_config() -> dict:
    """The current {default_limit, tiers, enabled}, cached per worker so a read
    on the hot rate-limit path is cheap. Falls back to the built-in defaults on
    any trouble so limiting never breaks."""
    if not os.environ.get("MONGO_URL", "").strip():
        return _fallback()
    now = time.monotonic()
    cached = _cache["cfg"]
    if cached is not None and now - _cache["at"] < _CACHE_TTL_SECONDS:
        return cached
    cfg = _fallback()
    try:
        doc = _coll().find_one({"_id": _DOC_ID})
        if doc:
            tiers = dict(_DEFAULT_TIERS)
            tiers.update(
                {k: v for k, v in (doc.get("tiers") or {}).items() if k in tiers}
            )
            cfg = {
                "default_limit": doc.get("default_limit") or _DEFAULT_LIMIT,
                "tiers": tiers,
                "enabled": bool(doc.get("enabled", True)),
            }
    except Exception:
        logger.warning("rate-limit config read failed", exc_info=True)
    _cache["cfg"] = cfg
    _cache["at"] = now
    return cfg


def rate_limit_key(request) -> str:
    """slowapi ``key_func``: the counter bucket for this request, which also
    carries the tier as a ``tier|domain`` prefix. A valid X-API-Key buckets by
    the key ("<tier>|k:<id>"); everything else buckets by IP ("browse|<ip>").
    Memoized on request.state since slowapi calls this more than once."""
    cached = getattr(request.state, "_rl_bucket", None)
    if cached is not None:
        return cached
    bucket = None
    raw = request.headers.get("x-api-key")
    if raw:
        from . import api_key_service

        info = api_key_service.resolve(raw.strip())
        if info:
            bucket = f"{info['tier']}|k:{info['key_id']}"
    if bucket is None:
        from ..dependencies import client_ip

        bucket = f"browse|{client_ip(request)}"
    try:
        request.state._rl_bucket = bucket
    except Exception:
        pass
    return bucket


def _limit_for_tier(tier: str, cfg: dict) -> str:
    if tier == "browse" or tier not in _DEFAULT_TIERS:
        return cfg.get("default_limit") or _DEFAULT_LIMIT
    tiers = cfg.get("tiers") or _DEFAULT_TIERS
    return tiers.get(tier) or cfg.get("default_limit") or _DEFAULT_LIMIT


def tier_limit_value(key: str = "browse") -> str:
    """slowapi ``default_limits`` callable. slowapi passes it ``rate_limit_key``'s
    output, whose ``tier|...`` prefix selects the cap. Re-read (cached) per
    request so admin changes take effect within the cache window. Effectively
    unlimited when limiting is toggled off."""
    cfg = get_config()
    if not cfg.get("enabled", True):
        return _DISABLED_LIMIT
    tier = (key or "browse").split("|", 1)[0]
    return _limit_for_tier(tier, cfg)


# Back-compat: the browse cap on its own (a handy helper; the limiter uses
# tier_limit_value now).
def default_limit_value(*_args, **_kwargs) -> str:
    cfg = get_config()
    if not cfg.get("enabled", True):
        return _DISABLED_LIMIT
    return cfg.get("default_limit") or _DEFAULT_LIMIT


def _validate_limit(value: str, field: str) -> str:
    from limits import parse

    candidate = value.strip()
    try:
        parse(candidate)
    except Exception as exc:
        raise ValueError(
            f"'{value}' is not a valid {field} limit (try e.g. 300/minute)"
        ) from exc
    return candidate


def set_config(
    default_limit: str | None = None,
    enabled: bool | None = None,
    tiers: dict | None = None,
) -> dict:
    """Update the config. Validates every limit string and raises ValueError on a
    bad one. Busts the local cache immediately; other workers pick it up within
    the cache window."""
    if not os.environ.get("MONGO_URL", "").strip():
        raise ValueError("rate-limit config needs MONGO_URL")
    current = get_config()
    new = {
        "default_limit": current["default_limit"],
        "tiers": dict(current["tiers"]),
        "enabled": current["enabled"],
    }
    if default_limit is not None:
        new["default_limit"] = _validate_limit(default_limit, "browse")
    if tiers is not None:
        for name, value in tiers.items():
            if name not in _DEFAULT_TIERS:
                raise ValueError(f"unknown tier '{name}'")
            new["tiers"][name] = _validate_limit(value, name)
    if enabled is not None:
        new["enabled"] = bool(enabled)
    _coll().replace_one({"_id": _DOC_ID}, {"_id": _DOC_ID, **new}, upsert=True)
    _cache["cfg"] = None
    return new
