# Corpus — Ollama documentation, 69 pages

**File:** `ollama-docs-corpus.md`
**Built:** 2026-10-03 · **Source:** `https://docs.ollama.com/llms.txt` (the per-page `.md` index)
**Fingerprint:** `defc2a8a766d2c29` (first 16 hex of SHA-256)

| Metric | Value |
|---|---|
| Size | 330,164 bytes · 9,522 lines |
| Pages | **69** |
| Headings | 78 `#` · 256 `##` · **122 `###`** |
| Code fences | 554 (even — no block is cut) |
| Estimated chunks | ~660, at the measured ~500 bytes/chunk ratio |
| Estimated tokens | ~91,455 proxy (`tiktoken`; the provider's own count is unknown) |
| Fits a 128k context window | **yes** |

## How it was built

`llms.txt` lists 69 individual `.md` pages. Each was fetched, and the pages were concatenated in
documentation order, preceded by a provenance comment so every chunk can name its source page:

```markdown
<!-- source: https://docs.ollama.com/api/embed.md -->

# Generate Embeddings
...
```

The first line of every page (`> ## Documentation Index ...`) is a navigation banner repeated 69
times; it was stripped. Nothing else was removed. `ollama-docs-corpus.manifest.json` holds the byte
offset, byte length and URL of each page, so a chunk can be traced back to the page it came from
without re-reading the corpus.

## Why not `llms-full.txt`

The obvious choice was the single concatenated file (`235,096 bytes`). Measured against the 69 pages,
it is **substantially incomplete**:

| Metric | `llms-full.txt` | 69 pages |
|---|---|---|
| Bytes | 235,096 | **330,164** |
| Code fences (example blocks) | 528 | **554** |
| `/api/...` endpoint references | 92 | **142** |
| Pages under 90% coverage | — | 42 of 69 |
| Pages absent entirely | — | 8 (embed, create, pull, push, delete, ps, copy, tags) |

The endpoint *names* do appear in the concatenated file, which is why a naive check says "present" —
but the **body** of those API pages does not: their sections are ~0% covered. For a documentation QA
system, that is the part a user is most likely to ask about.

## Caveat — this is a moving target

The site changed between snapshots: the previous recorded fingerprint of the concatenated file was
`ece45692c5358ef1`, the one fetched for this build is `25c6a813c9b3885a`. Every number above belongs to
the snapshot of 2026-10-03 and to no other. Re-probe before comparing.

## Reproducing

```bash
curl -sL https://docs.ollama.com/llms.txt -o ollama-index.txt
# extract the 69 *.md URLs, fetch each, concatenate in order with <!-- source: URL --> headers
shasum -a 256 ollama-docs-corpus.md | cut -c1-16   # expect defc2a8a766d2c29
```
