"""Redrawing the pictures, animations and videos in the chosen look (Settings > Look).

Each picture or animation the tutor makes gets a small recipe next to it: the tool
and its inputs (diagrams/name.recipe.json). Redrawing runs the recipes again, and
remakes the videos from the scripts kept next to them (videos/name.json), so the
chats show them in the new look (same file names). Pictures made before recipes
existed cannot be redrawn; they are counted and reported.
"""
import functools
import inspect
import json
import threading
from pathlib import Path

SUFFIX = ".recipe.json"
FOLDERS = ("diagrams", "animations")
MEDIA = (".png", ".mp4")
state = {"running": False, "done": 0, "total": 0, "current": "", "redrawn": 0, "failed": [], "older": 0}
_lock = threading.Lock()


def recipe_path(media_path):
    p = Path(media_path)
    return p.with_name(p.stem + SUFFIX)


def remember(func):
    """Wrap a drawing tool: when it makes a file, keep its recipe next to the file."""
    signature = inspect.signature(func)

    @functools.wraps(func)
    def tool(*args, **kwargs):
        result = func(*args, **kwargs)
        try:
            saved = result.get("saved_to") if isinstance(result, dict) else None
            if saved and not Path(saved).name.startswith("video_"):
                bound = signature.bind(*args, **kwargs)
                bound.apply_defaults()
                recipe_path(saved).write_text(json.dumps({"tool": func.__name__, "args": bound.arguments},
                                                         ensure_ascii=False, default=str), encoding="utf-8")
        except Exception as e:                       # a recipe is a bonus: never break the tool
            print(f"  (no recipe for {func.__name__}: {e})")
        return result
    return tool


def _tools():
    import animation_tools
    import diagram_tools
    import explainers
    return {f.__name__: f for f in [explainers.draw_explainer, explainers.animate_explainer,
                                    diagram_tools.draw_topology, diagram_tools.draw_sequence_diagram,
                                    diagram_tools.draw_packet_header, animation_tools.animate_message_exchange,
                                    animation_tools.animate_packet_flow, animation_tools.animate_sliding_window,
                                    animation_tools.animate_dijkstra]}


def plan():
    """What can be redrawn: [(kind, path)], and how many older pictures cannot."""
    jobs, older = [], 0
    for folder in FOLDERS:
        for f in sorted(Path(folder).glob("*")):
            if f.suffix.lower() not in MEDIA or f.name.startswith("video_"):
                continue
            if recipe_path(f).exists():
                jobs.append(("recipe", recipe_path(f)))
            else:
                older += 1
    for script in sorted(Path("videos").glob("*.json")):
        if script.with_suffix(".mp4").exists():
            jobs.append(("video", script))
    return jobs, older


def _run(jobs, older):
    import animation_tools
    import video_tools
    tools = _tools()
    for kind, path in jobs:
        state["current"] = str(path.with_suffix(".mp4") if kind == "video" else path).replace(SUFFIX, "")
        try:
            if kind == "video":
                result = video_tools.redraw_video(path)
            else:
                recipe = json.loads(path.read_text(encoding="utf-8"))
                with animation_tools.RENDER_LOCK:        # never while a video borrows the tools
                    result = tools[recipe["tool"]](**recipe["args"])
            if isinstance(result, dict) and result.get("error"):
                raise RuntimeError(result["error"])
            state["redrawn"] += 1
        except Exception as e:
            state["failed"].append(f"{state['current']}: {str(e)[:120]}")
        state["done"] += 1
    state["running"] = False
    state["current"] = ""


def start():
    """Start redrawing in the background. Returns the state (or None if already running)."""
    with _lock:
        if state["running"]:
            return None
        jobs, older = plan()
        state.update(running=True, done=0, total=len(jobs), current="", redrawn=0, failed=[], older=older)
        threading.Thread(target=_run, args=(jobs, older), daemon=True).start()
        return dict(state)
