import os

import httpx

from ai_docu.models.document_chunk import DocumentChunk
from ai_docu.models.document import Document
from ai_docu.vectore_store.chroma_store import get_document_collection


OLLAMA_EMBED_URL = os.getenv("OLLAMA_EMBED_URL", "http://127.0.0.1:11434/api/embed")
OLLAMA_EMBED_MODEL = os.getenv("OLLAMA_EMBED_MODEL", "nomic-embed-text")


def create_embeddings(texts: list[str]) -> list[list[float]]:
    if not texts:
        return []

    response = httpx.post(
        OLLAMA_EMBED_URL,
        json={"model": OLLAMA_EMBED_MODEL, "input": texts},
        timeout=120.0,
    )
    response.raise_for_status()
    payload = response.json()
    embeddings = payload.get("embeddings")
    if not isinstance(embeddings, list) or len(embeddings) != len(texts):
        raise RuntimeError("Ollama returned an unexpected embedding response.")
    return embeddings


def store_chunk_embeddings(
    document: Document,
    chunks: list[DocumentChunk],
    chroma_directory,
) -> int:
    if not chunks:
        return 0

    embeddings = create_embeddings([chunk.text for chunk in chunks])
    collection = get_document_collection(chroma_directory)
    collection.upsert(
        ids=[f"{document.id}:{chunk.chunk_index}" for chunk in chunks],
        embeddings=embeddings,
        documents=[chunk.text for chunk in chunks],
        metadatas=[
            {
                "document_id": str(document.id),
                "filename": document.original_filename,
                "chunk_index": chunk.chunk_index,
                "start_char": chunk.start_char,
                "end_char": chunk.end_char,
                "page_start": chunk.page_start if chunk.page_start is not None else -1,
                "page_end": chunk.page_end if chunk.page_end is not None else -1,
                "paragraph_start": (
                    chunk.paragraph_start
                    if chunk.paragraph_start is not None
                    else -1
                ),
                "paragraph_end": (
                    chunk.paragraph_end
                    if chunk.paragraph_end is not None
                    else -1
                ),
            }
            for chunk in chunks
        ],
    )
    return len(chunks)
