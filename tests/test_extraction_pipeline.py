
from pathlib import Path
import pytest

from app.extraction.pipeline import process_file
from app.extraction.text_chunker import chunk_text
from app.extraction.text_cleaner import clean_text


# Location of Tahmid's sample files
SAMPLE_FOLDER = (
    Path(__file__).resolve().parents[1]
    / "sample_files"
    / "ingestion"
)


# Test all five document types
@pytest.mark.parametrize("filename", [
    "notes.txt",
    "ai-evolution.pdf",
    "meeting-notes.docx",
    "ai-milestones.csv",
    "project-budget.xlsx"
])
def test_document_extraction(filename):
    result = process_file(SAMPLE_FOLDER / filename)

    assert result["status"] == "extracted"
    assert result["raw_text"].strip()
    assert len(result["chunks"]) >= 1


# Test image OCR detection
def test_image_needs_ocr():
    result = process_file(SAMPLE_FOLDER / "scanned-page.png")

    assert result["status"] == "ocr_needed"
    assert result["chunks"] == []


# Test an invalid PDF
def test_invalid_pdf():
    result = process_file(SAMPLE_FOLDER / "not-really-a.pdf")

    assert result["status"] == "failed"


# Test a missing file
def test_missing_file():
    result = process_file(SAMPLE_FOLDER / "missing.txt")

    assert result["status"] == "failed"


# Test text cleaning
def test_text_cleaning():
    text = "Hello    World\n\n\n\nThis   is AI."

    result = clean_text(text)

    assert result == "Hello World\n\nThis is AI."


# Test chunk order and overlap
def test_text_chunking():
    text = " ".join(f"word{i}" for i in range(1100))

    chunks = chunk_text(text, chunk_size=900, overlap=100)

    assert len(chunks) == 2
    assert chunks[0]["chunk_index"] == 0
    assert chunks[1]["chunk_index"] == 1

    first = chunks[0]["text"].split()
    second = chunks[1]["text"].split()

    assert first[-100:] == second[:100]
