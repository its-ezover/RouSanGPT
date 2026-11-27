import ast
import math
import operator


# ---------- Internet checksum (16-bit one's complement) ----------

def _to_int(word, bits):
    """A binary string ('0110011001100000', '01011100', '1010') or hex ('0x6660', or
    '6660' when it has digits other than 0 and 1). A string of only 0s and 1s is
    always read as binary, never as hex."""
    w = word.strip().replace(" ", "").replace("_", "")
    if w.lower().startswith("0x"):
        value = int(w, 16)
    elif w and set(w) <= {"0", "1"}:
        value = int(w, 2)
    else:
        value = int(w, 16)
    if not 0 <= value < (1 << bits):
        raise ValueError(f"'{word}' does not fit in {bits} bits")
    return value


def _word_bits(words, word_size_bits):
    if word_size_bits not in (0, 8, 16):
        raise ValueError("word_size_bits must be 16 (UDP, TCP, IP) or 8")
    if word_size_bits:
        return word_size_bits
    clean = [w.strip().replace(" ", "").replace("_", "") for w in words]
    if clean and all(set(w) <= {"0", "1"} and len(w) == 8 for w in clean):
        return 8                     # every word is written as 8 bits: an 8-bit problem
    return 16


def _ones_complement_sum(values, bits):
    mask = (1 << bits) - 1
    total = 0
    steps = []
    for v in values:
        total += v
        carried = total > mask
        if carried:
            total = (total & mask) + 1      # wrap the carry around
        steps.append(f"+ {v:0{bits}b} -> {total:0{bits}b}" + ("  (carry wrapped around)" if carried else ""))
    return total, steps


def _read_words(words, word_size_bits):
    bits = _word_bits(words, int(word_size_bits))
    return [_to_int(w, bits) for w in words], bits


def internet_checksum_calculate(words: list[str], word_size_bits: int = 0) -> dict:
    """Calculate the Internet checksum (used by UDP, TCP and IP) of a list of words.
    Each word is binary such as '0110011001100000' or hex such as '0x6660'. A word
    made only of 0s and 1s is always read as binary. word_size_bits: 16 (the real
    protocols) or 8 (textbook problems with 8-bit bytes); 0 = automatic (8 when
    every word is written as 8 bits, otherwise 16). The words are added with one's
    complement addition (a carry out of the top bit is added back at the bottom),
    and the checksum is the one's complement (all bits flipped) of that sum. Returns
    the sum, the checksum in binary and hex, and the addition steps."""
    try:
        values, bits = _read_words(words, word_size_bits)
    except ValueError as e:
        return {"error": f"Could not read the words: {e}"}
    if not values:
        return {"error": "Give at least one word."}
    total, steps = _ones_complement_sum(values, bits)
    checksum = ((1 << bits) - 1) ^ total
    digits = bits // 4
    return {
        "word_size_bits": bits,
        "sum": f"{total:0{bits}b}",
        "sum_hex": f"0x{total:0{digits}X}",
        "checksum": f"{checksum:0{bits}b}",
        "checksum_hex": f"0x{checksum:0{digits}X}",
        "steps": steps,
    }


def internet_checksum_verify(words_including_checksum: list[str], word_size_bits: int = 0) -> dict:
    """Check a received message with the Internet checksum. Give ALL words, including
    the checksum word itself (binary like '0110011001100000' or hex like '0x6660').
    word_size_bits: 16, 8, or 0 = automatic (as in internet_checksum_calculate). If
    the one's complement sum is all ones, no error is detected; otherwise an error is
    detected."""
    try:
        values, bits = _read_words(words_including_checksum, word_size_bits)
    except ValueError as e:
        return {"error": f"Could not read the words: {e}"}
    if not values:
        return {"error": "Give at least one word."}
    total, steps = _ones_complement_sum(values, bits)
    return {
        "word_size_bits": bits,
        "sum": f"{total:0{bits}b}",
        "error_detected": total != (1 << bits) - 1,
        "steps": steps,
    }


# ---------- Safe general calculator ----------

_OPERATORS = {
    ast.Add: operator.add, ast.Sub: operator.sub, ast.Mult: operator.mul,
    ast.Div: operator.truediv, ast.FloorDiv: operator.floordiv,
    ast.Mod: operator.mod, ast.Pow: operator.pow,
    ast.USub: operator.neg, ast.UAdd: operator.pos,
}
_FUNCTIONS = {
    "sqrt": math.sqrt, "log2": math.log2, "log10": math.log10, "ln": math.log,
    "ceil": math.ceil, "floor": math.floor, "abs": abs, "round": round,
    "min": min, "max": max,
}


def _evaluate(node):
    if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
        return node.value
    if isinstance(node, ast.BinOp) and type(node.op) in _OPERATORS:
        left, right = _evaluate(node.left), _evaluate(node.right)
        if isinstance(node.op, ast.Pow):
            if abs(right) > 1000:
                raise ValueError("exponent too large")
            # stop answers with millions of digits, e.g. (9**999)**999
            if left not in (0, 1, -1) and abs(right) * math.log10(max(abs(left), 2)) > 10000:
                raise ValueError("the result would have more than 10,000 digits")
        return _OPERATORS[type(node.op)](left, right)
    if isinstance(node, ast.UnaryOp) and type(node.op) in _OPERATORS:
        return _OPERATORS[type(node.op)](_evaluate(node.operand))
    if (isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
            and node.func.id in _FUNCTIONS and not node.keywords):
        return _FUNCTIONS[node.func.id](*[_evaluate(a) for a in node.args])
    raise ValueError("only numbers, + - * / // % **, parentheses and the listed functions are allowed")


def calculator(expression: str) -> dict:
    """Exactly evaluate a math expression. Use this for ANY arithmetic: throughput,
    utilization, RTT, queuing delay, unit conversions, powers of two, and so on.
    Write it with * for multiply, / for divide and ** for power, for example
    '(1500*8)/(10*10**6)' or '8000/(0.03+8000/10**9)'. Available functions: sqrt,
    log2, log10, ln, ceil, floor, abs, round, min, max. Convert units yourself
    first (bytes to bits, ms to seconds, Mbps to bps)."""
    try:
        result = _evaluate(ast.parse(expression.strip(), mode="eval").body)
    except ZeroDivisionError:
        return {"error": "Division by zero."}
    except (ValueError, SyntaxError, TypeError, OverflowError) as e:
        return {"error": f"Cannot calculate this: {e}"}
    return {"expression": expression, "result": result}


# The list we give to the AI
EXTRA_TOOLS = [internet_checksum_calculate, internet_checksum_verify, calculator]


# Quick self-test: run `python extra_tools.py`
if __name__ == "__main__":
    words = ["0110011001100000", "0101010101010101", "1000111100001100"]
    r = internet_checksum_calculate(words)
    print("sum:     ", r["sum"])
    print("checksum:", r["checksum"])
    print(internet_checksum_verify(words + [r["checksum"]]))
    print(calculator("(1500*8)/(10*10**6)"))
    print(calculator("log2(1024) + ceil(7/2)"))
    print(calculator("__import__('os').system('ls')"))   # must be refused