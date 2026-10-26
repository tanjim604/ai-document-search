
from app.ingestion.service import (
    get_file,
    update_processing_status
)

from app.shared.models.file import ProcessingStatus

from app.extraction.storage_bridge import process_uploaded_file
from app.extraction.save_results import save_results


def extract_and_save(db, file_id):

    # Step 1: Check whether the file exists
    record = get_file(db, file_id)

    if record is None:
        return {
            "file_id": file_id,
            "status": "failed",
            "error": "File not found"
        }

    # Step 2: Mark the file as being processed
    update_processing_status(
        db, file_id, ProcessingStatus.EXTRACTING
    )

    try:
        # Step 3: Extract, clean, and chunk the file
        result = process_uploaded_file(db, file_id)

        # Step 4: Handle files that could not be extracted
        if result["status"] != "extracted":
            update_processing_status(
                db, file_id, ProcessingStatus.FAILED
            )
            result["processing_status"] = "failed"
            return result

        # Step 5: Save the extracted text and chunks
        save_results(db, file_id, result)

        # Step 6: Mark extraction as complete
        update_processing_status(
            db, file_id, ProcessingStatus.EXTRACTED
        )

        result["processing_status"] = "extracted"

        return result

    except Exception:
        db.rollback()

        update_processing_status(
            db, file_id, ProcessingStatus.FAILED
        )

        raise
