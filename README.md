# ask-the-docs

Ask a question about a documentation corpus and get an answer that comes **only** from retrieved
sections, naming the section each claim came from — plus a panel showing which chunks were actually
sent to the model and how far each one was.

A retrieval-augmented question-answering system built from raw parts, then **measured** — retrieval
quality, token cost and latency are all numbers obtained from runs, and the limits of those numbers
are published alongside them.

Ask it a question about the Ollama documentation and it answers **only** from retrieved chunks,
naming the section each claim came from:

```
$ curl -s -X POST localhost:8000/ask -H 'Content-Type: application/json' \
    -d '{"pertanyaan":"How do I install Ollama on Linux?","k":3}'
{
  "answer": "To install Ollama on Linux, run:\n\n```shell\ncurl -fsSL https://ollama.com/install.sh | sh\n```\n\n[Linux > Install]",
  "sources": [
    { "heading": "Linux > Install",                 "distance": 0.2115 },
    { "heading": "Windows > Standalone CLI",        "distance": 0.2749 },
    { "heading": "macOS > Filesystem Requirements", "distance": 0.2839 }
  ],
  "usage": { "prompt_tokens": 429, "completion_tokens": 126, "cached_tokens": 300 }
}
```

## What this is

| Layer | File | Role |
|---|---|---|
| LLM door | `llm_client.py` | The only place the model is called. Provider = three `.env` values. |
| Ingest | `ingest.py` | Corpus → chunks, each carrying its heading path and order |
| Index | `index.py` | Local CPU embeddings → persistent Chroma collection |
| Retrieval | `retrieve.py` | Top-k nearest chunks by cosine distance |
| Answer | `ask.py` | Assemble context, apply the grounding prompt, call the LLM |
| Evaluation | `evaluate.py` | 12 fixed questions → hit@k, MRR, citation check, latency |
| Serving | `main.py`, `Dockerfile` | `POST /ask`, a chat page, and a container image |

No LangChain, no LlamaIndex. The pipeline is written out so every stage is inspectable — and so the
evaluation stage could actually measure something.

## Results

> **Read this before quoting a number.** These results were measured on the **previous** corpus
> snapshot — the concatenated `llms-full.txt`, 237,381 bytes, **490 chunks**, fingerprint
> `ece45692c5358ef1`. The corpus now shipped is different: **69 pages, 330,164 bytes, 532 chunks**,
> fingerprint `defc2a8a766d2c29` (built from the per-page files in `docs.ollama.com/llms.txt`; see
> `data/README.md` for why the single-file version is incomplete). A different corpus means different
> retrieval numbers, and the 532-chunk corpus has **not been re-measured yet**. The two are stated
> separately rather than blended.

Evaluation set: **12 fixed questions**, each with a gold source derived by `grep` over the corpus
before any tuning (kept in `eval_questions.txt` so the set can be disputed). Model:
`deepseek-v4.1-flash` over an OpenAI-compatible endpoint, `temperature=0`. Embeddings: local CPU.

### Retrieval — three retrievers, same 12 questions

| Retriever | hit@5 | MRR |
|---|---|---|
| BM25 (keyword) | 9/12 (75%) | 0.510 |
| Vector, chunk text only | 10/12 (83%) | 0.658 |
| **Vector, heading path + chunk text** | **12/12 (100%)** | **0.958** |

Including the heading path inside the embedded text was the single largest improvement measured
here (**+0.300 MRR**). The failures explain why: a question asking how to install *on Linux* could
not be answered by keyword matching, because the body text says "To install Ollama" and never says
"Linux" — the platform name exists only in the heading.

### Cost and latency — one knob at a time

| Change | Effect | Guard that had to hold |
|---|---|---|
| Disable the model's reasoning pass (`reasoning_effort=none`) | completion tokens **−78.4%**, p50 latency **2.53× faster** (2,932 → 1,161 ms) | citations 12/12 — no drop |
| Send 3 chunks instead of 5 (`k=3`) | prompt tokens **−23.3%** (10,586 → 8,120 over 12 questions) | hit@3 12/12 and citations 12/12 — no drop |
| Grounding itself | **+567 prompt tokens** per question vs. no context | answers became traceable |

For factual QA the visible answer is 100–280 characters while the billed completion is ~900 tokens
per question: the cost sits in the model's hidden deliberation, not in what you read.

### Serving

| Metric | Value |
|---|---|
| `POST /ask` over HTTP | 200 OK, correct answer, 3 sources |
| Prompt tokens per request | 429 (300 = **69.9%** served from provider cache) |
| Docker image | **2.32 GB**, of which the `pip install` layer is 1.65 GB (71.1%) |
| Container verification | `torch 2.14.1+cpu`; `.env` **absent** from the image |

## Limits — what these numbers do not prove

Published here on purpose. A number without its limits is advertising.

- **A citation check proves a source was *named*, not that the answer is right.** The automated
  check found the gold heading in 12/12 answers; **11 of those 12 answers were never read by a
  human**. An answer can name the correct section and still invent its content.
- **The corpus is public, so a correct answer does not prove retrieval worked.** Ollama's docs are
  on the internet and plausibly in the model's training data. This is the RAG form of data leakage:
  grading a system on material it may already have memorised. The check that does count — does the
  answer's text actually appear in the *retrieved chunk* — was run on **n=1 question** (3/3
  sentences matched).
- **Latency is not a single number.** Three runs gave p50 values of 1,161 / 2,932 / 4,920 ms. One run
  of 12 questions reported k=3 as *slower* than k=5 despite doing less work: service variance beats
  a small difference in work.
- **Cross-lingual retrieval is a measured gap, cause unknown.** The same question in English put the
  gold source at rank 1 (distance 0.2115); in Indonesian it never reached the top 5 (**0/5**,
  rank-1 distance 0.4532). The benchmark's 12/12 is therefore quoted **only for corpus-language
  (English) questions**, and the cause of the gap is not yet identified — an earlier hypothesis
  (a monolingual embedder) was contradicted by the multilingual model actually in use.
- **Retrieval distance cannot decide "unanswerable".** A question whose answer is present scored a
  top distance of 0.421; one whose answer is definitely absent scored 0.433 — a **2.9%** difference.
  What actually makes the system safe is the grounding prompt **giving the model permission to
  refuse**: 3/3 unanswerable questions were declined without inventing a source.
- **A proxy tokenizer is not the provider's counter.** `tiktoken` counted 12 tokens for a prompt the
  provider billed as 42 — a 3.5× under-count. Cost is read from `usage`, never estimated.
- **`temperature=0` is not determinism for this model.** Identical calls produced 112 / 125 / 147
  completion tokens and changed the visible answer in 1 of 3 runs. Pinning `seed` locked the text
  (3/3 identical) but **not** the token count. Cost and latency are therefore medians over repeated
  runs, never a single precise-looking figure.
- **Uploaded PDFs are not measured at all.** No hit-rate, citation or refusal figure is claimed for a
  document a visitor supplies. The upload path exists to show the pipeline generalises; the app labels
  every answer drawn from it accordingly.

## How to run it

```bash
pip install -r requirements.txt
python build_chunks.py                 # corpus -> data/chunks.jsonl   (expect: odd_fences 0)
python check_questions.py              # every gold pattern must resolve (expect: 0 wrong)

export LLM_BASE_URL=https://ollama.com/v1
export LLM_API_KEY=...                 # never commit this
export LLM_MODEL=deepseek-v4.1-flash

python app_gradio.py                   # http://127.0.0.1:7860
```

`build_chunks.py` refuses to continue if a chunk contains an unbalanced code fence, or if every chunk
shares one heading path — both are symptoms of a chunker bug that would otherwise surface much later,
as bad retrieval.

## Running it in a container

```bash
docker build -t rag-docs-assistant .
docker run --rm -p 8000:8000 --env-file .env \
  -v rag-models:/models rag-docs-assistant
```

`.env` is passed at run time and excluded by `.dockerignore` — verified absent inside the image.

## Notes and full write-up

The stage-by-stage decision log (including two hypotheses that measurement killed, and one claim
retracted after it failed to reproduce) lives in a separate notes repository.

## License

Code: MIT. Corpus content belongs to the Ollama documentation authors.
