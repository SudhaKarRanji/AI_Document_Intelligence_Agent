from datetime import datetime
from uuid import UUID

from pydantic import BaseModel

from ai_docu.schemas.chat import ChatCitation


class ConversationMessageResponse(BaseModel):
    id: UUID
    question: str
    answer: str
    retrieved_chunk_ids: list[str]
    citations: list[ChatCitation]
    created_at: datetime
