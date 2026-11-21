import os
import re
import subprocess
import sys
import tempfile
import textwrap
import time
from pathlib import Path
from typing import Literal

from dotenv import load_dotenv
from google import genai
from google.genai import types
from matplotlib import font_manager
from PIL import Image, ImageDraw, ImageFont
from pydantic import BaseModel

import animation_tools
import diagram_tools
from quiz import _course_excerpts   # finds course material (slides and books only)

load_dotenv()

client = genai.Client(
    api_key=os.getenv("GEMINI_API_KEY"),
    http_options=types.HttpOptions(
        timeout=90000,
        retry_options=types.HttpRetryOptions(attempts=1),
    ),
)
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
        "none", "sequence", "packet_header", "topology",
        "anim_message_exchange", "anim_packet_flow", "anim_sliding_window", "anim_dijkstra",
    ]
    sequence_participants: list[str]   # "sequence" and "anim_message_exchange"
    sequence_messages: list[str]       # "sequence" and "anim_message_exchange"
    header_fields: list[str]           # "packet_header"
    topology_dot: str                  # "topology"
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
    prompt = f"""You write short educational video scripts for Computer Networks students.
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
ANIMATION when movement is the point (use at most two animations per video). For a
scene with a picture, the narration must refer to it ("look at...", "watch how...").
Fill ONLY the fields of the type you choose; leave all other fields empty
([] or "" or 0).
- "sequence" (still picture) or "anim_message_exchange" (arrows appear one by one):
  a message exchange such as a handshake, DNS lookup or HTTP request.
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
    last_error = ""
    for voice in VOICES:
        result = subprocess.run(
            [sys.executable, "-m", "edge_tts", "--voice", voice,
             f"--rate={VOICE_RATE}", f"--text={text}", "--write-media", str(out_path)],
            capture_output=True, text=True, timeout=90,
        )
        if result.returncode == 0 and Path(out_path).exists():
            return
        last_error = result.stderr[-200:]
    raise RuntimeError("Text-to-speech failed (is the internet working?): " + last_error)


def _audio_seconds(path):
    result = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "default=noprint_wrappers=1:nokey=1", str(path)],
        capture_output=True, text=True,
    )
    try:
        return float(result.stdout.strip())
    except ValueError:
        return 10.0


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
        elif scene.diagram_type == "topology" and scene.topology_dot.strip():
            result = diagram_tools.draw_topology(scene.topology_dot, name)
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


def draw_slide(title, bullets, number, total, out_path, diagram_png=None):
    img = Image.new("RGB", (W, H), "#0f172a")
    d = ImageDraw.Draw(img)
    regular = font_manager.findfont("DejaVu Sans")
    bold = font_manager.findfont(font_manager.FontProperties(family="DejaVu Sans", weight="bold"))
    f_title = ImageFont.truetype(bold, 46 if diagram_png else 54)
    f_body = ImageFont.truetype(regular, 36)
    f_small = ImageFont.truetype(regular, 22)

    d.rectangle([0, 0, W, 12], fill="#38bdf8")
    y = 60 if diagram_png else 70
    for line in textwrap.wrap(title, width=34 if diagram_png else 30)[:2]:
        d.text((80, y), line, font=f_title, fill="white")
        y += 58 if diagram_png else 66

    if diagram_png:
        # a big white card with the diagram inside
        d.rounded_rectangle([80, 190, 1200, 655], radius=18, fill="white")
        pic = Image.open(diagram_png).convert("RGB")
        scale = min(1090 / pic.width, 435 / pic.height, 1.5)
        pic = pic.resize((max(1, int(pic.width * scale)), max(1, int(pic.height * scale))),
                         Image.Resampling.LANCZOS)
        img.paste(pic, (80 + (1120 - pic.width) // 2, 190 + (465 - pic.height) // 2))
    else:
        y += 30
        for bullet in bullets[:5]:
            d.ellipse([80, y + 14, 94, y + 28], fill="#38bdf8")
            for line in textwrap.wrap(bullet, width=46)[:2]:
                d.text((115, y), line, font=f_body, fill="#e2e8f0")
                y += 48
            y += 18

    d.text((80, H - 50), "Net.ai - Computer Networks", font=f_small, fill="#94a3b8")
    d.text((W - 150, H - 50), f"{number} / {total}", font=f_small, fill="#94a3b8")
    img.save(out_path)


# ---------- 4. Putting it together ----------

def _ffmpeg(args):
    result = subprocess.run(["ffmpeg", "-y", "-loglevel", "error"] + args,
                            capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError("ffmpeg failed: " + result.stderr[-300:])


def _open_file(path):
    try:
        subprocess.Popen(["xdg-open", str(path)],
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except FileNotFoundError:
        pass


def create_video(topic: str, num_scenes: int = 5) -> dict:
    """Create a short narrated educational video (an MP4 file) about a Computer
    Networks topic, based on the course materials. Scenes can be bullet slides,
    diagrams (message exchanges, packet headers, network layouts) or animations
    (message exchange, packets travelling through routers, a sliding window,
    Dijkstra's algorithm), with a spoken explanation in English. topic: for example
    'TCP three-way handshake' or 'how Dijkstra's algorithm works'. num_scenes: from
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
            clips = []
            for i, scene in enumerate(scenes, start=1):
                clip, mp3 = tmp / f"s{i}.mp4", tmp / f"s{i}.mp3"
                animation = make_scene_animation(scene)
                diagram_png = None if animation else make_scene_diagram(scene, i)
                if animation:
                    kind = scene.diagram_type
                elif diagram_png:
                    kind = scene.diagram_type
                else:
                    kind = "bullets"
                print(f"  (scene {i}/{len(scenes)}: {scene.title} [{kind}])", flush=True)

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
                    draw_slide(scene.title, scene.bullets, i, len(scenes), png, diagram_png)
                    _ffmpeg([
                        "-loop", "1", "-framerate", "30", "-i", str(png), "-i", str(mp3),
                        "-af", "apad=pad_dur=0.6",      # a short pause after speaking
                        "-c:v", "libx264", "-tune", "stillimage", "-pix_fmt", "yuv420p",
                        "-c:a", "aac", "-ar", "44100", "-ac", "2",
                        "-shortest", str(clip),
                    ])
                clips.append(clip)

            print("  (joining the scenes...)", flush=True)
            list_file = tmp / "list.txt"
            list_file.write_text("".join(f"file '{c}'\n" for c in clips))
            _ffmpeg(["-f", "concat", "-safe", "0", "-i", str(list_file),
                     "-c:v", "libx264", "-pix_fmt", "yuv420p",
                     "-c:a", "aac", "-ar", "44100", "-ac", "2", str(out_file)])
    except Exception as e:
        return {"error": f"The video could not be made: {e}"}

    # keep the script next to the video (useful for the report)
    out_file.with_suffix(".json").write_text(board.model_dump_json(indent=2))
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