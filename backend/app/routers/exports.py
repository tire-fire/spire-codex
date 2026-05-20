import io
import zipfile

from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse
from slowapi import Limiter

from ..dependencies import VALID_LANGUAGES, client_ip
from ..metrics import data_exports
from ..services.data_service import DATA_DIR

router = APIRouter(prefix="/api/exports", tags=["Exports"])

# Per-language export builds a multi-file zip (15+ JSON files, 1-3 MB
# compressed) on every request. CPU cost is the deflate pass — roughly
# 20-100ms each — plus the egress bytes. Way too expensive to fall
# under the global 300/min default. 10/hour per real IP is plenty for
# legitimate "give me a snapshot of the eng locale" use; anything
# higher and you're either scraping or you should be using the JSON
# endpoints directly.
limiter = Limiter(key_func=client_ip)

ENTITY_FILES = [
    "cards",
    "relics",
    "potions",
    "characters",
    "monsters",
    "powers",
    "events",
    "encounters",
    "enchantments",
    "keywords",
    "intents",
    "orbs",
    "afflictions",
    "modifiers",
    "achievements",
    "epochs",
]


@router.get("/{lang}")
@limiter.limit("10/hour")
def export_language(lang: str, request: Request):
    if lang not in VALID_LANGUAGES:
        lang = "eng"
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for entity in ENTITY_FILES:
            filepath = DATA_DIR / lang / f"{entity}.json"
            if filepath.exists():
                zf.write(filepath, f"{entity}.json")
    buf.seek(0)
    data_exports.labels(lang=lang).inc()
    return StreamingResponse(
        buf,
        media_type="application/zip",
        headers={
            "Content-Disposition": f'attachment; filename="spire-codex-{lang}.zip"'
        },
    )
