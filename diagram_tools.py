import subprocess
import textwrap
from pathlib import Path

import binaries


def _clean_name(name):
    safe = "".join(c for c in name if c.isalnum() or c in "-_")
    return safe or "diagram"


def _open_image(path):
    """Open the picture in the computer's default image viewer."""
    binaries.open_file(path)


def draw_topology(dot_code: str, name: str) -> dict:
    """Draw a network topology or graph (computers, switches, routers, links,
    routing graphs with link costs) from Graphviz DOT code.
    dot_code: complete DOT source. Use 'graph' with '--' for undirected links, or
    'digraph' with '->' for directed ones. Give links a label for costs, for example
    A -- B [label="4"]. Tip: start with 'rankdir=LR;' for a left-to-right layout.
    name: short file name without spaces, for example 'lan_topology'.
    The picture is saved and shown to the student. If the result contains an
    'error', fix the DOT code and call this tool again."""
    Path("diagrams").mkdir(exist_ok=True)
    safe = _clean_name(name)
    dot_file = Path("diagrams") / f"{safe}.dot"
    png_file = Path("diagrams") / f"{safe}.png"
    dot_file.write_text(dot_code, encoding="utf-8")
    dot = binaries.find_tool("dot")
    if dot is None:
        return {"error": str(binaries.ToolMissing("dot"))}
    try:
        result = subprocess.run(
            [dot, "-Tpng", str(dot_file), "-o", str(png_file)],
            capture_output=True, text=True, timeout=30, **binaries.NO_WINDOW,
        )
    except (OSError, subprocess.TimeoutExpired) as e:
        return {"error": f"Graphviz could not run: {e}"}
    if result.returncode != 0:
        return {"error": "Graphviz could not draw this DOT code: " + result.stderr[:300]}
    _open_image(png_file)
    return {"saved_to": str(png_file), "message": "Diagram drawn and shown to the student."}


def draw_sequence_diagram(title: str, participants: list[str],
                          messages: list[str], name: str) -> dict:
    """Draw a message-sequence diagram, for example a TCP three-way handshake,
    a DNS lookup, an HTTP request, DHCP or ARP.
    title: the diagram title.
    participants: the parties from left to right, for example ["Client", "Server"].
    messages: the steps in time order, each written exactly as
    'Sender -> Receiver: label', for example 'Client -> Server: SYN (seq=x)'.
    Sender and Receiver must be names from participants.
    name: short file name without spaces, for example 'tcp_handshake'.
    The picture is saved and shown to the student. If the result contains an
    'error', fix the input and call this tool again."""
    xs = {p: i for i, p in enumerate(participants)}
    steps = []
    for msg in messages:
        try:
            route, label = msg.split(":", 1)
            sender, receiver = [s.strip() for s in route.split("->")]
            steps.append((xs[sender], xs[receiver], label.strip()))
        except (ValueError, KeyError):
            return {"error": f"Bad message format: '{msg}'. Use 'Sender -> Receiver: label' "
                             f"with names taken from participants {participants}."}

    import matplotlib
    matplotlib.use("Agg")  # draw to a file, no window needed
    import matplotlib.pyplot as plt

    n = len(steps)
    fig, ax = plt.subplots(figsize=(3 + 2.5 * len(participants), 1.8 + 0.8 * n))
    bottom = -(n + 1)
    for p, x in xs.items():
        ax.text(x, 0.3, p, ha="center", va="bottom", fontsize=12, fontweight="bold",
                bbox=dict(boxstyle="round", fc="#dbeafe"))
        ax.plot([x, x], [0, bottom], color="gray", linestyle="--", linewidth=1)
    for i, (x1, x2, label) in enumerate(steps, start=1):
        y = -i
        ax.annotate("", xy=(x2, y), xytext=(x1, y),
                    arrowprops=dict(arrowstyle="->", lw=1.5))
        ax.text((x1 + x2) / 2, y + 0.12, f"{i}. {label}", ha="center",
                va="bottom", fontsize=10)
    ax.set_title(title)
    ax.axis("off")
    ax.set_xlim(-0.6, len(participants) - 0.4)
    ax.set_ylim(bottom - 0.3, 1.3)

    Path("diagrams").mkdir(exist_ok=True)
    png_file = Path("diagrams") / f"{_clean_name(name)}.png"
    fig.savefig(png_file, dpi=150, bbox_inches="tight")
    plt.close(fig)
    _open_image(png_file)
    return {"saved_to": str(png_file), "message": "Diagram drawn and shown to the student."}


def draw_packet_header(title: str, fields: list[str], name: str) -> dict:
    """Draw a protocol header (TCP, UDP, IP, ...) as rows of 32 bits, the way
    textbooks show them.
    title: the diagram title, for example 'TCP segment structure'.
    fields: the header fields in order, each written as 'Field name:bits', for
    example ['Source port:16', 'Destination port:16', 'Sequence number:32'].
    Fields are packed into rows of 32 bits. A field bigger than 32 bits, such as
    'Data:64', takes several full rows. Use the correct field sizes from the course
    materials. name: short file name without spaces, for example 'tcp_header'.
    The picture is saved and shown to the student. If the result contains an
    'error', fix the input and call this tool again."""
    parsed = []
    for f in fields:
        try:
            label, bits = f.rsplit(":", 1)
            bits = int(bits)
            if bits <= 0:
                raise ValueError
        except ValueError:
            return {"error": f"Bad field '{f}'. Use 'Field name:bits', for example 'Checksum:16'."}
        parsed.append((label.strip(), bits))

    # work out where each field goes: (label, start_bit, width, row, height_in_rows)
    items = []
    row, used = 0, 0
    for label, bits in parsed:
        if bits > 32:
            if used > 0:
                row, used = row + 1, 0
            height = -(-bits // 32)
            items.append((label, 0, 32, row, height))
            row += height
        else:
            if used + bits > 32:
                row, used = row + 1, 0
            items.append((label, used, bits, row, 1))
            used += bits
            if used == 32:
                row, used = row + 1, 0
    total_rows = row + (1 if used > 0 else 0)

    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.patches import Rectangle

    fig, ax = plt.subplots(figsize=(11, 1.4 + 0.75 * total_rows))
    for i in range(32):                      # the bit ruler on top
        ax.text(i + 0.5, 0.12, str(i), ha="center", va="bottom", fontsize=6)
    for label, x, w, r, h in items:
        ax.add_patch(Rectangle((x, -(r + h)), w, h, fc="#dbeafe", ec="black", lw=1.2))
        ax.text(x + w / 2, -(r + h / 2), textwrap.fill(label, width=max(5, w)),
                ha="center", va="center", fontsize=8)
    ax.set_xlim(-0.2, 32.2)
    ax.set_ylim(-total_rows - 0.2, 1.0)
    ax.axis("off")
    ax.set_title(title)

    Path("diagrams").mkdir(exist_ok=True)
    png_file = Path("diagrams") / f"{_clean_name(name)}.png"
    fig.savefig(png_file, dpi=150, bbox_inches="tight")
    plt.close(fig)
    _open_image(png_file)
    return {"saved_to": str(png_file), "message": "Header diagram drawn and shown to the student."}


# The list we give to the AI
DIAGRAM_TOOLS = [draw_topology, draw_sequence_diagram, draw_packet_header]


# Quick self-test: run `python diagram_tools.py`
if __name__ == "__main__":
    print(draw_sequence_diagram(
        "TCP three-way handshake",
        ["Client", "Server"],
        ["Client -> Server: SYN (seq=x)",
         "Server -> Client: SYN-ACK (seq=y, ack=x+1)",
         "Client -> Server: ACK (ack=y+1)"],
        "test_handshake",
    ))
    print(draw_topology(
        'graph { rankdir=LR; PC1 -- Switch; PC2 -- Switch; Switch -- Router; Router -- Internet; }',
        "test_topology",
    ))
    print(draw_packet_header(
        "TCP segment structure",
        ["Source port:16", "Destination port:16", "Sequence number:32",
         "Acknowledgment number:32", "Header length:4", "Reserved:6", "Flags:6",
         "Receive window:16", "Checksum:16", "Urgent pointer:16",
         "Options:32", "Data:64"],
        "test_tcp_header",
    ))