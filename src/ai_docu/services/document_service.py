from pathlib import Path
from uuid import UUID, uuid4

from fastapi import HTTPException, UploadFile
from sqlalchemy.orm import Session

from ai_docu.config import DATA_DIRECTORY
from ai_docu.database import Base
from ai_docu.models import Document
from ai_docu.schemas.documents import DocumentUploadResponse

MAX_FILE_SIZE_BYTES = 2 * 1024 * 1024
ALLOWED_EXTENSIONS = {".pdf", ".docx"}
CHUNK_SIZE_BYTES = 64 * 1024


def save_document(file: UploadFile, session: Session) -> DocumentUploadResponse:
    original_filename = file.filename
    if not original_filename:
        raise HTTPException(status_code=400, detail="A filename is required.")

    extension = Path(original_filename.replace("\\", "/")).suffix.lower()
    if extension not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=415,
            detail="Only PDF and DOCX files are accepted.",
        )

    document_id = uuid4()
    storage_key = f"{document_id}{extension}"
    temporary_path = DATA_DIRECTORY / f".{document_id}.tmp"
    destination_path = DATA_DIRECTORY / storage_key
    DATA_DIRECTORY.mkdir(parents=True, exist_ok=True)

    size_bytes = 0
    try:
        with temporary_path.open("xb") as destination:
            while chunk := file.file.read(CHUNK_SIZE_BYTES):
                size_bytes += len(chunk)
                if size_bytes >= MAX_FILE_SIZE_BYTES:
                    raise HTTPException(
                        status_code=413,
                        detail="File size must be smaller than 2 MiB.",
                    )
                destination.write(chunk)

        if size_bytes == 0:
            raise HTTPException(status_code=400, detail="The uploaded file is empty.")

        temporary_path.replace(destination_path)
        persisted = False
        try:
            document = Document(
                id=document_id,
                original_filename=original_filename,
                storage_key=storage_key,
                file_extension=extension,
                size_bytes=size_bytes,
                content_type=file.content_type,
            )
            Base.metadata.create_all(bind=session.get_bind())
            with session.begin():
                session.add(document)
            persisted = True

            return DocumentUploadResponse(
                id=document.id,
                filename=document.original_filename,
                size_bytes=document.size_bytes,
                uploaded_at=document.uploaded_at,
            )
        finally:
            if not persisted:
                destination_path.unlink(missing_ok=True)
    finally:
        temporary_path.unlink(missing_ok=True)

def get_all_documents(session: Session) -> list[DocumentUploadResponse]:
    documents = session.query(Document).all()
    return [
        DocumentUploadResponse(
            id=document.id,
            filename=document.original_filename,
            size_bytes=document.size_bytes,
            uploaded_at=document.uploaded_at,
        )
        for document in documents
    ]

def get_document_by_id(document_id: str | UUID, session: Session) -> DocumentUploadResponse:
    try:
        parsed_document_id = document_id if isinstance(document_id, UUID) else UUID(document_id)
    except (AttributeError, TypeError, ValueError):
        raise HTTPException(status_code=404, detail="Document not found.")

    document = session.get(Document, parsed_document_id)
    if not document:
        raise HTTPException(status_code=404, detail="Document not found.")
    return DocumentUploadResponse(
        id=document.id,
        filename=document.original_filename,
        size_bytes=document.size_bytes,
        uploaded_at=document.uploaded_at,
    )

def delete_document_by_id(document_id: str | UUID, session: Session) -> DocumentUploadResponse:
    try:
        parsed_document_id = document_id if isinstance(document_id, UUID) else UUID(document_id)
    except (AttributeError, TypeError, ValueError):
        raise HTTPException(status_code=404, detail="Document not found.")

    document = session.get(Document, parsed_document_id)
    if not document:
        raise HTTPException(status_code=404, detail="Document not found.")

    response = DocumentUploadResponse(
        id=document.id,
        filename=document.original_filename,
        size_bytes=document.size_bytes,
        uploaded_at=document.uploaded_at,
    )
    storage_path = DATA_DIRECTORY / document.storage_key

    session.delete(document)
    session.commit()

    storage_path.unlink(missing_ok=True)
    return response
