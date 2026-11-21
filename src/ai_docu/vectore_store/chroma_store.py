from pathlib import Path

import chromadb


COLLECTION_NAME = "documents"


def get_document_collection(chroma_directory: Path):
    chroma_directory.mkdir(parents=True, exist_ok=True)
    client = chromadb.PersistentClient(path=str(chroma_directory))
    return client.get_or_create_collection(name=COLLECTION_NAME)
