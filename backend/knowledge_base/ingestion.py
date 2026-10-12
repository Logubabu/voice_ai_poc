import asyncio
import os
import time

from knowledge_base.repository import KnowledgeBaseRepository
from knowledge_base.parsers import ParserFactory
from knowledge_base.chunking import StructureAwareChunker
from knowledge_base.embeddings import EmbeddingProvider
from knowledge_base.vector_store import VectorStore
from knowledge_base.exceptions import DocumentProcessingError
from app.utils.logging import logger


class DocumentIngestionPipeline:
    """Async background worker pipeline for document ingestion, parsing, chunking, embedding, and vector storage."""

    def __init__(
        self,
        repository: KnowledgeBaseRepository,
        vector_store: VectorStore,
        embedding_provider: EmbeddingProvider,
        max_concurrency: int = 2,
        collection_name: str = "sharyx_kb_vectors",
    ):
        self.repository = repository
        self.vector_store = vector_store
        self.embedding_provider = embedding_provider
        self.max_concurrency = max_concurrency
        self.collection_name = collection_name
        self.semaphore = asyncio.Semaphore(max_concurrency)
        self.chunker = StructureAwareChunker(target_chunk_tokens=600, overlap_tokens=80)

    async def ingest_document(self, document_id: str, tenant_id: str) -> bool:
        """Asynchronously processes a document: validates, parses, chunks, embeds, stores vectors, updates status."""
        async with self.semaphore:
            start_time = time.time()
            logger.info(f"[INGESTION] Starting processing for document '{document_id}' (tenant: '{tenant_id}')")

            doc = await self.repository.get_document(document_id, tenant_id=tenant_id)
            if not doc:
                logger.error(f"[INGESTION][ERROR] Document '{document_id}' not found.")
                return False

            try:
                # Mark status -> processing
                await self.repository.update_document_status(doc_id=document_id, status="processing")

                # Read raw file binary
                if not os.path.exists(doc.storage_path):
                    raise DocumentProcessingError(f"Storage file not found at path '{doc.storage_path}'.")

                with open(doc.storage_path, "rb") as f:
                    file_content = f.read()

                # Validate non-empty file
                if not file_content:
                    raise DocumentProcessingError(f"Document file '{doc.filename}' is empty (0 bytes).")

                # Parse document text into structured pages
                parser = ParserFactory.get_parser(filename=doc.original_filename, mime_type=doc.mime_type)
                pages = parser.parse(file_content=file_content, filename=doc.original_filename)

                page_count = max(1, len(pages))

                # Structure-aware chunking
                chunks = self.chunker.chunk_pages(
                    pages=pages,
                    document_id=doc.id,
                    tenant_id=doc.tenant_id,
                    knowledge_base_id=doc.knowledge_base_id,
                    source_name=doc.original_filename,
                    source_type=doc.mime_type,
                    document_version=doc.version,
                )

                if not chunks:
                    raise DocumentProcessingError(f"No text chunks could be extracted from document '{doc.original_filename}'.")

                # Generate Embeddings for chunks
                chunk_texts = [c.content for c in chunks]
                embeddings = await self.embedding_provider.embed_documents(chunk_texts)

                # Prepare Vector Store points & payloads
                vectors = embeddings
                payloads = []
                for c in chunks:
                    meta = dict(c.metadata)
                    meta["content"] = c.content
                    payloads.append(meta)
                chunk_ids = [c.id for c in chunks]

                # Store vectors into Qdrant/VectorStore with MANDATORY tenant_id
                await self.vector_store.upsert_chunks(
                    collection_name=self.collection_name,
                    vectors=vectors,
                    payloads=payloads,
                    ids=chunk_ids,
                )

                # Save document chunks metadata persistently
                await self.repository.save_chunks(chunks)

                # Mark status -> INDEXED
                await self.repository.update_document_status(
                    doc_id=document_id,
                    status="indexed",
                    chunk_count=len(chunks),
                    page_count=page_count,
                )

                duration_ms = (time.time() - start_time) * 1000
                logger.info(f"[INGESTION][SUCCESS] Document '{doc.original_filename}' indexed successfully ({len(chunks)} chunks, {duration_ms:.1f}ms)")
                return True

            except Exception as e:
                duration_ms = (time.time() - start_time) * 1000
                sanitized_error = str(e)[:300]
                logger.exception(f"[INGESTION][FAILED] Document '{document_id}' processing failed ({duration_ms:.1f}ms): {sanitized_error}")
                await self.repository.update_document_status(
                    doc_id=document_id,
                    status="failed",
                    error_message=sanitized_error,
                )
                return False
