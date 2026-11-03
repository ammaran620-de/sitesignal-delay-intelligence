from __future__ import annotations

from functools import lru_cache
from typing import Any

from app.config import CHROMA_PATH, GEMINI_API_KEY, GEMINI_EMBEDDING_DIMENSIONS, GEMINI_EMBEDDING_MODEL
from app.construction_service import EVIDENCE_DIR

COLLECTION_NAME = "sitesignal_construction_evidence"


@lru_cache(maxsize=1)
def _gemini_client():
    if not GEMINI_API_KEY:
        raise RuntimeError("GEMINI_API_KEY is missing from the local .env file.")
    from google import genai
    return genai.Client(api_key=GEMINI_API_KEY)


@lru_cache(maxsize=1)
def _collection():
    import chromadb
    CHROMA_PATH.mkdir(parents=True, exist_ok=True)
    client = chromadb.PersistentClient(path=str(CHROMA_PATH))
    return client.get_or_create_collection(
        name=COLLECTION_NAME,
        metadata={"hnsw:space": "cosine", "domain": "synthetic construction project evidence"},
    )


def _chunks(text: str, limit: int = 900) -> list[str]:
    paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
    output: list[str] = []
    current = ""
    for paragraph in paragraphs:
        if len(paragraph) > limit:
            if current:
                output.append(current)
                current = ""
            output.extend(paragraph[i:i + limit] for i in range(0, len(paragraph), limit))
            continue
        candidate = f"{current}\n\n{paragraph}" if current else paragraph
        if len(candidate) > limit and current:
            output.append(current)
            current = paragraph
        else:
            current = candidate
    if current:
        output.append(current)
    return output


def ingest_construction_evidence() -> int:
    from google.genai import types
    files = sorted(EVIDENCE_DIR.glob("*.md"))
    if not files:
        raise RuntimeError(f"No Markdown evidence files found in {EVIDENCE_DIR}")
    docs: list[str] = []
    ids: list[str] = []
    metadata: list[dict[str, str]] = []
    for file in files:
        for index, chunk in enumerate(_chunks(file.read_text(encoding="utf-8"))):
            docs.append(chunk)
            ids.append(f"{file.stem}-{index}")
            metadata.append({"source": file.name, "chunk": str(index + 1), "domain": "construction"})
    response = _gemini_client().models.embed_content(
        model=GEMINI_EMBEDDING_MODEL,
        contents=docs,
        config=types.EmbedContentConfig(
            task_type="RETRIEVAL_DOCUMENT",
            output_dimensionality=GEMINI_EMBEDDING_DIMENSIONS,
        ),
    )
    vectors = [item.values for item in (response.embeddings or [])]
    if len(vectors) != len(docs) or any(vector is None for vector in vectors):
        raise RuntimeError("Gemini returned an unexpected number of construction evidence embeddings.")
    _collection().upsert(ids=ids, documents=docs, embeddings=vectors, metadatas=metadata)
    return len(docs)


def search_construction_evidence(query: str, top_k: int = 4) -> dict[str, Any]:
    from google.genai import types
    if not query.strip():
        raise ValueError("Evidence search query cannot be empty.")
    collection = _collection()
    count = collection.count()
    if count == 0:
        raise RuntimeError("Construction evidence is not indexed. Run: python -m app.ingest_construction")
    response = _gemini_client().models.embed_content(
        model=GEMINI_EMBEDDING_MODEL,
        contents=query,
        config=types.EmbedContentConfig(
            task_type="RETRIEVAL_QUERY",
            output_dimensionality=GEMINI_EMBEDDING_DIMENSIONS,
        ),
    )
    if not response.embeddings or response.embeddings[0].values is None:
        raise RuntimeError("Gemini did not return a query embedding.")
    result = collection.query(
        query_embeddings=[response.embeddings[0].values],
        n_results=min(max(top_k, 1), count),
        include=["documents", "metadatas", "distances"],
    )
    docs = (result.get("documents") or [[]])[0]
    metas = (result.get("metadatas") or [[]])[0]
    distances = (result.get("distances") or [[]])[0]
    matches = []
    for text, meta, distance in zip(docs, metas, distances):
        meta = meta or {}
        matches.append({
            "text": text,
            "source": meta.get("source", "unknown"),
            "chunk": meta.get("chunk", "?"),
            "distance": round(float(distance), 4) if distance is not None else None,
        })
    return {"query": query, "matches": matches, "synthetic_evidence": True}


def construction_rag_status() -> dict[str, Any]:
    try:
        count = _collection().count()
        return {"ready": count > 0, "chunks": count}
    except Exception as exc:
        return {"ready": False, "chunks": 0, "reason": str(exc)}
