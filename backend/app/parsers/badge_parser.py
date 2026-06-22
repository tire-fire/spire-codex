"""Parse run-end badges from C# source + localization.

Badges are the mini-achievements awarded on the Game Over screen (introduced
in v0.103.x beta, shipped to stable in Major Update #1 / v0.103.2). Each
badge has an ID, optional tier variants (Bronze/Silver/Gold), and flags for
whether it requires a win or only applies to multiplayer.

Source of truth:
  - Localization: `extraction/raw/localization/<lang>/badges.json` —
    keys are either `ID.title`/`ID.description` (single-tier) or
    `ID.{bronze,silver,gold}Title`/`ID.{bronze,silver,gold}Description`.
  - C# classes under `MegaCrit.Sts2.Core.Models.Badges/`, one per badge.
    The id and the requiresWin / multiplayerOnly flags are passed into the
    Badge base(...) constructor, e.g.
    `base(run, won, playerId, "BIG_DECK", requiresWin: true, multiplayerOnly: false)`.
    Badges with no class (loc-only, e.g. FAVORITE_CARD) and disabled cut
    content (e.g. Whomper, IsObtained() => false) are not emitted.

Icons live at `static/images/badges/badge_<id_lower>.png` — the game derives
this from `Id.ToLowerInvariant()` (see Badge.cs `IconPath`).
"""

import json
import re
from collections import defaultdict
from pathlib import Path

from parser_paths import BASE, DECOMPILED, data_dir as _data_dir, loc_dir as _loc_dir

BADGES_CS_DIR = DECOMPILED / "MegaCrit.Sts2.Core.Models.Badges"
STATIC_IMAGES = BASE / "backend" / "static" / "images"

# Badges whose loc ID differs from the lower-snaked class ID (icons follow
# the loc ID per Badge.cs IconPath).
_TIER_ORDER = ("bronze", "silver", "gold")


def _is_disabled(text: str) -> bool:
    """True if the badge can never be obtained (cut content).

    A disabled badge overrides IsObtained() to always return false, e.g.
    Whomper.cs ("THIS BADGE IS CURRENTLY NOT IN USE"), which is also left out
    of BadgePool.cs CreateAll. Matches both the expression-bodied form
    (`IsObtained() => false;`) and the block form (`{ return false; }`).
    """
    if re.search(r"IsObtained\s*\(\s*\)\s*=>\s*false\s*;", text):
        return True
    block = re.search(
        r"IsObtained\s*\(\s*\)\s*\{(?P<body>.*?)\}",
        text,
        re.DOTALL,
    )
    if block and re.fullmatch(r"\s*return\s+false\s*;\s*", block.group("body")):
        return True
    return False


def _parse_cs_flags() -> dict[str, dict]:
    """Read each Badge subclass to pull Id / requiresWin / multiplayerOnly.

    Concrete badges set these in the Badge base(...) constructor call:
        base(run, won, playerId, "BIG_DECK", requiresWin: true, multiplayerOnly: false)
    The Id property is just `Id = id;` in Badge.cs, so there is no per-class
    `Id =>` to scrape; the quoted ctor argument is the source of truth. Only
    badges with a backing subclass land in this map, so callers can use it to
    gate out loc-only ids (e.g. FAVORITE_CARD has no class). Disabled badges
    (Whomper) are skipped entirely.
    """
    flags: dict[str, dict] = {}
    if not BADGES_CS_DIR.exists():
        return flags

    ctor_re = re.compile(
        r"base\s*\(\s*run\s*,\s*won\s*,\s*playerId\s*,\s*"
        r'"(?P<id>[A-Z_]+)"\s*,\s*'
        r"requiresWin:\s*(?P<win>true|false)\s*,\s*"
        r"multiplayerOnly:\s*(?P<mp>true|false)\s*\)"
    )

    for cs_file in sorted(BADGES_CS_DIR.glob("*.cs")):
        if cs_file.stem in {"Badge", "BadgePool", "BadgeRarity"}:
            continue
        text = cs_file.read_text(encoding="utf-8", errors="ignore")
        ctor = ctor_re.search(text)
        if not ctor:
            continue
        if _is_disabled(text):
            continue
        bid = ctor.group("id")
        flags[bid] = {
            "class_name": cs_file.stem,
            "requires_win": ctor.group("win") == "true",
            "multiplayer_only": ctor.group("mp") == "true",
        }
    return flags


def _group_localization(loc: dict[str, str]) -> dict[str, dict[str, str]]:
    groups: dict[str, dict[str, str]] = defaultdict(dict)
    for key, value in loc.items():
        if "." not in key:
            continue
        bid, _, suffix = key.partition(".")
        groups[bid][suffix] = value
    return groups


def _image_url(badge_id: str) -> str | None:
    filename = f"badge_{badge_id.lower()}.png"
    if (STATIC_IMAGES / "badges" / filename).exists():
        return f"/static/images/badges/{filename}"
    return None


def parse_badges(loc_dir: Path) -> list[dict]:
    loc_file = loc_dir / "badges.json"
    if not loc_file.exists():
        return []
    with open(loc_file, "r", encoding="utf-8") as f:
        loc = json.load(f)

    cs_flags = _parse_cs_flags()
    groups = _group_localization(loc)

    badges: list[dict] = []
    for bid in sorted(groups.keys()):
        # Only emit badges that have a real, enabled Badge subclass. This drops
        # loc-only ids with no backing C# class (e.g. FAVORITE_CARD) and cut
        # content disabled via IsObtained() => false (e.g. WHOMPER).
        if bid not in cs_flags:
            continue
        fields = groups[bid]
        tiered = any(
            f"{tier}Title" in fields or f"{tier}Description" in fields
            for tier in _TIER_ORDER
        )

        tiers: list[dict[str, str]] = []
        if tiered:
            for tier in _TIER_ORDER:
                title = fields.get(f"{tier}Title")
                desc = fields.get(f"{tier}Description")
                if not title and not desc:
                    continue
                tiers.append(
                    {
                        "rarity": tier,
                        "title": title or "",
                        "description": desc or "",
                    }
                )
        else:
            tiers.append(
                {
                    "rarity": "bronze",
                    "title": fields.get("title", ""),
                    "description": fields.get("description", ""),
                }
            )

        # Primary display name/desc: first tier for untiered, lowest-tier for tiered.
        primary = tiers[0] if tiers else {"title": "", "description": ""}
        flags = cs_flags.get(bid, {})

        badges.append(
            {
                "id": bid,
                "name": primary.get("title", ""),
                "description": primary.get("description", ""),
                "tiered": tiered,
                "tiers": tiers,
                "requires_win": flags.get("requires_win", False),
                "multiplayer_only": flags.get("multiplayer_only", False),
                "image_url": _image_url(bid),
            }
        )
    return badges


def main(lang: str):
    loc_dir = _loc_dir(lang)
    output_dir = _data_dir(lang)

    badges = parse_badges(loc_dir)
    with open(output_dir / "badges.json", "w", encoding="utf-8") as f:
        json.dump(badges, f, indent=2, ensure_ascii=False)
    print(f"Parsed {len(badges)} badges -> data/{lang}/badges.json")


if __name__ == "__main__":
    import sys

    main(sys.argv[1] if len(sys.argv) > 1 else "eng")
