"""
End-to-end tests: upload -> extraction -> summary -> indexing -> similarity -> search.

They use the real embedding model (the first run downloads it) with an in-memory
Qdrant and a temporary database, so nothing real is touched. They are skipped
when the model cannot be loaded (for example, offline on the first run).
"""
import dataclasses

import pytest
from qdrant_client import QdrantClient
from sqlalchemy import select

from app.main import app
from app.pipeline.dependencies import get_pipeline_runner, get_qdrant
from app.pipeline.service import process_document
from app.shared.config.settings import get_settings
from app.shared.models.document_content import DocumentContent

AI_HISTORY = (
    "Artificial intelligence began as a research field in the 1950s, when early "
    "pioneers asked whether machines could think. The perceptron, introduced in "
    "1958, was one of the first neural network models. Funding fell during the AI "
    "winters of the 1970s and 1980s because early systems failed to deliver. "
    "Deep learning transformed the field after 2012, as large neural networks "
    "trained on GPUs began winning image recognition contests. Today, large "
    "language models built on the transformer architecture write text and code."
)
AI_HISTORY_EDITED = AI_HISTORY.replace("fell during", "dropped during")
AI_OVERVIEW = (
    "Machine learning lets computers learn patterns from data instead of following "
    "hand written rules. Neural networks with many layers can recognise speech, "
    "translate languages and classify images. Researchers continue to study how "
    "such models generalise, and how they can be made safe and fair."
)
COOKING = (
    "To bake sourdough bread, mix flour, water and salt with an active starter. "
    "Let the dough rest overnight, shape it into a round loaf, then bake it in a "
    "preheated Dutch oven until the crust turns deep golden brown."
)


@pytest.fixture(scope="session", autouse=True)
def require_embedding_model():
    try:
        from app.ai_indexing.embeddings import embed_text

        embed_text("warm up")
    except Exception as error:  # no network and no cached model
        pytest.skip(f"embedding model unavailable: {error}")


@pytest.fixture
def api(client, session_factory, test_settings, storage, monkeypatch):
    # The extraction module calls get_storage() directly, not as a FastAPI dependency.
    monkeypatch.setattr("app.extraction.storage_bridge.get_storage", lambda: storage)
    qdrant = QdrantClient(":memory:")

    def run(file_id):
        db = session_factory()
        try:
            process_document(db, qdrant, file_id)
        finally:
            db.close()

    app.dependency_overrides[get_settings] = lambda: dataclasses.replace(
        test_settings, auto_process=True, max_upload_size_bytes=1_000_000
    )
    app.dependency_overrides[get_qdrant] = lambda: qdrant
    app.dependency_overrides[get_pipeline_runner] = lambda: run
    return client


def upload(api, name, content, mime="text/plain"):
    response = api.post("/files", files={"file": (name, content, mime)})
    assert response.status_code == 201, response.text
    return response.json()


def test_upload_is_processed_automatically(api, db_session):
    uploaded = upload(api, "history.txt", AI_HISTORY.encode())

    details = api.get(f"/files/{uploaded['file_id']}").json()
    assert details["status"] == "indexed"
    summary = db_session.get(DocumentContent, uploaded["file_id"]).summary
    assert summary and "1950s" in AI_HISTORY and len(summary) < len(AI_HISTORY)


def test_search_finds_document_by_meaning_not_filename(api):
    history = upload(api, "doc1.txt", AI_HISTORY.encode())
    upload(api, "doc2.txt", COOKING.encode())

    body = api.get("/search", params={"q": "how did neural networks and AI develop over time"}).json()

    assert body["results"][0]["file_id"] == history["file_id"]
    top = body["results"][0]
    assert top["summary"] and top["matched_excerpt"] and top["storage_path"]
    assert top["score"] > 0.3


def test_search_returns_one_result_per_document_and_respects_filters(api):
    upload(api, "history.txt", AI_HISTORY.encode())
    upload(api, "cooking.txt", COOKING.encode())

    results = api.get("/search", params={"q": "history of artificial intelligence"}).json()["results"]
    ids = [r["file_id"] for r in results]
    assert len(ids) == len(set(ids))

    only_pdf = api.get("/search", params={"q": "history of artificial intelligence", "extension": "pdf"})
    assert only_pdf.json()["results"] == []


def test_search_on_empty_index_returns_no_results(api):
    assert api.get("/search", params={"q": "anything"}).json()["results"] == []


def test_search_rejects_missing_query(api):
    assert api.get("/search").status_code == 422


def test_similarity_labels(api):
    original = upload(api, "history.txt", AI_HISTORY.encode())
    same = upload(api, "history-copy.txt", AI_HISTORY.encode())
    edited = upload(api, "history-edited.txt", AI_HISTORY_EDITED.encode())
    overview = upload(api, "overview.txt", AI_OVERVIEW.encode())
    cooking = upload(api, "cooking.txt", COOKING.encode())

    assert same["is_exact_duplicate"] and same["duplicate_of"] == original["file_id"]

    def labels(file):
        matches = api.get(f"/files/{file['file_id']}/similar").json()["matches"]
        return {m["file_id"]: m["match_type"] for m in matches}

    assert labels(same)[original["file_id"]] == "exact_duplicate"
    assert labels(edited)[original["file_id"]] == "near_duplicate"
    assert labels(overview).get(original["file_id"]) == "related"
    assert cooking["file_id"] not in labels(original)
    assert labels(cooking) == {}


def test_scanned_file_is_flagged_not_embedded(api):
    png = b"\x89PNG\r\n\x1a\n" + b"\x00" * 64
    uploaded = upload(api, "scan.png", png, "image/png")

    assert api.get(f"/files/{uploaded['file_id']}").json()["status"] == "ocr_needed"
    assert api.get("/search", params={"q": "scan"}).json()["results"] == []


def test_process_endpoint_and_unknown_ids(api):
    uploaded = upload(api, "history.txt", AI_HISTORY.encode())

    again = api.post(f"/files/{uploaded['file_id']}/process")
    assert again.status_code == 200 and again.json()["status"] == "indexed"
    assert api.post("/files/f_missing/process").status_code == 404
    assert api.get("/files/f_missing/similar").status_code == 404


def test_reprocessing_does_not_duplicate_results_or_matches(api):
    first = upload(api, "history.txt", AI_HISTORY.encode())
    edited = upload(api, "history-edited.txt", AI_HISTORY_EDITED.encode())
    api.post(f"/files/{edited['file_id']}/process")

    matches = api.get(f"/files/{edited['file_id']}/similar").json()["matches"]
    assert [m["file_id"] for m in matches] == [first["file_id"]]
    hits = api.get("/search", params={"q": "AI winters and deep learning"}).json()["results"]
    assert len({h["file_id"] for h in hits}) == len(hits)


def test_list_files(api):
    upload(api, "a.txt", AI_HISTORY.encode())
    listing = api.get("/files").json()
    assert [f["filename"] for f in listing] == ["a.txt"]
