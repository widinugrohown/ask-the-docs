"""app_gradio.py — the public demo: ask the Ollama docs, or your own PDF.

Thin on purpose: retrieval and answering live in `rag_core.py`, PDF handling in `pdf_upload.py`.
This file is only the interface. That split is what let the logic be tested without installing
Gradio, and it is why this file can be read in one sitting.

Two deliberate UI choices:

* **Blocks, not ChatInterface.** This is a look-up tool, not a conversation. The value is the answer
  *plus the panel showing which chunks were sent and how close they were* — a chat log hides that,
  which is the part that makes the system auditable.
* **Two indexes, labelled differently.** The bundled corpus carries the measured numbers; a visitor's
  upload is labelled **not measured** in the answer itself, not only in a footnote.
"""
from __future__ import annotations

import os

import gradio as gr

import pdf_upload
import rag_core

DEMO_PASSWORD = os.environ.get("DEMO_PASSWORD", "")
_BUNDLED: dict | None = None


def bundled_index() -> dict:
    """Loaded once per process; the first call downloads the embedding model (~100 MB)."""
    global _BUNDLED
    if _BUNDLED is None:
        try:
            _BUNDLED = rag_core.load_bundled_index()
        except rag_core.IndexMissing as exc:
            raise gr.Error(str(exc))
    return _BUNDLED


def on_ask(source_kind, uploaded_pdf, question, k):
    if not question or len(question.strip()) < 3:
        return "Type a question first.", "", "", rag_core.BUNDLED_NOTE

    if source_kind == "Uploaded PDF":
        if not uploaded_pdf:
            return "Upload a PDF first, or switch back to the bundled corpus.", "", "", ""
        try:
            data = open(uploaded_pdf.name, "rb").read()
            pages = pdf_upload.extract_pages(data)
            index = pdf_upload.build_upload(pages, os.path.basename(uploaded_pdf.name))
        except pdf_upload.UploadError as exc:
            return f"**Could not use that PDF.** {exc}", "", "", pdf_upload.LIMITS_TEXT
        note = rag_core.NOT_MEASURED_NOTE
    else:
        index = bundled_index()
        note = rag_core.BUNDLED_NOTE

    try:
        out = rag_core.answer(index, question.strip(), int(k))
    except KeyError:
        return ("The Space is missing its `LLM_API_KEY` secret. Add it in "
                "Settings → Variables and secrets.", "", "", note)

    text = out["text"].strip()
    if not text:
        text = ("**Empty answer.** The call succeeded, but the model spent its whole token budget on "
                "hidden reasoning — a known failure mode at low `max_tokens`.")
    return text, rag_core.sources_markdown(out["hits"]), rag_core.usage_line(out), note


with gr.Blocks(title="Ask the Ollama Docs") as demo:
    gr.Markdown(
        "# Ask the Ollama Docs\n"
        "Answers come **only** from the sections retrieved for your question, and name the section "
        "each claim came from. Ask about the bundled Ollama documentation — or upload your own PDF."
    )

    with gr.Row():
        source_kind = gr.Radio(["Bundled Ollama docs", "Uploaded PDF"], value="Bundled Ollama docs",
                               label="Answer from", scale=3)
        k = gr.Slider(1, 10, value=5, step=1, label="Chunks sent as context (k)", scale=2)

    uploaded = gr.File(label="Your PDF (text layer required — a scan will be refused)",
                       file_types=[".pdf"], visible=False)
    gr.Markdown(pdf_upload.LIMITS_TEXT)

    question = gr.Textbox(label="Question", placeholder="How do I install Ollama on Linux?")
    ask = gr.Button("Ask", variant="primary")

    reply = gr.Markdown(label="Answer")
    panel = gr.Markdown(label="Sources sent as context")
    usage = gr.Markdown()
    provenance = gr.Markdown()

    source_kind.change(lambda v: gr.update(visible=(v == "Uploaded PDF")), source_kind, uploaded)
    ask.click(on_ask, [source_kind, uploaded, question, k], [reply, panel, usage, provenance])

    gr.Markdown(
        "---\n"
        "**What this demo does not prove.** A citation shows a source was *named*, not that the "
        "answer is right. The bundled corpus is public documentation, so a correct answer may come "
        "from the model's memory instead of from retrieval. Distances are cosine distance on "
        "L2-normalised vectors: lower is closer, and the panel lists exactly what the model was given."
    )
    provenance.render(lambda: rag_core.BUNDLED_NOTE)

if __name__ == "__main__":
    demo.launch(auth=(("demo", DEMO_PASSWORD),) if DEMO_PASSWORD else None)
