
from app.ai_indexing import service
from app.shared.models import File, ProcessingStatus, SimilarityMatch, new_file_id


def make_file(db_session, *, filename, sha256_hash):
    file = File(
        id=new_file_id(),
        filename=filename,
        extension="txt",
        mime_type="text/plain",
        storage_path=f"uploads/{filename}",
        sha256_hash=sha256_hash,
        processing_status=ProcessingStatus.EXTRACTED,
    )
    db_session.add(file)
    db_session.commit()
    db_session.refresh(file)
    return file


def test_index_document_marks_file_indexed(db_session, monkeypatch):
    file = make_file(
        db_session,
        filename="notes.txt",
        sha256_hash="hash-notes",
    )

    monkeypatch.setattr(
        service,
        "index_chunks",
        lambda *args, **kwargs: service.IndexingResult(
            file_id=file.id,
            chunks_received=1,
            chunks_indexed=1,
            skipped_empty_chunks=0,
        ),
    )

    result = service.index_document(
        db_session,
        object(),
        file_id=file.id,
        chunks=["Some document text"],
        filename=file.filename,
        extension=file.extension,
    )

    db_session.refresh(file)
    assert file.processing_status == ProcessingStatus.INDEXED
    assert result.indexing.chunks_indexed == 1
    assert result.exact_duplicate_file_ids == ()


def test_index_document_records_exact_duplicate(
    db_session, monkeypatch
):
    original = make_file(
        db_session,
        filename="original.txt",
        sha256_hash="same-sha256",
    )
    new_file = make_file(
        db_session,
        filename="copy.txt",
        sha256_hash="same-sha256",
    )

    monkeypatch.setattr(
        service,
        "index_chunks",
        lambda *args, **kwargs: service.IndexingResult(
            file_id=new_file.id,
            chunks_received=1,
            chunks_indexed=1,
            skipped_empty_chunks=0,
        ),
    )

    result = service.index_document(
        db_session,
        object(),
        file_id=new_file.id,
        chunks=["Matching file content"],
        filename=new_file.filename,
        extension=new_file.extension,
    )

    matches = (
        db_session.query(SimilarityMatch)
        .filter_by(
            source_file_id=new_file.id,
            matched_file_id=original.id,
            match_type="exact_duplicate",
        )
        .all()
    )

    assert len(matches) == 1
    assert matches[0].similarity_score == 1.0
    assert result.exact_duplicate_file_ids == (original.id,)


def test_index_document_marks_file_failed(
    db_session, monkeypatch
):
    file = make_file(
        db_session,
        filename="broken.txt",
        sha256_hash="hash-broken",
    )

    def fail_indexing(*args, **kwargs):
        raise RuntimeError("Simulated indexing failure")

    monkeypatch.setattr(service, "index_chunks", fail_indexing)

    try:
        service.index_document(
            db_session,
            object(),
            file_id=file.id,
            chunks=["Some text"],
            filename=file.filename,
            extension=file.extension,
        )
        assert False, "Expected indexing to raise RuntimeError"
    except RuntimeError as exc:
        assert str(exc) == "Simulated indexing failure"

    db_session.refresh(file)
    assert file.processing_status == ProcessingStatus.FAILED
