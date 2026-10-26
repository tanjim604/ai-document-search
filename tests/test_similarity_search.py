
from types import SimpleNamespace

import pytest

from app.ai_indexing import search


def test_search_groups_results_by_file_and_sorts_them(monkeypatch):
    monkeypatch.setattr(
        search,
        "embed_chunks",
        lambda chunks: [[0.1] * 384, [0.2] * 384],
    )
    monkeypatch.setattr(search, "ensure_collection", lambda client: None)

    responses = [
        SimpleNamespace(
            points=[
                SimpleNamespace(
                    score=0.97,
                    payload={
                        "file_id": "file_a",
                        "filename": "a.txt",
                        "extension": "txt",
                        "text": "similar text",
                    },
                ),
                SimpleNamespace(
                    score=0.80,
                    payload={
                        "file_id": "file_b",
                        "filename": "b.pdf",
                        "extension": "pdf",
                        "text": "related text",
                    },
                ),
            ]
        ),
        SimpleNamespace(
            points=[
                SimpleNamespace(
                    score=0.91,
                    payload={
                        "file_id": "file_a",
                        "filename": "a.txt",
                        "extension": "txt",
                        "text": "another chunk",
                    },
                )
            ]
        ),
    ]

    class FakeClient:
        def query_points(self, **kwargs):
            return responses.pop(0)

    results = search.search_similar_files(
        FakeClient(),
        chunks=["first query chunk", "second query chunk"],
    )

    assert len(results) == 2
    assert results[0].file_id == "file_a"
    assert results[0].similarity_score == 0.97
    assert results[0].match_type == "near_duplicate"
    assert results[1].file_id == "file_b"
    assert results[1].match_type == "related"


def test_search_rejects_empty_query():
    with pytest.raises(ValueError, match="query chunk"):
        search.search_similar_files(object(), chunks=[])


def test_search_rejects_invalid_thresholds():
    with pytest.raises(ValueError, match="threshold"):
        search.search_similar_files(
            object(),
            chunks=["some text"],
            near_duplicate_threshold=0.75,
            related_threshold=0.95,
        )
