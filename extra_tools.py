import ast
import math
import operator


# ---------- Internet checksum (16-bit one's complement) ----------

def _to_int16(word):
    """Accepts a 16-bit binary string ('0110011001100000') or hex ('0x6660' or '6660')."""
    w = word.strip().replace(" ", "")
    if w.lower().startswith("0x"):
        value = int(w, 16)
    elif len(w) == 16 and set(w) <= {"0", "1"}:
        value = int(w, 2)
    else:
        value = int(w, 16)
    if not 0 <= value <= 0xFFFF:
        raise ValueError(f"'{word}' does not fit in 16 bits")
    return value


def _ones_complement_sum(values):
    total = 0
    steps = []
    for v in values:
        total += v
        carried = total > 0xFFFF
        if carried:
            total = (total & 0xFFFF) + 1      # wrap the carry around
        steps.append(f"+ {v:016b} -> {total:016b}" + ("  (carry wrapped around)" if carried else ""))
    return total, steps


def internet_checksum_calculate(words: list[str]) -> dict:
    """Calculate the Internet checksum (used by UDP, TCP and IP) of a list of
    16-bit words. Each word is a 16-bit binary string such as '0110011001100000'
    or a hex value such as '0x6660'. The words are added with one's complement
    addition (a carry out of the top bit is added back at the bottom), and the
    checksum is the one's complement (all bits flipped) of that sum. Returns the sum,
    the checksum in binary and hex, and the addition steps."""
    try:
        values = [_to_int16(w) for w in words]
    except ValueError as e:
        return {"error": f"Could not read the words: {e}"}
    if not values:
        return {"error": "Give at least one 16-bit word."}
    total, steps = _ones_complement_sum(values)
    checksum = 0xFFFF ^ total
    return {
        "sum": f"{total:016b}",
        "sum_hex": f"0x{total:04X}",
        "checksum": f"{checksum:016b}",
        "checksum_hex": f"0x{checksum:04X}",
        "steps": steps,
    }


def internet_checksum_verify(words_including_checksum: list[str]) -> dict:
    """Check a received message with the Internet checksum. Give ALL 16-bit words,
    including the checksum word itself (binary like '0110011001100000' or hex like
    '0x6660'). If the one's complement sum is all ones (1111111111111111), no error
    is detected; otherwise an error is detected."""
    try:
        values = [_to_int16(w) for w in words_including_checksum]
    except ValueError as e:
        return {"error": f"Could not read the words: {e}"}
    if not values:
        return {"error": "Give at least one 16-bit word."}
    total, steps = _ones_complement_sum(values)
    return {
        "sum": f"{total:016b}",
        "error_detected": total != 0xFFFF,
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
        if isinstance(node.op, ast.Pow) and abs(right) > 1000:
            raise ValueError("exponent too large")
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