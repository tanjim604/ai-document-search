"""API tests for POST /files and GET /files/{file_id}."""
import hashlib
from pathlib import Path

import pytest
from sqlalchemy import func, select

from app.ingestion.service import update_processing_status
from app.shared.models.file import File, ProcessingStatus


def upload(client, filename: str, data: bytes, content_type="application/octet-stream"):
    return client.post("/files", files={"file": (filename, data, content_type)})


def count_files(db_session) -> int:
    return db_session.scalar(select(func.count()).select_from(File))


def stored_files(upload_root: Path) -> list[Path]:
    return [p for p in upload_root.rglob("*") if p.is_file()] if upload_root.exists() else []


# ------------------------------------------------------------ normal cases ----
def test_upload_txt_saves_file_and_database_row(client, db_session, sample_bytes):
    data = sample_bytes["txt"]
    response = upload(client, "ai-evolution.txt", data, "text/plain")

    assert response.status_code == 201
    body = response.json()
    assert body["file_id"].startswith("f_")
    assert body["filename"] == "ai-evolution.txt"
    assert body["extension"] == "txt"
    assert body["mime_type"] == "text/plain"
    assert body["status"] == "uploaded"
    assert body["sha256_hash"] == hashlib.sha256(data).hexdigest()
    assert body["is_exact_duplicate"] is False
    assert body["duplicate_of"] is None

    # The original file exists and is byte-for-byte identical.
    assert Path(body["storage_path"]).read_bytes() == data

    # A metadata row exists with the same values.
    row = db_session.get(File, body["file_id"])
    assert row is not None
    assert row.storage_path == body["storage_path"]
    assert row.sha256_hash == body["sha256_hash"]
    assert row.processing_status == ProcessingStatus.UPLOADED.value
    assert row.created_at is not None


@pytest.mark.parametrize("extension", ["pdf", "docx", "txt", "csv", "xlsx", "png", "jpg", "jpeg"])
def test_every_supported_type_is_accepted_and_sorted_by_extension(
    client, sample_bytes, upload_root, extension
):
    response = upload(client, f"sample.{extension}", sample_bytes[extension])

    assert response.status_code == 201, response.text
    body = response.json()
    assert body["extension"] == extension
    stored = Path(body["storage_path"])
    assert stored.parent == upload_root / extension  # sorted into its own folder
    assert stored.name == f"{body['file_id']}.{extension}"  # named by file_id


def test_uppercase_extension_is_normalised(client, sample_bytes):
    response = upload(client, "REPORT.PDF", sample_bytes["pdf"])

    assert response.status_code == 201
    assert response.json()["extension"] == "pdf"
    assert response.json()["filename"] == "REPORT.PDF"  # original name kept


def test_browser_mime_type_is_not_trusted(client, sample_bytes):
    # Windows browsers send CSV as an Excel MIME type; the content decides.
    response = upload(client, "grades.csv", sample_bytes["csv"], "application/vnd.ms-excel")

    assert response.status_code == 201
    assert response.json()["mime_type"] == "text/csv"


# ----------------------------------------------------------- invalid input ----
@pytest.mark.parametrize("filename", ["setup.exe", "archive.zip", "README", "notes."])
def test_unsupported_or_missing_extension_is_rejected(
    client, db_session, upload_root, filename
):
    response = upload(client, filename, b"some bytes")

    assert response.status_code == 415
    assert "not supported" in response.json()["detail"]
    assert count_files(db_session) == 0
    assert stored_files(upload_root) == []


def test_fake_pdf_is_rejected(client, db_session, upload_root):
    response = upload(client, "not-really.pdf", b"This is plain text, not a PDF.")

    assert response.status_code == 400
    assert "does not look like a .pdf" in response.json()["detail"]
    assert count_files(db_session) == 0
    assert stored_files(upload_root) == []


def test_renamed_text_file_is_not_accepted_as_docx(client):
    response = upload(client, "essay.docx", b"just text")
    assert response.status_code == 400


def test_binary_file_is_not_accepted_as_txt(client, sample_bytes):
    response = upload(client, "notes.txt", sample_bytes["png"])
    assert response.status_code == 400


def test_empty_file_is_rejected(client, db_session):
    response = upload(client, "empty.txt", b"")

    assert response.status_code == 400
    assert response.json()["detail"] == "The file is empty."
    assert count_files(db_session) == 0


def test_request_without_a_file_field_is_rejected(client):
    response = client.post("/files")
    assert response.status_code == 422  # FastAPI validation error


# ---------------------------------------------------------- boundary cases ----
def test_file_exactly_at_size_limit_is_accepted(client, test_settings):
    limit = test_settings.max_upload_size_bytes
    response = upload(client, "big.txt", b"a" * limit)
    assert response.status_code == 201


def test_file_one_byte_over_limit_is_rejected(client, test_settings, db_session, upload_root):
    limit = test_settings.max_upload_size_bytes
    response = upload(client, "too-big.txt", b"a" * (limit + 1))

    assert response.status_code == 413
    assert count_files(db_session) == 0
    assert stored_files(upload_root) == []


def test_one_byte_file_is_accepted(client):
    assert upload(client, "tiny.txt", b"x").status_code == 201


# -------------------------------------------------------------- duplicates ----
def test_same_file_uploaded_twice_is_flagged_as_exact_duplicate(
    client, db_session, sample_bytes, upload_root
):
    first = upload(client, "ai-evolution.pdf", sample_bytes["pdf"]).json()
    second = upload(client, "ai-evolution.pdf", sample_bytes["pdf"]).json()

    assert first["sha256_hash"] == second["sha256_hash"]
    assert first["file_id"] != second["file_id"]  # each upload gets its own ID
    assert first["storage_path"] != second["storage_path"]
    assert first["is_exact_duplicate"] is False
    assert second["is_exact_duplicate"] is True
    assert second["duplicate_of"] == first["file_id"]
    assert count_files(db_session) == 2
    assert len(stored_files(upload_root)) == 2


def test_duplicate_is_detected_even_with_a_different_filename(client, sample_bytes):
    first = upload(client, "paper.pdf", sample_bytes["pdf"]).json()
    second = upload(client, "paper (copy).pdf", sample_bytes["pdf"]).json()

    assert second["duplicate_of"] == first["file_id"]


def test_third_copy_points_to_the_first_upload(client, sample_bytes):
    first = upload(client, "a.txt", sample_bytes["txt"]).json()
    upload(client, "b.txt", sample_bytes["txt"])
    third = upload(client, "c.txt", sample_bytes["txt"]).json()

    assert third["duplicate_of"] == first["file_id"]


def test_one_byte_difference_is_not_an_exact_duplicate(client):
    first = upload(client, "v1.txt", b"Version one").json()
    second = upload(client, "v2.txt", b"Version one.").json()

    assert first["sha256_hash"] != second["sha256_hash"]
    assert second["is_exact_duplicate"] is False


# ---------------------------------------------------------------- security ----
def test_path_in_filename_cannot_escape_upload_folder(client, sample_bytes, upload_root):
    response = upload(client, "../../../etc/passwd.txt", sample_bytes["txt"])

    assert response.status_code == 201
    body = response.json()
    assert body["filename"] == "passwd.txt"
    assert Path(body["storage_path"]).resolve().is_relative_to(upload_root.resolve())


def test_windows_style_path_is_reduced_to_filename(client, sample_bytes):
    response = upload(client, "C:\\Users\\me\\Desktop\\notes.txt", sample_bytes["txt"])
    assert response.json()["filename"] == "notes.txt"


# ------------------------------------------------------ GET /files/{file_id} ----
def test_get_file_details_returns_status_and_metadata(client, sample_bytes):
    uploaded = upload(client, "report.docx", sample_bytes["docx"]).json()

    response = client.get(f"/files/{uploaded['file_id']}")

    assert response.status_code == 200
    body = response.json()
    assert body["file_id"] == uploaded["file_id"]
    assert body["filename"] == "report.docx"
    assert body["status"] == "uploaded"
    assert body["storage_path"] == uploaded["storage_path"]
    assert "created_at" in body


def test_get_unknown_file_returns_404(client):
    response = client.get("/files/f_does_not_exist")
    assert response.status_code == 404


# ----------------------------------------------------- integration handoff ----
def test_status_change_by_a_teammate_is_visible_through_the_api(
    client, session_factory, sample_bytes
):
    """Simulates Diya finishing extraction, then the UI asking for status."""
    file_id = upload(client, "paper.pdf", sample_bytes["pdf"]).json()["file_id"]

    with session_factory() as db:
        update_processing_status(db, file_id, ProcessingStatus.EXTRACTED)

    assert client.get(f"/files/{file_id}").json()["status"] == "extracted"


def test_teammate_can_read_original_bytes_using_only_storage_path(
    client, storage, sample_bytes
):
    """What Diya does: take storage_path from the database and read the file."""
    body = upload(client, "paper.pdf", sample_bytes["pdf"]).json()
    assert storage.read_bytes(body["storage_path"]) == sample_bytes["pdf"]
