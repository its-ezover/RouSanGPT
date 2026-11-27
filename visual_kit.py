"""Shared drawing kit for the course "explainers": step tables, cipher pictures,
timing diagrams and charts, as still pictures or animations.

A visual is a dict:
    title     the heading
    steps     how many steps the animation shows
    per_step  seconds per step in the animation
    draw      draw(d, theme, cur): everything when cur is None (the still picture and
              the end of the animation), otherwise steps 0..cur with step cur highlighted
              (cur = -1: nothing yet)
    result    one line that says what the picture shows (given back to the AI)
    details   optional, extra data for the AI (for example the rows of a table)

Every explainer kind registers itself with register(); the numbers it shows come from
the course's calculators, never from the AI.
"""
import math
from pathlib import Path

from PIL import ImageDraw

import animation_tools as at
import device_icons
import diagram_tools

W, H = at.W, at.H

LIGHT = dict(bg="#ffffff", text="#0f172a", muted="#64748b", line="#cbd5e1", head="#e0f2fe",
             accent="#0284c7", mark="#fde68a", cell="#f8fafc", good="#15803d", bad="#b91c1c",
             on_accent="#ffffff", second="#7c3aed", warn="#c2410c")
DARK = dict(bg=at.BG, text="#e2e8f0", muted="#94a3b8", line="#334155", head="#1e293b",
            accent="#38bdf8", mark="#854d0e", cell="#111827", good="#4ade80", bad="#f87171",
            on_accent="#062030", second="#a78bfa", warn="#fb923c")
MAX_ROWS = 14


# ---------- drawing helpers ----------

def canvas(title, th):
    """A frame in the Frutiger Aero style: a sky behind it and a glossy title bar."""
    if th is DARK:
        return at.new_frame(title)
    img = at.aero_background(light=True).copy()
    d = ImageDraw.Draw(img)
    at.frame_title(d, title, light=True)
    return img, d


def box(d, x, y, w, h, th, fill=None, outline=None, width=2, radius=8):
    """A glossy box (a lighter upper half and a highlight, the Aero look)."""
    at.gloss_rect(d, [x, y, x + w, y + h], radius, fill or th["cell"], outline or th["line"], width,
                  light=th is LIGHT)


def center(d, x, y, text, size, th, color=None, bold=False):
    d.text((x, y), str(text), font=at.font(size, bold), fill=color or th["text"], anchor="mm")


def left(d, x, y, text, size, th, color=None, bold=False):
    d.text((x, y), str(text), font=at.font(size, bold), fill=color or th["text"], anchor="lm")


def fit_line(d, x, y, text, th, size=30, color=None, bold=True, max_w=W - 160):
    """One centred line, made smaller until it fits."""
    while size > 14 and d.textlength(text, font=at.font(size, bold)) > max_w:
        size -= 1
    center(d, x, y, text, size, th, color, bold)


def visible(cur, j):
    return cur is None or j <= cur


def arrow(d, x1, y1, x2, y2, color, width=3, head=14):
    d.line([(x1, y1), (x2, y2)], fill=color, width=width)
    ang = math.atan2(y2 - y1, x2 - x1)
    for side in (-1, 1):
        a = ang + math.pi + side * 0.45
        d.line([(x2, y2), (x2 + head * math.cos(a), y2 + head * math.sin(a))], fill=color, width=width)


def cross(d, x, y, color, size=12, width=4):
    d.line([(x - size, y - size), (x + size, y + size)], fill=color, width=width)
    d.line([(x - size, y + size), (x + size, y - size)], fill=color, width=width)


# ---------- tables ----------

def _fit_table(d, columns, rows, max_w, row_h):
    size = int(min(30, row_h * 0.52))
    widths = []
    while size >= 11:
        f, fb = at.font(size), at.font(size, True)
        pad = size * 0.8
        widths = [max([d.textlength(h, font=fb)] + [d.textlength(r[c], font=f) for r in rows]) + 2 * pad
                  for c, h in enumerate(columns)]
        if sum(widths) <= max_w:
            break
        size -= 1
    return size, widths


def draw_table(d, th, columns, rows, cur, marks, top, bottom, cell_marks=None, x_left=None, max_w=W - 140):
    """A table whose rows appear one by one. marks: {row: 'good'/'bad'/...} colours a
    whole row; cell_marks: {(row, col): colour key} colours one cell. The table is
    centred, unless x_left gives its left edge."""
    cell_marks = cell_marks or {}
    n = len(rows)
    row_h = min(54, (bottom - top) / (n + 1))
    size, widths = _fit_table(d, columns, rows, max_w, row_h)
    x0 = (W - sum(widths)) / 2 if x_left is None else x_left
    d.rounded_rectangle([x0, top, x0 + sum(widths), top + row_h * (n + 1)], radius=10,
                        fill=th["cell"], outline=th["line"], width=2)
    at.gloss_rect(d, [x0, top, x0 + sum(widths), top + row_h], 10, th["head"], light=th is LIGHT)
    x = x0
    for c, head in enumerate(columns):
        center(d, x + widths[c] / 2, top + row_h / 2, head, size, th, th["accent"], True)
        x += widths[c]
    for i, row in enumerate(rows):
        y = top + (i + 1) * row_h
        d.line([(x0, y), (x0 + sum(widths), y)], fill=th["line"], width=1)
        if not visible(cur, i):
            continue
        if cur == i:
            d.rectangle([x0 + 2, y + 1, x0 + sum(widths) - 2, y + row_h - 1], fill=th["mark"])
        x = x0
        for c, cell in enumerate(row):
            key = cell_marks.get((i, c), marks.get(i))
            color = th.get(key, th["text"]) if key else th["text"]
            center(d, x + widths[c] / 2, y + row_h / 2, cell, size, th, color, key is not None)
            x += widths[c]
    return top + row_h * (n + 1)


def short_rows(rows):
    """Very long tables: the first rows, a gap, and the last row."""
    if len(rows) <= MAX_ROWS:
        return rows
    return rows[:MAX_ROWS - 2] + [["..."] * len(rows[0])] + rows[-1:]


def table_visual(title, columns, rows, result, note="", marks=None, per_step=1.4, cell_marks=None):
    """The common case: a note, a table that fills row by row, and the result."""
    marks = marks or {}

    def draw(d, th, cur):
        top = 135
        if note:
            fit_line(d, W / 2, 140, note, th, 24, th["muted"], bold=False)
            top = 170
        bottom = draw_table(d, th, columns, rows, cur, marks if cur is None else {}, top, 620,
                            cell_marks if cur is None else {})
        if cur is None:
            fit_line(d, W / 2, min(bottom + 45, H - 40), result, th, 30, th["accent"])
    return dict(title=title, steps=len(rows), per_step=per_step, draw=draw, result=result,
                details={"columns": columns, "rows": rows[:MAX_ROWS]})


# ---------- charts ----------

def chart_axes(d, th, box_xy, x_max, y_max, x_label, y_label, x_ticks=None, y_ticks=None):
    """Axes inside box_xy = (x0, y0, x1, y1); returns a function (x, y) -> pixel."""
    x0, y0, x1, y1 = box_xy
    d.line([(x0, y1), (x1, y1)], fill=th["muted"], width=2)
    d.line([(x0, y0), (x0, y1)], fill=th["muted"], width=2)

    def px(x, y):
        return x0 + (x1 - x0) * x / x_max, y1 - (y1 - y0) * y / y_max

    for t in (x_ticks or []):
        x, _ = px(t, 0)
        d.line([(x, y1), (x, y1 + 6)], fill=th["muted"], width=2)
        center(d, x, y1 + 20, _num(t), 18, th, th["muted"])
    for t in (y_ticks or []):
        _, y = px(0, t)
        d.line([(x0 - 6, y), (x0, y)], fill=th["muted"], width=2)
        d.line([(x0, y), (x1, y)], fill=th["line"], width=1)
        d.text((x0 - 10, y), _num(t), font=at.font(18), fill=th["muted"], anchor="rm")
    center(d, (x0 + x1) / 2, y1 + 50, x_label, 20, th, th["muted"], True)
    d.text((x0, y0 - 18), y_label, font=at.font(20, True), fill=th["muted"], anchor="ls")
    return px


def _num(v):
    return str(int(v)) if float(v).is_integer() else f"{v:g}"


def nice_ticks(top, count=5):
    step = top / count
    mag = 10 ** math.floor(math.log10(step)) if step > 0 else 1
    step = min((m * mag for m in (1, 2, 2.5, 5, 10) if m * mag >= step), default=step)
    ticks, t = [], 0.0
    while t <= top + 1e-9:
        ticks.append(round(t, 10))
        t += step
    return ticks


# ---------- saving ----------

def _corner_icon(d, visual, theme):
    if visual.get("icon"):
        device_icons.paste_icon(d, visual["icon"], W - 105, 72, 76, theme)


def save_still(visual, name):
    img, d = canvas(visual["title"], LIGHT)
    _corner_icon(d, visual, "light")
    visual["draw"](d, LIGHT, None)
    Path("diagrams").mkdir(exist_ok=True)
    png = Path("diagrams") / f"{diagram_tools._clean_name(name)}.png"
    img.save(png)
    diagram_tools._open_image(png)
    result = {"saved_to": str(png), "result": visual["result"],
              "message": "Picture drawn and shown to the student. Explain it step by step."}
    result.update(visual.get("details", {}))
    return result


def save_animation(visual, name):
    start, steps, per = 0.8, visual["steps"], visual["per_step"]

    def frame(t):
        img, d = canvas(visual["title"], DARK)
        _corner_icon(d, visual, "dark")
        k = math.floor((t - start) / per)
        visual["draw"](d, DARK, None if k >= steps else max(k, -1))
        return img
    result = at._finish(name, frame, start + steps * per + 2.5)
    if "error" not in result:
        result["result"] = visual["result"]
    return result


# ---------- the registry of explainer kinds ----------

KINDS = {}   # name -> {"course", "about", "inputs", "make", "icon"}


def register(name, course, about, inputs, make, icon=None):
    """make(inputs: list[str]) -> visual. inputs explains what to give (and that an
    empty list uses the slides' example). icon: the device_icons icon shown in the
    corner of the picture."""
    KINDS[name] = {"course": course, "about": about, "inputs": inputs, "make": make, "icon": icon}


def build(kind, inputs):
    key = str(kind).strip().lower().replace(" ", "_").replace("-", "_")
    entry = KINDS.get(key)
    if entry is None:
        raise ValueError(f"unknown kind '{kind}'. Kinds: " + ", ".join(KINDS))
    clean = [str(x).strip() for x in (inputs or []) if str(x).strip()]
    visual = entry["make"](clean)
    visual.setdefault("icon", entry["icon"])
    return visual


def kinds_text(course=None):
    lines = []
    for name, e in KINDS.items():
        if course and e["course"] != course:
            continue
        lines.append(f"- '{name}': {e['about']} inputs: {e['inputs']}")
    return "\n".join(lines)
