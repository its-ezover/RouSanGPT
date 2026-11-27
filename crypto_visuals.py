"""Pictures and animations for the cryptography course.

Every number and letter shown comes from the crypto tools themselves (number theory,
finite fields, ciphers), never from the AI, so a picture cannot show a wrong step.

The same drawing code makes the still pictures (white, for the chat and the video
slides) and the animations (dark, like the other animations): draw(d, theme, cur)
shows every step when cur is None, or the steps 0..cur with step cur highlighted.
"""
import re

import animation_tools as at
import cipher_tools as ct
import finite_field_tools as ff
import number_theory_tools as nt
import visual_kit as vk
from visual_kit import W

AES_MODULUS = "x^8 + x^4 + x^3 + x + 1"
_canvas, _box, _center, _fit_line, _visible = vk.canvas, vk.box, vk.center, vk.fit_line, vk.visible
_short = vk.short_rows


def _ints(numbers, count, example):
    if len(numbers) < count:
        raise ValueError(f"give {count} numbers, for example {example}")
    return [nt._int(v, "number") for v in numbers[:count]]


def _steps_model(kind, numbers):
    """The table of one calculation: title, note, columns, rows, result, marks."""
    k = re.sub(r"[\s-]+", "_", str(kind).strip().lower())
    k = {"gcd_euclid": "gcd", "euclid": "gcd", "inverse": "modular_inverse", "mod_inverse": "modular_inverse",
         "power": "modular_power", "square_and_multiply": "modular_power", "fast_power": "modular_power",
         "miller_rabin_test": "miller_rabin", "crt": "chinese_remainder",
         "gf_multiply": "gf2n_multiply", "gf_inverse": "gf2n_inverse"}.get(k, k)
    nums = [str(x).strip() for x in (numbers or []) if str(x).strip()]

    if k == "gcd":
        a, b = (abs(v) for v in _ints(nums, 2, '["710", "310"]'))
        a, b = max(a, b), min(a, b)
        rows = []
        while b:
            q, r = divmod(a, b)
            rows.append([str(a), str(b), str(q), str(r)])
            a, b = b, r
        return dict(title="Euclidean algorithm", note="gcd(a, b) = gcd(b, a mod b), until the remainder is 0",
                    columns=["a", "b", "q = a div b", "r = a mod b"], rows=rows,
                    result=f"gcd = {a}" + ("  (relatively prime)" if a == 1 else ""), marks={})

    if k == "extended_euclid":
        a, b = _ints(nums, 2, '["1759", "550"]')
        r = nt.extended_euclid(a, b)
        if "error" in r:
            raise ValueError(r["error"])
        rows = [[str(t["i"]), str(t["r"]), str(t["q"]), str(t["x"]), str(t["y"])] for t in r["table"]]
        return dict(title="Extended Euclidean algorithm",
                    note=f"Every row: r = {a}*x + {b}*y.   x_i = x_(i-2) - q_i * x_(i-1), the same for y",
                    columns=["i", "r", "q", "x", "y"], rows=rows,
                    result=f"gcd = {r['gcd']},  x = {r['x']},  y = {r['y']}", marks={len(rows) - 2: "good"})

    if k == "modular_inverse":
        a, n = _ints(nums, 2, '["11", "26"]')
        r = nt.modular_inverse(a, n)
        if "error" in r:
            raise ValueError(r["error"])
        rows = [[str(t[c]) for c in ("q", "r1", "r2", "r", "t1", "t2", "t")] for t in r["table"]]
        result = (f"{a}^-1 mod {n} = {r['inverse']}   (t1 = {r['t1_from_table']})" if r["has_inverse"]
                  else r["reason"])
        return dict(title=f"Inverse of {a} mod {n}",
                    note="Start r1 = n, r2 = a, t1 = 0, t2 = 1.   r = r1 - q*r2,  t = t1 - q*t2",
                    columns=["q", "r1", "r2", "r", "t1", "t2", "t"], rows=rows, result=result,
                    marks={len(rows) - 1: "good" if r["has_inverse"] else "bad"})

    if k == "modular_power":
        base, e, n = _ints(nums, 3, '["20", "62", "77"]')
        r = nt.modular_power(base, e, n)
        if "error" in r:
            raise ValueError(r["error"])
        note = ""
        a = base % n
        if e < 0:
            a, e = int(r["inverse_of_base"]), -e
            note = f"negative exponent: use the inverse {a} of the base.  "
        bits = bin(e)[2:]
        rows, value = [], 1
        for bit in bits:
            sq = value * value % n
            new = sq * a % n if bit == "1" else sq
            rows.append([bit, f"{value}^2 = {sq}", f"{sq} * {a} = {new}" if bit == "1" else "-", str(new)])
            value = new
        if str(value) != str(r["result"]):
            raise ValueError("internal check failed")
        return dict(title="Square-and-multiply", note=note + f"exponent {e} in binary = {bits}   (all mod {n})",
                    columns=["bit", "square", "multiply (bit 1)", "value"], rows=_short(rows),
                    result=f"{base}^{nums[1]} mod {n} = {r['result']}", marks={})

    if k == "miller_rabin":
        n, a = _ints(nums, 2, '["1729", "671"]')
        r = nt.miller_rabin_test(n, [a])
        if "error" in r:
            raise ValueError(r["error"])
        test = r["tests"][0]
        if "error" in test:
            raise ValueError(test["error"])
        rows, marks = [], {}
        for j, line in enumerate(test["sequence"]):
            expr, value = line.split(" = ")
            rows.append([str(j), expr.replace(f" mod {n}", ""), value])
            if (j == 0 and value == "1") or value == str(n - 1):
                marks[j] = "good"
        if test["result"] == "composite":
            marks[len(rows) - 1] = "bad"
        return dict(title=f"Miller-Rabin test, n = {n}", note=f"n - 1 = {n - 1} = 2^{r['k']} * {r['q']},   a = {a}",
                    columns=["j", "a^(q*2^j)", f"mod {n}"], rows=rows,
                    result=f"{test['result'].upper()}: {test['reason']}", marks=marks)

    if k == "chinese_remainder":
        if len(nums) < 2:
            raise ValueError('give the remainders and the moduli, for example ["2, 3, 2", "3, 5, 7"]')
        r = nt.chinese_remainder(nums[0], nums[1])
        if "error" in r:
            raise ValueError(r["error"])
        rows = [[str(t["a"]), str(t["m"]), str(t["M_i"]), str(t["M_i_inverse_mod_m"]), str(t["a*M_i*inverse"])]
                for t in r["rows"]]
        return dict(title="Chinese Remainder Theorem", note=f"M = {r['M']},   M_i = M / m_i",
                    columns=["a_i", "m_i", "M_i", "M_i^-1 mod m_i", "a_i * M_i * M_i^-1"], rows=rows,
                    result=r["formula"], marks={})

    if k == "gf2n_multiply":
        if len(nums) < 2:
            raise ValueError('give two polynomials, for example ["x^5 + x^2 + x", "x^7 + x^4 + x^3 + x^2 + x"]')
        modulus = nums[2] if len(nums) > 2 else AES_MODULUS
        r = ff.gf2n_arithmetic(nums[0], nums[1], "multiply", modulus)
        if "error" in r:
            raise ValueError(r["error"])
        x = int(r["a"]["bits"], 2)
        y = int(r["b"]["bits"], 2)
        m = ff.poly_to_int(ff.parse_poly(modulus, 2))
        width = m.bit_length() - 1
        mask = (1 << width) - 1
        rows, value, total = [], y, 0
        for i in range(max(x.bit_length(), 1)):
            note = "-"
            if i:
                overflow = value >> (width - 1) & 1
                value = (value << 1) & mask
                if overflow:
                    value ^= m & mask
                    note = f"XOR {format(m & mask, f'0{width}b')}"
            used = x >> i & 1
            if used:
                total ^= value
            rows.append([f"x^{i} * b", format(value, f"0{width}b"), note, "yes" if used else ""])
        if format(total, f"0{width}b") != r["result"]["bits"]:
            raise ValueError("internal check failed")
        return dict(title=f"Multiplying in {r['field']}",
                    note=f"a = {r['a']['polynomial']},  b = {r['b']['polynomial']},  m(x) = {r['modulus']}",
                    columns=["step", "value", "top bit was 1", "used (bit of a)"], rows=rows,
                    result=f"a * b = XOR of the used rows = {r['result']['bits']} = {r['result']['polynomial']}",
                    marks={i: "good" for i, row in enumerate(rows) if row[3]})

    if k == "gf2n_inverse":
        if not nums:
            raise ValueError('give the polynomial, for example ["x^5"] (and the modulus if not AES)')
        modulus = nums[1] if len(nums) > 1 else AES_MODULUS
        r = ff.gf2n_arithmetic(nums[0], "", "inverse", modulus)
        if "error" in r:
            raise ValueError(r["error"])
        rows = [[t[c] for c in ("q", "r1", "r2", "r", "t1", "t2", "t")] for t in r["table"]]
        return dict(title=f"Inverse in {r['field']}",
                    note=f"m(x) = {r['modulus']}.   Start r1 = m(x), r2 = a, t1 = 0, t2 = 1;  t = t1 - q*t2",
                    columns=["q", "r1", "r2", "r", "t1", "t2", "t"], rows=_short(rows),
                    result=f"inverse = {r['inverse']['polynomial']} = {r['inverse']['bits']} ({r['inverse']['hex']})",
                    marks={len(rows) - 1: "good"})

    raise ValueError("kind must be one of: gcd, extended_euclid, modular_inverse, modular_power, "
                     "miller_rabin, chinese_remainder, gf2n_multiply, gf2n_inverse")


def _steps_visual(kind, numbers):
    m = _steps_model(kind, numbers)
    return vk.table_visual(m["title"], m["columns"], m["rows"], m["result"], m["note"], m["marks"])


# ---------- 2. ciphers ----------

ALPHABET = ct.ALPHABET


def _cipher_name(cipher):
    c = re.sub(r"[\s-]+", "_", str(cipher).strip().lower())
    return {"shift": "caesar", "caesar_cipher": "caesar", "vigenere_cipher": "vigenere", "vigenère": "vigenere",
            "playfair_cipher": "playfair", "railfence": "rail_fence", "rail_fence_cipher": "rail_fence",
            "transposition": "row_transposition", "columnar": "row_transposition",
            "columnar_transposition": "row_transposition", "row_transposition_cipher": "row_transposition",
            "one_time_pad": "vernam", "otp": "vernam", "xor": "vernam", "vernam_xor": "vernam"}.get(c, c)


def _caesar(text, key):
    k = nt._int(key or 3, "shift") % 26
    letters = ct._letters(text)[:30]
    if not letters:
        raise ValueError("the text has no letters")
    out = ct.caesar_cipher(letters, k)["result"]

    def draw(d, th, cur):
        cw = 42
        x0 = (W - 26 * cw) / 2
        now = letters[cur] if cur is not None and 0 <= cur < len(letters) else None
        d.text((x0, 128), "plain", font=at.font(20), fill=th["muted"])
        d.text((x0, 285), f"cipher (shift {k})", font=at.font(20), fill=th["muted"])
        for i in range(26):
            x = x0 + i * cw
            hit = now is not None and ALPHABET.index(now) == i
            _box(d, x, 155, cw - 4, 44, th, th["mark"] if hit else None)
            _center(d, x + cw / 2 - 2, 177, ALPHABET[i], 24, th)
            d.line([(x + cw / 2 - 2, 201), (x + cw / 2 - 2, 229)], fill=th["accent"] if hit else th["line"], width=2)
            _box(d, x, 231, cw - 4, 44, th, th["mark"] if hit else None)
            _center(d, x + cw / 2 - 2, 253, ALPHABET[(i + k) % 26].upper(), 24, th, th["accent"], True)
        n = len(letters)
        mw = min(46, (W - 160) / n)
        mx = (W - n * mw) / 2
        for j, ch in enumerate(letters):
            x = mx + j * mw
            hit = cur == j
            _box(d, x, 340, mw - 4, 46, th, th["mark"] if hit else None)
            _center(d, x + mw / 2 - 2, 363, ch, min(24, int(mw * 0.62)), th)
            if _visible(cur, j):
                _box(d, x, 410, mw - 4, 46, th, th["mark"] if hit else None)
                _center(d, x + mw / 2 - 2, 433, out[j], min(24, int(mw * 0.62)), th, th["accent"], True)
        if now is not None:
            p = ALPHABET.index(now)
            line = f"{now} = {p}  ->  ({p} + {k}) mod 26 = {(p + k) % 26}  ->  {out[cur]}"
        else:
            line = f"C = (p + {k}) mod 26"
        _fit_line(d, W / 2, 520, line, th, 30, th["text"], False)
        shown = out if cur is None else out[:max(0, cur + 1)]
        _fit_line(d, W / 2, 600, "Ciphertext: " + shown, th, 32, th["accent"])
    return dict(title=f"Caesar cipher, shift {k}", steps=len(letters), per_step=0.9, draw=draw, result=out)


def _vigenere(text, key):
    if not ct._letters(key):
        raise ValueError("the Vigenere key must be a word")
    r = ct.vigenere_cipher(ct._letters(text)[:30], key)
    plain, keys, out = r["input"], r["key_stream"], r["result"]
    if not plain:
        raise ValueError("the text has no letters")
    n = len(plain)

    def draw(d, th, cur):
        gx = 300
        cw = min(52, (W - 80 - gx) / n)
        labels = [("plaintext", plain, th["text"]), ("key", keys, th["muted"]), ("ciphertext", out, th["accent"])]
        for row, (label, letters, color) in enumerate(labels):
            y = 160 + row * 90
            d.text((80, y + 18), label, font=at.font(24, True), fill=th["muted"])
            for j, ch in enumerate(letters):
                if row == 2 and not _visible(cur, j):
                    continue
                x = gx + j * cw
                _box(d, x, y, cw - 4, 66, th, th["mark"] if cur == j else None)
                _center(d, x + cw / 2 - 2, y + 24, ch.upper() if row == 2 else ch, min(26, int(cw * 0.7)), th, color,
                        row == 2)
                _center(d, x + cw / 2 - 2, y + 51, ALPHABET.index(ch.lower()), 15, th, th["muted"])
        if cur is not None and 0 <= cur < n:
            p, k, c = (ALPHABET.index(v.lower()) for v in (plain[cur], keys[cur], out[cur]))
            line = f"{plain[cur]} ({p}) + {keys[cur]} ({k}) = {p + k}  ->  mod 26 = {c}  ->  {out[cur]}"
        else:
            line = f"C_i = (p_i + k_i) mod 26     key '{ct._letters(key)}' repeats"
        _fit_line(d, W / 2, 470, line, th, 30, th["text"], False)
        shown = out if cur is None else out[:max(0, cur + 1)]
        _fit_line(d, W / 2, 570, "Ciphertext: " + shown, th, 32, th["accent"])
    return dict(title="Vigenere cipher, key " + ct._letters(key).upper(), steps=n, per_step=0.9, draw=draw, result=out)


def _playfair(text, key):
    if not ct._letters(key):
        raise ValueError("the Playfair key must be a word")
    r = ct.playfair_cipher(ct._letters(text)[:24], key)
    grid = [row.split(" ") for row in r["key_matrix"]]
    where = {}
    for i, row in enumerate(grid):
        for j, cell in enumerate(row):
            for ch in cell.lower().split("/"):
                where[ch] = (i, j)
    pairs = []
    for line in r["steps"][:10]:
        m = re.match(r"(\w\w) -> (\w\w)\s+\((.*)\)", line)
        if m:
            pairs.append((m.group(1).lower(), m.group(2).upper(), m.group(3)))

    def draw(d, th, cur):
        cs, gx, gy = 74, 90, 150
        now = pairs[cur] if cur is not None and 0 <= cur < len(pairs) else None
        ins = {where.get(c) for c in now[0]} if now else set()
        outs = {where.get(c.lower()) for c in now[1]} if now else set()
        for i, row in enumerate(grid):
            for j, cell in enumerate(row):
                fill = th["accent"] if (i, j) in ins else th["mark"] if (i, j) in outs else None
                _box(d, gx + j * cs, gy + i * cs, cs - 6, cs - 6, th, fill)
                color = th["on_accent"] if (i, j) in ins else th["text"]
                _center(d, gx + j * cs + cs / 2 - 3, gy + i * cs + cs / 2 - 3, cell, 26 if len(cell) == 1 else 18,
                        th, color, True)
        d.text((560, 140), "pair  ->  cipher     rule", font=at.font(22, True), fill=th["muted"])
        for k, (p, c, rule) in enumerate(pairs):
            if not _visible(cur, k):
                continue
            y = 180 + k * 40
            if cur == k:
                at.gloss_rect(d, [550, y - 4, W - 60, y + 34], 8, th["mark"], light=th is vk.LIGHT)
            d.text((566, y), f"{p}  ->  {c}", font=at.font(24, True), fill=th["text"])
            d.text((760, y + 2), rule, font=at.font(20), fill=th["muted"])
        done = [c for k, (_, c, _) in enumerate(pairs) if _visible(cur, k)]
        _fit_line(d, W / 2, 640, "Ciphertext: " + " ".join(done), th, 30, th["accent"])
    return dict(title="Playfair cipher, key " + ct._letters(key).upper(), steps=len(pairs), per_step=1.7,
                draw=draw, result=" ".join(p[1] for p in pairs))


def _rail_fence(text, key):
    rails = nt._int(key or 2, "rails")
    if not 2 <= rails <= 6:
        raise ValueError("use 2 to 6 rails")
    letters = ct._letters(text)[:26]
    if not letters:
        raise ValueError("the text has no letters")
    n = len(letters)
    pattern = ct._rail_pattern(n, rails)
    rows = ["".join(letters[i] for i in range(n) if pattern[i] == r) for r in range(rails)]

    def draw(d, th, cur):
        cw = min(44, (W - 160) / n)
        rh = min(66, 330 / rails)
        gx, gy = (W - n * cw) / 2, 150
        placed = n if cur is None else min(n, cur + 1)
        read = rails if cur is None else max(0, cur - n + 1)
        reading = cur - n if cur is not None and cur >= n else None
        for r in range(rails):
            if reading == r:
                at.gloss_rect(d, [gx - 8, gy + r * rh, gx + n * cw + 4, gy + (r + 1) * rh - 6], 8, th["mark"],
                              light=th is vk.LIGHT)
        points = [(gx + i * cw + cw / 2, gy + pattern[i] * rh + rh / 2 - 3) for i in range(placed)]
        if len(points) > 1:
            d.line(points, fill=th["line"], width=2)
        for i in range(placed):
            x, y = points[i]
            hit = cur == i
            d.ellipse([x - cw / 2 + 2, y - cw / 2 + 2, x + cw / 2 - 2, y + cw / 2 - 2],
                      fill=th["accent"] if hit else th["cell"], outline=th["accent"], width=2)
            _center(d, x, y, letters[i], min(24, int(cw * 0.6)), th, th["on_accent"] if hit else th["text"], True)
        out = "".join(rows[:read]).upper()
        _fit_line(d, W / 2, gy + rails * rh + 60, f"Read rail by rail: {out}", th, 30, th["accent"])
    return dict(title=f"Rail fence cipher, {rails} rails", steps=n + rails, per_step=0.6, draw=draw,
                result="".join(rows).upper())


def _row_transposition(text, key):
    r = ct.row_transposition_cipher(ct._letters(text)[:60], key, padding="xyz")
    if "error" in r:
        raise ValueError(r["error"])
    order = r["column_order"]
    cols = len(order)
    grid = [line.split(" ") for line in r["grids"][0][1:]][:8]
    reading = [c for _, c in sorted((rank, c) for c, rank in enumerate(order))]

    def draw(d, th, cur):
        cw = min(70, (W - 200) / cols)
        rh = min(56, 380 / (len(grid) + 1))
        gx, gy = (W - cols * cw) / 2, 140
        current_col = reading[cur] if cur is not None and 0 <= cur < cols else None
        done = reading if cur is None else reading[:max(0, cur + 1)]
        for c in range(cols):
            x = gx + c * cw
            hit = c == current_col
            _box(d, x, gy, cw - 6, rh - 6, th, th["accent"] if hit else th["head"])
            _center(d, x + cw / 2 - 3, gy + rh / 2 - 3, order[c], 24, th,
                    th["on_accent"] if hit else th["accent"], True)
            for i, row in enumerate(grid):
                y = gy + (i + 1) * rh
                _box(d, x, y, cw - 6, rh - 6, th, th["mark"] if hit else None)
                _center(d, x + cw / 2 - 3, y + rh / 2 - 3, row[c], 24, th,
                        th["muted"] if c in done and not hit else th["text"])
        out = "".join("".join(row[c] for row in grid) for c in done).upper()
        _fit_line(d, W / 2, gy + (len(grid) + 1) * rh + 50, "Read the columns 1, 2, 3, ...: " + out,
                  th, 28, th["accent"])
    return dict(title="Row transposition, key " + str(key), steps=cols, per_step=1.3, draw=draw,
                result=r["result"])


def _vernam(text, key):
    r = ct.vernam_xor(text, key)
    if "error" in r:
        raise ValueError(r["error"])
    data, keyb, out = r["data_bits"][:32], r["key_bits"][:32], r["result_bits"][:32]
    n = len(data)

    def draw(d, th, cur):
        gx = 230
        cw = min(32, (W - 80 - gx) / n)
        for row, (label, bits) in enumerate((("data", data), ("key", keyb), ("XOR", out))):
            y = 170 + row * 90
            d.text((80, y + 12), label, font=at.font(26, True), fill=th["muted"])
            for j, b in enumerate(bits):
                if row == 2 and not _visible(cur, j):
                    continue
                x = gx + j * cw
                _box(d, x, y, cw - 3, 52, th, th["mark"] if cur == j else None, radius=5)
                _center(d, x + cw / 2 - 1, y + 26, b, 22, th, th["accent"] if row == 2 else th["text"], row == 2)
        d.line([(gx, 345), (gx + n * cw, 345)], fill=th["line"], width=2)
        line = "c_i = p_i XOR k_i   (1 when the bits differ)"
        if cur is not None and 0 <= cur < n:
            line = f"bit {cur + 1}: {data[cur]} XOR {keyb[cur]} = {out[cur]}"
        _fit_line(d, W / 2, 480, line, th, 30, th["text"], False)
        if cur is None:
            extra = f"   ('{r['result_text']}')" if "result_text" in r else ""
            _fit_line(d, W / 2, 560, f"Result: {r['result_hex']}{extra}", th, 30, th["accent"])
    return dict(title="Vernam cipher (XOR)", steps=n, per_step=0.3, draw=draw, result=r["result_hex"])


CIPHERS = {"caesar": _caesar, "vigenere": _vigenere, "playfair": _playfair, "rail_fence": _rail_fence,
           "row_transposition": _row_transposition, "vernam": _vernam}


def _cipher_visual(cipher, text, key):
    make = CIPHERS.get(_cipher_name(cipher))
    if make is None:
        raise ValueError("cipher must be one of: " + ", ".join(CIPHERS))
    return make(text, key)


# ---------- the registry (the explainer tools list these kinds) ----------

def _steps(kind, default):
    return lambda inputs: _steps_visual(kind, inputs or default)


def _cipher(cipher, default):
    def make(inputs):
        text, key = (inputs + default[len(inputs):])[:2] if len(inputs) < 2 else inputs[:2]
        return _cipher_visual(cipher, text, key)
    return make


C = "crypto"
vk.register("gcd", C, "Euclidean algorithm table.", '[a, b], e.g. ["710", "310"]',
            _steps("gcd", ["710", "310"]), icon="gear")
vk.register("extended_euclid", C, "Extended Euclidean table (r, q, x, y) for ax + by = gcd.",
            '[a, b], e.g. ["1759", "550"]', _steps("extended_euclid", ["1759", "550"]), icon="gear")
vk.register("modular_inverse", C, "Inverse of a mod n, table q r1 r2 r t1 t2 t.",
            '[a, n], e.g. ["11", "26"]', _steps("modular_inverse", ["11", "26"]), icon="key")
vk.register("modular_power", C, "Square-and-multiply for a^e mod n.",
            '[base, exponent, modulus], e.g. ["20", "62", "77"]', _steps("modular_power", ["20", "62", "77"]), icon="lock")
vk.register("miller_rabin", C, "Miller-Rabin test: n-1 = 2^k q and the sequence a^(q 2^j) mod n.",
            '[n, a], e.g. ["1729", "671"]', _steps("miller_rabin", ["1729", "671"]), icon="shield")
vk.register("chinese_remainder", C, "Chinese Remainder Theorem table.",
            '[remainders, moduli], e.g. ["2, 3, 2", "3, 5, 7"]',
            _steps("chinese_remainder", ["2, 3, 2", "3, 5, 7"]), icon="gear")
vk.register("gf2n_multiply", C, "GF(2^n) multiplication by repeated multiply-by-x (shift and XOR).",
            '[a, b] or [a, b, modulus], e.g. ["x^5 + x^2 + x", "x^7 + x^4 + x^3 + x^2 + x"] (AES modulus default)',
            _steps("gf2n_multiply", ["x^5 + x^2 + x", "x^7 + x^4 + x^3 + x^2 + x"]), icon="lock")
vk.register("gf2n_inverse", C, "GF(2^n) inverse with the extended Euclidean table.",
            '[a] or [a, modulus], e.g. ["x^5"] or ["x^2 + 1", "x^4 + x + 1"]', _steps("gf2n_inverse", ["x^5"]), icon="key")
vk.register("caesar", C, "Caesar cipher: the two alphabets and each letter.",
            '[text, shift], e.g. ["meet me after the toga party", "3"]',
            _cipher("caesar", ["meet me after the toga party", "3"]), icon="key")
vk.register("vigenere", C, "Vigenere cipher: plaintext, repeated key and ciphertext with numbers.",
            '[text, keyword], e.g. ["we are discovered save yourself", "deceptive"]',
            _cipher("vigenere", ["we are discovered save yourself", "deceptive"]), icon="key")
vk.register("playfair", C, "Playfair 5x5 matrix and every pair with its rule.",
            '[text, keyword], e.g. ["move forward", "monarchy"]', _cipher("playfair", ["move forward", "monarchy"]), icon="key")
vk.register("rail_fence", C, "Rail fence zigzag, then read rail by rail.",
            '[text, rails], e.g. ["meet me after the toga party", "2"]',
            _cipher("rail_fence", ["meet me after the toga party", "2"]), icon="lock")
vk.register("row_transposition", C, "Row (columnar) transposition grid, columns read in key order.",
            '[text, key], e.g. ["attack postponed until two am", "4312567"]',
            _cipher("row_transposition", ["attack postponed until two am", "4312567"]), icon="lock")
vk.register("vernam", C, "Vernam / one-time pad: data XOR key, bit by bit.",
            '[data, key] as bits, hex (0x..) or text, e.g. ["HI", "0x1234"]', _cipher("vernam", ["HI", "0x1234"]), icon="lock")
