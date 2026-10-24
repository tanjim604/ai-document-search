
from dataclasses import dataclass

from qdrant_client import QdrantClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.ai_indexing.embeddings import embed_chunks
from app.ai_indexing.vector_store import store_chunk
from app.ingestion.service import (
    FileRecordNotFound,
    find_files_with_same_hash,
    get_file,
    update_processing_status,
)
from app.shared.models.file import File, ProcessingStatus
from app.shared.models.similarity_match import SimilarityMatch


@dataclass(frozen=True)
class IndexingResult:
    file_id: str
    chunks_received: int
    chunks_indexed: int
    skipped_empty_chunks: int


@dataclass(frozen=True)
class DocumentIndexingResult:
    indexing: IndexingResult
    exact_duplicate_file_ids: tuple[str, ...]


def index_chunks(
    client: QdrantClient,
    *,
    file_id: str,
    chunks: list[str],
    filename: str,
    extension: str,
) -> IndexingResult:
    """Embed and store non-empty chunks in their original positions."""
    if not isinstance(file_id, str) or not file_id.strip():
        raise ValueError("file_id must not be empty.")
    if not isinstance(filename, str) or not filename.strip():
        raise ValueError("filename must not be empty.")
    if not isinstance(extension, str) or not extension.strip():
        raise ValueError("extension must not be empty.")
    if not chunks:
        raise ValueError("At least one chunk is required.")

    vectors = embed_chunks(chunks)
    if len(vectors) != len(chunks):
        raise ValueError("Embedding count must match the chunk count.")

    indexed = 0
    skipped = 0

    for index, (text, vector) in enumerate(zip(chunks, vectors)):
        if not isinstance(text, str) or not text.strip() or not vector:
            skipped += 1
            continue

        store_chunk(
            client,
            file_id=file_id,
            chunk_id=f"{file_id}_chunk_{index}",
            chunk_index=index,
            text=text.strip(),
            filename=filename,
            extension=extension.lower().lstrip("."),
            vector=vector,
        )
        indexed += 1

    if indexed == 0:
        raise ValueError("Document has no non-empty chunks to index.")

    return IndexingResult(
        file_id=file_id,
        chunks_received=len(chunks),
        chunks_indexed=indexed,
        skipped_empty_chunks=skipped,
    )


def index_document(
    db: Session,
    client: QdrantClient,
    *,
    file_id: str,
    chunks: list[str],
    filename: str,
    extension: str,
) -> DocumentIndexingResult:
    """
    Index a document, record exact duplicates, and update its status.

    The caller supplies extracted chunks. Extraction and text persistence
    are handled by the extraction component.
    """
    if get_file(db, file_id) is None:
        raise FileRecordNotFound(file_id)

    try:
        update_processing_status(db, file_id, ProcessingStatus.INDEXING)

        result = index_chunks(
            client,
            file_id=file_id,
            chunks=chunks,
            filename=filename,
            extension=extension,
        )

        duplicates = find_files_with_same_hash(db, file_id)
        duplicate_ids = []

        for duplicate in duplicates:
            duplicate_ids.append(duplicate.id)

            existing = db.scalar(
                select(SimilarityMatch).where(
                    SimilarityMatch.source_file_id == file_id,
                    SimilarityMatch.matched_file_id == duplicate.id,
                    SimilarityMatch.match_type == "exact_duplicate",
                )
            )

            if existing is None:
                db.add(
                    SimilarityMatch(
                        source_file_id=file_id,
                        matched_file_id=duplicate.id,
                        similarity_score=1.0,
                        match_type="exact_duplicate",
                    )
                )

        db.commit()
        update_processing_status(db, file_id, ProcessingStatus.INDEXED)

        return DocumentIndexingResult(
            indexing=result,
            exact_duplicate_file_ids=tuple(duplicate_ids),
        )

    except Exception:
        db.rollback()

        # Preserve the original error even if status recovery also fails.
        try:
            if get_file(db, file_id) is not None:
                update_processing_status(
                    db, file_id, ProcessingStatus.FAILED
                )
        except Exception:
            db.rollback()

        raise
