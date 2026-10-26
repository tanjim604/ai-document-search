
from pathlib import Path
import pymupdf


def check_ocr_needed(file_path):
    path = Path(file_path)

    if not path.is_file():
        return "file_not_found"

    extension = path.suffix.lower()

    # Image files need OCR for text extraction
    if extension in [".png", ".jpg", ".jpeg"]:
        return "ocr_needed"

    # Check whether a PDF has readable text
    if extension == ".pdf":
        try:
            with pymupdf.open(path) as document:
                text = ""

                for page in document:
                    text += page.get_text()

            if not text.strip():
                return "ocr_needed"

            return "text_available"

        except Exception as error:
            print("Error checking PDF:", error)
            return "failed"

    return "not_applicable"


