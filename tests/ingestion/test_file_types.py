"""Unit tests for filename cleaning, extension detection, content checks and hashing."""
import pytest

from app.ingestion.file_types import clean_filename, content_matches_extension, get_extension
from app.ingestion.hashing import sha256_hex


@pytest.mark.parametrize(
    "raw, expected",
    [
        ("report.pdf", "report.pdf"),
        ("  spaced name.docx  ", "spaced name.docx"),
        ("../../etc/passwd.txt", "passwd.txt"),
        ("C:\\Users\\me\\notes.txt", "notes.txt"),
        ("bad\x00name\n.txt", "badname.txt"),
        ("", ""),
        (None, ""),
    ],
)
def test_clean_filename(raw, expected):
    assert clean_filename(raw) == expected


def test_clean_filename_shortens_very_long_names_but_keeps_extension():
    cleaned = clean_filename("a" * 300 + ".pdf")
    assert len(cleaned) == 255
    assert cleaned.endswith(".pdf")


@pytest.mark.parametrize(
    "filename, expected",
    [
        ("paper.pdf", "pdf"),
        ("Paper.PDF", "pdf"),
        ("my.final.report.docx", "docx"),
        ("backup.tar.gz", "gz"),
        ("README", ""),
        (".gitignore", ""),
        ("notes.", ""),
    ],
)
def test_get_extension(filename, expected):
    assert get_extension(filename) == expected


def test_every_sample_matches_its_own_extension(sample_bytes):
    for extension, data in sample_bytes.items():
        assert content_matches_extension(extension, data), extension


@pytest.mark.parametrize(
    "extension, data",
    [
        ("pdf", b"hello"),
        ("docx", b"PK\x03\x04 not a real zip"),
        ("png", b"\xff\xd8\xff jpeg bytes"),
        ("jpg", b"\x89PNG\r\n\x1a\n png bytes"),
        ("txt", b"abc\x00def"),
        ("exe", b"MZ"),
    ],
)
def test_wrong_content_is_detected(extension, data):
    assert content_matches_extension(extension, data) is False


def test_docx_and_xlsx_are_not_confused(sample_bytes):
    assert content_matches_extension("docx", sample_bytes["xlsx"]) is False
    assert content_matches_extension("xlsx", sample_bytes["docx"]) is False


def test_utf16_text_with_byte_order_mark_is_accepted():
    assert content_matches_extension("txt", "Hello".encode("utf-16"))


def test_sha256_known_value():
    # Published test vector for "abc"
    assert sha256_hex(b"abc") == (
        "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad"
    )


def test_sha256_is_64_hex_characters():
    digest = sha256_hex(b"anything")
    assert len(digest) == 64
    int(digest, 16)  # raises if not hex
