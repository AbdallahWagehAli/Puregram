"""Regenerate the Telegram Desktop icon set from the new Jahed badge.

The new_logos2/apply.py pipeline only rebrands the Android launcher rasters; it
never touched tdesktop's icons (Resources/art/logo_256*, icon*, icon256.ico), so
they kept the old/stock Telegram art. This rewrites all of them from the new
red-J badge while preserving each file's pixel size.

Run:  python Jahed-Telegram/tdesktop/gen_jahed_icons.py
"""
from __future__ import annotations
import pathlib
from PIL import Image

REPO = pathlib.Path(__file__).resolve().parents[2]
SRC = REPO / "new_logos2" / "jahed-telegram.png"
ART = pathlib.Path(__file__).resolve().parent / "Telegram" / "Resources" / "art"

# icon<name> -> exact pixel size (matches the existing files).
ICON_PNGS = {
    "icon16.png": 16, "icon16@2x.png": 32,
    "icon32.png": 32, "icon32@2x.png": 64,
    "icon48.png": 48, "icon48@2x.png": 96,
    "icon64.png": 64, "icon64@2x.png": 128,
    "icon128.png": 128, "icon128@2x.png": 256,
    "icon256.png": 256, "icon256@2x.png": 512,
    "icon512.png": 512, "icon512@2x.png": 1024,
}
ICO_SIZES = [256, 128, 64, 48, 32, 16]


def main() -> None:
    badge = Image.open(SRC).convert("RGBA")

    def at(size: int) -> Image.Image:
        return badge.resize((size, size), Image.LANCZOS)

    # Runtime window/tray icon (bundled in telegram.qrc as :/gui/art/logo_256*).
    at(256).save(ART / "logo_256_no_margin.png")
    margined = Image.new("RGBA", (256, 256), (0, 0, 0, 0))
    inner = badge.resize((232, 232), Image.LANCZOS)
    margined.alpha_composite(inner, ((256 - 232) // 2, (256 - 232) // 2))
    margined.save(ART / "logo_256.png")

    for name, size in ICON_PNGS.items():
        at(size).save(ART / name)

    # Windows exe / Explorer / taskbar icon, embedded via Telegram.rc IDI_ICON1.
    at(256).save(ART / "icon256.ico", sizes=[(s, s) for s in ICO_SIZES])

    print(f"regenerated {len(ICON_PNGS) + 3} desktop icons from {SRC.name}")


if __name__ == "__main__":
    main()
