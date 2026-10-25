
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from app.shared.models.base import Base
from app.shared.models.file import File, ProcessingStatus
from app.shared.models.document_content import DocumentContent
from app.shared.models.document_chunk import DocumentChunk

from app.extraction.service import extract_and_save


def test_complete_extraction(monkeypatch):

    # Simulate Tahmid's file storage
    class FakeStorage:
        def read_bytes(self, storage_path):
            return b"Artificial intelligence helps computers learn from data."

    monkeypatch.setattr(
        "app.extraction.storage_bridge.get_storage",
        lambda: FakeStorage()
    )

    # Create a temporary database
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)

    try:
        with Session(engine) as db:

            # Create a sample uploaded file record
            file = File(
                id="f_integration123",
                filename="test.txt",
                extension="txt",
                mime_type="text/plain",
                storage_path="data/uploads/txt/test.txt",
                sha256_hash="a" * 64,
                processing_status="uploaded"
            )

            db.add(file)
            db.commit()

            # Run your complete extraction service
            result = extract_and_save(db, "f_integration123")

            assert result["status"] == "extracted"

            # Check the final processing status
            saved_file = db.get(File, "f_integration123")

            assert saved_file.processing_status == ProcessingStatus.EXTRACTED.value

            # Check extracted text
            content = db.get(DocumentContent, "f_integration123")

            assert content is not None
            assert "Artificial intelligence" in content.raw_text

            # Check the saved chunks
            chunks = db.scalars(
                select(DocumentChunk).where(
                    DocumentChunk.file_id == "f_integration123"
                )
            ).all()

            assert len(chunks) >= 1
            assert chunks[0].chunk_index == 0

    finally:
        engine.dispose()
