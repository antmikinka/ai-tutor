"""Knowledge base: chunking, embedders, stores, ingest/search and the REST API."""

import asyncio

import pytest

from services import knowledge_service as ks


# --------------------------------------------------------------------------- #
# Unit
# --------------------------------------------------------------------------- #


def test_chunk_text_respects_size_and_overlap():
    paragraphs = [f"Paragraph {i}. " + ("word " * 40) for i in range(12)]
    text = "\n\n".join(paragraphs)
    chunks = ks.chunk_text(text, chunk_chars=500, overlap_chars=60)
    assert len(chunks) > 1
    assert all(len(c["text"]) <= 500 + 60 + 2 for c in chunks)
    assert [c["index"] for c in chunks] == list(range(len(chunks)))
    # Overlap: the tail of chunk 0 should appear at the start of chunk 1
    assert chunks[0]["text"][-30:] in chunks[1]["text"]


def test_chunk_text_tracks_pdf_page_markers_and_strips_them():
    text = "[Page 1]\nIntro text.\n\n[Page 2]\nMore text about derivatives."
    chunks = ks.chunk_text(text, chunk_chars=2000, overlap_chars=0)
    assert len(chunks) == 1
    assert "[Page" not in chunks[0]["text"]
    assert chunks[0]["page"] == 2


def test_chunk_text_splits_huge_paragraph():
    text = "Sentence number one is here. " * 200
    chunks = ks.chunk_text(text, chunk_chars=400, overlap_chars=0)
    assert len(chunks) >= 10
    assert all(len(c["text"]) <= 400 for c in chunks)


def test_hashing_embedder_is_deterministic_and_normalised():
    emb = ks.HashingEmbedder(dimension=256)
    a, b = emb.embed(["solve linear equations", "solve linear equations"])
    assert a == b
    assert abs(sum(x * x for x in a) - 1.0) < 1e-6
    sim_related = sum(x * y for x, y in zip(*emb.embed(["linear equations algebra", "solving a linear equation"])))
    sim_unrelated = sum(x * y for x, y in zip(*emb.embed(["linear equations algebra", "chocolate cake recipe"])))
    assert sim_related > sim_unrelated


def test_extract_text_rejects_unknown_extension():
    with pytest.raises(ks.UnsupportedDocumentError):
        ks.extract_text("notes.docx", b"...")


def test_extract_text_decodes_markdown():
    text, meta = ks.extract_text("notes.md", "# Title\n\nBody é".encode("utf-8"))
    assert "Body é" in text and meta == {}


def test_extract_text_pdf(tmp_path):
    pypdf = pytest.importorskip("pypdf")
    from pypdf import PdfWriter

    writer = PdfWriter()
    writer.add_blank_page(width=200, height=200)
    out = tmp_path / "blank.pdf"
    with out.open("wb") as fh:
        writer.write(fh)
    with pytest.raises(ks.UnsupportedDocumentError, match="No extractable text"):
        ks.extract_text("blank.pdf", out.read_bytes())


@pytest.mark.parametrize("store_factory", ["local", pytest.param("chroma", marks=pytest.mark.skipif(not ks.HAS_CHROMA, reason="chromadb missing"))])
def test_vector_store_roundtrip(tmp_path, store_factory):
    store = ks.LocalStore(tmp_path / "s.json") if store_factory == "local" else ks.ChromaStore(tmp_path / "chroma", "t__hashing")
    emb = ks.HashingEmbedder(64)
    texts = ["linear equations", "derivatives and integrals", "ratios and proportion"]
    store.add([f"d1:{i}" for i in range(3)], texts, emb.embed(texts), [{"doc_id": "d1", "chunk_index": i} for i in range(3)])
    store.add(["d2:0"], ["more calculus derivatives"], emb.embed(["more calculus derivatives"]), [{"doc_id": "d2", "chunk_index": 0}])
    assert store.count() == 4

    hits = store.query(emb.embed(["derivative"])[0], k=2)
    assert hits and "derivative" in hits[0].text
    only_d2 = store.query(emb.embed(["derivative"])[0], k=5, doc_ids=["d2"])
    assert {h.metadata["doc_id"] for h in only_d2} == {"d2"}

    assert store.delete_document("d1") == 3
    assert store.count() == 1
    store.clear()
    assert store.count() == 0


# --------------------------------------------------------------------------- #
# Service
# --------------------------------------------------------------------------- #


@pytest.fixture
def knowledge(settings, tmp_path):
    from config.settings import create_settings

    s = create_settings(**{**settings.model_dump(), "knowledge_dir": tmp_path / "kb", "knowledge_embedding": "hashing"})
    service = ks.KnowledgeService(s)
    asyncio.run(service.initialize())
    assert service.is_initialized, service.error
    return service


def test_service_ingest_search_delete_persist(knowledge, tmp_path):
    doc = knowledge.add_text("Algebra", "Linear equations: ax + b = c. Isolate the variable.\n\nRatios compare quantities.", tags=["algebra"])
    assert doc["chunks"] >= 1 and doc["tags"] == ["algebra"]
    knowledge.add_file("calc.md", b"# Calculus\n\nThe derivative is a rate of change. Velocity is the derivative of position.")

    results = knowledge.search("derivative rate of change", k=2)
    assert results and results[0]["title"] == "calc"
    assert {"chunk_id", "doc_id", "title", "score", "text", "page"} <= set(results[0])

    assert knowledge.search("", k=3) == []
    status = knowledge.status()
    assert status["documents"] == 2 and status["chunks"] >= 2 and status["embedding"] == "hashing"

    # A fresh service on the same directory sees the same documents.
    reopened = ks.KnowledgeService(knowledge.settings)
    asyncio.run(reopened.initialize())
    assert {d["id"] for d in reopened.list_documents()} == {d["id"] for d in knowledge.list_documents()}
    assert reopened.search("linear equations", k=1)[0]["title"] == "Algebra"

    assert knowledge.delete_document(doc["id"]) is True
    assert knowledge.delete_document(doc["id"]) is False
    assert knowledge.status()["documents"] == 1
    knowledge.clear()
    assert knowledge.status() ["documents"] == 0 and knowledge.status()["chunks"] == 0


def test_service_rejects_empty_and_oversized(knowledge):
    with pytest.raises(ValueError):
        knowledge.add_text("Empty", "   ")
    knowledge.settings.knowledge_max_document_chars = 10
    with pytest.raises(ValueError, match="too large"):
        knowledge.add_text("Big", "x" * 50)


# --------------------------------------------------------------------------- #
# API
# --------------------------------------------------------------------------- #


def test_knowledge_api_flow(client):
    status = client.get("/api/knowledge/status").json()
    assert status["available"] is True
    assert ".pdf" in status["supported_extensions"]

    created = client.post("/api/knowledge/documents/text", json={"title": "Notes", "text": "Percent problems: a discount of 20% means paying 80%.", "tags": ["percent"]})
    assert created.status_code == 201
    doc_id = created.json()["id"]

    uploaded = client.post("/api/knowledge/documents/upload", files={"file": ("geo.txt", b"Perimeter of a rectangle is 2(w + l).", "text/plain")}, data={"tags": "geometry, shapes"})
    assert uploaded.status_code == 201
    assert uploaded.json()["tags"] == ["geometry", "shapes"]

    bad = client.post("/api/knowledge/documents/upload", files={"file": ("x.exe", b"MZ", "application/octet-stream")})
    assert bad.status_code == 415

    listing = client.get("/api/knowledge/documents").json()
    assert listing["total"] >= 2

    search = client.post("/api/knowledge/search", json={"query": "discount percent", "k": 1}).json()
    assert search["results"][0]["doc_id"] == doc_id

    assert client.get(f"/api/knowledge/documents/{doc_id}").status_code == 200
    assert client.delete(f"/api/knowledge/documents/{doc_id}").status_code == 200
    assert client.get(f"/api/knowledge/documents/{doc_id}").status_code == 404
    assert client.post("/api/knowledge/search", json={"query": "", "k": 1}).status_code == 422
    assert client.delete("/api/knowledge/documents").json() == {"cleared": True}
