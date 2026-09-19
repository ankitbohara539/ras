"""Generate the PWA icon set.

    python scripts/make-icons.py

Drawn rather than hand-designed so the set is reproducible and consistent.
Replace public/icon-*.png with real artwork whenever there is any.

The maskable variant matters: Android crops icons to whatever shape the
launcher uses, so the glyph sits inside the safe zone (the middle 80%) with
the brand colour bleeding to the edges.
"""

from __future__ import annotations

import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

BRAND = (13, 92, 99)
BRAND_DARK = (8, 63, 68)
INK = (255, 255, 255)

PUBLIC = Path(__file__).resolve().parent.parent / "public"

FONT_CANDIDATES = [
    r"C:\Windows\Fonts\Nirmala.ttf",       # Devanagari on Windows
    r"C:\Windows\Fonts\mangal.ttf",
    "/usr/share/fonts/truetype/lohit-devanagari/Lohit-Devanagari.ttf",
    "/System/Library/Fonts/Supplemental/Kohinoor.ttc",
]


def load_font(size: int) -> ImageFont.FreeTypeFont:
    for path in FONT_CANDIDATES:
        if Path(path).exists():
            try:
                return ImageFont.truetype(path, size)
            except OSError:
                continue
    return ImageFont.load_default()


def draw_icon(size: int, maskable: bool = False) -> Image.Image:
    image = Image.new("RGBA", (size, size), BRAND + (255,))
    draw = ImageDraw.Draw(image)

    # Subtle depth so the icon does not read as a flat square.
    draw.ellipse(
        [-size * 0.25, size * 0.45, size * 0.75, size * 1.45],
        fill=BRAND_DARK + (255,),
    )

    # A maskable icon must keep its glyph inside the middle 80%.
    glyph_ratio = 0.46 if maskable else 0.60
    font = load_font(int(size * glyph_ratio))

    glyph = "\u0938"  # स -- Sahayatri
    box = draw.textbbox((0, 0), glyph, font=font)
    x = (size - (box[2] - box[0])) / 2 - box[0]
    y = (size - (box[3] - box[1])) / 2 - box[1]
    draw.text((x, y), glyph, font=font, fill=INK + (255,))

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
