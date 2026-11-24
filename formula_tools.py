import ast
import inspect
import json
import keyword
import math
import operator
import re

from pydantic import BaseModel

from app_paths import FORMULA_TOOLS_FILE

FILE = FORMULA_TOOLS_FILE
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
    raise ValueError("only numbers, the input names, + - * / // % **, brackets and "
                     "simple functions (sqrt, log2, log10, ln, exp, ceil, floor, abs, "
                     "round, min, max) are allowed")


def evaluate(formula, values):
    """Safely calculate a formula with the given input values."""
    return _evaluate(ast.parse(formula.strip(), mode="eval").body, values)


def load_specs():
    if not FILE.exists():
        return []
    try:
        return json.loads(FILE.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return []


def save_specs(specs):
    FILE.write_text(json.dumps(specs, indent=2, ensure_ascii=False), encoding="utf-8")


def validate(raw, taken_names):
    name = (raw.get("name") or "").strip()
    if not NAME_RE.match(name) or keyword.iskeyword(name):
        raise ValueError("The tool name must use only English letters, digits and _ "
                         "(for example queuing_delay).")
    if name in taken_names:
        raise ValueError(f"A tool called '{name}' already exists. Choose another name.")
    description = (raw.get("description") or "").strip()
    if len(description) < 10:
        raise ValueError("Please describe what the tool calculates, in at least a short sentence.")
    params = []
    for p in raw.get("params") or []:
        pname = (p.get("name") or "").strip()
        if not NAME_RE.match(pname) or keyword.iskeyword(pname):
            raise ValueError(f"Bad input name '{pname}'. Use English letters, digits and _.")
        if pname in _CONSTANTS or pname in _FUNCTIONS:
            raise ValueError(f"'{pname}' is a reserved name, please choose another one.")
        example = p.get("example")
        try:
            example = float(example) if example not in (None, "") else None
        except (TypeError, ValueError):
            example = None
        params.append({"name": pname, "description": (p.get("description") or "").strip(),
                       "example": example})
    if not params:
        raise ValueError("The formula needs at least one input.")
    if len({p["name"] for p in params}) != len(params):
        raise ValueError("Each input needs a different name.")
    formula = (raw.get("formula") or "").strip()
    try:
        evaluate(formula, {p["name"]: 1.7 for p in params})
    except ZeroDivisionError:
        pass
    except (ValueError, SyntaxError, TypeError, OverflowError) as e:
        raise ValueError(f"The formula has a problem: {e}")
    return {"name": name, "description": description, "params": params,
            "formula": formula, "unit": (raw.get("unit") or "").strip()}


def add_spec(raw, taken_names, replace=False):
    """Save a new tool. With replace=True, an existing tool of the same name is updated."""
    specs = load_specs()
    name = (raw.get("name") or "").strip()
    if replace:
        specs = [s for s in specs if s.get("name") != name]
        taken_names = set(taken_names) - {name}
    spec = validate(raw, taken_names)
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
             "Inputs:"]
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


# ---------- Let the AI turn a plain description into a draft tool ----------

class _DraftInput(BaseModel):
    name: str
    description: str
    example: float


class _Draft(BaseModel):
    name: str
    description: str
    params: list[_DraftInput]
    formula: str
    unit: str


def draft_from_idea(idea, client, models):
    """Ask the AI to fill in the tool form from a description. Nothing is saved."""
    from google.genai import types

    prompt = f"""A teacher wants a calculator tool for a Computer Networks course.
Turn this idea into a formula tool:

{idea}

Rules:
- name: a short snake_case English name, for example queuing_delay.
- description: one or two English sentences saying what it calculates and when to use it.
- params: the inputs. Each has a short English name made of letters, digits or _
  (for example L, R, rtt, prefix), a description that includes the unit (for example
  "packet length in bits"), and a realistic example value in that unit.
- Use base units (bits, bits per second, seconds, meters) so the formula never has
  to convert units.
- formula: ONE expression that uses only the input names, numbers, + - * / ** // %
  and brackets, and these functions: sqrt, log2, log10, ln, exp, ceil, floor, abs,
  round, min, max. No other names, no variables, no assignments.
- unit: the unit of the result, for example "seconds".
- Always answer in English, even if the idea is written in Arabic."""

    config = types.GenerateContentConfig(response_mime_type="application/json",
                                         response_schema=_Draft)
    last_error = None
    for model in models:
        try:
            response = client.models.generate_content(model=model, contents=prompt,
                                                      config=config)
            parsed = response.parsed
            if parsed is None:
                parsed = _Draft.model_validate_json(response.text)
            draft = parsed.model_dump()
            break
        except Exception as e:
            last_error = e
            print(f"  (draft with {model} failed: {str(e)[:80]})")
    else:
        raise ValueError(f"The AI could not make a draft right now: {str(last_error)[:150]}")

    draft["name"] = re.sub(r"[^A-Za-z0-9_]", "_", draft["name"].strip())[:41]
    try:
        values = {p["name"]: p["example"] for p in draft["params"]}
        draft["example_result"] = evaluate(draft["formula"], values)
    except ZeroDivisionError:
        draft["warning"] = "The formula divides by zero with the example values."
    except (ValueError, SyntaxError, TypeError, OverflowError) as e:
        draft["warning"] = f"Check the formula, it has a problem: {e}"
    return draft
