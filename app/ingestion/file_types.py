"""
Which file types we accept, and a check that the file's CONTENT really is
that type.

Why check content? A file's extension and the MIME type the browser sends are
both chosen by the user's computer, so neither can be trusted on its own
(Windows, for example, sends CSV files as "application/vnd.ms-excel").
Every real file type starts with recognisable bytes (a "magic number"),
so we look at those bytes instead.
"""
import io
import zipfile

# extension -> MIME type we store in the database
SUPPORTED_TYPES: dict[str, str] = {
    "pdf": "application/pdf",
    "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "txt": "text/plain",
    "csv": "text/csv",
    "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "png": "image/png",
    "jpg": "image/jpeg",
    "jpeg": "image/jpeg",
}


def clean_filename(raw_name: str | None) -> str:
    """
    Keep only the file's own name, e.g. 'C:\\Users\\me\\report.pdf' -> 'report.pdf'.
    Folder parts are removed so a name like '../../secret.txt' can never be
    used as a path. (Files are saved under their file_id anyway.)
    """
    if not raw_name:
        return ""
    name = raw_name.replace("\\", "/").split("/")[-1]
    name = "".join(ch for ch in name if ch.isprintable()).strip()
    if len(name) > 255:  # fit the database column, keep the extension
        stem, dot, ext = name.rpartition(".")
        name = stem[: 255 - len(ext) - 1] + dot + ext if dot else name[:255]
    return name


def get_extension(filename: str) -> str:
    """'Report.Final.PDF' -> 'pdf'. Returns '' when there is no extension."""
    stem, dot, ext = filename.rpartition(".")
    if not dot or not stem:  # 'README' or '.gitignore'
        return ""
    return ext.lower()


def is_supported(extension: str) -> bool:
    return extension in SUPPORTED_TYPES


def content_matches_extension(extension: str, data: bytes) -> bool:
    """True if the file's bytes look like the type its extension claims."""
    if extension == "pdf":
        return b"%PDF-" in data[:1024]
    if extension == "docx":
        return _zip_contains(data, "word/document.xml")
    if extension == "xlsx":
        return _zip_contains(data, "xl/workbook.xml")
    if extension == "png":
        return data.startswith(b"\x89PNG\r\n\x1a\n")
    if extension in ("jpg", "jpeg"):
        return data.startswith(b"\xff\xd8\xff")
    if extension in ("txt", "csv"):
        return _looks_like_text(data)
    return False


def _zip_contains(data: bytes, required_name: str) -> bool:
    """DOCX and XLSX files are really ZIP archives with a known file inside."""
    try:
        with zipfile.ZipFile(io.BytesIO(data)) as archive:
            return required_name in archive.namelist()
    except zipfile.BadZipFile:
        return False


def _looks_like_text(data: bytes) -> bool:
    """
    Simple rule used by tools like Git: binary files almost always contain a
    zero byte near the start; text files do not. UTF-16 text (which does
    contain zero bytes) is allowed when it starts with a byte-order mark.
    """
    if data.startswith((b"\xff\xfe", b"\xfe\xff")):
        return True
    return b"\x00" not in data[:8192]
