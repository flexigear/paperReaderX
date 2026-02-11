"""PDF text extraction and page rendering using PyMuPDF."""

import hashlib
import fitz  # PyMuPDF
from pathlib import Path


def compute_fingerprint(pdf_bytes: bytes) -> str:
    """Compute SHA256 fingerprint of PDF content."""
    return hashlib.sha256(pdf_bytes).hexdigest()


def extract_text(pdf_path: str | Path) -> str:
    """Extract full text from a PDF file."""
    doc = fitz.open(str(pdf_path))
    text_parts = []
    for page in doc:
        text_parts.append(page.get_text())
    doc.close()
    return "\n".join(text_parts)


def get_page_count(pdf_path: str | Path) -> int:
    """Get the number of pages in a PDF."""
    doc = fitz.open(str(pdf_path))
    count = len(doc)
    doc.close()
    return count


def extract_metadata(pdf_path: str | Path) -> dict:
    """Extract title and authors from PDF metadata."""
    doc = fitz.open(str(pdf_path))
    meta = doc.metadata or {}
    doc.close()
    title = meta.get("title", "").strip()
    author = meta.get("author", "").strip()
    return {"title": title, "authors": author}


def render_page_png(pdf_path: str | Path, page_num: int, dpi: int = 150) -> bytes:
    """Render a single page as PNG bytes. page_num is 0-indexed."""
    doc = fitz.open(str(pdf_path))
    if page_num < 0 or page_num >= len(doc):
        doc.close()
        raise ValueError(f"Page {page_num} out of range (0-{len(doc)-1})")
    page = doc[page_num]
    zoom = dpi / 72.0
    mat = fitz.Matrix(zoom, zoom)
    pix = page.get_pixmap(matrix=mat)
    png_bytes = pix.tobytes("png")
    doc.close()
    return png_bytes
