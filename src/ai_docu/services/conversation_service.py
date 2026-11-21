from sqlalchemy.orm import Session

from ai_docu.models.conversation import ConversationMessage
from ai_docu.schemas.chat import ChatCitation
from ai_docu.schemas.conversations import ConversationMessageResponse


def get_conversations(session: Session) -> list[ConversationMessageResponse]:
    messages = (
        session.query(ConversationMessage)
        .order_by(ConversationMessage.created_at.desc())
        .all()
    )
    return [
        ConversationMessageResponse(
            id=message.id,
            question=message.question,
            answer=message.answer,
            retrieved_chunk_ids=message.retrieved_chunk_ids or [],
            citations=[
                ChatCitation.model_validate(citation)
                for citation in (message.citations or [])
            ],
            created_at=message.created_at,
        )
        for message in messages
    ]
