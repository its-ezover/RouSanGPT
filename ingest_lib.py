import logging
import subprocess
import tempfile
from pathlib import Path

from pypdf import PdfReader
from pptx import Presentation

import binaries

logging.getLogger("pypdf").setLevel(logging.ERROR)
SUPPORTED = (".pdf", ".pptx", ".ppt", ".txt")


def split_text(text, size=800, overlap=150):
    pieces = []
    start = 0
    while start < len(text):
        pieces.append(text[start:start + size])
        start += size - overlap
    return pieces


def read_pdf(path, progress=None):
    reader = PdfReader(path)
    total = len(reader.pages)
    for n, page in enumerate(reader.pages, start=1):
        if progress and n % 25 == 0:
            progress(f"page {n}/{total}")
        yield f"page {n}", page.extract_text() or ""


def read_pptx(path, progress=None):
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


def read_ppt(path, progress=None):
    """Old .ppt: convert with LibreOffice if installed, otherwise use catppt."""
    soffice = binaries.find_tool("soffice") or binaries.find_tool("libreoffice")
    if soffice:
        if progress:
            progress("converting the old .ppt file")
        # (LibreOffice on Windows may still hold the folder for a moment when it ends)
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
            subprocess.run([soffice, "--headless", "--convert-to", "pptx", "--outdir", tmp, str(path)],
                           capture_output=True, timeout=300, **binaries.NO_WINDOW)
            converted = Path(tmp) / (Path(path).stem + ".pptx")
            if converted.exists():
                yield from read_pptx(converted, progress)
                return
    catppt = binaries.find_tool("catppt")
    if catppt is None:
        raise RuntimeError("Old .ppt files need LibreOffice or catdoc. "
                           + str(binaries.ToolMissing("soffice")))
    result = subprocess.run([catppt, str(path)], capture_output=True, text=True, **binaries.NO_WINDOW)
    yield "all slides", result.stdout


def read_txt(path, progress=None):
    lines = Path(path).read_text(encoding="utf-8", errors="ignore").splitlines()
    for i in range(0, len(lines), 4):
        yield f"lines {i + 1}-{i + 4}", "\n".join(lines[i:i + 4])


READERS = {".pdf": read_pdf, ".pptx": read_pptx, ".ppt": read_ppt, ".txt": read_txt}


def remove_source(collection, name):
    collection.delete(where={"source": name})


def add_file(collection, path, progress=None):
    """Read one file and add its pieces to the database. Returns the number of pieces."""
    path = Path(path)
    reader = READERS.get(path.suffix.lower())
    if reader is None:
        raise ValueError(f"{path.suffix} files are not supported")
    remove_source(collection, path.name)          # replace an older copy of the same file
    total = 0
    ids, docs, metas = [], [], []
    for location, text in reader(path, progress):
        for i, piece in enumerate(split_text(text)):
            if piece.strip():
                ids.append(f"{path.name}|{location}|{i}")
                docs.append(piece)
                metas.append({"source": path.name, "location": location})
        if len(ids) >= 200:
            collection.upsert(ids=ids, documents=docs, metadatas=metas)
            total += len(ids)
            ids, docs, metas = [], [], []
            if progress:
                progress(f"{total} pieces stored")
    if ids:
        collection.upsert(ids=ids, documents=docs, metadatas=metas)
        total += len(ids)
    return total