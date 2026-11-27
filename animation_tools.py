import math
import re
import subprocess
import tempfile
from functools import lru_cache
from pathlib import Path

from PIL import ImageDraw, ImageFont

import binaries
import device_icons
import looks
from more_tools import _read_edge, dijkstra_shortest_paths

W, H, FPS = 1280, 720, 30
BG = "#0f172a"
PALETTE = ["#38bdf8", "#a78bfa", "#f472b6", "#fb923c", "#facc15", "#4ade80"]
_CAPTURE = None   # video_tools uses this to borrow the drawing code

# ---------- Drawing helpers ----------

@lru_cache(maxsize=None)
def font_path(bold=False):
    """DejaVu Sans, which comes with matplotlib. Imported here, not at the top:
    the first import builds a font list, which would slow down every app start."""
    from matplotlib import font_manager
    if bold:
        return font_manager.findfont(font_manager.FontProperties(family="DejaVu Sans", weight="bold"))
    return font_manager.findfont("DejaVu Sans")


@lru_cache(maxsize=None)
def font(size, bold=False):
    return ImageFont.truetype(font_path(bold), size)


@lru_cache(maxsize=None)
def mono_font(size, bold=False):
    """DejaVu Sans Mono (comes with matplotlib), for the Cybercore look."""
    from matplotlib import font_manager
    path = font_manager.findfont(font_manager.FontProperties(family="DejaVu Sans Mono",
                                                             weight="bold" if bold else "normal"))
    return ImageFont.truetype(path, size)


def ease(x):
    """Smooth start and stop: turns 0..1 into a gentle curve."""
    x = max(0.0, min(1.0, x))
    return x * x * (3 - 2 * x)


# ---------- the look (Settings > Look, see looks.py) ----------

def aero_background(light=False):
    return looks.background("aero", light)


def gloss_rect(d, xy, radius, fill, outline=None, width=1, light=False):
    """A box in the chosen look's style (flat, glossy, neon or candy)."""
    looks.box(d, xy, radius, fill, outline, width, light)


def frame_title(d, title, light=False):
    looks.title(d, title, None, light)


def new_frame(title):
    """A frame in the chosen look: its background, top bar and title."""
    look = looks.current()
    img = looks.background(look, False).copy()
    d = ImageDraw.Draw(img)
    looks.title(d, title, look, False)
    return img, d


def render_video(frame_fn, duration, out_path):
    """Draw every frame with frame_fn(time_in_seconds) and hand it straight to FFmpeg,
    which makes the MP4 while the next frames are drawn (no picture files in between)."""
    total = int(duration * FPS)
    cmd = [binaries.require_tool("ffmpeg"), "-y", "-loglevel", "error",
           "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-framerate", str(FPS),
           "-i", "-", "-c:v", "libx264", "-pix_fmt", "yuv420p", str(out_path)]
    with tempfile.TemporaryFile() as errors:          # a file, so FFmpeg can never block on it
        proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.DEVNULL,
                                stderr=errors, **binaries.NO_WINDOW)
        try:
            for i in range(total):
                if i % 90 == 0:
                    print(f"  (drawing frames {i}/{total}...)", flush=True)
                frame = frame_fn(i / FPS)
                if frame.mode != "RGB":
                    frame = frame.convert("RGB")
                if frame.size != (W, H):
                    raise ValueError(f"a frame is {frame.size[0]}x{frame.size[1]}, not {W}x{H}")
                proc.stdin.write(frame.tobytes())
            proc.stdin.close()
        except BrokenPipeError:
            pass                                       # FFmpeg stopped: its message is below
        except BaseException:
            proc.kill()
            proc.wait()
            raise
        if proc.wait() != 0:
            errors.seek(0)
            raise RuntimeError("ffmpeg failed: " + errors.read().decode(errors="replace")[-300:])


def _clean_name(name):
    return re.sub(r"[^A-Za-z0-9_-]+", "", name) or "animation"


def _open_file(path):
    binaries.open_file(path)


def _finish(name, frame_fn, duration):
    if _CAPTURE is not None:      # video_tools only wants the drawing function
        _CAPTURE.append((frame_fn, duration))
        return {"captured": True}
    Path("animations").mkdir(exist_ok=True)
    out = Path("animations") / f"{_clean_name(name)}.mp4"
    try:
        render_video(frame_fn, duration, out)
    except Exception as e:
        return {"error": f"Could not make the animation: {e}"}
    _open_file(out)
    return {"saved_to": str(out), "duration_seconds": round(duration, 1),
            "message": "Animation created and opened for the student."}

# ---------- 1. Message exchange ----------

def animate_message_exchange(title: str, participants: list[str],
                             messages: list[str], name: str = "message_exchange") -> dict:
    """Make an ANIMATED video of a message exchange, for example a TCP three-way
    handshake, a DNS lookup, an HTTP request, DHCP or ARP. The arrows appear one by
    one between the parties. title: the animation title. participants: the parties
    from left to right, for example ["Client", "Server"]. messages: at most 8 steps
    in time order, each written exactly as 'Sender -> Receiver: label', for example
    'Client -> Server: SYN (seq=x)'. name: short file name without spaces. The silent
    video is saved and opened for the student. If the result contains an 'error',
    fix the input and call this tool again."""
    if not 2 <= len(participants) <= 5 or not 1 <= len(messages) <= 8:
        return {"error": "Use 2 to 5 participants and 1 to 8 messages."}
    index = {p: i for i, p in enumerate(participants)}
    steps = []
    for msg in messages:
        try:
            route, label = msg.split(":", 1)
            sender, receiver = [s.strip() for s in route.split("->")]
            steps.append((index[sender], index[receiver], label.strip()))
        except (ValueError, KeyError):
            return {"error": f"Bad message format: '{msg}'. Use 'Sender -> Receiver: label' "
                             f"with names taken from {participants}."}

    per_msg = 1.6
    n = len(participants)
    xs = [int(180 + i * (W - 360) / (n - 1)) for i in range(n)]
    top, bottom = 250, H - 50
    step_h = min(90, (bottom - top - 20) / len(steps))

    def frame(t):
        img, d = new_frame(title)
        c = looks.anim()
        for pname, x in zip(participants, xs):
            device_icons.device(d, pname, x, 150, 64, "dark", c["text"], 22)
            d.line([(x, 210), (x, bottom)], fill=c["line"], width=3)
        for k, (s, r, label) in enumerate(steps):
            start = 0.6 + k * per_msg
            if t < start:
                break
            p = min(1.0, (t - start) / (per_msg * 0.6))
            y = int(top + 30 + k * step_h)
            x1, x2 = xs[s], xs[r]
            xe = x1 + (x2 - x1) * ease(p)
            color = c["packets"][k % len(c["packets"])]
            d.line([(x1, y), (xe, y)], fill=color, width=5)
            direction = 1 if x2 >= x1 else -1
            d.polygon([(xe, y), (xe - direction * 18, y - 10), (xe - direction * 18, y + 10)],
                      fill=color)
            if p > 0.25:
                d.text(((x1 + x2) / 2, y - 12), f"{k + 1}. {label}",
                       font=font(24), fill=c["text"], anchor="ms")
        return img

    return _finish(name, frame, 0.6 + len(steps) * per_msg + 1.5)


# ---------- 2. Packet flow (store-and-forward) ----------

def animate_packet_flow(title: str, nodes: list[str], num_packets: int = 4,
                        name: str = "packet_flow") -> dict:
    """Make an ANIMATED video of packets travelling from a source through routers to
    a destination with store-and-forward, so the student sees pipelining. title: the
    animation title. nodes: the devices in order from source to destination, for
    example ["Source", "Router 1", "Router 2", "Destination"] (2 to 6 nodes).
    num_packets: from 1 to 6. name: short file name without spaces. The silent video
    is saved and opened for the student."""
    n = len(nodes)
    num_packets = max(1, min(int(num_packets), 6))
    if not 2 <= n <= 6:
        return {"error": "Use 2 to 6 nodes."}
    xs = [int(150 + i * (W - 300) / (n - 1)) for i in range(n)]
    y = 360
    hop_time, pause, gap = 1.4, 0.3, 0.7
    seg = hop_time + pause

    def frame(t):
        img, d = new_frame(title)
        c = looks.anim()
        for i in range(n - 1):
            d.line([(xs[i], y), (xs[i + 1], y)], fill=c["line"], width=6)
        delivered = 0
        for p in range(num_packets):
            elapsed = t - (0.6 + p * gap)
            if elapsed < 0:
                continue
            hop = int(elapsed // seg)
            if hop >= n - 1:
                delivered += 1
                continue
            frac = min(1.0, (elapsed - hop * seg) / hop_time)
            x = xs[hop] + (xs[hop + 1] - xs[hop]) * frac
            gloss_rect(d, [x - 24, y - 20, x + 24, y + 20], 6, c["packets"][p % len(c["packets"])])
            d.text((x, y), str(p + 1), font=font(22, True), fill=c["bg"], anchor="mm")
        for node, x in zip(nodes, xs):      # drawn last, so packets "enter" the devices
            device_icons.device(d, node, x, y, 104, "dark", c["text"], 24)
        d.text((W // 2, 560), f"Packets delivered: {delivered} / {num_packets}",
               font=font(32, True), fill=c["good"], anchor="mm")
        d.text((W // 2, 620), "Each router receives the whole packet before forwarding it",
               font=font(22), fill=c["muted"], anchor="mm")
        return img

    return _finish(name, frame, 0.6 + (num_packets - 1) * gap + (n - 1) * seg + 1.5)


# ---------- 3. Sliding window ----------

def animate_sliding_window(total_packets: int = 10, window_size: int = 4,
                           name: str = "sliding_window") -> dict:
    """Make an ANIMATED video of a sliding window protocol: the sender transmits
    packets inside the window and the window slides forward as acknowledgements
    arrive. total_packets: from 3 to 12. window_size: from 1 to 6 (1 means
    stop-and-wait). name: short file name without spaces. The silent video is saved
    and opened for the student."""
    total = max(3, min(int(total_packets), 12))
    win = max(1, min(int(window_size), 6, total))
    round_len = 1.2
    box_w, gap = 70, 18
    start_x = (W - (total * box_w + (total - 1) * gap)) // 2
    y = 320

    def frame(t):
        img, d = new_frame(f"Sliding window (window size = {win})")
        c = looks.anim()
        r_float = max(0.0, (t - 0.8) / round_len)
        r = int(r_float)
        frac = r_float - r
        if r >= total:
            acked, left = total, float(total)
        else:
            acked = r + (1 if frac >= 0.5 else 0)
            left = r + (ease((frac - 0.5) / 0.5) if frac >= 0.5 else 0.0)
        sent = min(acked + win, total)

        for i in range(total):
            x = start_x + i * (box_w + gap)
            if i < acked:
                color = c["good"]          # acknowledged
            elif i < sent:
                color = c["waiting"]       # sent, waiting for the ACK
            else:
                color = c["line"]          # not sent yet
            gloss_rect(d, [x, y, x + box_w, y + box_w], 8, color)
            d.text((x + box_w / 2, y + box_w / 2), str(i), font=font(26, True),
                   fill=c["bg"], anchor="mm")
        wx = start_x + left * (box_w + gap) - 8
        ww = win * (box_w + gap) - gap + 16
        d.rounded_rectangle([wx, y - 14, wx + ww, y + box_w + 14], radius=12,
                            outline=c["accent"], width=5)
        d.text((wx + ww / 2, y - 26), "window", font=font(24, True), fill=c["accent"], anchor="ms")
        d.text((W // 2, 500), f"base = {acked}      next packet to send = {sent}",
               font=font(30, True), fill="white", anchor="mm")
        for k, (color, label) in enumerate([(c["good"], "acknowledged"),
                                            (c["waiting"], "sent, waiting for ACK"),
                                            (c["line"], "not sent yet")]):
            lx = 220 + k * 340
            gloss_rect(d, [lx, 590, lx + 28, 618], 5, color)
            d.text((lx + 42, 604), label, font=font(24), fill=c["text"], anchor="lm")
        return img

    return _finish(name, frame, 0.8 + total * round_len + 1.5)


# ---------- 4. Dijkstra ----------

def animate_dijkstra(edges: list[str], source: str, name: str = "dijkstra") -> dict:
    """Make an ANIMATED video of Dijkstra's shortest-path algorithm on a network
    graph. Each step finalises the closest node, updates the distances of its
    neighbours, and in the end the shortest-path tree is highlighted. edges: the
    links, each written as 'A-B:cost', for example ['A-B:2', 'A-C:5', 'B-C:1']
    (at most 8 nodes). source: the starting node. name: short file name without
    spaces. The silent video is saved and opened for the student."""
    result = dijkstra_shortest_paths(edges, source)
    if "error" in result:
        return result
    nodes = list(result["shortest_distances"].keys())
    if len(nodes) > 8:
        return {"error": "Use at most 8 nodes."}
    steps = result["steps"]
    source = source.strip()

    links = []
    for e in edges:                      # the same reader as the tool ('R-1->R-2:3' works too)
        a, b, cost = _read_edge(e)
        links.append((a, b, str(int(cost)) if cost.is_integer() else f"{cost:g}"))
    tree = set()
    for path in result["shortest_paths"].values():
        if path != "unreachable":
            parts = path.split(" -> ")
            tree.update(frozenset((u, v)) for u, v in zip(parts, parts[1:]))

    cx, cy, rad = W // 2, 428, 182
    pos = {}
    for i, node in enumerate(nodes):
        angle = 2 * math.pi * i / len(nodes) - math.pi / 2
        pos[node] = (cx + rad * math.cos(angle), cy + rad * math.sin(angle))
    step_len = 2.2

    def frame(t):
        img, d = new_frame("Dijkstra's shortest path algorithm")
        c = looks.anim()
        k = min(int((t - 0.8) // step_len), len(steps) - 1) if t >= 0.8 else -1
        if k < 0:
            dist = {n: (0 if n == source else "infinity") for n in nodes}
            done, current = [], None
            caption = f"Start: the source node is {source}, its distance is 0"
        else:
            dist = steps[k]["distances"]
            done = [s["node_finalised"] for s in steps[:k + 1]]
            current = steps[k]["node_finalised"]
            caption = (f"Step {k + 1}: finalise {current} (shortest distance {dist[current]}), "
                       f"then update its neighbours")
        d.text((80, 115), caption, font=font(26), fill=c["caption"])

        for a, b, w in links:
            (x1, y1), (x2, y2) = pos[a], pos[b]
            in_tree = frozenset((a, b)) in tree and a in done and b in done
            d.line([(x1, y1), (x2, y2)], fill=c["good"] if in_tree else c["line"],
                   width=9 if in_tree else 4)
        for a, b, w in links:
            (x1, y1), (x2, y2) = pos[a], pos[b]
            mx, my = (x1 + x2) / 2, (y1 + y2) / 2
            d.ellipse([mx - 19, my - 19, mx + 19, my + 19], fill=c["bg"])
            d.text((mx, my), w, font=font(22, True), fill=c["text"], anchor="mm")
        for node in nodes:
            x, y = pos[node]
            if node == current:
                fill, outline = c["warn"], c["warn"]
            elif node in done:
                fill, outline = c["good"], c["good"]
            else:
                fill, outline = c["node"], c["accent"]
            # a router in a ring: orange = being finalised, green = finalised, blue = not yet
            d.ellipse([x - 46, y - 46, x + 46, y + 46], fill=c["bg"], outline=outline, width=5)
            device_icons.paste_icon(d, "router", x, y - 8, 58, "dark")
            d.text((x, y + 30), node, font=font(20, True), fill=outline if fill != c["node"] else c["text"],
                   anchor="mm")
            ox, oy = (x - cx) / rad, (y - cy) / rad
            value = dist[node]
            label = "d = ∞" if value == "infinity" else f"d = {value}"
            d.text((x + ox * 76, y + oy * 76), label, font=font(22, True),
                   fill=c["text"], anchor="mm")
        return img

    return _finish(name, frame, 0.8 + len(steps) * step_len + 2.0)


# The list we give to the AI
ANIMATION_TOOLS = [animate_message_exchange, animate_packet_flow,
                   animate_sliding_window, animate_dijkstra]


# Quick self-test: run `python animation_tools.py`
if __name__ == "__main__":
    print(animate_message_exchange(
        "TCP three-way handshake", ["Client", "Server"],
        ["Client -> Server: SYN (seq=x)",
         "Server -> Client: SYN-ACK (seq=y, ack=x+1)",
         "Client -> Server: ACK (ack=y+1)"], "test_handshake"))
    print(animate_packet_flow("Store-and-forward packet switching",
                              ["Source", "Router 1", "Router 2", "Destination"], 4, "test_flow"))
    print(animate_sliding_window(8, 3, "test_window"))
    print(animate_dijkstra(["A-B:2", "A-C:5", "B-C:1", "B-D:4", "C-D:3"], "A", "test_dijkstra"))