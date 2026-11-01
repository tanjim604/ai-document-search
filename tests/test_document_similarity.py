import pytest
from qdrant_client import QdrantClient

from app.ai_indexing.vector_store import ensure_collection, store_chunk, delete_file_chunks
from app.pipeline.similarity import find_document_matches


def vector(axis):
    result = [0.0] * 384
    result[axis] = 1.0
    return result


@pytest.fixture
def qdrant():
    client = QdrantClient(":memory:")
    ensure_collection(client)
    yield client
    client.close()


def put(client, file_id, axes):
    for i, axis in enumerate(axes):
        store_chunk(client, file_id=file_id, chunk_id=str(i), chunk_index=i,
                    text=f"Chunk {i}", filename=f"{file_id}.txt", extension="txt",
                    vector=vector(axis))


def matches(client, axes, **kwargs):
    return find_document_matches(client, file_id="source", vectors=[vector(a) for a in axes],
                                 near_duplicate_threshold=0.95, related_threshold=0.45, **kwargs)


def test_excerpt_is_not_near_duplicate_in_either_direction(qdrant):
    put(qdrant, "long", [0, 1])
    assert matches(qdrant, [0])[0].match_type == "related"
    assert matches(qdrant, [0])[0].similarity_score == pytest.approx(0.5)
    delete_file_chunks(qdrant, "long")
    put(qdrant, "short", [0])
    assert matches(qdrant, [0, 1])[0].similarity_score == pytest.approx(0.5)


def test_complete_matches_and_unrelated_and_self(qdrant):
    put(qdrant, "copy", [0, 1])
    put(qdrant, "unrelated", [2])
    put(qdrant, "source", [0, 1])
    result = matches(qdrant, [0, 1])
    assert [(m.file_id, m.match_type) for m in result] == [("copy", "near_duplicate")]
    assert matches(qdrant, [0, 1], skip_file_ids={"copy"}) == []


def test_more_than_ten_candidates_are_compared(qdrant):
    for i in range(12):
        put(qdrant, f"copy{i}", [0])
    assert len(matches(qdrant, [0])) == 12


def test_vector_cleanup_keeps_other_files(qdrant):
    put(qdrant, "old", [0, 1])
    put(qdrant, "other", [2])
    delete_file_chunks(qdrant, "old")
    assert qdrant.count("document_chunks").count == 1


@pytest.mark.parametrize("thresholds", [(0.4, 0.5), (float("nan"), 0.4), (1.1, 0.4)])
def test_invalid_thresholds(qdrant, thresholds):
    with pytest.raises(ValueError):
        find_document_matches(qdrant, file_id="source", vectors=[],
                              near_duplicate_threshold=thresholds[0], related_threshold=thresholds[1])

def test_reprocessing_refreshes_semantic_pairs(db_session, monkeypatch):
    from app.pipeline import service
    from app.pipeline.similarity import DocumentMatch
    from app.shared.models import File, SimilarityMatch
    for name in ("source", "other", "failed"):
        db_session.add(File(id=name, filename=f"{name}.txt", extension="txt", mime_type="text/plain",
                            storage_path=f"{name}.txt", sha256_hash=name,
                            processing_status="failed" if name == "failed" else "indexed"))
    db_session.commit()
    db_session.add(SimilarityMatch(source_file_id="other", matched_file_id="source",
                                   match_type="near_duplicate", similarity_score=0.99))
    db_session.commit()
    monkeypatch.setattr(service, "embed_chunks", lambda _: [[1.0]])
    monkeypatch.setattr(service, "find_document_matches", lambda *a, **kw: [
        DocumentMatch("other", 0.6, "related"), DocumentMatch("failed", 0.99, "near_duplicate")])
    for _ in range(2):
        result = service.record_similarity_matches(db_session, object(), "source", ["text"])
        assert result == [{"file_id": "other", "match_type": "related", "score": 0.6}]
        assert db_session.query(SimilarityMatch).count() == 1
    monkeypatch.setattr(service, "find_document_matches", lambda *a, **kw: [])
    assert service.record_similarity_matches(db_session, object(), "source", ["text"]) == []
    assert db_session.query(SimilarityMatch).count() == 0

def test_similar_endpoint_deduplicates_reverse_exact_pairs(db_session, client):
    from app.shared.models import File, SimilarityMatch
    for name in ("first", "second"):
        db_session.add(File(id=name, filename=f"{name}.txt", extension="txt", mime_type="text/plain",
                            storage_path=f"{name}.txt", sha256_hash="same", processing_status="indexed"))
    db_session.commit()
    for source, target in [("first", "second"), ("second", "first")]:
        db_session.add(SimilarityMatch(source_file_id=source, matched_file_id=target,
                                       match_type="exact_duplicate", similarity_score=1.0))
    db_session.commit()
    response = client.get("/files/first/similar")
    assert response.status_code == 200
    assert response.json()["matches"] == [dict(file_id="second", filename="second.txt",
                                              match_type="exact_duplicate", score=1.0)]
