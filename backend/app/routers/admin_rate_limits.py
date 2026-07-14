"""Admin control over the API's blanket rate limit.

Gated by the same require_admin as the rest of the operator surface. Lets me
raise/lower the global per-IP cap or switch it off entirely at runtime, without
a redeploy. Per-endpoint limits (auth, feedback, ...) are unaffected.
"""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from ..services import rate_limit_config
from ..services.auth_jwt import require_admin

router = APIRouter(
    prefix="/api/admin/rate-limits",
    tags=["Admin"],
    dependencies=[Depends(require_admin)],
)


@router.get("")
def get_rate_limits():
    """Current browse cap, per-tier caps, and whether limiting is on."""
    return rate_limit_config.get_config()


class RateLimitUpdate(BaseModel):
    default_limit: str | None = Field(
        default=None,
        description="Un-keyed browse cap (per IP), e.g. '300/minute'.",
    )
    tiers: dict[str, str] | None = Field(
        default=None,
        description="Per API-key tier caps, e.g. {'general': '15/minute', ...}.",
    )
    enabled: bool | None = Field(
        default=None,
        description="False turns limiting off (per-endpoint limits stay).",
    )


@router.put("")
def set_rate_limits(body: RateLimitUpdate):
    """Change the browse cap, any tier caps, and/or toggle limiting. Takes effect
    across workers within the config cache window (~15s)."""
    try:
        return rate_limit_config.set_config(
            body.default_limit, body.enabled, body.tiers
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
