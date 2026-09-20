"""
Course-material knowledge base API (Chroma-backed embedding index).
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from pydantic import BaseModel, Field

from api.dependencies import get_knowledge_service
from services.knowledge_service import KnowledgeService, UnsupportedDocumentError

logger = logging.getLogger(__name__)
router = APIRouter()


class TextDocumentRequest(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    text: str = Field(min_length=1)
    tags: List[str] = Field(default_factory=list, max_length=20)


class SearchRequest(BaseModel):
    query: str = Field(min_length=1, max_length=2000)
    k: int = Field(default=5, ge=1, le=25)
    doc_ids: Optional[List[str]] = None
    min_score: float = Field(default=0.0, ge=0.0, le=1.0)


def _ready(service: KnowledgeService) -> None:
    if not service.is_initialized:
        raise HTTPException(status_code=503, detail=service.error or "Knowledge base is not available")


def _parse_tags(raw: Optional[str]) -> List[str]:
    return [t.strip() for t in (raw or "").split(",") if t.strip()]


@router.get("/status")
async def knowledge_status(service: KnowledgeService = Depends(get_knowledge_service)) -> Dict[str, Any]:
    return service.status()


@router.get("/documents")
async def list_documents(service: KnowledgeService = Depends(get_knowledge_service)) -> Dict[str, Any]:
    _ready(service)
    docs = service.list_documents()
    return {"documents": docs, "total": len(docs)}


@router.post("/documents/text", status_code=201)
async def add_text_document(request: TextDocumentRequest, service: KnowledgeService = Depends(get_knowledge_service)) -> Dict[str, Any]:
    _ready(service)
    try:
        return await asyncio.to_thread(service.add_text, request.title, request.text, tags=request.tags)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.post("/documents/upload", status_code=201)
async def upload_document(
    file: UploadFile = File(...),
    title: Optional[str] = Form(None),
    tags: Optional[str] = Form(None),
    service: KnowledgeService = Depends(get_knowledge_service),
) -> Dict[str, Any]:
    _ready(service)
    data = await file.read(service.settings.knowledge_max_upload_bytes + 1)
    if len(data) > service.settings.knowledge_max_upload_bytes:
        raise HTTPException(status_code=413, detail="File exceeds the upload size limit")
    try:
        return await asyncio.to_thread(service.add_file, file.filename or "upload.txt", data, title=title, tags=_parse_tags(tags))
    except UnsupportedDocumentError as exc:
        raise HTTPException(status_code=415, detail=str(exc))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.get("/documents/{doc_id}")
async def get_document(doc_id: str, service: KnowledgeService = Depends(get_knowledge_service)) -> Dict[str, Any]:
    _ready(service)
    doc = service.get_document(doc_id)
    if doc is None:
        raise HTTPException(status_code=404, detail="Document not found")
    return doc


@router.delete("/documents/{doc_id}")
async def delete_document(doc_id: str, service: KnowledgeService = Depends(get_knowledge_service)) -> Dict[str, Any]:
    _ready(service)
    if not await asyncio.to_thread(service.delete_document, doc_id):
        raise HTTPException(status_code=404, detail="Document not found")
    return {"deleted": doc_id}


@router.delete("/documents")
async def clear_documents(service: KnowledgeService = Depends(get_knowledge_service)) -> Dict[str, Any]:
    _ready(service)
    await asyncio.to_thread(service.clear)
    return {"cleared": True}


@router.post("/search")
async def search(request: SearchRequest, service: KnowledgeService = Depends(get_knowledge_service)) -> Dict[str, Any]:
    _ready(service)
    results = await asyncio.to_thread(service.search, request.query, request.k, request.doc_ids, request.min_score)
    return {"query": request.query, "results": results, "total": len(results)}
