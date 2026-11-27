"""The page's own icons (Settings, Materials, Tools, search, theme, microphone,
Listen, Copy...) for the Frutiger Aero, Cybercore and Y2K looks, with the same
finish as device_icons.py (gloss, neon glow, candy sparkle). The Classic look keeps
the page's line icons.

They are saved as PNG files in web/looks/<look>/, which the page shows. Run this
file to make them again after changing a drawing:

    python ui_icons.py
"""
import math
from pathlib import Path

from PIL import Image, ImageDraw

import device_icons
from device_icons import SCALE, _aero, _arrowhead, _candy, _key, _lock, _neon

# one set per look, for both themes: colours with an outline that shows on both
PALETTES = {
    "aero": dict(line="#245a86", body="#eaf4fc", screen="#2a9fe6", accent="#2a9fe6", second="#7b5ce0",
                 warn="#f39a2b", bad="#e0443a", good="#43b649", paper="#ffffff", dim="#9db5c9",
                 gold="#f6c431", silver="#c9d6e2"),
    "cybercore": dict(line="#00e5ff", body="#120a2a", screen="#ff2bd6", accent="#00e5ff", second="#b026ff",
                      warn="#ffb300", bad="#ff2a6d", good="#39ff14", paper="#e8f7ff", dim="#5a4f8a",
                      gold="#ffe600", silver="#2a2050"),
    "y2k": dict(line="#8a3fb0", body="#fff0fb", screen="#8fd3ff", accent="#ff6fd0", second="#a99bff",
                warn="#ffb347", bad="#ff5c8a", good="#4fd1b5", paper="#ffffff", dim="#d9b8ea",
                gold="#ffd84d", silver="#efe4fa"),
}
FINISH = {"aero": lambda img: _aero(img, "light"), "cybercore": lambda img: _neon(img, "dark"),
          "y2k": lambda img: _candy(img, "light")}
P = PALETTES["aero"]
OUT = Path(__file__).resolve().parent / "web" / "looks"


def _gear(d, x, y, s, c, w):
    cx, cy = x + s * .5, y + s * .5
    pts = []
    for k in range(20):
        r = s * (.44 if k % 2 == 0 else .34)
        a = k * math.pi / 10
        pts.append((cx + r * math.cos(a), cy + r * math.sin(a)))
    d.polygon(pts, fill=c["silver"], outline=c["line"], width=w)
    d.ellipse([cx - s * .2, cy - s * .2, cx + s * .2, cy + s * .2], fill=c["accent"], outline=c["line"], width=w)
    d.ellipse([cx - s * .09, cy - s * .09, cx + s * .09, cy + s * .09], fill=c["paper"])


def _book(d, x, y, s, c, w):
    d.rounded_rectangle([x + s * .16, y + s * .08, x + s * .84, y + s * .92], radius=s * .06,
                        fill=c["accent"], outline=c["line"], width=w)
    d.rectangle([x + s * .24, y + s * .74, x + s * .84 - w, y + s * .86], fill=c["paper"])
    d.line([(x + s * .24, y + s * .08), (x + s * .24, y + s * .92)], fill=c["line"], width=w)
    d.rounded_rectangle([x + s * .36, y + s * .22, x + s * .74, y + s * .36], radius=s * .03, fill=c["paper"])


def _calculator(d, x, y, s, c, w):
    d.rounded_rectangle([x + s * .18, y + s * .06, x + s * .82, y + s * .94], radius=s * .08,
                        fill=c["silver"], outline=c["line"], width=w)
    d.rounded_rectangle([x + s * .27, y + s * .14, x + s * .73, y + s * .32], radius=s * .03,
                        fill="#bdf0c6", outline=c["line"], width=max(1, w - 1))
    for r in range(3):
        for col in range(3):
            l, t = x + s * (.27 + col * .16), y + s * (.42 + r * .16)
            fill = c["warn"] if col == 2 else c["accent"]
            d.rounded_rectangle([l, t, l + s * .12, t + s * .11], radius=s * .02, fill=fill)


def _search(d, x, y, s, c, w):
    d.line([(x + s * .6, y + s * .6), (x + s * .88, y + s * .88)], fill=c["line"], width=int(s * .12))
    d.ellipse([x + s * .1, y + s * .1, x + s * .66, y + s * .66], fill="#bfe6ff", outline=c["line"], width=w + 2)
    d.arc([x + s * .2, y + s * .2, x + s * .56, y + s * .56], 200, 260, fill=c["paper"], width=w + 1)


def _sidebar(d, x, y, s, c, w):
    d.rounded_rectangle([x + s * .08, y + s * .16, x + s * .92, y + s * .84], radius=s * .08,
                        fill=c["paper"], outline=c["line"], width=w)
    d.rounded_rectangle([x + s * .08, y + s * .16, x + s * .38, y + s * .84], radius=s * .08,
                        fill=c["accent"], outline=c["line"], width=w, corners=(True, False, False, True))
    for k in range(3):
        yy = y + s * (.32 + k * .14)
        d.line([(x + s * .15, yy), (x + s * .31, yy)], fill=c["paper"], width=w)


def _menu(d, x, y, s, c, w):
    for k in range(3):
        t = y + s * (.2 + k * .24)
        d.rounded_rectangle([x + s * .12, t, x + s * .88, t + s * .14], radius=s * .07, fill=c["accent"],
                            outline=c["line"], width=max(1, w - 1))


def _moon(d, x, y, s, c, w):
    d.ellipse([x + s * .12, y + s * .1, x + s * .84, y + s * .82], fill=c["gold"], outline="#b8860b", width=w)
    d.ellipse([x + s * .36, y + s * .02, x + s * 1.0, y + s * .66], fill=(0, 0, 0, 0))
    d.arc([x + s * .36, y + s * .02, x + s * 1.0, y + s * .66], 95, 235, fill="#b8860b", width=w)


def _sun(d, x, y, s, c, w):
    cx, cy = x + s * .5, y + s * .5
    for k in range(8):
        a = k * math.pi / 4
        d.line([(cx + s * .3 * math.cos(a), cy + s * .3 * math.sin(a)),
                (cx + s * .46 * math.cos(a), cy + s * .46 * math.sin(a))], fill=c["warn"], width=int(s * .08))
    d.ellipse([cx - s * .24, cy - s * .24, cx + s * .24, cy + s * .24], fill=c["gold"], outline=c["warn"], width=w)


def _orb(d, x, y, s, color, outline):
    d.ellipse([x + s * .08, y + s * .08, x + s * .92, y + s * .92], fill=color, outline=outline, width=max(2, s // 26))


def _close(d, x, y, s, c, w):
    _orb(d, x, y, s, c["bad"], "#a52a22")
    d.line([(x + s * .34, y + s * .34), (x + s * .66, y + s * .66)], fill=c["paper"], width=int(s * .1))
    d.line([(x + s * .66, y + s * .34), (x + s * .34, y + s * .66)], fill=c["paper"], width=int(s * .1))


def _check(d, x, y, s, c, w):
    _orb(d, x, y, s, c["good"], "#2f7f33")
    d.line([(x + s * .28, y + s * .52), (x + s * .44, y + s * .68), (x + s * .72, y + s * .36)],
           fill=c["paper"], width=int(s * .1), joint="curve")


def _play(d, x, y, s, c, w):
    _orb(d, x, y, s, c["good"], "#2f7f33")
    d.polygon([(x + s * .4, y + s * .3), (x + s * .72, y + s * .5), (x + s * .4, y + s * .7)], fill=c["paper"])


def _stop(d, x, y, s, c, w):
    d.rounded_rectangle([x + s * .18, y + s * .18, x + s * .82, y + s * .82], radius=s * .12,
                        fill=c["bad"], outline="#a52a22", width=w)


def _mic(d, x, y, s, c, w):
    d.arc([x + s * .2, y + s * .24, x + s * .8, y + s * .74], 0, 180, fill=c["line"], width=int(s * .07))
    d.line([(x + s * .5, y + s * .74), (x + s * .5, y + s * .88)], fill=c["line"], width=int(s * .07))
    d.rounded_rectangle([x + s * .3, y + s * .88, x + s * .7, y + s * .95], radius=s * .03, fill=c["line"])
    d.rounded_rectangle([x + s * .32, y + s * .06, x + s * .68, y + s * .62], radius=s * .18,
                        fill=c["silver"], outline=c["line"], width=w)
    for k in range(3):
        yy = y + s * (.2 + k * .1)
        d.line([(x + s * .38, yy), (x + s * .62, yy)], fill=c["dim"], width=max(1, w - 1))


def _speaker(d, x, y, s, c, w):
    d.polygon([(x + s * .1, y + s * .36), (x + s * .3, y + s * .36), (x + s * .52, y + s * .16),
               (x + s * .52, y + s * .84), (x + s * .3, y + s * .64), (x + s * .1, y + s * .64)],
              fill=c["silver"], outline=c["line"], width=w)
    for r in (.18, .3):
        d.arc([x + s * (.52 - r), y + s * (.5 - r), x + s * (.52 + r), y + s * (.5 + r)], -50, 50,
              fill=c["accent"], width=int(s * .07))


def _copy(d, x, y, s, c, w):
    for off, fill in ((0, c["body"]), (.16, c["paper"])):
        d.rounded_rectangle([x + s * (.14 + off), y + s * (.1 + off), x + s * (.66 + off), y + s * (.72 + off)],
                            radius=s * .06, fill=fill, outline=c["line"], width=w)
    for k in range(3):
        yy = y + s * (.42 + k * .1)
        d.line([(x + s * .4, yy), (x + s * .7, yy)], fill=c["accent"], width=max(1, w - 1))


def _wrench(d, x, y, s, c, w):
    d.line([(x + s * .3, y + s * .7), (x + s * .62, y + s * .38)], fill=c["line"], width=int(s * .2))
    d.line([(x + s * .3, y + s * .7), (x + s * .62, y + s * .38)], fill=c["silver"], width=int(s * .13))
    d.ellipse([x + s * .1, y + s * .6, x + s * .4, y + s * .9], fill=c["silver"], outline=c["line"], width=w)
    d.ellipse([x + s * .52, y + s * .1, x + s * .9, y + s * .48], fill=c["silver"], outline=c["line"], width=w)
    d.polygon([(x + s * .7, y + s * .06), (x + s * .94, y + s * .06), (x + s * .94, y + s * .3),
               (x + s * .74, y + s * .3)], fill=(0, 0, 0, 0))
    d.rectangle([x + s * .7, y + s * .04, x + s * .96, y + s * .3], fill=(0, 0, 0, 0))


def _alert(d, x, y, s, c, w):
    d.polygon([(x + s * .5, y + s * .08), (x + s * .94, y + s * .86), (x + s * .06, y + s * .86)],
              fill=c["warn"], outline="#a85a10", width=w)
    d.rounded_rectangle([x + s * .45, y + s * .32, x + s * .55, y + s * .62], radius=s * .04, fill=c["paper"])
    d.ellipse([x + s * .45, y + s * .68, x + s * .55, y + s * .78], fill=c["paper"])


def _retry(d, x, y, s, c, w):
    box = [x + s * .14, y + s * .14, x + s * .86, y + s * .86]
    d.arc(box, 40, 330, fill=c["line"], width=int(s * .16))
    d.arc(box, 40, 330, fill=c["good"], width=int(s * .1))
    cx, cy, r = x + s * .5, y + s * .5, s * .36
    a = math.radians(40)
    tip = (cx + r * math.cos(a), cy + r * math.sin(a))
    d.polygon([(tip[0] + s * .16, tip[1] - s * .02), (tip[0] - s * .1, tip[1] - s * .08),
               (tip[0] + s * .02, tip[1] + s * .16)], fill=c["good"], outline=c["line"])


def _upload(d, x, y, s, c, w):
    device_icons._cloud(d, x, y - s * .06, s, {**c, "body": "#d8efff"}, w)
    _arrowhead(d, x + s * .5, y + s * .82, x + s * .5, y + s * .42, c["accent"], int(s * .08), s * .14)


def _bulb(d, x, y, s, c, w):
    d.ellipse([x + s * .22, y + s * .06, x + s * .78, y + s * .62], fill=c["gold"], outline="#b8860b", width=w)
    d.rectangle([x + s * .36, y + s * .56, x + s * .64, y + s * .7], fill=c["gold"])
    d.rounded_rectangle([x + s * .34, y + s * .68, x + s * .66, y + s * .9], radius=s * .04,
                        fill=c["silver"], outline=c["line"], width=w)
    for k in (.75, .82):
        d.line([(x + s * .36, y + s * k), (x + s * .64, y + s * k)], fill=c["line"], width=max(1, w - 1))


def _network(d, x, y, s, c, w):
    pts = [(x + s * .5, y + s * .2), (x + s * .2, y + s * .76), (x + s * .8, y + s * .76)]
    for a, b in ((0, 1), (0, 2), (1, 2)):
        d.line([pts[a], pts[b]], fill=c["line"], width=w + 1)
    for (px, py), color in zip(pts, (c["accent"], c["good"], c["warn"])):
        d.ellipse([px - s * .14, py - s * .14, px + s * .14, py + s * .14], fill=color, outline=c["line"], width=w)


def _quiz(d, x, y, s, c, w):
    d.rounded_rectangle([x + s * .16, y + s * .12, x + s * .84, y + s * .94], radius=s * .06,
                        fill=c["paper"], outline=c["line"], width=w)
    d.rounded_rectangle([x + s * .36, y + s * .05, x + s * .64, y + s * .18], radius=s * .03, fill=c["silver"],
                        outline=c["line"], width=max(1, w - 1))
    for k in range(3):
        yy = y + s * (.34 + k * .19)
        d.line([(x + s * .26, yy), (x + s * .32, yy + s * .05), (x + s * .4, yy - s * .05)],
               fill=c["good"], width=w + 1)
        d.line([(x + s * .48, yy), (x + s * .74, yy)], fill=c["dim"], width=w)


def _film(d, x, y, s, c, w):
    d.rounded_rectangle([x + s * .1, y + s * .38, x + s * .9, y + s * .9], radius=s * .05,
                        fill="#2b3e52", outline=c["line"], width=w)
    d.polygon([(x + s * .1, y + s * .36), (x + s * .86, y + s * .14), (x + s * .9, y + s * .3),
               (x + s * .14, y + s * .52)], fill=c["paper"], outline=c["line"])
    for k in range(4):
        x0 = x + s * (.22 + k * .17)
        d.polygon([(x0, y + s * (.33 - k * .05)), (x0 + s * .08, y + s * (.31 - k * .05)),
                   (x0 + s * .14, y + s * (.47 - k * .05)), (x0 + s * .06, y + s * (.49 - k * .05))], fill="#2b3e52")
    d.polygon([(x + s * .42, y + s * .52), (x + s * .64, y + s * .64), (x + s * .42, y + s * .76)], fill=c["accent"])


ICONS = {
    "settings": _gear, "materials": _book, "tools": _calculator, "search": _search, "sidebar": _sidebar,
    "menu": _menu, "moon": _moon, "sun": _sun, "close": _close, "check": _check, "stop": _stop, "mic": _mic,
    "speaker": _speaker, "copy": _copy, "wrench": _wrench, "book": _book, "alert": _alert, "retry": _retry,
    "upload": _upload, "explain": _bulb, "calc": _calculator, "diagram": _network, "play": _play,
    "key": lambda d, x, y, s, c, w: _key(d, x, y, s, c, w), "lock": lambda d, x, y, s, c, w: _lock(d, x, y, s, c, w),
    "quiz": _quiz, "video": _film,
}


def render(name, look="aero", size=96):
    big = size * SCALE
    img = Image.new("RGBA", (big, big), (0, 0, 0, 0))
    ICONS[name](ImageDraw.Draw(img), 0, 0, big, PALETTES[look], max(2, big // 26))
    return FINISH[look](img).resize((size, size), Image.Resampling.LANCZOS)


def export(folder=OUT, size=96):
    made = []
    for look in PALETTES:
        (folder / look).mkdir(parents=True, exist_ok=True)
        for name in ICONS:
            render(name, look, size).save(folder / look / f"{name}.png", optimize=True)
            made.append(f"{look}/{name}.png")
    return made


if __name__ == "__main__":
    print(export())
