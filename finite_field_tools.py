"""Polynomials and finite fields for cryptography (Stallings ch. 5, Forouzan ch. 4).

Polynomials can be written the way students write them: 'x^3 + x + 1',
'x8 + x4 + x3 + x + 1' (exponents written after x, as in copied slides),
'3x^2 - x + 2', as bits '100011011' (GF(2) only) or as hex '0x11B' (GF(2) only).
"""
import itertools
import re
from fractions import Fraction

from number_theory_tools import MAX_STEPS, _safe, inverse_mod, is_probable_prime

AES_MODULUS = 0x11B      # x^8 + x^4 + x^3 + x + 1


# ---------- reading and writing polynomials ----------
# A polynomial is a list of coefficients, lowest power first: x^2 + 2 -> [2, 0, 1].

_TERM = re.compile(r"([+-]?)\s*(\d*)\s*(\*?\s*x\s*(?:\^?\s*(\d+))?)?", re.IGNORECASE)


def parse_poly(text, p):
    """p = 0 means ordinary (integer or fraction) coefficients."""
    s = str(text).strip().replace("−", "-").replace("·", "*").replace("X", "x")
    s = s.replace("**", "^").replace(" ", "")
    if not s:
        raise ValueError("empty polynomial")
    if p == 2 and s.lower().startswith("0x"):
        return int_to_poly(int(s, 16))
    if p == 2 and re.fullmatch(r"[01]+", s) and len(s) > 1:
        return int_to_poly(int(s, 2))
    if "x" not in s:
        if re.fullmatch(r"[+-]?\d+", s):
            return _trim([_reduce(int(s), p)])
        raise ValueError(f"cannot read the polynomial '{text}'")
    coeffs = {}
    pos = 0
    while pos < len(s):
        m = _TERM.match(s, pos)
        if not m or m.end() == pos:
            raise ValueError(f"cannot read the polynomial '{text}' near '{s[pos:]}'")
        sign, num, xpart, exp = m.groups()
        if not num and not xpart:
            raise ValueError(f"cannot read the polynomial '{text}' near '{s[pos:]}'")
        c = int(num) if num else 1
        c = -c if sign == "-" else c
        power = (int(exp) if exp else 1) if xpart else 0
        coeffs[power] = coeffs.get(power, 0) + c
        pos = m.end()
    poly = [0] * (max(coeffs) + 1)
    for power, c in coeffs.items():
        poly[power] = _reduce(c, p)
    return _trim(poly)


def _reduce(c, p):
    return c % p if p else c


def _trim(poly):
    poly = list(poly)
    while len(poly) > 1 and poly[-1] == 0:
        poly.pop()
    return poly or [0]


def int_to_poly(value):
    return _trim([(value >> i) & 1 for i in range(max(value.bit_length(), 1))])


def poly_to_int(poly):
    return sum(1 << i for i, c in enumerate(poly) if c % 2)


def poly_str(poly):
    terms = []
    for power in range(len(poly) - 1, -1, -1):
        c = poly[power]
        if c == 0:
            continue
        sign = "-" if c < 0 else "+"
        c = abs(c)
        if power == 0:
            body = str(c)
        else:
            body = ("" if c == 1 else str(c)) + ("x" if power == 1 else f"x^{power}")
        terms.append((sign, body))
    if not terms:
        return "0"
    text = ("-" if terms[0][0] == "-" else "") + terms[0][1]
    for sign, body in terms[1:]:
        text += f" {sign} {body}"
    return text


def degree(poly):
    return -1 if poly == [0] else len(poly) - 1


# ---------- arithmetic over Zp (p = 0: ordinary arithmetic) ----------

def p_add(a, b, p):
    n = max(len(a), len(b))
    return _trim([_reduce((a[i] if i < len(a) else 0) + (b[i] if i < len(b) else 0), p)
                  for i in range(n)])


def p_neg(a, p):
    return [_reduce(-c, p) for c in a]


def p_mul(a, b, p):
    out = [0] * (len(a) + len(b) - 1)
    for i, x in enumerate(a):
        for j, y in enumerate(b):
            out[i + j] += x * y
    return _trim([_reduce(c, p) for c in out])


def p_divmod(a, b, p, steps=None):
    """Long division a = q*b + r. Over Zp p must be prime; p = 0 uses fractions."""
    if b == [0]:
        raise ZeroDivisionError("division by the zero polynomial")
    lead = b[-1]
    if p:
        lead_inv = inverse_mod(lead, p)
    r = [Fraction(c) for c in a] if not p else list(a)
    q = [0] * max(len(a) - len(b) + 1, 1)
    while degree(r) >= degree(b):
        shift = degree(r) - degree(b)
        c = r[-1] * lead_inv % p if p else Fraction(r[-1]) / lead
        q[shift] = c
        term = [0] * shift + [c]
        sub = p_mul(term, b, p) if p else [c * x for x in [0] * shift + b]
        r = p_add(r, p_neg(sub, p), p)
        if steps is not None:
            steps.append(f"subtract ({poly_str(_nice(term))}) * ({poly_str(_nice(b))}) "
                         f"-> remainder {poly_str(_nice(r))}")
    return _trim(q), _trim(r)


def _nice(poly):
    """Fractions that are whole numbers shown as integers."""
    out = []
    for c in poly:
        if isinstance(c, Fraction):
            out.append(c.numerator if c.denominator == 1 else c)
        else:
            out.append(c)
    return out


def _fmt(poly):
    poly = _nice(poly)
    if any(isinstance(c, Fraction) for c in poly):
        # show fractional coefficients in brackets
        terms = []
        for power in range(len(poly) - 1, -1, -1):
            c = poly[power]
            if c:
                x = "" if power == 0 else ("x" if power == 1 else f"x^{power}")
                terms.append(f"({c}){x}" if isinstance(c, Fraction) else f"{c}{x}")
        return " + ".join(terms) or "0"
    return poly_str(poly)


def _monic_polys(deg, p):
    for tail in itertools.product(range(p), repeat=deg):
        yield list(tail) + [1]


def factor_poly(poly, p):
    """Factor over GF(p) into irreducible polynomials (small degrees)."""
    factors = []
    poly = list(poly)
    lead = poly[-1]
    if lead != 1:
        poly = [c * inverse_mod(lead, p) % p for c in poly]
    d = 1
    while degree(poly) >= 2 * d:
        found = False
        for cand in _monic_polys(d, p):
            q, r = p_divmod(poly, cand, p)
            if r == [0]:
                factors.append(cand)
                poly = q
                found = True
                break
        if not found:
            d += 1
    if degree(poly) > 0:
        factors.append(poly)
    return lead, factors


# ---------- GF(2^n) with integers as bit patterns ----------

def gf2_mul_raw(a, b):
    out = 0
    while b:
        if b & 1:
            out ^= a
        a <<= 1
        b >>= 1
    return out


def gf2_divmod(a, b):
    q = 0
    db = b.bit_length()
    while a and a.bit_length() >= db:
        shift = a.bit_length() - db
        q |= 1 << shift
        a ^= b << shift
    return q, a


def _bits(value, n):
    return format(value, f"0{n}b")


def _check_prime(p):
    if p == 0:
        return
    if not is_probable_prime(p):
        raise ValueError(f"the coefficient modulus p = {p} must be a prime (or 0 for ordinary "
                         "arithmetic): division only works over a field")


# ---------- the tools ----------

@_safe
def polynomial_arithmetic(a: str, b: str, operation: str, p: int = 2) -> dict:
    """Polynomial arithmetic with coefficients in Zp (default GF(2), where + is XOR).
    a, b: polynomials such as 'x^3 + x^2 + 2', 'x7 + x5 + x4 + x3 + x + 1' or, for
    p=2, bits '10011'. p: a prime, or 0 for ordinary arithmetic with integer
    coefficients (division then gives fractions).
    operation: 'add', 'subtract', 'multiply', 'divide' (quotient q(x) and remainder
    r(x) with a = q*b + r, plus the long-division steps), 'gcd' (Euclid's algorithm
    for polynomials, with steps), or 'factor' (is a irreducible? its factors over
    GF(p); b is ignored). Example: p=0, a='x^3+x^2+2', b='x^2-x+1', 'divide' gives
    q = x + 2, r = x."""
    p = int(p)
    _check_prime(p)
    op = operation.strip().lower()
    pa = parse_poly(a, p)
    result = {"a": poly_str(pa), "p": p or "ordinary integers"}
    if op in ("factor", "irreducible", "is_irreducible"):
        if not p:
            raise ValueError("factoring is supported over GF(p) only (give a prime p)")
        if degree(pa) < 1:
            raise ValueError("give a polynomial of degree 1 or more")
        if degree(pa) > 24 or p ** (degree(pa) // 2) > 200_000:
            raise ValueError("this polynomial is too large to factor here")
        lead, factors = factor_poly(pa, p)
        result.update({"irreducible": len(factors) == 1,
                       "factors": [poly_str(f) for f in factors],
                       "factorization": (f"{lead} * " if lead != 1 else "")
                       + " * ".join(f"({poly_str(f)})" for f in factors)})
        if p == 2 and degree(pa) >= 2:
            result["note"] = ("over GF(2) a polynomial with no root (f(0) and f(1) both 1) has no "
                              "factor of degree 1; degree 2 and 3 polynomials with no root are "
                              "irreducible")
        return result
    pb = parse_poly(b, p)
    result["b"] = poly_str(pb)
    if op in ("add", "+", "addition"):
        r = p_add(pa, pb, p)
        result["result"] = poly_str(r)
    elif op in ("subtract", "sub", "-", "subtraction"):
        r = p_add(pa, p_neg(pb, p), p)
        result["result"] = poly_str(r)
    elif op in ("multiply", "mul", "*", "multiplication"):
        r = p_mul(pa, pb, p)
        result["result"] = poly_str(r)
    elif op in ("divide", "div", "/", "division", "mod"):
        steps = []
        q, r = p_divmod(pa, pb, p, steps)
        result.update({"quotient": _fmt(q), "remainder": _fmt(r), "steps": steps[:MAX_STEPS],
                       "check": "a = quotient * b + remainder"})
        if p == 2:
            result["bits"] = {"a": _bits(poly_to_int(pa), 1), "b": _bits(poly_to_int(pb), 1),
                              "quotient": _bits(poly_to_int(q), 1),
                              "remainder": _bits(poly_to_int(r), 1)}
        return result
    elif op == "gcd":
        if not p:
            raise ValueError("polynomial gcd is supported over GF(p) only (give a prime p)")
        x, y, steps = pa, pb, []
        if degree(x) < degree(y):
            x, y = y, x
        while y != [0]:
            q, r = p_divmod(x, y, p)
            steps.append(f"{poly_str(x)} = ({poly_str(q)}) * ({poly_str(y)}) + ({poly_str(r)})")
            x, y = y, r
        if x[-1] != 1:            # make the gcd monic
            inv = inverse_mod(x[-1], p)
            x = [c * inv % p for c in x]
        result.update({"gcd": poly_str(x), "steps": steps[:MAX_STEPS]})
        return result
    else:
        raise ValueError("operation must be add, subtract, multiply, divide, gcd or factor")
    if p == 2:
        result["result_bits"] = _bits(poly_to_int(r), 1)
    return result


@_safe
def gf2n_arithmetic(a: str, b: str, operation: str,
                    modulus: str = "x^8 + x^4 + x^3 + x + 1") -> dict:
    """Arithmetic in the finite field GF(2^n), e.g. AES's GF(2^8). Elements are
    polynomials over GF(2) of degree below n, which are n-bit words.
    a, b: polynomials ('x^5 + x^2 + x'), bits ('00100110') or hex ('0x57').
    modulus: the irreducible polynomial m(x) of degree n (default the AES one,
    x^8 + x^4 + x^3 + x + 1 = 100011011). Examples: GF(2^3) uses 'x^3 + x + 1',
    GF(2^4) uses 'x^4 + x + 1'.
    operation: 'add' (= subtract = XOR), 'multiply' (shows both the long division
    of the product by m(x) and the computer method of repeatedly multiplying by x,
    with shift and XOR), 'inverse' (multiplicative inverse of a with the extended
    Euclidean table q, r1, r2, r, t1, t2, t; b is ignored), or 'divide' (a * b^-1).
    Example: (x^5 + x^2 + x) * (x^7 + x^4 + x^3 + x^2 + x) in GF(2^8) = x^5 + x^3 + x^2 + x + 1."""
    m = poly_to_int(parse_poly(modulus, 2))
    n = m.bit_length() - 1
    if n < 1:
        raise ValueError("the modulus must have degree 1 or more")
    _, factors = factor_poly(int_to_poly(m), 2) if n <= 24 else (1, [None])
    irreducible = len(factors) == 1
    op = operation.strip().lower()
    x = poly_to_int(parse_poly(a, 2))
    result = {"field": f"GF(2^{n})", "modulus": poly_str(int_to_poly(m)),
              "modulus_bits": _bits(m, n + 1)}
    if not irreducible:
        result["warning"] = (f"{poly_str(int_to_poly(m))} is NOT irreducible "
                             f"({' * '.join('(' + poly_str(f) + ')' for f in factors)}), "
                             "so this is not a field and some elements have no inverse")
    if x.bit_length() > n:
        r = gf2_divmod(x, m)[1]
        result["note_a"] = f"a has degree n or more, reduced mod m(x) to {poly_str(int_to_poly(r))}"
        x = r

    def show(v):
        return {"polynomial": poly_str(int_to_poly(v)), "bits": _bits(v, n), "hex": f"0x{v:0{(n + 3) // 4}X}"}

    result["a"] = show(x)
    if op in ("inverse", "inv"):
        return _gf_inverse(x, m, n, result, show)

    y = poly_to_int(parse_poly(b, 2))
    if y.bit_length() > n:
        y = gf2_divmod(y, m)[1]
    result["b"] = show(y)
    if op in ("add", "subtract", "xor", "+", "-"):
        result["result"] = show(x ^ y)
        result["steps"] = [f"{_bits(x, n)} XOR {_bits(y, n)} = {_bits(x ^ y, n)}"]
        return result
    if op in ("divide", "div", "/"):
        inv = _gf_inverse(y, m, n, {}, show)
        if "inverse" not in inv:
            return {**result, "error": "b has no inverse, so a / b is not defined"}
        y_inv = poly_to_int(parse_poly(inv["inverse"]["polynomial"], 2))
        result["b_inverse"] = inv["inverse"]
        x, y = x, y_inv
        result["note"] = "a / b = a * b^-1"
    elif op not in ("multiply", "mul", "*", "times"):
        raise ValueError("operation must be add, multiply, inverse or divide")

    product = gf2_mul_raw(x, y)
    q, r = gf2_divmod(product, m)
    # the computer method: x^i * b for i = 0..deg(a), reducing whenever the top bit overflows
    shifts, value = [], y
    for i in range(max(x.bit_length(), 1)):
        if i:
            overflow = value >> (n - 1) & 1
            value = (value << 1) & ((1 << n) - 1)
            line = f"x^{i} * b = {_bits(value, n)}"
            if overflow:
                value ^= m & ((1 << n) - 1)
                line = f"x^{i} * b = shift left, top bit was 1 so XOR {_bits(m & ((1 << n) - 1), n)} -> {_bits(value, n)}"
            shifts.append(line)
        else:
            shifts.append(f"x^0 * b = {_bits(value, n)}")
        shifts[-1] += "   (used)" if x >> i & 1 else ""
    result.update({
        "unreduced_product": poly_str(int_to_poly(product)),
        "division_by_modulus": f"{poly_str(int_to_poly(product))} = ({poly_str(int_to_poly(q))}) * m(x) + "
                               f"({poly_str(int_to_poly(r))})",
        "shift_and_xor_method": shifts,
        "result": show(r)})
    return result


def _gf_inverse(x, m, n, result, show):
    if x == 0:
        return {**result, "error": "0 has no multiplicative inverse"}
    r1, r2, t1, t2 = m, x, 0, 1
    rows = []
    while r2:
        q, r = gf2_divmod(r1, r2)
        t = t1 ^ gf2_mul_raw(q, t2)
        rows.append({k: poly_str(int_to_poly(v)) for k, v in
                     (("q", q), ("r1", r1), ("r2", r2), ("r", r), ("t1", t1), ("t2", t2), ("t", t))})
        r1, r2, t1, t2 = r2, r, t2, t
    rows.append({"q": "", "r1": poly_str(int_to_poly(r1)), "r2": "0", "r": "",
                 "t1": poly_str(int_to_poly(t1)), "t2": poly_str(int_to_poly(t2)), "t": ""})
    if r1 != 1:
        return {**result, "error": f"gcd is {poly_str(int_to_poly(r1))}, not 1, so there is no inverse",
                "table": rows}
    inv = gf2_divmod(t1, m)[1]
    check = gf2_divmod(gf2_mul_raw(x, inv), m)[1]
    return {**result, "inverse": show(inv), "table": rows[:MAX_STEPS],
            "how_to_read": "start r1 = m(x), r2 = a, t1 = 0, t2 = 1; t = t1 - q*t2 (= XOR in GF(2)); "
                           "when r1 = 1 the inverse is t1",
            "check": f"a * inverse mod m(x) = {poly_str(int_to_poly(check))}"}


FINITE_FIELD_TOOLS = [polynomial_arithmetic, gf2n_arithmetic]


if __name__ == "__main__":
    print(polynomial_arithmetic("x^3 + x^2 + 2", "x^2 - x + 1", "divide", 0))
    print(gf2n_arithmetic("x^5 + x^2 + x", "x^7 + x^4 + x^3 + x^2 + x", "multiply")["result"])
    print(gf2n_arithmetic("x5", "", "inverse")["inverse"])            # x^5 + x^4 + x^3 + x
    print(gf2n_arithmetic("x^2 + 1", "", "inverse", "x^4 + x + 1")["inverse"])  # x^3 + x + 1
    print(polynomial_arithmetic("x^4 + 1", "", "factor"))
