"""The evidence index against a real ChromaDB in a temp directory, with deterministic fake embeddings.

Gemini is never called. The point is the index lifecycle: an index built from older evidence must be detected as
stale, refused by search, and rebuilt without leaving chunks of edited or removed files behind.
"""
from __future__ import annotations

import hashlib
import shutil
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from app import construction_rag as rag
from app import construction_service as service
from app import db, main


def fake_vector(text: str, dims: int = 8) -> list[float]:
    h = hashlib.sha256(text.encode()).digest()
    return [b / 255 for b in h[:dims]]


class FakeEmbeddings:
    calls = 0

    def embed_content(self, model, contents, config):
        FakeEmbeddings.calls += 1
        texts = [contents] if isinstance(contents, str) else contents
        return SimpleNamespace(embeddings=[SimpleNamespace(values=fake_vector(t)) for t in texts])


@pytest.fixture
def index(tmp_path, monkeypatch):
    docs = tmp_path / "docs"
    shutil.copytree(service.EVIDENCE_DIR, docs)
    monkeypatch.setattr(rag, "EVIDENCE_DIR", docs)
    monkeypatch.setattr(service, "EVIDENCE_DIR", docs)
    monkeypatch.setattr(rag, "CHROMA_PATH", tmp_path / "chroma")
    monkeypatch.setattr(rag, "_gemini_client", lambda: SimpleNamespace(models=FakeEmbeddings()))
    rag._client.cache_clear()
    yield SimpleNamespace(docs=docs)
    rag._client.cache_clear()


def sources_in_index():
    got = rag._collection().get(include=["metadatas"])
    return {m["source"] for m in got["metadatas"]}


def test_fresh_index_is_ready_and_searchable(index):
    assert rag.construction_rag_status() == {"ready": False, "stale": False, "chunks": 0}
    n = rag.ingest_construction_evidence()
    status = rag.construction_rag_status()
    assert status == {"ready": True, "stale": False, "chunks": n}
    result = rag.search_construction_evidence("structural approval")
    assert result["matches"] and {m["source"] for m in result["matches"]} <= {p.name for p in index.docs.glob("*.md")}


def test_editing_an_evidence_file_makes_the_index_stale_and_search_refuses_it(index):
    rag.ingest_construction_evidence()
    report = index.docs / "site_report_001.md"
    report.write_text(report.read_text(encoding="utf-8").replace("2026-11-09", "2026-11-10"), encoding="utf-8")

    status = rag.construction_rag_status()
    assert status["ready"] is False and status["stale"] is True
    with pytest.raises(RuntimeError, match="out of date"):
        rag.search_construction_evidence("structural approval")

    rag.ingest_construction_evidence()
    assert rag.construction_rag_status()["ready"] is True
    texts = " ".join(rag.search_construction_evidence("approval date", top_k=8)["matches"][i]["text"]
                     for i in range(len(rag.search_construction_evidence("approval date", top_k=8)["matches"])))
    assert "2026-11-10" in texts


def test_reindexing_after_removing_a_file_leaves_no_chunks_of_it(index):
    rag.ingest_construction_evidence()
    assert "site_report_002.md" in sources_in_index()
    (index.docs / "site_report_002.md").unlink()
    assert rag.construction_rag_status()["stale"] is True
    rag.ingest_construction_evidence()
    assert "site_report_002.md" not in sources_in_index()
    assert rag.construction_rag_status()["ready"] is True


def test_reindexing_after_a_file_shrinks_drops_the_surplus_chunks(index):
    big = index.docs / "site_report_001.md"
    big.write_text(big.read_text(encoding="utf-8") + ("\n\nExtra paragraph. " + "x" * 850) * 6, encoding="utf-8")
    rag.ingest_construction_evidence()
    before = rag._collection().count()
    big.write_text("# Short\n\nOnly this remains.\n", encoding="utf-8")
    rag.ingest_construction_evidence()
    after = rag._collection().count()
    assert after < before and rag.construction_rag_status()["ready"] is True
    assert not [i for i in rag._collection().get()["ids"] if i.startswith("site_report_001-") and int(i.rsplit("-", 1)[1]) > 0]


def test_changing_the_embedding_model_or_size_makes_the_index_stale(index, monkeypatch):
    rag.ingest_construction_evidence()
    monkeypatch.setattr(rag, "GEMINI_EMBEDDING_MODEL", "some-other-embedding-model")
    assert rag.construction_rag_status()["stale"] is True
    monkeypatch.undo()
    monkeypatch.setattr(rag, "GEMINI_EMBEDDING_DIMENSIONS", 256)
    assert rag.construction_rag_status()["stale"] is True


def test_adding_a_file_makes_the_index_stale(index):
    rag.ingest_construction_evidence()
    (index.docs / "site_report_003.md").write_text("# New report\n\nSomething new.\n", encoding="utf-8")
    assert rag.construction_rag_status()["stale"] is True


@pytest.fixture
def app_client(index, database, monkeypatch):
    monkeypatch.setattr(main, "GEMINI_API_KEY", "test-key-not-real")
    return TestClient(main.app)


def test_startup_rebuilds_a_stale_index(index, app_client):
    rag.ingest_construction_evidence()
    (index.docs / "site_report_003.md").write_text("# New report\n\nSomething new.\n", encoding="utf-8")
    with app_client as client:
        health = client.get("/api/health").json()
    assert health["construction_rag_ready"] is True and health["construction_rag_stale"] is False
    assert "site_report_003.md" in sources_in_index()


def test_startup_survives_an_embedding_failure_and_reports_it(index, app_client, monkeypatch):
    def fail(*_a, **_k):
        raise RuntimeError("embedding service down")
    monkeypatch.setattr(main, "ingest_construction_evidence", fail)
    with app_client as client:
        health = client.get("/api/health").json()
    assert health["status"] == "healthy" and health["construction_rag_ready"] is False


def test_startup_does_not_reindex_a_current_index(index, app_client):
    rag.ingest_construction_evidence()
    FakeEmbeddings.calls = 0
    with app_client as client:
        assert client.get("/api/health").json()["construction_rag_ready"] is True
    assert FakeEmbeddings.calls == 0
