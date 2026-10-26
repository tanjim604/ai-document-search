"""The database storage adapter and the tool that moves old files into it."""
import hashlib

import pytest

from app.shared.models.file import File
from app.shared.models.stored_file import StoredFile
from app.shared.storage.database import DatabaseStorage
from app.shared.storage.migrate import move_files_to_database


@pytest.fixture
def db_storage(session_factory, storage):
    return DatabaseStorage(session_factory, fallback=storage)


def test_save_and_read_back(db_storage):
    path = db_storage.save("f_abc", "pdf", b"%PDF-1.4 data")

    assert path == "db/pdf/f_abc.pdf"
    assert db_storage.read_bytes(path) == b"%PDF-1.4 data"
    assert db_storage.exists(path)


def test_save_never_overwrites(db_storage):
    db_storage.save("f_same", "txt", b"first")
    with pytest.raises(FileExistsError):
        db_storage.save("f_same", "txt", b"second")


def test_delete_removes_the_row_and_ignores_missing(db_storage, db_session):
    path = db_storage.save("f_del", "txt", b"x")
    db_storage.delete(path)
    db_storage.delete(path)

    assert not db_storage.exists(path)
    assert db_session.query(StoredFile).count() == 0


def test_reading_a_missing_file_raises(db_storage):
    with pytest.raises(FileNotFoundError):
        db_storage.read_bytes("db/pdf/f_nothing.pdf")


def test_binary_content_survives_unchanged(db_storage):
    data = bytes(range(256)) * 50
    assert db_storage.read_bytes(db_storage.save("f_bin", "png", data)) == data


def test_old_local_paths_are_still_readable_through_the_fallback(db_storage, storage):
    old = storage.save("f_old", "txt", b"saved before the switch")
    assert db_storage.read_bytes(old) == b"saved before the switch"
    assert db_storage.exists(old)


def test_local_path_without_a_fallback_raises(session_factory, storage):
    old = storage.save("f_old", "txt", b"x")
    with pytest.raises(FileNotFoundError):
        DatabaseStorage(session_factory).read_bytes(old)


def add_local_file(db, storage, file_id, data, *, hash_override=None):
    path = storage.save(file_id, "txt", data)
    db.add(File(id=file_id, filename=f"{file_id}.txt", extension="txt", mime_type="text/plain",
                storage_path=path, sha256_hash=hash_override or hashlib.sha256(data).hexdigest()))
    db.commit()
    return path


def test_migration_moves_files_and_updates_their_records(db_session, db_storage, storage):
    old = add_local_file(db_session, storage, "f_1", b"first file")
    add_local_file(db_session, storage, "f_2", b"second file")

    report = move_files_to_database(db_session, db_storage, storage)

    assert (report.moved, report.missing, report.mismatched) == (2, 0, 0)
    record = db_session.get(File, "f_1")
    assert record.storage_path == "db/txt/f_1.txt"
    assert db_storage.read_bytes(record.storage_path) == b"first file"
    assert storage.exists(old)  # the local copy is kept unless asked otherwise


def test_migration_can_be_repeated(db_session, db_storage, storage):
    add_local_file(db_session, storage, "f_1", b"data")
    move_files_to_database(db_session, db_storage, storage)

    again = move_files_to_database(db_session, db_storage, storage)

    assert (again.moved, again.already_in_database) == (0, 1)


def test_migration_deletes_local_copies_only_when_asked(db_session, db_storage, storage):
    old = add_local_file(db_session, storage, "f_1", b"data")
    report = move_files_to_database(db_session, db_storage, storage, delete_old=True)

    assert report.deleted_old == 1 and not storage.exists(old)


def test_migration_reports_files_missing_from_disk(db_session, db_storage, storage):
    old = add_local_file(db_session, storage, "f_gone", b"data")
    storage.delete(old)

    report = move_files_to_database(db_session, db_storage, storage)

    assert report.missing == 1 and db_session.get(File, "f_gone").storage_path == old


def test_migration_refuses_a_copy_that_does_not_match_the_stored_hash(db_session, db_storage, storage):
    old = add_local_file(db_session, storage, "f_bad", b"data", hash_override="0" * 64)

    report = move_files_to_database(db_session, db_storage, storage, delete_old=True)

    assert report.mismatched == 1 and report.moved == 0
    assert storage.exists(old)                       # nothing was deleted
    assert not db_storage.exists("db/txt/f_bad.txt")  # and no bad copy was kept
