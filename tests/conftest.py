"""
Shared test setup.

Every test gets:
  * a brand-new empty database (SQLite file in a temp folder by default,
    or your PostgreSQL TEST database if TEST_DATABASE_URL is set), and
  * a brand-new empty upload folder.
So the tests can be run again and again without cleaning anything by hand.
"""
import io
import os
import tempfile
import zipfile

from dotenv import load_dotenv

load_dotenv()
TEST_DATABASE_URL = os.getenv("TEST_DATABASE_URL")

# Set BEFORE importing the app, so tests never touch the real development
# database or the real data/uploads folder.
os.environ["DATABASE_URL"] = "sqlite://"
os.environ["UPLOAD_DIR"] = tempfile.mkdtemp(prefix="ai-docs-test-")

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import create_engine  # noqa: E402
from sqlalchemy.orm import sessionmaker  # noqa: E402

from app.main import app  # noqa: E402
from app.shared.config.settings import Settings, get_settings  # noqa: E402
from app.shared.database import get_db, init_db  # noqa: E402
from app.shared.models import Base  # noqa: E402
from app.shared.storage import LocalStorage, get_storage  # noqa: E402

@pytest.fixture(autouse=True)
def no_app_password(monkeypatch):
    """A developer's local .env password must not lock the tests out."""
    monkeypatch.delenv("APP_PASSWORD", raising=False)


TEST_MAX_UPLOAD_BYTES = 10_000  # small limit so size tests are fast


@pytest.fixture
def engine(tmp_path):
    if TEST_DATABASE_URL:
        eng = create_engine(TEST_DATABASE_URL)
        Base.metadata.drop_all(eng)  # start from empty tables
    else:
        eng = create_engine(
            f"sqlite:///{tmp_path / 'test.db'}",
            connect_args={"check_same_thread": False},
        )
    init_db(eng)
    yield eng
    if TEST_DATABASE_URL:
        Base.metadata.drop_all(eng)
    eng.dispose()


@pytest.fixture
def session_factory(engine):
    return sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


@pytest.fixture
def db_session(session_factory):
    session = session_factory()
    yield session
    session.close()


@pytest.fixture
def upload_root(tmp_path):
    return tmp_path / "uploads"


@pytest.fixture
def storage(upload_root):
    return LocalStorage(upload_root)


@pytest.fixture
def test_settings(upload_root):
    return Settings(
        database_url="(test)",
        upload_dir=str(upload_root),
        max_upload_size_bytes=TEST_MAX_UPLOAD_BYTES,
        storage_backend="local",
        auto_process=False,  # ingestion tests only check the upload itself
    )


@pytest.fixture
def client(session_factory, storage, test_settings):
    """A TestClient wired to the test database and test upload folder."""

    def override_get_db():
        db = session_factory()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_storage] = lambda: storage
    app.dependency_overrides[get_settings] = lambda: test_settings
    yield TestClient(app)
    app.dependency_overrides.clear()


# ------------------------------------------------------------ sample bytes ----
def _zip_with(*names: str) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        for name in names:
            archive.writestr(name, "<xml/>")
    return buffer.getvalue()


@pytest.fixture
def sample_bytes() -> dict[str, bytes]:
    """Small but valid-looking content for every supported extension."""
    return {
        "txt": b"The history of AI began in the 1950s.\n",
        "csv": b"title,year\nPerceptron,1958\n",
        "pdf": b"%PDF-1.4\n1 0 obj << >> endobj\ntrailer << >>\n%%EOF\n",
        "docx": _zip_with("[Content_Types].xml", "word/document.xml"),
        "xlsx": _zip_with("[Content_Types].xml", "xl/workbook.xml"),
        "png": b"\x89PNG\r\n\x1a\n" + b"\x00" * 32,
        "jpg": b"\xff\xd8\xff\xe0" + b"\x00" * 32,
        "jpeg": b"\xff\xd8\xff\xe0" + b"\x00" * 32,
    }
