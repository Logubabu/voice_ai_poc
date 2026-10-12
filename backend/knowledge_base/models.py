import uuid
from datetime import datetime, timezone
from typing import Optional, Dict, Any


def generate_uuid() -> str:
    return str(uuid.uuid4())


def current_utc_time() -> datetime:
    return datetime.now(timezone.utc)


class KnowledgeBaseModel:
    def __init__(
        self,
        tenant_id: str,
        name: str,
        description: Optional[str] = None,
        id: Optional[str] = None,
        status: str = "active",
        created_at: Optional[datetime] = None,
        updated_at: Optional[datetime] = None,
    ):
        self.id = id or generate_uuid()
        self.tenant_id = tenant_id
        self.name = name
        self.description = description
        self.status = status
        self.created_at = created_at or current_utc_time()
        self.updated_at = updated_at or current_utc_time()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "tenant_id": self.tenant_id,
            "name": self.name,
            "description": self.description,
            "status": self.status,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "KnowledgeBaseModel":
        return cls(
            id=data["id"],
            tenant_id=data["tenant_id"],
            name=data["name"],
            description=data.get("description"),
            status=data.get("status", "active"),
            created_at=datetime.fromisoformat(data["created_at"]),
            updated_at=datetime.fromisoformat(data["updated_at"]),
        )


class DocumentModel:
    def __init__(
        self,
        knowledge_base_id: str,
        tenant_id: str,
        filename: str,
        original_filename: str,
        mime_type: str,
        size_bytes: int,
        checksum: str,
        storage_path: str,
        status: str = "uploaded",
        version: int = 1,
        language: str = "en",
        page_count: int = 1,
        chunk_count: int = 0,
        error_message: Optional[str] = None,
        id: Optional[str] = None,
        created_at: Optional[datetime] = None,
        updated_at: Optional[datetime] = None,
    ):
        self.id = id or generate_uuid()
        self.knowledge_base_id = knowledge_base_id
        self.tenant_id = tenant_id
        self.filename = filename
        self.original_filename = original_filename
        self.mime_type = mime_type
        self.size_bytes = size_bytes
        self.checksum = checksum
        self.storage_path = storage_path
        self.status = status
        self.version = version
        self.language = language
        self.page_count = page_count
        self.chunk_count = chunk_count
        self.error_message = error_message
        self.created_at = created_at or current_utc_time()
        self.updated_at = updated_at or current_utc_time()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "knowledge_base_id": self.knowledge_base_id,
            "tenant_id": self.tenant_id,
            "filename": self.filename,
            "original_filename": self.original_filename,
            "mime_type": self.mime_type,
            "size_bytes": self.size_bytes,
            "checksum": self.checksum,
            "storage_path": self.storage_path,
            "status": self.status,
            "version": self.version,
            "language": self.language,
            "page_count": self.page_count,
            "chunk_count": self.chunk_count,
            "error_message": self.error_message,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "DocumentModel":
        return cls(
            id=data["id"],
            knowledge_base_id=data["knowledge_base_id"],
            tenant_id=data["tenant_id"],
            filename=data["filename"],
            original_filename=data["original_filename"],
            mime_type=data["mime_type"],
            size_bytes=data["size_bytes"],
            checksum=data["checksum"],
            storage_path=data["storage_path"],
            status=data.get("status", "uploaded"),
            version=data.get("version", 1),
            language=data.get("language", "en"),
            page_count=data.get("page_count", 1),
            chunk_count=data.get("chunk_count", 0),
            error_message=data.get("error_message"),
            created_at=datetime.fromisoformat(data["created_at"]),
            updated_at=datetime.fromisoformat(data["updated_at"]),
        )


class DocumentChunkModel:
    def __init__(
        self,
        document_id: str,
        tenant_id: str,
        chunk_index: int,
        content: str,
        page_number: int = 1,
        section_title: Optional[str] = None,
        token_count: int = 0,
        content_hash: str = "",
        metadata: Optional[Dict[str, Any]] = None,
        id: Optional[str] = None,
        created_at: Optional[datetime] = None,
    ):
        self.id = id or generate_uuid()
        self.document_id = document_id
        self.tenant_id = tenant_id
        self.chunk_index = chunk_index
        self.content = content
        self.page_number = page_number
        self.section_title = section_title
        self.token_count = token_count
        self.content_hash = content_hash
        self.metadata = metadata or {}
        self.created_at = created_at or current_utc_time()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "document_id": self.document_id,
            "tenant_id": self.tenant_id,
            "chunk_index": self.chunk_index,
            "content": self.content,
            "page_number": self.page_number,
            "section_title": self.section_title,
            "token_count": self.token_count,
            "content_hash": self.content_hash,
            "metadata": self.metadata,
            "created_at": self.created_at.isoformat(),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "DocumentChunkModel":
        return cls(
            id=data["id"],
            document_id=data["document_id"],
            tenant_id=data["tenant_id"],
            chunk_index=data["chunk_index"],
            content=data["content"],
            page_number=data.get("page_number", 1),
            section_title=data.get("section_title"),
            token_count=data.get("token_count", 0),
            content_hash=data.get("content_hash", ""),
            metadata=data.get("metadata", {}),
            created_at=datetime.fromisoformat(data["created_at"]),
        )
