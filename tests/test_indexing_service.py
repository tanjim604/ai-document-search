
import pytest

from app.ai_indexing import service


def test_index_chunks_skips_empty_chunks(monkeypatch):
    stored = []

    monkeypatch.setattr(
        service,
        "embed_chunks",
        lambda chunks: [[0.1] * 384, [], [0.2] * 384],
    )
    monkeypatch.setattr(
        service,
        "store_chunk",
        lambda client, **kwargs: stored.append(kwargs),
    )

    result = service.index_chunks(
        object(),
        file_id="f_test",
        chunks=["first chunk", "   ", "third chunk"],
        filename="notes.txt",
        extension="txt",
    )

    assert result.chunks_received == 3
    assert result.chunks_indexed == 2
    assert result.skipped_empty_chunks == 1
    assert [item["chunk_index"] for item in stored] == [0, 2]


def test_index_chunks_rejects_all_empty_chunks(monkeypatch):
    monkeypatch.setattr(service, "embed_chunks", lambda chunks: [[], []])

    with pytest.raises(ValueError, match="no non-empty chunks"):
        service.index_chunks(
            object(),
            file_id="f_empty",
            chunks=["", "  "],
            filename="empty.txt",
            extension="txt",
        )


def test_index_chunks_rejects_missing_file_id():
    with pytest.raises(ValueError, match="file_id"):
        service.index_chunks(
            object(),
            file_id=" ",
            chunks=["some text"],
            filename="notes.txt",
            extension="txt",
        )
