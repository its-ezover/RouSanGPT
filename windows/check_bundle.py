"""Build step for the Windows setup (run by windows/build.ps1 with the bundled Python).

Checks that the bundled Python loads every package and the app itself, saves the
course-search model inside the app (so the first start needs no 80 MB download),
checks the bundled FFmpeg and Graphviz, and precompiles the app.

    python check_bundle.py <app folder>
"""
import compileall
import os
import subprocess
import sys
import tempfile
from pathlib import Path

app = Path(sys.argv[1]).resolve()
assert Path(sys.executable).parent.parent == app.parent, "run this with the bundled Python"

# 1. every package loads (a missing DLL shows up here, not on a student's computer)
import chromadb, onnxruntime, fastapi, uvicorn, google.genai, pptx, pypdf  # noqa: E401,F401
import matplotlib, PIL, numpy, edge_tts, psutil, truststore, ollama  # noqa: E401,F401
print("packages load: ok")

# 2. the search model, saved in app\models (knowledge.py uses it from there)
from chromadb.utils.embedding_functions.onnx_mini_lm_l6_v2 import ONNXMiniLM_L6_V2

model_dir = app / "models" / ONNXMiniLM_L6_V2.MODEL_NAME
ONNXMiniLM_L6_V2.DOWNLOAD_PATH = model_dir
vector = ONNXMiniLM_L6_V2()(["TCP opens a connection with a three-way handshake."])[0]
assert len(vector) == 384, len(vector)
archive = model_dir / ONNXMiniLM_L6_V2.ARCHIVE_FILENAME
if archive.exists():
    archive.unlink()                                 # only the unpacked model is used
print("search model:", model_dir)

# 3. the app's own modules load, and use the bundled model and programs
import binaries
import knowledge
import server  # noqa: F401

assert Path(ONNXMiniLM_L6_V2.DOWNLOAD_PATH) == model_dir, ONNXMiniLM_L6_V2.DOWNLOAD_PATH
for tool in ("ffmpeg", "dot"):
    path = binaries.find_tool(tool)
    assert path and Path(path).parent == app / "bin", f"{tool}: {path}"
with tempfile.TemporaryDirectory() as tmp:
    binaries.run_ffmpeg(["-f", "lavfi", "-i", "sine=duration=1", os.path.join(tmp, "tone.wav")])
    png = os.path.join(tmp, "g.png")
    r = subprocess.run([binaries.find_tool("dot"), "-Tpng", "-o", png], input="digraph { A -> B }",
                       capture_output=True, text=True)
    assert r.returncode == 0 and os.path.getsize(png) > 100, r.stderr
print("app, FFmpeg and Graphviz: ok")
knowledge.collection.count()

# 4. precompile, so the first start is faster
assert compileall.compile_dir(str(app), quiet=1, legacy=False)
print("bundle ok")
