"""build_chunks.py — turn the corpus into data/chunks.jsonl using the project's own chunker.

Run once at build time (locally or as a Space build step), before the app starts:

    python build_chunks.py
    # chunks 532 · odd_fences 0 · distinct headings 376

The app depends on this file existing; it refuses to serve a corpus it cannot chunk.
"""
from __future__ import annotations

import json
import os
import statistics
import sys
from pathlib import Path

from chunker import chunk_doc, load_docs

CORPUS = Path(os.environ.get("CORPUS", "data/ollama-docs-corpus.md"))
OUT = Path(os.environ.get("CHUNKS_JSONL", "data/chunks.jsonl"))


def main() -> int:
    if not CORPUS.exists():
        print(f"corpus not found: {CORPUS}")
        return 2

    chunks = [c for src, body in load_docs(CORPUS) for c in chunk_doc(src, body)]
    if not chunks:
        print("chunker produced zero chunks — check the corpus format before continuing")
        return 1

    OUT.parent.mkdir(parents=True, exist_ok=True)
    with OUT.open("w", encoding="utf-8") as f:
        for source, heading, order, text in chunks:
            f.write(json.dumps(
                {"source": source, "heading": heading, "order": order, "text": text},
                ensure_ascii=False) + "\n")

    lengths = sorted(len(c[3]) for c in chunks)
    odd = sum(1 for c in chunks if c[3].count("```") % 2)
    print(f"chunks            {len(chunks)}")
    print(f"median_chars      {int(statistics.median(lengths))}")
    print(f"min / max chars   {lengths[0]} / {lengths[-1]}   (above target = a whole code block)")
    print(f"no_heading        {sum(1 for c in chunks if c[1] == '(intro)')}")
    print(f"odd_fences        {odd}   <- MUST be 0, otherwise a code block was split")
    print(f"distinct headings {len({c[1] for c in chunks})}")
    print(f"written           {OUT} ({OUT.stat().st_size:,} bytes)")
    if odd:
        print("FAIL: fix the fence handling before serving this corpus")
        return 1
    if len(chunks) > 20 and len({c[1] for c in chunks}) == 1:
        print("SUSPECT: every chunk shares one heading path (heading captured at flush time)")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
