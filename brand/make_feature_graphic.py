# -*- coding: utf-8 -*-
"""Draw the Google Play feature graphic (1024x500).

Generated rather than hand-edited for the same reason the icons are: the mark
changed once and had to be chased through six files. This reads the mark from
make_icons, so the two can never drift.

Two things changed with ADR-002 besides the mark: the "Supervised" badge is gone
— nobody supervises anyone any more, each user governs their own lists — and the
gold ring went with the paper plane.

Usage: python brand/make_feature_graphic.py
"""
from __future__ import annotations

import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

sys.path.insert(0, str(Path(__file__).resolve().parent))
from make_icons import REPO, render  # noqa: E402

WIDTH, HEIGHT = 1024, 500
OUT = REPO / "play-assets" / "graphics" / "feature-graphic-1024x500.png"

# Near-black on the left easing into deep brand green on the right.
BG_LEFT = (0x0A, 0x0F, 0x0C)
BG_RIGHT = (0x10, 0x3A, 0x22)

WHITE = (0xFF, 0xFF, 0xFF)
TAGLINE = (0xD6, 0xE6, 0xDC)
PILL_TEXT = (0xC8, 0xDE, 0xD0)
PILL_EDGE = (0x3F, 0xB7, 0x68)

TITLE = "Puregram"
# Short enough to clear the mark \u2014 the longer line ran under the disc.
SUBTITLE = "A cleaner messenger \u2014 under your control."
PILLS = ("Unofficial build", "Ad-free", "Your rules", "Free")

FONTS = Path("C:/Windows/Fonts")


def _font(name: str, size: int) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(str(FONTS / name), size)


def _background() -> Image.Image:
    """A horizontal ramp, drawn small and scaled: linear stays linear."""
    small = Image.new("RGB", (64, 1))
    px = small.load()
    for x in range(64):
        t = x / 63.0
        px[x, 0] = tuple(round(BG_LEFT[i] + (BG_RIGHT[i] - BG_LEFT[i]) * t) for i in range(3))
    return small.resize((WIDTH, HEIGHT), Image.BICUBIC).convert("RGBA")


def _draw_pills(draw: ImageDraw.ImageDraw, x: int, y: int) -> None:
    font = _font("segoeui.ttf", 21)
    pad_x, height, gap = 20, 42, 14
    for label in PILLS:
        w = draw.textlength(label, font=font)
        box = (x, y, x + w + pad_x * 2, y + height)
        draw.rounded_rectangle(box, radius=height // 2, outline=PILL_EDGE, width=2)
        draw.text((x + pad_x, y + height / 2), label, font=font, fill=PILL_TEXT, anchor="lm")
        x += int(w) + pad_x * 2 + gap


def main() -> int:
    img = _background()
    draw = ImageDraw.Draw(img)

    # The mark, right of centre, sized so it breathes against the 500px height.
    mark_size = 290
    mark = render(mark_size, "circle", mark_scale=0.60)
    img.alpha_composite(mark, (WIDTH - mark_size - 72, (HEIGHT - mark_size) // 2))

    draw.text((72, 196), TITLE, font=_font("segoeuib.ttf", 82), fill=WHITE, anchor="ls")
    draw.text((74, 246), SUBTITLE, font=_font("segoeui.ttf", 25), fill=TAGLINE, anchor="ls")
    _draw_pills(draw, 72, 286)

    OUT.parent.mkdir(parents=True, exist_ok=True)
    img.convert("RGB").save(OUT, "PNG")
    print("wrote %s %dx%d" % (OUT.relative_to(REPO), WIDTH, HEIGHT))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
