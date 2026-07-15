"""Per-key daily usage counters.

Every request carrying a valid X-API-Key bumps a per-key per-day counter so the
admin keys page can show who's actually consuming the API. Increments buffer
in-process and flush as batched $inc upserts (time- or size-triggered), so the
request path never waits on Mongo: worst case a worker restart loses a few
seconds of counts, which is fine for usage accounting. Browse (un-keyed)
traffic is deliberately NOT tracked per-identity — that would mean per-IP
counters — only in the aggregate Prometheus tier metric.

Documents: {_id: "<key_id>:<YYYY-MM-DD>", key_id, day, count, ts} with a TTL on
ts so the collection trims itself after the retention window.
"""

import logging
import os
import threading
import time
from datetime import datetime, timezone

logger = logging.getLogger("spire-codex")

USAGE_COLLECTION = "api_key_usage"
_RETENTION_DAYS = 90
_FLUSH_SECONDS = 10.0
_FLUSH_MAX_BUFFER = 500

_lock = threading.Lock()
_buffer: dict[tuple[str, str], int] = {}  # (key_id, day) -> pending count
_last_flush = 0.0
_indexed = False


def _coll():
    from .runs_db_mongo import _get_collection

    col = _get_collection().database[USAGE_COLLECTION]
    global _indexed
    if not _indexed:
        try:
            col.create_index(
                "ts", expireAfterSeconds=_RETENTION_DAYS * 86400, name="ttl_ts"
            )
            col.create_index([("key_id", 1), ("day", -1)])
            _indexed = True
        except Exception:
            logger.warning("api-key usage index setup failed", exc_info=True)
    return col


def record(key_id: str) -> None:
    """Count one request for a key. Buffers in-process; flushes when the buffer
    is old or large. Never raises — usage accounting must not break requests."""
    if not key_id or not os.environ.get("MONGO_URL", "").strip():
        return
    try:
        day = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        now = time.monotonic()
        to_flush: dict[tuple[str, str], int] | None = None
        global _last_flush
        with _lock:
            _buffer[(key_id, day)] = _buffer.get((key_id, day), 0) + 1
            if (
                now - _last_flush >= _FLUSH_SECONDS
                or sum(_buffer.values()) >= _FLUSH_MAX_BUFFER
            ):
                to_flush = dict(_buffer)
                _buffer.clear()
                _last_flush = now
        if to_flush:
            # Off the request path: the unlucky request that trips the flush
            # shouldn't pay for the bulk write either.
            threading.Thread(
                target=_flush_safe, args=(to_flush,), daemon=True, name="key-usage"
            ).start()
    except Exception:
        logger.warning("api-key usage record failed", exc_info=True)


def _flush_safe(items: dict[tuple[str, str], int]) -> None:
    try:
        _flush(items)
    except Exception:
        logger.warning("api-key usage flush failed", exc_info=True)


def _flush(items: dict[tuple[str, str], int]) -> None:
    from pymongo import UpdateOne

    ts = datetime.now(timezone.utc)
    ops = [
        UpdateOne(
            {"_id": f"{kid}:{day}"},
            {
                "$inc": {"count": n},
                "$set": {"ts": ts},
                "$setOnInsert": {"key_id": kid, "day": day},
            },
            upsert=True,
        )
        for (kid, day), n in items.items()
    ]
    if ops:
        _coll().bulk_write(ops, ordered=False)


def usage_for_keys(key_ids: list[str], days: int = 7) -> dict[str, dict]:
    """{key_id: {today, week}} for the admin keys list. One aggregation."""
    if not key_ids or not os.environ.get("MONGO_URL", "").strip():
        return {}
    try:
        from datetime import timedelta

        now = datetime.now(timezone.utc)
        today = now.strftime("%Y-%m-%d")
        cutoff = (now - timedelta(days=days)).strftime("%Y-%m-%d")
        out: dict[str, dict] = {}
        pipeline = [
            {"$match": {"key_id": {"$in": key_ids}, "day": {"$gte": cutoff}}},
            {
                "$group": {
                    "_id": "$key_id",
                    "week": {"$sum": "$count"},
                    "today": {
                        "$sum": {"$cond": [{"$eq": ["$day", today]}, "$count", 0]}
                    },
                }
            },
        ]
        for r in _coll().aggregate(pipeline):
            out[r["_id"]] = {"today": r.get("today", 0), "week": r.get("week", 0)}
        return out
    except Exception:
        logger.warning("api-key usage read failed", exc_info=True)
        return {}
