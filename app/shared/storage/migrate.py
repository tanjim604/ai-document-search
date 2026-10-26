"""
Move files saved on local disk into the database.

    python -m app.shared.storage.migrate               copy every old file into the database
    python -m app.shared.storage.migrate --delete-old  also delete the local copies afterwards

Safe to run again: files already in the database are skipped, and a local copy is only
deleted after the database copy has been read back and matches the stored SHA-256.
"""
import hashlib
import sys
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.shared.models.file import File
from app.shared.storage.base import StorageBackend
from app.shared.storage.database import DatabaseStorage


@dataclass
class MigrationReport:
    moved: int = 0
    already_in_database: int = 0
    missing: int = 0
    mismatched: int = 0
    deleted_old: int = 0


def move_files_to_database(
    db: Session, storage: DatabaseStorage, legacy: StorageBackend, delete_old: bool = False
) -> MigrationReport:
    report = MigrationReport()
    for record in db.scalars(select(File).order_by(File.created_at)).all():
        if storage.is_database_path(record.storage_path):
            report.already_in_database += 1
            continue
        old_path = record.storage_path
        try:
            data = legacy.read_bytes(old_path)
        except (FileNotFoundError, ValueError):
            report.missing += 1
            continue
        new_path = storage.save(record.id, record.extension, data)
        if hashlib.sha256(storage.read_bytes(new_path)).hexdigest() != record.sha256_hash:
            storage.delete(new_path)  # never keep a copy that does not match
            report.mismatched += 1
            continue
        record.storage_path = new_path
        db.commit()
        report.moved += 1
        if delete_old:
            legacy.delete(old_path)
            report.deleted_old += 1
    return report


if __name__ == "__main__":
    from app.shared.config.settings import get_settings
    from app.shared.database import get_session_factory, init_db
    from app.shared.storage.local import LocalStorage

    init_db()  # make sure the stored_files table exists
    factory = get_session_factory()
    legacy = LocalStorage(get_settings().upload_dir)
    with factory() as session:
        result = move_files_to_database(
            session, DatabaseStorage(factory, fallback=legacy), legacy, delete_old="--delete-old" in sys.argv
        )
    print(result)
