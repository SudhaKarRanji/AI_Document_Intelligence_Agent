import os

import httpx
from fastapi import HTTPException

from ai_docu.config import CHROMA_DIRECTORY
from ai_docu.services.embedding_service import create_embeddings
from ai_docu.vectore_store.chroma_store import get_document_collection
from ai_docu.schemas.chat import ChatAnswerResponse, ChatCitation
from ai_docu.models.conversation import ConversationMessage
from sqlalchemy.orm import Session


OLLAMA_CHAT_URL = os.getenv(
    "OLLAMA_CHAT_URL",
    "http://127.0.0.1:11434/api/chat",
)
OLLAMA_CHAT_MODEL = os.getenv("OLLAMA_CHAT_MODEL", "gemma4:latest")
RETRIEVAL_COUNT = 5


def ask_documents(question: str, session: Session) -> ChatAnswerResponse:
    question_embeddings = create_embeddings([question])
    if not question_embeddings:
        raise RuntimeError("Ollama did not return a question embedding.")

    collection = get_document_collection(CHROMA_DIRECTORY)
    results = collection.query(
        query_embeddings=question_embeddings,
        n_results=RETRIEVAL_COUNT,
        include=["documents", "metadatas"],
    )

    documents = results.get("documents") or [[]]
    metadatas = results.get("metadatas") or [[]]
    ids = results.get("ids") or [[]]
    context_chunks = documents[0]
    context_metadata = metadatas[0]

    context_parts: list[str] = []
    citations: list[ChatCitation] = []
    citation_keys: set[tuple] = set()
    for chunk, metadata in zip(context_chunks, context_metadata):
        filename = metadata.get("filename", "unknown")
        chunk_index = metadata.get("chunk_index")
        context_parts.append(
            f"[Source: {filename}, chunk {chunk_index}]\n{chunk}"
        )
        page_start = metadata.get("page_start")
        page_end = metadata.get("page_end")
        paragraph_start = metadata.get("paragraph_start")
        paragraph_end = metadata.get("paragraph_end")
        page_start = page_start if isinstance(page_start, int) and page_start >= 0 else None
        page_end = page_end if isinstance(page_end, int) and page_end >= 0 else None
        paragraph_start = (
            paragraph_start
            if isinstance(paragraph_start, int) and paragraph_start >= 0
            else None
        )
        paragraph_end = (
            paragraph_end
            if isinstance(paragraph_end, int) and paragraph_end >= 0
            else None
        )
        citation_key = (
            str(metadata.get("document_id", "")),
            filename,
            page_start,
            page_end,
            paragraph_start,
            paragraph_end,
        )
        if citation_key not in citation_keys:
            citation_keys.add(citation_key)
            citations.append(
                ChatCitation(
                    document_id=str(metadata.get("document_id", "")),
                    filename=filename,
                    page_start=page_start,
                    page_end=page_end,
                    paragraph_start=paragraph_start,
                    paragraph_end=paragraph_end,
                )
            )

    prompt = (
        "Answer the question using only the provided context. "
        "If the context is insufficient, say that it does not contain enough information.\n\n"
        f"Context:\n{chr(10).join(context_parts)}\n\n"
        f"Question:\n{question}"
    )

    try:
        response = httpx.post(
            OLLAMA_CHAT_URL,
            json={
                "model": OLLAMA_CHAT_MODEL,
                "messages": [
                    {
                        "role": "system",
                        "content": "You are a document question-answering assistant.",
                    },
                    {"role": "user", "content": prompt},
                ],
                "stream": False,
            },
            timeout=180.0,
        )
        response.raise_for_status()
    except (httpx.HTTPError, RuntimeError) as error:
        raise HTTPException(
            status_code=502,
            detail="The Ollama chat service is unavailable.",
        ) from error
    payload = response.json()
    message = payload.get("message") or {}
    answer = message.get("content")
    if not isinstance(answer, str):
        raise RuntimeError("Ollama returned an unexpected chat response.")

    retrieved_ids = ids[0] if ids else []
    result = ChatAnswerResponse(
        answer=answer,
        retrieved_chunk_ids=retrieved_ids,
        citations=citations,
    )

    message = ConversationMessage(
        question=question,
        answer=result.answer,
        retrieved_chunk_ids=result.retrieved_chunk_ids,
        citations=[citation.model_dump() for citation in result.citations],
    )
    try:
        with session.begin():
            session.add(message)
    except Exception as error:
        raise HTTPException(
            status_code=500,
            detail="The answer was generated, but conversation history could not be saved.",
        ) from error

    return result
