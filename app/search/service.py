"""Semantic search: embed the query, find close chunks, return one result per file."""
from dataclasses import dataclass

from qdrant_client import QdrantClient, models
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.ai_indexing.embeddings import embed_text
from app.ai_indexing.vector_store import COLLECTION_NAME, ensure_collection
from app.shared.models.document_content import DocumentContent
from app.shared.models.file import File, ProcessingStatus

CHUNKS_PER_RESULT = 5  # fetch extra chunks so grouping by file still fills `limit`
EXCERPT_CHARS = 300


@dataclass(frozen=True)
class SearchResult:
    file_id: str
    filename: str
    extension: str
    storage_path: str
    summary: str | None
    score: float
    matched_excerpt: str


def make_excerpt(text: str) -> str:
    flat = " ".join(text.split())
    return flat if len(flat) <= EXCERPT_CHARS else flat[:EXCERPT_CHARS].rstrip() + "..."


def search_documents(
    db: Session,
    client: QdrantClient,
    query: str,
    *,
    limit: int = 10,
    min_score: float = 0.2,
    extension: str | None = None,
) -> list[SearchResult]:
    ensure_collection(client)
    conditions = []
    if extension:
        conditions.append(models.FieldCondition(
            key="extension", match=models.MatchValue(value=extension.lower().lstrip("."))
        ))
    response = client.query_points(
        collection_name=COLLECTION_NAME,
        query=embed_text(query),  # same model as the documents
        query_filter=models.Filter(must=conditions) if conditions else None,
        limit=limit * CHUNKS_PER_RESULT,
        score_threshold=min_score,
        with_payload=True,
    )

    best: dict[str, tuple[float, str]] = {}  # file_id -> (best chunk score, its text)
    for point in response.points:  # points arrive best-first
        payload = point.payload or {}
        file_id = payload.get("file_id")
        if file_id and file_id not in best:
            best[file_id] = (float(point.score), payload.get("text", ""))
    if not best:
        return []

    files = {
        f.id: f for f in db.scalars(select(File).where(File.id.in_(best)))
    }
    summaries = dict(db.execute(
        select(DocumentContent.file_id, DocumentContent.summary)
        .where(DocumentContent.file_id.in_(best))
    ).all())

    results = []
    for file_id, (score, text) in best.items():
        record = files.get(file_id)
        # Skip vectors whose file was removed or is being re-processed.
        if record is None or record.processing_status != ProcessingStatus.INDEXED.value:
            continue
        results.append(SearchResult(
            file_id=file_id, filename=record.filename, extension=record.extension,
            storage_path=record.storage_path, summary=summaries.get(file_id),
            score=round(score, 4), matched_excerpt=make_excerpt(text),
        ))
    return results[:limit]
