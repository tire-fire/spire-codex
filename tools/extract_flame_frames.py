#!/usr/bin/env python3
"""Extract the 10 ancient-card flame frames and the static flame, reconstructed
to match the game exactly.

The Fire node is an AnimatedSprite2D with `centered = true`, so each frame is
centred at the Fire point. The frames have different trimmed sizes (each .tres
carries a `region` plus a `margin` that records the trim), so to animate without
the flame jumping, every frame must be rebuilt to its full logical size
(region + margin) and then centred in a common canvas (the max logical size,
49x76). The static `ancient_flame` is frame 0 built the same way, so it lines up
with the animation in the game-exact CSS box.
"""
from __future__ import annotations
import re
from pathlib import Path
from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
ATLAS = ROOT / "extraction/beta/raw/images/atlases/compressed_0.png"
SPR = ROOT / "extraction/beta/raw/images/atlases/compressed.sprites/card_template/ancient_flame"
OUT = ROOT / "backend/static/images/card-frames"
FRAMES_OUT = Path("/tmp/flame_frames")
FRAMES_OUT.mkdir(parents=True, exist_ok=True)


def parse(tres: Path):
    t = tres.read_text()
    r = re.search(r"region = Rect2\(([\d.]+), ([\d.]+), ([\d.]+), ([\d.]+)\)", t)
    m = re.search(r"margin = Rect2\(([\d.]+), ([\d.]+), ([\d.]+), ([\d.]+)\)", t)
    region = tuple(int(float(x)) for x in r.groups())
    margin = tuple(int(float(x)) for x in m.groups()) if m else (0, 0, 0, 0)
    return region, margin


def main() -> int:
    atlas = Image.open(ATLAS).convert("RGBA")
    frames = []
    for i in range(10):
        region, margin = parse(SPR / f"ancient_card_flame_{i}.tres")
        rw, rh = region[2], region[3]
        mx, my, mw, mh = margin
        logical = (rw + mx + mw, rh + my + mh)
        frames.append((i, region, margin, logical))

    cw = max(f[3][0] for f in frames)
    ch = max(f[3][1] for f in frames)

    for i, (rx, ry, rw, rh), (mx, my, mw, mh), (lw, lh) in frames:
        piece = atlas.crop((rx, ry, rx + rw, ry + rh))
        canvas = Image.new("RGBA", (cw, ch), (0, 0, 0, 0))
        # centre the full logical box, then place the region at its margin offset
        ox = (cw - lw) // 2 + mx
        oy = (ch - lh) // 2 + my
        canvas.paste(piece, (ox, oy))
        canvas.save(FRAMES_OUT / f"f_{i:02d}.png")
        if i == 0:
            canvas.save(OUT / "ancient_flame.png")
            canvas.save(OUT / "ancient_flame.webp", "WEBP", quality=95, method=6)

    print(f"flame canvas {cw}x{ch}; wrote 10 frames to {FRAMES_OUT} + ancient_flame to {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
