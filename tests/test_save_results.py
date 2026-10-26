
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from app.shared.models.base import Base
from app.shared.models.file import File
from app.shared.models.document_content import DocumentContent
from app.shared.models.document_chunk import DocumentChunk

from app.extraction.pipeline import process_file
from app.extraction.save_results import save_results


def test_save_extracted_results(tmp_path):

    # Step 1: Create a temporary test database
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)

    # Step 2: Create a sample text document
    test_file = tmp_path / "test.txt"

    test_file.write_text(
        "Artificial intelligence helps computers learn. " * 250,
        encoding="utf-8"
    )

    # Step 3: Extract and chunk the document
    result = process_file(test_file)

    assert result["status"] == "extracted"
    assert len(result["chunks"]) > 1

    # Step 4: Create the original file's database record
    with Session(engine) as db:

        file_record = File(
            id="f_test123",
            filename="test.txt",
            extension="txt",
            mime_type="text/plain",
            storage_path="data/uploads/txt/f_test123.txt",
            sha256_hash="a" * 64,
            processing_status="uploaded"
        )

        db.add(file_record)
        db.commit()

        # Step 5: Save extraction results
        save_results(db, "f_test123", result)

        # Step 6: Check the saved full text
        content = db.get(DocumentContent, "f_test123")

        assert content is not None
        assert content.raw_text == result["raw_text"]

        # Step 7: Check the saved chunks
        chunks = db.scalars(
            select(DocumentChunk)
            .where(DocumentChunk.file_id == "f_test123")
            .order_by(DocumentChunk.chunk_index)
        ).all()

        assert len(chunks) == len(result["chunks"])

        for index, chunk in enumerate(chunks):
            assert chunk.chunk_index == index
            assert chunk.text == result["chunks"][index]["text"]

        # Step 8: Save again to check for duplicates
        save_results(db, "f_test123", result)

        chunks_again = db.scalars(
            select(DocumentChunk)
            .where(DocumentChunk.file_id == "f_test123")
        ).all()

        assert len(chunks_again) == len(result["chunks"])

    engine.dispose()
