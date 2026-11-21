from pydantic import BaseModel


class ChatCitation(BaseModel):
    document_id: str
    filename: str
    page_start: int | None = None
    page_end: int | None = None
    paragraph_start: int | None = None
    paragraph_end: int | None = None


class ChatAnswerResponse(BaseModel):
    answer: str
    retrieved_chunk_ids: list[str]
    citations: list[ChatCitation]
