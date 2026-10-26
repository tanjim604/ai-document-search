"""
Pipeline endpoints (Tanjim).

    POST /files/{file_id}/process   run (or re-run) extraction, summary and indexing
    GET  /files/{file_id}/similar   duplicate and related files for one file
    GET  /files                     list uploaded files and their status
"""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from qdrant_client import QdrantClient
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.ingestion.schemas import FileDetailsResponse
from app.ingestion.service import FileRecordNotFound, get_file
from app.pipeline.dependencies import get_qdrant
from app.pipeline.service import process_document
from app.shared.database import get_db
from app.shared.models.file import File
from app.shared.models.similarity_match import SimilarityMatch

router = APIRouter(prefix="/files", tags=["pipeline"])


class ProcessResponse(BaseModel):
    file_id: str
    status: str
    error: str | None = None
    chunks: int = 0
    summary: str | None = None


class SimilarFile(BaseModel):
    file_id: str
    filename: str
    match_type: str  # exact_duplicate, near_duplicate or related
    score: float


class SimilarResponse(BaseModel):
    file_id: str
    matches: list[SimilarFile]


@router.get("", response_model=list[FileDetailsResponse])
def list_files(limit: int = 100, offset: int = 0, db: Session = Depends(get_db)):
    query = select(File).order_by(File.created_at.desc()).limit(min(limit, 500)).offset(offset)
    return [FileDetailsResponse.from_record(f) for f in db.scalars(query)]


@router.post("/{file_id}/process", response_model=ProcessResponse)
def process_file_now(
    file_id: str, db: Session = Depends(get_db), client: QdrantClient = Depends(get_qdrant)
):
    try:
        result = process_document(db, client, file_id)
    except FileRecordNotFound:
        raise HTTPException(status_code=404, detail=f"No file with id {file_id}.")
    return ProcessResponse(
        file_id=result.file_id, status=result.status, error=result.error,
        chunks=result.chunks, summary=result.summary,
    )


@router.get("/{file_id}/similar", response_model=SimilarResponse)
def get_similar_files(file_id: str, db: Session = Depends(get_db)):
    if get_file(db, file_id) is None:
        raise HTTPException(status_code=404, detail=f"No file with id {file_id}.")
    rows = db.scalars(
        select(SimilarityMatch).where(
            or_(SimilarityMatch.source_file_id == file_id,
                SimilarityMatch.matched_file_id == file_id)
        )
    )
    matches = []
    for row in rows:  # a match is stored once, from the newer file's side; show both ways
        other_id = row.matched_file_id if row.source_file_id == file_id else row.source_file_id
        other = get_file(db, other_id)
        if other is not None:
            matches.append(SimilarFile(
                file_id=other_id, filename=other.filename,
                match_type=row.match_type, score=row.similarity_score,
            ))
    matches.sort(key=lambda m: m.score, reverse=True)
    return SimilarResponse(file_id=file_id, matches=matches)
