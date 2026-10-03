# Credentials — what to give the VPS, and where to paste it

Two tokens are needed **only so the agent can create the repo and the Space from the VPS**. If you
would rather upload by hand, no token is needed at all — the steps for that path are at the bottom.

## 1. GitHub token — to create and push `ask-the-docs`

Open `https://github.com/settings/personal-access-tokens/new` (fine-grained, **not** classic).

| Field | Value | Why |
|---|---|---|
| Token name | `hermes-vps-rag` | so you can find and revoke it later |
| Expiration | 90 days | short enough to be harmless |
| Repository access | **All repositories** | the repo does not exist yet, and "only select repositories" cannot select a repo that has not been created |
| Permissions → **Administration** | **Read and write** | required to *create* a repository (`POST /user/repos`); this is the strongest scope in the set |
| Permissions → **Contents** | **Read and write** | required to push commits |

Leave every other permission at *No access*. Then **Generate token** and copy it (it starts with
`github_pat_`, ~93 characters).

> The `Administration: write` scope lets the token change repository settings across the account.
> That is why it expires in 90 days and why the right move is to **revoke it once the repo is pushed**.

## 2. Hugging Face token — to create the Space and upload the files

Open `https://huggingface.co/settings/tokens` → **New token** → type **Write** → name `hermes-vps-rag`.
No finer permission granularity exists for user tokens; *Write* is what allows creating a Space and
pushing files. Copy it (~37 characters, starts with `hf_`).

## 3. Paste them — in YOUR terminal, not in chat

Values are read with echo off, so they never appear on screen and never enter this conversation.

```bash
bash ~/.hermes/profiles/learn/bin/add-tokens.sh
```

It backs up `.env` first, replaces any existing `GITHUB_TOKEN` / `HF_TOKEN` lines, sets the file to
`chmod 600`, and prints only the **lengths** — compare them with what GitHub and Hugging Face showed.

## 4. The LLM key: do NOT give it to the VPS

The Space needs `LLM_API_KEY` to answer questions. Add it yourself in the Space settings:

**Space → Settings → Variables and secrets → New secret**
`LLM_API_KEY` = your Ollama Cloud key

Add these as ordinary **Variables** in the same panel:

| Name | Value |
|---|---|
| `LLM_BASE_URL` | `https://ollama.com/v1` |
| `LLM_MODEL` | `deepseek-v4.1-flash` |
| `DEMO_PASSWORD` | a passphrase you choose (the demo is public and rate-limited) |

That way no model key ever leaves your hands, and the VPS tokens cannot spend your inference budget.

## The no-token path

1. `https://huggingface.co/new-space` → name `ask-the-docs`, SDK **Gradio**, hardware **CPU basic
   (free)**, visibility **Public**, license MIT.
2. Upload these files through **Files → Upload files**:
   `app_gradio.py`, `rag_core.py`, `embed.py`, `pdf_upload.py`, `chunker.py`, `requirements.txt`,
   `README-space.md` (rename to `README.md` in the Space), and the whole `data/` folder.
3. Add the secret/variables from step 4. The Space rebuilds itself on every upload.

## After it works

- Revoke the GitHub token if you used the API path, or shorten its expiry.
- Move the repo files to your Mac for day-to-day editing (`git clone`).
