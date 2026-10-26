"""
Extraction for files with no text layer (photos, screenshots, scanned PDFs).

Diya's extraction reports `ocr_needed` for these. This step reads them with the
vision module and then saves the result exactly as normal extraction would, so the
rest of the pipeline (summary, indexing, search) needs no special cases.
"""
from sqlalchemy.orm import Session

from app.extraction.save_results import save_results
from app.extraction.text_chunker import chunk_text
from app.extraction.text_cleaner import clean_text
from app.ingestion.service import get_file, update_processing_status
from app.shared.models.file import ProcessingStatus
from app.shared.storage import get_storage
from app.vision import read_file


def extract_with_vision(db: Session, file_id: str) -> dict:
    """Return an extraction result: status 'extracted' on success, else 'ocr_needed'."""
    record = get_file(db, file_id)
    update_processing_status(db, file_id, ProcessingStatus.EXTRACTING)
    try:
        text = read_file(get_storage().read_bytes(record.storage_path), record.extension)
    except Exception as error:  # an unreadable or corrupt image
        update_processing_status(db, file_id, ProcessingStatus.OCR_NEEDED)
        return {"status": "ocr_needed", "error": f"Could not read this file: {error}"}

    if not text.strip():
        update_processing_status(db, file_id, ProcessingStatus.OCR_NEEDED)
        return {"status": "ocr_needed", "error": "Nothing could be read from this file."}

    result = {
        "status": "extracted",
        "raw_text": text,
        "chunks": chunk_text(clean_text(text), chunk_size=900, overlap=100),
    }
    save_results(db, file_id, result)
    update_processing_status(db, file_id, ProcessingStatus.EXTRACTED)
    return result
