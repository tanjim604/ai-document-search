"""
Ingestion API endpoints.

    POST /files            upload one file (multipart form field name: "file")
    GET  /files/{file_id}  processing status and details for one file
"""
from fastapi import APIRouter, Depends, HTTPException, UploadFile
from sqlalchemy.orm import Session

from app.ingestion.schemas import FileDetailsResponse, FileUploadResponse
from app.ingestion.service import (
    FileTooLarge,
    IngestionError,
    get_file,
    ingest_file,
)
from app.shared.config.settings import Settings, get_settings
from app.shared.database import get_db
from app.shared.storage import StorageBackend, get_storage

router = APIRouter(prefix="/files", tags=["files"])

READ_CHUNK_BYTES = 1024 * 1024  # read uploads 1 MB at a time


def read_upload_limited(upload: UploadFile, max_bytes: int) -> bytes:
    """
    Read the uploaded file, but stop as soon as it goes over the size limit,
    so a huge upload is never fully loaded into memory.
    """
    chunks: list[bytes] = []
    total = 0
    while chunk := upload.file.read(READ_CHUNK_BYTES):
        total += len(chunk)
        if total > max_bytes:
            raise FileTooLarge(f"The file is larger than {max_bytes} bytes.")
        chunks.append(chunk)
    return b"".join(chunks)


# A plain `def` (not `async def`): FastAPI runs it in a worker thread, so the
# blocking disk and database calls do not freeze the server.
@router.post("", status_code=201, response_model=FileUploadResponse)
def upload_file(
    file: UploadFile,
    db: Session = Depends(get_db),
    storage: StorageBackend = Depends(get_storage),
    settings: Settings = Depends(get_settings),
) -> FileUploadResponse:
    try:
        data = read_upload_limited(file, settings.max_upload_size_bytes)
        result = ingest_file(
            db, storage, file.filename, data, settings.max_upload_size_bytes
        )
    except IngestionError as error:
        raise HTTPException(status_code=error.status_code, detail=str(error))
    finally:
        file.file.close()

    return FileUploadResponse.from_record(result.file, result.duplicate_of)


@router.get("/{file_id}", response_model=FileDetailsResponse)
def get_file_details(file_id: str, db: Session = Depends(get_db)) -> FileDetailsResponse:
    record = get_file(db, file_id)
    if record is None:
        raise HTTPException(status_code=404, detail=f"No file with id {file_id}.")
    return FileDetailsResponse.from_record(record)
