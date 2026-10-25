
from sqlalchemy import delete
from sqlalchemy.orm import Session

from app.shared.models.file import File
from app.shared.models.document_content import DocumentContent
from app.shared.models.document_chunk import DocumentChunk


def save_results(db: Session, file_id: str, result: dict):

    # Only save files that were extracted successfully
    if result.get("status") != "extracted":
        raise ValueError("File extraction was not successful")

    # Confirm the original file exists
    file_record = db.get(File, file_id)

    if file_record is None:
        raise ValueError("File ID not found in database")

    raw_text = result["raw_text"]
    chunks = result["chunks"]

    if not raw_text.strip() or not chunks:
        raise ValueError("No extracted text or chunks to save")

    # Check that chunks are numbered correctly
    for index, chunk in enumerate(chunks):
        if chunk["chunk_index"] != index or not chunk["text"].strip():
            raise ValueError("Invalid chunk data")

    try:
        # Save the complete extracted text
        content = db.get(DocumentContent, file_id)

        if content is None:
            content = DocumentContent(
                file_id=file_id,
                raw_text=raw_text,
                summary=None
            )
            db.add(content)
        else:
            if content.raw_text != raw_text:
                content.summary = None
            content.raw_text = raw_text

        # Replace old chunks if the file is processed again
        db.execute(
            delete(DocumentChunk).where(
                DocumentChunk.file_id == file_id
            )
        )

        # Save each numbered chunk
        for chunk in chunks:
            db.add(
                DocumentChunk(
                    file_id=file_id,
                    chunk_index=chunk["chunk_index"],
                    text=chunk["text"]
                )
            )

        db.commit()

    except Exception:
        db.rollback()
        raise

    return True
