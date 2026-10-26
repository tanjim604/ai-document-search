"""
Document-level similarity between a new file and files already indexed.

AI indexing's search_similar_files() labels a file from its single best chunk,
so two unrelated documents that share one boilerplate paragraph would look like
near-duplicates. Here a candidate file is scored as the AVERAGE, over all of the
new file's chunks, of each chunk's best match in that candidate (0 when the
candidate has nothing close). Only files that are alike overall score high.
"""
from dataclasses import dataclass

from qdrant_client import QdrantClient, models

from app.ai_indexing.similarity import classify_similarity
from app.ai_indexing.vector_store import COLLECTION_NAME, ensure_collection

CANDIDATES_PER_CHUNK = 10


@dataclass(frozen=True)
class DocumentMatch:
    file_id: str
    similarity_score: float
    match_type: str  # near_duplicate or related


def find_document_matches(
    client: QdrantClient,
    *,
    file_id: str,
    vectors: list[list[float]],
    near_duplicate_threshold: float,
    related_threshold: float,
    skip_file_ids: set[str] = frozenset(),
) -> list[DocumentMatch]:
    """Compare a file's chunk vectors with every other indexed file."""
    vectors = [v for v in vectors if v]
    if not vectors:
        return []
    ensure_collection(client)

    not_this_file = models.Filter(
        must_not=[models.FieldCondition(key="file_id", match=models.MatchValue(value=file_id))]
    )
    best_per_file: dict[str, list[float]] = {}  # candidate -> best score per chunk
    for position, vector in enumerate(vectors):
        response = client.query_points(
            collection_name=COLLECTION_NAME,
            query=vector,
            query_filter=not_this_file,
            limit=CANDIDATES_PER_CHUNK,
            with_payload=["file_id"],
        )
        for point in response.points:
            other = (point.payload or {}).get("file_id")
            if not other or other in skip_file_ids:
                continue
            scores = best_per_file.setdefault(other, [0.0] * len(vectors))
            scores[position] = max(scores[position], float(point.score))

    matches = []
    for other, scores in best_per_file.items():
        document_score = min(1.0, sum(scores) / len(vectors))
        label = classify_similarity(
            document_score,
            near_duplicate_threshold=near_duplicate_threshold,
            related_threshold=related_threshold,
        )
        if label != "unrelated":
            matches.append(DocumentMatch(other, document_score, label))
    return sorted(matches, key=lambda m: m.similarity_score, reverse=True)
