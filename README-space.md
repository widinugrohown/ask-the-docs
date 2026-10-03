---
title: Ask the Ollama Docs
emoji: 🔎
colorFrom: blue
colorTo: gray
sdk: gradio
app_file: app_gradio.py
pinned: false
license: mit
---

# Ask the Ollama Docs

Ask a question about the Ollama documentation and get an answer that comes **only** from retrieved
sections, naming the section it came from — plus a panel showing which chunks were sent to the model
and how close each one was.

You can also **upload your own PDF** and ask questions about that instead.

Password-gated, because the demo holds a model API key and is rate-limited.

## What is measured, and what is not

**Read this first.** The figures below were measured on an **earlier corpus snapshot** (the
concatenated `llms-full.txt`, 490 chunks, fingerprint `ece45692c5358ef1`). This Space ships the newer
69-page corpus (**532 chunks**, fingerprint `defc2a8a766d2c29`), which has **not been re-measured
yet** — a different corpus means different numbers, so the two are stated separately rather than
blended. Re-measurement is the immediate next step, and the figures will be replaced when it is done.

Figures for that earlier snapshot:

| Metric | Value | How |
|---|---|---|
| Retrieval hit@5 | **12/12** | fixed 12-question set, gold source per question derived by `grep` |
| MRR | **0.958** | 11 questions at rank 1, 1 at rank 2 |
| Refusal on unanswerable questions | **3/3** | answering "I don't know" instead of inventing a source |
| Reasoning pass off | **−78% tokens, 2.5× faster** | citation rate unchanged at 12/12 |

**Uploaded PDFs are not measured.** Nothing on this page claims retrieval quality for a document the
visitor supplied — no hit-rate, no citation check, no refusal figure.

## What it does not prove

A citation shows a source was *named*, not that the answer is right. The bundled corpus is public
documentation, so a correct answer may come from the model's memory rather than from retrieval. The
cross-lingual gap measured on this project (**0/5** for an Indonesian question against an
English corpus) is written up in the project notes.

## Implementation

Raw pipeline, no framework: heading-aware chunking (a fenced code block is never split), a local CPU
embedding model, one provider-agnostic LLM client, in-memory index for uploads. The same code runs as
a CLI and behind FastAPI.
