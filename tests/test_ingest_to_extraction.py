
from pathlib import Path

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from app.shared.models.base import Base
from app.shared.models.file import File, ProcessingStatus
from app.shared.models.document_content import DocumentContent
from app.shared.models.document_chunk import DocumentChunk

from app.ingestion.service import ingest_file
from app.extraction.service import extract_and_save


def test_ingestion_to_extraction(tmp_path, monkeypatch):

    # Create temporary file storage for testing
    class TestStorage:

        def save(self, file_id, extension, data):
            path = tmp_path / extension / f"{file_id}.{extension}"
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(data)
            return str(path)

        def read_bytes(self, storage_path):
            return Path(storage_path).read_bytes()

        def delete(self, storage_path):
            Path(storage_path).unlink(missing_ok=True)

    storage = TestStorage()

    # Make extraction use our temporary storage
    monkeypatch.setattr(
        "app.extraction.storage_bridge.get_storage",
        lambda: storage
    )

    # Create temporary database
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)

    try:
        with Session(engine) as db:

            # Create sample document
            data = (
                "Artificial intelligence helps computers learn.\n"
                * 300
            ).encode("utf-8")

            # Step 1: Upload using Tahmid's actual function
            uploaded = ingest_file(
                db=db,
                storage=storage,
                original_filename="ai-notes.txt",
                data=data,
                max_size_bytes=25 * 1024 * 1024
            )

            file_id = uploaded.file.id

            assert uploaded.file.processing_status == "uploaded"

            # Step 2: Run your extraction module
            result = extract_and_save(db, file_id)

            assert result["status"] == "extracted"

            # Step 3: Check database status
            record = db.get(File, file_id)

            assert record.processing_status == (
                ProcessingStatus.EXTRACTED.value
            )

            # Step 4: Check extracted text
            content = db.get(DocumentContent, file_id)

            assert content is not None
            assert "Artificial intelligence" in content.raw_text

            # Step 5: Check chunks
            chunks = db.scalars(
                select(DocumentChunk)
                .where(DocumentChunk.file_id == file_id)
                .order_by(DocumentChunk.chunk_index)
            ).all()

            assert len(chunks) >= 1

            for index, chunk in enumerate(chunks):
                assert chunk.chunk_index == index
                assert chunk.file_id == file_id
                assert chunk.text.strip()

    finally:
        engine.dispose()
