"""Symmetric document similarity using both documents' complete chunk sets."""
from dataclasses import dataclass

import numpy as np
from qdrant_client import QdrantClient, models

from app.ai_indexing.similarity import classify_similarity
from app.ai_indexing.vector_store import COLLECTION_NAME, ensure_collection


@dataclass(frozen=True)
class DocumentMatch:
    file_id: str
    similarity_score: float
    match_type: str


def _normalise(vectors):
    matrix = np.asarray(vectors, dtype=float)
    if matrix.ndim != 2 or not np.isfinite(matrix).all():
        raise ValueError("Chunk vectors must be a finite matrix.")
    lengths = np.linalg.norm(matrix, axis=1, keepdims=True)
    if (lengths == 0).any():
        raise ValueError("Chunk vectors must have non-zero magnitude.")
    return matrix / lengths


def find_document_matches(
    client: QdrantClient,
    *,
    file_id: str,
    vectors: list[list[float]],
    near_duplicate_threshold: float,
    related_threshold: float,
    skip_file_ids: set[str] = frozenset(),
) -> list[DocumentMatch]:
    """Use the lower of the two directional mean best-chunk similarities.

    A short excerpt of a larger document must not become a near duplicate just
    because all of the excerpt occurs in the larger document. Scrolling complete
    chunk sets also avoids losing candidates behind a top-ten chunk cutoff.
    This exhaustive comparison suits the project's small demonstration library.
    """
    if not 0 <= related_threshold < near_duplicate_threshold <= 1:
        raise ValueError("Require 0 <= related threshold < near-duplicate threshold <= 1.")
    vectors = [v for v in vectors if v]
    if not vectors:
        return []
    source = _normalise(vectors)
    ensure_collection(client)
    candidates = {}
    offset = None
    while True:
        points, offset = client.scroll(
            collection_name=COLLECTION_NAME,
            scroll_filter=models.Filter(must_not=[models.FieldCondition(
                key="file_id", match=models.MatchValue(value=file_id),
            )]),
            limit=256, offset=offset, with_vectors=True, with_payload=["file_id"],
        )
        for point in points:
            other = (point.payload or {}).get("file_id")
            if isinstance(other, str) and other and other != file_id and other not in skip_file_ids:
                candidates.setdefault(other, []).append(point.vector)
        if offset is None:
            break

    matches = []
    for other, chunks in candidates.items():
        scores = np.clip(source @ _normalise(chunks).T, 0.0, 1.0)
        score = float(min(scores.max(axis=1).mean(), scores.max(axis=0).mean()))
        label = classify_similarity(score, near_duplicate_threshold, related_threshold)
        if label != "unrelated":
            matches.append(DocumentMatch(other, score, label))
    return sorted(matches, key=lambda match: (-match.similarity_score, match.file_id))
