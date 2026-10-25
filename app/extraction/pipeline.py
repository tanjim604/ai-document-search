
from pathlib import Path

from app.extraction.txt_reader import extract_txt
from app.extraction.pdf_reader import extract_pdf
from app.extraction.docx_reader import extract_docx
from app.extraction.csv_reader import extract_csv
from app.extraction.xlsx_reader import extract_xlsx

from app.extraction.text_cleaner import clean_text
from app.extraction.text_chunker import chunk_text
from app.extraction.ocr_checker import check_ocr_needed


def process_file(file_path):

    path = Path(file_path)
    extension = path.suffix.lower()

    # Select the correct reader for each file type
    readers = {
        ".txt": extract_txt,
        ".pdf": extract_pdf,
        ".docx": extract_docx,
        ".csv": extract_csv,
        ".xlsx": extract_xlsx
    }

    # Check whether the file exists
    if not path.is_file():
        return {"status": "failed", "error": "File not found"}

    # Images require OCR
    if extension in [".png", ".jpg", ".jpeg"]:
        return {"status": "ocr_needed", "chunks": []}

    # Check scanned or corrupted PDFs
    if extension == ".pdf":
        ocr_result = check_ocr_needed(file_path)

        if ocr_result == "ocr_needed":
            return {"status": "ocr_needed", "chunks": []}

        if ocr_result != "text_available":
            return {"status": "failed", "error": "Cannot read PDF"}

    # Reject unsupported file types
    if extension not in readers:
        return {"status": "failed", "error": "Unsupported file type"}

    # Step 1: Extract text
    raw_text = readers[extension](file_path)

    if raw_text is None or not raw_text.strip():
        return {"status": "failed", "error": "No readable text"}

    # Step 2: Clean the text
    cleaned_text = clean_text(raw_text)

    # Step 3: Divide into chunks
    chunks = chunk_text(
        cleaned_text,
        chunk_size=900,
        overlap=100
    )

    return {
        "status": "extracted",
        "filename": path.name,
        "extension": extension.lstrip("."),
        "raw_text": raw_text,
        "cleaned_text": cleaned_text,
        "chunks": chunks
    }


# Only run these examples when this file is executed directly
if __name__ == "__main__":
    sample_files = [
        "notes.txt",
        "ai-evolution.pdf",
        "meeting-notes.docx",
        "ai-milestones.csv",
        "project-budget.xlsx",
        "scanned-page.png",
        "not-really-a.pdf"
    ]

    for filename in sample_files:
        file_path = "sample_files/ingestion/" + filename

        result = process_file(file_path)

        print("\nFile:", filename)
        print("Status:", result["status"])
        print("Total chunks:", len(result.get("chunks", [])))

        if "error" in result:
            print("Error:", result["error"])
