#!/usr/bin/env python3
"""
Generate the application icons (renderer favicon/PWA PNGs and the Electron
installer .ico) from simple geometry so no hand-made binaries live in git.

    python scripts/make_icons.py

Requires Pillow (already a backend dependency).
"""

from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parent.parent
RENDERER_PUBLIC = ROOT / "src" / "renderer" / "public"
ASSETS = ROOT / "assets"

BG = (26, 35, 126)  # indigo 900 — matches the default pen colour
FG = (255, 255, 255)
ACCENT = (255, 193, 7)  # amber 500


def render(size: int) -> Image.Image:
    """Rounded indigo tile with a white 'x' and an amber '=' — 'solve for x'."""
    scale = 8  # draw large, downsample for smooth edges
    s = size * scale
    img = Image.new("RGBA", (s, s), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    radius = int(s * 0.22)
    d.rounded_rectangle((0, 0, s - 1, s - 1), radius=radius, fill=BG)

    stroke = max(1, int(s * 0.11))
    # 'x' occupying the left/centre
    x0, y0 = int(s * 0.20), int(s * 0.30)
    x1, y1 = int(s * 0.52), int(s * 0.74)
    d.line((x0, y0, x1, y1), fill=FG, width=stroke)
    d.line((x0, y1, x1, y0), fill=FG, width=stroke)
    # '=' on the right
    ex0, ex1 = int(s * 0.60), int(s * 0.84)
    for cy in (int(s * 0.44), int(s * 0.60)):
        d.rounded_rectangle((ex0, cy - stroke // 2, ex1, cy + stroke // 2), radius=stroke // 2, fill=ACCENT)

    return img.resize((size, size), Image.LANCZOS)


def main() -> None:
    RENDERER_PUBLIC.mkdir(parents=True, exist_ok=True)
    ASSETS.mkdir(parents=True, exist_ok=True)

    for size in (192, 512):
        render(size).save(RENDERER_PUBLIC / f"logo{size}.png", optimize=True)

    ico_sizes = [16, 24, 32, 48, 64, 128, 256]
    base = render(256)
    base.save(RENDERER_PUBLIC / "favicon.ico", sizes=[(n, n) for n in ico_sizes if n <= 64])
    base.save(ASSETS / "icon.ico", sizes=[(n, n) for n in ico_sizes])
    render(512).save(ASSETS / "icon.png", optimize=True)
    print("icons written to", RENDERER_PUBLIC, "and", ASSETS)


if __name__ == "__main__":
    main()
