import asyncio
import math
from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional

from knowledge_base.exceptions import VectorStoreError
from app.utils.logging import logger


class VectorStore(ABC):
    """Abstract VectorStore interface for vector database abstraction."""

    @abstractmethod
    async def upsert_chunks(self, collection_name: str, vectors: List[List[float]], payloads: List[Dict[str, Any]], ids: List[str]) -> bool:
        """Upserts embedded vectors and mandatory metadata payloads."""
        pass

    @abstractmethod
    async def search(
        self,
        collection_name: str,
        query_vector: List[float],
        tenant_id: str,
        kb_id: Optional[str] = None,
        top_k: int = 5,
        score_threshold: float = 0.0,
        filters: Optional[Dict[str, Any]] = None,
    ) -> List[Dict[str, Any]]:
        """Performs vector similarity search with MANDATORY tenant_id metadata filtering."""
        pass

    @abstractmethod
    async def delete_document(self, collection_name: str, tenant_id: str, document_id: str) -> bool:
        """Deletes all vector chunks associated with a document under tenant_id."""
        pass

    @abstractmethod
    async def delete_tenant(self, collection_name: str, tenant_id: str) -> bool:
        """Deletes all vector chunks associated with a tenant_id."""
        pass

    @abstractmethod
    async def health_check(self) -> bool:
        """Checks health and connectivity of the vector database."""
        pass


class InMemoryVectorStore(VectorStore):
    """High-performance thread-safe In-Memory fallback vector store with exact cosine similarity and strict tenant filtering."""

    def __init__(self):
        self._store: Dict[str, List[Dict[str, Any]]] = {}
        self._lock = asyncio.Lock()

    def _cosine_similarity(self, v1: List[float], v2: List[float]) -> float:
        if not v1 or not v2 or len(v1) != len(v2):
            return 0.0
        dot = sum(a * b for a, b in zip(v1, v2))
        norm1 = math.sqrt(sum(a * a for a in v1))
        norm2 = math.sqrt(sum(b * b for b in v2))
        if norm1 == 0 or norm2 == 0:
            return 0.0
        return dot / (norm1 * norm2)

    async def upsert_chunks(self, collection_name: str, vectors: List[List[float]], payloads: List[Dict[str, Any]], ids: List[str]) -> bool:
        async with self._lock:
            if collection_name not in self._store:
                self._store[collection_name] = []

            for vec, payload, cid in zip(vectors, payloads, ids):
                # Verify mandatory metadata fields exist
                if "tenant_id" not in payload:
                    raise VectorStoreError("CRITICAL: Vector payload missing mandatory field 'tenant_id'!")

                # Delete old vector with same chunk_id if re-upserting
                self._store[collection_name] = [item for item in self._store[collection_name] if item["id"] != cid]

                self._store[collection_name].append({
                    "id": cid,
                    "vector": vec,
                    "payload": payload,
                })
            return True

    async def search(
        self,
        collection_name: str,
        query_vector: List[float],
        tenant_id: str,
        kb_id: Optional[str] = None,
        top_k: int = 5,
        score_threshold: float = 0.0,
        filters: Optional[Dict[str, Any]] = None,
    ) -> List[Dict[str, Any]]:
        # MANDATORY TENANT CHECK: tenant_id must be provided
        if not tenant_id:
            raise VectorStoreError("MANDATORY TENANT ISOLATION: Search request rejected because tenant_id was not specified.")

        async with self._lock:
            items = self._store.get(collection_name, [])
            results = []

            for item in items:
                payload = item["payload"]
                # 1. STRICT MANDATORY TENANT ISOLATION FILTER
                if payload.get("tenant_id") != tenant_id:
                    continue

                # 2. KB ID Filter if provided
                if kb_id and payload.get("knowledge_base_id") != kb_id:
                    continue

                # 3. Additional optional metadata filters
                if filters:
                    match = True
                    for fk, fval in filters.items():
                        if payload.get(fk) != fval:
                            match = False
                            break
                    if not match:
                        continue

                score = self._cosine_similarity(query_vector, item["vector"])
                if score >= score_threshold:
                    results.append({
                        "id": item["id"],
                        "score": round(float(score), 4),
                        "payload": payload,
                    })

            # Sort by descending cosine similarity score
            results.sort(key=lambda x: x["score"], reverse=True)
            return results[:top_k]

    async def delete_document(self, collection_name: str, tenant_id: str, document_id: str) -> bool:
        async with self._lock:
            if collection_name in self._store:
                self._store[collection_name] = [
                    item for item in self._store[collection_name]
                    if not (item["payload"].get("tenant_id") == tenant_id and item["payload"].get("document_id") == document_id)
                ]
            return True

    async def delete_tenant(self, collection_name: str, tenant_id: str) -> bool:
        async with self._lock:
            if collection_name in self._store:
                self._store[collection_name] = [
                    item for item in self._store[collection_name]
                    if item["payload"].get("tenant_id") != tenant_id
                ]
            return True

    async def health_check(self) -> bool:
        return True


class QdrantVectorStore(VectorStore):
    """Production Qdrant Vector Store with automatic fallback and strict tenant isolation metadata filtering."""

    def __init__(self, url: str = "http://localhost:6333", api_key: Optional[str] = None):
        self.url = url
        self.api_key = api_key
        self.fallback = InMemoryVectorStore()
        self._client = None
        self._qdrant_available = False
        self._init_qdrant()

    def _init_qdrant(self):
        try:
            from qdrant_client import QdrantClient
            key = self.api_key if self.api_key else None
            self._client = QdrantClient(url=self.url, api_key=key, timeout=5.0, check_compatibility=False)
            # Ping health
            self._client.get_collections()
            self._qdrant_available = True
            logger.info(f"[VECTOR-STORE] Connected to Qdrant at {self.url}")
        except Exception as e:
            logger.warning(f"[VECTOR-STORE] Qdrant unavailable at {self.url} ({e}). Using In-Memory Vector Store fallback.")
            self._qdrant_available = False

    async def upsert_chunks(self, collection_name: str, vectors: List[List[float]], payloads: List[Dict[str, Any]], ids: List[str]) -> bool:
        # Always maintain fallback in memory as well
        await self.fallback.upsert_chunks(collection_name, vectors, payloads, ids)

        if not self._qdrant_available:
            return True

        try:
            from qdrant_client.models import VectorParams, Distance, PointStruct
            def _op():
                # Ensure collection exists
                try:
                    self._client.get_collection(collection_name)
                except Exception:
                    dim = len(vectors[0]) if vectors else 384
                    self._client.create_collection(
                        collection_name=collection_name,
                        vectors_config=VectorParams(size=dim, distance=Distance.COSINE),
                    )

                points = [
                    PointStruct(id=cid, vector=vec, payload=pload)
                    for cid, vec, pload in zip(ids, vectors, payloads)
                ]
                self._client.upsert(collection_name=collection_name, points=points)
            await asyncio.to_thread(_op)
            return True
        except Exception as e:
            logger.error(f"[VECTOR-STORE][ERROR] Qdrant upsert failed ({e}). Fallback in-memory vectors will be used.")
            return True

    async def search(
        self,
        collection_name: str,
        query_vector: List[float],
        tenant_id: str,
        kb_id: Optional[str] = None,
        top_k: int = 5,
        score_threshold: float = 0.0,
        filters: Optional[Dict[str, Any]] = None,
    ) -> List[Dict[str, Any]]:
        # MANDATORY TENANT CHECK: tenant_id must be provided
        if not tenant_id:
            raise VectorStoreError("MANDATORY TENANT ISOLATION: Search request rejected because tenant_id was not specified.")

        if not self._qdrant_available:
            return await self.fallback.search(
                collection_name=collection_name,
                query_vector=query_vector,
                tenant_id=tenant_id,
                kb_id=kb_id,
                top_k=top_k,
                score_threshold=score_threshold,
                filters=filters,
            )

        try:
            from qdrant_client.models import Filter, FieldCondition, MatchValue
            def _op():
                must_conditions = [
                    FieldCondition(key="tenant_id", match=MatchValue(value=tenant_id))
                ]
                if kb_id:
                    must_conditions.append(FieldCondition(key="knowledge_base_id", match=MatchValue(value=kb_id)))

                if filters:
                    for fk, fv in filters.items():
                        must_conditions.append(FieldCondition(key=fk, match=MatchValue(value=fv)))

                qdrant_filter = Filter(must=must_conditions)
                hits = self._client.search(
                    collection_name=collection_name,
                    query_vector=query_vector,
                    query_filter=qdrant_filter,
                    limit=top_k,
                    score_threshold=score_threshold,
                )
                return [
                    {
                        "id": str(hit.id),
                        "score": round(float(hit.score), 4),
                        "payload": hit.payload or {},
                    }
                    for hit in hits
                ]
            return await asyncio.to_thread(_op)
        except Exception as e:
            logger.warning(f"[VECTOR-STORE] Qdrant search failed ({e}). Falling back to In-Memory vector search.")
            return await self.fallback.search(
                collection_name=collection_name,
                query_vector=query_vector,
                tenant_id=tenant_id,
                kb_id=kb_id,
                top_k=top_k,
                score_threshold=score_threshold,
                filters=filters,
            )

    async def delete_document(self, collection_name: str, tenant_id: str, document_id: str) -> bool:
        await self.fallback.delete_document(collection_name, tenant_id, document_id)
        if not self._qdrant_available:
            return True
        try:
            from qdrant_client.models import Filter, FieldCondition, MatchValue
            def _op():
                qdrant_filter = Filter(must=[
                    FieldCondition(key="tenant_id", match=MatchValue(value=tenant_id)),
                    FieldCondition(key="document_id", match=MatchValue(value=document_id)),
                ])
                self._client.delete(collection_name=collection_name, points_selector=qdrant_filter)
            await asyncio.to_thread(_op)
            return True
        except Exception as e:
            logger.warning(f"[VECTOR-STORE] Qdrant delete_document failed ({e}).")
            return True

    async def delete_tenant(self, collection_name: str, tenant_id: str) -> bool:
        await self.fallback.delete_tenant(collection_name, tenant_id)
        if not self._qdrant_available:
            return True
        try:
            from qdrant_client.models import Filter, FieldCondition, MatchValue
            def _op():
                qdrant_filter = Filter(must=[
                    FieldCondition(key="tenant_id", match=MatchValue(value=tenant_id))
                ])
                self._client.delete(collection_name=collection_name, points_selector=qdrant_filter)
            await asyncio.to_thread(_op)
            return True
        except Exception as e:
            logger.warning(f"[VECTOR-STORE] Qdrant delete_tenant failed ({e}).")
            return True

    async def health_check(self) -> bool:
        if self._qdrant_available:
            try:
                def _op():
                    self._client.get_collections()
                await asyncio.to_thread(_op)
                return True
            except Exception:
                return False
        return await self.fallback.health_check()
