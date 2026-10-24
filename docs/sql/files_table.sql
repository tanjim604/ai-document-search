-- files table (owner: Tahmid - ingestion and storage)
--
-- You normally do NOT need to run this by hand: the app creates the table
-- automatically on startup (init_db() in app/shared/database.py).
-- This file documents the exact schema PostgreSQL 16 created from
-- app/shared/models/file.py, and can be run manually in psql or pgAdmin
-- if the team prefers to create tables with SQL.

CREATE TABLE IF NOT EXISTS files (
    id                 VARCHAR(40)  NOT NULL PRIMARY KEY,   -- file_id, e.g. f_3f2a9c...
    filename           VARCHAR(255) NOT NULL,               -- original name, not unique
    extension          VARCHAR(10)  NOT NULL,               -- pdf, docx, txt, csv, xlsx, png, jpg, jpeg
    mime_type          VARCHAR(100) NOT NULL,               -- confirmed from file content
    storage_path       VARCHAR(500) NOT NULL UNIQUE,        -- data/uploads/<ext>/<file_id>.<ext>
    sha256_hash        VARCHAR(64)  NOT NULL,               -- exact-duplicate fingerprint
    processing_status  VARCHAR(20)  NOT NULL,               -- uploaded, extracting, extracted, indexing, indexed, failed
    created_at         TIMESTAMP WITH TIME ZONE NOT NULL
);

CREATE INDEX IF NOT EXISTS ix_files_extension         ON files (extension);
CREATE INDEX IF NOT EXISTS ix_files_processing_status ON files (processing_status);
CREATE INDEX IF NOT EXISTS ix_files_sha256_hash       ON files (sha256_hash);

-- Useful queries for checking your work ---------------------------------

-- Every uploaded file, newest first
-- SELECT id, filename, extension, processing_status, created_at FROM files ORDER BY created_at DESC;

-- Files grouped by extension
-- SELECT extension, COUNT(*) FROM files GROUP BY extension ORDER BY extension;

-- Groups of exact duplicates (same bytes uploaded more than once)
-- SELECT sha256_hash, COUNT(*), array_agg(filename) FROM files GROUP BY sha256_hash HAVING COUNT(*) > 1;
