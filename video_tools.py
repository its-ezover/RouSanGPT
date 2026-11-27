import re
import tempfile
import textwrap
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Literal

from google.genai import types
from PIL import Image, ImageDraw, ImageFilter, ImageFont
from pydantic import BaseModel

import animation_tools
import binaries
import diagram_tools
import explainers
import gemini_client
import tts
import visual_kit
from quiz import _course_excerpts   # finds course material (slides and books only)

client = gemini_client.LazyClient(timeout_ms=90000)   # uses the key from Settings or .env
MODELS = ["gemini-3.1-flash-lite", "gemini-3.8-flash"]
VOICES = ["en-US-AvaMultilingualNeural", "en-US-AriaNeural"]   # tried in this order
VOICE_RATE = "-5%"     # a little slower, like a teacher; try "-10%" for slower
W, H = 1280, 720


# ---------- 1. The script ----------

class Scene(BaseModel):
    title: str
    bullets: list[str]
    narration: str
    diagram_type: Literal[
        "none", "explainer", "anim_explainer", "sequence", "packet_header", "topology", "flowchart",
        "anim_message_exchange", "anim_packet_flow", "anim_sliding_window", "anim_dijkstra",
    ]
    explainer_kind: str                # "explainer" and "anim_explainer"
    explainer_inputs: list[str]        # "explainer" and "anim_explainer"
    sequence_participants: list[str]   # "sequence" and "anim_message_exchange"
    sequence_messages: list[str]       # "sequence" and "anim_message_exchange"
    header_fields: list[str]           # "packet_header"
    topology_dot: str                  # "topology" and "flowchart"
    flow_nodes: list[str]              # "anim_packet_flow"
    flow_packets: int                  # "anim_packet_flow"
    window_total: int                  # "anim_sliding_window"
    window_size: int                   # "anim_sliding_window"
    graph_edges: list[str]             # "anim_dijkstra"
    graph_source: str                  # "anim_dijkstra"


class Storyboard(BaseModel):
    video_title: str
    scenes: list[Scene]


def write_storyboard(topic, num_scenes):
    context = _course_excerpts(topic)
    prompt = f"""You write short educational video scripts for university students of
Computer Networks and of Cryptography and Network Security.
Topic: {topic}
Number of scenes: {num_scenes}

Use ONLY facts supported by these course excerpts:
{context}

Rules:
- The first scene is a friendly introduction, the last scene is a short summary.
- Each scene has: a title (at most 6 words), 2 to 4 bullet points (at most 8 words
  each), and a narration of 35 to 60 words.
- Write the narration the way a warm, enthusiastic teacher talks to a class, not
  the way a textbook is written:
  * short sentences, mostly under 15 words
  * use contractions (it's, we'll, that's) and talk to the student ("you", "let's")
  * add a simple everyday comparison where it helps
  * once in a while ask a question and then answer it
  * vary how sentences start; never start two sentences the same way
  * use commas and full stops to create natural pauses
- Do not just read the bullets aloud; explain them.
- No markdown, no symbols, no emojis, no bullet characters, no brackets.
- Spell out an acronym the first time it appears, for example "Transmission
  Control Protocol, or TCP".

Pictures: in the scenes where a picture explains better than bullets (about half
of the scenes, never the first or the last), choose a diagram_type. Prefer an
ANIMATION when movement is the point (use at most two animations per video). Use a
DIFFERENT picture in each scene: never the same type and kind twice in one video.
For a scene with a picture, the narration must refer to it ("look at...", "watch
how..."), and any numbers in the narration must be the ones of that picture's inputs.
Fill ONLY the fields of the type you choose; leave all other fields empty
([] or "" or 0).
- "explainer" (still picture) or "anim_explainer" (built step by step): the figures
  of the lecture slides, with every number calculated for you. explainer_kind is
  one of the kinds below; explainer_inputs are its inputs as text, or [] for the
  slides' own example. This is the BEST choice whenever a kind matches the topic,
  and the ONLY choice for calculations, algorithms with numbers and ciphers: never
  draw a calculation or a cipher as a "sequence" of messages.
{visual_kit.kinds_text()}
- "flowchart": the steps of an algorithm or the parts of a system as boxes and
  arrows (for example the Miller-Rabin TEST, the symmetric cipher model, a Feistel
  round). topology_dot is complete Graphviz DOT code: a digraph with at most 9 nodes,
  for example: digraph {{ rankdir=TB; node [shape=box]; A [label="n - 1 = 2^k q"]; B
  [label="a^q mod n = 1?" shape=diamond]; A -> B; }}
- "sequence" (still picture) or "anim_message_exchange" (arrows appear one by one):
  ONLY a real message exchange between parties, such as a handshake, DNS lookup or
  HTTP request.
  sequence_participants lists the parties from left to right, for example
  ["Client", "Server"]. sequence_messages lists at most 8 steps in time order, each
  written exactly as 'Sender -> Receiver: short label', for example
  'Client -> Server: SYN (seq=x)'. Names must come from sequence_participants.
- "packet_header": a protocol header (TCP, UDP or IP). header_fields lists the
  fields in order, each written as 'Field name:bits', for example 'Source port:16'.
  Use the real field sizes.
- "topology": a network layout. topology_dot is complete Graphviz DOT code with at
  most 8 nodes, for example: graph {{ rankdir=LR; PC1 -- Switch; Switch -- Router; }}
- "anim_packet_flow": packets travelling through routers with store-and-forward.
  flow_nodes lists the devices from source to destination, for example
  ["Source", "Router 1", "Router 2", "Destination"] (2 to 6). flow_packets is 1 to 6.
- "anim_sliding_window": a sliding window protocol. window_total is 3 to 12 and
  window_size is 1 to 6.
- "anim_dijkstra": Dijkstra's shortest path algorithm. graph_edges lists the links,
  each written as 'A-B:cost' (at most 8 nodes), and graph_source is the start node.
- "none": no picture (bullets are shown)."""
    for model in MODELS:
        try:
            response = client.models.generate_content(
                model=model,
                contents=prompt,
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    response_schema=Storyboard,
                ),
            )
            board = Storyboard.model_validate_json(response.text)
            if board.scenes:
                return board
        except Exception as e:
            print(f"  (video script: {model} failed: {str(e)[:70]})")
            time.sleep(2)
    return None


# ---------- 2. The voice ----------

def text_to_speech(text, out_path):
    tts.synthesize(text, out_path, VOICES, rate=VOICE_RATE)


def _audio_seconds(path):
    return binaries.media_seconds(path, default=10.0)


# ---------- 3. The pictures ----------

def make_scene_diagram(scene, number):
    """Draw the still diagram of a scene. Returns a PNG path, or None."""
    if scene.diagram_type == "none" or scene.diagram_type.startswith("anim_"):
        return None
    original = diagram_tools._open_image
    diagram_tools._open_image = lambda path: None     # do not pop up windows
    try:
        name = f"video_{int(time.time())}_{number}"
        if scene.diagram_type == "sequence" and scene.sequence_participants and scene.sequence_messages:
            result = diagram_tools.draw_sequence_diagram(
                scene.title, scene.sequence_participants, scene.sequence_messages, name)
        elif scene.diagram_type == "packet_header" and scene.header_fields:
            result = diagram_tools.draw_packet_header(scene.title, scene.header_fields, name)
        elif scene.diagram_type in ("topology", "flowchart") and scene.topology_dot.strip():
            result = diagram_tools.draw_topology(scene.topology_dot, name)
        elif scene.diagram_type == "explainer" and scene.explainer_kind.strip():
            result = explainers.draw_explainer(scene.explainer_kind, scene.explainer_inputs, name)
        else:
            return None
        if "error" in result:
            print(f"    (diagram skipped: {result['error'][:80]})")
            return None
        return result.get("saved_to")
    except Exception as e:
        print(f"    (diagram skipped: {str(e)[:80]})")
        return None
    finally:
        diagram_tools._open_image = original


def make_scene_animation(scene):
    """For an animated scene, returns (drawing_function, natural_length_in_seconds).
    Returns None if the scene is not animated or the animation could not be built."""
    kind = scene.diagram_type
    if not kind.startswith("anim_"):
        return None
    captured = []
    animation_tools._CAPTURE = captured
    try:
        if kind == "anim_message_exchange":
            result = animation_tools.animate_message_exchange(
                scene.title, scene.sequence_participants, scene.sequence_messages)
        elif kind == "anim_packet_flow":
            result = animation_tools.animate_packet_flow(
                scene.title, scene.flow_nodes, scene.flow_packets or 4)
        elif kind == "anim_sliding_window":
            result = animation_tools.animate_sliding_window(
                scene.window_total or 8, scene.window_size or 3)
        elif kind == "anim_dijkstra":
            result = animation_tools.animate_dijkstra(scene.graph_edges, scene.graph_source)
        elif kind == "anim_explainer":
            result = explainers.animate_explainer(scene.explainer_kind, scene.explainer_inputs)
        else:
            return None
        if "error" in result or not captured:
            print(f"    (animation skipped: {str(result.get('error', 'unknown'))[:80]})")
            return None
        return captured[0]
    except Exception as e:
        print(f"    (animation skipped: {str(e)[:80]})")
        return None
    finally:
        animation_tools._CAPTURE = None


def render_animation_clip(frame_fn, natural, narration_seconds, out_path):
    """Speed the animation up or down (0.5x to 2x) so it fits the narration."""
    target = narration_seconds + 0.5
    speed = max(0.5, min(2.0, natural / target))
    duration = max(target, natural / speed)
    animation_tools.render_video(lambda t: frame_fn(t * speed), duration, out_path)


def _glass(img, box, radius, fill=(255, 255, 255, 22), shadow=110):
    """A Frutiger Aero glass panel: a soft shadow, a see-through panel and a shine."""
    x0, y0, x1, y1 = box
    layer = Image.new("RGBA", img.size, (0, 0, 0, 0))
    ImageDraw.Draw(layer).rounded_rectangle([x0, y0 + 10, x1, y1 + 10], radius=radius, fill=(0, 10, 25, shadow))
    out = img.convert("RGBA")
    out.alpha_composite(layer.filter(ImageFilter.GaussianBlur(14)))
    panel = Image.new("RGBA", img.size, (0, 0, 0, 0))
    ImageDraw.Draw(panel).rounded_rectangle(box, radius=radius, fill=fill, outline=(160, 220, 255, 70), width=2)
    out.alpha_composite(panel)
    # the shine goes on its own layer: drawing it on the panel would replace the panel's pixels
    shine = Image.new("RGBA", img.size, (0, 0, 0, 0))
    ImageDraw.Draw(shine).rounded_rectangle([x0 + 2, y0 + 2, x1 - 2, y0 + (y1 - y0) * 0.42], radius=radius,
                                            fill=(255, 255, 255, 16), corners=(True, True, False, False))
    out.alpha_composite(shine)
    return out.convert("RGB")


def draw_slide(title, bullets, number, total, out_path, diagram_png=None):
    img = animation_tools.aero_background().copy()
    if diagram_png:
        img = _glass(img, [80, 190, 1200, 655], 18, fill=(255, 255, 255, 255), shadow=140)
    elif bullets:
        img = _glass(img, [60, 215, 1220, 640], 24)
    d = ImageDraw.Draw(img)
    regular = animation_tools.font_path()
    bold = animation_tools.font_path(bold=True)
    f_title = ImageFont.truetype(bold, 46 if diagram_png else 54)
    f_body = ImageFont.truetype(regular, 36)
    f_small = ImageFont.truetype(regular, 22)

    d.rectangle([0, 0, W, 12], fill="#3fb2f5")
    d.rectangle([0, 0, W, 4], fill="#bdeaff")
    y = 60 if diagram_png else 70
    for line in textwrap.wrap(title, width=34 if diagram_png else 30)[:2]:
        d.text((82, y + 3), line, font=f_title, fill="#021627")      # a soft shadow
        d.text((80, y), line, font=f_title, fill="white")
        y += 58 if diagram_png else 66

    if diagram_png:
        # the diagram on the white glass card drawn above
        pic = Image.open(diagram_png).convert("RGB")
        scale = min(1090 / pic.width, 435 / pic.height, 1.5)
        pic = pic.resize((max(1, int(pic.width * scale)), max(1, int(pic.height * scale))),
                         Image.Resampling.LANCZOS)
        img.paste(pic, (80 + (1120 - pic.width) // 2, 190 + (465 - pic.height) // 2))
    else:
        y = max(y + 30, 245)
        for bullet in bullets[:5]:
            # a glossy orb
            d.ellipse([96, y + 11, 116, y + 31], fill="#1b93de", outline="#0b6db3")
            d.ellipse([100, y + 13, 112, y + 21], fill="#9fe2ff")
            for line in textwrap.wrap(bullet, width=46)[:2]:
                d.text((135, y), line, font=f_body, fill="#e7f5ff")
                y += 48
            y += 18

    d.text((80, H - 50), "RouSanGPT", font=f_small, fill="#94a3b8")
    d.text((W - 150, H - 50), f"{number} / {total}", font=f_small, fill="#94a3b8")
    img.save(out_path)


# ---------- 4. Putting it together ----------

def _ffmpeg(args):
    binaries.run_ffmpeg(args)


def _open_file(path):
    binaries.open_file(path)


SCENE_WORKERS = 3          # scenes made at the same time


def _make_clip(i, scene, animation, diagram_png, total, tmp):
    """The narrated clip of one scene. Returns its path."""
    clip, mp3 = tmp / f"s{i}.mp4", tmp / f"s{i}.mp3"
    text_to_speech(scene.narration, mp3)
    if animation:
        frame_fn, natural = animation
        silent = tmp / f"a{i}.mp4"
        render_animation_clip(frame_fn, natural, _audio_seconds(mp3), silent)
        _ffmpeg([
            "-i", str(silent), "-i", str(mp3),
            "-af", "apad",                  # silence after the narration
            "-c:v", "copy", "-c:a", "aac", "-ar", "44100", "-ac", "2",
            "-shortest", str(clip),
        ])
    else:
        png = tmp / f"s{i}.png"
        draw_slide(scene.title, scene.bullets, i, total, png, diagram_png)
        _ffmpeg([
            "-loop", "1", "-framerate", "30", "-i", str(png), "-i", str(mp3),
            "-af", "apad=pad_dur=0.6",      # a short pause after speaking
            "-c:v", "libx264", "-tune", "stillimage", "-pix_fmt", "yuv420p",
            "-c:a", "aac", "-ar", "44100", "-ac", "2",
            "-shortest", str(clip),
        ])
    return clip


def create_video(topic: str, num_scenes: int = 5) -> dict:
    """Create a short narrated educational video (an MP4 file) about a Computer
    Networks or Cryptography topic, based on the course materials. Scenes can be
    bullet slides, the slides' figures with calculated numbers (step tables, timing
    diagrams, charts, cipher pictures, still or built step by step), flowcharts,
    message exchanges, packet headers, network layouts or animations, with a spoken
    explanation in English. topic: for example 'TCP three-way handshake', 'Go-Back-N',
    'the Miller-Rabin test' or 'the Playfair cipher'. num_scenes: from
    3 to 8 (default 5). It takes two to four minutes. The video is saved in the
    'videos' folder and opened for the student."""
    num_scenes = max(3, min(int(num_scenes), 8))
    print("  (writing the video script...)", flush=True)
    board = write_storyboard(topic, num_scenes)
    if board is None:
        return {"error": "Could not write the video script right now. Please try again."}
    scenes = board.scenes[:num_scenes]

    Path("videos").mkdir(exist_ok=True)
    safe = re.sub(r"[^A-Za-z0-9]+", "_", board.video_title).strip("_")[:40] or "video"
    out_file = Path("videos") / f"{safe}_{int(time.time())}.mp4"

    try:
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            # 1. pictures and animations, one scene after the other (the drawing tools
            #    are switched into "capture" mode for this, which is not thread-safe)
            plans = []
            for i, scene in enumerate(scenes, start=1):
                animation = make_scene_animation(scene)
                diagram_png = None if animation else make_scene_diagram(scene, i)
                kind = scene.diagram_type if (animation or diagram_png) else "bullets"
                print(f"  (scene {i}/{len(scenes)}: {scene.title} [{kind}])", flush=True)
                plans.append((i, scene, animation, diagram_png))
            # 2. voice and video of several scenes at the same time: they mostly wait
            #    for the voice service and for FFmpeg. Same clips, in the same order.
            with ThreadPoolExecutor(max_workers=SCENE_WORKERS) as pool:
                clips = list(pool.map(lambda plan: _make_clip(*plan, len(scenes), tmp), plans))

            print("  (joining the scenes...)", flush=True)
            list_file = tmp / "list.txt"
            # names only: the clips are next to the list (Windows paths would need escaping)
            list_file.write_text("".join(f"file '{Path(c).name}'\n" for c in clips), encoding="utf-8")
            _ffmpeg(["-f", "concat", "-safe", "0", "-i", str(list_file),
                     "-c:v", "libx264", "-pix_fmt", "yuv420p",
                     "-c:a", "aac", "-ar", "44100", "-ac", "2", str(out_file)])
    except Exception as e:
        return {"error": f"The video could not be made: {e}"}

    # keep the script next to the video (useful for the report)
    out_file.with_suffix(".json").write_text(board.model_dump_json(indent=2), encoding="utf-8")
    _open_file(out_file)
    return {
        "saved_to": str(out_file),
        "video_title": board.video_title,
        "scenes": [s.title for s in scenes],
        "message": "Video created and opened for the student.",
    }


# The list we give to the AI
VIDEO_TOOLS = [create_video]


# Quick self-test: run `python video_tools.py`
if __name__ == "__main__":
    print(create_video("Store-and-forward packet switching and sliding windows", 5))