from __future__ import annotations

import hashlib
from functools import lru_cache
from typing import Any

from app.config import CHROMA_PATH, GEMINI_API_KEY, GEMINI_EMBEDDING_DIMENSIONS, GEMINI_EMBEDDING_MODEL
from app.construction_service import EVIDENCE_DIR

COLLECTION_NAME = "sitesignal_construction_evidence"
CHUNK_LIMIT = 900


@lru_cache(maxsize=1)
def _gemini_client():
    if not GEMINI_API_KEY:
        raise RuntimeError("GEMINI_API_KEY is missing from the local .env file.")
    from google import genai
    return genai.Client(api_key=GEMINI_API_KEY)


@lru_cache(maxsize=1)
def _client():
    import chromadb
    CHROMA_PATH.mkdir(parents=True, exist_ok=True)
    return chromadb.PersistentClient(path=str(CHROMA_PATH))


def _collection():
    return _client().get_or_create_collection(
        name=COLLECTION_NAME,
        metadata={"hnsw:space": "cosine", "domain": "synthetic construction project evidence"},
    )


def evidence_fingerprint() -> str:
    """Hash of everything the index depends on: the evidence files, the embedding model and size,
    and the chunking limit. A persisted index built from anything else is stale."""
    digest = hashlib.sha256(f"{GEMINI_EMBEDDING_MODEL}|{GEMINI_EMBEDDING_DIMENSIONS}|{CHUNK_LIMIT}".encode())
    for file in sorted(EVIDENCE_DIR.glob("*.md")):
        digest.update(b"\0" + file.name.encode() + b"\0" + file.read_bytes())
    return digest.hexdigest()


def _expected_chunks() -> int:
    return sum(len(_chunks(f.read_text(encoding="utf-8"))) for f in sorted(EVIDENCE_DIR.glob("*.md")))


def _chunks(text: str, limit: int = CHUNK_LIMIT) -> list[str]:
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
    fingerprint = evidence_fingerprint()
    docs: list[str] = []
    ids: list[str] = []
    metadata: list[dict[str, str]] = []
    for file in files:
        for index, chunk in enumerate(_chunks(file.read_text(encoding="utf-8"))):
            docs.append(chunk)
            ids.append(f"{file.stem}-{index}")
            metadata.append({"source": file.name, "chunk": str(index + 1), "domain": "construction",
                             "fingerprint": fingerprint})
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
    # Rebuild rather than upsert: upsert leaves behind chunks of files that were edited shorter or removed.
    try:
        _client().delete_collection(COLLECTION_NAME)
    except Exception:  # no collection yet
        pass
    _collection().add(ids=ids, documents=docs, embeddings=vectors, metadatas=metadata)
    return len(docs)


def search_construction_evidence(query: str, top_k: int = 4) -> dict[str, Any]:
    from google.genai import types
    if not query.strip():
        raise ValueError("Evidence search query cannot be empty.")
    collection = _collection()
    count = collection.count()
    if count == 0:
        raise RuntimeError("Construction evidence is not indexed. Run: python -m app.ingest_construction")
    if construction_rag_status().get("stale"):
        raise RuntimeError(
            "The construction evidence index is out of date with the evidence files. "
            "Run: python -m app.ingest_construction"
        )
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
    """ready: the index exists and matches the evidence files on disk. stale: it exists but does not."""
    try:
        collection = _collection()
        count = collection.count()
        if count == 0:
            return {"ready": False, "stale": False, "chunks": 0}
        stored = (collection.get(limit=1, include=["metadatas"]).get("metadatas") or [{}])[0] or {}
        stale = stored.get("fingerprint") != evidence_fingerprint() or count != _expected_chunks()
        return {"ready": not stale, "stale": stale, "chunks": count,
                **({"reason": "index does not match the evidence files; re-run python -m app.ingest_construction"} if stale else {})}
    except Exception as exc:
        return {"ready": False, "stale": False, "chunks": 0, "reason": str(exc)}
