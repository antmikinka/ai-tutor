"""
Course-material knowledge base: ingest documents, embed chunks, retrieve
relevant passages for practice-problem generation and tutoring.

Storage: Chroma (persistent, cosine HNSW) when ``chromadb`` is installed,
otherwise a small numpy-backed store with the same interface.

Embeddings: Chroma's bundled all-MiniLM-L6-v2 ONNX model when it can be
loaded (downloaded on first use, ~80 MB, no torch needed); otherwise a
deterministic hashing embedder that works fully offline. The embedder name is
part of the collection name, so switching embedders never mixes vector spaces.
"""

from __future__ import annotations

import hashlib
import json
import logging
import math
import re
import threading
import uuid
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Protocol, Sequence, Tuple

from config.settings import get_settings
from services.common import utc_now_iso

logger = logging.getLogger(__name__)

try:
    import chromadb

    HAS_CHROMA = True
except Exception:  # pragma: no cover - import side effects vary by version
    chromadb = None  # type: ignore[assignment]
    HAS_CHROMA = False

try:
    import numpy as np
except ImportError:  # pragma: no cover
    np = None  # type: ignore[assignment]


SUPPORTED_EXTENSIONS = {".txt", ".md", ".markdown", ".csv", ".tex", ".pdf", ".json"}


# --------------------------------------------------------------------------- #
# Embedders
# --------------------------------------------------------------------------- #


class Embedder(Protocol):
    name: str
    dimension: int

    def embed(self, texts: Sequence[str]) -> List[List[float]]: ...


_TOKEN_RE = re.compile(r"[a-z0-9]+|[=+\-*/^<>≤≥∫∑√π]", re.IGNORECASE)


class HashingEmbedder:
    """
    Offline bag-of-features embedding: word unigrams + bigrams + character
    trigrams hashed into a fixed number of buckets with sign hashing, sublinear
    tf, L2-normalised. No model download, deterministic, ~0.1 ms per chunk.
    Quality is well below MiniLM but adequate for topical retrieval.
    """

    name = "hashing"

    def __init__(self, dimension: int = 1024):
        self.dimension = dimension

    @staticmethod
    def _features(text: str) -> Iterable[str]:
        tokens = [t.lower() for t in _TOKEN_RE.findall(text)]
        for tok in tokens:
            yield f"w:{tok}"
            if len(tok) >= 5:
                for i in range(len(tok) - 2):
                    yield f"c:{tok[i:i + 3]}"
        for a, b in zip(tokens, tokens[1:]):
            yield f"b:{a}_{b}"

    def _embed_one(self, text: str) -> List[float]:
        counts: Dict[int, float] = {}
        for feat in self._features(text):
            digest = hashlib.blake2b(feat.encode("utf-8"), digest_size=8).digest()
            value = int.from_bytes(digest, "little")
            bucket = value % self.dimension
            sign = 1.0 if (value >> 63) & 1 else -1.0
            counts[bucket] = counts.get(bucket, 0.0) + sign
        vec = [0.0] * self.dimension
        for bucket, count in counts.items():
            vec[bucket] = math.copysign(1.0 + math.log(abs(count)), count) if count else 0.0
        norm = math.sqrt(sum(v * v for v in vec)) or 1.0
        return [v / norm for v in vec]

    def embed(self, texts: Sequence[str]) -> List[List[float]]:
        return [self._embed_one(t) for t in texts]


class MiniLMEmbedder:
    """all-MiniLM-L6-v2 via Chroma's ONNX runtime (no torch)."""

    name = "minilm"
    dimension = 384

    def __init__(self):
        from chromadb.utils import embedding_functions

        self._fn = embedding_functions.DefaultEmbeddingFunction()
        # Force the model download / load now so failures surface at startup.
        self._fn(["warm up"])

    def embed(self, texts: Sequence[str]) -> List[List[float]]:
        vectors = self._fn(list(texts))
        return [[float(x) for x in vec] for vec in vectors]


def build_embedder(preference: str) -> Embedder:
    preference = (preference or "auto").lower()
    if preference in ("auto", "minilm") and HAS_CHROMA:
        try:
            embedder = MiniLMEmbedder()
            logger.info("Knowledge base embeddings: all-MiniLM-L6-v2 (ONNX)")
            return embedder
        except Exception as exc:
            if preference == "minilm":
                logger.error("MiniLM embedder requested but unavailable: %s", exc)
            else:
                logger.warning("MiniLM embedder unavailable (%s); using offline hashing embedder", str(exc)[:200])
    logger.info("Knowledge base embeddings: hashing (offline)")
    return HashingEmbedder()


# --------------------------------------------------------------------------- #
# Vector stores
# --------------------------------------------------------------------------- #


@dataclass
class Hit:
    chunk_id: str
    text: str
    score: float  # cosine similarity in [0, 1]
    metadata: Dict[str, Any]


class VectorStore(Protocol):
    backend: str

    def add(self, ids: List[str], texts: List[str], embeddings: List[List[float]], metadatas: List[Dict[str, Any]]) -> None: ...
    def query(self, embedding: List[float], k: int, doc_ids: Optional[List[str]] = None) -> List[Hit]: ...
    def delete_document(self, doc_id: str) -> int: ...
    def count(self) -> int: ...
    def clear(self) -> None: ...


class ChromaStore:
    backend = "chroma"

    def __init__(self, path: Path, collection: str):
        self._client = chromadb.PersistentClient(path=str(path))
        self._collection_name = collection
        self._col = self._client.get_or_create_collection(
            collection, metadata={"hnsw:space": "cosine"}, embedding_function=None
        )

    def add(self, ids, texts, embeddings, metadatas):
        # Chroma has a per-call batch cap; stay well under it.
        for start in range(0, len(ids), 256):
            end = start + 256
            self._col.add(ids=ids[start:end], documents=texts[start:end], embeddings=embeddings[start:end], metadatas=metadatas[start:end])

    def query(self, embedding, k, doc_ids=None):
        total = self._col.count()
        if total == 0:
            return []
        where = {"doc_id": {"$in": doc_ids}} if doc_ids else None
        result = self._col.query(
            query_embeddings=[embedding],
            n_results=min(k, total),
            where=where,
            include=["documents", "metadatas", "distances"],
        )
        hits = []
        for cid, doc, meta, dist in zip(result["ids"][0], result["documents"][0], result["metadatas"][0], result["distances"][0]):
            hits.append(Hit(chunk_id=cid, text=doc, score=max(0.0, 1.0 - float(dist)), metadata=dict(meta or {})))
        return hits

    def delete_document(self, doc_id):
        existing = self._col.get(where={"doc_id": doc_id}, include=[])
        ids = existing.get("ids", [])
        if ids:
            self._col.delete(ids=ids)
        return len(ids)

    def count(self):
        return self._col.count()

    def clear(self):
        self._client.delete_collection(self._collection_name)
        self._col = self._client.get_or_create_collection(
            self._collection_name, metadata={"hnsw:space": "cosine"}, embedding_function=None
        )


class LocalStore:
    """JSON + numpy fallback with brute-force cosine search."""

    backend = "local"

    def __init__(self, path: Path):
        self._path = path
        self._ids: List[str] = []
        self._texts: List[str] = []
        self._metas: List[Dict[str, Any]] = []
        self._vectors: Optional["np.ndarray"] = None
        self._load()

    def _load(self):
        if not self._path.exists():
            return
        try:
            data = json.loads(self._path.read_text("utf-8"))
            self._ids = data["ids"]
            self._texts = data["texts"]
            self._metas = data["metas"]
            self._vectors = np.asarray(data["vectors"], dtype=np.float32) if data["vectors"] else None
        except Exception as exc:
            logger.error("Could not load local vector store %s: %s", self._path, exc)

    def _save(self):
        payload = {
            "ids": self._ids,
            "texts": self._texts,
            "metas": self._metas,
            "vectors": self._vectors.tolist() if self._vectors is not None else [],
        }
        tmp = self._path.with_suffix(".tmp")
        tmp.write_text(json.dumps(payload), "utf-8")
        tmp.replace(self._path)

    def add(self, ids, texts, embeddings, metadatas):
        vectors = np.asarray(embeddings, dtype=np.float32)
        self._ids.extend(ids)
        self._texts.extend(texts)
        self._metas.extend(metadatas)
        self._vectors = vectors if self._vectors is None else np.vstack([self._vectors, vectors])
        self._save()

    def query(self, embedding, k, doc_ids=None):
        if self._vectors is None or not len(self._ids):
            return []
        q = np.asarray(embedding, dtype=np.float32)
        sims = self._vectors @ q / ((np.linalg.norm(self._vectors, axis=1) * np.linalg.norm(q)) + 1e-9)
        order = np.argsort(-sims)
        hits: List[Hit] = []
        for idx in order:
            meta = self._metas[idx]
            if doc_ids and meta.get("doc_id") not in doc_ids:
                continue
            hits.append(Hit(self._ids[idx], self._texts[idx], float(max(0.0, sims[idx])), dict(meta)))
            if len(hits) >= k:
                break
        return hits

    def delete_document(self, doc_id):
        keep = [i for i, m in enumerate(self._metas) if m.get("doc_id") != doc_id]
        removed = len(self._ids) - len(keep)
        if removed:
            self._ids = [self._ids[i] for i in keep]
            self._texts = [self._texts[i] for i in keep]
            self._metas = [self._metas[i] for i in keep]
            self._vectors = self._vectors[keep] if keep else None
            self._save()
        return removed

    def count(self):
        return len(self._ids)

    def clear(self):
        self._ids, self._texts, self._metas, self._vectors = [], [], [], None
        self._save()


# --------------------------------------------------------------------------- #
# Text extraction and chunking
# --------------------------------------------------------------------------- #


class UnsupportedDocumentError(ValueError):
    pass


def extract_text(filename: str, data: bytes) -> Tuple[str, Dict[str, Any]]:
    """Return (text, extra_metadata) for an uploaded file."""
    ext = Path(filename).suffix.lower()
    if ext not in SUPPORTED_EXTENSIONS:
        raise UnsupportedDocumentError(f"Unsupported file type '{ext}'. Supported: {', '.join(sorted(SUPPORTED_EXTENSIONS))}")
    if ext == ".pdf":
        try:
            from pypdf import PdfReader
        except ImportError as exc:
            raise UnsupportedDocumentError("PDF support requires the 'pypdf' package") from exc
        import io

        reader = PdfReader(io.BytesIO(data))
        pages = []
        for number, page in enumerate(reader.pages, start=1):
            try:
                text = page.extract_text() or ""
            except Exception as exc:  # corrupt page
                logger.debug("Failed to extract page %d of %s: %s", number, filename, exc)
                text = ""
            if text.strip():
                pages.append(f"\n\n[Page {number}]\n{text}")
        text = "".join(pages).strip()
        if not text:
            raise UnsupportedDocumentError("No extractable text found in the PDF (scanned image?).")
        return text, {"pages": len(reader.pages)}
    for encoding in ("utf-8", "utf-16", "latin-1"):
        try:
            return data.decode(encoding), {}
        except UnicodeDecodeError:
            continue
    raise UnsupportedDocumentError("Could not decode the file as text.")


_PAGE_RE = re.compile(r"\[Page (\d+)\]")


def chunk_text(text: str, chunk_chars: int, overlap_chars: int) -> List[Dict[str, Any]]:
    """
    Split on paragraph boundaries, packing paragraphs up to ``chunk_chars`` and
    carrying ``overlap_chars`` of trailing context into the next chunk. Long
    paragraphs are split on sentence boundaries. Tracks '[Page N]' markers.
    """
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    paragraphs = [p.strip() for p in re.split(r"\n\s*\n", text) if p.strip()]

    units: List[str] = []
    for para in paragraphs:
        if len(para) <= chunk_chars:
            units.append(para)
            continue
        sentences = re.split(r"(?<=[.!?])\s+", para)
        buf = ""
        for sentence in sentences:
            if len(buf) + len(sentence) + 1 > chunk_chars and buf:
                units.append(buf.strip())
                buf = ""
            if len(sentence) > chunk_chars:  # pathological: hard split
                for i in range(0, len(sentence), chunk_chars):
                    units.append(sentence[i : i + chunk_chars])
                continue
            buf = f"{buf} {sentence}"
        if buf.strip():
            units.append(buf.strip())

    chunks: List[Dict[str, Any]] = []
    current = ""
    page = None
    for unit in units:
        marker = _PAGE_RE.search(unit)
        if marker:
            page = int(marker.group(1))
        if current and len(current) + len(unit) + 2 > chunk_chars:
            chunks.append({"text": current.strip(), "page": page})
            tail = current[-overlap_chars:] if overlap_chars else ""
            current = f"{tail}\n\n{unit}" if tail else unit
        else:
            current = f"{current}\n\n{unit}" if current else unit
    if current.strip():
        chunks.append({"text": current.strip(), "page": page})
    for index, chunk in enumerate(chunks):
        chunk["index"] = index
        chunk["text"] = _PAGE_RE.sub("", chunk["text"]).strip()
    return [c for c in chunks if c["text"]]


# --------------------------------------------------------------------------- #
# Service
# --------------------------------------------------------------------------- #


@dataclass
class DocumentRecord:
    id: str
    title: str
    source: str  # filename or 'text'
    tags: List[str] = field(default_factory=list)
    chars: int = 0
    chunks: int = 0
    pages: Optional[int] = None
    created_at: str = field(default_factory=utc_now_iso)
    preview: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class KnowledgeService:
    def __init__(self, settings=None):
        self.settings = settings or get_settings()
        self.embedder: Optional[Embedder] = None
        self.store: Optional[VectorStore] = None
        self._documents: Dict[str, DocumentRecord] = {}
        self._lock = threading.Lock()
        self.is_initialized = False
        self.error: Optional[str] = None

    # ---- lifecycle ---------------------------------------------------- #

    @property
    def root(self) -> Path:
        return Path(self.settings.knowledge_dir)

    @property
    def _registry_path(self) -> Path:
        return self.root / "documents.json"

    async def initialize(self) -> None:
        import asyncio

        # Embedder construction may download a model; keep it off the event loop.
        await asyncio.to_thread(self._initialize_sync)

    def _initialize_sync(self) -> None:
        self.root.mkdir(parents=True, exist_ok=True)
        try:
            self.embedder = build_embedder(self.settings.knowledge_embedding)
            collection = f"course_material__{self.embedder.name}"
            if HAS_CHROMA:
                self.store = ChromaStore(self.root / "chroma", collection)
            else:
                logger.warning("chromadb not installed; using local numpy vector store")
                self.store = LocalStore(self.root / f"{collection}.json")
            self._load_registry()
            self.is_initialized = True
            logger.info(
                "Knowledge base ready (%s, %s, %d documents, %d chunks)",
                self.store.backend, self.embedder.name, len(self._documents), self.store.count(),
            )
        except Exception as exc:
            self.error = str(exc)
            logger.error("Knowledge base failed to initialise: %s", exc)

    async def cleanup(self) -> None:
        self.is_initialized = False

    def is_healthy(self) -> bool:
        return self.is_initialized

    def _load_registry(self) -> None:
        if not self._registry_path.exists():
            return
        try:
            raw = json.loads(self._registry_path.read_text("utf-8"))
            self._documents = {d["id"]: DocumentRecord(**d) for d in raw}
        except Exception as exc:
            logger.error("Could not read %s: %s", self._registry_path, exc)

    def _save_registry(self) -> None:
        tmp = self._registry_path.with_suffix(".tmp")
        tmp.write_text(json.dumps([d.to_dict() for d in self._documents.values()], indent=1), "utf-8")
        tmp.replace(self._registry_path)

    def _require_ready(self) -> None:
        if not self.is_initialized or self.store is None or self.embedder is None:
            raise RuntimeError(self.error or "Knowledge base is not initialised")

    # ---- documents ---------------------------------------------------- #

    def status(self) -> Dict[str, Any]:
        return {
            "available": self.is_initialized,
            "error": self.error,
            "backend": self.store.backend if self.store else None,
            "embedding": self.embedder.name if self.embedder else None,
            "documents": len(self._documents),
            "chunks": self.store.count() if self.store else 0,
            "supported_extensions": sorted(SUPPORTED_EXTENSIONS),
            "max_upload_bytes": self.settings.knowledge_max_upload_bytes,
        }

    def list_documents(self) -> List[Dict[str, Any]]:
        return [d.to_dict() for d in sorted(self._documents.values(), key=lambda d: d.created_at, reverse=True)]

    def get_document(self, doc_id: str) -> Optional[Dict[str, Any]]:
        record = self._documents.get(doc_id)
        return record.to_dict() if record else None

    def add_text(self, title: str, text: str, *, source: str = "text", tags: Optional[List[str]] = None, extra: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        self._require_ready()
        title = (title or "").strip() or "Untitled"
        text = (text or "").strip()
        if not text:
            raise ValueError("The document is empty.")
        if len(text) > self.settings.knowledge_max_document_chars:
            raise ValueError(f"Document is too large ({len(text):,} characters; limit {self.settings.knowledge_max_document_chars:,}).")

        chunks = chunk_text(text, self.settings.knowledge_chunk_chars, self.settings.knowledge_chunk_overlap_chars)
        if not chunks:
            raise ValueError("No usable text found in the document.")

        doc_id = uuid.uuid4().hex[:12]
        tags = [t.strip() for t in (tags or []) if t.strip()]
        ids = [f"{doc_id}:{c['index']}" for c in chunks]
        texts = [c["text"] for c in chunks]
        metadatas = [
            {
                "doc_id": doc_id,
                "title": title,
                "source": source,
                "chunk_index": c["index"],
                "page": c["page"] if c["page"] is not None else -1,
                "tags": ",".join(tags),
            }
            for c in chunks
        ]
        embeddings = self.embedder.embed(texts)

        with self._lock:
            self.store.add(ids, texts, embeddings, metadatas)
            record = DocumentRecord(
                id=doc_id,
                title=title,
                source=source,
                tags=tags,
                chars=len(text),
                chunks=len(chunks),
                pages=(extra or {}).get("pages"),
                preview=re.sub(r"\s+", " ", text[:240]),
            )
            self._documents[doc_id] = record
            self._save_registry()
        logger.info("Indexed '%s' (%d chunks, %d chars)", title, len(chunks), len(text))
        return record.to_dict()

    def add_file(self, filename: str, data: bytes, *, title: Optional[str] = None, tags: Optional[List[str]] = None) -> Dict[str, Any]:
        if len(data) > self.settings.knowledge_max_upload_bytes:
            raise ValueError(f"File is larger than {self.settings.knowledge_max_upload_bytes // (1024 * 1024)} MB.")
        text, extra = extract_text(filename, data)
        return self.add_text(title or Path(filename).stem, text, source=Path(filename).name, tags=tags, extra=extra)

    def delete_document(self, doc_id: str) -> bool:
        self._require_ready()
        with self._lock:
            if doc_id not in self._documents:
                return False
            self.store.delete_document(doc_id)
            del self._documents[doc_id]
            self._save_registry()
        return True

    def clear(self) -> None:
        self._require_ready()
        with self._lock:
            self.store.clear()
            self._documents.clear()
            self._save_registry()

    # ---- retrieval ---------------------------------------------------- #

    def search(self, query: str, k: int = 5, doc_ids: Optional[List[str]] = None, min_score: float = 0.0) -> List[Dict[str, Any]]:
        self._require_ready()
        query = (query or "").strip()
        if not query or not self._documents:
            return []
        [embedding] = self.embedder.embed([query])
        hits = self.store.query(embedding, k, doc_ids)
        results = []
        for hit in hits:
            if hit.score < min_score:
                continue
            meta = hit.metadata
            page = meta.get("page")
            results.append(
                {
                    "chunk_id": hit.chunk_id,
                    "doc_id": meta.get("doc_id"),
                    "title": meta.get("title"),
                    "source": meta.get("source"),
                    "page": None if page in (None, -1) else int(page),
                    "chunk_index": meta.get("chunk_index"),
                    "score": round(hit.score, 4),
                    "text": hit.text,
                }
            )
        return results

    def has_documents(self) -> bool:
        return bool(self._documents)
