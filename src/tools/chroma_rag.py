from __future__ import annotations

from pathlib import Path
import os
import uuid

import chromadb


def _client() -> chromadb.PersistentClient:
    db_path = Path(os.getenv("CHROMA_DB_PATH", "./chroma_db"))
    db_path.mkdir(parents=True, exist_ok=True)
    return chromadb.PersistentClient(path=str(db_path))


def _collection_name(client_id: str) -> str:
    safe = "".join(ch if ch.isalnum() or ch in ("-", "_") else "_" for ch in client_id)
    return f"client_{safe}"


def upsert_documents(*, client_id: str, texts: list[str], source_ref: str) -> int:
    if not texts:
        return 0

    collection = _client().get_or_create_collection(name=_collection_name(client_id))
    ids = [str(uuid.uuid4()) for _ in texts]
    metadatas = [{"client_id": client_id, "source_ref": source_ref} for _ in texts]
    collection.add(ids=ids, documents=texts, metadatas=metadatas)
    return len(texts)


def search_vectors(*, client_id: str, query: str, k: int = 5) -> list[dict]:
    collection = _client().get_or_create_collection(name=_collection_name(client_id))

    try:
        result = collection.query(query_texts=[query], n_results=max(1, k))
        ids = result.get("ids", [[]])[0]
        docs = result.get("documents", [[]])[0]
        distances = result.get("distances", [[]])[0] if result.get("distances") else []

        payload: list[dict] = []
        for idx, doc_id in enumerate(ids):
            doc = docs[idx] if idx < len(docs) else ""
            distance = distances[idx] if idx < len(distances) else None
            score = None if distance is None else round(max(0.0, 1.0 - float(distance)), 4)
            payload.append(
                {
                    "id": doc_id,
                    "score": score,
                    "snippet": (doc or "")[:300],
                }
            )
        return payload
    except Exception:
        return []
