from fastapi import APIRouter, Depends, Form
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from ai_docu.services.chat_service import ask_documents
from ai_docu.schemas.chat import ChatAnswerResponse
from ai_docu.database import get_db_session
from ai_docu.schemas.conversations import ConversationMessageResponse
from ai_docu.services.conversation_service import get_conversations

router = APIRouter()    


class ChatQuestionRequest(BaseModel):
    question: str = Field(min_length=1)



@router.post("/chat", tags=["Chat"], summary="Chat with the AI", description="Send a message to the AI and receive a response.")
async def chat_with_ai(message: str = Form(...)) -> dict[str, str]:
    # Here you would implement the logic to handle the chat message and generate a response.
    # For now, we will just return a placeholder response.
    return {"response": f"AI response to your message: {message}"}


@router.post(
    "/api/v1/chat/ask",
    tags=["Chat"],
    summary="Ask a question",
    description="Retrieves five relevant chunks and asks the Ollama chat model.",
)
def ask_question(
    request: ChatQuestionRequest,
    session: Session = Depends(get_db_session),
) -> ChatAnswerResponse:
    return ask_documents(request.question, session)


@router.get(
    "/api/v1/conversations",
    tags=["Chat"],
    summary="Get conversation history",
    response_model=list[ConversationMessageResponse],
)
def list_conversations(
    session: Session = Depends(get_db_session),
) -> list[ConversationMessageResponse]:
    return get_conversations(session)