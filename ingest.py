import logging
import subprocess
from pathlib import Path
from pypdf import PdfReader
from pptx import Presentation
import chromadb

# hide the harmless warnings some PDFs cause
logging.getLogger("pypdf").setLevel(logging.ERROR)

MATERIALS = Path("materials")

# Start fresh every time, so re-running never creates duplicates
db = chromadb.PersistentClient(path="course_db")
try:
    db.delete_collection("course")
except Exception:
    pass
collection = db.create_collection("course")


def split_text(text, size=800, overlap=150):
    """Cut a long text into overlapping pieces."""
    pieces = []
    start = 0
    while start < len(text):
        pieces.append(text[start:start + size])
        start += size - overlap
    return pieces


# Each "reader" gives back pairs of: (where it is, the text there)

def read_pdf(path):
    reader = PdfReader(path)
    total = len(reader.pages)
    for n, page in enumerate(reader.pages, start=1):
        if n % 50 == 0:
            print(f"    page {n}/{total}", flush=True)
        yield f"page {n}", page.extract_text() or ""


def read_pptx(path):
    prs = Presentation(path)
    for n, slide in enumerate(prs.slides, start=1):
        parts = []
        for shape in slide.shapes:
            if shape.has_text_frame:
                parts.append(shape.text_frame.text)
            if shape.has_table:
                for row in shape.table.rows:
                    parts.append(" | ".join(cell.text for cell in row.cells))
        if slide.has_notes_slide and slide.notes_slide.notes_text_frame:
            parts.append(slide.notes_slide.notes_text_frame.text)
        yield f"slide {n}", "\n".join(parts)


def read_ppt(path):
    # old .ppt format: use the free command-line tool 'catppt'
    result = subprocess.run(["catppt", str(path)], capture_output=True, text=True)
    yield "all slides", result.stdout


def read_txt(path):
    # keep link files in small groups of lines so links never get cut in half
    lines = path.read_text(errors="ignore").splitlines()
    for i in range(0, len(lines), 4):
        yield f"lines {i + 1}-{i + 4}", "\n".join(lines[i:i + 4])


READERS = {
    ".pdf": read_pdf,
    ".pptx": read_pptx,
    ".ppt": read_ppt,
    ".txt": read_txt,
}

for file in sorted(MATERIALS.iterdir()):
    reader = READERS.get(file.suffix.lower())
    if reader is None:
        print("Skipping (unknown type):", file.name, flush=True)
        continue
    print("Reading", file.name, "...", flush=True)
    try:
        for location, text in reader(file):
            ids, docs, metas = [], [], []
            for i, piece in enumerate(split_text(text)):
                if piece.strip():
                    ids.append(f"{file.name}|{location}|{i}")
                    docs.append(piece)
                    metas.append({"source": file.name, "location": location})
            if docs:
                collection.upsert(ids=ids, documents=docs, metadatas=metas)
        print("  done", flush=True)
    except Exception as e:
        print("  PROBLEM with this file:", str(e)[:150], flush=True)

print("\nTotal pieces stored:", collection.count())