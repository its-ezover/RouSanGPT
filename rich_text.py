"""Math in the pictures, written the way it is typed and drawn the way it is printed:

    2^k * q          ->  2 with a raised k, then  · q
    a^(q*2^j) mod n  ->  a with a raised q·2ʲ
    x_i, D_v(y)      ->  a lowered i, a lowered v
    a -> b, <=, >=   ->  →, ≤, ≥

Only letters that stand alone get a subscript (x_i, not file_name), and a '*' is a
multiplication only between two numbers or names (the *** of an address range
stays as it is). Text without any of this is drawn exactly as before.
"""
import re

from animation_tools import font

SUP = str.maketrans("0123456789+-=()abcdefghijklmnoprstuvwxyzABDEGHIJKLMNOPRTUVW",
                    "⁰¹²³⁴⁵⁶⁷⁸⁹⁺⁻⁼⁽⁾ᵃᵇᶜᵈᵉᶠᵍʰⁱʲᵏˡᵐⁿᵒᵖʳˢᵗᵘᵛʷˣʸᶻᴬᴮᴰᴱᴳᴴᴵᴶᴷᴸᴹᴺᴼᴾᴿᵀᵁⱽᵂ")
_SUP_OK = set("0123456789+-=()abcdefghijklmnoprstuvwxyzABDEGHIJKLMNOPRTUVW")


def prettify(text):
    """Multiplication dots and arrows (before the parts are found)."""
    t = re.sub(r"(?<=\w)\*\*(?=[\w(-])", "^", text)               # Python-style 2**53
    # a * with a space on both sides (2 * 3) or on neither (2*3) is a multiplication
    t = re.sub(r"(?<=[\w)])(?: \* |\*)(?=[\w(])", lambda m: " · " if " " in m.group(0) else "·", t)
    t = t.replace("->", "→").replace("<=", "≤").replace(">=", "≥").replace("!=", "≠")
    return t


def _group(text, i):
    """The exponent or subscript starting at text[i]: '(...)' or a run of letters/digits."""
    if i < len(text) and text[i] == "(":
        depth = 0
        for j in range(i, len(text)):
            depth += {"(": 1, ")": -1}.get(text[j], 0)
            if depth == 0:
                return text[i + 1:j], j + 1
        return None, i
    m = re.match(r"[-+]?[A-Za-z0-9]+", text[i:])
    return (m.group(0), i + m.end()) if m else (None, i)


def _inner(text):
    """An exponent that has its own exponent (q*2^j): the inner one as superscript letters."""
    return re.sub(r"\^([A-Za-z0-9+-]+)",
                  lambda m: m.group(1).translate(SUP) if set(m.group(1)) <= _SUP_OK else "^" + m.group(1), text)


def parts(text):
    """[(text, level)]: level 0 normal, 1 raised, -1 lowered."""
    text = prettify(text)
    out, buf, i = [], "", 0
    while i < len(text):
        ch = text[i]
        if ch == "^" and (buf or out):                 # also right after a subscript: M_i^-1
            body, end = _group(text, i + 1)
            if body:
                if buf:
                    out.append((buf, 0))
                out.append((_inner(body), 1))
                buf, i = "", end
                continue
        if (ch == "_" and buf and buf[-1].isalpha() and (len(buf) == 1 or not buf[-2].isalnum())):
            body, end = _group(text, i + 1)
            if body and len(body) <= 4 and (end >= len(text) or not text[end].isalnum() or text[i + 1] == "("):
                out.append((buf, 0))
                out.append((body, -1))
                buf, i = "", end
                continue
        buf += ch
        i += 1
    if buf:
        out.append((buf, 0))
    return out


def needs(text):
    t = str(text)
    return "^" in t or "_" in t or "*" in t or "->" in t or "<=" in t or ">=" in t


def _font(size, bold, level):
    return font(size if level == 0 else max(8, round(size * 0.64)), bold)


def width(d, text, size, bold=False):
    if not needs(text):
        return d.textlength(str(text), font=font(size, bold))
    return sum(d.textlength(t, font=_font(size, bold, lv)) for t, lv in parts(str(text)))


def draw(d, xy, text, size, color, bold=False, anchor="mm"):
    """Draw text at xy with anchor 'mm' (centre), 'lm' (left) or 'rm' (right)."""
    text = str(text)
    x, y = xy
    if not needs(text):
        d.text((x, y), text, font=font(size, bold), fill=color, anchor=anchor)
        return
    pieces = parts(text)
    total = sum(d.textlength(t, font=_font(size, bold, lv)) for t, lv in pieces)
    x0 = x - total / 2 if anchor[0] == "m" else x - total if anchor[0] == "r" else x
    ascent, descent = font(size, bold).getmetrics()
    baseline = y + (ascent - descent) / 2
    for t, lv in pieces:
        f = _font(size, bold, lv)
        shift = -size * 0.42 if lv == 1 else size * 0.2 if lv == -1 else 0
        d.text((x0, baseline + shift), t, font=f, fill=color, anchor="ls")
        x0 += d.textlength(t, font=f)


SUB = str.maketrans("0123456789+-=()aehijklmnoprstuvx", "₀₁₂₃₄₅₆₇₈₉₊₋₌₍₎ₐₑₕᵢⱼₖₗₘₙₒₚᵣₛₜᵤᵥₓ")
_SUB_OK = set("0123456789+-=()aehijklmnoprstuvx")


def unicode(text):
    """The same math in one line of plain characters, for titles drawn with effects:
    2^k * q -> 2ᵏ · q, x_i -> xᵢ. A power or index with a character that has no raised
    or lowered form (there is no raised q) keeps its ^ or _."""
    out = []
    for t, level in parts(str(text)):
        if level == 1:
            out.append(t.translate(SUP) if set(t) <= _SUP_OK | set("·ʲᵏ⁰¹²³⁴⁵⁶⁷⁸⁹") else "^" + (
                t if len(t) == 1 else f"({t})"))
        elif level == -1:
            out.append(t.translate(SUB) if set(t) <= _SUB_OK else "_" + (t if len(t) == 1 else f"({t})"))
        else:
            out.append(t)
    return "".join(out)
