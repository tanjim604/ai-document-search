"""JSON shapes returned by the ingestion API (shared with the future UI)."""
from datetime import datetime

from pydantic import BaseModel

from app.shared.models.file import File


class FileUploadResponse(BaseModel):
    file_id: str
    filename: str
    extension: str
    mime_type: str
    storage_path: str
    sha256_hash: str
    status: str
    is_exact_duplicate: bool
    duplicate_of: str | None = None

    @classmethod
    def from_record(cls, record: File, duplicate_of: str | None) -> "FileUploadResponse":
        return cls(
            file_id=record.id,
            filename=record.filename,
            extension=record.extension,
            mime_type=record.mime_type,
            storage_path=record.storage_path,
            sha256_hash=record.sha256_hash,
            status=record.processing_status,
            is_exact_duplicate=duplicate_of is not None,
            duplicate_of=duplicate_of,
        )


class FileDetailsResponse(BaseModel):
    file_id: str
    filename: str
    extension: str
    mime_type: str
    storage_path: str
    sha256_hash: str
    status: str
    created_at: datetime

    @classmethod
    def from_record(cls, record: File) -> "FileDetailsResponse":
        return cls(
            file_id=record.id,
            filename=record.filename,
            extension=record.extension,
            mime_type=record.mime_type,
            storage_path=record.storage_path,
            sha256_hash=record.sha256_hash,
            status=record.processing_status,
            created_at=record.created_at,
        )
