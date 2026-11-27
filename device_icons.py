"""Device and security icons for the pictures and animations: PCs, servers,
routers, switches, clouds, phones, people, keys, locks and more, drawn with
Pillow (no image files), in a light and a dark colour set, in the glossy
"Frutiger Aero" style: bright sky-blue and green colours, a light gradient, a
glass highlight on the upper half and a soft shadow (see _aero).

    icon_kind("Router 1") -> "router"      (picks the icon from a name)
    paste_icon(d, "router", cx, cy, 90, "dark")
    icon_file("switch")  -> a PNG for Graphviz and matplotlib

Icons are drawn three times bigger and scaled down, so their edges are smooth.
"""
import math
import re
from functools import lru_cache
from pathlib import Path

from PIL import Image, ImageChops, ImageDraw, ImageFilter

SCALE = 3

# Frutiger Aero colours: sky blue, leaf green, warm orange, soft silver
COLORS = {
    "dark": dict(line="#d6ecff", body="#34506b", screen="#3fb2f5", accent="#3fb2f5", second="#a48bf5",
                 warn="#ffa040", bad="#ff6b5e", good="#6fd96a", paper="#ffffff", dim="#6f8ca8"),
    "light": dict(line="#1d4f7a", body="#e6f1fa", screen="#2a9fe6", accent="#2a9fe6", second="#7b5ce0",
                  warn="#f08a24", bad="#e0443a", good="#43b649", paper="#ffffff", dim="#8aa6bf"),
}


# ---------- choosing an icon from a name ----------

# (icon, words): the first rule with a matching word wins, so specific rules come first
RULES = [
    ("attacker", r"attacker|trudy|eve|hacker|intruder|adversary|opponent|mallory|man in the middle|mitm"),
    ("person", r"alice|bob|user|person|student|customer|people|human|you|me"),
    ("ca", r"ca|kdc|certificate authority|certification authority|key distribution center|pki"),
    ("server", r"proxy|proxy server|cache|web cache|caching server"),
    ("web_server", r"web server|http server|web|website|origin server"),
    ("dns_server", r"dns|dns server|resolver|root server|tld server|authoritative|name server|local dns"),
    ("mail_server", r"mail|mail server|smtp|imap|pop3|email server|mail server"),
    ("database", r"database|db|sql|storage"),
    ("datacenter", r"data center|datacenter|data centre|cluster"),
    ("firewall", r"firewall|fw|ids|ips"),
    ("router", r"router|routers|gateway|gw|nat|edge router|r\d+|bgp|ospf|rip|as\d*"),
    ("switch", r"switch|switches|s\d+|ethernet switch|vlan switch|bridge"),
    ("hub", r"hub|repeater"),
    ("access_point", r"access point|ap|wifi|wi-fi|wireless|wlan|hotspot"),
    ("cell_tower", r"tower|base station|cell|cellular|bs|enodeb|gnodeb|4g|5g|lte"),
    ("satellite", r"satellite|sat"),
    ("modem", r"modem|dsl|dslam|cable modem|cmts|ont|onu"),
    ("cloud", r"internet|cloud|isp|cdn|wan|tier|backbone|network core|core"),
    ("server", r"server|servers|proxy|cache|web cache|dhcp|host server|peer server|tracker|p2p server"),
    ("phone", r"phone|smartphone|mobile|iphone|android|cellphone"),
    ("tablet", r"tablet|ipad"),
    ("laptop", r"laptop|notebook|macbook"),
    ("printer", r"printer"),
    ("camera", r"camera|webcam|cctv|iot|sensor"),
    ("tv", r"tv|television|smart tv|display"),
    ("home", r"home|house|residential|home network"),
    ("building", r"building|enterprise|company|university|campus|institution|office|corporate"),
    ("key", r"key|secret key|public key|private key|session key"),
    ("lock", r"lock|encrypted|encryption|secure|ssl|tls|https"),
    ("document", r"document|file|plaintext|ciphertext|message|text|data|packet|segment|datagram|frame"),
    ("envelope", r"envelope|letter|e-mail|email"),
    ("shield", r"shield|security|integrity|authentication|signature"),
    ("globe", r"globe|world|www"),
    ("pc", r"pc|pcs|host|hosts|h\d+|client|clients|computer|desktop|workstation|source|destination|sender|"
           r"receiver|end system|end host|peer|a|b|c|d"),
]
_RULES = [(icon, re.compile(r"\b(?:" + words + r")\b", re.IGNORECASE)) for icon, words in RULES]


def icon_kind(name, default="pc"):
    """The icon for a device name such as 'Router 1', 'DNS server', 'Alice' or 'PC2'."""
    text = re.sub(r"[_\-]+", " ", str(name)).strip()
    text = re.sub(r"(?<=[a-zA-Z])(?=\d)", " ", text)        # R1 -> R 1, PC2 -> PC 2
    text = re.sub(r"\b([a-zA-Z]) (\d+)\b", r"\1\2", text)    # but keep R1, H3, S2 together
    for icon, pattern in _RULES:
        if pattern.search(text):
            return icon
    return default


# ---------- the icons (each draws inside the square x, y, x+s, y+s) ----------

def _pc(d, x, y, s, c, w):
    d.rounded_rectangle([x + s * .08, y + s * .08, x + s * .92, y + s * .66], radius=s * .05,
                        fill=c["body"], outline=c["line"], width=w)
    d.rectangle([x + s * .15, y + s * .15, x + s * .85, y + s * .58], fill=c["screen"])
    d.line([(x + s * .22, y + s * .24), (x + s * .5, y + s * .24)], fill=c["paper"], width=w)
    d.polygon([(x + s * .42, y + s * .66), (x + s * .58, y + s * .66), (x + s * .63, y + s * .8),
               (x + s * .37, y + s * .8)], fill=c["line"])
    d.rounded_rectangle([x + s * .24, y + s * .8, x + s * .76, y + s * .9], radius=s * .03, fill=c["line"])


def _laptop(d, x, y, s, c, w):
    d.rounded_rectangle([x + s * .17, y + s * .15, x + s * .83, y + s * .62], radius=s * .04,
                        fill=c["body"], outline=c["line"], width=w)
    d.rectangle([x + s * .23, y + s * .21, x + s * .77, y + s * .56], fill=c["screen"])
    d.polygon([(x + s * .1, y + s * .66), (x + s * .9, y + s * .66), (x + s * .97, y + s * .8),
               (x + s * .03, y + s * .8)], fill=c["line"])
    d.line([(x + s * .42, y + s * .73), (x + s * .58, y + s * .73)], fill=c["body"], width=w)


def _server(d, x, y, s, c, w):
    d.rounded_rectangle([x + s * .22, y + s * .05, x + s * .78, y + s * .95], radius=s * .05,
                        fill=c["body"], outline=c["line"], width=w)
    for k in range(3):
        top = y + s * (.13 + k * .27)
        d.rounded_rectangle([x + s * .29, top, x + s * .71, top + s * .2], radius=s * .03,
                            outline=c["line"], width=max(1, w - 1))
        d.ellipse([x + s * .34, top + s * .07, x + s * .4, top + s * .13], fill=c["good"])
        d.line([(x + s * .47, top + s * .1), (x + s * .65, top + s * .1)], fill=c["line"], width=max(1, w - 1))


def _database(d, x, y, s, c, w):
    l, r = x + s * .18, x + s * .82
    d.rectangle([l, y + s * .2, r, y + s * .8], fill=c["accent"])
    d.ellipse([l, y + s * .68, r, y + s * .92], fill=c["accent"], outline=c["line"], width=w)
    d.rectangle([l + w, y + s * .2, r - w, y + s * .8], fill=c["accent"])
    d.line([(l, y + s * .2), (l, y + s * .8)], fill=c["line"], width=w)
    d.line([(r, y + s * .2), (r, y + s * .8)], fill=c["line"], width=w)
    for k in (.4, .6):
        d.arc([l, y + s * (k - .12), r, y + s * (k + .12)], 0, 180, fill=c["line"], width=w)
    d.ellipse([l, y + s * .08, r, y + s * .32], fill=c["screen"], outline=c["line"], width=w)


def _arrowhead(d, x1, y1, x2, y2, color, w, head):
    d.line([(x1, y1), (x2, y2)], fill=color, width=w)
    ang = math.atan2(y2 - y1, x2 - x1)
    for side in (-1, 1):
        a = ang + math.pi + side * 0.55
        d.line([(x2, y2), (x2 + head * math.cos(a), y2 + head * math.sin(a))], fill=color, width=w)


def _router(d, x, y, s, c, w):
    l, r = x + s * .06, x + s * .94
    d.ellipse([l, y + s * .5, r, y + s * .86], fill=c["accent"], outline=c["line"], width=w)
    d.rectangle([l, y + s * .38, r, y + s * .68], fill=c["accent"])
    d.line([(l, y + s * .38), (l, y + s * .68)], fill=c["line"], width=w)
    d.line([(r, y + s * .38), (r, y + s * .68)], fill=c["line"], width=w)
    d.ellipse([l, y + s * .2, r, y + s * .56], fill=c["screen"], outline=c["line"], width=w)
    cx, cy, h = x + s * .5, y + s * .38, s * .07
    white = c["paper"]
    _arrowhead(d, cx - s * .3, cy - s * .1, cx - s * .08, cy - s * .02, white, w, h)    # two arrows in
    _arrowhead(d, cx + s * .3, cy + s * .1, cx + s * .08, cy + s * .02, white, w, h)
    _arrowhead(d, cx - s * .05, cy + s * .05, cx - s * .27, cy + s * .12, white, w, h)  # two arrows out
    _arrowhead(d, cx + s * .05, cy - s * .05, cx + s * .27, cy - s * .12, white, w, h)


def _switch(d, x, y, s, c, w):
    d.rounded_rectangle([x + s * .04, y + s * .3, x + s * .96, y + s * .72], radius=s * .06,
                        fill=c["accent"], outline=c["line"], width=w)
    white, h = c["paper"], s * .06
    _arrowhead(d, x + s * .14, y + s * .42, x + s * .44, y + s * .42, white, w, h)
    _arrowhead(d, x + s * .56, y + s * .42, x + s * .86, y + s * .42, white, w, h)
    _arrowhead(d, x + s * .44, y + s * .6, x + s * .14, y + s * .6, white, w, h)
    _arrowhead(d, x + s * .86, y + s * .6, x + s * .56, y + s * .6, white, w, h)
    for k in range(6):
        px = x + s * (.14 + k * .13)
        d.rectangle([px, y + s * .74, px + s * .08, y + s * .8], fill=c["line"])


def _hub(d, x, y, s, c, w):
    d.rounded_rectangle([x + s * .06, y + s * .34, x + s * .94, y + s * .68], radius=s * .05,
                        fill=c["body"], outline=c["line"], width=w)
    for k in range(5):
        px = x + s * (.15 + k * .15)
        d.rectangle([px, y + s * .45, px + s * .1, y + s * .57], fill=c["line"])
        d.ellipse([px + s * .03, y + s * .38, px + s * .06, y + s * .41], fill=c["good"])


def _firewall(d, x, y, s, c, w):
    l, t, r, b = x + s * .08, y + s * .15, x + s * .92, y + s * .85
    d.rectangle([l, t, r, b], fill=c["warn"], outline=c["line"], width=w)
    rows = 5
    for k in range(1, rows):
        yy = t + (b - t) * k / rows
        d.line([(l, yy), (r, yy)], fill=c["paper"], width=w)
    for k in range(rows):
        y0, y1 = t + (b - t) * k / rows, t + (b - t) * (k + 1) / rows
        off = 0 if k % 2 == 0 else (r - l) / 6
        for j in range(4):
            xx = l + off + j * (r - l) / 3
            if l < xx < r:
                d.line([(xx, y0), (xx, y1)], fill=c["paper"], width=w)


def _cloud(d, x, y, s, c, w):
    parts = [(.08, .42, .42, .76), (.25, .25, .6, .62), (.48, .22, .82, .58), (.6, .4, .94, .76), (.25, .45, .75, .8)]
    for (a, b, e, f) in parts:
        d.ellipse([x + s * a, y + s * b, x + s * e, y + s * f], fill=c["line"])
    inset = w * 1.2
    for (a, b, e, f) in parts:
        d.ellipse([x + s * a + inset, y + s * b + inset, x + s * e - inset, y + s * f - inset], fill=c["body"])
    d.ellipse([x + s * .28, y + s * .36, x + s * .72, y + s * .72], fill=c["body"])     # fill the middle


def _access_point(d, x, y, s, c, w):
    d.rounded_rectangle([x + s * .15, y + s * .6, x + s * .85, y + s * .82], radius=s * .05,
                        fill=c["body"], outline=c["line"], width=w)
    d.ellipse([x + s * .25, y + s * .68, x + s * .31, y + s * .74], fill=c["good"])
    d.line([(x + s * .3, y + s * .6), (x + s * .22, y + s * .3)], fill=c["line"], width=w)
    d.line([(x + s * .7, y + s * .6), (x + s * .78, y + s * .3)], fill=c["line"], width=w)
    cx, cy = x + s * .5, y + s * .5
    for k, r in enumerate((.12, .22, .32)):
        d.arc([cx - s * r, cy - s * r, cx + s * r, cy + s * r], 225, 315, fill=c["accent"], width=w + 1)


def _phone(d, x, y, s, c, w):
    d.rounded_rectangle([x + s * .3, y + s * .06, x + s * .7, y + s * .94], radius=s * .07,
                        fill=c["body"], outline=c["line"], width=w)
    d.rectangle([x + s * .35, y + s * .15, x + s * .65, y + s * .8], fill=c["screen"])
    d.ellipse([x + s * .47, y + s * .84, x + s * .53, y + s * .9], fill=c["line"])


def _tablet(d, x, y, s, c, w):
    d.rounded_rectangle([x + s * .14, y + s * .1, x + s * .86, y + s * .9], radius=s * .07,
                        fill=c["body"], outline=c["line"], width=w)
    d.rectangle([x + s * .2, y + s * .17, x + s * .8, y + s * .8], fill=c["screen"])
    d.ellipse([x + s * .47, y + s * .82, x + s * .53, y + s * .88], fill=c["line"])


def _printer(d, x, y, s, c, w):
    d.rectangle([x + s * .28, y + s * .1, x + s * .72, y + s * .38], fill=c["paper"], outline=c["line"], width=w)
    d.rounded_rectangle([x + s * .08, y + s * .36, x + s * .92, y + s * .72], radius=s * .05,
                        fill=c["body"], outline=c["line"], width=w)
    d.ellipse([x + s * .78, y + s * .44, x + s * .84, y + s * .5], fill=c["good"])
    d.rectangle([x + s * .26, y + s * .62, x + s * .74, y + s * .9], fill=c["paper"], outline=c["line"], width=w)
    for k in (.72, .79):
        d.line([(x + s * .33, y + s * k), (x + s * .67, y + s * k)], fill=c["dim"], width=max(1, w - 1))


def _modem(d, x, y, s, c, w):
    d.rounded_rectangle([x + s * .1, y + s * .45, x + s * .9, y + s * .75], radius=s * .06,
                        fill=c["body"], outline=c["line"], width=w)
    for k in range(4):
        px = x + s * (.22 + k * .1)
        d.ellipse([px, y + s * .57, px + s * .05, y + s * .62], fill=c["good"] if k < 3 else c["warn"])
    d.line([(x + s * .75, y + s * .45), (x + s * .82, y + s * .18)], fill=c["line"], width=w)
    d.ellipse([x + s * .79, y + s * .13, x + s * .86, y + s * .2], fill=c["line"])


def _cell_tower(d, x, y, s, c, w):
    top, cx = y + s * .25, x + s * .5
    d.line([(cx, top), (x + s * .3, y + s * .92)], fill=c["line"], width=w)
    d.line([(cx, top), (x + s * .7, y + s * .92)], fill=c["line"], width=w)
    for k in (.45, .65, .85):
        half = (k - .25) / .67 * .2
        d.line([(cx - s * half, y + s * k), (cx + s * half, y + s * k)], fill=c["line"], width=max(1, w - 1))
    d.ellipse([cx - s * .05, top - s * .05, cx + s * .05, top + s * .05], fill=c["accent"])
    for r in (.14, .24):
        d.arc([cx - s * r, top - s * r, cx + s * r, top + s * r], 130, 230, fill=c["accent"], width=w)
        d.arc([cx - s * r, top - s * r, cx + s * r, top + s * r], -50, 50, fill=c["accent"], width=w)


def _satellite(d, x, y, s, c, w):
    cx, cy = x + s * .5, y + s * .5
    d.rectangle([x + s * .04, cy - s * .12, x + s * .32, cy + s * .12], fill=c["screen"], outline=c["line"], width=w)
    d.rectangle([x + s * .68, cy - s * .12, x + s * .96, cy + s * .12], fill=c["screen"], outline=c["line"], width=w)
    for xx in (.13, .23, .77, .87):
        d.line([(x + s * xx, cy - s * .12), (x + s * xx, cy + s * .12)], fill=c["line"], width=max(1, w - 1))
    d.line([(x + s * .32, cy), (x + s * .68, cy)], fill=c["line"], width=w)
    d.rounded_rectangle([cx - s * .12, cy - s * .16, cx + s * .12, cy + s * .16], radius=s * .03,
                        fill=c["body"], outline=c["line"], width=w)
    d.pieslice([cx - s * .14, cy + s * .1, cx + s * .14, cy + s * .38], 0, 180, fill=c["line"])


def _person(d, x, y, s, c, w, color=None):
    color = color or c["accent"]
    d.ellipse([x + s * .33, y + s * .1, x + s * .67, y + s * .44], fill=color, outline=c["line"], width=w)
    d.chord([x + s * .15, y + s * .5, x + s * .85, y + s * 1.15], 180, 360, fill=color, outline=c["line"], width=w)


def _attacker(d, x, y, s, c, w):
    _person(d, x, y, s, c, w, c["bad"])
    dark = "#111827"                                                                          # same in both themes
    d.pieslice([x + s * .28, y + s * .05, x + s * .72, y + s * .5], 180, 360, fill=dark)       # hood
    d.rectangle([x + s * .35, y + s * .24, x + s * .65, y + s * .32], fill=dark)               # mask
    d.ellipse([x + s * .4, y + s * .26, x + s * .46, y + s * .3], fill=c["paper"])
    d.ellipse([x + s * .54, y + s * .26, x + s * .6, y + s * .3], fill=c["paper"])


def _key(d, x, y, s, c, w):
    d.ellipse([x + s * .08, y + s * .3, x + s * .44, y + s * .66], fill=c["warn"], outline=c["line"], width=w)
    d.ellipse([x + s * .2, y + s * .42, x + s * .32, y + s * .54], fill=c["body"])
    d.rectangle([x + s * .42, y + s * .44, x + s * .92, y + s * .53], fill=c["warn"], outline=c["line"], width=w)
    for k in (.7, .82):
        d.rectangle([x + s * k, y + s * .53, x + s * (k + .07), y + s * .66], fill=c["warn"], outline=c["line"], width=w)


def _lock(d, x, y, s, c, w):
    d.arc([x + s * .28, y + s * .1, x + s * .72, y + s * .6], 180, 360, fill=c["line"], width=w + 2)
    d.line([(x + s * .28, y + s * .35), (x + s * .28, y + s * .45)], fill=c["line"], width=w + 2)
    d.line([(x + s * .72, y + s * .35), (x + s * .72, y + s * .45)], fill=c["line"], width=w + 2)
    d.rounded_rectangle([x + s * .18, y + s * .42, x + s * .82, y + s * .92], radius=s * .06,
                        fill=c["warn"], outline=c["line"], width=w)
    d.ellipse([x + s * .45, y + s * .56, x + s * .55, y + s * .66], fill=c["line"])
    d.rectangle([x + s * .48, y + s * .63, x + s * .52, y + s * .78], fill=c["line"])


def _document(d, x, y, s, c, w):
    d.polygon([(x + s * .2, y + s * .06), (x + s * .64, y + s * .06), (x + s * .8, y + s * .22),
               (x + s * .8, y + s * .94), (x + s * .2, y + s * .94)], fill=c["paper"], outline=c["line"])
    d.line([(x + s * .64, y + s * .06), (x + s * .64, y + s * .22), (x + s * .8, y + s * .22)], fill=c["line"], width=w)
    for k in range(5):
        yy = y + s * (.34 + k * .11)
        d.line([(x + s * .3, yy), (x + s * (.7 if k % 2 else .62), yy)], fill=c["dim"], width=w)


def _envelope(d, x, y, s, c, w):
    l, t, r, b = x + s * .08, y + s * .25, x + s * .92, y + s * .78
    d.rectangle([l, t, r, b], fill=c["paper"], outline=c["line"], width=w)
    d.line([(l, t), ((l + r) / 2, (t + b) / 2 + s * .05), (r, t)], fill=c["line"], width=w)


def _shield(d, x, y, s, c, w):
    pts = [(x + s * .5, y + s * .06), (x + s * .86, y + s * .2), (x + s * .8, y + s * .6),
           (x + s * .5, y + s * .94), (x + s * .2, y + s * .6), (x + s * .14, y + s * .2)]
    d.polygon(pts, fill=c["good"], outline=c["line"])
    d.line([(x + s * .34, y + s * .48), (x + s * .46, y + s * .6), (x + s * .68, y + s * .36)],
           fill=c["paper"], width=w + 2)


def _globe(d, x, y, s, c, w):
    box = [x + s * .1, y + s * .1, x + s * .9, y + s * .9]
    d.ellipse(box, fill=c["screen"], outline=c["line"], width=w)
    d.ellipse([x + s * .32, y + s * .1, x + s * .68, y + s * .9], outline=c["paper"], width=w)
    d.line([(x + s * .5, y + s * .1), (x + s * .5, y + s * .9)], fill=c["paper"], width=w)
    d.line([(x + s * .1, y + s * .5), (x + s * .9, y + s * .5)], fill=c["paper"], width=w)
    for k in (.3, .7):
        d.line([(x + s * .18, y + s * k), (x + s * .82, y + s * k)], fill=c["paper"], width=max(1, w - 1))


def _camera(d, x, y, s, c, w):
    d.rounded_rectangle([x + s * .1, y + s * .3, x + s * .9, y + s * .78], radius=s * .07,
                        fill=c["body"], outline=c["line"], width=w)
    d.rectangle([x + s * .3, y + s * .22, x + s * .5, y + s * .3], fill=c["line"])
    d.ellipse([x + s * .34, y + s * .36, x + s * .66, y + s * .68], fill=c["screen"], outline=c["line"], width=w)
    d.ellipse([x + s * .44, y + s * .46, x + s * .56, y + s * .58], fill=c["line"])


def _tv(d, x, y, s, c, w):
    d.rounded_rectangle([x + s * .06, y + s * .14, x + s * .94, y + s * .7], radius=s * .04,
                        fill=c["body"], outline=c["line"], width=w)
    d.rectangle([x + s * .12, y + s * .2, x + s * .88, y + s * .64], fill=c["screen"])
    d.line([(x + s * .35, y + s * .7), (x + s * .28, y + s * .86)], fill=c["line"], width=w)
    d.line([(x + s * .65, y + s * .7), (x + s * .72, y + s * .86)], fill=c["line"], width=w)


def _datacenter(d, x, y, s, c, w):
    for k in range(3):
        l = x + s * (.06 + k * .31)
        d.rounded_rectangle([l, y + s * .12, l + s * .26, y + s * .9], radius=s * .03,
                            fill=c["body"], outline=c["line"], width=w)
        for j in range(4):
            yy = y + s * (.2 + j * .17)
            d.line([(l + s * .05, yy), (l + s * .21, yy)], fill=c["line"], width=max(1, w - 1))
            d.ellipse([l + s * .05, yy + s * .04, l + s * .09, yy + s * .08], fill=c["good"])


def _home(d, x, y, s, c, w):
    d.polygon([(x + s * .5, y + s * .08), (x + s * .94, y + s * .48), (x + s * .06, y + s * .48)],
              fill=c["warn"], outline=c["line"])
    d.rectangle([x + s * .16, y + s * .46, x + s * .84, y + s * .92], fill=c["body"], outline=c["line"], width=w)
    d.rectangle([x + s * .42, y + s * .62, x + s * .58, y + s * .92], fill=c["accent"])
    d.rectangle([x + s * .24, y + s * .56, x + s * .36, y + s * .68], fill=c["screen"])
    d.rectangle([x + s * .64, y + s * .56, x + s * .76, y + s * .68], fill=c["screen"])


def _building(d, x, y, s, c, w):
    d.rectangle([x + s * .2, y + s * .06, x + s * .8, y + s * .94], fill=c["body"], outline=c["line"], width=w)
    for row in range(5):
        for col in range(3):
            l, t = x + s * (.28 + col * .17), y + s * (.13 + row * .14)
            d.rectangle([l, t, l + s * .1, t + s * .08], fill=c["screen"])
    d.rectangle([x + s * .43, y + s * .8, x + s * .57, y + s * .94], fill=c["line"])


def _badge(inner):
    """An icon with a small icon in its lower right corner, e.g. a server with a globe."""
    def draw(d, x, y, s, c, w):
        _server(d, x - s * .08, y, s, c, w)
        bx, by, bs = x + s * .52, y + s * .5, s * .46
        d.ellipse([bx, by, bx + bs, by + bs], fill=c["body"], outline=c["line"], width=w)
        inner(d, bx + bs * .1, by + bs * .1, bs * .8, c, max(1, w - 1))
    return draw


def _gear(d, x, y, s, c, w):
    cx, cy = x + s * .5, y + s * .5
    pts = []
    for k in range(16):
        r = s * (.42 if k % 2 == 0 else .32)
        a = k * math.pi / 8
        pts.append((cx + r * math.cos(a), cy + r * math.sin(a)))
    d.polygon(pts, fill=c["dim"], outline=c["line"])
    d.ellipse([cx - s * .14, cy - s * .14, cx + s * .14, cy + s * .14], fill=c["body"], outline=c["line"], width=w)


ICONS = {
    "pc": _pc, "laptop": _laptop, "server": _server, "database": _database, "datacenter": _datacenter,
    "router": _router, "switch": _switch, "hub": _hub, "firewall": _firewall, "cloud": _cloud,
    "access_point": _access_point, "cell_tower": _cell_tower, "satellite": _satellite, "modem": _modem,
    "phone": _phone, "tablet": _tablet, "printer": _printer, "camera": _camera, "tv": _tv,
    "person": _person, "attacker": _attacker, "key": _key, "lock": _lock, "shield": _shield,
    "document": _document, "envelope": _envelope, "globe": _globe, "home": _home, "building": _building,
    "gear": _gear,
    "web_server": _badge(_globe),
    # a DNS server: the same globe badge, in the second colour, so it differs from a web server
    "dns_server": _badge(lambda d, x, y, s, c, w: _globe(d, x, y, s, {**c, "screen": c["second"]}, w)),
    "mail_server": _badge(_envelope), "ca": _badge(_key),
}


# ---------- drawing them ----------

def _aero(img, theme):
    """The Frutiger Aero finish on a flat icon: lighter at the top and a little
    darker at the bottom, a glass highlight over the upper half (only on the icon
    itself), and a soft shadow underneath."""
    big = img.width
    alpha = img.getchannel("A")
    box = alpha.getbbox()
    if box is None:
        return img
    rgb = img.convert("RGB")
    white, black = Image.new("RGB", img.size, "white"), Image.new("RGB", img.size, "black")
    # 1. the light gradient, from the top of the icon to its bottom
    x0, y0, x1, y1 = box
    ramp = Image.new("L", img.size, 0)
    rd = ImageDraw.Draw(ramp)
    for y in range(y0, y1):
        rd.line([(0, y), (big, y)], fill=int(255 * (y - y0) / max(1, y1 - y0)))
    rgb = Image.composite(white, rgb, ramp.point(lambda v: int((255 - v) * 0.16)))
    rgb = Image.composite(black, rgb, ramp.point(lambda v: int(v * 0.18)))
    # 2. the glass highlight: a soft white oval over the upper half, fading downwards
    h, w = y1 - y0, x1 - x0
    gloss = Image.new("L", img.size, 0)
    gd = ImageDraw.Draw(gloss)
    top, bottom = y0 - h * 0.45, y0 + h * 0.46
    for k in range(24):                                  # brighter at the top of the oval
        t = k / 24
        gd.ellipse([x0 - w * 0.08 + t * w * 0.04, top + t * (bottom - top) * 0.5,
                    x1 + w * 0.08 - t * w * 0.04, bottom], fill=int(105 * t ** 0.6))
    gloss = gloss.filter(ImageFilter.GaussianBlur(big * 0.004))   # a crisp glass edge
    gloss = ImageChops.multiply(gloss, alpha)
    gloss = ImageChops.multiply(gloss, ramp.point(lambda v: 255 if v < 128 else max(0, 255 - (v - 128) * 4)))
    rgb = Image.composite(white, rgb, gloss)
    shiny = rgb.convert("RGBA")
    shiny.putalpha(alpha)
    # 3. a soft shadow, a little below the icon
    shadow_alpha = alpha.filter(ImageFilter.GaussianBlur(big * 0.025)).point(
        lambda v: int(v * (0.55 if theme == "dark" else 0.32)))
    shadow = Image.new("RGBA", img.size, "#000000" if theme == "dark" else "#0b2a4a")
    shadow.putalpha(shadow_alpha)
    out = Image.new("RGBA", img.size, (0, 0, 0, 0))
    out.alpha_composite(shadow, (0, int(big * 0.03)))
    out.alpha_composite(shiny)
    return out


@lru_cache(maxsize=512)
def icon_image(kind, size, theme="dark"):
    """A smooth RGBA picture of the icon, size x size pixels, in the Aero style."""
    draw = ICONS.get(kind, _pc)
    big = int(size) * SCALE
    img = Image.new("RGBA", (big, big), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    theme = "dark" if theme == "dark" else "light"
    draw(d, 0, 0, big, COLORS[theme], max(2, big // 26))
    return _aero(img, theme).resize((int(size), int(size)), Image.Resampling.LANCZOS)


def paste_icon(d, kind, cx, cy, size, theme="dark"):
    """Draw the icon centred at (cx, cy) on the picture that d draws on."""
    tile = icon_image(kind, int(size), theme)
    d._image.paste(tile, (int(cx - size / 2), int(cy - size / 2)), tile)


def device(d, name, cx, cy, size, theme="dark", label_color=None, label_size=22, kind=None):
    """An icon picked from the name, with the name under it. Returns the label's y."""
    from animation_tools import font
    paste_icon(d, kind or icon_kind(name), cx, cy, size, theme)
    y = cy + size / 2 + label_size * 0.7
    color = label_color or COLORS["dark" if theme == "dark" else "light"]["line"]
    d.text((cx, y), str(name), font=font(label_size, True), fill=color, anchor="mm")
    return y


def icon_file(kind, theme="light", size=96):
    """The icon as a PNG file (for Graphviz and matplotlib). Kept in diagrams/_icons."""
    folder = Path("diagrams") / "_icons"
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / f"{kind}_{theme}_{size}.png"
    if not path.exists():
        icon_image(kind, size, theme).save(path)
    return path.resolve()


# Quick look: run `python device_icons.py` -> diagrams/_icons/all_icons.png
if __name__ == "__main__":
    from animation_tools import font
    for theme, bg in (("light", "#ffffff"), ("dark", "#0f172a")):
        cols = 8
        rows = math.ceil(len(ICONS) / cols)
        sheet = Image.new("RGB", (cols * 150, rows * 150), bg)
        d = ImageDraw.Draw(sheet)
        for i, kind in enumerate(ICONS):
            cx, cy = (i % cols) * 150 + 75, (i // cols) * 150 + 60
            paste_icon(d, kind, cx, cy, 90, theme)
            d.text((cx, cy + 62), kind, font=font(15), fill=COLORS[theme]["line"], anchor="mm")
        Path("diagrams/_icons").mkdir(parents=True, exist_ok=True)
        sheet.save(f"diagrams/_icons/all_icons_{theme}.png")
    for name in ["PC1", "Router 1", "R2", "Switch", "DNS server", "Alice", "Trudy", "Internet", "Client", "Server",
                 "Web server", "AP", "Laptop", "Phone", "Host H3", "Firewall", "local DNS", "u", "Source", "KDC"]:
        print(f"{name:12} -> {icon_kind(name)}")
