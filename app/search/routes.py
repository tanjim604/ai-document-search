"""GET /search?q=... (Tanjim)"""
from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from qdrant_client import QdrantClient
from sqlalchemy.orm import Session

from app.pipeline.dependencies import get_qdrant
from app.search.service import search_documents
from app.shared.database import get_db

router = APIRouter(tags=["search"])


class SearchHit(BaseModel):
    file_id: str
    filename: str
    extension: str
    summary: str | None
    score: float  # relevance, 0 to 1
    semantic_score: float  # raw cosine similarity of the best chunk
    matched_excerpt: str
    storage_path: str


class SearchResponse(BaseModel):
    query: str
    results: list[SearchHit]


@router.get("/search", response_model=SearchResponse)
def search(
    q: str = Query(..., min_length=1, max_length=500, description="What you are looking for"),
    limit: int = Query(10, ge=1, le=50),
    min_score: float = Query(0.2, ge=0, le=1, description="Hide matches whose raw cosine similarity is below this"),
    extension: str | None = Query(None, description="Only this file type, e.g. pdf"),
    db: Session = Depends(get_db),
    client: QdrantClient = Depends(get_qdrant),
) -> SearchResponse:
    hits = search_documents(
        db, client, q.strip(), limit=limit, min_score=min_score, extension=extension
    )
    return SearchResponse(query=q, results=[SearchHit(**h.__dict__) for h in hits])
