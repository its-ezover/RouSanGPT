"""Classical ciphers and block cipher sizes (Stallings ch. 3-4, Forouzan ch. 3 and 5).

Letters are numbered a=0 ... z=25. Following the textbook, plaintext is shown in
lowercase and ciphertext in UPPERCASE.
"""
import math
import re

from number_theory_tools import MAX_STEPS, _int, _safe, inverse_mod

ALPHABET = "abcdefghijklmnopqrstuvwxyz"

# Relative frequency of letters in English text, in percent (Stallings Figure 3.5)
ENGLISH = {
    "a": 8.167, "b": 1.492, "c": 2.782, "d": 4.253, "e": 12.702, "f": 2.228, "g": 2.015,
    "h": 6.094, "i": 6.966, "j": 0.153, "k": 0.772, "l": 4.025, "m": 2.406, "n": 6.749,
    "o": 7.507, "p": 1.929, "q": 0.095, "r": 5.987, "s": 6.327, "t": 9.056, "u": 2.758,
    "v": 0.978, "w": 2.360, "x": 0.150, "y": 1.974, "z": 0.074,
}


def _letters(text):
    return re.sub(r"[^a-z]", "", str(text).lower())


def _mode(mode):
    m = str(mode).strip().lower()
    if m.startswith("enc"):
        return "encrypt"
    if m.startswith("dec"):
        return "decrypt"
    raise ValueError("mode must be 'encrypt' or 'decrypt'")


def _out(text, mode):
    return text.upper() if mode == "encrypt" else text.lower()


def _shift_letter(ch, k):
    return ALPHABET[(ALPHABET.index(ch) + k) % 26]


def _english_score(text):
    """Chi-squared distance from English letter frequencies (smaller = more English)."""
    letters = _letters(text)
    if not letters:
        return float("inf")
    n = len(letters)
    return sum((letters.count(c) - n * f / 100) ** 2 / (n * f / 100) for c, f in ENGLISH.items())


# ---------- substitution ciphers ----------

@_safe
def caesar_cipher(text: str, shift: int = 3, mode: str = "encrypt") -> dict:
    """Caesar (shift) cipher: C = (p + k) mod 26, p = (C - k) mod 26, with a=0..z=25.
    shift: the key k (Caesar's own was 3). mode: 'encrypt', 'decrypt' or
    'brute_force' (try all 25 keys on a ciphertext and rank them by how much they
    look like English). Spaces and punctuation are kept.
    Example: 'meet me after the toga party', k=3 -> 'PHHW PH DIWHU WKH WRJD SDUWB'."""
    k = _int(shift, "shift") % 26
    if str(mode).strip().lower().startswith("brute"):
        tries = []
        for key in range(1, 26):
            plain = "".join(_shift_letter(c, -key) if c in ALPHABET else c for c in str(text).lower())
            tries.append({"key": key, "plaintext": plain, "english_score": round(_english_score(plain), 1)})
        best = sorted(tries, key=lambda t: t["english_score"])
        return {"all_25_keys": tries, "most_likely": best[:3],
                "note": "a lower english_score means the letters look more like English"}
    m = _mode(mode)
    sign = 1 if m == "encrypt" else -1
    src = str(text).lower()
    out = "".join(_shift_letter(c, sign * k) if c in ALPHABET else c for c in src)
    first = next((c for c in src if c in ALPHABET), None)
    result = {"result": _out(out, m), "key": k,
              "formula": f"C = (p + {k}) mod 26" if m == "encrypt" else f"p = (C - {k}) mod 26"}
    if first:
        n = ALPHABET.index(first)
        result["first_letter"] = (f"{first} = {n} -> ({n} {'+' if sign > 0 else '-'} {k}) mod 26 = "
                                  f"{(n + sign * k) % 26} = {_shift_letter(first, sign * k)}")
    return result


@_safe
def affine_cipher(text: str, a: int, b: int, mode: str = "encrypt") -> dict:
    """Affine cipher: C = (a*p + b) mod 26 and p = a^-1 * (C - b) mod 26.
    a must be relatively prime to 26 (1, 3, 5, 7, 9, 11, 15, 17, 19, 21, 23, 25).
    Spaces and punctuation are kept."""
    a, b = _int(a, "a") % 26, _int(b, "b") % 26
    m = _mode(mode)
    if math.gcd(a, 26) != 1:
        raise ValueError(f"a = {a} is not relatively prime to 26, so it cannot be decrypted "
                         "(two letters would map to the same letter)")
    a_inv = inverse_mod(a, 26)
    out = []
    for c in str(text).lower():
        if c in ALPHABET:
            p = ALPHABET.index(c)
            out.append(ALPHABET[(a * p + b) % 26] if m == "encrypt" else ALPHABET[a_inv * (p - b) % 26])
        else:
            out.append(c)
    return {"result": _out("".join(out), m), "a_inverse_mod_26": a_inv,
            "formula": f"C = ({a}p + {b}) mod 26" if m == "encrypt" else f"p = {a_inv}(C - {b}) mod 26"}


def _keyword_alphabet(key):
    k = _letters(key)
    if len(k) == 26 and len(set(k)) == 26:
        return k
    seen = []
    for c in k + ALPHABET:
        if c not in seen:
            seen.append(c)
    return "".join(seen)


@_safe
def monoalphabetic_cipher(text: str, key: str, mode: str = "encrypt") -> dict:
    """Monoalphabetic substitution: each plain letter is replaced by one fixed cipher
    letter. key: either the full 26-letter cipher alphabet (cipher letters for a..z)
    or a keyword, which is written first (without repeats) followed by the rest of the
    alphabet. Spaces and punctuation are kept. Returns the substitution table."""
    m = _mode(mode)
    cipher_alpha = _keyword_alphabet(key)
    table = dict(zip(ALPHABET, cipher_alpha)) if m == "encrypt" else dict(zip(cipher_alpha, ALPHABET))
    out = "".join(table.get(c, c) for c in str(text).lower())
    return {"result": _out(out, m),
            "plain_alphabet": ALPHABET, "cipher_alphabet": cipher_alpha.upper()}


@_safe
def letter_frequency(text: str) -> dict:
    """Frequency analysis for breaking substitution ciphers: counts and percentages of
    each letter (most common first), the most common digrams and trigrams, and the
    English letter frequencies to compare with (e, t, a, o, i, n are the most common;
    th and the the most common digram and trigram)."""
    letters = _letters(text)
    if not letters:
        raise ValueError("the text has no letters")
    n = len(letters)
    counts = sorted(((c, letters.count(c)) for c in set(letters)), key=lambda x: (-x[1], x[0]))

    def top(size):
        grams = {}
        for i in range(n - size + 1):
            g = letters[i:i + size]
            grams[g] = grams.get(g, 0) + 1
        return [{"text": g.upper(), "count": c} for g, c in
                sorted(grams.items(), key=lambda x: (-x[1], x[0]))[:10] if c > 1]

    return {"total_letters": n,
            "letters": [{"letter": c.upper(), "count": k, "percent": round(100 * k / n, 2)}
                        for c, k in counts],
            "top_digrams": top(2), "top_trigrams": top(3),
            "english_order": "e t a o i n s h r d l c u m w f g y p b v k j x q z",
            "english_percent": ENGLISH}


@_safe
def vigenere_cipher(text: str, key: str, mode: str = "encrypt", autokey: bool = False) -> dict:
    """Vigenere cipher: C_i = (p_i + k_(i mod m)) mod 26, p_i = (C_i - k_i) mod 26,
    with the keyword repeated over the message (non-letters are removed, as in the
    textbook). autokey=True uses the autokey system: the keyword followed by the
    plaintext itself. Example: key 'deceptive', 'we are discovered save yourself' ->
    'ZICVTWQNGRZGVTWAVZHCQYGLMGJ'."""
    m = _mode(mode)
    src, k = _letters(text), _letters(key)
    if not k:
        raise ValueError("the key must contain letters")
    out, used = [], []
    for i, c in enumerate(src):
        if autokey:
            if i < len(k):
                kc = k[i]
            else:
                kc = src[i - len(k)] if m == "encrypt" else out[i - len(k)]
        else:
            kc = k[i % len(k)]
        used.append(kc)
        sign = 1 if m == "encrypt" else -1
        out.append(_shift_letter(c, sign * ALPHABET.index(kc)))
    rows = [f"{p} ({ALPHABET.index(p)}) {'+' if m == 'encrypt' else '-'} {kc} ({ALPHABET.index(kc)}) = "
            f"{o.upper() if m == 'encrypt' else o} ({ALPHABET.index(o)})"
            for p, kc, o in list(zip(src, used, out))[:MAX_STEPS]]
    return {"key_stream": "".join(used), "input": src, "result": _out("".join(out), m), "letters": rows}


def _playfair_matrix(key):
    seen = []
    for c in _letters(key).replace("j", "i") + ALPHABET.replace("j", ""):
        if c not in seen:
            seen.append(c)
    return [seen[i:i + 5] for i in range(0, 25, 5)]


@_safe
def playfair_cipher(text: str, key: str, mode: str = "encrypt", filler: str = "x") -> dict:
    """Playfair cipher with a 5x5 key matrix (I and J share a cell). The keyword is
    written first (no repeats), then the other letters in order. Encryption splits the
    plaintext into pairs, putting the filler (x) between a repeated letter in a pair and
    at the end if needed. Rules: same row -> letter to the right; same column ->
    letter below; otherwise -> the letter in the same row but the other letter's
    column (decryption goes left / up). Example: key 'monarchy', 'move forward' ->
    'ON UF PH NZ RM BZ'."""
    m = _mode(mode)
    grid = _playfair_matrix(key)
    where = {c: (r, col) for r, row in enumerate(grid) for col, c in enumerate(row)}
    src = _letters(text).replace("j", "i")
    fill = (_letters(filler) or "x")[0]
    pairs = []
    if m == "encrypt":
        i = 0
        while i < len(src):
            a = src[i]
            b = src[i + 1] if i + 1 < len(src) else None
            if b is None or a == b:
                other = fill if a != fill else ("q" if fill != "q" else "z")
                pairs.append(a + other)
                i += 1
            else:
                pairs.append(a + b)
                i += 2
    else:
        if len(src) % 2:
            raise ValueError("Playfair ciphertext must have an even number of letters")
        pairs = [src[i:i + 2] for i in range(0, len(src), 2)]
        for p in pairs:
            if p[0] == p[1]:
                raise ValueError(f"'{p.upper()}' is not a valid Playfair pair (two equal letters)")
    step = 1 if m == "encrypt" else -1
    out, rows = [], []
    for p in pairs:
        (r1, c1), (r2, c2) = where[p[0]], where[p[1]]
        if r1 == r2:
            o = grid[r1][(c1 + step) % 5] + grid[r2][(c2 + step) % 5]
            rule = "same row: " + ("letter to the right" if step > 0 else "letter to the left")
        elif c1 == c2:
            o = grid[(r1 + step) % 5][c1] + grid[(r2 + step) % 5][c2]
            rule = "same column: " + ("letter below" if step > 0 else "letter above")
        else:
            o = grid[r1][c2] + grid[r2][c1]
            rule = "rectangle: same row, other letter's column"
        out.append(o)
        rows.append(f"{p.upper() if m == 'decrypt' else p} -> {o.upper() if m == 'encrypt' else o}  ({rule})")
    result = {"key_matrix": [" ".join(c.upper() if c != "i" else "I/J" for c in row) for row in grid],
              "pairs": " ".join(pairs), "steps": rows[:MAX_STEPS],
              "result": " ".join(_out(o, m) for o in out)}
    if m == "decrypt":
        result["note"] = f"remove the filler letters ({fill}) that do not belong to the message"
    return result


def _parse_matrix(key):
    k = str(key).strip()
    letters_only = re.fullmatch(r"[A-Za-z\s]+", k)
    if letters_only:
        vals = [ALPHABET.index(c) for c in _letters(k)]
    else:
        vals = [int(v) for v in re.findall(r"-?\d+", k)]
    n = math.isqrt(len(vals))
    if n < 2 or n * n != len(vals):
        raise ValueError("the key matrix must be square (4, 9 or 16 numbers, or a key word of "
                         "that many letters), e.g. '[[9, 4], [5, 7]]'")
    return [[v % 26 for v in vals[r * n:(r + 1) * n]] for r in range(n)]


def _det(mat):
    if len(mat) == 1:
        return mat[0][0]
    return sum((-1) ** c * mat[0][c] * _det([row[:c] + row[c + 1:] for row in mat[1:]])
               for c in range(len(mat)))


def _inverse_matrix(mat, mod=26):
    n = len(mat)
    d = _det(mat) % mod
    if math.gcd(d, mod) != 1:
        raise ValueError(f"det(K) mod {mod} = {d} and gcd({d}, {mod}) = {math.gcd(d, mod)}, so K has "
                         "no inverse mod 26 and this key cannot be used (it could not be decrypted)")
    d_inv = inverse_mod(d, mod)
    adj = [[(-1) ** (r + c) * _det([row[:r] + row[r + 1:] for k, row in enumerate(mat) if k != c])
            for c in range(n)] for r in range(n)]
    return [[d_inv * adj[r][c] % mod for c in range(n)] for r in range(n)], d, d_inv


@_safe
def hill_cipher(text: str, key_matrix: str, mode: str = "encrypt", column_vectors: bool = False,
                filler: str = "x") -> dict:
    """Hill cipher with an n x n key matrix K mod 26. key_matrix: numbers row by row,
    e.g. '[[9, 4], [5, 7]]' or '17 17 5 21 18 21 2 2 19', or a key word whose length
    is 4, 9 or 16. By default blocks are row vectors, C = P * K mod 26 and
    P = C * K^-1 mod 26 (Stallings 7th ed. and Forouzan); column_vectors=True uses
    C = K * P instead. Shows det(K), its inverse mod 26, K^-1 and every block.
    The plaintext is padded with the filler (x). K must have gcd(det K, 26) = 1."""
    m = _mode(mode)
    k = _parse_matrix(key_matrix)
    n = len(k)
    k_inv, det, det_inv = _inverse_matrix(k)
    use = k if m == "encrypt" else k_inv
    src = _letters(text)
    pad = 0
    if len(src) % n:
        pad = n - len(src) % n
        src += (_letters(filler) or "x")[0] * pad
    out, steps = [], []
    for i in range(0, len(src), n):
        vec = [ALPHABET.index(c) for c in src[i:i + n]]
        if column_vectors:
            res = [sum(use[r][j] * vec[j] for j in range(n)) % 26 for r in range(n)]
        else:
            res = [sum(vec[j] * use[j][c] for j in range(n)) % 26 for c in range(n)]
        block = "".join(ALPHABET[v] for v in res)
        out.append(block)
        steps.append(f"{src[i:i + n]} = {vec} -> {res} = {_out(block, m)}")
    return {"key_matrix": k, "determinant_mod_26": det, "determinant_inverse_mod_26": det_inv,
            "inverse_key_matrix": k_inv, "convention": "C = K * P (column vectors)" if column_vectors
            else "C = P * K (row vectors)", "padded_with": pad, "blocks": steps[:MAX_STEPS],
            "result": _out("".join(out), m)}


@_safe
def vernam_xor(data: str, key: str) -> dict:
    """Vernam cipher / one-time pad: c_i = p_i XOR k_i and p_i = c_i XOR k_i (the same
    operation both ways). data and key can each be bits ('10110'), hex ('0x3F') or
    text (sent as 8-bit ASCII). A key shorter than the data is repeated (then it is no
    longer a one-time pad). Returns the result in binary, hex and, if readable, text."""
    def to_bits(value):
        v = str(value).strip()
        if re.fullmatch(r"[01\s]+", v) and len(v.replace(" ", "")) > 1:
            return v.replace(" ", "")
        if v.lower().startswith("0x"):
            h = v[2:].replace(" ", "")
            return bin(int(h, 16))[2:].zfill(len(h) * 4)
        return "".join(format(b, "08b") for b in v.encode("utf-8"))

    d, k = to_bits(data), to_bits(key)
    if not d or not k:
        raise ValueError("give both data and key")
    repeated = len(k) < len(d)
    kk = (k * (len(d) // len(k) + 1))[:len(d)]
    out = "".join("1" if x != y else "0" for x, y in zip(d, kk))
    result = {"data_bits": d, "key_bits": kk, "result_bits": out,
              "result_hex": f"0x{int(out, 2):0{(len(out) + 3) // 4}X}"}
    if len(out) % 8 == 0:
        raw = bytes(int(out[i:i + 8], 2) for i in range(0, len(out), 8))
        if all(32 <= b < 127 for b in raw):
            result["result_text"] = raw.decode("ascii")
    if repeated:
        result["warning"] = "the key was shorter than the data and was repeated"
    return result


# ---------- transposition ciphers ----------

def _rail_pattern(length, rails):
    pattern, r, step = [], 0, 1
    for _ in range(length):
        pattern.append(r)
        if rails > 1:
            if r == 0:
                step = 1
            elif r == rails - 1:
                step = -1
            r += step
    return pattern


@_safe
def rail_fence_cipher(text: str, rails: int = 2, mode: str = "encrypt") -> dict:
    """Rail fence transposition: write the letters in a zigzag over the given number of
    rails (rows) and read row by row. Decryption fills the zigzag spots row by row and
    reads along the zigzag. Non-letters are removed. Example: depth 2,
    'meet me after the toga party' -> 'MEMATRHTGPRYETEFETEOAAT'."""
    m = _mode(mode)
    rails = _int(rails, "rails")
    src = _letters(text)
    if rails < 2:
        raise ValueError("use 2 or more rails")
    pattern = _rail_pattern(len(src), rails)
    if m == "encrypt":
        grid = [["."] * len(src) for _ in range(rails)]
        for i, (c, r) in enumerate(zip(src, pattern)):
            grid[r][i] = c
        out = "".join(src[i] for r in range(rails) for i in range(len(src)) if pattern[i] == r)
    else:
        order = [i for r in range(rails) for i in range(len(src)) if pattern[i] == r]
        plain = [""] * len(src)
        for c, i in zip(src, order):
            plain[i] = c
        out = "".join(plain)
        grid = [["."] * len(src) for _ in range(rails)]
        for i, (c, r) in enumerate(zip(out, pattern)):
            grid[r][i] = c
    return {"rails": [" ".join(row) for row in grid][:MAX_STEPS], "result": _out(out, m)}


def _column_order(key):
    """'4312567' or '4 3 1 2 5 6 7' -> reading ranks; a word -> alphabetical ranks."""
    k = str(key).strip()
    if re.fullmatch(r"[\d\s,]+", k):
        nums = [int(x) for x in re.findall(r"\d+", k)] if re.search(r"[\s,]", k) else [int(c) for c in k]
        if sorted(nums) != list(range(1, len(nums) + 1)) and sorted(nums) != list(range(len(nums))):
            raise ValueError("a number key must use each column number once, e.g. '4312567'")
        base = min(nums)
        return [x - base + 1 for x in nums]
    letters = _letters(k)
    if not letters:
        raise ValueError("the key must be numbers like '4312567' or a word")
    ranked = sorted(range(len(letters)), key=lambda i: (letters[i], i))
    ranks = [0] * len(letters)
    for rank, i in enumerate(ranked, start=1):
        ranks[i] = rank
    return ranks


@_safe
def row_transposition_cipher(text: str, key: str, mode: str = "encrypt", rounds: int = 1,
                             padding: str = "x") -> dict:
    """Row (columnar) transposition: write the message in rows under the key, then
    read the columns in the order the key gives (column marked 1 first). key: numbers
    like '4312567' or a word (columns ranked alphabetically). padding: letters used in
    turn to fill the last row (the textbook example uses 'xyz'). rounds=2 does a double
    transposition. Example: key 4312567, 'attack postponed until two am', padding 'xyz'
    -> 'TTNAAPTMTSUOAODWCOIXKNLYPETZ'."""
    m = _mode(mode)
    order = _column_order(key)
    cols = len(order)
    text_now = _letters(text)
    pad_letters = _letters(padding) or "x"
    grids = []
    for _ in range(max(1, _int(rounds, "rounds"))):
        if m == "encrypt":
            if len(text_now) % cols:
                extra = cols - len(text_now) % cols
                text_now += (pad_letters * extra)[:extra]
            rows = [text_now[i:i + cols] for i in range(0, len(text_now), cols)]
            grids.append([" ".join(map(str, order))] + [" ".join(r) for r in rows])
            text_now = "".join("".join(r[c] for r in rows)
                               for c in sorted(range(cols), key=lambda c: order[c]))
        else:
            if len(text_now) % cols:
                raise ValueError(f"the ciphertext length ({len(text_now)}) must be a multiple of "
                                 f"the key length ({cols})")
            nrows = len(text_now) // cols
            columns, pos = {}, 0
            for c in sorted(range(cols), key=lambda c: order[c]):
                columns[c] = text_now[pos:pos + nrows]
                pos += nrows
            rows = ["".join(columns[c][r] for c in range(cols)) for r in range(nrows)]
            grids.append([" ".join(map(str, order))] + [" ".join(r) for r in rows])
            text_now = "".join(rows)
    return {"column_order": order, "grids": grids, "result": _out(text_now, m)}


# ---------- block ciphers and brute force ----------

def _size_text(log2_value):
    if log2_value < 60:
        return f"{round(2 ** log2_value):,}"
    exp10 = log2_value * math.log10(2)
    return f"about 2^{log2_value:.1f} = {10 ** (exp10 % 1):.2f} x 10^{int(exp10)}"


@_safe
def block_cipher_sizes(block_bits: int) -> dict:
    """Sizes for an ideal n-bit block cipher (Feistel's 'ideal block cipher'): the
    number of possible plaintext blocks 2^n, the number of possible reversible
    mappings (2^n)!, and the key length needed to store one mapping as a table,
    n * 2^n bits. Example: n = 4 gives 16 blocks, 16! mappings, a 64-bit key;
    n = 64 needs 2^70 bits."""
    n = _int(block_bits, "block_bits")
    if not 1 <= n <= 256:
        raise ValueError("block_bits must be between 1 and 256")
    blocks_log2 = n
    mappings_log2 = math.lgamma(2 ** n + 1) / math.log(2) if n < 64 else (2 ** n) * (n - 1.4427)
    key_log2 = n + math.log2(n)
    return {"possible_blocks": _size_text(blocks_log2),
            "possible_mappings_(2^n)!": f"(2^{n})! = " + (f"{math.factorial(2 ** n):,}" if n <= 4
                                                         else _size_text(mappings_log2)),
            "ideal_key_length_bits": f"n * 2^n = {n} * 2^{n} = " + (f"{n * 2 ** n:,}" if n <= 40
                                                                    else f"2^{key_log2:.1f}"),
            "note": "real block ciphers use a k-bit key, so only 2^k of these mappings can be chosen"}


@_safe
def brute_force_time(key_space: str, tries_per_second: float = 1e9) -> dict:
    """How long an exhaustive key search takes. key_space: the number of keys, written
    like '2^56', '2**128', '26!' (monoalphabetic cipher) or '25' (Caesar).
    tries_per_second: decryptions per second (the textbook uses 10^9 and 10^13).
    Returns the worst case (all keys) and the average (half the keys) in seconds and
    years."""
    s = str(key_space).strip().replace(" ", "").replace("^", "**")
    m = re.fullmatch(r"(\d+)!", s)
    if m:
        if int(m.group(1)) > 5000:
            raise ValueError("that factorial is too large")
        keys = math.factorial(int(m.group(1)))
    else:
        m = re.fullmatch(r"(\d+)\*\*(\d+)", s) or re.fullmatch(r"(\d+)", s)
        if not m:
            raise ValueError("write the key space like 2^56, 26! or 1000000")
        keys = int(m.group(1)) ** int(m.group(2)) if m.lastindex == 2 else int(m.group(1))
    rate = float(tries_per_second)
    if rate <= 0:
        raise ValueError("tries_per_second must be positive")
    year = 365.25 * 24 * 3600

    def show(n_keys):
        sec = n_keys / rate
        return {"seconds": f"{sec:.3e}", "years": f"{sec / year:.3e}"}

    return {"number_of_keys": f"{keys:.3e}" if keys > 10 ** 15 else keys,
            "key_bits": round(math.log2(keys), 2) if keys > 1 else 0,
            "worst_case_all_keys": show(keys), "average_half_the_keys": show(keys / 2),
            "rate": f"{rate:.0e} keys per second"}


CIPHER_TOOLS = [caesar_cipher, affine_cipher, monoalphabetic_cipher, letter_frequency,
                vigenere_cipher, playfair_cipher, hill_cipher, vernam_xor, rail_fence_cipher,
                row_transposition_cipher, block_cipher_sizes, brute_force_time]


if __name__ == "__main__":
    print(caesar_cipher("meet me after the toga party", 3)["result"])
    print(vigenere_cipher("we are discovered save yourself", "deceptive")["result"])
    print(playfair_cipher("move forward", "monarchy")["result"])
    print(hill_cipher("paymoremoney", "17 17 5 21 18 21 2 2 19")["result"])
    print(rail_fence_cipher("meet me after the toga party", 2)["result"])
    print(row_transposition_cipher("attack postponed until two am", "4312567", padding="xyz")["result"])
