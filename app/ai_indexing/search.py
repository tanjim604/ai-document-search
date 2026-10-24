
from dataclasses import dataclass

from qdrant_client import QdrantClient, models

from app.ai_indexing.embeddings import embed_chunks
from app.ai_indexing.similarity import classify_similarity
from app.ai_indexing.vector_store import COLLECTION_NAME, ensure_collection


@dataclass(frozen=True)
class SimilarFile:
    file_id: str
    filename: str
    extension: str
    similarity_score: float
    match_type: str
    matched_chunk_text: str


def search_similar_files(
    client: QdrantClient,
    *,
    chunks: list[str],
    source_file_id: str | None = None,
    limit_per_chunk: int = 10,
    near_duplicate_threshold: float = 0.95,
    related_threshold: float = 0.75,
) -> list[SimilarFile]:
    """Find candidate documents using their most similar indexed chunks."""
    if not chunks:
        raise ValueError("At least one query chunk is required.")

    if limit_per_chunk < 1:
        raise ValueError("limit_per_chunk must be at least 1.")

    if near_duplicate_threshold <= related_threshold:
        raise ValueError(
            "Near-duplicate threshold must exceed related threshold."
        )

    vectors = embed_chunks(chunks)
    candidates: dict[str, SimilarFile] = {}

    ensure_collection(client)

    for text, vector in zip(chunks, vectors):
        if not isinstance(text, str) or not text.strip() or not vector:
            continue

        query_filter = None
        if source_file_id:
            query_filter = models.Filter(
                must_not=[
                    models.FieldCondition(
                        key="file_id",
                        match=models.MatchValue(value=source_file_id),
                    )
                ]
            )

        response = client.query_points(
            collection_name=COLLECTION_NAME,
            query=vector,
            query_filter=query_filter,
            limit=limit_per_chunk,
            with_payload=True,
        )

        for point in response.points:
            payload = point.payload or {}
            matched_file_id = payload.get("file_id")
            filename = payload.get("filename")
            extension = payload.get("extension")
            matched_text = payload.get("text")

            if not all(
                isinstance(value, str) and value.strip()
                for value in (
                    matched_file_id,
                    filename,
                    extension,
                    matched_text,
                )
            ):
                continue

            if source_file_id and matched_file_id == source_file_id:
                continue

            score = float(point.score)
            match_type = classify_similarity(
                score,
                near_duplicate_threshold=near_duplicate_threshold,
                related_threshold=related_threshold,
            )

            candidate = SimilarFile(
                file_id=matched_file_id,
                filename=filename,
                extension=extension,
                similarity_score=score,
                match_type=match_type,
                matched_chunk_text=matched_text,
            )

            previous = candidates.get(matched_file_id)
            if (
                previous is None
                or candidate.similarity_score > previous.similarity_score
            ):
                candidates[matched_file_id] = candidate

    return sorted(
        candidates.values(),
        key=lambda item: item.similarity_score,
        reverse=True,
    )

