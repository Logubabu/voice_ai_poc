from datetime import datetime
from enum import Enum
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field, ConfigDict


class DocumentStatus(str, Enum):
    UPLOADED = "uploaded"
    PROCESSING = "processing"
    INDEXED = "indexed"
    FAILED = "failed"
    DELETED = "deleted"


class KnowledgeBaseCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    description: Optional[str] = Field(None, max_length=500)
    tenant_id: str = Field(..., description="Tenant ID owning this Knowledge Base")


class KnowledgeBaseUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    description: Optional[str] = Field(None, max_length=500)


class KnowledgeBaseResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    tenant_id: str
    name: str
    description: Optional[str] = None
    status: str = "active"
    document_count: int = 0
    total_chunks: int = 0
    created_at: datetime
    updated_at: datetime


class DocumentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    knowledge_base_id: str
    tenant_id: str
    filename: str
    original_filename: str
    mime_type: str
    size_bytes: int
    checksum: str
    status: DocumentStatus
    version: int = 1
    language: Optional[str] = "en"
    page_count: Optional[int] = 1
    chunk_count: int = 0
    error_message: Optional[str] = None
    created_at: datetime
    updated_at: datetime


class DocumentListResponse(BaseModel):
    total: int
    documents: List[DocumentResponse]


class ChunkMetadata(BaseModel):
    document_id: str
    tenant_id: str
    knowledge_base_id: str
    agent_id: Optional[str] = None
    page_number: Optional[int] = 1
    section: Optional[str] = None
    chunk_index: int
    source_name: str
    source_type: str
    document_version: int = 1
    content_hash: str
    created_at: str


class DocumentChunkSchema(BaseModel):
    id: str
    document_id: str
    tenant_id: str
    chunk_index: int
    content: str
    page_number: Optional[int] = 1
    section_title: Optional[str] = None
    token_count: int = 0
    content_hash: str
    metadata: Dict[str, Any] = {}
    created_at: datetime


class KnowledgeSearchRequest(BaseModel):
    query: str = Field(..., min_length=1, description="The user query to search against the knowledge base")
    top_k: int = Field(5, ge=1, le=10, description="Top K candidate chunks to retrieve")
    category: Optional[str] = Field(None, description="Optional category filter")
    tenant_id: Optional[str] = Field(None, description="Explicit tenant ID filter if authorized")
    agent_id: Optional[str] = Field(None, description="Agent ID context")


class KnowledgeSearchResultItem(BaseModel):
    document_id: str
    document_name: str
    chunk_id: str
    content: str
    score: float
    page: Optional[int] = 1
    section: Optional[str] = None
    metadata: Dict[str, Any] = {}


class KnowledgeSearchResponse(BaseModel):
    success: bool = True
    found: bool = True
    query: str
    confidence: float
    latency_ms: float = 0.0
    results: List[KnowledgeSearchResultItem] = []
    message: Optional[str] = None
    error_code: Optional[str] = None
