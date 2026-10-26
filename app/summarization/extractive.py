"""
Local, key-free summarizer (Tanjim, integration).

It keeps the few sentences that best represent the whole document: every
sentence is embedded with the project's embedding model, and the sentences
closest to the document's average embedding are kept, in their original order.

This is a stand-in until the AI indexing module adds its own summarizer.
To swap it, change `summarize_text` in app/summarization/__init__.py; the rest
of the system only calls that one function.
"""
import re

import numpy as np

from app.ai_indexing.embeddings import embed_chunks

MAX_SENTENCES = 3
MIN_SENTENCE_CHARS = 25     # skips headings and page numbers
MAX_SENTENCE_CHARS = 400    # skips table dumps with no sentence breaks
MAX_CANDIDATES = 300        # keeps embedding time bounded for very long files

_SENTENCE_BREAK = re.compile(r"(?<=[.!?])\s+")


def split_sentences(text: str) -> list[str]:
    flat = " ".join(text.split())
    sentences = [s.strip() for s in _SENTENCE_BREAK.split(flat)]
    return [s for s in sentences if MIN_SENTENCE_CHARS <= len(s) <= MAX_SENTENCE_CHARS]


def summarize_extractive(text: str, max_sentences: int = MAX_SENTENCES) -> str:
    """Return up to `max_sentences` representative sentences ('' if none found)."""
    sentences = split_sentences(text)[:MAX_CANDIDATES]
    if not sentences:
        # No proper sentences (a CSV, say): fall back to the opening text.
        return " ".join(text.split())[:300].strip()
    if len(sentences) <= max_sentences:
        return " ".join(sentences)

    vectors = np.asarray(embed_chunks(sentences))
    centroid = vectors.mean(axis=0)
    scores = vectors @ centroid  # vectors are normalised, so this ranks by cosine
    best = sorted(np.argsort(scores)[::-1][:max_sentences])
    return " ".join(sentences[i] for i in best)
