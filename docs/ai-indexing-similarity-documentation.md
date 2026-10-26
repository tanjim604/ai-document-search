# AI Indexing & Similarity --- Jahid's Implementation

**Project:** COMP 3710 --- AI Document Search\
**Owner:** Md Jahid Hossain\
**Branch:** `feature/ai-indexing-similarity`\
**Latest reported verification:** 91 tests passed, 1 Starlette/httpx
deprecation warning.

> This guide documents the implementation currently present in the AI
> indexing/similarity branch. It separates implemented behavior from
> features that still depend on the extraction and search components.

## 1. Purpose and scope

This component receives already-extracted text chunks, creates
embeddings, stores vectors in Qdrant, supports similarity retrieval,
detects exact byte-level duplicates using SHA-256, records
exact-duplicate relationships in SQL, and updates file processing status
during indexing.

It does **not** currently extract text from PDFs/DOCX/images, generate
document summaries, or expose the final HTTP search endpoint. Those
belong to other components or require a later integration decision.

## 2. System workflow

1.  Ingestion receives a file, stores it, and creates a `File` database
    record.
2.  The extraction component extracts text and splits it into ordered
    chunks.
3.  The indexing component receives `file_id`, `filename`, `extension`,
    and `chunks`.
4.  `all-MiniLM-L6-v2` embeds non-empty chunks into 384-dimensional
    vectors.
5.  Qdrant stores each vector and its metadata in `document_chunks`.
6.  The service looks for files with the same SHA-256 hash and records
    exact duplicates.
7.  The service marks the file `indexed` after successful indexing.
8.  The search component can call `search_similar_files()` to retrieve
    candidate documents.

``` text
Ingestion / file record
        |
        v
Extraction and chunking (other component)
        |
        v
AI indexing service
   |                  |
   v                  v
Embeddings         SHA-256 lookup
   |                  |
   v                  v
Qdrant vectors     similarity_matches SQL table
        |
        v
Similarity-search helper
        |
        v
Search API (other component)
```

## 3. Files and responsibilities

  -----------------------------------------------------------------------------
  File                                      Responsibility
  ----------------------------------------- -----------------------------------
  `app/ai_indexing/embeddings.py`           Loads the sentence-transformer
                                            model and embeds text/chunks.

  `app/ai_indexing/vector_store.py`         Creates the Qdrant
                                            client/collection and stores
                                            vectors with metadata.

  `app/ai_indexing/similarity.py`           Cosine similarity, average
                                            embeddings, and similarity
                                            classification.

  `app/ai_indexing/deduplication.py`        SHA-256 hashing and exact byte
                                            comparison.

  `app/ai_indexing/service.py`              Coordinates chunk indexing,
                                            duplicate recording, and file
                                            status updates.

  `app/ai_indexing/search.py`               Queries Qdrant and groups chunk
                                            matches into file-level results.

  `app/shared/models/similarity_match.py`   SQLAlchemy model for file-to-file
                                            match records.

  `app/shared/models/__init__.py`           Exports `SimilarityMatch` for
                                            shared model metadata.

  `tests/test_indexing_service.py`          Tests chunk validation and
                                            empty-chunk behavior.

  `tests/test_document_indexing.py`         Tests status updates, exact
                                            duplicate recording, and failure
                                            handling.

  `tests/test_similarity_search.py`         Tests search validation, grouping,
                                            and ranking.
  -----------------------------------------------------------------------------

The shared `File` model, database session, storage adapter, hash lookup,
and status helper are owned by the ingestion/storage component.

## 4. Embeddings

-   **Model:** `all-MiniLM-L6-v2`
-   **Vector dimensions:** `384`
-   Embeddings are normalized before use.
-   `get_model()` caches the model so it is not reloaded on every call.
-   Document chunks and search queries must use the same model.

### Functions

-   `get_model()` --- load/reuse the cached model.
-   `embed_text(text)` --- embed one non-empty string and verify its
    vector has 384 dimensions.
-   `embed_chunks(chunks)` --- embed valid chunks in a batch. Output
    positions match input positions; blank/invalid chunks receive an
    empty-list placeholder. Callers must skip these placeholders.

## 5. Qdrant vector storage

### Collection

-   Name: `document_chunks`
-   Vector size: `384`
-   Distance: cosine

### Client configuration

`create_client()` supports two modes:

-   **Local persistent mode:** set `QDRANT_PATH=data/qdrant`. This
    persists data locally without a separate Qdrant server.
-   **Server mode:** if `QDRANT_PATH` is not set, it connects to
    `QDRANT_URL`, default `http://localhost:6333`.

Choose the mode in your local `.env`. Do not commit `.env` or Qdrant
runtime data; the repository ignores `.env` and `data/`.

`ensure_collection(client)` creates the collection only if it does not
already exist.

### Stored point payload

Each vector stores `file_id`, `chunk_id`, `chunk_index`, `text`,
`filename`, and `extension`.

The Qdrant point ID is a deterministic UUID derived from `file_id` and
`chunk_id`, so retrying the same chunk updates the same point instead of
generating a random new point. `store_chunk()` rejects empty text and
vectors that are not 384 dimensions.

## 6. Similarity calculation and classification

`cosine_similarity(a, b)` compares equal-sized, one-dimensional,
non-zero vectors and clamps the result to `[-1, 1]`.

`average_embedding(vectors)` averages equally sized vectors and
normalizes the result. It is available as a helper, but the current
indexing service does not use it to persist document-level semantic
matches.

### Initial thresholds

  Score                    Label
  ------------------------ ------------------
  `>= 0.95`                `near_duplicate`
  `>= 0.75` and `< 0.95`   `related`
  `< 0.75`                 `unrelated`

These are starting values, not universal rules. Test them using labeled
examples of exact duplicates, lightly edited copies, related documents,
and unrelated documents.

## 7. Exact duplicate detection

-   `calculate_sha256(content)` returns the SHA-256 hash of the original
    bytes.
-   `is_exact_duplicate(a, b)` compares the hashes of two byte
    sequences.
-   `index_document()` uses the ingestion component's
    `find_files_with_same_hash()` lookup to find files with the same
    hash.
-   Exact duplicates are recorded with `match_type="exact_duplicate"`
    and `similarity_score=1.0`.

This detects byte-identical files. Two files that appear the same to a
person can still have different hashes if their bytes differ (for
example, metadata or formatting changes).

## 8. SQL model: `SimilarityMatch`

  -----------------------------------------------------------------------
  Field                               Meaning
  ----------------------------------- -----------------------------------
  `id`                                UUID string primary key.

  `source_file_id`                    Source file; foreign key to
                                      `files.id`.

  `matched_file_id`                   Matching file; foreign key to
                                      `files.id`.

  `similarity_score`                  Score constrained to the range
                                      `0–1`.

  `match_type`                        Such as `exact_duplicate`,
                                      `near_duplicate`, or `related`.

  `created_at`                        UTC timestamp by default.
  -----------------------------------------------------------------------

  : `similarity_matches`.

A uniqueness constraint prevents duplicate records for the same source
file, matched file, and match type. File foreign keys use cascading
deletion.

**Current scope:** the indexing service currently persists
exact-duplicate records. `search_similar_files()` returns semantic
candidates but does not save those results as `near_duplicate` or
`related` rows.

## 9. Indexing service

### `index_chunks(...)`

Inputs: Qdrant client, `file_id`, ordered `chunks`, `filename`, and
`extension`.

It validates inputs, embeds chunks, skips blank chunks, stores non-empty
chunks, and returns an `IndexingResult` containing chunks
received/indexed/skipped. If no usable chunks remain, it raises an
error.

### `index_document(...)`

1.  Confirms the file record exists.
2.  Sets status to `indexing`.
3.  Calls `index_chunks(...)`.
4.  Looks up files with the same hash and adds missing exact-duplicate
    records.
5.  Commits the duplicate records.
6.  Sets status to `indexed`.
7.  Returns indexing statistics and exact-duplicate file IDs.

On an exception, the SQL session is rolled back and the service attempts
to mark the file `failed`, then re-raises the original exception.

The expected successful status sequence is
`extracted → indexing → indexed`. The shared ingestion service owns the
allowed status transitions.

**Transaction limitation:** SQL and Qdrant are separate systems. A SQL
rollback cannot undo vectors already written to Qdrant. Deterministic
point IDs help retries overwrite existing chunk points, but a partial
failure can leave some vectors until retry or cleanup.

## 10. Similarity-search helper

Function: `search_similar_files(...)` in `app/ai_indexing/search.py`.

It embeds query chunks with the same model, queries Qdrant for each
valid chunk, optionally excludes a supplied `source_file_id`, validates
the returned metadata, groups matches by `file_id`, keeps each file's
highest-scoring chunk, classifies the score, and sorts results
highest-first.

Each `SimilarFile` includes `file_id`, `filename`, `extension`,
`similarity_score`, `match_type`, and `matched_chunk_text`.

Important limitations:

-   This is a Python helper, not an HTTP endpoint.
-   It scores the best matching chunk per file; that alone does not
    prove whole-document near-duplication.
-   Results classified `unrelated` are still returned by this helper
    unless the caller filters them.
-   The API integration must map these results into the agreed response
    format and add other database fields (such as summaries) if
    required.

## 11. Local setup and commands

Use the project's existing virtual environment and dependencies.

Example `.env` setting for local Qdrant:

``` dotenv
QDRANT_PATH=data/qdrant
```

Alternatively, use a running Qdrant server:

``` dotenv
QDRANT_URL=http://localhost:6333
```

To verify local client/collection setup from the repository root:

``` powershell
python -c "from dotenv import load_dotenv; load_dotenv(); from app.ai_indexing.vector_store import create_client, ensure_collection; c=create_client(); ensure_collection(c); print(c.get_collections()); c.close()"
```

Run the full test suite:

``` powershell
python -m pytest -q
```

Latest reported result: `91 passed, 1 warning`. The warning was a
Starlette/httpx test-client deprecation warning, not a failing test.

## 12. Current test coverage

The tests cover:

-   Skipping empty chunks.
-   Rejecting all-empty input.
-   Rejecting a missing file ID.
-   Successful document indexing and status update.
-   Exact-duplicate record creation.
-   Failed-indexing status handling.
-   Grouping search results by file and sorting by score.
-   Rejecting an empty search query.
-   Rejecting invalid threshold combinations.

The 91 passing tests are the **whole project's test suite** at the time
of the latest run, not 91 tests belonging only to this component.

## 13. Integration contract

### For the extraction component

The indexer expects ordered extracted chunks and an existing file
record. The intended call shape is:

``` python
index_document(
    db,
    qdrant_client,
    file_id=file_id,
    chunks=ordered_chunk_texts,
    filename=filename,
    extension=extension,
)
```

Agree on the actual handoff point with the extraction owner. Do not try
to index empty/scanned content that has not produced usable text;
extraction should report empty/unreadable content and coordinate status
handling.

### For the search/API component

The search helper can be called as:

``` python
search_similar_files(
    qdrant_client,
    chunks=query_chunks,
    limit_per_chunk=10,
)
```

Pass `source_file_id` if the source document should be excluded. Agree
on the final API schema, including whether results require summaries,
excerpts, filters, and pagination. This function does not implement HTTP
concerns.

### Database initialization

`SimilarityMatch` is imported by `app/shared/models/__init__.py`, so it
is included when shared SQLAlchemy metadata is loaded. If the project
uses migrations or standalone SQL schema files, confirm that the new
table is created in every environment.

## 14. Known gaps and next improvements

1.  Document summaries are not generated by this component.
2.  The final HTTP search endpoint is not implemented here.
3.  Semantic matches are not currently persisted by `index_document()`;
    only exact duplicates are.
4.  Whole-document semantic near-duplicate detection is not yet
    implemented; current search keeps the best chunk score.
5.  Thresholds need evaluation on a labeled corpus.
6.  Partial Qdrant writes may remain after an indexing failure.
7.  Empty/scanned-document extraction behavior belongs to the extraction
    component.
8.  A full upload → extract → index → search end-to-end test is still
    needed once the other components are ready.

## 15. Suggested integration/demo checklist

1.  Start the project services using the team's agreed runbook.
2.  Upload a sample text-based document.
3.  Confirm its database record and stored file exist.
4.  Confirm extraction produces non-empty chunks.
5.  Confirm Qdrant contains vectors in `document_chunks`.
6.  Upload an identical copy and verify an `exact_duplicate` record with
    score `1.0`.
7.  Search with wording different from the filename and inspect
    results/excerpts.
8.  Try a related document and an unrelated document to evaluate
    thresholds.
9.  Check status after success and after a controlled failure.
10. Run `python -m pytest -q` and record the actual output.

## 16. Quick reference

  Goal                                         Function
  -------------------------------------------- ------------------------------
  Load embedding model                         `get_model()`
  Embed one string                             `embed_text(text)`
  Embed multiple chunks                        `embed_chunks(chunks)`
  Create/open Qdrant client                    `create_client()`
  Ensure collection exists                     `ensure_collection(client)`
  Store a chunk vector                         `store_chunk(...)`
  Cosine similarity                            `cosine_similarity(a, b)`
  Average vectors                              `average_embedding(vectors)`
  Classify a score                             `classify_similarity(score)`
  Hash file bytes                              `calculate_sha256(content)`
  Compare exact bytes                          `is_exact_duplicate(a, b)`
  Index chunks                                 `index_chunks(...)`
  Index document and record exact duplicates   `index_document(...)`
  Find similar files                           `search_similar_files(...)`
  Run tests                                    `python -m pytest -q`
