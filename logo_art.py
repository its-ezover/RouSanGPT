"""The RouSanGPT logo: a network (connected nodes), a graduation cap on top and a
padlock in front, for the two courses: Computer Networks and Cryptography.

It is drawn here, so it can be changed and made again in every size:

    python logo_art.py

writes web/logo-mark.png (tab, sidebar, avatar), web/logo.png and logo.png (with the
name, for the welcome screen and the README) and icons/ (app menu, Windows setup).
"""
import math
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont

ROOT = Path(__file__).resolve().parent
S = 2048                                    # drawn this big, then made smaller (smooth edges)

NAVY, NAVY_2 = "#0f2a4a", "#1d4570"
BLUE_TOP, BLUE_BOTTOM = "#5fd0ff", "#0a7fd1"
GOLD_TOP, GOLD_BOTTOM = "#ffd65a", "#f19a0b"


def _gradient(size, top, bottom):
    from PIL import ImageColor
    a, b = ImageColor.getrgb(top), ImageColor.getrgb(bottom)
    grad = Image.new("RGB", (1, size[1]))
    for y in range(size[1]):
        t = y / max(1, size[1] - 1)
        grad.putpixel((0, y), tuple(int(a[i] + (b[i] - a[i]) * t) for i in range(3)))
    return grad.resize(size)


def _fill(canvas, mask, top, bottom, box):
    """Paint the shape in mask with a top-to-bottom gradient over box."""
    x0, y0, x1, y1 = [int(v) for v in box]
    grad = Image.new("RGB", canvas.size)
    grad.paste(_gradient((x1 - x0, y1 - y0), top, bottom), (x0, y0))
    canvas.paste(grad, (0, 0), mask)


def _shape(draw_fn):
    mask = Image.new("L", (S, S), 0)
    draw_fn(ImageDraw.Draw(mask))
    return mask


def _outline(canvas, mask, width, color=(255, 255, 255, 255)):
    """A border around a shape (drawn under it): the shape made a little bigger."""
    grown = mask.filter(ImageFilter.MaxFilter(width * 2 + 1))
    layer = Image.new("RGBA", canvas.size, color)
    canvas.paste(layer, (0, 0), grown)


def mark():
    """The square logo (transparent background), S x S pixels."""
    img = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    cx, cy, r = S * 0.5, S * 0.62, S * 0.29

    # 1. the network: a ring of nodes, linked to each other and to the hub in the middle
    nodes = [(cx + r * math.cos(math.radians(a)), cy + r * math.sin(math.radians(a)))
             for a in (-90 + k * 60 for k in range(6))]
    links = [(nodes[k], nodes[(k + 1) % 6]) for k in range(6)] + [((cx, cy), n) for n in nodes]
    links += [(nodes[0], nodes[2]), (nodes[3], nodes[5])]
    glow = Image.new("RGBA", (S, S), (56, 189, 248, 0))
    gd = ImageDraw.Draw(glow)
    for a, b in links:
        gd.line([a, b], fill=(56, 189, 248, 150), width=int(S * 0.03))
    for (x, y) in nodes:
        gd.ellipse([x - S * .07, y - S * .07, x + S * .07, y + S * .07], fill=(56, 189, 248, 160))
    img.alpha_composite(glow.filter(ImageFilter.GaussianBlur(S * 0.02)))
    line_mask = _shape(lambda d: [d.line([a, b], fill=255, width=int(S * 0.022)) for a, b in links])
    _fill(img, line_mask, "#7fdcff", "#1b8fd6", (0, cy - r, S, cy + r))
    node_r = S * 0.052
    for (x, y) in nodes:
        m = _shape(lambda d, x=x, y=y: d.ellipse([x - node_r, y - node_r, x + node_r, y + node_r], fill=255))
        _outline(img, m, int(S * 0.012))
        _fill(img, m, BLUE_TOP, BLUE_BOTTOM, (x - node_r, y - node_r, x + node_r, y + node_r))
        d = ImageDraw.Draw(img)
        d.ellipse([x - node_r * .55, y - node_r * .75, x + node_r * .15, y - node_r * .2], fill=(255, 255, 255, 170))

    # 2. the padlock in front of the hub
    lw, lh = S * 0.30, S * 0.24
    lx0, ly0 = cx - lw / 2, cy - lh * 0.02
    shackle = _shape(lambda d: d.arc([cx - lw * .34, ly0 - lh * .78, cx + lw * .34, ly0 + lh * .42], 180, 360,
                                     fill=255, width=int(S * 0.045)))
    legs = _shape(lambda d: [d.rectangle([cx + sx * lw * .34 - S * .0225, ly0 - lh * .18, cx + sx * lw * .34 + S * .0225,
                                          ly0 + lh * .1], fill=255) for sx in (-1, 1)])
    shackle.paste(255, (0, 0), legs)
    _outline(img, shackle, int(S * 0.014))
    _fill(img, shackle, "#e9eef4", "#8a99ab", (cx - lw, ly0 - lh, cx + lw, ly0 + lh * .2))
    body = _shape(lambda d: d.rounded_rectangle([lx0, ly0, lx0 + lw, ly0 + lh], radius=S * 0.04, fill=255))
    _outline(img, body, int(S * 0.016))
    _fill(img, body, GOLD_TOP, GOLD_BOTTOM, (lx0, ly0, lx0 + lw, ly0 + lh))
    d = ImageDraw.Draw(img)
    shine = Image.new("RGBA", (S, S), (255, 255, 255, 0))                 # the shine, on its own layer
    ImageDraw.Draw(shine).rounded_rectangle([lx0 + lw * .1, ly0 + lh * .08, lx0 + lw * .9, ly0 + lh * .3],
                                            radius=S * 0.03, fill=(255, 255, 255, 60))
    img.alpha_composite(shine)
    d = ImageDraw.Draw(img)
    kx, ky = cx, ly0 + lh * .5
    d.ellipse([kx - S * .03, ky - S * .035, kx + S * .03, ky + S * .025], fill=NAVY)
    d.polygon([(kx - S * .018, ky), (kx + S * .018, ky), (kx + S * .028, ky + S * .075), (kx - S * .028, ky + S * .075)],
              fill=NAVY)

    # 3. the graduation cap on top
    top_y, bw, bh = S * 0.2, S * 0.36, S * 0.115
    board = [(cx, top_y - bh), (cx + bw, top_y), (cx, top_y + bh), (cx - bw, top_y)]
    skull = _shape(lambda d: d.chord([cx - bw * .55, top_y - bh * .2, cx + bw * .55, top_y + bh * 1.7], 0, 180, fill=255))
    skull_box = _shape(lambda d: d.rectangle([cx - bw * .55, top_y, cx + bw * .55, top_y + bh * .75], fill=255))
    skull.paste(255, (0, 0), skull_box)
    _outline(img, skull, int(S * 0.014))
    _fill(img, skull, NAVY_2, NAVY, (cx - bw, top_y, cx + bw, top_y + bh * 1.7))
    board_mask = _shape(lambda d: d.polygon(board, fill=255))
    _outline(img, board_mask, int(S * 0.014))
    _fill(img, board_mask, "#2a5a8a", NAVY, (cx - bw, top_y - bh, cx + bw, top_y + bh))
    d = ImageDraw.Draw(img)
    d.polygon([(cx, top_y - bh), (cx + bw, top_y), (cx + bw * .45, top_y + bh * .06), (cx - bw * .2, top_y - bh * .55)],
              fill=(255, 255, 255, 38))                                # light on the board
    # the tassel: from the button, over the edge, hanging down
    d.ellipse([cx - S * .022, top_y - S * .022, cx + S * .022, top_y + S * .022], fill=GOLD_BOTTOM)
    tx = cx + bw * .82
    d.line([(cx, top_y), (tx, top_y + bh * .35)], fill=GOLD_BOTTOM, width=int(S * 0.012))
    d.line([(tx, top_y + bh * .35), (tx, top_y + bh * 2.2)], fill=GOLD_BOTTOM, width=int(S * 0.012))
    tassel = [(tx - S * .028, top_y + bh * 2.1), (tx + S * .028, top_y + bh * 2.1), (tx + S * .036, top_y + bh * 3.0),
              (tx - S * .036, top_y + bh * 3.0)]
    tm = _shape(lambda d: d.polygon(tassel, fill=255))
    _fill(img, tm, GOLD_TOP, GOLD_BOTTOM, (tx - S * .04, top_y + bh * 2.1, tx + S * .04, top_y + bh * 3))

    # trim the empty border and centre the drawing in the square
    box = img.getbbox()
    pad = int(S * 0.04)
    cropped = img.crop(box)
    side = max(cropped.size) + 2 * pad
    out = Image.new("RGBA", (side, side), (0, 0, 0, 0))
    out.paste(cropped, ((side - cropped.width) // 2, (side - cropped.height) // 2), cropped)
    return out.resize((S, S), Image.Resampling.LANCZOS)


def with_name(icon):
    """The logo with the name under it (for the welcome screen and the README)."""
    from matplotlib import font_manager
    bold = font_manager.findfont(font_manager.FontProperties(family="DejaVu Sans", weight="bold"))
    w, h = 1600, 1500
    img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    img.alpha_composite(icon.resize((1180, 1180), Image.Resampling.LANCZOS), ((w - 1180) // 2, 0))
    d = ImageDraw.Draw(img)
    f = ImageFont.truetype(bold, 250)
    text = "RouSanGPT"
    tw = d.textlength(text, font=f)
    x, y = (w - tw) / 2, 1190
    mask = Image.new("L", (w, h), 0)
    ImageDraw.Draw(mask).text((x, y), text, font=f, fill=255)
    _outline(img, mask, 10, (255, 255, 255, 230))                  # readable on dark and light
    _fill(img, mask, "#29a8f0", "#0a6fb8", (0, y + 20, w, y + 290))
    return img.crop(img.getbbox())


def export():
    icon = mark()
    small = {}
    (ROOT / "icons").mkdir(exist_ok=True)
    for size in (48, 64, 128, 256, 512):
        small[size] = icon.resize((size, size), Image.Resampling.LANCZOS)
        small[size].save(ROOT / "icons" / f"rousangpt-{size}.png", optimize=True)
    icon.resize((256, 256), Image.Resampling.LANCZOS).save(
        ROOT / "icons" / "rousangpt.ico", sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])
    small[128].save(ROOT / "web" / "logo-mark.png", optimize=True)
    named = with_name(icon)
    for path, width in ((ROOT / "web" / "logo.png", 360), (ROOT / "logo.png", 480)):
        named.resize((width, round(named.height * width / named.width)), Image.Resampling.LANCZOS).save(path, optimize=True)
    return icon, named


if __name__ == "__main__":
    export()
    print("logo written: icons/, web/logo-mark.png, web/logo.png, logo.png")
