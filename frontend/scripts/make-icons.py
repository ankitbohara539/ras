"""Generate the PWA icon set.

    python scripts/make-icons.py

Generated from the official companion mark in the project logo bundle so the
installed app, browser tabs and application UI all use the same identity.

The maskable variant matters: Android crops icons to whatever shape the
launcher uses, so the glyph sits inside the safe zone (the middle 80%) with
the brand colour bleeding to the edges.
"""

from __future__ import annotations

import sys
from pathlib import Path

from PIL import Image

NAVY = (29, 41, 61)

FRONTEND = Path(__file__).resolve().parent.parent
PUBLIC = FRONTEND / "public"
MARK = FRONTEND / "assets" / "Icon" / "Companions" / "Open path@4x-1.png"


def draw_icon(size: int, maskable: bool = False) -> Image.Image:
    image = Image.new("RGBA", (size, size), NAVY + (255,))
    mark = Image.open(MARK).convert("RGBA")
    # Maskable launchers may crop to a circle or squircle, so keep the mark in
    # the central safe zone. Standard icons can use a little more of the tile.
    mark_size = int(size * (0.58 if maskable else 0.68))
    mark.thumbnail((mark_size, mark_size), Image.Resampling.LANCZOS)
    x = (size - mark.width) // 2
    y = (size - mark.height) // 2
    image.alpha_composite(mark, (x, y))
    return image


def main() -> int:
    PUBLIC.mkdir(parents=True, exist_ok=True)

    outputs = [
        ("icon-192.png", 192, False),
        ("icon-512.png", 512, False),
        ("icon-maskable-512.png", 512, True),
        ("apple-touch-icon.png", 180, False),
    ]

    for name, size, maskable in outputs:
        icon = draw_icon(size, maskable)
        icon.save(PUBLIC / name, format="PNG")
        print(f"  {name:26} {size}x{size}")

    # Multi-resolution favicon.
    favicon = draw_icon(64)
    favicon.save(
        PUBLIC / "favicon.ico",
        format="ICO",
        sizes=[(16, 16), (32, 32), (48, 48), (64, 64)],
    )
    print(f"  {'favicon.ico':26} 16/32/48/64")

    return 0


if __name__ == "__main__":
    sys.exit(main())
