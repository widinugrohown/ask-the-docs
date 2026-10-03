"""check_questions.py — verify every gold-source pattern in eval_questions.txt really exists.

Run this before using the question set to measure anything. A gold pattern derived from memory
rather than from `grep` looks plausible and scores 0/N, which then looks like a broken retriever.
The first draft of eval_questions.txt had 9 of 12 patterns wrong; this script is why that was caught.

What it checks against: the **heading paths** the chunker produces (`Linux > Install`), rebuilt by
walking the corpus and keeping a heading stack — not literal strings in the file. Checking the raw
corpus for a path-shaped pattern reports a false failure for every correct entry, which is how the
first version of this script lied (10 of 24 "wrong" were actually right).

Usage:
    python check_questions.py                 # checks data/eval_questions.txt
    python check_questions.py other.txt       # any file in the same format

Exit code 0 = every pattern resolves to a real heading path. Exit code 1 = at least one does not.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

CORPUS = Path("data/ollama-docs-corpus.md")
QFILES = sys.argv[1:] or ["data/eval_questions.txt"]
SEP = " > "


def heading_paths(text: str) -> set[str]:
    """Every heading path in the corpus, built the way the chunker builds them.

    Fenced code blocks are skipped: shell and Python comments start with `#`, so a naive heading
    scan cuts a code block open at `# comment` and invents paths that do not exist.
    """
    stack: list[str] = []
    paths: set[str] = set()
    in_fence = False
    for line in text.splitlines():
        if line.lstrip().startswith("```"):
            in_fence = not in_fence
            continue
        if in_fence:
            continue
        m = re.match(r"^(#{1,4})\s+(.+?)\s*$", line)
        if not m:
            continue
        level, title = len(m.group(1)), m.group(2).strip()
        stack = stack[: level - 1]
        stack.append(title)
        paths.add(SEP.join(stack))
    return paths


def load(path: Path) -> list[tuple[str, str]]:
    out = []
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "|" not in line:
            continue
        q, pat = (x.strip() for x in line.split("|", 1))
        if q and pat:
            out.append((q, pat))
    return out


def main() -> int:
    if not CORPUS.exists():
        print(f"corpus not found: {CORPUS} (run from the project root)")
        return 2

    text = CORPUS.read_text(encoding="utf-8")
    paths = heading_paths(text)
    print(f"heading paths in corpus: {len(paths)} (code fences skipped)")

    failures: list[tuple[str, str]] = []
    total = 0
    for qf in QFILES:
        path = Path(qf)
        rows = load(path)
        print(f"\n{path} — {len(rows)} questions")
        for q, pat in rows:
            total += 1
            if pat in paths:
                mark = "ok (path)"
            elif pat in text:
                mark = "ok (text)"
            else:
                mark = "NOT FOUND"
                failures.append((q, pat))
            print(f"  {mark:>10}  {pat[:60]:<62} {q[:42]}")

    print(f"\n{total} patterns checked · {total - len(failures)} found · {len(failures)} wrong")
    if failures:
        tails = sorted({p.split(SEP)[-1] for p in paths})
        print("\nPatterns that must be fixed before measuring — a gold pattern that does not exist")
        print("scores 0/N and looks like a retrieval failure instead of a bad question set:")
        for q, pat in failures:
            key = pat.split(SEP)[-1].split()[0].lower()[:5]
            near = [t for t in tails if t.lower().startswith(key)][:3]
            print(f"  {pat!r}\n      question: {q}\n      similar headings: {near}")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
