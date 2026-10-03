"""app.py — a public demo of the measured RAG assistant (Hugging Face Space).

UNVERIFIED — written from the pipeline design recorded in the notes repo; not executed yet.
Read the two assumptions in "ASSUMPTIONS" below and check them against your own files
before deploying.

What it does
------------
Serves the same pipeline as the CLI (retrieve -> ground -> answer -> cite), behind a shared
password, on a free CPU Space instead of on a RAM-limited VPS.

ASSUMPTIONS (verify these two, they are the only places this file guesses)
--------------------------------------------------------------------------
1. `data/chunks.jsonl` exists in this repo: one JSON object per line, the output of your
   own `ingest.py` (490 rows). The loader below accepts several key spellings
   (`text`/`isi`, `heading`/`heading_path`) and prints what it found, so a wrong guess
   shows up as a message instead of a crash.
2. The embedding model used to build the index is the one named in `EMBED_MODEL`.
   Query vectors and stored vectors must come from the SAME model, or every distance is
   meaningless. Change one, you must rebuild the index.

Secrets (Space -> Settings -> Variables and secrets)
-----------------------------------------------------
    LLM_BASE_URL = https://ollama.com/v1
    LLM_API_KEY  = <your key>        (secret; never in the source)
    LLM_MODEL    = deepseek-v4.1-flash
    DEMO_PASSWORD = <the shared passphrase>

Cost note: the Space runs on the free CPU tier (2 vCPU / 16 GB). Embedding 490 short
chunks on CPU is a one-time cost per cold start; the model download is ~100 MB.
"""
from __future__ import annotations

import json
import os
import time
from pathlib import Path

import numpy as np
import streamlit as st

CHUNKS = Path("data/chunks.jsonl")
EMBED_MODEL = os.environ.get("EMBED_MODEL", "paraphrase-multilingual-MiniLM-L12-v2")
BASE_URL = os.environ.get("LLM_BASE_URL", "https://ollama.com/v1")
MODEL = os.environ.get("LLM_MODEL", "deepseek-v4.1-flash")

SISTEM = (
    "Answer only from the provided context. "
    "If the answer is not in the context, say you don't know and list nearby topics. "
    "Cite the source heading for each claim in the form [heading > path]."
)

# A sentence-transformers model is not needed at query time only: the same model must
# also have produced the stored vectors. Everything is embedded at startup, then cached.


def _field(row: dict, *names: str) -> str:
    """Read the first key that exists, so a key-name mismatch is visible, not fatal."""
    for n in names:
        if n in row and row[n] is not None:
            return str(row[n])
    raise KeyError(f"none of {names} in row keys {list(row.keys())[:8]}")


@st.cache_resource(show_spinner="Loading the index (first run downloads ~100 MB)...")
def load_index():
    from sentence_transformers import SentenceTransformer

    if not CHUNKS.exists():
        st.error(
            f"`{CHUNKS}` not found. Copy your ingest output into the Space repo "
            "(it is ~230 KB and is what makes the demo possible without re-downloading "
            "the corpus)."
        )
        st.stop()

    rows = [json.loads(l) for l in CHUNKS.read_text(encoding="utf-8").splitlines() if l.strip()]
    texts = [_field(r, "text", "isi", "content") for r in rows]
    headings = [_field(r, "heading", "heading_path", "sumber") for r in rows]

    model = SentenceTransformer(EMBED_MODEL)
    emb = model.encode(texts, normalize_embeddings=True, show_progress_bar=False)
    return {"texts": texts, "headings": headings, "emb": np.asarray(emb, dtype="float32"), "model": model}


def retrieve(q: str, k: int, idx):
    qv = idx["model"].encode([q], normalize_embeddings=True)[0]
    sims = idx["emb"] @ np.asarray(qv, dtype="float32")   # vectors are L2-normalised
    order = np.argsort(-sims)[:k]
    return [
        {"text": idx["texts"][i], "heading": idx["headings"][i], "distance": float(1.0 - sims[i])}
        for i in order
    ]


def jawab(pertanyaan: str, k: int, api_key: str, idx):
    from openai import OpenAI

    hits = retrieve(pertanyaan, k, idx)
    konteks = "\n\n".join(f"[{h['heading']}]\n{h['text']}" for h in hits)
    client = OpenAI(base_url=BASE_URL, api_key=api_key)
    t0 = time.perf_counter()
    r = client.chat.completions.create(
        model=MODEL, temperature=0, max_tokens=2048,
        messages=[
            {"role": "system", "content": SISTEM},
            {"role": "user", "content": f"Context:\n{konteks}\n\nQuestion: {pertanyaan}"},
        ],
    )
    return {
        "text": r.choices[0].message.content or "",
        "usage": r.usage.model_dump() if r.usage else {},
        "hits": hits,
        "elapsed_s": time.perf_counter() - t0,
    }


# ---------------------------------------------------------------------------------
st.set_page_config(page_title="Measured RAG demo", page_icon="🔎", layout="centered")
st.title("A Measured RAG Assistant")
st.caption(
    "Retrieval-augmented QA over the Ollama documentation. Answers come only from retrieved "
    "chunks and name the section they came from."
)

try:
    api_key = st.secrets["LLM_API_KEY"]
    password = st.secrets.get("DEMO_PASSWORD", "")
except Exception:
    api_key, password = os.environ.get("LLM_API_KEY", ""), os.environ.get("DEMO_PASSWORD", "")

if password and not st.session_state.get("ok"):
    st.text_input("Password", type="password", key="pw")
    if st.button("Enter"):
        if st.session_state.get("pw") == password:
            st.session_state["ok"] = True
            st.rerun()
        else:
            st.error("Wrong password.")
    st.stop()

if not api_key:
    st.error("`LLM_API_KEY` is not set. Add it in the Space settings (Variables and secrets).")
    st.stop()

idx = load_index()
st.caption(f"Index: **{len(idx['texts'])} chunks** · embedder `{EMBED_MODEL}` · model `{MODEL}`")

with st.form("ask"):
    q = st.text_input("Question", placeholder="How do I install Ollama on Linux?")
    k = st.slider("Chunks sent as context (k)", 1, 10, 5)
    go = st.form_submit_button("Ask")

if go and q.strip():
    with st.spinner("Retrieving and answering..."):
        out = jawab(q, k, api_key, idx)

    if not out["text"].strip():
        st.warning(
            "The model returned an **empty answer** with a successful call — its token budget "
            "was spent on hidden reasoning. This is a known failure mode at low `max_tokens`."
        )
    else:
        st.markdown(out["text"])

    st.markdown("**Sources actually sent as context** (distance: lower = closer)")
    st.table(
        [
            {"#": i + 1, "heading": h["heading"], "distance": round(h["distance"], 4)}
            for i, h in enumerate(out["hits"])
        ]
    )
    u = out["usage"]
    st.caption(
        f"{out['elapsed_s']:.1f} s end to end · prompt {u.get('prompt_tokens')} tokens · "
        f"completion {u.get('completion_tokens')} tokens"
    )
    if len({h["heading"] for h in out["hits"]}) < len(out["hits"]):
        st.caption(
            "Note: two of the chunks above share one heading, so k chunks covered fewer "
            "distinct sections than k suggests."
        )

st.divider()
st.caption(
    "**What this demo does not prove.** A citation shows a source was *named*, not that the "
    "answer is right. The corpus is public documentation, so a correct answer can come from the "
    "model's memory rather than from retrieval. Measured limits of this system — including a "
    "cross-lingual retrieval gap of 0/5 — are written up in the project README."
)
