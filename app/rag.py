from __future__ import annotations

from pathlib import Path
from typing import Any

from app.config import (
    CHROMA_PATH,
    GEMINI_API_KEY,
    GEMINI_EMBEDDING_DIMENSIONS,
    GEMINI_EMBEDDING_MODEL,
    POLICY_PATH,
)

COLLECTION_NAME = "dealership_operations_policies"


def _client():
    if not GEMINI_API_KEY:
        raise RuntimeError("GEMINI_API_KEY is not configured in the local .env file.")
    from google import genai
    return genai.Client(api_key=GEMINI_API_KEY)


def split_into_chunks(text: str, max_chars: int = 900) -> list[str]:
    paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
    chunks: list[str] = []
    current = ""
    for paragraph in paragraphs:
        if len(paragraph) > max_chars:
            if current:
                chunks.append(current)
                current = ""
            for start in range(0, len(paragraph), max_chars):
                chunks.append(paragraph[start : start + max_chars])
            continue
        candidate = f"{current}\n\n{paragraph}" if current else paragraph
        if len(candidate) > max_chars and current:
            chunks.append(current)
            current = paragraph
        else:
            current = candidate
    if current:
        chunks.append(current)
    return chunks


def _collection():
    import chromadb
    CHROMA_PATH.mkdir(parents=True, exist_ok=True)
    client = chromadb.PersistentClient(path=str(CHROMA_PATH))
    return client.get_or_create_collection(
        name=COLLECTION_NAME,
        metadata={"hnsw:space": "cosine", "description": "Synthetic dealership policy knowledge base"},
    )


def ingest_policies() -> int:
    files = sorted(POLICY_PATH.glob("*.md"))
    if not files:
        raise RuntimeError(f"No .md policy files found in {POLICY_PATH}")

    chunks: list[str] = []
    ids: list[str] = []
    metadatas: list[dict[str, str]] = []
    for file_path in files:
        text = file_path.read_text(encoding="utf-8")
        for index, chunk in enumerate(split_into_chunks(text)):
            chunks.append(chunk)
            ids.append(f"{file_path.stem}-{index}")
            metadatas.append({"source": file_path.name, "chunk": str(index + 1)})

    from google.genai import types
    response = _client().models.embed_content(
        model=GEMINI_EMBEDDING_MODEL,
        contents=chunks,
        config=types.EmbedContentConfig(
            task_type="RETRIEVAL_DOCUMENT",
            output_dimensionality=GEMINI_EMBEDDING_DIMENSIONS,
        ),
    )
    vectors = [embedding.values for embedding in (response.embeddings or [])]
    if len(vectors) != len(chunks):
        raise RuntimeError("The embedding API returned an unexpected number of vectors.")

    collection = _collection()
    collection.upsert(ids=ids, documents=chunks, embeddings=vectors, metadatas=metadatas)
    return len(chunks)


def search_policies(query: str, top_k: int = 3) -> list[dict[str, Any]]:
    collection = _collection()
    if collection.count() == 0:
        raise RuntimeError("The policy knowledge base is empty. Run: python -m app.ingest")

    from google.genai import types
    response = _client().models.embed_content(
        model=GEMINI_EMBEDDING_MODEL,
        contents=query,
        config=types.EmbedContentConfig(
            task_type="RETRIEVAL_QUERY",
            output_dimensionality=GEMINI_EMBEDDING_DIMENSIONS,
        ),
    )
    if not response.embeddings:
        raise RuntimeError("The embedding API returned no query vector.")

    result = collection.query(
        query_embeddings=[response.embeddings[0].values],
        n_results=min(top_k, collection.count()),
        include=["documents", "metadatas", "distances"],
    )
    documents = (result.get("documents") or [[]])[0]
    metadatas = (result.get("metadatas") or [[]])[0]
    distances = (result.get("distances") or [[]])[0]
    return [
        {
            "text": doc,
            "source": meta.get("source", "unknown"),
            "chunk": meta.get("chunk", "?"),
            "distance": round(float(distance), 4) if distance is not None else None,
        }
        for doc, meta, distance in zip(documents, metadatas, distances)
    ]


def knowledge_base_status() -> dict[str, Any]:
    try:
        count = _collection().count()
        return {"ready": count > 0, "chunks": count}
    except Exception as exc:
        return {"ready": False, "chunks": 0, "reason": str(exc)}
