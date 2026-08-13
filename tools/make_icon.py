"""Generate the FTC Autovelox app icon.

The mark is the product's one real idea: a road with a highlighted stretch. The
sources never say exactly where a camera stands, only which stretch it is on, so
the icon shows a band across a road rather than a pin on a point. Amber because
that is the colour the app already uses for a monitored stretch.

Run: .venv/bin/python tools/make_icon.py
"""

from __future__ import annotations

import math
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont

OUT = Path("ios/App/Resources/Assets.xcassets/AppIcon.appiconset")
SIZE = 1024

INK = (11, 18, 32)
INK_TOP = (25, 40, 66)
ROAD = (43, 54, 74)
LINE = (233, 238, 245)
AMBER = (245, 158, 11)
AMBER_SOFT = (245, 158, 11, 120)


def _background(size: int) -> Image.Image:
    """A vertical gradient, dark at the bottom so the amber band carries."""
    image = Image.new("RGB", (size, size), INK)
    draw = ImageDraw.Draw(image)
    for y in range(size):
        t = y / size
        draw.line(
            [(0, y), (size, y)],
            fill=(
                int(INK_TOP[0] + (INK[0] - INK_TOP[0]) * t),
                int(INK_TOP[1] + (INK[1] - INK_TOP[1]) * t),
                int(INK_TOP[2] + (INK[2] - INK_TOP[2]) * t),
            ),
        )
    return image


def _road(image: Image.Image, size: int) -> None:
    """A road sweeping up the icon, drawn as a thick tapered polyline."""
    layer = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(layer)

    points = [
        (size * 0.16, size * 0.94),
        (size * 0.34, size * 0.70),
        (size * 0.46, size * 0.48),
        (size * 0.62, size * 0.26),
        (size * 0.84, size * 0.08),
    ]
    # Taper: wide at the bottom, narrow towards the horizon.
    for i in range(len(points) - 1):
        width = int(size * (0.20 - 0.030 * i))
        draw.line([points[i], points[i + 1]], fill=ROAD, width=width, joint="curve")

    # Centre dashes, thinning with the road.
    for i in range(len(points) - 1):
        x1, y1 = points[i]
        x2, y2 = points[i + 1]
        steps = 4
        for s in range(steps):
            a = s / steps
            b = a + 0.42 / steps
            draw.line(
                [
                    (x1 + (x2 - x1) * a, y1 + (y2 - y1) * a),
                    (x1 + (x2 - x1) * b, y1 + (y2 - y1) * b),
                ],
                fill=LINE + (210,),
                width=max(3, int(size * (0.016 - 0.0026 * i))),
            )
    image.paste(layer, (0, 0), layer)


def _stretch_band(image: Image.Image, size: int) -> None:
    """The highlighted stretch — the whole point of the product."""
    glow = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(glow)
    a = (size * 0.335, size * 0.705)
    b = (size * 0.475, size * 0.455)
    draw.line([a, b], fill=AMBER_SOFT, width=int(size * 0.30), joint="curve")
    glow = glow.filter(ImageFilter.GaussianBlur(size * 0.045))
    image.paste(glow, (0, 0), glow)

    layer = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(layer)
    draw.line([a, b], fill=AMBER + (255,), width=int(size * 0.175), joint="curve")
    image.paste(layer, (0, 0), layer)


def _font(px: int) -> ImageFont.FreeTypeFont:
    for candidate in (
        "/System/Library/Fonts/SFCompact.ttf",
        "/System/Library/Fonts/HelveticaNeue.ttc",
        "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
        "/Library/Fonts/Arial Bold.ttf",
    ):
        if Path(candidate).exists():
            try:
                return ImageFont.truetype(candidate, px)
            except OSError:
                continue
    return ImageFont.load_default()


def _wordmark(image: Image.Image, size: int) -> None:
    draw = ImageDraw.Draw(image)
    font = _font(int(size * 0.20))
    text = "FTC"
    box = draw.textbbox((0, 0), text, font=font)
    x = size * 0.085
    y = size * 0.075
    # A soft shadow keeps it readable over the gradient at small sizes.
    draw.text((x + size * 0.006, y + size * 0.006), text, font=font, fill=(0, 0, 0, 160))
    draw.text((x, y), text, font=font, fill=LINE)
    _ = box


def build(size: int = SIZE) -> Image.Image:
    image = _background(size)
    _road(image, size)
    _stretch_band(image, size)
    _wordmark(image, size)
    return image


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    icon = build(SIZE)
    icon.save(OUT / "icon-1024.png")

    contents = """{
  "images" : [
    {
      "filename" : "icon-1024.png",
      "idiom" : "universal",
      "platform" : "ios",
      "size" : "1024x1024"
    }
  ],
  "info" : { "author" : "xcode", "version" : 1 }
}
"""
    (OUT / "Contents.json").write_text(contents)

    # A quick look at how it holds up small.
    preview = Image.new("RGB", (760, 200), (248, 250, 252))
    x = 24
    for px in (180, 120, 80, 60, 40):
        thumb = icon.resize((px, px), Image.LANCZOS)
        preview.paste(thumb, (x, 100 - px // 2))
        x += px + 24
    preview.save("docs/screenshots/icon-sizes.png")
    print(f"wrote {OUT/'icon-1024.png'} and docs/screenshots/icon-sizes.png")


if __name__ == "__main__":
    main()
