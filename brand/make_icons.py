# -*- coding: utf-8 -*-
"""Draw the Puregram mark and write every icon the project ships.

The mark is a "P" monogram. It replaces the recoloured paper plane, which was too
close to Telegram's own logo for both Telegram's API terms and Google Play's
impersonation policy — see LEGAL-COMPLIANCE.md.

The counter — the hole in the P — is punched out rather than filled, so the same
drawing works whether it sits on a solid tile (the launcher icon) or on a
transparent foreground layer (the Android adaptive icon), where the background
layer shows through.

Everything is drawn at SUPERSAMPLE times the target size and resampled down, so
edges are clean at 16 px as well as 512.

Usage: python brand/make_icons.py [--check]
  --check  draw everything and report, but write nothing.
"""
from __future__ import annotations

import sys
from pathlib import Path

from PIL import Image, ImageDraw

REPO = Path(__file__).resolve().parent.parent

# Brand green. The tile is a diagonal ramp between these two, matching the
# Android adaptive background vector in drawable/icon_background.xml.
GREEN_LIGHT = (0x3F, 0xB7, 0x68)
GREEN_DARK = (0x1E, 0x7A, 0x3C)
WHITE = (0xFF, 0xFF, 0xFF)

SUPERSAMPLE = 8
_MAX_SUPERSAMPLED_PX = 4096


def _scale_for(size: int) -> int:
    """Keep the working canvas sane for large targets."""
    return max(1, min(SUPERSAMPLE, _MAX_SUPERSAMPLED_PX // size))


# ── the mark, in a unit square ──────────────────────────────────────────────
# The bowl is a disc with a half-disc counter knocked out of it. The counter
# starts at the stem's right edge — that is what gives a P its half-moon hole.
STEM = (0.280, 0.100, 0.440, 0.880)
STEM_RADIUS = 0.030

BOWL_CENTRE = (0.440, 0.395)
BOWL_OUTER_R = 0.295
BOWL_COUNTER_R = 0.145

# No tail. A nib hanging off the stem at the baseline turned the P into an R at
# every size — the leg of an R is exactly that shape. A plain P is what the
# monogram is for.


def _rounded_rect(draw: ImageDraw.ImageDraw, box, radius: float, s: int, fill) -> None:
    x0, y0, x1, y1 = (v * s for v in box)
    draw.rounded_rectangle((x0, y0, x1, y1), radius=radius * s, fill=fill)


def _disc(draw: ImageDraw.ImageDraw, centre, radius: float, s: int, fill) -> None:
    cx, cy = (v * s for v in centre)
    r = radius * s
    draw.ellipse((cx - r, cy - r, cx + r, cy + r), fill=fill)


def _draw_mark_mask(s: int) -> Image.Image:
    """An L-mode mask: 255 where the white mark is, 0 where the counter is cut out."""
    mask = Image.new("L", (s, s), 0)
    d = ImageDraw.Draw(mask)

    # The bowl is drawn first and clipped to the stem's left edge, so it never
    # bulges out to the left of the stem.
    bowl = Image.new("L", (s, s), 0)
    _disc(ImageDraw.Draw(bowl), BOWL_CENTRE, BOWL_OUTER_R, s, 255)
    clip = Image.new("L", (s, s), 0)
    ImageDraw.Draw(clip).rectangle((STEM[0] * s, 0, s, s), fill=255)
    bowl.paste(0, (0, 0), Image.eval(clip, lambda v: 255 - v))
    mask.paste(255, (0, 0), bowl)

    _rounded_rect(d, STEM, STEM_RADIUS, s, 255)

    # The counter is a half-disc starting at the stem's right edge — that is what
    # makes the shape read as a P rather than a filled lollipop.
    counter = Image.new("L", (s, s), 0)
    _disc(ImageDraw.Draw(counter), BOWL_CENTRE, BOWL_COUNTER_R, s, 255)
    left = Image.new("L", (s, s), 0)
    ImageDraw.Draw(left).rectangle((0, 0, STEM[2] * s, s), fill=255)
    counter.paste(0, (0, 0), left)
    mask.paste(0, (0, 0), counter)

    return mask


_RAMP_RESOLUTION = 64


def _diagonal_ramp(s: int) -> Image.Image:
    """A light-to-dark diagonal ramp.

    Drawn tiny and scaled up: a linear ramp stays linear under interpolation, and
    a per-pixel loop at 4096 square is thousands of times slower for no gain.
    """
    n = _RAMP_RESOLUTION
    small = Image.new("RGBA", (n, n))
    px = small.load()
    for y in range(n):
        for x in range(n):
            t = (x + y) / (2.0 * (n - 1))
            px[x, y] = (
                round(GREEN_LIGHT[0] + (GREEN_DARK[0] - GREEN_LIGHT[0]) * t),
                round(GREEN_LIGHT[1] + (GREEN_DARK[1] - GREEN_LIGHT[1]) * t),
                round(GREEN_LIGHT[2] + (GREEN_DARK[2] - GREEN_LIGHT[2]) * t),
                255,
            )
    return small.resize((s, s), Image.BICUBIC)


def _tile(s: int, shape: str) -> Image.Image:
    """The coloured plate behind the mark: 'square' (rounded), 'circle' or 'none'."""
    if shape == "none":
        return Image.new("RGBA", (s, s), (0, 0, 0, 0))
    ramp = _diagonal_ramp(s)

    plate = Image.new("L", (s, s), 0)
    d = ImageDraw.Draw(plate)
    if shape == "circle":
        d.ellipse((0, 0, s - 1, s - 1), fill=255)
    else:
        d.rounded_rectangle((0, 0, s - 1, s - 1), radius=s * 0.2237, fill=255)

    out = Image.new("RGBA", (s, s), (0, 0, 0, 0))
    out.paste(ramp, (0, 0), plate)
    return out


def render(size: int, shape: str = "square", mark_scale: float = 0.62) -> Image.Image:
    """One finished icon.

    mark_scale is the mark's width as a fraction of the canvas. 0.52 keeps it
    inside the 66/108 safe zone Android reserves on adaptive icons.
    """
    scale = _scale_for(size)
    s = size * scale
    img = _tile(s, shape)

    m = max(1, int(round(s * mark_scale)))
    mark_mask = _draw_mark_mask(m)
    white = Image.new("RGBA", (m, m), WHITE + (255,))
    offset = (s - m) // 2
    img.paste(white, (offset, offset), mark_mask)

    if scale > 1:
        img = img.resize((size, size), Image.LANCZOS)
    return img


def render_in_frame(width: int, height: int, mark_scale: float = 0.92) -> Image.Image:
    """The white mark, transparent, centred in a frame that need not be square.

    Used where a caller sizes something from the image's own dimensions and would
    stretch a square one.
    """
    side = max(1, int(round(min(width, height) * mark_scale)))
    mark = Image.new("RGBA", (side, side), (0, 0, 0, 0))
    mark.paste(Image.new("RGBA", (side, side), WHITE + (255,)), (0, 0),
               _draw_mark_mask(side * _scale_for(side)).resize((side, side), Image.LANCZOS))
    out = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    out.alpha_composite(mark, ((width - side) // 2, (height - side) // 2))
    return out


# ── the same mark as vector geometry ────────────────────────────────────────
# One source of truth for the SVG logo, the favicon and Android's monochrome
# adaptive layer. The outline runs up the stem's left edge, across its top, in a
# half-circle round the bowl, then down the stem's right edge. The counter is a
# second subpath, filled with the even-odd rule so it reads as a hole.


def mark_path(scale: float, offset: float, decimals: int = 2) -> str:
    """The P as an SVG / VectorDrawable path, mapped through x -> offset + scale*x."""
    fmt = "%%.%df" % decimals

    def u(v: float) -> str:
        return fmt % (offset + scale * v)

    def r(v: float) -> str:
        return fmt % (scale * v)

    left, top, right, bottom = STEM
    bowl_bottom = BOWL_CENTRE[1] + BOWL_OUTER_R
    counter_top = BOWL_CENTRE[1] - BOWL_COUNTER_R
    counter_bottom = BOWL_CENTRE[1] + BOWL_COUNTER_R

    outer = "M%s,%s L%s,%s L%s,%s A%s,%s 0 0 1 %s,%s L%s,%s Z" % (
        u(left), u(bottom), u(left), u(top), u(right), u(top),
        r(BOWL_OUTER_R), r(BOWL_OUTER_R), u(right), u(bowl_bottom),
        u(right), u(bottom))
    counter = "M%s,%s A%s,%s 0 0 1 %s,%s Z" % (
        u(right), u(counter_top), r(BOWL_COUNTER_R), r(BOWL_COUNTER_R),
        u(right), u(counter_bottom))
    return outer + " " + counter


MONO_TEMPLATE = """<?xml version="1.0" encoding="utf-8"?>
<!-- Puregram monogram, monochrome adaptive-icon layer.
     Generated by brand/make_icons.py - do not edit by hand. -->
<vector xmlns:android="http://schemas.android.com/apk/res/android"
    android:width="108dp" android:height="108dp"
    android:viewportWidth="108" android:viewportHeight="108">
    <path
        android:fillColor="#FFFFFF"
        android:fillType="evenOdd"
        android:pathData="%s"/>
</vector>
"""

SVG_TEMPLATE = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 96 96" width="96" height="96" role="img" aria-label="Puregram">
  <!-- Generated by brand/make_icons.py - do not edit by hand. -->
  <defs>
    <linearGradient id="pgTile" x1="0" y1="0" x2="1" y2="1">
      <stop offset="0" stop-color="#3FB768"/>
      <stop offset="1" stop-color="#1E7A3C"/>
    </linearGradient>
  </defs>
  <rect x="0" y="0" width="96" height="96" rx="21.5" fill="url(#pgTile)"/>
  <path fill="#FFFFFF" fill-rule="evenodd" d="%s"/>
</svg>
"""

# ── what to write ───────────────────────────────────────────────────────────
ANDROID_RES = REPO / "telegram/telegram-android/TMessagesProj/src/main/res"
# The shipped app does NOT use the library module's ic_launcher. The standalone
# manifest points android:icon at @mipmap/ic_launcher_sa, which lives here with
# its own adaptive pair. Miss this set and the launcher keeps the old artwork
# however carefully the other one is regenerated.
STANDALONE_RES = REPO / "telegram/telegram-android/TMessagesProj_AppStandalone/src/main/res"
DENSITIES = {"mdpi": 1, "hdpi": 1.5, "xhdpi": 2, "xxhdpi": 3, "xxxhdpi": 4}

# The standalone adaptive icon paints a flat colour behind the foreground.
BRAND_GREEN_HEX = "#2E9E4F"
STANDALONE_COLORS = """<?xml version="1.0" encoding="utf-8"?>
<resources>
    <!-- Adaptive-icon background for the standalone build. Generated by
         brand/make_icons.py - do not edit by hand. -->
    <color name="puregram_icon_bg">%s</color>
</resources>
""" % BRAND_GREEN_HEX


def write_vector_assets() -> list[Path]:
    """The monochrome Android layer, the site logo and the site favicon."""
    written: list[Path] = []

    # 108dp viewport, mark at the same 0.52 scale as the foreground PNGs so the
    # three adaptive layers line up.
    mono_scale = 108 * 0.52
    mono_path = ANDROID_RES / "drawable" / "icon_mark.xml"
    if mono_path.parent.exists():
        mono_path.write_text(
            MONO_TEMPLATE % mark_path(mono_scale, (108 - mono_scale) / 2),
            encoding="utf-8", newline="\n")
        written.append(mono_path)

    colors = STANDALONE_RES / "values" / "puregram_colors.xml"
    if colors.parent.exists():
        colors.write_text(STANDALONE_COLORS, encoding="utf-8", newline="\n")
        written.append(colors)

    logo_scale = 96 * 0.62
    svg = SVG_TEMPLATE % mark_path(logo_scale, (96 - logo_scale) / 2)
    site_icons = REPO / "site" / "assets" / "icons"
    if site_icons.exists():
        for name in ("logo.svg", "favicon.svg"):
            (site_icons / name).write_text(svg, encoding="utf-8", newline="\n")
            written.append(site_icons / name)

    return written


def targets() -> list[tuple[Path, Image.Image]]:
    out: list[tuple[Path, Image.Image]] = []

    for density, factor in DENSITIES.items():
        legacy = int(round(48 * factor))
        adaptive = int(round(108 * factor))

        mip = ANDROID_RES / f"mipmap-{density}"
        out.append((mip / "ic_launcher.png", render(legacy, "square")))
        out.append((mip / "ic_launcher_round.png", render(legacy, "circle")))
        # The adaptive foreground is transparent; the background vector paints
        # the tile, and the punched-out counter shows it through.
        for name in ("icon_foreground.png", "icon_foreground_round.png",
                     "icon_foreground_sa.png"):
            out.append((mip / name, render(adaptive, "none", mark_scale=0.52)))

        out.append((ANDROID_RES / f"drawable-{density}" / "ic_launcher_dr.webp",
                    render(legacy, "square")))

        # The set the shipped app actually shows.
        sa = STANDALONE_RES / f"mipmap-{density}"
        out.append((sa / "ic_launcher_sa.png", render(legacy, "square")))
        out.append((sa / "puregram_fg.png", render(adaptive, "none", mark_scale=0.52)))

        # The welcome screen's mark. IntroActivity paints a brand disc in code
        # and lays this on top as a GL texture, so it has to be a raster —
        # loadTexture() only accepts a BitmapDrawable, never a vector. The GL
        # quad is sized from the texture, so the 82x74 frame upstream ships is
        # kept exactly; the square mark is centred inside it rather than
        # stretched to fill.
        if density != "xxxhdpi":  # upstream ships this one only to xxhdpi
            out.append((ANDROID_RES / f"drawable-{density}" / "intro_tg_plane.webp",
                        render_in_frame(int(round(82 * factor)), int(round(74 * factor)))))

            # The status-bar notification icon. Android tints it, so it has to be
            # a white glyph on transparent — no tile.
            notif = int(round(24 * factor))
            out.append((ANDROID_RES / f"drawable-{density}" / "notification.webp",
                        render(notif, "none", mark_scale=0.86)))

            # The mark on the Terms of Service screen.
            middle = int(round(68 * factor))
            suffix = "webp" if density in ("mdpi", "hdpi") else "png"
            out.append((ANDROID_RES / f"drawable-{density}" / f"logo_middle.{suffix}",
                        render(middle, "square")))

    # Google Play wants a full-bleed 512 square; Play applies its own mask.
    out.append((REPO / "play-assets/graphics/icon-512.png", render(512, "square")))

    for name, size, shape in (
        ("icon-512x512.png", 512, "square"),
        ("icon-192x192.png", 192, "square"),
        ("apple-touch-icon.png", 180, "square"),
        ("favicon-32x32.png", 32, "square"),
        ("favicon-16x16.png", 16, "square"),
    ):
        out.append((REPO / "brand" / name, render(size, shape)))

    art = REPO / "telegram/tdesktop/Telegram/Resources/art"
    for size in (16, 32, 48, 64, 128, 256, 512):
        out.append((art / f"icon{size}.png", render(size, "square")))
        out.append((art / f"icon{size}@2x.png", render(size * 2, "square")))
    out.append((art / "icon_round512@2x.png", render(1024, "circle")))
    out.append((art / "logo_256.png", render(256, "square")))
    out.append((art / "logo_256_no_margin.png", render(256, "square")))
    # Nothing references these two, but keep the dimensions upstream shipped —
    # the names are misleading, "big" is the small one.
    out.append((art / "icon_green.png", render(1024, "square")))
    out.append((art / "iconbig_green.png", render(256, "square")))

    return out


def main() -> int:
    check_only = "--check" in sys.argv
    written = 0
    for path, image in targets():
        if not path.parent.exists():
            print("skip (no dir): %s" % path)
            continue
        if check_only:
            print("would write %-70s %s" % (path.relative_to(REPO), image.size))
            continue
        if path.suffix == ".webp":
            image.save(path, "WEBP", lossless=True)
        else:
            image.save(path, "PNG")
        written += 1

    if check_only:
        return 0

    ico = REPO / "telegram/tdesktop/Telegram/Resources/art/icon256.ico"
    if ico.parent.exists():
        render(256, "square").save(
            ico, format="ICO",
            sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64),
                   (128, 128), (256, 256)])
        written += 1
    for path in write_vector_assets():
        print("wrote %s" % path.relative_to(REPO))
        written += 1

    print("wrote %d files" % written)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
