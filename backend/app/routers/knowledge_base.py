from typing import List, Optional
from fastapi import APIRouter, HTTPException, UploadFile, File, Form, Header, Query

from knowledge_base.service import kb_service
from knowledge_base.schemas import (
    KnowledgeBaseCreate,
    KnowledgeBaseUpdate,
    KnowledgeBaseResponse,
    DocumentResponse,
    KnowledgeSearchRequest,
    KnowledgeSearchResponse,
)
from knowledge_base.exceptions import KnowledgeBaseNotFoundError, DocumentNotFoundError
from knowledge_base.metrics import kb_metrics
from app.utils.logging import logger

router = APIRouter(prefix="/api/v1/knowledge-bases", tags=["Knowledge Base"])


def _get_tenant_id(x_tenant_id: Optional[str] = Header(None), tenant_id: Optional[str] = Query(None)) -> str:
    tid = x_tenant_id or tenant_id or "default_tenant"
    return tid.strip()


@router.post("", response_model=KnowledgeBaseResponse, summary="Create a new Knowledge Base")
async def create_knowledge_base(
    req: KnowledgeBaseCreate,
    x_tenant_id: Optional[str] = Header(None),
):
    tid = x_tenant_id or req.tenant_id or "default_tenant"
    req.tenant_id = tid
    return await kb_service.create_kb(req)


@router.get("", response_model=List[KnowledgeBaseResponse], summary="List Knowledge Bases for tenant")
async def list_knowledge_bases(
    x_tenant_id: Optional[str] = Header(None),
    tenant_id: Optional[str] = Query(None),
):
    tid = _get_tenant_id(x_tenant_id, tenant_id)
    return await kb_service.list_kbs(tenant_id=tid)


@router.get("/health", summary="Knowledge Base health check")
async def kb_health():
    health_status = await kb_service.health_check()
    health_status["metrics"] = kb_metrics.get_summary()
    return health_status


@router.get("/{kb_id}", response_model=KnowledgeBaseResponse, summary="Get Knowledge Base details")
async def get_knowledge_base(
    kb_id: str,
    x_tenant_id: Optional[str] = Header(None),
    tenant_id: Optional[str] = Query(None),
):
    tid = _get_tenant_id(x_tenant_id, tenant_id)
    try:
        return await kb_service.get_kb(kb_id=kb_id, tenant_id=tid)
    except KnowledgeBaseNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.patch("/{kb_id}", response_model=KnowledgeBaseResponse, summary="Update Knowledge Base metadata")
async def update_knowledge_base(
    kb_id: str,
    req: KnowledgeBaseUpdate,
    x_tenant_id: Optional[str] = Header(None),
    tenant_id: Optional[str] = Query(None),
):
    tid = _get_tenant_id(x_tenant_id, tenant_id)
    try:
        return await kb_service.update_kb(kb_id=kb_id, tenant_id=tid, req=req)
    except KnowledgeBaseNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.delete("/{kb_id}", summary="Delete Knowledge Base and associated vectors")
async def delete_knowledge_base(
    kb_id: str,
    x_tenant_id: Optional[str] = Header(None),
    tenant_id: Optional[str] = Query(None),
):
    tid = _get_tenant_id(x_tenant_id, tenant_id)
    success = await kb_service.delete_kb(kb_id=kb_id, tenant_id=tid)
    if not success:
        raise HTTPException(status_code=404, detail=f"Knowledge base '{kb_id}' not found.")
    return {"status": "success", "message": f"Knowledge Base '{kb_id}' deleted."}


@router.post("/{kb_id}/documents", response_model=DocumentResponse, summary="Upload document for ingestion")
async def upload_document(
    kb_id: str,
    file: UploadFile = File(...),
    x_tenant_id: Optional[str] = Header(None),
    tenant_id: Optional[str] = Form(None),
):
    tid = x_tenant_id or tenant_id or "default_tenant"
    try:
        content = await file.read()
        return await kb_service.upload_document(
            kb_id=kb_id,
            tenant_id=tid,
            filename=file.filename or "document.txt",
            file_content=content,
            mime_type=file.content_type or "application/octet-stream",
        )
    except KnowledgeBaseNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.exception(f"[API] Upload document failed: {e}")
        raise HTTPException(status_code=400, detail=f"Document upload failed: {str(e)}")


@router.get("/{kb_id}/documents", response_model=List[DocumentResponse], summary="List documents in Knowledge Base")
async def list_documents(
    kb_id: str,
    x_tenant_id: Optional[str] = Header(None),
    tenant_id: Optional[str] = Query(None),
):
    tid = _get_tenant_id(x_tenant_id, tenant_id)
    return await kb_service.list_documents(kb_id=kb_id, tenant_id=tid)


@router.get("/{kb_id}/documents/{document_id}", response_model=DocumentResponse, summary="Get document status")
async def get_document(
    kb_id: str,
    document_id: str,
    x_tenant_id: Optional[str] = Header(None),
    tenant_id: Optional[str] = Query(None),
):
    tid = _get_tenant_id(x_tenant_id, tenant_id)
    try:
        return await kb_service.get_document(doc_id=document_id, tenant_id=tid)
    except DocumentNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.delete("/{kb_id}/documents/{document_id}", summary="Delete document")
async def delete_document(
    kb_id: str,
    document_id: str,
    x_tenant_id: Optional[str] = Header(None),
    tenant_id: Optional[str] = Query(None),
):
    tid = _get_tenant_id(x_tenant_id, tenant_id)
    success = await kb_service.delete_document(doc_id=document_id, tenant_id=tid)
    if not success:
        raise HTTPException(status_code=404, detail=f"Document '{document_id}' not found.")
    return {"status": "success", "message": f"Document '{document_id}' deleted."}


@router.post("/{kb_id}/documents/{document_id}/reindex", response_model=DocumentResponse, summary="Reindex document")
async def reindex_document(
    kb_id: str,
    document_id: str,
    x_tenant_id: Optional[str] = Header(None),
    tenant_id: Optional[str] = Query(None),
):
    tid = _get_tenant_id(x_tenant_id, tenant_id)
    try:
        return await kb_service.reindex_document(doc_id=document_id, tenant_id=tid)
    except DocumentNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post("/{kb_id}/search", response_model=KnowledgeSearchResponse, summary="Non-voice testing search endpoint")
async def test_search_knowledge_base(
    kb_id: str,
    req: KnowledgeSearchRequest,
    x_tenant_id: Optional[str] = Header(None),
):
    tid = x_tenant_id or req.tenant_id or "default_tenant"
    return await kb_service.search(
        query=req.query,
        tenant_id=tid,
        knowledge_base_id=kb_id,
        top_k=req.top_k,
        category=req.category,
    )


@router.get("/debug/search", summary="Diagnostic search endpoint to verify indexed document retrieval")
async def debug_search_knowledge_base(
    q: str = Query(..., description="Search query string"),
    tenant_id: Optional[str] = Query("default_tenant"),
    kb_id: Optional[str] = Query(None),
    x_tenant_id: Optional[str] = Header(None),
):
    tid = x_tenant_id or tenant_id or "default_tenant"
    docs = await kb_service.list_documents(kb_id=kb_id or "default_kb", tenant_id=tid) if kb_id else []
    search_res = await kb_service.search(
        query=q,
        tenant_id=tid,
        knowledge_base_id=kb_id,
        top_k=5,
    )
    return {
        "query": q,
        "tenant_id": tid,
        "knowledge_base_id": kb_id,
        "documents_found": len(docs),
        "found": search_res.found,
        "confidence": search_res.confidence,
        "results_count": len(search_res.results),
        "results": [r.model_dump() for r in search_res.results],
    }
