"""rag_core.py — retrieval and answering, with no UI framework in the import path.

Kept separate from `app_gradio.py` so the logic can be tested (and reused by a CLI or an HTTP API)
without installing Gradio. The app file imports from here; this file knows nothing about the UI.
"""
from __future__ import annotations

import json
import os
import time
from pathlib import Path

import numpy as np

import embed

LLM_BASE_URL = os.environ.get("LLM_BASE_URL", "https://ollama.com/v1")
LLM_MODEL = os.environ.get("LLM_MODEL", "deepseek-v4.1-flash")

CHUNKS_JSONL = Path(os.environ.get("CHUNKS_JSONL", "data/chunks.jsonl"))

SISTEM = (
    "Answer only from the provided context. "
    "If the answer is not in the context, say you don't know and list nearby topics. "
    "Cite the source heading for each claim in the form [heading > path]."
)

BUNDLED_NOTE = (
    "Retrieval and citation figures for this corpus are published: **hit@5 12/12, MRR 0.958**, "
    "refusal on unanswerable questions **3/3**. A citation proves a source was *named* — not that "
    "the answer is right — because this corpus is public documentation the model may already know."
)

NOT_MEASURED_NOTE = (
    "**This document was not measured.** The hit-rate, citation and refusal figures in the project "
    "README apply to the bundled Ollama corpus only — nothing here claims them for your upload. "
    "The panel below shows the sources that actually reached the model."
)


class IndexMissing(RuntimeError):
    """Raised when chunks.jsonl is absent, with the command that creates it."""


def load_bundled_index(chunks_path: Path | None = None) -> dict:
    """Read the pre-built chunks and embed them once, in memory.

    The chunk file is produced at build time by the project's own chunker, so the bundled corpus and
    any uploaded document go through identical splitting rules.
    """
    path = Path(chunks_path or CHUNKS_JSONL)
    if not path.exists():
        raise IndexMissing(
            f"{path} not found. Build it with:\n"
            "  python build_chunks.py        # chunker -> data/chunks.jsonl"
        )
    rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    if not rows:
        raise IndexMissing(f"{path} is empty.")
    texts = [r["text"] for r in rows]
    headings = [r["heading"] for r in rows]
    return {"kind": "bundled", "name": "Ollama documentation",
            "texts": texts, "headings": headings, "emb": embed.embed_texts(texts)}


def retrieve(index: dict, question: str, k: int = 5) -> list[dict]:
    """The k nearest chunks by cosine distance. Embeddings are L2-normalised, so this is a dot product."""
    qv = np.asarray(embed.embed_query(question), dtype="float32")
    sims = index["emb"] @ qv
    order = np.argsort(-sims)[: max(1, int(k))]
    return [{"text": index["texts"][i], "heading": index["headings"][i],
             "distance": float(1.0 - sims[i])} for i in order]


def answer(index: dict, question: str, k: int = 5) -> dict:
    """Retrieve, ground, generate. Returns the text, the usage, the hits, and the wall-clock time."""
    from openai import OpenAI

    hits = retrieve(index, question, k)
    context = "\n\n".join(f"[{h['heading']}]\n{h['text']}" for h in hits)
    client = OpenAI(base_url=LLM_BASE_URL, api_key=os.environ["LLM_API_KEY"])
    t0 = time.perf_counter()
    r = client.chat.completions.create(
        model=LLM_MODEL, temperature=0, max_tokens=2048,
        messages=[{"role": "system", "content": SISTEM},
                  {"role": "user", "content": f"Context:\n{context}\n\nQuestion: {question}"}],
    )
    return {"text": r.choices[0].message.content or "",
            "usage": r.usage.model_dump() if r.usage else {},
            "hits": hits,
            "elapsed_s": time.perf_counter() - t0}


def sources_markdown(hits: list[dict]) -> str:
    """The panel: what was actually sent, and how far each chunk was."""
    rows = "\n".join(f"| {i+1} | {h['heading']} | {h['distance']:.4f} |" for i, h in enumerate(hits))
    out = "| # | Heading sent as context | Distance |\n|---|---|---|\n" + rows
    distinct = len({h["heading"] for h in hits})
    if distinct < len(hits):
        out += (f"\n\n_{len(hits)} chunks covered only **{distinct} distinct sections** — overlap "
                "produced duplicates, so k is a ceiling, not a count._")
    return out


def usage_line(out: dict) -> str:
    u = out.get("usage") or {}
    line = (f"{out['elapsed_s']:.1f} s end to end · prompt {u.get('prompt_tokens', '?')} tokens · "
            f"completion {u.get('completion_tokens', '?')} tokens")
    details = u.get("prompt_tokens_details") or {}
    if details.get("cached_tokens"):
        line += f" · {details['cached_tokens']} cached"
    return line
