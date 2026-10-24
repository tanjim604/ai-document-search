"""
The File table: one row per uploaded file.

This is part of the SHARED DATA CONTRACT (docs/api-contract.md).
Owner: Tahmid. Do not rename or remove columns without telling the whole team,
because Diya, Zahid and Tanjim all read this table.

Contract fields:
    id, filename, extension, mime_type, storage_path,
    sha256_hash, processing_status, created_at
"""
import uuid
from datetime import datetime, timezone
from enum import Enum

from sqlalchemy import DateTime, String
from sqlalchemy.orm import Mapped, mapped_column

from app.shared.models.base import Base


class ProcessingStatus(str, Enum):
    """
    Where a file is in the pipeline.

        uploaded -> extracting -> extracted -> indexing -> indexed
                         (any step can go to) failed

    Who sets what:
        uploaded              Tahmid (ingestion)
        extracting, extracted Diya   (extraction)
        indexing, indexed     Zahid  (AI indexing)
        failed                whoever hit the error

    The database column is a plain string (not a database ENUM), so the team
    can add a new value here (for example "ocr_needed") without a migration.
    """

    UPLOADED = "uploaded"
    EXTRACTING = "extracting"
    EXTRACTED = "extracted"
    INDEXING = "indexing"
    INDEXED = "indexed"
    FAILED = "failed"


def new_file_id() -> str:
    """Create a unique file_id such as 'f_3f2a9c...'. Every service uses this ID."""
    return f"f_{uuid.uuid4().hex}"


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class File(Base):
    __tablename__ = "files"

    id: Mapped[str] = mapped_column(String(40), primary_key=True, default=new_file_id)

    # Original name as the user uploaded it (folder parts removed). NOT unique.
    filename: Mapped[str] = mapped_column(String(255), nullable=False)

    # Lower-case, no dot: "pdf", "docx", "txt", "csv", "xlsx", "png", "jpg", "jpeg"
    extension: Mapped[str] = mapped_column(String(10), nullable=False, index=True)

    # MIME type confirmed from the file's content, e.g. "application/pdf"
    mime_type: Mapped[str] = mapped_column(String(100), nullable=False)

    # Where the original file is saved, e.g. "data/uploads/pdf/f_3f2a....pdf".
    # Always read it through the storage adapter (app.shared.storage).
    storage_path: Mapped[str] = mapped_column(String(500), nullable=False, unique=True)

    # SHA-256 fingerprint of the file bytes (64 hex characters).
    # Indexed but NOT unique: an identical re-upload gets its own row so that
    # Zahid can record it as an exact duplicate.
    sha256_hash: Mapped[str] = mapped_column(String(64), nullable=False, index=True)

    processing_status: Mapped[str] = mapped_column(
        String(20), nullable=False, default=ProcessingStatus.UPLOADED.value, index=True
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now
    )

    def __repr__(self) -> str:
        return f"<File {self.id} {self.filename!r} status={self.processing_status}>"
