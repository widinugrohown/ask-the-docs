"""embed.py — the one place text becomes vectors.

Query vectors and stored vectors must come from the SAME model, or every distance is meaningless.
That is why this module has exactly one model name and both the bundled index and any uploaded
document go through it.
"""
from __future__ import annotations

import os

import numpy as np

EMBED_MODEL = os.environ.get("EMBED_MODEL", "paraphrase-multilingual-MiniLM-L12-v2")

_model = None


def _model_instance():
    """Loaded once per process. The first call downloads ~100 MB on a fresh Space."""
    global _model
    if _model is None:
        from sentence_transformers import SentenceTransformer

        _model = SentenceTransformer(EMBED_MODEL)
    return _model


def embed_texts(texts) -> np.ndarray:
    """L2-normalised embeddings, so cosine similarity is a plain dot product."""
    vecs = _model_instance().encode(list(texts), normalize_embeddings=True, show_progress_bar=False)
    return np.asarray(vecs, dtype="float32")


def embed_query(question: str) -> np.ndarray:
    return embed_texts([question])[0]
