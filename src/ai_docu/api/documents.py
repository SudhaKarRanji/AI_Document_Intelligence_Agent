from fastapi import APIRouter, Depends, File, Query, UploadFile
from sqlalchemy.orm import Session
from uuid import UUID

from ai_docu.database import get_db_session
from ai_docu.schemas.documents import DocumentUploadResponse
from ai_docu.services.document_service import delete_document_by_id, get_all_documents, get_document_by_id, save_document

router = APIRouter()


@router.post(
    "/documents/upload",
    tags=["Documents"],
    summary="Upload a document",
    description="Uploads a PDF or DOCX smaller than 2 MiB.",
    status_code=201,
    response_model=DocumentUploadResponse,
)
def upload_document(
    file: UploadFile = File(...),
    session: Session = Depends(get_db_session),
) -> DocumentUploadResponse:
    return save_document(file, session)

@router.get("/documents", tags=["Documents"],
            summary="List all documents",
            description="Returns a list of all uploaded documents.")
def list_documents(
    document_id: UUID | None = Query(default=None),
    session: Session = Depends(get_db_session),
) -> list[DocumentUploadResponse] | DocumentUploadResponse:
    if document_id is not None:
        return get_document_by_id(str(document_id), session)
    return get_all_documents(session)

@router.get("/documents/{document_id}", tags=["Documents"],
            summary="Get document by ID",
            description="Returns the document with the specified ID.")
def get_document(
    document_id: str,
    session: Session = Depends(get_db_session),
) -> DocumentUploadResponse:
    return get_document_by_id(document_id, session)

@router.delete("/documents/{document_id}", tags=["Documents"],
               summary="Delete document by ID",
               description="Deletes the document with the specified ID.")
def delete_document(
    document_id: str,
    session: Session = Depends(get_db_session),
) -> DocumentUploadResponse:
    return delete_document_by_id(document_id, session)