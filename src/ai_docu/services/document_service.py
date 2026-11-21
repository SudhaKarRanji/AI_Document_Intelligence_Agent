from pathlib import Path
from uuid import UUID, uuid4

from fastapi import HTTPException, UploadFile
from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from ai_docu.config import CHROMA_DIRECTORY, DATA_DIRECTORY
from ai_docu.database import Base
from ai_docu.models import Document
from ai_docu.models.document_chunk import DocumentChunk
from ai_docu.parsers.document_extractor import DocumentExtractionError, extract_document_text
from ai_docu.schemas.documents import DocumentUploadResponse
from ai_docu.services.document_chunker import build_document_chunks
from ai_docu.services.embedding_service import store_chunk_embeddings

MAX_FILE_SIZE_BYTES = 2 * 1024 * 1024
ALLOWED_EXTENSIONS = {".pdf", ".docx"}
CHUNK_SIZE_BYTES = 64 * 1024
TEXT_PREVIEW_LENGTH = 500


def get_chunk_count(document_id: UUID, session: Session) -> int:
    count = session.scalar(
        select(func.count())
        .select_from(DocumentChunk)
        .where(DocumentChunk.document_id == document_id)
    )
    return count or 0


def build_upload_response(
    document: Document,
    chunk_count: int = 0,
    embedding_count: int = 0,
) -> DocumentUploadResponse:
    preview = document.extracted_text[:TEXT_PREVIEW_LENGTH] if document.extracted_text else None
    return DocumentUploadResponse(
        id=document.id,
        filename=document.original_filename,
        size_bytes=document.size_bytes,
        uploaded_at=document.uploaded_at,
        extracted_text_preview=preview,
        chunk_count=chunk_count,
        embedding_count=embedding_count,
    )


def ensure_extracted_text_column(session: Session) -> None:
    bind = session.get_bind()
    if bind.dialect.name == "postgresql":
        with session.begin():
            session.execute(
                text(
                    "ALTER TABLE documents "
                    "ADD COLUMN IF NOT EXISTS extracted_text TEXT"
                )
            )


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
            ensure_extracted_text_column(session)
            try:
                document.extracted_text = extract_document_text(destination_path)
            except DocumentExtractionError as error:
                raise HTTPException(status_code=422, detail=str(error)) from error
            chunk_ranges = build_document_chunks(destination_path, document.extracted_text)
            with session.begin():
                session.add(document)
                session.flush()
                chunks: list[DocumentChunk] = []
                for chunk_index, chunk_range in enumerate(chunk_ranges):
                    chunk_text = document.extracted_text[
                        chunk_range.start_char:chunk_range.end_char
                    ]
                    chunk = DocumentChunk(
                        document_id=document.id,
                        chunk_index=chunk_index,
                        text=chunk_text,
                        start_char=chunk_range.start_char,
                        end_char=chunk_range.end_char,
                        page_start=chunk_range.page_start,
                        page_end=chunk_range.page_end,
                        paragraph_start=chunk_range.paragraph_start,
                        paragraph_end=chunk_range.paragraph_end,
                    )
                    session.add(chunk)
                    chunks.append(chunk)
                session.flush()
                try:
                    embedding_count = store_chunk_embeddings(
                        document,
                        chunks,
                        CHROMA_DIRECTORY,
                    )
                except Exception as error:
                    raise HTTPException(
                        status_code=502,
                        detail="Document uploaded, but embedding creation failed.",
                    ) from error
            persisted = True

            return build_upload_response(
                document,
                len(chunk_ranges),
                embedding_count,
            )
        finally:
            if not persisted:
                destination_path.unlink(missing_ok=True)
    finally:
        temporary_path.unlink(missing_ok=True)

def get_all_documents(session: Session) -> list[DocumentUploadResponse]:
    documents = session.query(Document).all()
    return [
        build_upload_response(document, get_chunk_count(document.id, session))
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
    return build_upload_response(document, get_chunk_count(document.id, session))

def delete_document_by_id(document_id: str | UUID, session: Session) -> DocumentUploadResponse:
    try:
        parsed_document_id = document_id if isinstance(document_id, UUID) else UUID(document_id)
    except (AttributeError, TypeError, ValueError):
        raise HTTPException(status_code=404, detail="Document not found.")

    document = session.get(Document, parsed_document_id)
    if not document:
        raise HTTPException(status_code=404, detail="Document not found.")

    response = build_upload_response(document, get_chunk_count(document.id, session))
    storage_path = DATA_DIRECTORY / document.storage_key

    session.delete(document)
    session.commit()

    storage_path.unlink(missing_ok=True)
    return response
