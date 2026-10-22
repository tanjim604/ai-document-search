"""
Ingestion business logic. No FastAPI code here, so these functions can be
called from routes, from tests, and from teammates' code.

Functions teammates use:
    get_file(db, file_id)                          -> File or None
    update_processing_status(db, file_id, status)  -> File
    find_files_with_same_hash(db, file_id)         -> list[File]
"""
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.ingestion.file_types import (
    SUPPORTED_TYPES,
    clean_filename,
    content_matches_extension,
    get_extension,
    is_supported,
)
from app.ingestion.hashing import sha256_hex
from app.shared.models.file import File, ProcessingStatus, new_file_id
from app.shared.storage.base import StorageBackend


# ---------------------------------------------------------------- errors ----
class IngestionError(Exception):
    """Base class. status_code is the HTTP code the route should return."""

    status_code = 400


class MissingFilename(IngestionError):
    status_code = 400


class UnsupportedFileType(IngestionError):
    status_code = 415


class EmptyFile(IngestionError):
    status_code = 400


class FileTooLarge(IngestionError):
    status_code = 413


class ContentMismatch(IngestionError):
    status_code = 400


class FileRecordNotFound(Exception):
    pass


# ---------------------------------------------------------------- upload ----
@dataclass
class IngestResult:
    file: File
    duplicate_of: str | None  # file_id of the first identical upload, if any


def ingest_file(
    db: Session,
    storage: StorageBackend,
    original_filename: str | None,
    data: bytes,
    max_size_bytes: int,
) -> IngestResult:
    """
    Validate, hash, store and record one uploaded file.

    Order matters: all checks happen BEFORE anything is saved, so a rejected
    upload leaves nothing behind on disk or in the database.
    """
    filename = clean_filename(original_filename)
    if not filename:
        raise MissingFilename("The upload has no filename.")

    extension = get_extension(filename)
    if not is_supported(extension):
        allowed = ", ".join(sorted(SUPPORTED_TYPES))
        shown = f".{extension}" if extension else "files with no extension"
        raise UnsupportedFileType(f"{shown} is not supported. Allowed: {allowed}.")

    if len(data) == 0:
        raise EmptyFile("The file is empty.")

    if len(data) > max_size_bytes:
        raise FileTooLarge(f"The file is larger than {max_size_bytes} bytes.")

    if not content_matches_extension(extension, data):
        raise ContentMismatch(
            f"The file's content does not look like a .{extension} file."
        )

    file_hash = sha256_hex(data)
    earlier_copy = _first_file_with_hash(db, file_hash)

    file_id = new_file_id()
    storage_path = storage.save(file_id, extension, data)

    record = File(
        id=file_id,
        filename=filename,
        extension=extension,
        mime_type=SUPPORTED_TYPES[extension],
        storage_path=storage_path,
        sha256_hash=file_hash,
        processing_status=ProcessingStatus.UPLOADED.value,
    )
    try:
        db.add(record)
        db.commit()
    except Exception:
        # If the database insert fails, remove the saved file so storage and
        # database never disagree.
        db.rollback()
        storage.delete(storage_path)
        raise
    db.refresh(record)

    return IngestResult(file=record, duplicate_of=earlier_copy.id if earlier_copy else None)


# ------------------------------------------------- functions for teammates ----
def get_file(db: Session, file_id: str) -> File | None:
    """Return the File row for file_id, or None if it does not exist."""
    return db.get(File, file_id)


def update_processing_status(
    db: Session, file_id: str, new_status: ProcessingStatus | str
) -> File:
    """
    Change a file's processing_status. Diya and Zahid call this, e.g.

        update_processing_status(db, file_id, ProcessingStatus.EXTRACTED)

    Raises ValueError for a status that is not in ProcessingStatus, and
    FileRecordNotFound for an unknown file_id.
    """
    status = ProcessingStatus(new_status)  # raises ValueError if unknown
    record = get_file(db, file_id)
    if record is None:
        raise FileRecordNotFound(file_id)
    record.processing_status = status.value
    db.commit()
    db.refresh(record)
    return record


def find_files_with_same_hash(db: Session, file_id: str) -> list[File]:
    """
    Other files whose bytes are identical to this one (same SHA-256),
    oldest first. Zahid uses this to create exact_duplicate SimilarityMatch rows.
    """
    record = get_file(db, file_id)
    if record is None:
        raise FileRecordNotFound(file_id)
    query = (
        select(File)
        .where(File.sha256_hash == record.sha256_hash, File.id != record.id)
        .order_by(File.created_at)
    )
    return list(db.scalars(query))


def _first_file_with_hash(db: Session, file_hash: str) -> File | None:
    query = select(File).where(File.sha256_hash == file_hash).order_by(File.created_at).limit(1)
    return db.scalars(query).first()
