"""Admin API. Same container as everything else; isolation comes from layers:

1. `require_admin` at the *router* level, so every route here is guarded by
   construction and a forgotten decorator can't open a hole. The allowlist
   is the ADMIN_IDS env var (site user ids, Steam64 ids, or Discord ids),
   checked per request so removals apply instantly. Fails closed when unset.
2. Non-admins get a 404, never a 403: the code is public, no need to confirm
   to a probe that it found something real.
3. Cloudflare Access fronts /admin and /api/admin at the edge (configured in
   the Zero Trust dashboard, not in this repo), so unauthenticated traffic
   never reaches the app in production.

Every hit is audit-logged with the admin's identity.
"""

import logging
import os
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, Request

from ..services import cache as app_cache
from ..services.auth_jwt import require_admin

logger = logging.getLogger("spire-codex.admin")

router = APIRouter(
    prefix="/api/admin",
    tags=["Admin"],
    dependencies=[Depends(require_admin)],
)


def _audit(request: Request) -> None:
    user = getattr(request.state, "admin_user", None) or {}
    logger.info(
        "admin %s %s by user=%s",
        request.method,
        request.url.path,
        user.get("_id") or "?",
    )


def _runs_info() -> dict:
    out: dict = {}
    try:
        if os.environ.get("MONGO_URL", "").strip():
            from ..services.runs_db_mongo import _get_collection

            coll = _get_collection()
            out["total"] = coll.estimated_document_count()
            cutoff = datetime.now(timezone.utc) - timedelta(hours=24)
            out["last_24h"] = coll.count_documents({"submitted_at": {"$gte": cutoff}})
            latest = coll.find_one({}, {"submitted_at": 1}, sort=[("submitted_at", -1)])
            sub = (latest or {}).get("submitted_at")
            out["last_submission"] = sub.isoformat() if sub else None
        else:
            from ..services.runs_db import get_conn

            with get_conn() as conn:
                out["total"] = conn.execute("SELECT COUNT(*) FROM runs").fetchone()[0]
                out["last_24h"] = conn.execute(
                    "SELECT COUNT(*) FROM runs WHERE submitted_at >= datetime('now', '-1 day')"
                ).fetchone()[0]
                row = conn.execute("SELECT MAX(submitted_at) FROM runs").fetchone()
                out["last_submission"] = row[0]
    except Exception:
        logger.warning("admin runs info failed", exc_info=True)
    return out


def _users_info() -> dict:
    try:
        from ..services.users_db import _get_collection

        return {"total": _get_collection().estimated_document_count()}
    except Exception:
        return {}


def _snapshot_info() -> dict:
    """The persisted snapshot's vitals (the shared truth all workers serve
    from), falling back to this worker's in-process cache on SQLite."""
    try:
        if os.environ.get("MONGO_URL", "").strip():
            from ..services.run_entity_stats import SNAPSHOT_COLLECTION_NAME
            from ..services.runs_db_mongo import _get_collection

            db = _get_collection().database
            meta = db[SNAPSHOT_COLLECTION_NAME].find_one({"_id": "__meta__"}) or {}
            built = meta.get("built_at")
            built_iso = built.isoformat() if hasattr(built, "isoformat") else built
            age = None
            if hasattr(built, "timestamp"):
                if built.tzinfo is None:
                    built = built.replace(tzinfo=timezone.utc)
                age = int(datetime.now(timezone.utc).timestamp() - built.timestamp())
            return {
                "built_at": built_iso,
                "age_seconds": age,
                "version": meta.get("snapshot_version"),
                "total_runs": (meta.get("global_totals") or {}).get("total_runs"),
                "has_charts": bool(meta.get("charts")),
            }
        from ..services import run_entity_stats as res

        return {
            "built_at": res._cache_built_at or None,
            "version": res.SNAPSHOT_VERSION,
            "total_runs": (res._global_totals or {}).get("total_runs"),
        }
    except Exception:
        logger.warning("admin snapshot info failed", exc_info=True)
        return {}


@router.get("/overview")
def overview(request: Request):
    """Operational vitals: run volume, users, snapshot freshness, Redis."""
    _audit(request)
    return {
        "runs": _runs_info(),
        "users": _users_info(),
        "snapshot": _snapshot_info(),
        "redis": app_cache.info(),
        "environment": os.environ.get("ENVIRONMENT", "development"),
    }


# ── The operational surfaces (the rest of the lair) ─────────────────────


@router.get("/runs/search")
def runs_search(
    request: Request,
    username: str | None = None,
    seed: str | None = None,
    run_hash: str | None = None,
    limit: int = 25,
):
    """Find submitted runs to inspect or delete. run_hash wins when given;
    otherwise username/seed filter the normal listing, newest first."""
    _audit(request)
    if not os.environ.get("MONGO_URL", "").strip():
        return {"runs": [], "total": 0}
    from ..services.runs_db_mongo import get_database, list_runs

    limit = max(1, min(limit, 100))
    if run_hash:
        docs = list(get_database()["runs"].find({"run_hash": run_hash.strip()}))
        for d in docs:
            d.pop("_id", None)
            d.pop("raw", None)
        return {"runs": docs, "total": len(docs)}
    result = list_runs(
        username=(username or "").strip() or None,
        seed=(seed or "").strip() or None,
        sort="newest",
        page=1,
        limit=limit,
    )
    return result


@router.delete("/runs/{run_hash}")
def runs_delete(request: Request, run_hash: str):
    """Remove a submitted run: every Mongo doc sharing the hash, the blob
    file, and the in-process blob cache. Aggregates (snapshot, leaderboard
    summaries) drop it on their next scheduled rebuild."""
    _audit(request)
    from ..services import admin_db
    from .runs import _data_dir, _load_run_blob

    result = admin_db.delete_run(run_hash.strip(), _data_dir / "runs")
    # The shared-run endpoint serves blobs from an in-process LRU; evict so
    # a deleted run stops being served by this worker immediately. Other
    # workers age it out on their own.
    _load_run_blob.cache_clear()
    logger.info(
        "admin deleted run %s: %s docs, file_removed=%s",
        run_hash,
        result["deleted_docs"],
        result["file_removed"],
    )
    return {"run_hash": run_hash, **result}


@router.get("/feedback")
def feedback_inbox(request: Request, include_resolved: bool = False, limit: int = 50):
    """The feedback inbox: site feedback and QA card reports, newest first.
    Submissions land here alongside the Discord webhook."""
    _audit(request)
    from ..services import admin_db

    return {
        "items": admin_db.list_feedback(limit=limit, include_resolved=include_resolved)
    }


@router.post("/feedback/{item_id}/resolve")
def feedback_resolve(request: Request, item_id: str):
    _audit(request)
    from ..services import admin_db

    return {"resolved": admin_db.resolve_feedback(item_id)}


@router.get("/guides/pending")
def guides_pending(request: Request, limit: int = 50):
    """Guide submissions awaiting review. Publishing stays a git operation
    (guides ship in data/guides.json); dismiss clears handled entries."""
    _audit(request)
    from ..services import admin_db

    return {"items": admin_db.list_pending_guides(limit=limit)}


@router.post("/guides/submissions/{sub_id}/dismiss")
def guides_dismiss(request: Request, sub_id: str):
    _audit(request)
    from ..services import admin_db

    return {"dismissed": admin_db.dismiss_guide_submission(sub_id)}


@router.post("/cf/purge")
async def cf_purge(request: Request):
    """Purge the Cloudflare cache: body {"paths": ["/cards", ...]} purges
    those URLs on the apex domain; an empty/missing list purges the whole
    zone. Needs CF_TOKEN + CF_ZONE in the backend env."""
    _audit(request)
    token = os.environ.get("CF_TOKEN", "").strip()
    zone = os.environ.get("CF_ZONE", "").strip()
    if not token or not zone:
        from fastapi import HTTPException

        raise HTTPException(status_code=503, detail="CF_TOKEN / CF_ZONE not configured")

    try:
        body = await request.json()
    except Exception:
        body = {}
    paths = [p for p in (body.get("paths") or []) if isinstance(p, str) and p.strip()]
    if paths:
        site = os.environ.get("PUBLIC_SITE_BASE", "https://spire-codex.com").rstrip("/")
        files = [f"{site}{p if p.startswith('/') else '/' + p}" for p in paths[:30]]
        payload: dict = {"files": files}
    else:
        payload = {"purge_everything": True}

    import httpx

    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.post(
            f"https://api.cloudflare.com/client/v4/zones/{zone}/purge_cache",
            headers={"Authorization": f"Bearer {token}"},
            json=payload,
        )
    ok = resp.status_code == 200 and resp.json().get("success") is True
    logger.info("admin CF purge (%s): ok=%s", "paths" if paths else "everything", ok)
    return {"ok": ok, "purged": "paths" if paths else "everything", "count": len(paths)}
