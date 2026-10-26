"""
The full document pipeline (Tanjim, integration). Ties the four modules together:

    uploaded -> extracting -> extracted -> indexing -> indexed
                  |-> ocr_needed (no text)      any step -> failed

    1. extraction  (Diya)   extract_and_save()      text + ordered chunks in the database
    2. summary     (Tanjim) summarize_text()        saved on DocumentContent.summary
    3. indexing    (Jahid)  index_document()        chunk vectors in Qdrant, exact duplicates
    4. similarity  (Tanjim) find_document_matches() near_duplicate / related records
"""
from dataclasses import dataclass, field

from qdrant_client import QdrantClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.ai_indexing.embeddings import embed_chunks
from app.ai_indexing.service import index_document
from app.ai_indexing.vector_store import ensure_collection
from app.extraction.service import extract_and_save
from app.ingestion.service import FileRecordNotFound, get_file, update_processing_status
from app.pipeline.similarity import find_document_matches
from app.shared.config.settings import get_settings
from app.shared.models.document_chunk import DocumentChunk
from app.shared.models.document_content import DocumentContent
from app.shared.models.file import ProcessingStatus
from app.shared.models.similarity_match import SimilarityMatch
from app.summarization import summarize_text


@dataclass
class PipelineResult:
    file_id: str
    status: str
    error: str | None = None
    chunks: int = 0
    summary: str | None = None
    matches: list[dict] = field(default_factory=list)


def process_document(db: Session, client: QdrantClient, file_id: str) -> PipelineResult:
    """Run every stage for one uploaded file. Never raises for a bad document:
    the problem is recorded in the file's status and returned in the result."""
    if get_file(db, file_id) is None:
        raise FileRecordNotFound(file_id)

    try:
        extracted = extract_and_save(db, file_id)
    except Exception as error:  # extract_and_save already marked the file failed
        return PipelineResult(file_id, ProcessingStatus.FAILED.value, error=str(error))

    if extracted["status"] == "ocr_needed":
        update_processing_status(db, file_id, ProcessingStatus.OCR_NEEDED)
        return PipelineResult(
            file_id, ProcessingStatus.OCR_NEEDED.value,
            error="No extractable text. OCR is needed.",
        )
    if extracted["status"] != "extracted":
        return PipelineResult(
            file_id, ProcessingStatus.FAILED.value, error=extracted.get("error")
        )

    try:
        record = get_file(db, file_id)
        chunks = [
            row.text
            for row in db.scalars(
                select(DocumentChunk)
                .where(DocumentChunk.file_id == file_id)
                .order_by(DocumentChunk.chunk_index)
            )
        ]
        content = db.get(DocumentContent, file_id)
        content.summary = summarize_text(content.raw_text)
        db.commit()

        # index_chunks() writes straight to Qdrant and never creates the collection,
        # so a first upload on an empty Qdrant would fail without this.
        ensure_collection(client)
        index_document(
            db, client,
            file_id=file_id, chunks=chunks,
            filename=record.filename, extension=record.extension,
        )
        matches = record_similarity_matches(db, client, file_id, chunks)
    except Exception as error:  # index_document marks failed; cover the other steps
        db.rollback()
        update_processing_status(db, file_id, ProcessingStatus.FAILED)
        return PipelineResult(file_id, ProcessingStatus.FAILED.value, error=str(error))

    return PipelineResult(
        file_id, ProcessingStatus.INDEXED.value,
        chunks=len(chunks), summary=content.summary, matches=matches,
    )


def record_similarity_matches(
    db: Session, client: QdrantClient, file_id: str, chunks: list[str]
) -> list[dict]:
    """Save exact_duplicate (already written by indexing), near_duplicate and
    related matches for this file, and return them all."""
    settings = get_settings()
    existing = {
        row.matched_file_id: row
        for row in db.scalars(
            select(SimilarityMatch).where(SimilarityMatch.source_file_id == file_id)
        )
    }
    exact_ids = {
        other for other, row in existing.items() if row.match_type == "exact_duplicate"
    }

    for match in find_document_matches(
        client,
        file_id=file_id,
        vectors=embed_chunks(chunks),
        near_duplicate_threshold=settings.near_duplicate_threshold,
        related_threshold=settings.related_threshold,
        skip_file_ids=exact_ids,
    ):
        if match.file_id in existing:
            continue
        row = SimilarityMatch(
            source_file_id=file_id,
            matched_file_id=match.file_id,
            similarity_score=match.similarity_score,
            match_type=match.match_type,
        )
        db.add(row)
        existing[match.file_id] = row
    db.commit()
    return [
        {"file_id": other, "match_type": row.match_type, "score": row.similarity_score}
        for other, row in existing.items()
    ]
