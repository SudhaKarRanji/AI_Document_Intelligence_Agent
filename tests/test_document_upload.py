from collections.abc import Generator
from io import BytesIO
from pathlib import Path
from uuid import UUID

import pytest
import pymupdf
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session
from docx import Document as DocxDocument

from ai_docu.database import Base, get_db_session
from ai_docu.main import app
from ai_docu.models import Document, DocumentChunk
from ai_docu.services.document_chunker import CHUNK_SIZE, CHUNK_OVERLAP, build_text_chunks


def make_pdf_bytes(text: str = "Extractable PDF text") -> bytes:
    pdf = pymupdf.open()
    page = pdf.new_page()
    page.insert_text((72, 72), text)
    content = pdf.tobytes()
    pdf.close()
    return content


def make_docx_bytes(text: str = "Extractable DOCX text") -> bytes:
    document = DocxDocument()
    document.add_paragraph(text)
    buffer = BytesIO()
    document.save(buffer)
    return buffer.getvalue()


@pytest.fixture
def database_engine(tmp_path: Path) -> Generator[Engine, None, None]:
    engine = create_engine(f"sqlite:///{tmp_path / 'documents.db'}")
    Base.metadata.create_all(engine)
    yield engine
    engine.dispose()


@pytest.fixture
def client(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    database_engine: Engine,
) -> Generator[TestClient, None, None]:
    monkeypatch.setattr("ai_docu.services.document_service.DATA_DIRECTORY", tmp_path / "data")
    monkeypatch.setattr(
        "ai_docu.services.document_service.CHROMA_DIRECTORY",
        tmp_path / "chroma_db",
    )

    def mock_store_chunk_embeddings(document, chunks, chroma_directory) -> int:
        return len(chunks)

    monkeypatch.setattr(
        "ai_docu.services.document_service.store_chunk_embeddings",
        mock_store_chunk_embeddings,
    )

    def override_get_db_session() -> Generator[Session, None, None]:
        with Session(database_engine) as session:
            yield session

    app.dependency_overrides[get_db_session] = override_get_db_session
    try:
        with TestClient(app) as test_client:
            yield test_client
    finally:
        app.dependency_overrides.clear()


@pytest.mark.parametrize(
    ("filename", "content_type", "extension"),
    [
        ("report.PDF", "application/pdf", ".pdf"),
        (
            "report.DOCX",
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            ".docx",
        ),
    ],
)
def test_upload_stores_file_and_metadata(
    client: TestClient,
    tmp_path: Path,
    database_engine: Engine,
    filename: str,
    content_type: str,
    extension: str,
) -> None:
    if extension == ".pdf":
        content = make_pdf_bytes()
    else:
        content = make_docx_bytes()
    response = client.post(
        "/documents/upload",
        files={"file": (filename, content, content_type)},
    )

    assert response.status_code == 201
    uploaded = response.json()
    assert uploaded["filename"] == filename
    assert uploaded["size_bytes"] == len(content)
    assert uploaded["extracted_text_preview"]
    assert uploaded["chunk_count"] >= 1
    assert uploaded["embedding_count"] == uploaded["chunk_count"]

    stored_files = list((tmp_path / "data").glob(f"*{extension}"))
    assert len(stored_files) == 1
    assert stored_files[0].read_bytes() == content

    with Session(database_engine) as session:
        document = session.scalar(select(Document))
    assert document is not None
    assert document.original_filename == filename
    assert document.storage_key == stored_files[0].name
    assert document.size_bytes == len(content)
    assert document.extracted_text

    chunks = session.scalars(
        select(DocumentChunk).where(DocumentChunk.document_id == document.id)
    ).all()
    assert len(chunks) >= 1


@pytest.mark.parametrize(
    ("filename", "content", "expected_status"),
    [
        ("report.txt", b"not allowed", 415),
        ("report.pdf", b"x" * (2 * 1024 * 1024), 413),
    ],
)
def test_upload_rejects_unsupported_extension_and_size(
    client: TestClient,
    tmp_path: Path,
    filename: str,
    content: bytes,
    expected_status: int,
) -> None:
    response = client.post(
        "/documents/upload",
        files={"file": (filename, content, "application/octet-stream")},
    )

    assert response.status_code == expected_status
    storage_directory = tmp_path / "data"
    assert not storage_directory.exists() or not any(storage_directory.iterdir())


def test_delete_document_removes_database_record_and_file(
    client: TestClient,
    tmp_path: Path,
    database_engine: Engine,
) -> None:
    upload_response = client.post(
        "/documents/upload",
        files={"file": ("delete-me.pdf", make_pdf_bytes(), "application/pdf")},
    )
    assert upload_response.status_code == 201
    document_id = upload_response.json()["id"]

    delete_response = client.request("DELETE", f"/documents/{document_id}")

    assert delete_response.status_code == 200
    assert delete_response.json()["id"] == document_id
    assert not list((tmp_path / "data").glob("*"))

    with Session(database_engine) as session:
        assert session.get(Document, UUID(document_id)) is None


def test_delete_document_rejects_invalid_id(
    client: TestClient,
) -> None:
    response = client.request("DELETE", "/documents/not-a-uuid")

    assert response.status_code == 404
    assert response.json() == {"detail": "Document not found."}


def test_get_document_by_id_returns_one_document(
    client: TestClient,
) -> None:
    first_upload = client.post(
        "/documents/upload",
        files={"file": ("first.pdf", make_pdf_bytes("First document"), "application/pdf")},
    )
    second_upload = client.post(
        "/documents/upload",
        files={"file": ("second.docx", make_docx_bytes("Second document"), "application/vnd.openxmlformats-officedocument.wordprocessingml.document")},
    )
    assert first_upload.status_code == 201
    assert second_upload.status_code == 201

    first_id = first_upload.json()["id"]
    response = client.get(f"/documents/{first_id}")

    assert response.status_code == 200
    assert response.json()["id"] == first_id
    assert response.json()["filename"] == "first.pdf"


def test_get_document_by_id_rejects_invalid_id(
    client: TestClient,
) -> None:
    response = client.get("/documents/not-a-uuid")

    assert response.status_code == 404
    assert response.json() == {"detail": "Document not found."}


def test_get_documents_query_returns_one_document(
    client: TestClient,
) -> None:
    first_upload = client.post(
        "/documents/upload",
        files={"file": ("first.pdf", make_pdf_bytes("First document"), "application/pdf")},
    )
    second_upload = client.post(
        "/documents/upload",
        files={"file": ("second.docx", make_docx_bytes("Second document"), "application/vnd.openxmlformats-officedocument.wordprocessingml.document")},
    )
    assert first_upload.status_code == 201
    assert second_upload.status_code == 201

    first_id = first_upload.json()["id"]
    response = client.get("/documents", params={"document_id": first_id})

    assert response.status_code == 200
    assert response.json()["id"] == first_id
    assert response.json()["filename"] == "first.pdf"


def test_text_chunks_use_configured_size_and_overlap() -> None:
    text = "a" * (CHUNK_SIZE + 150)
    chunks = build_text_chunks(text)

    assert len(chunks) == 2
    assert chunks[0][0] == 0
    assert chunks[0][1] == CHUNK_SIZE
    assert chunks[1][0] == CHUNK_SIZE - CHUNK_OVERLAP
    assert chunks[1][1] == len(text)
    assert chunks[0][2].endswith(chunks[1][2][:CHUNK_OVERLAP])
