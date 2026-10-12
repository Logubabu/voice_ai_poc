import asyncio
import hashlib
import os
import uuid
from typing import List, Optional, Dict, Any

from knowledge_base.models import KnowledgeBaseModel, DocumentModel
from knowledge_base.schemas import (
    KnowledgeBaseCreate,
    KnowledgeBaseUpdate,
    KnowledgeBaseResponse,
    DocumentResponse,
    KnowledgeSearchResponse,
)
from knowledge_base.repository import KnowledgeBaseRepository
from knowledge_base.vector_store import QdrantVectorStore, VectorStore
from knowledge_base.embeddings import EmbeddingProviderFactory, EmbeddingProvider
from knowledge_base.ingestion import DocumentIngestionPipeline
from knowledge_base.retrieval import KnowledgeRetrievalEngine
from knowledge_base.exceptions import KnowledgeBaseNotFoundError, DocumentNotFoundError
from app.config import config
from app.utils.logging import logger


class KnowledgeBaseService:
    """Unified high-level facade for Knowledge Base CRUD, document uploading, async ingestion, and RAG search."""

    def __init__(
        self,
        storage_dir: str = "data/documents",
        db_path: str = "data/knowledge_base.db",
    ):
        self.storage_dir = storage_dir
        os.makedirs(storage_dir, exist_ok=True)

        self.repository = KnowledgeBaseRepository(db_path=db_path)

        # Vector store initialization
        qdrant_url = getattr(config, "QDRANT_URL", "http://localhost:6333")
        qdrant_api_key = getattr(config, "QDRANT_API_KEY", "")
        self.vector_store: VectorStore = QdrantVectorStore(url=qdrant_url, api_key=qdrant_api_key)

        # Embedding provider initialization
        emb_provider_type = getattr(config, "EMBEDDING_PROVIDER", "auto")
        emb_model = getattr(config, "EMBEDDING_MODEL", "all-MiniLM-L6-v2")
        self.embedding_provider: EmbeddingProvider = EmbeddingProviderFactory.create_provider(
            provider_type=emb_provider_type, model_name=emb_model
        )

        # Ingestion pipeline
        max_concurrency = getattr(config, "INGESTION_MAX_CONCURRENCY", 2)
        self.ingestion_pipeline = DocumentIngestionPipeline(
            repository=self.repository,
            vector_store=self.vector_store,
            embedding_provider=self.embedding_provider,
            max_concurrency=max_concurrency,
        )

        # Retrieval engine
        min_score = getattr(config, "KB_MIN_SCORE", 0.70)
        max_context = getattr(config, "KB_MAX_CONTEXT_TOKENS", 2500)
        cache_enabled = getattr(config, "KB_CACHE_ENABLED", False)

        self.retrieval_engine = KnowledgeRetrievalEngine(
            vector_store=self.vector_store,
            embedding_provider=self.embedding_provider,
            min_score=min_score,
            max_context_tokens=max_context,
            cache_enabled=cache_enabled,
        )

    # --- Knowledge Base Operations ---

    async def create_kb(self, req: KnowledgeBaseCreate) -> KnowledgeBaseResponse:
        kb_model = KnowledgeBaseModel(tenant_id=req.tenant_id, name=req.name, description=req.description)
        created = await self.repository.create_kb(kb_model)
        return KnowledgeBaseResponse(
            id=created.id,
            tenant_id=created.tenant_id,
            name=created.name,
            description=created.description,
            status=created.status,
            document_count=0,
            total_chunks=0,
            created_at=created.created_at,
            updated_at=created.updated_at,
        )

    async def get_kb(self, kb_id: str, tenant_id: str) -> KnowledgeBaseResponse:
        kb = await self.repository.get_kb(kb_id, tenant_id=tenant_id)
        if not kb:
            raise KnowledgeBaseNotFoundError(f"Knowledge Base '{kb_id}' not found for tenant '{tenant_id}'.")
        docs = await self.repository.list_documents(kb_id=kb_id, tenant_id=tenant_id)
        total_chunks = sum(d.chunk_count for d in docs)
        return KnowledgeBaseResponse(
            id=kb.id,
            tenant_id=kb.tenant_id,
            name=kb.name,
            description=kb.description,
            status=kb.status,
            document_count=len(docs),
            total_chunks=total_chunks,
            created_at=kb.created_at,
            updated_at=kb.updated_at,
        )

    async def list_kbs(self, tenant_id: str) -> List[KnowledgeBaseResponse]:
        kbs = await self.repository.list_kbs(tenant_id=tenant_id)
        responses = []
        for kb in kbs:
            docs = await self.repository.list_documents(kb_id=kb.id, tenant_id=tenant_id)
            total_chunks = sum(d.chunk_count for d in docs)
            responses.append(
                KnowledgeBaseResponse(
                    id=kb.id,
                    tenant_id=kb.tenant_id,
                    name=kb.name,
                    description=kb.description,
                    status=kb.status,
                    document_count=len(docs),
                    total_chunks=total_chunks,
                    created_at=kb.created_at,
                    updated_at=kb.updated_at,
                )
            )
        return responses

    async def update_kb(self, kb_id: str, tenant_id: str, req: KnowledgeBaseUpdate) -> KnowledgeBaseResponse:
        kb = await self.repository.get_kb(kb_id, tenant_id=tenant_id)
        if not kb:
            raise KnowledgeBaseNotFoundError(f"Knowledge Base '{kb_id}' not found for tenant '{tenant_id}'.")
        if req.name is not None:
            kb.name = req.name
        if req.description is not None:
            kb.description = req.description
        updated = await self.repository.update_kb(kb)
        docs = await self.repository.list_documents(kb_id=kb_id, tenant_id=tenant_id)
        return KnowledgeBaseResponse(
            id=updated.id,
            tenant_id=updated.tenant_id,
            name=updated.name,
            description=updated.description,
            status=updated.status,
            document_count=len(docs),
            total_chunks=sum(d.chunk_count for d in docs),
            created_at=updated.created_at,
            updated_at=updated.updated_at,
        )

    async def delete_kb(self, kb_id: str, tenant_id: str) -> bool:
        await self.vector_store.delete_tenant(collection_name="sharyx_kb_vectors", tenant_id=tenant_id)
        return await self.repository.delete_kb(kb_id=kb_id, tenant_id=tenant_id)

    # --- Document Upload & Ingestion Operations ---

    async def upload_document(
        self,
        kb_id: str,
        tenant_id: str,
        filename: str,
        file_content: bytes,
        mime_type: str = "application/octet-stream",
    ) -> DocumentResponse:
        kb = await self.repository.get_kb(kb_id, tenant_id=tenant_id)
        if not kb:
            raise KnowledgeBaseNotFoundError(f"Knowledge Base '{kb_id}' not found for tenant '{tenant_id}'.")

        # Calculate SHA-256 Checksum for duplicate detection
        checksum = hashlib.sha256(file_content).hexdigest()

        # Duplicate Detection
        existing_doc = await self.repository.find_duplicate_document(kb_id=kb_id, tenant_id=tenant_id, checksum=checksum)
        if existing_doc and existing_doc.status == "indexed":
            logger.info(f"[INGESTION][DUPLICATE] Identical document '{filename}' (checksum: {checksum[:8]}) already indexed. Reusing doc id: {existing_doc.id}")
            return DocumentResponse.model_validate(existing_doc.to_dict())

        # Save document binary file on disk
        doc_id = str(uuid.uuid4())
        safe_filename = f"{doc_id}_{os.path.basename(filename)}"
        storage_path = os.path.join(self.storage_dir, safe_filename)

        with open(storage_path, "wb") as f:
            f.write(file_content)

        # Create Document Metadata Model
        doc_model = DocumentModel(
            id=doc_id,
            knowledge_base_id=kb_id,
            tenant_id=tenant_id,
            filename=safe_filename,
            original_filename=os.path.basename(filename),
            mime_type=mime_type,
            size_bytes=len(file_content),
            checksum=checksum,
            storage_path=storage_path,
            status="uploaded",
        )
        created_doc = await self.repository.create_document(doc_model)

        # Launch background ingestion worker task (voice API never waits for ingestion)
        asyncio.create_task(self.ingestion_pipeline.ingest_document(document_id=doc_id, tenant_id=tenant_id))

        return DocumentResponse.model_validate(created_doc.to_dict())

    async def list_documents(self, kb_id: str, tenant_id: str) -> List[DocumentResponse]:
        docs = await self.repository.list_documents(kb_id=kb_id, tenant_id=tenant_id)
        return [DocumentResponse.model_validate(d.to_dict()) for d in docs]

    async def get_document(self, doc_id: str, tenant_id: str) -> DocumentResponse:
        doc = await self.repository.get_document(doc_id, tenant_id=tenant_id)
        if not doc:
            raise DocumentNotFoundError(f"Document '{doc_id}' not found for tenant '{tenant_id}'.")
        return DocumentResponse.model_validate(doc.to_dict())

    async def delete_document(self, doc_id: str, tenant_id: str) -> bool:
        doc = await self.repository.get_document(doc_id, tenant_id=tenant_id)
        if not doc:
            return False
        # Remove vectors from VectorStore
        await self.vector_store.delete_document(
            collection_name="sharyx_kb_vectors", tenant_id=tenant_id, document_id=doc_id
        )
        # Remove raw storage file
        if os.path.exists(doc.storage_path):
            try:
                os.remove(doc.storage_path)
            except Exception:
                pass
        return await self.repository.delete_document(doc_id=doc_id, tenant_id=tenant_id)

    async def reindex_document(self, doc_id: str, tenant_id: str) -> DocumentResponse:
        doc = await self.repository.get_document(doc_id, tenant_id=tenant_id)
        if not doc:
            raise DocumentNotFoundError(f"Document '{doc_id}' not found.")
        # Delete old vectors
        await self.vector_store.delete_document(
            collection_name="sharyx_kb_vectors", tenant_id=tenant_id, document_id=doc_id
        )
        # Trigger re-ingestion
        asyncio.create_task(self.ingestion_pipeline.ingest_document(document_id=doc_id, tenant_id=tenant_id))
        return DocumentResponse.model_validate(doc.to_dict())

    # --- Search / Retrieval Operations ---

    async def search(
        self,
        query: str,
        tenant_id: str,
        knowledge_base_id: Optional[str] = None,
        top_k: int = 5,
        category: Optional[str] = None,
    ) -> KnowledgeSearchResponse:
        return await self.retrieval_engine.search(
            query=query,
            tenant_id=tenant_id,
            knowledge_base_id=knowledge_base_id,
            top_k=top_k,
            category=category,
        )

    async def health_check(self) -> Dict[str, Any]:
        vs_healthy = await self.vector_store.health_check()
        return {
            "status": "ok" if vs_healthy else "degraded",
            "vector_store": "healthy" if vs_healthy else "unhealthy",
            "embedding_provider": self.embedding_provider.__class__.__name__,
            "vector_dimension": self.embedding_provider.vector_dimension,
        }


kb_service = KnowledgeBaseService()
