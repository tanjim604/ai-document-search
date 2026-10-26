"""Shared objects the pipeline and search routes depend on (overridden in tests)."""
import logging
import queue
import threading
from functools import lru_cache
from typing import Callable

from qdrant_client import QdrantClient
from sqlalchemy import select

from app.ai_indexing.vector_store import create_client
from app.pipeline.service import process_document
from app.shared.database import get_session_factory
from app.shared.models.file import File, ProcessingStatus

log = logging.getLogger(__name__)

UNFINISHED = (
    ProcessingStatus.UPLOADED.value,
    ProcessingStatus.EXTRACTING.value,
    ProcessingStatus.EXTRACTED.value,
    ProcessingStatus.INDEXING.value,
)


@lru_cache
def get_qdrant() -> QdrantClient:
    """One shared client. Qdrant's embedded mode locks its folder, so we never open two."""
    return create_client()


# One worker thread takes files from this queue in order. Uploads only add an id, so
# a batch of 100 files never ties up request threads or database connections, and
# the embedding model and Qdrant are only ever used by one indexing job at a time.
_jobs: "queue.Queue[str]" = queue.Queue()
_worker_lock = threading.Lock()
_worker: threading.Thread | None = None


def _process(file_id: str) -> None:
    db = get_session_factory()()
    try:
        process_document(db, get_qdrant(), file_id)
    finally:
        db.close()


def _work() -> None:
    while True:
        file_id = _jobs.get()
        try:
            _process(file_id)
        except Exception:  # keep the worker alive whatever happens to one file
            log.exception("Processing %s failed", file_id)
        finally:
            _jobs.task_done()


def _ensure_worker() -> None:
    global _worker
    with _worker_lock:
        if _worker is None or not _worker.is_alive():
            _worker = threading.Thread(target=_work, name="pipeline-worker", daemon=True)
            _worker.start()


def get_pipeline_runner() -> Callable[[str], None]:
    """Return a function that queues one file for processing."""
    _ensure_worker()
    return _jobs.put


def resume_unfinished() -> int:
    """Queue files left half-processed by a restart or crash. Returns how many."""
    db = get_session_factory()()
    try:
        ids = list(db.scalars(
            select(File.id).where(File.processing_status.in_(UNFINISHED)).order_by(File.created_at)
        ))
    finally:
        db.close()
    _ensure_worker()
    for file_id in ids:
        _jobs.put(file_id)
    return len(ids)
