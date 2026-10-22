"""Unit tests for the service functions teammates call directly."""
import pytest

from app.ingestion.service import (
    FileRecordNotFound,
    find_files_with_same_hash,
    get_file,
    ingest_file,
    update_processing_status,
)
from app.shared.models.file import ProcessingStatus

LIMIT = 10_000


def test_ingest_file_returns_record_with_uploaded_status(db_session, storage):
    result = ingest_file(db_session, storage, "notes.txt", b"hello", LIMIT)

    assert result.file.processing_status == "uploaded"
    assert result.duplicate_of is None
    assert get_file(db_session, result.file.id) is not None


def test_get_file_returns_none_for_unknown_id(db_session):
    assert get_file(db_session, "f_missing") is None


@pytest.mark.parametrize(
    "new_status",
    [ProcessingStatus.EXTRACTING, "extracted", "indexing", ProcessingStatus.INDEXED, "failed"],
)
def test_update_processing_status_accepts_every_contract_value(db_session, storage, new_status):
    file_id = ingest_file(db_session, storage, "a.txt", b"abc", LIMIT).file.id

    updated = update_processing_status(db_session, file_id, new_status)

    assert updated.processing_status == ProcessingStatus(new_status).value
    db_session.expire_all()  # re-read from the database
    assert get_file(db_session, file_id).processing_status == ProcessingStatus(new_status).value


def test_update_processing_status_rejects_unknown_value(db_session, storage):
    file_id = ingest_file(db_session, storage, "a.txt", b"abc", LIMIT).file.id

    with pytest.raises(ValueError):
        update_processing_status(db_session, file_id, "done")


def test_update_processing_status_rejects_unknown_file(db_session):
    with pytest.raises(FileRecordNotFound):
        update_processing_status(db_session, "f_missing", "extracted")


def test_find_files_with_same_hash_returns_other_copies_only(db_session, storage):
    original = ingest_file(db_session, storage, "a.txt", b"same bytes", LIMIT).file
    copy = ingest_file(db_session, storage, "b.txt", b"same bytes", LIMIT).file
    ingest_file(db_session, storage, "c.txt", b"different", LIMIT)

    assert [f.id for f in find_files_with_same_hash(db_session, copy.id)] == [original.id]
    assert [f.id for f in find_files_with_same_hash(db_session, original.id)] == [copy.id]


def test_database_failure_removes_the_saved_file(db_session, storage, upload_root, monkeypatch):
    """Storage and database must never disagree: no orphan files on disk."""

    def broken_commit():
        raise RuntimeError("database is down")

    monkeypatch.setattr(db_session, "commit", broken_commit)

    with pytest.raises(RuntimeError):
        ingest_file(db_session, storage, "a.txt", b"abc", LIMIT)

    leftover = [p for p in upload_root.rglob("*") if p.is_file()]
    assert leftover == []
