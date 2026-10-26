"""Shared objects the pipeline and search routes depend on (overridden in tests)."""
import threading
from functools import lru_cache
from typing import Callable

from qdrant_client import QdrantClient

from app.ai_indexing.vector_store import create_client
from app.shared.database import get_session_factory
from app.pipeline.service import process_document


# Uploading several files at once starts several background jobs in parallel threads.
# They would all load the embedding model and write to Qdrant at the same time (embedded
# Qdrant is not safe for that), so jobs take turns.
_pipeline_lock = threading.Lock()


@lru_cache
def get_qdrant() -> QdrantClient:
    """One shared client. Qdrant's embedded mode locks its folder, so we never open two."""
    return create_client()


def get_pipeline_runner() -> Callable[[str], None]:
    """Return a function that processes one file in its own database session.
    Background tasks outlive the request, so they cannot reuse the request's session."""

    def run(file_id: str) -> None:
        with _pipeline_lock:
            db = get_session_factory()()
            try:
                process_document(db, get_qdrant(), file_id)
            finally:
                db.close()

    return run
