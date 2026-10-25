# Content Extraction and Processing Module

**Project:** AI Document Search
**Course:** COMP 3710 – Applied Artificial Intelligence
**Module Owner:** Diya Sudheer
**Module Directory:** `app/extraction/`
**Feature Branch:** `feature/content-extraction`
**Status:** Implemented and locally tested; final team integration and PostgreSQL verification pending.

---

## 1. Purpose and Scope

The Content Extraction and Processing module is responsible for converting uploaded files into readable text and preparing their contents for AI-based search and indexing.

This module connects Tahmid's File Ingestion and Storage component with Jahid's AI Indexing and Similarity component.

The main responsibilities of this module are:

- Extract text from supported document types.
- Clean and normalize extracted text.
- Divide long documents into smaller, overlapping chunks.
- Identify files that require Optical Character Recognition (OCR).
- Store extracted text and chunks in the database.
- Maintain the original file ID throughout processing.
- Update extraction processing statuses.
- Prepare extracted content for the AI indexing module.

The module does not generate AI embeddings, summaries, or similarity scores. Those functionalities belong to the AI Indexing and Similarity component.

## 2. Files Implemented

The following Python files were created for the Content Extraction and Processing module.

| File                | Responsibility                                              |
| ------------------- | ----------------------------------------------------------- |
| `txt_reader.py`     | Extract text from TXT files                                 |
| `pdf_reader.py`     | Extract selectable text from PDF documents                  |
| `docx_reader.py`    | Extract text from Microsoft Word documents                  |
| `csv_reader.py`     | Read CSV rows and convert them into text                    |
| `xlsx_reader.py`    | Extract worksheet names and cell values from Excel files    |
| `text_cleaner.py`   | Remove unnecessary whitespace and normalize text            |
| `text_chunker.py`   | Split long text into numbered, overlapping chunks           |
| `ocr_checker.py`    | Identify image files and PDFs that require OCR              |
| `pipeline.py`       | Combine file extraction, cleaning, and chunking             |
| `storage_bridge.py` | Connect the extraction module to Tahmid's storage system    |
| `save_results.py`   | Save extracted text and chunks into the database            |
| `service.py`        | Manage the complete extraction and database-saving workflow |

Two additional database models were created:

- `app/shared/models/document_content.py`
- `app/shared/models/document_chunk.py`

The shared `app/shared/models/__init__.py` file was updated to register the new models.

The project's `requirements.txt` was also updated to include the required extraction libraries.

## 3. Supported File Types

Tahmid's ingestion module accepts eight file extensions. The extraction module reads five document formats and identifies three image formats as requiring OCR.

| File Type | Library Used        | Functionality                               |
| --------- | ------------------- | ------------------------------------------- |
| PDF       | PyMuPDF             | Extract selectable text from PDF pages      |
| DOCX      | python-docx         | Extract text from Word document paragraphs  |
| TXT       | pathlib             | Read plain text files                       |
| CSV       | csv                 | Convert spreadsheet rows into readable text |
| XLSX      | openpyxl            | Read Excel worksheets and cell values       |
| PNG       | Extension detection | Flag as OCR-needed                          |
| JPG       | Extension detection | Flag as OCR-needed                          |
| JPEG      | Extension detection | Flag as OCR-needed                          |

### PDF Extraction

The `pdf_reader.py` file uses PyMuPDF to open PDF documents and extract text from each page.

It combines the extracted page contents into one text string.

If a PDF contains no readable selectable text, the module identifies it as potentially requiring OCR.

Corrupted or unreadable PDF files are handled through error checking rather than causing the entire application to crash.

### DOCX Extraction

The `docx_reader.py` file uses the python-docx library.

It reads non-empty paragraphs and combines their contents into a single text string.

The current implementation focuses on paragraph extraction. More complex document elements, such as some tables, are not fully reconstructed.

### CSV Extraction

The `csv_reader.py` file uses Python's built-in CSV library.

It reads spreadsheet rows and joins column values using the `|` separator.

This converts tabular information into a readable text representation for later AI processing.

### XLSX Extraction

The `xlsx_reader.py` file uses openpyxl.

It reads worksheet names and cell values from Excel spreadsheets.

The extracted information is converted into readable text while retaining the worksheet names.

### TXT Extraction

The `txt_reader.py` file uses Python's pathlib library to read text files.

It includes basic error handling for missing files and decoding problems.

## 4. Text Cleaning

**Implementation:** `text_cleaner.py`

Extracted text may contain unnecessary formatting such as multiple spaces, repeated blank lines, or null characters.

The `clean_text()` function prepares the content for further processing.

It performs the following operations:

- Removes null characters.
- Normalizes line endings.
- Removes repeated spaces and tabs.
- Removes unnecessary leading and trailing whitespace.
- Reduces excessive blank lines.
- Preserves useful paragraph breaks where possible.

For example:

**Before cleaning:**

```text
Artificial    Intelligence


Machine     learning   is useful.
```

**After cleaning:**

```text
Artificial Intelligence

Machine learning is useful.
```

The cleaning function does not summarize the document or intentionally change its meaning.

## 5. Text Chunking

**Implementation:** `text_chunker.py`

Long documents are divided into smaller sections called chunks.

Chunking allows the AI indexing component to process smaller sections of text rather than an entire long document at once.

The current implementation uses:

- **Chunk size:** 900 words
- **Overlap:** 100 words
- **Starting chunk index:** 0

For example, a 2,500-word document would produce:

| Chunk Index | Word Range        |
| ----------- | ----------------- |
| 0           | Words 1–900       |
| 1           | Words 801–1,700   |
| 2           | Words 1,601–2,500 |

The 100-word overlap helps preserve context between neighbouring chunks.

Each chunk is returned with its `chunk_index` and text.

The implementation uses word-based chunking rather than model-specific token counting. This is suitable for the initial prototype but does not guarantee sentence or paragraph boundaries will always be preserved.

## 6. OCR-Needed Detection

**Implementation:** `ocr_checker.py`

OCR stands for Optical Character Recognition. It is used to recognize text inside images and scanned documents.

Some PDFs contain selectable text, while others contain scanned images of pages.

The extraction module identifies files that cannot be processed using standard text extraction.

The current behavior is:

- Normal PDFs with extractable text are processed.
- PDFs without extractable text are flagged as `ocr_needed`.
- PNG, JPG, and JPEG files are flagged as `ocr_needed`.
- Corrupted PDFs return an extraction failure.

The module does not perform OCR itself.

**Limitation:** A PDF may contain both selectable text and scanned pages. The current implementation does not guarantee that all text from mixed-content PDFs is extracted.

## 7. Complete Extraction Pipeline

**Implementation:** `pipeline.py`

The pipeline combines the individual extraction and text-processing functions.

The workflow is:

1. Receive the file path.
2. Check whether the file exists.
3. Identify the file extension.
4. Select the appropriate extraction function.
5. Check whether OCR is required.
6. Extract readable text.
7. Clean the extracted text.
8. Divide the cleaned text into numbered chunks.
9. Return the processing result.

A successful result contains:

- Processing status
- Filename
- File extension
- Original extracted text
- Cleaned text
- Ordered chunks

The pipeline supports all eight file extensions accepted by Tahmid's ingestion module, although image formats are currently flagged for OCR instead of being converted to text.

## 8. Integration with File Ingestion and Storage

**Implementations:**

- `storage_bridge.py`
- `service.py`

Tahmid's ingestion module receives uploaded files, validates them, saves the originals, and creates file records in the database.

Each uploaded file receives a unique `file_id`.

The extraction module uses this ID to retrieve the original file and process its contents.

### Storage Integration

The module uses Tahmid's existing functions:

```python
get_file(db, file_id)
```

This retrieves the uploaded file's database record.

```python
get_storage().read_bytes(record.storage_path)
```

This retrieves the original file contents through the shared storage adapter.

The storage bridge creates a temporary copy of the uploaded document so the existing file readers can process it.

The temporary copy is removed after processing.

The original uploaded file is not modified.

### Extraction Service

The main integration function is:

```python
extract_and_save(db, file_id)
```

This function coordinates the complete process:

1. Retrieve the uploaded file record.
2. Set processing status to `extracting`.
3. Read the uploaded file contents.
4. Run the extraction pipeline.
5. Save extracted text and chunks.
6. Update processing status to `extracted` after saving succeeds.

If extraction fails, the service records a failure using the currently supported shared status values.

## 9. Database Models and Storage

Two SQLAlchemy database models were implemented.

### 9.1 DocumentContent

**File:** `app/shared/models/document_content.py`

**Database table:** `document_contents`

| Field      | Description                                               |
| ---------- | --------------------------------------------------------- |
| `file_id`  | Primary key and foreign key referencing the uploaded file |
| `raw_text` | Complete extracted document text                          |
| `summary`  | Nullable field reserved for Jahid's AI summary            |

Every DocumentContent record is associated with a file in Tahmid's `files` table.

### 9.2 DocumentChunk

**File:** `app/shared/models/document_chunk.py`

**Database table:** `document_chunks`

| Field         | Description                                        |
| ------------- | -------------------------------------------------- |
| `id`          | Unique identifier for each chunk                   |
| `file_id`     | Foreign key referencing the original uploaded file |
| `chunk_index` | Position of the chunk in the document              |
| `text`        | Text contained in the chunk                        |

A unique constraint on `file_id` and `chunk_index` prevents two chunks belonging to the same document from having the same index.

### 9.3 Database Saving

**Implementation:** `save_results.py`

The `save_results()` function saves extracted document information into the database.

It performs the following tasks:

- Verifies that extraction was successful.
- Confirms the original file exists in the database.
- Validates the extracted text and chunks.
- Inserts or updates the DocumentContent record.
- Saves numbered DocumentChunk records.
- Replaces old chunks if the document is processed again.
- Clears an outdated summary when the extracted raw text changes.
- Commits successful database changes.
- Rolls back changes if database saving fails.

This prevents duplicate chunk records from accumulating when the same document is reprocessed.

## 10. Processing Statuses and Error Handling

The shared project currently uses the following processing statuses:

```text
uploaded
extracting
extracted
indexing
indexed
failed
```

The extraction module manages the `extracting` and `extracted` stages.

A file is marked as `extracted` only after its extracted text and chunks have been successfully saved.

### OCR Status

The extraction pipeline also returns an internal result called:

```text
ocr_needed
```

However, this status is not yet included in the agreed shared database status enum.

For now, the integration service records unsuccessful OCR-needed processing as `failed` in the shared database, while retaining the more specific internal extraction result.

The team must agree on whether to introduce a separate persistent `ocr_needed` status.

### Error Handling

The module includes checks for:

- Missing files
- Unsupported file extensions
- Corrupted or unreadable PDFs
- Empty extracted text
- Files requiring OCR
- Invalid chunk data
- Database-saving failures

Files that cannot be processed successfully are not passed forward as valid text chunks for embedding.

The current shared database model does not include a dedicated persistent field for detailed extraction-error messages.

## 11. Automated Testing and Results

The module was tested using pytest.

Four test files were created.

| Test File                        | Purpose                                                                           |
| -------------------------------- | --------------------------------------------------------------------------------- |
| `test_extraction_pipeline.py`    | Tests supported files, text cleaning, chunking, OCR detection, and error handling |
| `test_save_results.py`           | Tests saving complete text and chunks into the database                           |
| `test_extraction_integration.py` | Tests the extraction service using simulated storage                              |
| `test_ingest_to_extraction.py`   | Tests Tahmid's ingestion function together with extraction                        |

### 11.1 Extraction Pipeline Testing

Ten automated tests cover:

- TXT extraction
- PDF extraction
- DOCX extraction
- CSV extraction
- XLSX extraction
- Image OCR-needed detection
- Invalid PDF handling
- Missing file handling
- Text cleaning
- Chunk ordering and overlap

All ten tests passed during local development.

### 11.2 Database-Saving Test

The database-saving test verifies:

- Extracted text can be saved.
- Chunks are stored in the correct order.
- Each chunk is associated with the correct file ID.
- Reprocessing does not create duplicate chunk records.

This test passed using an in-memory SQLite database.

### 11.3 Extraction Integration Test

The integration test uses simulated file storage and a temporary SQLite database.

It checks whether the extraction service can process a file, save its content, and update the processing status.

This test passed.

### 11.4 Ingestion-to-Extraction Test

This test calls Tahmid's actual `ingest_file()` function using temporary local storage.

It then passes the generated `file_id` to the extraction service.

The test verifies that:

- The uploaded file is registered.
- The extraction service receives its file ID.
- Text is extracted and saved.
- Chunks are stored in the database.
- The final file status becomes `extracted`.

This test passed.

### 11.5 Full Test Suite

The latest reported result during local development was:

**88 tests passed.**

This includes:

| Module                       |  Tests |
| ---------------------------- | -----: |
| Tahmid's ingestion module    |     75 |
| Content extraction pipeline  |     10 |
| Database-saving test         |      1 |
| Extraction integration test  |      1 |
| Ingestion-to-extraction test |      1 |
| **Total**                    | **88** |

An earlier test run reported a dependency warning, but no failed tests.

These test results were observed and reported from the local VS Code environment. The latest team's shared environment has not yet been independently verified.

## 12. Installation and Running Instructions

The project uses Python 3.11.

The extraction module requires the following additional libraries:

```text
PyMuPDF>=1.24
python-docx>=1.1
openpyxl>=3.1
```

These dependencies were added to the project's `requirements.txt`.

The other dependencies, including SQLAlchemy, pytest, FastAPI, and the PostgreSQL driver, are part of the existing project setup.

### Install Dependencies

From the project root on Windows:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

### Run the Sample Extraction Pipeline

```powershell
.\.venv\Scripts\python.exe -m app.extraction.pipeline
```

The demonstration uses sample documents from:

```text
sample_files/ingestion/
```

### Run All Automated Tests

```powershell
.\.venv\Scripts\python.exe -m pytest -q
```

The latest reported local test result was 88 passing tests.

## 13. Handoff to the AI Indexing Module

The extraction module prepares documents for Jahid's AI Indexing and Similarity component.

Jahid requires:

- The original `file_id`
- Filename
- File extension
- Full extracted text
- Ordered document chunks
- Processing status

The extracted content is stored using the DocumentContent and DocumentChunk models.

The AI indexing component can retrieve chunks associated with a file ID and process them in `chunk_index` order.

Jahid's component is responsible for:

- Generating document summaries.
- Creating embeddings.
- Storing embeddings in Qdrant.
- Identifying duplicate and similar documents.
- Making indexed documents available to semantic search.

The extraction module does not perform these tasks.

## 14. Known Limitations

The following limitations have been identified.

### 14.1 OCR

The module detects image files and PDFs requiring OCR, but does not perform OCR.

An actual scanned PDF and JPG/JPEG samples should receive additional dedicated tests.

### 14.2 PDF Content

Mixed-content PDFs may contain scanned sections that are not detected when other pages contain selectable text.

### 14.3 Word Document Formatting

The initial DOCX reader focuses on paragraph content.

Complex tables and certain embedded elements are not fully extracted.

### 14.4 Spreadsheet Processing

CSV and XLSX data are converted into simplified readable text.

The module does not preserve every spreadsheet formula, relationship, or formatting detail.

### 14.5 Text Chunking

Chunking is word-based, not token-based.

Chunks may occasionally split sentences or paragraphs.

### 14.6 Text Encoding

The initial TXT and CSV readers primarily use UTF-8-based decoding.

Additional encoding support may be needed for older documents.

### 14.7 Shared OCR Status

The persistent handling of OCR-needed files needs agreement from the team.

### 14.8 PostgreSQL Integration

Database-saving functionality was tested with SQLite.

Final verification using the team's PostgreSQL and Docker environment remains.

### 14.9 Team Branch Compatibility

The extraction module was developed using Tahmid's ingestion branch.

Compatibility with the latest combined team branch should be tested before merging.

## 15. Remaining Integration and Submission Tasks

The core implementation and local tests are complete.

The following tasks remain:

- [x] Implement extraction for five document formats.
- [x] Implement text cleaning.
- [x] Implement overlapping text chunking.
- [x] Implement OCR-needed detection.
- [x] Create the combined processing pipeline.
- [x] Connect the pipeline to Tahmid's ingestion functions in a test environment.
- [x] Implement database models and saving functionality.
- [x] Create automated tests.
- [x] Report 88 passing tests.
- [ ] Verify the module against the latest team branch.
- [ ] Test the complete process with PostgreSQL and the team's Docker configuration.
- [ ] Agree on persistent OCR-needed status handling.
- [ ] Confirm Jahid can retrieve and process the saved chunks.
- [ ] Have the team review and merge the module into GitHub.

Shared model changes and API contract changes must be reviewed by the team before merging.

## 16. Conclusion

The Content Extraction and Processing module provides the document-reading and text-preparation functionality required by the AI Document Search project.

It supports five document formats, identifies image files that require OCR, cleans extracted text, and divides documents into smaller overlapping chunks.

The module also includes database models, persistence functions, error handling, processing-status updates, and integration with Tahmid's ingestion component.

Automated tests have been implemented, with 88 tests reported as passing during the latest local run.

The core assigned functionality is implemented and locally tested. The remaining work involves verification in the team's shared environment, confirmation of the AI-indexing handoff, and final repository integration.
