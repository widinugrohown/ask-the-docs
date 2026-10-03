"""pdf_upload.py — accept a visitor's own PDF and turn it into a searchable index, safely.

Measured while writing this (2026-10-03): pypdf installed = 4.2 MB; it read a 102-page / 624 KB
regulation PDF in 2.1 s and produced 171,991 characters of clean text. So extraction is cheap —
the cost is the *embedding* step, which runs on CPU, which is why the limits below exist.

Three rules this file enforces, each for a stated reason:

1. **A text layer must exist.** A scanned PDF returns an empty string. Without this check the app
   would silently build an index of zero chunks and then answer "I don't know" to everything, which
   looks like a retrieval failure instead of an unsupported file. OCR is deliberately out of scope.
2. **Hard limits, printed to the visitor.** Pages, bytes and chunks are capped because the embedder
   runs on the free CPU tier and the LLM calls are paid for by the project owner. A refusal that
   explains itself is better than a mysterious timeout.
3. **Nothing leaves the session.** The uploaded text and its index live in memory for that visitor's
   session only — never written to disk, never shared between visitors.
"""
from __future__ import annotations

import io
import re

MAX_PDF_MB = 8
MAX_PAGES = 60
MAX_CHUNKS = 300
MAX_REQUESTS_PER_DAY = 40          # enforced by the caller, which tracks per-session counts

LIMITS_TEXT = (
    f"Limits: PDF up to **{MAX_PDF_MB} MB**, up to **{MAX_PAGES} pages**, "
    f"up to **{MAX_CHUNKS} chunks** indexed, and up to **{MAX_REQUESTS_PER_DAY} questions per day**."
)


class UploadError(Exception):
    """Raised with a message written for the visitor, not for a log file."""


def extract_pages(data: bytes) -> list[str]:
    """Return the text of each page. Raises UploadError with a readable reason on failure."""
    if len(data) > MAX_PDF_MB * 1024 * 1024:
        raise UploadError(
            f"That file is {len(data)/1024/1024:.1f} MB. The limit is {MAX_PDF_MB} MB — "
            "please send a smaller extract."
        )
    try:
        from pypdf import PdfReader
    except ImportError:  # pragma: no cover
        raise UploadError("PDF support is not installed on this Space (pypdf missing).")

    try:
        reader = PdfReader(io.BytesIO(data))
        if reader.is_encrypted:
            raise UploadError("That PDF is password-protected, so its text cannot be read.")
        pages = [(p.extract_text() or "") for p in reader.pages[:MAX_PAGES]]
    except UploadError:
        raise
    except Exception as exc:  # a corrupt file must not take the app down
        raise UploadError(f"Could not read that PDF ({type(exc).__name__}: {exc}).")

    total_chars = sum(len(p) for p in pages)
    if total_chars < 500:
        raise UploadError(
            "No text layer found in that PDF. It looks like a scan or an image-only export; "
            "this demo reads text, it does not run OCR."
        )
    return pages


def pages_to_corpus(pages: list[str], name: str) -> str:
    """Turn pages into markdown the chunker understands, with honest provenance.

    A PDF has no headings, so a synthetic heading per page is added: that is what gives every
    chunk a citable source and gives the chunker section boundaries to work with. The heading is
    declared as synthetic rather than pretending the document had one.
    """
    base = re.sub(r"[^A-Za-z0-9._ -]", "", name)[:60] or "uploaded.pdf"
    out = []
    for i, text in enumerate(pages, 1):
        out.append(f"<!-- source: {base}#page={i} -->\n\n# {base} — page {i}\n\n{text.strip()}\n")
    return "\n".join(out)


def build_upload(pages: list[str], name: str):
    """Chunk + embed + index an uploaded document, in memory only.

    Uses the project's own chunker (`chunker.py`, next to this file) so an uploaded PDF is split by
    exactly the same heading-aware, fence-safe rules as the bundled corpus — otherwise the two would
    not be comparable, and the demo would be measuring one thing while claiming another.
    """
    from chunker import chunk_doc
    from embed import embed_texts

    corpus = pages_to_corpus(pages, name)
    chunks = chunk_doc(f"upload:{name}", corpus)
    texts = [c[3] for c in chunks]
    headings = [c[1] for c in chunks]

    if len(texts) > MAX_CHUNKS:
        raise UploadError(
            f"That document produced {len(texts)} chunks; the limit is {MAX_CHUNKS}. "
            "Try a shorter extract, or fewer pages."
        )
    if not texts:
        raise UploadError("The document produced no usable text after chunking.")

    return {"kind": "upload", "name": name, "texts": texts, "headings": headings,
            "emb": embed_texts(texts)}
