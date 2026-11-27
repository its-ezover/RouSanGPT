import math


def _clean_bits(text):
    return text.strip().replace(" ", "")


def _divide_mod2(bits, generator):
    """Modulo-2 (XOR) long division. Returns (remainder, list of steps)."""
    work = list(bits)
    r = len(generator) - 1
    steps = []
    for i in range(len(work) - r):
        if work[i] == "1":
            for j in range(len(generator)):
                work[i + j] = "0" if work[i + j] == generator[j] else "1"
            steps.append(f"XOR at position {i}: {''.join(work)}")
    return "".join(work[-r:]), steps


def crc_calculate(data_bits: str, generator_bits: str) -> dict:
    """Calculate the CRC (cyclic redundancy check) for a bit string, the way it is
    done in the textbook. data_bits is the data D as 0s and 1s, for example
    '101110'. generator_bits is the generator G as 0s and 1s, for example '1001'.
    Returns the CRC remainder R (r bits, where r = length of G minus 1), the full
    frame to transmit (data followed by R) and the division steps."""
    d, g = _clean_bits(data_bits), _clean_bits(generator_bits)
    if not d or set(d) - {"0", "1"} or set(g) - {"0", "1"}:
        return {"error": "data_bits and generator_bits must contain only 0 and 1."}
    if len(g) < 2 or g[0] != "1":
        return {"error": "generator_bits must start with 1 and have at least 2 bits."}
    r = len(g) - 1
    remainder, steps = _divide_mod2(d + "0" * r, g)
    return {
        "crc_remainder": remainder,
        "transmitted_frame": d + remainder,
        "bits_added": r,
        "division_steps": steps[:50],
    }


def crc_check(received_bits: str, generator_bits: str) -> dict:
    """Check a received frame for transmission errors using CRC. received_bits is
    the whole received frame (data plus CRC bits) as 0s and 1s. generator_bits is
    the generator G. If the division remainder is all zeros, no error is detected."""
    rx, g = _clean_bits(received_bits), _clean_bits(generator_bits)
    if not rx or set(rx) - {"0", "1"} or set(g) - {"0", "1"}:
        return {"error": "received_bits and generator_bits must contain only 0 and 1."}
    if len(g) < 2 or g[0] != "1" or len(rx) <= len(g) - 1:
        return {"error": "Invalid generator, or the frame is too short for it."}
    remainder, steps = _divide_mod2(rx, g)
    return {
        "remainder": remainder,
        "error_detected": "1" in remainder,
        "division_steps": steps[:50],
    }


def _read_edge(text):
    """'A-B:2', 'R-1->R-2:3' or 'R-1 R-2:3' -> ('A', 'B', 2.0)."""
    pair, cost = text.rsplit(":", 1)
    pair = pair.strip()
    if "->" in pair:
        parts = pair.split("->")
    elif " " in pair:
        parts = pair.split()
    else:
        parts = pair.split("-")
    if len(parts) != 2 or not all(p.strip() for p in parts):
        raise ValueError(text)
    return parts[0].strip(), parts[1].strip(), float(cost)


def _add_link(graph, a, b, cost):
    """Keep the cheapest cost when the same link is given more than once."""
    links = graph.setdefault(a, {})
    links[b] = min(cost, links.get(b, cost))


def dijkstra_shortest_paths(edges: list[str], source: str, directed: bool = False) -> dict:
    """Run Dijkstra's shortest-path algorithm on a network graph.
    edges: the links, each written as 'A-B:cost', for example ['A-B:2', 'A-C:5', 'B-C:1'].
    Node names that contain a hyphen (R-1) can be written 'R-1->R-2:3' or 'R-1 R-2:3'.
    If the same link is given twice, the cheaper cost is used.
    source: the starting node, for example 'A'.
    directed: False (default) means every link works in both directions.
    Returns the shortest distance and path to every node, the order in which
    nodes were finalised, and a step-by-step table of distances."""
    graph = {}
    for e in edges:
        try:
            a, b, cost = _read_edge(e)
        except ValueError:
            return {"error": f"Bad edge '{e}'. Use the format 'A-B:cost', for example 'A-B:2' "
                             "(or 'R-1->R-2:3' when names contain a hyphen)."}
        if cost < 0:
            return {"error": "Dijkstra's algorithm needs costs that are not negative."}
        if cost.is_integer():
            cost = int(cost)
        _add_link(graph, a, b, cost)
        graph.setdefault(b, {})
        if not directed:
            _add_link(graph, b, a, cost)
    source = source.strip()
    if source not in graph:
        return {"error": f"Source node '{source}' is not in the graph: {list(graph)}"}

    dist = {n: math.inf for n in graph}
    dist[source] = 0
    previous = {}
    done = []
    steps = []
    while True:
        candidates = [n for n in graph if n not in done and dist[n] < math.inf]
        if not candidates:
            break
        u = min(candidates, key=lambda n: dist[n])   # closest unfinished node
        done.append(u)
        for v, w in graph[u].items():
            if v not in done and dist[u] + w < dist[v]:
                dist[v] = dist[u] + w
                previous[v] = u
        steps.append({
            "step": len(done),
            "node_finalised": u,
            "distances": {n: (d if d < math.inf else "infinity") for n, d in dist.items()},
        })

    paths = {}
    for n in graph:
        if dist[n] == math.inf:
            paths[n] = "unreachable"
            continue
        route, node = [n], n
        while node in previous:
            node = previous[node]
            route.append(node)
        paths[n] = " -> ".join(reversed(route))

    return {
        "shortest_distances": {n: (d if d < math.inf else "unreachable") for n, d in dist.items()},
        "shortest_paths": paths,
        "order_finalised": done,
        "steps": steps,
    }


# The list we give to the AI
MORE_TOOLS = [crc_calculate, crc_check, dijkstra_shortest_paths]


# Quick self-test: run `python more_tools.py`
if __name__ == "__main__":
    print(crc_calculate("101110", "1001"))
    print(crc_check("101110011", "1001"))
    result = dijkstra_shortest_paths(["A-B:2", "A-C:5", "B-C:1", "B-D:4", "C-D:3"], "A")
    print(result["shortest_distances"])
    print(result["shortest_paths"])