import ast
import inspect
import json
import keyword
import math
import operator
import re
from pathlib import Path

FILE = Path(__file__).resolve().parent / "formula_tools.json"
NAME_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]{0,40}$")

_OPERATORS = {
    ast.Add: operator.add, ast.Sub: operator.sub, ast.Mult: operator.mul,
    ast.Div: operator.truediv, ast.FloorDiv: operator.floordiv,
    ast.Mod: operator.mod, ast.Pow: operator.pow,
    ast.USub: operator.neg, ast.UAdd: operator.pos,
}
_FUNCTIONS = {
    "sqrt": math.sqrt, "log2": math.log2, "log10": math.log10, "ln": math.log,
    "exp": math.exp, "ceil": math.ceil, "floor": math.floor, "abs": abs,
    "round": round, "min": min, "max": max,
}
_CONSTANTS = {"pi": math.pi, "e": math.e}


def _evaluate(node, values):
    if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
        return node.value
    if isinstance(node, ast.Name):
        if node.id in values:
            return values[node.id]
        if node.id in _CONSTANTS:
            return _CONSTANTS[node.id]
        raise ValueError(f"unknown name '{node.id}'")
    if isinstance(node, ast.BinOp) and type(node.op) in _OPERATORS:
        left, right = _evaluate(node.left, values), _evaluate(node.right, values)
        if isinstance(node.op, ast.Pow) and abs(right) > 1000:
            raise ValueError("exponent too large")
        return _OPERATORS[type(node.op)](left, right)
    if isinstance(node, ast.UnaryOp) and type(node.op) in _OPERATORS:
        return _OPERATORS[type(node.op)](_evaluate(node.operand, values))
    if (isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
            and node.func.id in _FUNCTIONS and not node.keywords):
        return _FUNCTIONS[node.func.id](*[_evaluate(a, values) for a in node.args])
    raise ValueError("only numbers, the parameter names, + - * / // % **, brackets and "
                     "simple functions (sqrt, log2, log10, ln, exp, ceil, floor, abs, "
                     "round, min, max) are allowed")


def evaluate(formula, values):
    """Safely calculate a formula with the given parameter values."""
    return _evaluate(ast.parse(formula.strip(), mode="eval").body, values)


def load_specs():
    if not FILE.exists():
        return []
    try:
        return json.loads(FILE.read_text())
    except (json.JSONDecodeError, OSError):
        return []


def save_specs(specs):
    FILE.write_text(json.dumps(specs, indent=2, ensure_ascii=False))


def validate(raw, taken_names):
    name = (raw.get("name") or "").strip()
    if not NAME_RE.match(name) or keyword.iskeyword(name):
        raise ValueError("The tool name must use only English letters, digits and _ "
                         "(for example queuing_delay).")
    if name in taken_names:
        raise ValueError(f"A tool called '{name}' already exists.")
    description = (raw.get("description") or "").strip()
    if len(description) < 10:
        raise ValueError("Please describe what the tool calculates, in at least a short sentence.")
    params = []
    for p in raw.get("params") or []:
        pname = (p.get("name") or "").strip()
        if not NAME_RE.match(pname) or keyword.iskeyword(pname):
            raise ValueError(f"Bad parameter name '{pname}'. Use English letters, digits and _.")
        if pname in _CONSTANTS or pname in _FUNCTIONS:
            raise ValueError(f"'{pname}' is a reserved name, please choose another one.")
        params.append({"name": pname, "description": (p.get("description") or "").strip()})
    if not params:
        raise ValueError("Add at least one parameter.")
    if len({p["name"] for p in params}) != len(params):
        raise ValueError("Each parameter needs a different name.")
    formula = (raw.get("formula") or "").strip()
    try:
        evaluate(formula, {p["name"]: 1.7 for p in params})
    except ZeroDivisionError:
        pass
    except (ValueError, SyntaxError, TypeError, OverflowError) as e:
        raise ValueError(f"The formula has a problem: {e}")
    return {"name": name, "description": description, "params": params,
            "formula": formula, "unit": (raw.get("unit") or "").strip()}


def add_spec(raw, taken_names):
    spec = validate(raw, taken_names)
    specs = load_specs()
    specs.append(spec)
    save_specs(specs)
    return spec


def delete_spec(name):
    save_specs([s for s in load_specs() if s.get("name") != name])


def make_tool(spec):
    """Turn a saved formula into a real tool the AI can call."""
    names = [p["name"] for p in spec["params"]]

    def tool(**kwargs):
        try:
            values = {n: float(kwargs[n]) for n in names}
        except (KeyError, TypeError, ValueError):
            return {"error": f"Give a number for each of: {', '.join(names)}"}
        try:
            result = evaluate(spec["formula"], values)
        except ZeroDivisionError:
            return {"error": "Division by zero."}
        except (ValueError, OverflowError) as e:
            return {"error": str(e)}
        return {"result": result, "unit": spec["unit"], "formula": spec["formula"],
                "inputs": values}

    lines = [spec["description"], "",
             f"Formula: {spec['formula']}" + (f" (result in {spec['unit']})" if spec["unit"] else ""),
             "Parameters:"]
    for p in spec["params"]:
        lines.append(f"  {p['name']}: {p['description'] or 'a number'}")
    tool.__name__ = spec["name"]
    tool.__qualname__ = spec["name"]
    tool.__doc__ = "\n".join(lines)
    tool.__signature__ = inspect.Signature(
        [inspect.Parameter(n, inspect.Parameter.POSITIONAL_OR_KEYWORD, annotation=float)
         for n in names],
        return_annotation=dict)
    tool.__annotations__ = {**{n: float for n in names}, "return": dict}
    return tool


def load_tools():
    tools = []
    for spec in load_specs():
        try:
            tools.append(make_tool(spec))
        except Exception as e:
            print(f"  (skipping formula tool {spec.get('name')}: {e})")
    return tools