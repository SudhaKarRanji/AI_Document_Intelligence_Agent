from fastapi import APIRouter, File, UploadFile

router = APIRouter()


@router.post("/documents/upload", tags=["Documents"], summary="Upload a document", description="Uploads a document to the server.")
async def upload_document(file: UploadFile = File(...)) -> dict[str, str]:
    # Here you would implement the logic to handle the uploaded document.
    # For now, we will just return a success message.
    return {"message": "Document uploaded successfully!"}