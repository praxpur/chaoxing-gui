"""生成扁平化 Material Design 3 风格图标。

输出到 packaging/assets/：logo.svg（矢量母版）、logo.png（1024px）、
app.ico（多尺寸）、logo_preview.png（尺寸检查图）。
用法：python packaging/build_logo_ico.py
"""
from pathlib import Path
from PIL import Image, ImageDraw

HERE = Path(__file__).resolve().parent
ASSETS = HERE / "assets"
CANVAS = 1024
SCALE = 4
PRIMARY = "#6750A4"
ON_PRIMARY = "#EADDFF"
TERTIARY = "#EFB8C8"
SIZES = (16, 24, 32, 48, 64, 128, 256)


def cubic(p0, p1, p2, p3, steps=24):
    points = []
    for i in range(1, steps + 1):
        t = i / steps
        u = 1 - t
        points.append((
            u**3 * p0[0] + 3 * u**2 * t * p1[0] + 3 * u * t**2 * p2[0] + t**3 * p3[0],
            u**3 * p0[1] + 3 * u**2 * t * p1[1] + 3 * u * t**2 * p2[1] + t**3 * p3[1],
        ))
    return points


def book_page(mirror=False):
    def p(x, y):
        return (CANVAS - x if mirror else x, y)

    start = p(252, 400)
    points = [start]
    current = start
    segments = [
        (p(342, 382), p(434, 402), p(512, 462)),
    ]
    for c1, c2, end in segments:
        points.extend(cubic(current, c1, c2, end))
        current = end
    points.append(p(512, 768))
    current = p(512, 768)
    for c1, c2, end in [
        (p(430, 710), p(344, 688), p(240, 704)),
        (p(222, 707), p(208, 693), p(208, 675)),
    ]:
        points.extend(cubic(current, c1, c2, end))
        current = end
    points.append(p(208, 440))
    current = p(208, 440)
    points.extend(cubic(current, p(208, 420), p(226, 406), start))
    return points


def sparkle():
    return [
        (512, 174), (540, 254), (620, 282), (540, 310),
        (512, 390), (484, 310), (404, 282), (484, 254),
    ]


def scaled(points):
    return [(round(x * SCALE), round(y * SCALE)) for x, y in points]


def render_png():
    image = Image.new("RGBA", (CANVAS * SCALE, CANVAS * SCALE), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    draw.rounded_rectangle(
        (48 * SCALE, 48 * SCALE, 976 * SCALE, 976 * SCALE),
        radius=220 * SCALE,
        fill=PRIMARY,
    )
    draw.polygon(scaled(book_page()), fill=ON_PRIMARY)
    draw.polygon(scaled(book_page(mirror=True)), fill=ON_PRIMARY)
    draw.polygon(scaled(sparkle()), fill=TERTIARY)
    image = image.resize((CANVAS, CANVAS), Image.Resampling.LANCZOS)
    image.save(ASSETS / "logo.png")
    return image


def write_svg():
    left = "M252 400 C342 382 434 402 512 462 L512 768 C430 710 344 688 240 704 C222 707 208 693 208 675 L208 440 C208 420 226 406 252 400 Z"
    star = " ".join(f"{x},{y}" for x, y in sparkle())
    svg = f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1024 1024">
  <rect x="48" y="48" width="928" height="928" rx="220" fill="{PRIMARY}"/>
  <path d="{left}" fill="{ON_PRIMARY}"/>
  <path d="{left}" transform="translate(1024 0) scale(-1 1)" fill="{ON_PRIMARY}"/>
  <polygon points="{star}" fill="{TERTIARY}"/>
</svg>
'''
    (ASSETS / "logo.svg").write_text(svg, encoding="utf-8")


def main():
    ASSETS.mkdir(parents=True, exist_ok=True)
    write_svg()
    image = render_png()
    image.save(ASSETS / "app.ico", format="ICO", sizes=[(size, size) for size in SIZES])
    preview = Image.new("RGBA", (1120, 360), "#F7F2FA")
    for x, size in [(32, 256), (336, 128), (512, 64), (624, 48), (720, 32), (800, 24), (872, 16)]:
        icon = image.resize((size, size), Image.Resampling.LANCZOS)
        preview.alpha_composite(icon, (x, 52 + (256 - size) // 2))
    preview.convert("RGB").save(ASSETS / "logo_preview.png")
    for name in ("logo.svg", "logo.png", "app.ico", "logo_preview.png"):
        print(f"Generated: {ASSETS / name}")


if __name__ == "__main__":
    main()
