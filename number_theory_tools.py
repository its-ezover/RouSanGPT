"""Number theory for cryptography (Stallings ch. 2, Forouzan ch. 2 and 9).

Every tool shows its working in the same table form the slides use, so the tutor can
explain each step and check a student's own table.
"""
import functools
import math
import random

MAX_STEPS = 60          # longest list of steps a tool returns
SEARCH_LIMIT = 2_000_000  # most values tried by the brute-force searches


def _int(value, name):
    """The AI sometimes sends numbers as text: accept '1759' as well as 1759."""
    try:
        return int(str(value).strip().replace(",", "").replace(" ", ""))
    except ValueError:
        raise ValueError(f"{name} must be a whole number, not '{value}'") from None


def _ints(values, name):
    if isinstance(values, str):
        values = values.replace(",", " ").split()
    return [_int(v, name) for v in values]


def _safe(func):
    """Turn bad input into {'error': ...} so the AI can tell the student what was wrong."""
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except (ValueError, ZeroDivisionError, OverflowError) as e:
            return {"error": str(e)}
    return wrapper


# ---------- helpers shared with the other crypto tools ----------

def egcd(a, b):
    """(g, x, y) with a*x + b*y = g = gcd(a, b)."""
    x0, x1, y0, y1 = 1, 0, 0, 1
    while b:
        q, a, b = a // b, b, a % b
        x0, x1 = x1, x0 - q * x1
        y0, y1 = y1, y0 - q * y1
    return a, x0, y0


def inverse_mod(a, n):
    g, x, _ = egcd(a % n, n)
    if g != 1:
        raise ValueError(f"{a} has no inverse modulo {n}, because gcd({a}, {n}) = {g}, not 1")
    return x % n


def is_probable_prime(n):
    """Exact for every n below 3.3 * 10^24 (fixed Miller-Rabin bases)."""
    if n < 2:
        return False
    small = (2, 3, 5, 7, 11, 13, 17, 19, 23, 29, 31, 37, 41)
    for p in small:
        if n % p == 0:
            return n == p
    q, k = n - 1, 0
    while q % 2 == 0:
        q, k = q // 2, k + 1
    for a in small:
        x = pow(a, q, n)
        if x in (1, n - 1):
            continue
        for _ in range(k - 1):
            x = x * x % n
            if x == n - 1:
                break
        else:
            return False
    return True


def _pollard_rho(n):
    if n % 2 == 0:
        return 2
    while True:
        c = random.randrange(1, n)
        x = y = random.randrange(2, n)
        d = 1
        while d == 1:
            x = (x * x + c) % n
            y = (y * y + c) % n
            y = (y * y + c) % n
            d = math.gcd(abs(x - y), n)
        if d != n:
            return d


def factorize(n):
    """{prime: exponent} for n >= 1."""
    factors = {}
    for p in (2, 3, 5):
        while n % p == 0:
            factors[p] = factors.get(p, 0) + 1
            n //= p
    p, gaps, i = 7, (4, 2, 4, 2, 4, 6, 2, 6), 0
    while p * p <= n and p < 100_000:
        while n % p == 0:
            factors[p] = factors.get(p, 0) + 1
            n //= p
        p += gaps[i]
        i = (i + 1) % 8
    stack = [n] if n > 1 else []
    while stack:
        m = stack.pop()
        if is_probable_prime(m):
            factors[m] = factors.get(m, 0) + 1
        else:
            d = _pollard_rho(m)
            stack += [d, m // d]
    return dict(sorted(factors.items()))


def _factor_text(factors):
    return " * ".join(f"{p}^{e}" if e > 1 else str(p) for p, e in factors.items()) or "1"


def totient(n):
    result = n
    for p in factorize(n):
        result = result // p * (p - 1)
    return result


# ---------- the tools ----------

@_safe
def gcd_euclid(a: int, b: int) -> dict:
    """Find gcd(a, b) with the Euclidean algorithm, showing every division step
    a = q*b + r, using gcd(a, b) = gcd(b, a mod b). Also says whether a and b are
    relatively prime (gcd = 1). Example: a=710, b=310 gives 10."""
    a, b = abs(_int(a, "a")), abs(_int(b, "b"))
    x, y = max(a, b), min(a, b)
    steps = []
    while y:
        q, r = divmod(x, y)
        steps.append(f"{x} = {q} * {y} + {r}   ->   gcd({x}, {y}) = gcd({y}, {r})")
        x, y = y, r
    return {"gcd": x, "relatively_prime": x == 1, "steps": steps[:MAX_STEPS]}


@_safe
def extended_euclid(a: int, b: int) -> dict:
    """Extended Euclidean algorithm: find d = gcd(a, b) and integers x, y with
    a*x + b*y = d (Bezout). Returns the table of rows (r_i, q_i, x_i, y_i) where
    each row satisfies r_i = a*x_i + b*y_i, as in the slides (x_i = x_(i-2) - q_i*x_(i-1)).
    Example: a=1759, b=550 gives d=1, x=-111, y=355. If d = 1 it also gives
    a^-1 mod b and b^-1 mod a."""
    a, b = _int(a, "a"), _int(b, "b")
    if a == 0 and b == 0:
        raise ValueError("gcd(0, 0) is defined as 0, there is nothing to solve")
    rows = [{"i": -1, "r": a, "q": "", "x": 1, "y": 0},
            {"i": 0, "r": b, "q": "", "x": 0, "y": 1}]
    while rows[-1]["r"] != 0:
        p, c = rows[-2], rows[-1]
        q = p["r"] // c["r"]
        rows.append({"i": c["i"] + 1, "r": p["r"] - q * c["r"], "q": q,
                     "x": p["x"] - q * c["x"], "y": p["y"] - q * c["y"]})
    last = rows[-2]
    d, x, y = last["r"], last["x"], last["y"]
    if d < 0:
        d, x, y = -d, -x, -y
    result = {"gcd": d, "x": x, "y": y,
              "check": f"{a}*({x}) + {b}*({y}) = {a * x + b * y}",
              "table": rows[:MAX_STEPS]}
    if d == 1:
        if b:
            result["a_inverse_mod_b"] = x % abs(b)
        if a:
            result["b_inverse_mod_a"] = y % abs(a)
    return result


@_safe
def modular_inverse(a: int, n: int) -> dict:
    """Find the multiplicative inverse a^-1 mod n (the number b with a*b mod n = 1)
    with the extended Euclidean algorithm. Returns the table with columns
    q, r1, r2, r, t1, t2, t (Forouzan / slide style, starting r1=n, r2=a, t1=0, t2=1):
    the inverse is t1 when r1 reaches 1. Example: the inverse of 11 in Z26 is 19
    (also written -7). If gcd(a, n) is not 1 there is no inverse."""
    a, n = _int(a, "a"), _int(n, "n")
    if n < 2:
        raise ValueError("the modulus n must be at least 2")
    r1, r2, t1, t2 = n, a % n, 0, 1
    rows = []
    while r2 > 0:
        q = r1 // r2
        r, t = r1 - q * r2, t1 - q * t2
        rows.append({"q": q, "r1": r1, "r2": r2, "r": r, "t1": t1, "t2": t2, "t": t})
        r1, r2, t1, t2 = r2, r, t2, t
    rows.append({"q": "", "r1": r1, "r2": r2, "r": "", "t1": t1, "t2": t2, "t": ""})
    if r1 != 1:
        return {"has_inverse": False, "gcd": r1,
                "reason": f"gcd({a}, {n}) = {r1}, so {a} has no inverse modulo {n}",
                "table": rows[:MAX_STEPS]}
    inv = t1 % n
    return {"has_inverse": True, "inverse": inv, "t1_from_table": t1,
            "check": f"{a} * {inv} mod {n} = {a * inv % n}", "table": rows[:MAX_STEPS]}


@_safe
def modular_power(base: int, exponent: int, modulus: int) -> dict:
    """Calculate base^exponent mod modulus exactly, with the square-and-multiply
    steps. A negative exponent means the inverse first (8^-1 mod 17 = 15).
    Also shows the Fermat / Euler shortcut when it applies (a^(p-1) = 1 mod p,
    a^phi(n) = 1 mod n). Examples: 6^10 mod 11 = 1, 20^62 mod 77 = 15."""
    a, e, n = _int(base, "base"), _int(exponent, "exponent"), _int(modulus, "modulus")
    if n < 1:
        raise ValueError("the modulus must be positive")
    result = {"base": a, "exponent": e, "modulus": n}
    if e < 0:
        inv = inverse_mod(a, n)
        result["inverse_of_base"] = inv
        result["note"] = f"{a}^{e} mod {n} = ({a}^-1)^{-e} mod {n} = {inv}^{-e} mod {n}"
        a, e = inv, -e
    a %= n
    bits = bin(e)[2:]
    steps, value = [], 1
    for bit in bits:                         # left-to-right square-and-multiply
        before = value
        value = value * value % n
        line = f"bit {bit}: square {before}^2 mod {n} = {value}"
        if bit == "1":
            value = value * a % n
            line += f", multiply by {a} -> {value}"
        steps.append(line)
    result.update({"result": value, "exponent_in_binary": bits, "steps": steps[:MAX_STEPS]})
    if math.gcd(a, n) == 1 and n > 2 and e > 0:
        phi = totient(n)
        name = "Fermat" if is_probable_prime(n) else "Euler"
        rule = f"p-1 = {n - 1}" if name == "Fermat" else f"phi({n}) = {phi}"
        result["shortcut"] = (f"{name}: {a}^{phi} = 1 mod {n} ({rule}), so reduce the exponent "
                              f"mod {phi}: {e} mod {phi} = {e % phi}, and {a}^{e % phi} mod {n} = "
                              f"{pow(a, e % phi, n)}")
    return result


@_safe
def euler_totient(n: int) -> dict:
    """Euler's totient phi(n): how many numbers in 1..n-1 are relatively prime to n.
    Shows the prime factorization and the formula phi(n) = n * product(1 - 1/p),
    e.g. phi(p) = p-1 for a prime and phi(p*q) = (p-1)(q-1). For n up to 200 it
    also lists the set Zn* of those numbers. Example: phi(21) = 12."""
    n = _int(n, "n")
    if n < 1:
        raise ValueError("n must be positive")
    if n == 1:
        return {"phi": 1, "note": "phi(1) = 1 by definition"}
    f = factorize(n)
    parts = []
    for p, e in f.items():
        parts.append(f"({p}-1)" if e == 1 else f"{p}^{e - 1}*({p}-1)")
    result = {"phi": totient(n), "factorization": _factor_text(f),
              "formula": f"phi({n}) = " + " * ".join(parts) + f" = {totient(n)}",
              "n_is_prime": len(f) == 1 and list(f.values()) == [1]}
    if n <= 200:
        result["Zn_star"] = [k for k in range(1, n) if math.gcd(k, n) == 1]
    return result


@_safe
def prime_factorization(n: int) -> dict:
    """Is n prime? Gives the prime factorization n = p1^a1 * p2^a2 * ...
    (Fundamental Theorem of Arithmetic), and for n up to 10^6 the list of
    positive divisors. Works for very large numbers too."""
    n = _int(n, "n")
    if n < 2:
        raise ValueError("give a whole number of 2 or more")
    f = factorize(n)
    result = {"n": n, "is_prime": len(f) == 1 and list(f.values()) == [1],
              "factorization": _factor_text(f),
              "prime_factors": [{"prime": p, "exponent": e} for p, e in f.items()]}
    if n <= 1_000_000:
        result["divisors"] = [d for d in range(1, math.isqrt(n) + 1) if n % d == 0]
        result["divisors"] = sorted(set(result["divisors"] + [n // d for d in result["divisors"]]))
    return result


@_safe
def miller_rabin_test(n: int, bases: list[int]) -> dict:
    """Miller-Rabin primality test, step by step as in the slides: write
    n-1 = 2^k * q with q odd, then for each base a compute a^q, a^(2q), a^(4q), ...
    mod n. If the first is 1 or some value is n-1 the result is 'inconclusive'
    (maybe prime), otherwise 'composite' (surely not prime). bases: the values of a
    to test, e.g. [671]; give [] to use a few random bases.
    Example: n=1729, bases=[671] gives k=6, q=27 and 'composite'."""
    n = _int(n, "n")
    if n < 5 or n % 2 == 0:
        raise ValueError("Miller-Rabin needs an odd n of 5 or more")
    q, k = n - 1, 0
    while q % 2 == 0:
        q, k = q // 2, k + 1
    chosen = _ints(bases or [], "bases") or random.sample(range(2, n - 1), min(4, n - 3))
    tests = []
    for a in chosen:
        if not 1 < a < n - 1:
            tests.append({"a": a, "error": f"a must be between 2 and {n - 2}"})
            continue
        x = pow(a, q, n)
        sequence = [f"{a}^{q} mod {n} = {x}"]
        verdict = "inconclusive" if x in (1, n - 1) else None
        reason = f"a^q mod n = {x}" + (" = 1" if x == 1 else " = n-1" if x == n - 1 else "")
        j = 0
        while verdict is None and j < k - 1:
            j += 1
            x = x * x % n
            sequence.append(f"{a}^({q}*2^{j}) mod {n} = {x}")
            if x == n - 1:
                verdict, reason = "inconclusive", f"a^(q*2^{j}) mod n = n-1"
        if verdict is None:
            verdict, reason = "composite", "no value in the list equals n-1"
        tests.append({"a": a, "sequence": sequence, "result": verdict, "reason": reason})
    composite = any(t.get("result") == "composite" for t in tests)
    return {"n": n, "k": k, "q": q, "n_minus_1": f"{n - 1} = 2^{k} * {q}", "tests": tests,
            "conclusion": "composite (definitely not prime)" if composite
            else f"probably prime (chance of error below (1/4)^{len(tests)})",
            "actually_prime": is_probable_prime(n)}


@_safe
def chinese_remainder(remainders: list[int], moduli: list[int]) -> dict:
    """Solve x = a1 mod m1, x = a2 mod m2, ... with the Chinese Remainder Theorem.
    remainders: [a1, a2, ...]; moduli: [m1, m2, ...] (pairwise relatively prime).
    Shows M = m1*m2*..., Mi = M/mi, the inverse of Mi mod mi and
    x = sum(ai * Mi * Mi^-1) mod M. Example: remainders [2, 3, 2], moduli [3, 5, 7]
    gives 23."""
    a, m = _ints(remainders, "remainders"), _ints(moduli, "moduli")
    if len(a) != len(m) or not a:
        raise ValueError("give the same number of remainders and moduli")
    for i in range(len(m)):
        for j in range(i + 1, len(m)):
            if math.gcd(m[i], m[j]) != 1:
                raise ValueError(f"moduli {m[i]} and {m[j]} are not relatively prime "
                                 f"(gcd = {math.gcd(m[i], m[j])})")
    big_m = math.prod(m)
    rows, total = [], 0
    for ai, mi in zip(a, m):
        mi_big = big_m // mi
        inv = inverse_mod(mi_big, mi)
        rows.append({"a": ai, "m": mi, "M_i": mi_big, "M_i_inverse_mod_m": inv,
                     "a*M_i*inverse": ai * mi_big * inv})
        total += ai * mi_big * inv
    x = total % big_m
    return {"x": x, "M": big_m, "rows": rows,
            "formula": f"x = {total} mod {big_m} = {x}",
            "check": [f"{x} mod {mi} = {x % mi}" for mi in m]}


@_safe
def solve_linear_congruence(a: int, b: int, n: int) -> dict:
    """Solve a*x = b (mod n). Let d = gcd(a, n): if d does not divide b there is no
    solution; otherwise there are d solutions, found with
    x0 = (b/d) * (a/d)^-1 mod (n/d), then x0 + k*(n/d). Example: 14x = 12 (mod 18)."""
    a, b, n = _int(a, "a"), _int(b, "b"), _int(n, "n")
    if n < 2:
        raise ValueError("n must be at least 2")
    d = math.gcd(a, n)
    if b % d:
        return {"gcd": d, "solutions": [], "reason": f"gcd({a}, {n}) = {d} does not divide {b}"}
    a2, b2, n2 = a // d, b // d, n // d
    inv = inverse_mod(a2, n2) if n2 > 1 else 0
    x0 = b2 * inv % n2 if n2 > 1 else 0
    sols = [x0 + k * n2 for k in range(d)]
    return {"gcd": d, "reduced": f"{a2}x = {b2} (mod {n2})",
            "inverse": f"{a2}^-1 mod {n2} = {inv}", "x0": x0,
            "solutions": sols[:200], "number_of_solutions": d}


@_safe
def primitive_roots(n: int, a: int = 0) -> dict:
    """Orders and primitive roots modulo n. With a = 0: list the primitive roots of n
    (numbers whose order equals phi(n)). With a given: the order of a mod n and the
    table of its powers a^1, a^2, ... mod n (like Stallings Table 2.7)."""
    n, a = _int(n, "n"), _int(a, "a")
    if not 2 <= n <= SEARCH_LIMIT:
        raise ValueError(f"n must be between 2 and {SEARCH_LIMIT}")
    phi = totient(n)
    prime_factors_of_phi = list(factorize(phi)) if phi > 1 else []

    def order(g):
        if math.gcd(g, n) != 1:
            return None
        o = phi
        for p in prime_factors_of_phi:
            while o % p == 0 and pow(g, o // p, n) == 1:
                o //= p
        return o

    if a:
        o = order(a % n)
        if o is None:
            return {"a": a, "n": n, "order": None,
                    "reason": f"gcd({a}, {n}) is not 1, so the powers never reach 1"}
        powers = [f"{a}^{i} = {pow(a, i, n)}" for i in range(1, min(o, 100) + 1)]
        return {"a": a, "n": n, "phi": phi, "order": o, "is_primitive_root": o == phi,
                "powers_mod_n": powers}
    roots = []
    for g in range(1, n):
        if order(g) == phi:
            roots.append(g)
            if len(roots) >= 100:
                break
    return {"n": n, "phi": phi, "primitive_roots": roots,
            "count": totient(phi) if roots else 0,
            "note": "" if roots else f"{n} has no primitive root"}


@_safe
def discrete_logarithm(base: int, value: int, modulus: int) -> dict:
    """Discrete logarithm: find the smallest x >= 0 with base^x = value (mod modulus),
    written x = dlog(base, modulus)(value). Uses baby-step giant-step, so it works
    for moduli up to about 10^12. Example: base 2, value 9, modulus 11 gives 6."""
    g, h, n = _int(base, "base"), _int(value, "value"), _int(modulus, "modulus")
    if n < 2 or n > 10 ** 12:
        raise ValueError("the modulus must be between 2 and 10^12")
    g, h = g % n, h % n
    m = math.isqrt(n) + 1
    table, e = {}, 1
    for j in range(m):
        table.setdefault(e, j)
        e = e * g % n
    found = None
    if math.gcd(g, n) == 1:
        factor, gamma = pow(inverse_mod(g, n), m, n), h
        for i in range(m):
            if gamma in table:
                found = i * m + table[gamma]
                break
            gamma = gamma * factor % n
    else:   # no inverse of the base: try small exponents directly
        e = 1
        for x in range(min(n, SEARCH_LIMIT)):
            if e == h:
                found = x
                break
            e = e * g % n
    if found is None:
        return {"exists": False, "reason": f"no power of {g} is {h} mod {n}"}
    return {"exists": True, "x": found, "check": f"{g}^{found} mod {n} = {pow(g, found, n)}"}


@_safe
def modular_tables(n: int) -> dict:
    """Addition and multiplication tables modulo n (Zn), with the additive and
    multiplicative inverse of every element (slides: 'Addition/Multiplication Modulo 8').
    Also says whether Zn is a field (n prime) and whether GF(n) exists (n a prime
    power). Tables are given for n up to 16, inverses for n up to 200."""
    n = _int(n, "n")
    if not 2 <= n <= 200:
        raise ValueError("n must be between 2 and 200")
    f = factorize(n)
    result = {"n": n, "is_field": len(f) == 1 and list(f.values()) == [1],
              "GF_n_exists": len(f) == 1,
              "additive_inverses": {w: (-w) % n for w in range(n)},
              "multiplicative_inverses": {w: (inverse_mod(w, n) if math.gcd(w, n) == 1 else "none")
                                          for w in range(1, n)}}
    if n <= 16:
        result["addition_table"] = [[(r + c) % n for c in range(n)] for r in range(n)]
        result["multiplication_table"] = [[(r * c) % n for c in range(n)] for r in range(n)]
    result["note"] = ("Zn is a field because n is prime" if result["is_field"] else
                      "Zn is a commutative ring but not a field: some elements have no "
                      "multiplicative inverse" + (f"; GF({n}) exists but is built with "
                                                  "polynomials, not mod n" if len(f) == 1 else ""))
    return result


NUMBER_THEORY_TOOLS = [gcd_euclid, extended_euclid, modular_inverse, modular_power,
                       euler_totient, prime_factorization, miller_rabin_test,
                       chinese_remainder, solve_linear_congruence, primitive_roots,
                       discrete_logarithm, modular_tables]


if __name__ == "__main__":
    print(extended_euclid(1759, 550)["x"], extended_euclid(1759, 550)["y"])  # -111 355
    print(modular_inverse(11, 26)["inverse"])                                # 19
    print(modular_power(20, 62, 77)["result"], modular_power(8, -1, 17)["result"])  # 15 15
    print(miller_rabin_test(1729, [671])["conclusion"])
    print(chinese_remainder([2, 3, 2], [3, 5, 7])["x"])                      # 23
