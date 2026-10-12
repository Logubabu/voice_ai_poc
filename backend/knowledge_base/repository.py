import asyncio
import json
import sqlite3
import os
from typing import List, Optional
from datetime import datetime

from knowledge_base.models import KnowledgeBaseModel, DocumentModel, DocumentChunkModel


class KnowledgeBaseRepository:
    """Persistent SQLite-backed repository for KnowledgeBase, Document, and Chunk metadata."""

    def __init__(self, db_path: str = "data/knowledge_base.db"):
        self.db_path = db_path
        os.makedirs(os.path.dirname(os.path.abspath(db_path)), exist_ok=True)
        self._lock = asyncio.Lock()
        self._init_db()

    def _get_connection(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self):
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS knowledge_bases (
                    id TEXT PRIMARY KEY,
                    tenant_id TEXT NOT NULL,
                    name TEXT NOT NULL,
                    description TEXT,
                    status TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
            """)
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_kb_tenant ON knowledge_bases(tenant_id)")

            cursor.execute("""
                CREATE TABLE IF NOT EXISTS documents (
                    id TEXT PRIMARY KEY,
                    knowledge_base_id TEXT NOT NULL,
                    tenant_id TEXT NOT NULL,
                    filename TEXT NOT NULL,
                    original_filename TEXT NOT NULL,
                    mime_type TEXT NOT NULL,
                    size_bytes INTEGER NOT NULL,
                    checksum TEXT NOT NULL,
                    storage_path TEXT NOT NULL,
                    status TEXT NOT NULL,
                    version INTEGER NOT NULL DEFAULT 1,
                    language TEXT DEFAULT 'en',
                    page_count INTEGER DEFAULT 1,
                    chunk_count INTEGER DEFAULT 0,
                    error_message TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    FOREIGN KEY(knowledge_base_id) REFERENCES knowledge_bases(id) ON DELETE CASCADE
                )
            """)
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_doc_tenant_kb ON documents(tenant_id, knowledge_base_id)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_doc_checksum ON documents(tenant_id, knowledge_base_id, checksum)")

            cursor.execute("""
                CREATE TABLE IF NOT EXISTS document_chunks (
                    id TEXT PRIMARY KEY,
                    document_id TEXT NOT NULL,
                    tenant_id TEXT NOT NULL,
                    chunk_index INTEGER NOT NULL,
                    content TEXT NOT NULL,
                    page_number INTEGER DEFAULT 1,
                    section_title TEXT,
                    token_count INTEGER DEFAULT 0,
                    content_hash TEXT NOT NULL,
                    metadata TEXT,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY(document_id) REFERENCES documents(id) ON DELETE CASCADE
                )
            """)
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_chunk_doc ON document_chunks(document_id)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_chunk_tenant ON document_chunks(tenant_id)")
            conn.commit()

    # --- Knowledge Base CRUD ---

    async def create_kb(self, kb: KnowledgeBaseModel) -> KnowledgeBaseModel:
        async with self._lock:
            def _op():
                with self._get_connection() as conn:
                    conn.cursor().execute(
                        "INSERT INTO knowledge_bases (id, tenant_id, name, description, status, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
                        (kb.id, kb.tenant_id, kb.name, kb.description, kb.status, kb.created_at.isoformat(), kb.updated_at.isoformat())
                    )
                    conn.commit()
            await asyncio.to_thread(_op)
            return kb

    async def get_kb(self, kb_id: str, tenant_id: Optional[str] = None) -> Optional[KnowledgeBaseModel]:
        def _op():
            with self._get_connection() as conn:
                if tenant_id:
                    row = conn.cursor().execute("SELECT * FROM knowledge_bases WHERE id = ? AND tenant_id = ?", (kb_id, tenant_id)).fetchone()
                else:
                    row = conn.cursor().execute("SELECT * FROM knowledge_bases WHERE id = ?", (kb_id,)).fetchone()
                if row:
                    return KnowledgeBaseModel.from_dict(dict(row))
                return None
        return await asyncio.to_thread(_op)

    async def list_kbs(self, tenant_id: str) -> List[KnowledgeBaseModel]:
        def _op():
            with self._get_connection() as conn:
                rows = conn.cursor().execute("SELECT * FROM knowledge_bases WHERE tenant_id = ? ORDER BY created_at DESC", (tenant_id,)).fetchall()
                return [KnowledgeBaseModel.from_dict(dict(r)) for r in rows]
        return await asyncio.to_thread(_op)

    async def update_kb(self, kb: KnowledgeBaseModel) -> KnowledgeBaseModel:
        async with self._lock:
            def _op():
                with self._get_connection() as conn:
                    kb.updated_at = datetime.now()
                    conn.cursor().execute(
                        "UPDATE knowledge_bases SET name = ?, description = ?, status = ?, updated_at = ? WHERE id = ? AND tenant_id = ?",
                        (kb.name, kb.description, kb.status, kb.updated_at.isoformat(), kb.id, kb.tenant_id)
                    )
                    conn.commit()
            await asyncio.to_thread(_op)
            return kb

    async def delete_kb(self, kb_id: str, tenant_id: str) -> bool:
        async with self._lock:
            def _op():
                with self._get_connection() as conn:
                    cur = conn.cursor()
                    cur.execute("DELETE FROM document_chunks WHERE tenant_id = ? AND document_id IN (SELECT id FROM documents WHERE knowledge_base_id = ?)", (tenant_id, kb_id))
                    cur.execute("DELETE FROM documents WHERE knowledge_base_id = ? AND tenant_id = ?", (kb_id, tenant_id))
                    res = cur.execute("DELETE FROM knowledge_bases WHERE id = ? AND tenant_id = ?", (kb_id, tenant_id))
                    conn.commit()
                    return res.rowcount > 0
            return await asyncio.to_thread(_op)

    # --- Document CRUD ---

    async def create_document(self, doc: DocumentModel) -> DocumentModel:
        async with self._lock:
            def _op():
                with self._get_connection() as conn:
                    conn.cursor().execute(
                        """INSERT INTO documents (
                            id, knowledge_base_id, tenant_id, filename, original_filename, mime_type,
                            size_bytes, checksum, storage_path, status, version, language, page_count,
                            chunk_count, error_message, created_at, updated_at
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                        (
                            doc.id, doc.knowledge_base_id, doc.tenant_id, doc.filename, doc.original_filename,
                            doc.mime_type, doc.size_bytes, doc.checksum, doc.storage_path, doc.status,
                            doc.version, doc.language, doc.page_count, doc.chunk_count, doc.error_message,
                            doc.created_at.isoformat(), doc.updated_at.isoformat()
                        )
                    )
                    conn.commit()
            await asyncio.to_thread(_op)
            return doc

    async def find_duplicate_document(self, kb_id: str, tenant_id: str, checksum: str) -> Optional[DocumentModel]:
        def _op():
            with self._get_connection() as conn:
                row = conn.cursor().execute(
                    "SELECT * FROM documents WHERE knowledge_base_id = ? AND tenant_id = ? AND checksum = ? AND status != 'deleted' ORDER BY version DESC LIMIT 1",
                    (kb_id, tenant_id, checksum)
                ).fetchone()
                if row:
                    return DocumentModel.from_dict(dict(row))
                return None
        return await asyncio.to_thread(_op)

    async def get_document(self, doc_id: str, tenant_id: Optional[str] = None) -> Optional[DocumentModel]:
        def _op():
            with self._get_connection() as conn:
                if tenant_id:
                    row = conn.cursor().execute("SELECT * FROM documents WHERE id = ? AND tenant_id = ?", (doc_id, tenant_id)).fetchone()
                else:
                    row = conn.cursor().execute("SELECT * FROM documents WHERE id = ?", (doc_id,)).fetchone()
                if row:
                    return DocumentModel.from_dict(dict(row))
                return None
        return await asyncio.to_thread(_op)

    async def list_documents(self, kb_id: str, tenant_id: str) -> List[DocumentModel]:
        def _op():
            with self._get_connection() as conn:
                rows = conn.cursor().execute(
                    "SELECT * FROM documents WHERE knowledge_base_id = ? AND tenant_id = ? AND status != 'deleted' ORDER BY created_at DESC",
                    (kb_id, tenant_id)
                ).fetchall()
                return [DocumentModel.from_dict(dict(r)) for r in rows]
        return await asyncio.to_thread(_op)

    async def update_document_status(
        self, doc_id: str, status: str, chunk_count: Optional[int] = None, page_count: Optional[int] = None, error_message: Optional[str] = None
    ) -> bool:
        async with self._lock:
            def _op():
                with self._get_connection() as conn:
                    updated_at = datetime.now().isoformat()
                    cur = conn.cursor()
                    if chunk_count is not None and page_count is not None:
                        cur.execute(
                            "UPDATE documents SET status = ?, chunk_count = ?, page_count = ?, error_message = ?, updated_at = ? WHERE id = ?",
                            (status, chunk_count, page_count, error_message, updated_at, doc_id)
                        )
                    else:
                        cur.execute(
                            "UPDATE documents SET status = ?, error_message = ?, updated_at = ? WHERE id = ?",
                            (status, error_message, updated_at, doc_id)
                        )
                    conn.commit()
                    return cur.rowcount > 0
            return await asyncio.to_thread(_op)

    async def delete_document(self, doc_id: str, tenant_id: str) -> bool:
        async with self._lock:
            def _op():
                with self._get_connection() as conn:
                    cur = conn.cursor()
                    cur.execute("DELETE FROM document_chunks WHERE document_id = ? AND tenant_id = ?", (doc_id, tenant_id))
                    cur.execute("UPDATE documents SET status = 'deleted', updated_at = ? WHERE id = ? AND tenant_id = ?", (datetime.now().isoformat(), doc_id, tenant_id))
                    conn.commit()
                    return cur.rowcount > 0
            return await asyncio.to_thread(_op)

    # --- Chunk CRUD ---

    async def save_chunks(self, chunks: List[DocumentChunkModel]):
        if not chunks:
            return
        async with self._lock:
            def _op():
                with self._get_connection() as conn:
                    cur = conn.cursor()
                    for chk in chunks:
                        meta_str = json.dumps(chk.metadata)
                        cur.execute(
                            """INSERT INTO document_chunks (
                                id, document_id, tenant_id, chunk_index, content, page_number, section_title, token_count, content_hash, metadata, created_at
                            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                            (
                                chk.id, chk.document_id, chk.tenant_id, chk.chunk_index, chk.content,
                                chk.page_number, chk.section_title, chk.token_count, chk.content_hash,
                                meta_str, chk.created_at.isoformat()
                            )
                        )
                    conn.commit()
            await asyncio.to_thread(_op)

    async def get_document_chunks(self, doc_id: str, tenant_id: str) -> List[DocumentChunkModel]:
        def _op():
            with self._get_connection() as conn:
                rows = conn.cursor().execute(
                    "SELECT * FROM document_chunks WHERE document_id = ? AND tenant_id = ? ORDER BY chunk_index ASC",
                    (doc_id, tenant_id)
                ).fetchall()
                results = []
                for r in rows:
                    d = dict(r)
                    if d.get("metadata"):
                        try:
                            d["metadata"] = json.loads(d["metadata"])
                        except Exception:
                            d["metadata"] = {}
                    results.append(DocumentChunkModel.from_dict(d))
                return results
        return await asyncio.to_thread(_op)
