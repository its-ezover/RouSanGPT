"""The app's looks (Settings > Look): Classic, Frutiger Aero, Cybercore and Y2K.

Everything that differs between the looks is here: the colours of the pictures and
animations, the backgrounds, titles and boxes of every frame, and the panels and
bullets of the video slides. The page's own styles are in web/index.html, the device
icons in device_icons.py and the page's icons in ui_icons.py.

    look = current()                    # what Settings > Look says
    background(look, light)             # the backdrop of a frame (made once)
    title(d, text, look, light)         # the title bar and the title of a frame
    box(d, xy, radius, fill, ...)       # a box in the look's style
"""
from functools import lru_cache

from PIL import Image, ImageColor, ImageDraw, ImageFilter

import settings

W, H = 1280, 720
NAMES = {
    "classic": "Classic (flat)",
    "aero": "Frutiger Aero (glass and gloss)",
    "cybercore": "Cybercore (neon, grid and scanlines)",
    "y2k": "Y2K (chrome, holographic and sparkles)",
}


def current():
    return settings.look()


def mix(color, other, amount):
    a, b = ImageColor.getrgb(color)[:3], ImageColor.getrgb(other)[:3]
    return "#%02x%02x%02x" % tuple(int(x + (y - x) * amount) for x, y in zip(a, b))


# ---------- colours of the pictures (the keys of visual_kit's LIGHT and DARK) ----------

_BASE_LIGHT = dict(bg="#ffffff", text="#0f172a", muted="#64748b", line="#cbd5e1", head="#e0f2fe",
                   accent="#0284c7", mark="#fde68a", cell="#f8fafc", good="#15803d", bad="#b91c1c",
                   on_accent="#ffffff", second="#7c3aed", warn="#c2410c")
_BASE_DARK = dict(bg="#0f172a", text="#e2e8f0", muted="#94a3b8", line="#334155", head="#1e293b",
                  accent="#38bdf8", mark="#854d0e", cell="#111827", good="#4ade80", bad="#f87171",
                  on_accent="#062030", second="#a78bfa", warn="#fb923c")
PICTURE = {
    "classic": {"light": _BASE_LIGHT, "dark": _BASE_DARK},
    "aero": {"light": _BASE_LIGHT, "dark": _BASE_DARK},
    "cybercore": {
        "light": dict(bg="#f4f2ff", text="#14082b", muted="#5a4f7a", line="#c9c2ee", head="#ebe3ff",
                      accent="#b000f0", mark="#ffd6fb", cell="#ffffff", good="#00a650", bad="#e0005a",
                      on_accent="#ffffff", second="#0090b0", warn="#e06000"),
        "dark": dict(bg="#05010d", text="#e8f7ff", muted="#8aa5c8", line="#2b1f55", head="#160736",
                     accent="#00f0ff", mark="#4a0e5c", cell="#0a0618", good="#39ff14", bad="#ff2a6d",
                     on_accent="#05010d", second="#ff00e5", warn="#ffb300"),
    },
    "y2k": {
        "light": dict(bg="#fff4fd", text="#3a1450", muted="#8a6a9e", line="#ecc9f5", head="#ffe0f7",
                      accent="#e83fb0", mark="#d9f3ff", cell="#ffffff", good="#1f9f84", bad="#ff3d7a",
                      on_accent="#ffffff", second="#7a63f0", warn="#e8890c"),
        "dark": dict(bg="#1b0b2e", text="#fbe9ff", muted="#c7a6dc", line="#4b2a66", head="#2c1248",
                     accent="#ff7ad9", mark="#5a2a75", cell="#22103a", good="#5ef0c8", bad="#ff7096",
                     on_accent="#2a0d3a", second="#a99bff", warn="#ffc46b"),
    },
}

# packets and arrows in the animations, one colour after the other
PACKETS = {
    "classic": ["#38bdf8", "#a78bfa", "#f472b6", "#fb923c", "#facc15", "#4ade80"],
    "aero": ["#38bdf8", "#a78bfa", "#f472b6", "#fb923c", "#facc15", "#4ade80"],
    "cybercore": ["#00f0ff", "#ff00e5", "#39ff14", "#ffb300", "#b026ff", "#ff2a6d"],
    "y2k": ["#ff7ad9", "#a99bff", "#7ad7ff", "#ffc46b", "#5ef0c8", "#ff9ec7"],
}


def picture_palette(theme, look=None):
    return PICTURE[look or current()]["dark" if theme == "dark" else "light"]


def still_theme(look=None):
    """The theme of the pictures shown in the chat: dark for Cybercore, light otherwise."""
    return "dark" if (look or current()) == "cybercore" else "light"


def anim(look=None):
    """Colours for the animations (always on the dark theme)."""
    look = look or current()
    p = PICTURE[look]["dark"]
    return dict(bg=p["bg"], text=p["text"], muted=p["muted"], line=mix(p["line"], p["text"], 0.2),
                accent=p["accent"], second=p["second"], good=p["good"], warn=p["warn"], bad=p["bad"],
                waiting="#facc15" if look in ("classic", "aero") else p["warn"], node=p["head"],
                caption="#fbbf24" if look in ("classic", "aero") else p["warn"], packets=PACKETS[look])


# ---------- backgrounds ----------

def _gradient(stops, size=(W, H)):
    img = Image.new("RGB", size)
    d = ImageDraw.Draw(img)
    w, h = size
    for y in range(h):
        t = y / (h - 1)
        for (t0, c0), (t1, c1) in zip(stops, stops[1:]):
            if t0 <= t <= t1:
                d.line([(0, y), (w, y)], fill=mix(c0, c1, (t - t0) / (t1 - t0)))
                break
    return img


def _glows(out, glows, blur=110):
    for box_xy, rgb, alpha in glows:
        # each glow on its own layer, whose see-through pixels already have its colour, so
        # the blur fades it out instead of mixing in black (which would make a grey smudge)
        glow = Image.new("RGBA", (W, H), rgb + (0,))
        ImageDraw.Draw(glow).ellipse(box_xy, fill=rgb + (alpha,))
        out.alpha_composite(glow.filter(ImageFilter.GaussianBlur(blur)))


def _bubbles(out, light, positions=((1130, 140, 34), (1185, 230, 18), (1060, 610, 26), (70, 640, 22), (140, 560, 12))):
    layer = Image.new("RGBA", (W, H), (255, 255, 255, 0))
    b = ImageDraw.Draw(layer)
    for (x, y, r) in positions:
        b.ellipse([x - r, y - r, x + r, y + r], outline=(255, 255, 255, 60 if light else 40), width=2)
        b.ellipse([x - r * .5, y - r * .7, x - r * .05, y - r * .35], fill=(255, 255, 255, 70 if light else 45))
    out.alpha_composite(layer.filter(ImageFilter.GaussianBlur(1)))


def _sparkle(d, x, y, r, fill):
    """A four-pointed star."""
    t = r * 0.22
    d.polygon([(x, y - r), (x + t, y - t), (x + r, y), (x + t, y + t), (x, y + r), (x - t, y + t),
               (x - r, y), (x - t, y - t)], fill=fill)


def _aero_bg(light):
    stops = ([(0, "#bfe5ff"), (0.5, "#e6f5ff"), (1, "#f5fbff")] if light else
             [(0, "#031a2d"), (0.55, "#06304f"), (1, "#073d4a")])
    out = _gradient(stops).convert("RGBA")
    _glows(out, [([-260, -320, 640, 300], (255, 255, 255), 200), ([820, 470, 1520, 980], (120, 214, 130), 95),
                 ([880, 60, 1120, 300], (255, 255, 255), 110)] if light else
           [([-260, -320, 640, 300], (76, 195, 255), 70), ([820, 470, 1520, 980], (70, 200, 140), 60),
            ([900, 80, 1120, 300], (143, 220, 255), 40)])
    _bubbles(out, light)
    return out


def _cyber_bg(light):
    stops = ([(0, "#f6f4ff"), (1, "#e9e3ff")] if light else [(0, "#05010d"), (0.6, "#12042a"), (1, "#05010d")])
    out = _gradient(stops).convert("RGBA")
    horizon = int(H * 0.58)
    _glows(out, [([200, horizon - 120, 1080, horizon + 120], (255, 0, 229) if not light else (196, 0, 255),
                  90 if not light else 45),
                 ([-200, -260, 500, 200], (0, 240, 255) if not light else (0, 160, 200), 50 if not light else 30)], 90)
    grid = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    g = ImageDraw.Draw(grid)
    pink = (255, 0, 229, 110) if not light else (176, 0, 240, 60)
    cyan = (0, 240, 255, 70) if not light else (0, 144, 176, 45)
    for k in range(1, 16):                              # the floor, getting closer
        y = horizon + (H - horizon) * (k / 15) ** 1.9
        g.line([(0, y), (W, y)], fill=pink, width=2)
    for k in range(-14, 15):                            # lines to the vanishing point
        g.line([(W / 2 + k * 16, horizon), (W / 2 + k * 150, H)], fill=cyan, width=2)
    g.line([(0, horizon), (W, horizon)], fill=pink, width=2)
    out.alpha_composite(grid.filter(ImageFilter.GaussianBlur(4)))     # the neon glow
    out.alpha_composite(grid)
    lines = Image.new("RGBA", (W, H), (0, 0, 0, 0))     # scanlines
    sl = ImageDraw.Draw(lines)
    for y in range(0, H, 3):
        sl.line([(0, y), (W, y)], fill=(0, 0, 0, 34 if not light else 10))
    out.alpha_composite(lines)
    hud = ImageDraw.Draw(out)                           # HUD corner brackets
    c = (0, 240, 255, 170) if not light else (176, 0, 240, 150)
    for x, y, sx, sy in ((14, 20, 1, 1), (W - 14, 20, -1, 1), (14, H - 14, 1, -1), (W - 14, H - 14, -1, -1)):
        hud.line([(x, y), (x + 40 * sx, y)], fill=c, width=3)
        hud.line([(x, y), (x, y + 40 * sy)], fill=c, width=3)
    return out


def _y2k_bg(light):
    grid = ([["#ffd6f2", "#e6d6ff", "#cfeeff", "#ffe7c7"], ["#d8fff0", "#ffe9f7", "#f3d9ff", "#d6ecff"],
             ["#e6d6ff", "#cfeeff", "#ffd6f2", "#e8fff4"]] if light else
            [["#2a0d45", "#1b0b2e", "#0e2a4a", "#3a0f4d"], ["#3a0f4d", "#1d1440", "#22103a", "#0e2a4a"],
             ["#1b0b2e", "#2a0d45", "#14264a", "#2a0d45"]])
    small = Image.new("RGB", (len(grid[0]), len(grid)))
    for y, row in enumerate(grid):
        for x, color in enumerate(row):
            small.putpixel((x, y), ImageColor.getrgb(color))
    out = small.resize((W, H), Image.Resampling.BICUBIC).filter(ImageFilter.GaussianBlur(30)).convert("RGBA")
    _glows(out, [([-200, -200, 520, 300], (255, 255, 255) if light else (255, 122, 217), 150 if light else 60),
                 ([860, 420, 1500, 960], (143, 211, 255) if light else (122, 215, 255), 110 if light else 45)], 100)
    _bubbles(out, light, ((1120, 160, 40), (1190, 260, 20), (90, 600, 30), (170, 670, 14), (1000, 640, 22)))
    stars = Image.new("RGBA", (W, H), (255, 255, 255, 0))
    s = ImageDraw.Draw(stars)
    for (x, y, r) in ((1040, 110, 16), (1210, 90, 9), (160, 140, 11), (60, 470, 14), (1150, 470, 12),
                      (640, 690, 9), (380, 60, 7), (900, 680, 13)):
        _sparkle(s, x, y, r, (255, 255, 255, 230 if light else 200))
        _sparkle(s, x, y, r * 0.45, (255, 180, 236, 255) if light else (255, 122, 217, 255))
    out.alpha_composite(stars.filter(ImageFilter.GaussianBlur(0.6)))
    return out


@lru_cache(maxsize=8)
def background(look=None, light=False):
    """The backdrop of a frame in a look (made once, then copied)."""
    look = look or current()
    if look == "aero":
        img = _aero_bg(light)
    elif look == "cybercore":
        img = _cyber_bg(light)
    elif look == "y2k":
        img = _y2k_bg(light)
    else:
        return Image.new("RGB", (W, H), "#ffffff" if light else "#0f172a")
    return img.convert("RGB")


# ---------- titles ----------

def title_text(d, xy, text, font, look=None, light=False):
    """A title in the look's style: a glow, a chromatic split or a chrome outline."""
    look = look or current()
    x, y = xy
    if look == "aero":
        d.text((x + 2, y + 3), text, font=font, fill="#7fb4d6" if light else "#021627")
        d.text((x, y), text, font=font, fill="#0b2a45" if light else "white")
    elif look == "cybercore":
        d.text((x - 3, y), text, font=font, fill="#ff00e5" if not light else "#e060ff")     # the glitch
        d.text((x + 3, y), text, font=font, fill="#00f0ff" if not light else "#40c8e0")
        d.text((x, y), text, font=font, fill="#ffffff" if not light else "#14082b")
    elif look == "y2k":
        d.text((x + 3, y + 4), text, font=font, fill="#b98ce0" if light else "#0b0216")
        d.text((x, y), text, font=font, fill="#ffffff", stroke_width=3,
               stroke_fill="#e83fb0" if light else "#ff7ad9")
    else:
        d.text((x, y), text, font=font, fill="#0f172a" if light else "white")


def title(d, text, look=None, light=False):
    """The top bar and the title of a frame."""
    from animation_tools import font, mono_font
    look = look or current()
    if look == "aero":
        d.rectangle([0, 0, W, 12], fill="#2aa7ee" if light else "#3fb2f5")
        d.rectangle([0, 0, W, 4], fill="#bdeaff")
    elif look == "cybercore":
        d.rectangle([0, 0, W, 5], fill="#ff00e5" if not light else "#b000f0")
        d.rectangle([0, 5, W, 8], fill="#00f0ff" if not light else "#0090b0")
        for k in range(0, W, 64):                          # HUD ticks
            d.line([(k, 8), (k, 14)], fill="#00f0ff" if not light else "#0090b0", width=2)
    elif look == "y2k":
        for k, color in enumerate(("#ff7ad9", "#c9a6ff", "#7ad7ff", "#9ff5d6")):
            d.rectangle([k * W / 4, 0, (k + 1) * W / 4, 10], fill=color)
        d.rectangle([0, 0, W, 3], fill="#ffffff")
    else:
        d.rectangle([0, 0, W, 12], fill="#0284c7" if light else "#38bdf8")
    from rich_text import unicode
    f = mono_font(40, True) if look == "cybercore" else font(42, True)
    shown = unicode(text)[:48]                          # 2^k * q -> 2ᵏ · q
    shown = shown.upper() if look == "cybercore" else shown
    title_text(d, (80, 55), shown, f, look, light)


# ---------- boxes ----------

def box(d, xy, radius, fill, outline=None, width=1, light=False, look=None):
    """A box in the look's style: flat, glossy (Aero), sharp and lit (Cybercore) or a
    rounder candy bubble (Y2K)."""
    look = look or current()
    x0, y0, x1, y1 = xy
    w, h = x1 - x0, y1 - y0
    if look == "cybercore":
        radius = min(radius, 3)
    elif look == "y2k":
        radius = min(radius * 1.8 + 2, h / 2, w / 2)
    d.rounded_rectangle(xy, radius=radius, fill=fill, outline=outline, width=width)
    if fill is None or w < 6 or h < 6 or look == "classic":
        return
    if look == "cybercore":
        d.line([(x0 + 2, y0 + 1), (x1 - 2, y0 + 1)], fill=mix(fill, "#ffffff", 0.55), width=2)
        return
    top = mix(fill, "#ffffff", 0.30 if light else 0.22)
    inset = max(1, width)
    half = [x0 + inset, y0 + inset, x1 - inset, y0 + h * 0.48]
    try:
        d.rounded_rectangle(half, radius=max(0, radius - inset), fill=top, corners=(True, True, False, False))
    except TypeError:                                   # older Pillow: no per-corner rounding
        d.rectangle(half, fill=top)
    if h > 14:
        d.line([(x0 + radius, y0 + inset + 1), (x1 - radius, y0 + inset + 1)], fill=mix(fill, "#ffffff", 0.6), width=1)
    if look == "y2k" and h > 18 and w > 18:             # a little shine dot
        r = min(h, w) * 0.09
        d.ellipse([x0 + radius * 0.6 + r, y0 + h * 0.18, x0 + radius * 0.6 + 3 * r, y0 + h * 0.18 + 2 * r],
                  fill=mix(fill, "#ffffff", 0.85))


# ---------- the video slides ----------

def panel(img, box_xy, look=None, card=False):
    """The panel behind a slide's bullets, or the card around its picture (card=True)."""
    look = look or current()
    x0, y0, x1, y1 = box_xy
    out = img.convert("RGBA")
    if look == "classic":
        if card:
            ImageDraw.Draw(out).rounded_rectangle(box_xy, radius=18, fill="white")
        return out.convert("RGB")
    radius = {"aero": 18 if card else 24, "cybercore": 2, "y2k": 34 if card else 40}[look]
    shadow = Image.new("RGBA", img.size, (0, 0, 0, 0))
    shadow_color = {"aero": (0, 10, 25, 140 if card else 110), "cybercore": (255, 0, 229, 70),
                    "y2k": (120, 20, 110, 90)}[look]
    ImageDraw.Draw(shadow).rounded_rectangle([x0, y0 + (0 if look == "cybercore" else 10), x1, y1 + 10],
                                             radius=radius, fill=shadow_color)
    out.alpha_composite(shadow.filter(ImageFilter.GaussianBlur(16 if look == "cybercore" else 14)))
    layer = Image.new("RGBA", img.size, (0, 0, 0, 0))
    ld = ImageDraw.Draw(layer)
    if look == "aero":
        fill, edge = ((255, 255, 255, 255) if card else (255, 255, 255, 22)), (160, 220, 255, 70)
    elif look == "cybercore":
        fill, edge = ((10, 6, 24, 255) if card else (8, 3, 20, 170)), (0, 240, 255, 200)
    else:
        fill, edge = ((255, 255, 255, 255) if card else (255, 255, 255, 34)), (255, 122, 217, 200)
    ld.rounded_rectangle(box_xy, radius=radius, fill=fill, outline=edge, width=3 if look == "y2k" else 2)
    out.alpha_composite(layer)
    deco = Image.new("RGBA", img.size, (0, 0, 0, 0))   # on its own layer: drawn on the panel it would replace it
    dd = ImageDraw.Draw(deco)
    if look == "cybercore":
        for x, y, sx, sy in ((x0, y0, 1, 1), (x1, y0, -1, 1), (x0, y1, 1, -1), (x1, y1, -1, -1)):
            dd.line([(x, y), (x + 34 * sx, y)], fill=(255, 0, 229, 255), width=4)
            dd.line([(x, y), (x, y + 34 * sy)], fill=(255, 0, 229, 255), width=4)
    elif not card:
        dd.rounded_rectangle([x0 + 2, y0 + 2, x1 - 2, y0 + (y1 - y0) * 0.42], radius=radius,
                             fill=(255, 255, 255, 16 if look == "aero" else 22), corners=(True, True, False, False))
    out.alpha_composite(deco)
    return out.convert("RGB")


def bullet(d, x, y, look=None):
    """The mark before a bullet point, centred at (x, y)."""
    look = look or current()
    if look == "aero":
        d.ellipse([x - 10, y - 10, x + 10, y + 10], fill="#1b93de", outline="#0b6db3")
        d.ellipse([x - 6, y - 8, x + 6, y], fill="#9fe2ff")
    elif look == "cybercore":
        d.polygon([(x - 9, y - 11), (x + 9, y), (x - 9, y + 11), (x - 4, y)], fill="#00f0ff")
    elif look == "y2k":
        _sparkle(d, x, y, 15, "#ff7ad9")
        _sparkle(d, x, y, 6, "#ffffff")
    else:
        d.ellipse([x - 7, y - 7, x + 7, y + 7], fill="#38bdf8")


def slide_text_color(look=None):
    return {"classic": "#e2e8f0", "aero": "#e7f5ff", "cybercore": "#e8f7ff", "y2k": "#fbe9ff"}[look or current()]


# ---------- Graphviz and matplotlib diagrams ----------

def diagram(look=None):
    """Colours of the diagrams drawn with Graphviz and matplotlib. Classic keeps the
    original look (white, black lines)."""
    look = look or current()
    if look == "classic":
        return dict(bg="white", text="black", line="gray", arrow="black", box="#dbeafe", edge="black",
                    font="", icons="light")
    p = picture_palette(still_theme(look), look)
    return dict(bg=p["bg"], text=p["text"], line=p["muted"], arrow=p["accent"], box=p["head"], edge=p["accent"],
                font="DejaVu Sans Mono" if look == "cybercore" else "", icons=still_theme(look))


def graphviz_args(look=None):
    """Graphviz command-line defaults for the look (a node or link that sets its own
    colour keeps it)."""
    c = diagram(look)
    if (look or current()) == "classic":
        return []
    args = [f"-Gbgcolor={c['bg']}", f"-Gfontcolor={c['text']}", f"-Nfontcolor={c['text']}",
            f"-Ncolor={c['edge']}", f"-Ecolor={c['edge']}", f"-Efontcolor={c['text']}"]
    if c["font"]:
        args += [f"-Gfontname={c['font']}", f"-Nfontname={c['font']}", f"-Efontname={c['font']}"]
    return args
