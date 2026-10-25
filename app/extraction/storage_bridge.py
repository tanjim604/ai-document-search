
from pathlib import Path
from tempfile import TemporaryDirectory

from app.ingestion.service import get_file
from app.shared.storage import get_storage
from app.extraction.pipeline import process_file


def process_uploaded_file(db, file_id):

    # Step 1: Get file information from Tahmid's database
    record = get_file(db, file_id)

    if record is None:
        return {
            "file_id": file_id,
            "status": "failed",
            "error": "File ID not found"
        }

    # Step 2: Read the uploaded file
    data = get_storage().read_bytes(record.storage_path)

    # Step 3: Make a temporary file for our existing readers
    with TemporaryDirectory() as folder:
        temp_path = Path(folder) / f"uploaded.{record.extension}"
        temp_path.write_bytes(data)

        # Step 4: Run our extraction pipeline
        result = process_file(temp_path)

    # Step 5: Include the original file information
    result["file_id"] = file_id
    result["filename"] = record.filename
    result["extension"] = record.extension

    return result
