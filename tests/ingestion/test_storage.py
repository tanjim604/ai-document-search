"""Unit tests for the local storage adapter."""
import pytest


def test_save_and_read_back(storage, upload_root):
    path = storage.save("f_abc", "pdf", b"%PDF-1.4 data")

    assert path == (upload_root / "pdf" / "f_abc.pdf").as_posix()
    assert storage.read_bytes(path) == b"%PDF-1.4 data"
    assert storage.exists(path)


def test_files_are_sorted_into_extension_folders(storage, upload_root):
    storage.save("f_1", "pdf", b"a")
    storage.save("f_2", "txt", b"b")
    storage.save("f_3", "pdf", b"c")

    assert sorted(p.name for p in (upload_root / "pdf").iterdir()) == ["f_1.pdf", "f_3.pdf"]
    assert [p.name for p in (upload_root / "txt").iterdir()] == ["f_2.txt"]


def test_save_never_overwrites_an_existing_file(storage):
    storage.save("f_same", "txt", b"first")
    with pytest.raises(FileExistsError):
        storage.save("f_same", "txt", b"second")


def test_delete_removes_file_and_ignores_missing(storage):
    path = storage.save("f_del", "txt", b"x")
    storage.delete(path)
    assert not storage.exists(path)
    storage.delete(path)  # second delete does not raise


def test_paths_outside_upload_folder_are_refused(storage, tmp_path):
    secret = tmp_path / "secret.env"
    secret.write_text("API_KEY=123")

    with pytest.raises(ValueError):
        storage.read_bytes(str(secret))
    with pytest.raises(ValueError):
        storage.delete(str(secret))
    assert secret.exists()
