from types import SimpleNamespace

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from ai_docu.main import app
import ai_docu.services.chat_service as chat_service
from ai_docu.database import Base, get_db_session


class FakeCollection:
    def query(self, **kwargs):
        assert len(kwargs["query_embeddings"]) == 1
        assert kwargs["n_results"] == 5
        return {
            "ids": [["document-id:0", "document-id:1"]],
            "documents": [["first context", "second context"]],
            "metadatas": [
                [
                    {
                        "document_id": "document-1",
                        "filename": "first.pdf",
                        "chunk_index": 0,
                        "page_start": 1,
                        "page_end": 2,
                        "paragraph_start": -1,
                        "paragraph_end": -1,
                    },
                    {
                        "document_id": "document-2",
                        "filename": "second.docx",
                        "chunk_index": 1,
                        "page_start": -1,
                        "page_end": -1,
                        "paragraph_start": 3,
                        "paragraph_end": 4,
                    },
                ]
            ],
        }


def test_chat_ask_retrieves_context_and_calls_ollama(
    monkeypatch,
    tmp_path,
) -> None:
    monkeypatch.setattr(
        chat_service,
        "create_embeddings",
        lambda texts: [[0.1, 0.2]],
    )
    monkeypatch.setattr(
        chat_service,
        "get_document_collection",
        lambda _: FakeCollection(),
    )

    def fake_post(*args, **kwargs):
        assert kwargs["json"]["messages"][1]["content"].find("first.pdf") >= 0
        return SimpleNamespace(
            json=lambda: {"message": {"content": "The answer is in the context."}},
            raise_for_status=lambda: None,
        )

    monkeypatch.setattr(chat_service.httpx, "post", fake_post)

    engine = create_engine(f"sqlite:///{tmp_path / 'chat.db'}")
    Base.metadata.create_all(engine)

    def override_get_db_session():
        with Session(engine) as session:
            yield session

    app.dependency_overrides[get_db_session] = override_get_db_session
    try:
        with TestClient(app) as client:
            response = client.post(
                "/api/v1/chat/ask",
                json={"question": "What does the document say?"},
            )
            history = client.get("/api/v1/conversations")
    finally:
        app.dependency_overrides.clear()
        engine.dispose()

    assert response.status_code == 200
    assert response.json()["answer"] == "The answer is in the context."
    assert response.json()["retrieved_chunk_ids"] == [
        "document-id:0",
        "document-id:1",
    ]
    assert response.json()["citations"] == [
        {
            "document_id": "document-1",
            "filename": "first.pdf",
            "page_start": 1,
            "page_end": 2,
            "paragraph_start": None,
            "paragraph_end": None,
        },
        {
            "document_id": "document-2",
            "filename": "second.docx",
            "page_start": None,
            "page_end": None,
            "paragraph_start": 3,
            "paragraph_end": 4,
        },
    ]
    assert history.status_code == 200
    assert len(history.json()) == 1
    assert history.json()[0]["question"] == "What does the document say?"
