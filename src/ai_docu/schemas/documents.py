from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class DocumentUploadResponse(BaseModel):
    id: UUID
    filename: str
    size_bytes: int
    uploaded_at: datetime
    extracted_text_preview: str | None = None
    chunk_count: int = 0
    embedding_count: int = 0
