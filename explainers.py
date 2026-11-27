"""The two explainer tools the AI uses for course pictures and animations.

The kinds come from crypto_visuals.py and net_visuals.py (see visual_kit.py). Two
tools for all of them keep the request to the AI small; their descriptions list
every kind with the inputs it needs.
"""
import crypto_visuals  # noqa: F401  (registers the cryptography kinds)
import net_visuals  # noqa: F401  (registers the networking kinds)
import visual_kit as vk


def _run(kind, inputs, name, save):
    try:
        visual = vk.build(kind, inputs)
    except (ValueError, ZeroDivisionError, OverflowError) as e:
        return {"error": str(e)}
    return save(visual, name or str(kind))


def draw_explainer(kind: str, inputs: list[str], name: str = "") -> dict:
    return _run(kind, inputs, name, vk.save_still)


def animate_explainer(kind: str, inputs: list[str], name: str = "") -> dict:
    return _run(kind, inputs, name, vk.save_animation)


_COMMON = """
kind: one of the kinds below. inputs: text values, written exactly (numbers as
text). Give [] to show the lecture slides' own example for that kind. name: a short
file name without spaces (optional). Every number and letter in the picture is
calculated by the course tools, so it is always right; the result also says what it
shows, to explain it to the student step by step.

Computer Networks kinds:
{net}

Cryptography kinds:
{crypto}"""

draw_explainer.__doc__ = (
    "Draw a course picture in the style of the lecture slides: step tables, timing\n"
    "diagrams, charts, cipher pictures and bit-level pictures, for Computer Networks and\n"
    "Cryptography. Use it whenever a picture helps explain a calculation, an algorithm,\n"
    "a protocol in action or a cipher (and for cryptography, instead of a\n"
    "message-sequence diagram)." + _COMMON.format(net=vk.kinds_text("networks"), crypto=vk.kinds_text("crypto")))

animate_explainer.__doc__ = (
    "Make an ANIMATION (a short silent video) of a course picture: the same kinds as\n"
    "draw_explainer, built step by step (table rows one by one, packets moving, letters\n"
    "encrypted one at a time, a chart growing). Use it when the student wants to SEE\n"
    "the process happen." + _COMMON.format(net=vk.kinds_text("networks"), crypto=vk.kinds_text("crypto")))

EXPLAINER_TOOLS = [draw_explainer, animate_explainer]
