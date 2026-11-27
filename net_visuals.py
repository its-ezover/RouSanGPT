"""Pictures and animations for the Computer Networks course, after the figures in the
lecture slides (Kurose and Ross): encapsulation, HTTP response time, stop-and-wait
and pipelining, Go-Back-N and Selective Repeat in action, TCP RTT estimation and
congestion control, the Internet checksum, CRC, longest prefix matching, IP
fragmentation, address bits, Dijkstra's table, distance vectors, switch
self-learning, packet vs circuit switching and ALOHA.

Every number comes from a calculation here or from the networking calculators,
never from the AI. With no inputs, each kind shows the slides' own example.
"""
import ipaddress
import math
import re

import animation_tools as at
import device_icons
import extra_tools
import more_tools
import tools
import visual_kit as vk
from visual_kit import H, W, arrow, box, center, cross, fit_line, left, visible

N = "networks"


def _num(text, name):
    """'1e9', '1 Gbps', '30ms', '8000' -> a number (k, M, G = 10^3, 10^6, 10^9)."""
    s = str(text).strip().lower().replace(" ", "").replace(",", "")
    m = re.fullmatch(r"([-+]?\d*\.?\d+(?:e[-+]?\d+)?)([kmg]?)(?:bps|b|bits|bytes|ms|s)?", s)
    if not m:
        raise ValueError(f"{name}: '{text}' is not a number")
    return float(m.group(1)) * {"": 1, "k": 1e3, "m": 1e6, "g": 1e9}[m.group(2)]


def _int(text, name):
    v = _num(text, name)
    if not v.is_integer():
        raise ValueError(f"{name} must be a whole number")
    return int(v)


def _get(inputs, defaults):
    return list(inputs) + defaults[len(inputs):]


def _fmt(v, digits=2):
    if abs(v - round(v)) < 1e-9:
        return str(int(round(v)))
    return f"{v:.{digits}f}"


# ---------- Chapter 1: encapsulation ----------

LAYERS = ["application", "transport", "network", "link", "physical"]
PDU = [("message", []), ("segment", ["Ht"]), ("datagram", ["Hn", "Ht"]), ("frame", ["Hl", "Hn", "Ht"])]


def _pdu(d, th, x, y, level, highlight=False):
    colors = {"Ht": th["accent"], "Hn": th["second"], "Hl": th["warn"]}
    for h in PDU[level][1]:
        box(d, x, y, 50, 46, th, colors[h], radius=6)
        center(d, x + 25, y + 23, h, 20, th, th["on_accent"], True)
        x += 52
    box(d, x, y, 70, 46, th, th["mark"] if highlight else th["head"], radius=6)
    center(d, x + 35, y + 23, "M", 22, th, th["text"], True)
    return x + 70


def _encapsulation(inputs):
    def draw(d, th, cur):
        rows = [150 + i * 86 for i in range(5)]
        lx, rx, sw = 80, W - 300, 220
        theme = "dark" if th is vk.DARK else "light"
        for side, x in (("source", lx), ("destination", rx)):
            device_icons.paste_icon(d, "pc", x + sw / 2 - 72, 126, 40, theme)
            left(d, x + sw / 2 - 44, 128, side + " host", 22, th, th["muted"], True)
            for i, name in enumerate(LAYERS):
                active = cur is not None and ((side == "source" and cur == i and i < 4) or
                                              (side == "destination" and cur == 8 - i and i < 4) or
                                              (i == 4 and cur == 4))
                box(d, x, rows[i], sw, 66, th, th["mark"] if active else None)
                center(d, x + sw / 2, rows[i] + 33, name, 24, th, th["text"], True)
        d.line([(lx + sw, rows[4] + 33), (rx, rows[4] + 33)], fill=th["line"], width=4)
        for i in range(4):
            if visible(cur, i):
                end = _pdu(d, th, lx + sw + 24, rows[i] + 10, i, cur == i)
                if cur is None:
                    left(d, end + 10, rows[i] + 33, PDU[i][0], 20, th, th["muted"])
            if visible(cur, 8 - i) and cur is not None and cur >= 5:
                _pdu(d, th, rx - 24 - (52 * len(PDU[i][1]) + 70), rows[i] + 10, i, cur == 8 - i)
        if cur is None:
            for i in range(4):
                _pdu(d, th, rx - 24 - (52 * len(PDU[i][1]) + 70), rows[i] + 10, i)
            arrow(d, lx - 30, rows[0] + 10, lx - 30, rows[4] + 50, th["accent"])
            arrow(d, rx + sw + 30, rows[4] + 50, rx + sw + 30, rows[0] + 10, th["accent"])
        if cur == 4:
            x = lx + sw + (rx - lx - sw) / 2 - 120
            _pdu(d, th, x, rows[4] + 10, 3, True)
        caption = ("each layer adds its header going down, and removes it going up" if cur is None else
                   ["the application makes a message M", "transport adds Ht: a segment",
                    "network adds Hn: a datagram", "link adds Hl: a frame", "the physical layer sends the bits",
                    "link removes Hl", "network removes Hn", "transport removes Ht", "M reaches the application"]
                   [max(cur, 0)])
        fit_line(d, W / 2, H - 50, caption, th, 28, th["accent"])
    return dict(title="Encapsulation", steps=9, per_step=1.3, draw=draw,
                result="message -> segment (Ht) -> datagram (Hn) -> frame (Hl), and back up")


# ---------- Chapter 1: packet switching vs circuit switching ----------

def _binomial(inputs):
    link, user, n, p = _get(inputs, ["1", "0.1", "35", "0.1"])
    link, user, p, n = _num(link, "link Mbps"), _num(user, "user Mbps"), _num(p, "p"), _int(n, "users")
    if not (0 < p < 1 and 1 <= n <= 200 and link > 0 and user > 0):
        raise ValueError("give link and user rates above 0, users from 1 to 200 and p between 0 and 1")
    limit = int(link / user + 1e-9)          # 1 / 0.1 is 9.999... in floating point
    probs = [math.comb(n, k) * p ** k * (1 - p) ** (n - k) for k in range(n + 1)]
    over = sum(probs[limit + 1:])
    shown = min(n, max(limit + 8, int(n * p * 3) + 4))
    top = max(probs[:shown + 1])

    def draw(d, th, cur):
        px = vk.chart_axes(d, th, (130, 150, W - 90, 560), shown + 1, top * 1.15, "number of active users k",
                           "P(k users active)", x_ticks=list(range(0, shown + 1, max(1, shown // 10))),
                           y_ticks=vk.nice_ticks(top * 1.1, 4))
        for k in range(shown + 1):
            if cur is not None and ((k > limit and cur < 1) or cur < 0):
                continue
            x0, y = px(k + 0.15, probs[k])
            x1, yb = px(k + 0.85, 0)
            at.gloss_rect(d, [x0, y, x1, yb], 2, th["bad"] if k > limit else th["accent"], light=th is vk.LIGHT)
        xl, _ = px(limit + 1, 0)
        d.line([(xl, 150), (xl, 560)], fill=th["warn"], width=3)
        left(d, xl + 8, 165, f"more than {limit} active: too many", 20, th, th["warn"], True)
        if cur is None or cur >= 2:
            fit_line(d, W / 2, 650, f"Circuit switching: {limit} users.   Packet switching: {n} users, "
                     f"P(more than {limit} active) = {over:.6f}", th, 26, th["accent"])
    return dict(title="Packet vs circuit switching", steps=3, per_step=1.8, draw=draw,
                result=f"circuit switching supports {limit} users; with {n} users and p = {p}, "
                       f"P(more than {limit} active) = {over:.6f}")


# ---------- Chapter 2: HTTP response time ----------

def _http_timing(inputs):
    rtt, objects, trans, parallel = _get(inputs, ["100", "10", "0", "5"])
    rtt, trans = _num(rtt, "RTT ms"), _num(trans, "transmit ms")
    objects, parallel = _int(objects, "objects"), max(1, _int(parallel, "parallel connections"))
    base = 2 * rtt + trans
    cases = [
        ("non-persistent, one at a time", (1 + objects) * (2 * rtt + trans),
         f"(1 + {objects}) x (2 RTT + t)"),
        (f"non-persistent, {parallel} in parallel", base + math.ceil(objects / parallel) * (2 * rtt + trans),
         f"(2 RTT + t) + {math.ceil(objects / parallel)} x (2 RTT + t)"),
        ("persistent, no pipelining", base + objects * (rtt + trans), f"(2 RTT + t) + {objects} x (RTT + t)"),
        ("persistent, with pipelining", base + rtt + objects * trans, f"(2 RTT + t) + RTT + {objects} t"),
    ]
    top = max(c[1] for c in cases)

    def draw(d, th, cur):
        fit_line(d, W / 2, 140, f"RTT = {_fmt(rtt)} ms,  base file + {objects} objects,  "
                 f"transmit time t = {_fmt(trans)} ms per object", th, 24, th["muted"], False)
        for i, (name, total, formula) in enumerate(cases):
            if not visible(cur, i):
                continue
            y = 200 + i * 110
            left(d, 80, y, name, 24, th, th["text"], True)
            width = (W - 420) * total / top
            at.gloss_rect(d, [80, y + 22, 80 + max(width, 6), y + 62], 8,
                          th["accent"] if i < 2 else th["good"], light=th is vk.LIGHT)
            left(d, 90 + max(width, 6), y + 42, f"{_fmt(total)} ms", 24, th, th["text"], True)
            left(d, 80, y + 82, formula, 18, th, th["muted"])
        if cur is None:
            fit_line(d, W / 2, 660, "each new TCP connection costs one RTT, each request-response one more",
                     th, 24, th["accent"])
    return dict(title="HTTP response time", steps=4, per_step=1.6, draw=draw,
                result="; ".join(f"{n}: {_fmt(t)} ms" for n, t, _ in cases),
                details={"cases": [{"case": n, "ms": round(t, 3), "formula": f} for n, t, f in cases]})


# ---------- Chapter 3: stop-and-wait vs pipelining ----------

def _stop_and_wait(inputs):
    length, rate, rtt, n = _get(inputs, ["8000", "1e9", "30", "3"])
    length, rate, rtt, n = _num(length, "L bits"), _num(rate, "R bps"), _num(rtt, "RTT ms"), _int(n, "N")
    if length <= 0 or rate <= 0 or rtt < 0 or not 1 <= n <= 8:
        raise ValueError("L and R must be above 0, RTT 0 or more, and N from 1 to 8")
    t = length / rate * 1000           # ms
    u1 = t / (rtt + t)
    un = min(1.0, n * t / (rtt + t))

    def timeline(d, th, x0, packets, show_ack, label):
        sx, rx, top = x0, x0 + 300, 190
        theme = "dark" if th is vk.DARK else "light"
        for x, name in ((sx, "sender"), (rx, "receiver")):
            device_icons.paste_icon(d, "pc", x - 66, 163, 36, theme)
            center(d, x + 6, 165, name, 22, th, th["muted"], True)
        d.line([(sx, top), (sx, 600)], fill=th["line"], width=3)
        d.line([(rx, top), (rx, 600)], fill=th["line"], width=3)
        band, travel = 26, 150
        for k in range(packets):
            y0 = top + 10 + k * band
            d.polygon([(sx, y0), (sx, y0 + band - 3), (rx, y0 + band - 3 + travel), (rx, y0 + travel)],
                      fill=th["accent"] if k == 0 else th["second"])
        if show_ack:
            # the ACK of the FIRST packet: it leaves when that packet's last bit arrives
            ya = top + 10 + travel + band
            arrow(d, rx, ya, sx, ya + travel, th["good"])
            d.text((sx - 12, ya + travel), "ACK arrives, send next:", font=at.font(17, True), fill=th["good"],
                   anchor="rs")
            d.text((sx - 12, ya + travel + 4), "t = RTT + L/R", font=at.font(17), fill=th["good"], anchor="rt")
        d.text((sx - 12, top + 12), "first bit sent, t = 0", font=at.font(17), fill=th["muted"], anchor="rm")
        d.text((sx - 12, top + 10 + band * packets), f"last bit sent, t = {packets} L/R" if packets > 1
               else "last bit sent, t = L/R", font=at.font(17), fill=th["muted"], anchor="rm")
        center(d, (sx + rx) / 2, 640, label, 24, th, th["accent"], True)

    def draw(d, th, cur):
        timeline(d, th, 260, 1, visible(cur, 1), f"stop-and-wait: U = {u1:.6f}" if visible(cur, 3)
                 else "stop-and-wait")
        if visible(cur, 2):
            timeline(d, th, 260 + 600, n, True, f"{n} pipelined: U = {un:.6f}" if visible(cur, 3)
                     else f"{n} packets pipelined")
        if visible(cur, 3):
            fit_line(d, W / 2, 685, f"L/R = {_fmt(t, 6)} ms,  U = (L/R) / (RTT + L/R),  "
                     f"pipelined U = N (L/R) / (RTT + L/R)", th, 20, th["muted"], False)
    return dict(title="Stop-and-wait vs pipelining", steps=4, per_step=1.8, draw=draw,
                result=f"L/R = {t:.6f} ms; stop-and-wait U = {u1:.6f}; {n} pipelined U = {un:.6f}")


# ---------- Chapter 3: Go-Back-N and Selective Repeat in action ----------

DELAY, TIMEOUT = 3, 12      # ticks: one-way delay, and the timeout (after the slides' figures)


def _simulate(protocol, window, total, lost):
    sends, acks, rcv_notes, snd_notes = [], [], [], []
    base, nxt, t = 0, 0, 0
    timer = None
    sent_time, acked = {}, set()
    queue = []
    expected, rbase, buffered = 0, 0, set()
    used_loss = set()
    arrivals = {}            # tick -> [seq]
    ack_arrivals = {}        # tick -> [ackno]
    while t < 300:
        for a in ack_arrivals.pop(t, []):
            if protocol == "gbn":
                note = f"rcv ack{a}"
                if a >= base:
                    base = a + 1
                    timer = t if base < nxt else None
                snd_notes.append((t, note))
            else:
                acked.add(a)
                snd_notes.append((t, f"rcv ack{a}, mark pkt{a} acked"))
                while base in acked:
                    base += 1
        if protocol == "gbn" and timer is not None and t >= timer + TIMEOUT:
            snd_notes.append((t, f"pkt{base} timeout"))
            queue = list(range(base, nxt))
            timer = t
        if protocol == "sr":
            for seq, st in sorted(sent_time.items()):
                if seq not in acked and seq >= base and t >= st + TIMEOUT and seq not in queue:
                    snd_notes.append((t, f"pkt{seq} timeout"))
                    queue.append(seq)
                    sent_time[seq] = t
        seq = None
        if queue:
            seq = queue.pop(0)
            again = True
        elif nxt < min(base + window, total):
            seq, again = nxt, False
            nxt += 1
        if seq is not None:
            drop = seq in lost and seq not in used_loss
            if drop:
                used_loss.add(seq)
            sends.append((t, seq, drop, again))
            sent_time[seq] = t
            if protocol == "gbn" and timer is None:
                timer = t
            if not drop:
                arrivals.setdefault(t + DELAY, []).append(seq)
        for s in arrivals.pop(t, []):
            if protocol == "gbn":
                if s == expected:
                    expected += 1
                    note, ack = f"rcv pkt{s}, deliver, send ack{s}", s
                else:
                    note, ack = f"rcv pkt{s}, discard, (re)send ack{expected - 1}", expected - 1
            else:
                if rbase <= s < rbase + window:
                    buffered.add(s)
                    delivered = []
                    while rbase in buffered:
                        delivered.append(rbase)
                        rbase += 1
                    note = (f"rcv pkt{s}, deliver pkt{','.join(map(str, delivered))}, send ack{s}" if delivered
                            else f"rcv pkt{s}, buffer, send ack{s}")
                else:
                    note = f"rcv pkt{s} again, send ack{s}"
                ack = s
            rcv_notes.append((t, note))
            if ack >= 0:
                acks.append((t, ack))
                ack_arrivals.setdefault(t + DELAY, []).append(ack)
        t += 1
        if base >= total and not arrivals and not ack_arrivals and not queue:
            break
    return sends, acks, rcv_notes, snd_notes, t


def _window_protocol(protocol):
    name = {"gbn": "Go-Back-N", "sr": "Selective Repeat"}[protocol]

    def make(inputs):
        window, total, lost = _get(inputs, ["4", "9", "2"])
        window, total = _int(window, "window"), _int(total, "packets")
        lost_set = {int(x) for x in re.findall(r"\d+", lost)}
        if not (1 <= window <= 8 and 2 <= total <= 12):
            raise ValueError("use a window of 1 to 8 and 2 to 12 packets")
        sends, acks, rnotes, snotes, ticks = _simulate(protocol, window, total, lost_set)
        retrans = sum(1 for s in sends if s[3])

        def draw(d, th, cur):
            sx, rx, top = 470, 860, 135
            step = min(15.5, (H - top - 40) / (ticks + DELAY))
            now = ticks + DELAY if cur is None else cur

            def y(tick):
                return top + 12 + tick * step

            theme = "dark" if th is vk.DARK else "light"
            for x, label in ((sx, "sender"), (rx, "receiver")):
                device_icons.paste_icon(d, "pc", x - 62, top - 8, 34, theme)
                center(d, x + 6, top - 8, label, 20, th, th["muted"], True)
            d.line([(sx, top + 4), (sx, H - 20)], fill=th["line"], width=3)
            d.line([(rx, top + 4), (rx, H - 20)], fill=th["line"], width=3)
            left(d, 60, top + 10, f"window size N = {window}", 18, th, th["accent"], True)
            for (ts, seq, drop, again) in sends:
                if ts > now:
                    continue
                end = ts + (DELAY / 2 if drop else DELAY)
                frac = min(1.0, (now - ts) / (end - ts))
                x2 = sx + (rx - sx) * frac * (0.5 if drop else 1)     # a lost packet stops halfway
                y2 = y(ts) + (y(end) - y(ts)) * frac
                color = th["warn"] if again else th["accent"]
                d.line([(sx, y(ts)), (x2, y2)], fill=color, width=3)
                if drop and frac >= 1:
                    cross(d, x2, y2, th["bad"], 9, 4)
                left(d, sx - 150, y(ts), f"send pkt{seq}", 14, th, color, again)
            for (ta, a) in acks:
                if ta > now:
                    continue
                frac = min(1.0, (now - ta) / DELAY)
                d.line([(rx, y(ta)), (rx - (rx - sx) * frac, y(ta) + DELAY * step * frac)],
                       fill=th["good"], width=2)
            for (tn, text) in rnotes:
                if tn <= now:
                    left(d, rx + 14, y(tn), text, 14, th, th["text"])
            for (tn, text) in snotes:
                if tn <= now:
                    color = th["bad"] if "timeout" in text else th["muted"]
                    d.text((sx - 160, y(tn) + 8), text, font=at.font(14, "timeout" in text), fill=color,
                           anchor="rm")
            if cur is None:
                left(d, 60, H - 40, f"{len(sends)} packets sent, {retrans} of them retransmitted", 20, th,
                     th["accent"], True)
        return dict(title=f"{name} in action", steps=ticks + DELAY, per_step=0.32, draw=draw,
                    result=f"{name}, window {window}, {total} packets, lost {sorted(lost_set)}: "
                           f"{len(sends)} sends, {retrans} retransmissions",
                    details={"receiver": [n for _, n in rnotes], "sender": [n for _, n in snotes]})
    return make


# ---------- Chapter 3: TCP RTT estimation ----------

def _tcp_rtt(inputs):
    samples, est, dev, alpha, beta = _get(inputs, ["106, 120, 140, 90, 115", "100", "5", "0.125", "0.25"])
    xs = [_num(v, "SampleRTT") for v in re.split(r"[,\s]+", samples.strip()) if v]
    est, dev, alpha, beta = _num(est, "EstimatedRTT"), _num(dev, "DevRTT"), _num(alpha, "alpha"), _num(beta, "beta")
    rows = []
    for i, s in enumerate(xs[:12], start=1):
        dev = (1 - beta) * dev + beta * abs(s - est)        # with the previous EstimatedRTT
        est = (1 - alpha) * est + alpha * s
        rows.append([str(i), _fmt(s), _fmt(dev), _fmt(est), _fmt(est + 4 * dev)])
    return vk.table_visual(
        "TCP round trip time and timeout", ["#", "SampleRTT", "DevRTT", "EstimatedRTT", "TimeoutInterval"], rows,
        f"TimeoutInterval = {rows[-1][3]} + 4 x {rows[-1][2]} = {rows[-1][4]} ms",
        note=f"DevRTT = (1-{beta:g}) DevRTT + {beta:g} |Sample - Est|,  then  Est = (1-{alpha:g}) Est + {alpha:g} Sample",
        per_step=1.3)


# ---------- Chapter 3: TCP congestion control ----------

def _cwnd_trace(ssthresh, rounds, events, variant):
    cwnd, trace = 1.0, []
    for r in range(1, rounds + 1):
        trace.append((r, cwnd, ssthresh))
        ev = events.get(r)
        if ev == "3dup":
            ssthresh = max(cwnd / 2, 1)
            cwnd = ssthresh + 3 if variant == "reno" else 1.0
        elif ev == "timeout":
            ssthresh = max(cwnd / 2, 1)
            cwnd = 1.0
        elif cwnd < ssthresh:
            cwnd = min(cwnd * 2, ssthresh)
        else:
            cwnd += 1
    return trace


def _tcp_congestion(inputs):
    ssthresh, rounds, events_text, variant = _get(inputs, ["8", "15", "8:3dup", "both"])
    ssthresh, rounds = _num(ssthresh, "ssthresh"), _int(rounds, "rounds")
    if not 2 <= rounds <= 40:
        raise ValueError("use 2 to 40 transmission rounds")
    events = {}
    for r, kind in re.findall(r"(\d+)\s*:\s*(3\s*dup|triple|timeout|to)", events_text.lower()):
        events[int(r)] = "timeout" if kind.startswith("t") and kind != "triple" else "3dup"
    variant = variant.strip().lower()
    names = ["reno", "tahoe"] if variant not in ("reno", "tahoe") else [variant]
    traces = {v: _cwnd_trace(ssthresh, rounds, events, v) for v in names}
    top = max(c for tr in traces.values() for _, c, _ in tr)

    def draw(d, th, cur):
        px = vk.chart_axes(d, th, (130, 150, W - 260, 600), rounds + 1, top * 1.15 + 1,
                           "transmission round", "cwnd (segments)", x_ticks=list(range(0, rounds + 1, 1 if rounds <= 20 else 2)),
                           y_ticks=vk.nice_ticks(top * 1.1, 5))
        colors = {"reno": th["accent"], "tahoe": th["second"]}
        for v, tr in traces.items():
            pts = [px(r, c) for r, c, _ in tr if visible(cur, r - 1)]
            if len(pts) > 1:
                d.line(pts, fill=colors[v], width=4)
            for x, y in pts:
                d.ellipse([x - 5, y - 5, x + 5, y + 5], fill=colors[v])
        tr0 = traces[names[0]]
        for r, _, th_val in tr0:
            if visible(cur, r - 1) and r < rounds:
                (x1, y1), (x2, _) = px(r, th_val), px(r + 1, th_val)
                d.line([(x1, y1), (x2, y1)], fill=th["warn"], width=2)
        for r, kind in events.items():
            if r <= rounds and visible(cur, r - 1):
                x, y = px(r, [c for rr, c, _ in tr0 if rr == r][0])
                center(d, x, y - 26, "3 dup ACKs" if kind == "3dup" else "timeout", 16, th, th["bad"], True)
        for k, v in enumerate(names):
            ly = 190 + k * 40
            d.line([(W - 240, ly), (W - 200, ly)], fill=colors[v], width=4)
            left(d, W - 190, ly, "TCP " + v.capitalize(), 20, th, colors[v], True)
        d.line([(W - 240, 190 + len(names) * 40), (W - 200, 190 + len(names) * 40)], fill=th["warn"], width=2)
        left(d, W - 190, 190 + len(names) * 40, "ssthresh", 20, th, th["warn"], True)
    detail = {v: [f"round {r}: cwnd {_fmt(c)}, ssthresh {_fmt(s)}" for r, c, s in tr] for v, tr in traces.items()}
    return dict(title="TCP congestion control", steps=rounds, per_step=0.6, draw=draw,
                result=" | ".join(f"{v}: " + ", ".join(_fmt(c) for _, c, _ in tr) for v, tr in traces.items()),
                details={"rounds": detail})


# ---------- Chapter 3 and 6: checksum and CRC ----------

def _checksum(inputs):
    words = inputs or ["0110011001100000", "0101010101010101", "1000111100001100"]
    r = extra_tools.internet_checksum_calculate(words)
    if "error" in r:
        raise ValueError(r["error"])
    rows = []
    for i, step in enumerate(r["steps"], start=1):
        m = re.match(r"\+ (\S+) -> (\S+)(.*)", step)
        rows.append([str(i), m.group(1), m.group(2), "carry wrapped around" if m.group(3).strip() else ""])
    rows.append(["", "flip every bit", r["checksum"], "checksum"])
    return vk.table_visual("Internet checksum", ["word", "add", "sum so far", ""], rows,
                           f"sum = {r['sum']},  checksum = {r['checksum']} ({r['checksum_hex']})",
                           note=f"{r['word_size_bits']}-bit words, one's complement addition",
                           marks={len(rows) - 1: "good"}, per_step=1.4)


def _crc(inputs):
    data, gen = _get(inputs, ["101110", "1001"])
    data, gen = data.replace(" ", ""), gen.replace(" ", "")
    check = more_tools.crc_calculate(data, gen)
    if "error" in check:
        raise ValueError(check["error"])
    r = len(gen) - 1
    work = list(data + "0" * r)
    lines = [("dividend", "".join(work), 0)]
    for i in range(len(work) - r):
        if work[i] == "1":
            for j in range(len(gen)):
                work[i + j] = "0" if work[i + j] == gen[j] else "1"
            lines.append(("xor", gen, i))
            lines.append(("result", "".join(work), i + len(gen)))
    remainder = "".join(work[-r:])
    if remainder != check["crc_remainder"]:
        raise ValueError("internal check failed")
    steps = (len(lines) - 1) // 2
    width = len(work)

    def draw(d, th, cur):
        cw = min(46, (W - 420) / width)
        x0 = (W - width * cw) / 2 + 60
        fit_line(d, W / 2, 140, f"D = {data},  G = {gen} (r = {r}): divide D followed by {r} zeros by G, "
                 "with XOR", th, 22, th["muted"], False)
        rh = min(44, 470 / len(lines))
        for k, (kind, bits, pos) in enumerate(lines):
            stepno = (k - 1) // 2
            if k > 0 and not visible(cur, stepno):
                continue
            y = 175 + k * rh
            if kind == "dividend":
                for i, b in enumerate(bits):
                    color = th["muted"] if i >= len(data) else th["text"]
                    center(d, x0 + i * cw + cw / 2, y + rh / 2, b, 26, th, color, True)
                left(d, x0 - 200, y + rh / 2, "D + zeros", 20, th, th["muted"])
            elif kind == "xor":
                d.text((x0 + pos * cw - 12, y + rh / 2), "XOR", font=at.font(18, True), fill=th["accent"],
                       anchor="rm")
                for i, b in enumerate(bits):
                    center(d, x0 + (pos + i) * cw + cw / 2, y + rh / 2, b, 26, th, th["accent"], True)
                d.line([(x0 + pos * cw, y + rh - 3), (x0 + (pos + len(bits)) * cw, y + rh - 3)],
                       fill=th["accent"], width=2)
            else:
                for i, b in enumerate(bits):
                    done = i < pos - len(gen) + 1
                    color = th["line"] if done and b == "0" else th["text"]
                    if cur is None and k == len(lines) - 1 and i >= width - r:
                        color = th["good"]
                    center(d, x0 + i * cw + cw / 2, y + rh / 2, b, 26, th, color, cur == stepno)
        if cur is None:
            fit_line(d, W / 2, H - 45, f"remainder R = {remainder},  send D followed by R: {data}{remainder}",
                     th, 28, th["accent"])
    return dict(title="CRC: dividing by the generator", steps=steps, per_step=1.5, draw=draw,
                result=f"R = {remainder}; transmitted {data}{remainder}")


# ---------- Chapter 4: forwarding and addressing ----------

def _bits(addr):
    return format(int(ipaddress.IPv4Address(addr)), "032b")


def _octets(bits, prefix=None, star=False):
    out = []
    for i, b in enumerate(bits):
        out.append("*" if star and prefix is not None and i >= prefix else b)
    s = "".join(out)
    return " ".join(s[i:i + 8] for i in range(0, 32, 8))


def _longest_prefix(inputs):
    defaults = ["200.23.24.170", "200.23.16.0/21:0", "200.23.24.0/24:1", "200.23.24.0/21:2", "default:3"]
    if len(inputs) < 2:
        inputs = ([inputs[0]] if inputs else defaults[:1]) + defaults[1:]
    addr = ipaddress.IPv4Address(inputs[0])
    abits = _bits(str(addr))
    entries = []
    for e in inputs[1:]:
        prefix, _, link = e.partition(":")
        if prefix.strip().lower() in ("default", "otherwise", "0.0.0.0/0"):
            net = ipaddress.IPv4Network("0.0.0.0/0")
        else:
            net = ipaddress.IPv4Network(prefix.strip(), strict=False)
        entries.append((net, link.strip() or "?"))
    matches = [(net.prefixlen, k) for k, (net, _) in enumerate(entries) if addr in net]
    if not matches:
        raise ValueError("no entry matches; add a default entry, e.g. 'default:3'")
    best = max(matches)[1]
    rows = []
    for net, link in entries:
        label = "otherwise" if net.prefixlen == 0 else _octets(_bits(str(net.network_address)), net.prefixlen, True)
        rows.append([label, f"/{net.prefixlen}", link, "yes" if addr in net else "no"])
    marks = {k: "good" if k == best else ("muted" if addr in entries[k][0] else None) for k in range(len(rows))}
    marks = {k: v for k, v in marks.items() if v}
    return vk.table_visual(
        "Longest prefix matching", ["destination address range", "length", "link", "matches?"], rows,
        f"{addr} -> link {entries[best][1]} (longest matching prefix /{entries[best][0].prefixlen})",
        note=f"destination {addr} = {_octets(abits)}", marks=marks, per_step=1.4)


def _fragmentation(inputs):
    size, mtu, header, ident = _get(inputs, ["4000", "1500", "20", "777"])
    size, mtu, header = _int(size, "datagram bytes"), _int(mtu, "MTU"), _int(header, "header bytes")
    if not (header < mtu and header < size <= 65535):
        raise ValueError("the datagram must be bigger than its header, and the MTU bigger than the header")
    data = size - header
    per = (mtu - header) // 8 * 8
    frags, offset = [], 0
    while data > 0:
        part = min(per, data)
        data -= part
        frags.append((part + header, offset // 8, 1 if data > 0 else 0, part))
        offset += part
    rows = [[str(i + 1), str(length), ident, str(flag), str(off), f"{part} (bytes {off * 8}-{off * 8 + part - 1})"]
            for i, (length, off, flag, part) in enumerate(frags)]
    visual = vk.table_visual("IP fragmentation", ["fragment", "length", "ID", "fragflag", "offset", "data bytes"],
                             rows, f"{len(frags)} fragments; offset = data byte position / 8",
                             note=f"{size}-byte datagram ({size - header} data bytes + {header} header), MTU {mtu}: "
                                  f"at most {per} data bytes per fragment (a multiple of 8)",
                             per_step=1.6)
    table_draw = visual["draw"]

    def draw(d, th, cur):
        table_draw(d, th, cur)
        x0, total_w, y = 160, W - 320, 470
        if len(frags) <= 12:
            left(d, 60, y + 20, "data", 18, th, th["muted"], True)
            x = x0
            for k, (_, _, _, part) in enumerate(frags):
                w = total_w * part / (size - header)
                if visible(cur, k):
                    at.gloss_rect(d, [x, y, x + w - 3, y + 40], 6, th["accent"] if k % 2 == 0 else th["second"],
                                  light=th is vk.LIGHT)
                    center(d, x + w / 2, y + 20, f"{part} B", 18, th, th["on_accent"], True)
                x += w
    visual["draw"] = draw
    return visual


def _address_bits(inputs):
    cidr = (inputs or ["200.23.16.42/23"])[0]
    info = tools.subnet_info(cidr)
    if "error" in info:
        raise ValueError(info["error"])
    addr = cidr.split("/")[0]
    prefix = info["prefix_length"]
    abits, mbits = _bits(addr), _bits(info["subnet_mask"])

    def bit_row(d, th, y, bits, label, show_net):
        cw = 30
        x0 = (W - (32 * cw + 3 * 18)) / 2 + 60
        d.text((x0 - 14, y + 18), label, font=at.font(20, True), fill=th["muted"], anchor="rm")
        for i, b in enumerate(bits):
            x = x0 + i * cw + (i // 8) * 18
            net = i < prefix
            fill = (th["accent"] if net else th["second"]) if show_net else None
            box(d, x, y, cw - 3, 36, th, fill, radius=4)
            center(d, x + cw / 2 - 1, y + 18, b, 18, th, th["on_accent"] if show_net else th["text"], True)
        return x0, cw

    def draw(d, th, cur):
        octs = addr.split(".")
        x0, cw = bit_row(d, th, 190, abits, "address", visible(cur, 2))
        for k, o in enumerate(octs):
            center(d, x0 + k * (8 * cw + 18) + 4 * cw, 168, o, 22, th, th["text"], True)
        if visible(cur, 1):
            bit_row(d, th, 260, mbits, "mask", visible(cur, 2))
            center(d, W / 2 + 60, 320, f"mask {info['subnet_mask']} = /{prefix}", 20, th, th["muted"])
        if visible(cur, 2):
            left(d, 200, 370, f"network part: {prefix} bits", 22, th, th["accent"], True)
            left(d, 700, 370, f"host part: {32 - prefix} bits", 22, th, th["second"], True)
        if visible(cur, 3):
            lines = [f"network address:  {info['network_address']}/{prefix}",
                     f"broadcast address:  {info['broadcast_address']}",
                     f"usable hosts:  {info.get('first_usable_host', '-')}  to  {info.get('last_usable_host', '-')}"
                     f"   ({info['usable_hosts']} hosts)"]
            for k, line in enumerate(lines):
                center(d, W / 2, 450 + k * 50, line, 26, th, th["text"], k == 0)
    return dict(title=f"IP address {cidr}", steps=4, per_step=1.6, draw=draw,
                result=f"network {info['network_address']}/{prefix}, broadcast {info['broadcast_address']}, "
                       f"{info['usable_hosts']} usable hosts")


# ---------- Chapter 5: routing ----------

def _graph(edges):
    graph = {}
    for e in edges:
        try:
            a, b, cost = more_tools._read_edge(e)
        except ValueError:
            raise ValueError(f"bad link '{e}': write it as 'A-B:cost'") from None
        more_tools._add_link(graph, a, b, cost)
        more_tools._add_link(graph, b, a, cost)
    return graph


def _dijkstra_table(inputs):
    defaults = ["u", "u-v:2", "u-x:1", "u-w:5", "v-x:2", "v-w:3", "x-w:3", "x-y:1", "w-y:1", "w-z:5", "y-z:2"]
    source, edges = (inputs[0], inputs[1:]) if len(inputs) > 1 else (defaults[0], defaults[1:])
    graph = _graph(edges)
    if source not in graph:
        raise ValueError(f"the source {source} is not in the graph")
    nodes = sorted(n for n in graph if n != source)
    dist, prev, done = {n: math.inf for n in graph}, {}, [source]
    dist[source] = 0
    for v, c in graph[source].items():
        dist[v], prev[v] = c, source
    rows = []

    def row(step):
        cells = [str(step), "".join(done)]
        for n in nodes:
            if n in done:                        # in N': its least cost is known
                cells.append("")
            elif dist[n] == math.inf:
                cells.append("inf")
            else:
                cells.append(f"{_fmt(dist[n])},{prev[n]}")
        return cells

    rows.append(row(0))
    while len(done) < len(graph):
        u = min((n for n in graph if n not in done and dist[n] < math.inf), key=lambda n: (dist[n], n), default=None)
        if u is None:
            break
        done.append(u)
        for v, c in graph[u].items():
            if v not in done and dist[u] + c < dist[v]:
                dist[v], prev[v] = dist[u] + c, u
        rows.append(row(len(done) - 1))
    check = more_tools.dijkstra_shortest_paths(edges, source)["shortest_distances"]
    if any(check[n] != (dist[n] if dist[n] < math.inf else "unreachable") for n in graph):
        raise ValueError("internal check failed")
    cell_marks = {}
    for i in range(1, len(rows)):
        col = nodes.index(done[i]) + 2 if done[i] in nodes else None
        if col is not None:
            cell_marks[(i - 1, col)] = "good"
    return vk.table_visual("Dijkstra's algorithm", ["step", "N'"] + [f"D({n}),p({n})" for n in nodes], rows,
                           "least costs: " + ", ".join(f"{n} {_fmt(dist[n])}" for n in nodes),
                           note=f"source {source};  ties are broken by name;  green = the node added next",
                           cell_marks=cell_marks, per_step=1.5)


def _distance_vector(inputs):
    graph = _graph(inputs or ["x-y:2", "y-z:1", "x-z:7"])
    nodes = sorted(graph)
    dv = {n: {m: (0 if m == n else graph[n].get(m, math.inf)) for m in nodes} for n in nodes}

    def vec(n):
        return "  ".join("inf" if dv[n][m] == math.inf else _fmt(dv[n][m]) for m in nodes)

    rows, cell_marks = [["0"] + [vec(n) for n in nodes]], {}
    for it in range(1, 12):
        new = {n: {m: (0 if m == n else min(c + dv[v][m] for v, c in graph[n].items())) for m in nodes}
               for n in nodes}
        changed = [n for n in nodes if new[n] != dv[n]]
        dv = new
        if not changed:
            break
        rows.append([str(it)] + [vec(n) for n in nodes])
        for n in changed:
            cell_marks[(len(rows) - 1, nodes.index(n) + 1)] = "good"
    return vk.table_visual("Distance vector (Bellman-Ford)", ["iteration"] + [f"D_{n}: to {' '.join(nodes)}" for n in nodes],
                           rows, f"converged after {len(rows) - 1} iteration(s)",
                           note="D_x(y) = min over neighbours v of { c(x,v) + D_v(y) };  green = changed",
                           cell_marks=cell_marks, per_step=1.8)


# ---------- Chapter 6: switch self-learning ----------

def _switch_learning(inputs):
    defaults = ["A:1, A':4, B:2, B':5, C:3, C':6", "A->A'", "A'->A", "C->A'"]
    if not inputs:
        inputs = defaults
    ports = {}
    for item in re.split(r"[,;]\s*", inputs[0]):
        if ":" in item:
            host, port = item.rsplit(":", 1)
            ports[host.strip()] = _int(port, "interface")
    frames = []
    for f in inputs[1:] or defaults[1:]:
        src, _, dst = f.partition("->")
        src, dst = src.strip(), dst.strip()
        if src not in ports or dst not in ports:
            raise ValueError(f"frame '{f}': both hosts must be in the port list {list(ports)}")
        frames.append((src, dst))
    table, events = {}, []
    for src, dst in frames:
        table[src] = ports[src]
        if dst in table:
            outs = [] if table[dst] == ports[src] else [table[dst]]
            action = f"{dst} is in the table: forward on interface {table[dst]} only" if outs else \
                     "destination is on the same interface: drop the frame"
        else:
            outs = sorted(p for p in set(ports.values()) if p != ports[src])
            action = f"{dst} is not in the table: flood on every other interface"
        events.append((src, dst, dict(table), outs, action))
    interfaces = sorted(set(ports.values()))

    def draw(d, th, cur):
        k = len(events) - 1 if cur is None else cur
        cx, cy = 400, 370
        theme = "dark" if th is vk.DARK else "light"
        device_icons.paste_icon(d, "switch", cx, cy, 170, theme)
        pos = {}
        half = math.ceil(len(interfaces) / 2)
        for i, p in enumerate(interfaces):
            top = i < half
            n = half if top else len(interfaces) - half
            j = i if top else i - half
            x = cx - 200 + (400 * (j + 0.5) / n)
            y = cy - 195 if top else cy + 170
            pos[p] = (x, y)
        src, dst, snapshot, outs, action = events[k] if k >= 0 else (None, None, {}, [], "")
        for host, p in ports.items():
            x, y = pos[p]
            top = y < cy
            edge_y = cy - 30 if top else cy + 52                 # the switch icon's top and bottom
            color = th["line"]
            if k >= 0 and p == ports[src]:
                color = th["accent"]
            elif k >= 0 and p in outs:
                color = th["good"]
            port_x = min(max(x, cx - 66), cx + 66)               # a point on the switch's edge
            d.line([(port_x, edge_y), (x, y + (66 if top else -38))], fill=color,
                   width=5 if color != th["line"] else 2)
            if k >= 0 and host in (src, dst):
                at.gloss_rect(d, [x - 44, y - 40, x + 44, y + 40], 12, th["mark"], light=th is vk.LIGHT)
            device_icons.paste_icon(d, "pc", x, y, 70, theme)
            center(d, x, y + 52, f"{host}  (port {p})", 18, th, th["text"], True)
        tx = 800
        left(d, tx, 160, "switch table", 24, th, th["muted"], True)
        draw_rows = [[h, str(p)] for h, p in snapshot.items()]
        vk.draw_table(d, th, ["MAC addr", "interface"], draw_rows or [["(empty)", ""]], None, {}, 190,
                      190 + 52 * (max(len(draw_rows), 1) + 1), x_left=tx, max_w=W - tx - 60)
        if k >= 0:
            fit_line(d, W / 2, 646, f"frame {src} -> {dst}: learn {src} on interface {ports[src]}", th, 26, th["accent"])
            fit_line(d, W / 2, 690, action, th, 24, th["text"], False)
    return dict(title="Switch self-learning", steps=len(events), per_step=2.4, draw=draw,
                result=" | ".join(f"{s}->{t}: {a}" for s, t, _, _, a in events))


# ---------- Chapter 6: ALOHA efficiency ----------

def _aloha(inputs):
    n = _int((inputs or ["10"])[0], "nodes N")
    if not 2 <= n <= 200:
        raise ValueError("use 2 to 200 nodes")
    ps = [i / 400 for i in range(1, 401)]
    slotted = [n * p * (1 - p) ** (n - 1) for p in ps]
    pure = [n * p * (1 - p) ** (2 * (n - 1)) for p in ps]
    best_s = n * (1 / n) * (1 - 1 / n) ** (n - 1)
    best_p = max(pure)
    p_max = min(1.0, 6 / n)

    def draw(d, th, cur):
        px = vk.chart_axes(d, th, (130, 150, W - 300, 590), p_max, 0.45, "p (probability a node transmits)",
                           "efficiency", x_ticks=vk.nice_ticks(p_max, 5), y_ticks=[0.1, 0.2, 0.3, 0.4])
        for k, (vals, key, label) in enumerate(((slotted, "accent", "slotted ALOHA"), (pure, "second", "pure ALOHA"))):
            if not visible(cur, k):
                continue
            pts = [px(p, v) for p, v in zip(ps, vals) if p <= p_max]
            d.line(pts, fill=th[key], width=4)
            left(d, W - 280, 200 + 40 * k, label, 22, th, th[key], True)
        for k, (value, key) in enumerate(((1 / math.e, "accent"), (1 / (2 * math.e), "second"))):
            if visible(cur, k):
                _, y = px(0, value)
                d.line([(130, y), (W - 300, y)], fill=th[key], width=1)
                left(d, W - 290, y, f"{value:.2f} as N grows", 16, th, th[key])
        if cur is None:
            fit_line(d, W / 2, 665, f"N = {n}: best slotted {best_s:.3f} (at p = 1/N),  best pure {best_p:.3f}",
                     th, 26, th["accent"])
    return dict(title="ALOHA efficiency", steps=2, per_step=2.0, draw=draw,
                result=f"N = {n}: max slotted efficiency {best_s:.3f}, max pure {best_p:.3f}; limits 1/e = 0.37 and 1/(2e) = 0.18")


# ---------- the registry ----------

vk.register("encapsulation", N, "Message going down the protocol stack (headers Ht, Hn, Hl added) and back up.",
            "[] (nothing needed)", _encapsulation, icon="pc")
vk.register("packet_vs_circuit", N, "Packet vs circuit switching: binomial chance that too many users are active.",
            '[link Mbps, Mbps per user, users, p active], default ["1", "0.1", "35", "0.1"]', _binomial, icon="cloud")
vk.register("http_response_time", N, "Non-persistent vs persistent HTTP response time, compared as bars.",
            '[RTT ms, objects, transmit ms per object, parallel connections], default ["100", "10", "0", "5"]',
            _http_timing, icon="web_server")
vk.register("stop_and_wait", N, "rdt3.0 stop-and-wait vs pipelined timing and utilization U.",
            '[L bits, R bps, RTT ms, N pipelined], default ["8000", "1e9", "30", "3"]', _stop_and_wait, icon="pc")
vk.register("go_back_n", N, "Go-Back-N in action: sender/receiver timelines, a lost packet, timeout, resend all.",
            '[window, packets, lost packet numbers], default ["4", "9", "2"]', _window_protocol("gbn"), icon="pc")
vk.register("selective_repeat", N, "Selective Repeat in action: buffering, per-packet timeout, resend only the lost one.",
            '[window, packets, lost packet numbers], default ["4", "9", "2"]', _window_protocol("sr"), icon="pc")
vk.register("tcp_rtt", N, "TCP EstimatedRTT, DevRTT and TimeoutInterval table.",
            '[samples, initial EstimatedRTT, initial DevRTT, alpha, beta], default ["106, 120, 140, 90, 115", "100", "5", "0.125", "0.25"]',
            _tcp_rtt, icon="server")
vk.register("tcp_congestion", N, "TCP cwnd per transmission round: slow start, congestion avoidance, Reno vs Tahoe.",
            '[ssthresh, rounds, events like "8:3dup, 14:timeout", "reno"/"tahoe"/"both"], default ["8", "15", "8:3dup", "both"]',
            _tcp_congestion, icon="router")
vk.register("internet_checksum", N, "Internet checksum: one's complement addition with wraparound, then flip.",
            "[16-bit words as bits or 0x hex], default the textbook's three words", _checksum, icon="document")
vk.register("crc", N, "CRC long division with XOR, the remainder R.",
            '[data bits, generator bits], default ["101110", "1001"]', _crc, icon="document")
vk.register("longest_prefix_match", N, "Forwarding table lookup by longest prefix match, in binary.",
            '[address, "prefix/len:link", ..., "default:link"], default the slides\' table and 200.23.24.170',
            _longest_prefix, icon="router")
vk.register("ip_fragmentation", N, "IP fragmentation: fragments with length, ID, fragflag and offset.",
            '[datagram bytes, MTU, header bytes, ID], default ["4000", "1500", "20", "777"]', _fragmentation, icon="router")
vk.register("ip_address", N, "An IPv4 address in bits: network and host part, mask, network, broadcast, hosts.",
            '[CIDR], default ["200.23.16.42/23"]', _address_bits, icon="pc")
vk.register("dijkstra_table", N, "Dijkstra's table (step, N', D(v),p(v)) as in the slides.",
            '[source, "A-B:cost", ...], default the slides\' u v w x y z graph', _dijkstra_table, icon="router")
vk.register("distance_vector", N, "Distance vector (Bellman-Ford) tables, iteration by iteration.",
            '["A-B:cost", ...], default ["x-y:2", "y-z:1", "x-z:7"]', _distance_vector, icon="router")
vk.register("switch_learning", N, "Switch self-learning: frames, flooding or forwarding, the table filling up.",
            '["host:interface, ...", "A->B", ...], default the slides\' A A\' B B\' C C\' example', _switch_learning, icon="switch")
vk.register("aloha", N, "Slotted vs pure ALOHA efficiency against p for N nodes.",
            '[N nodes], default ["10"]', _aloha, icon="access_point")
