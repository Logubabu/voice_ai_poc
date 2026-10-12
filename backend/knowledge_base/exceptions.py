class KnowledgeBaseError(Exception):
    """Base exception for all Knowledge Base errors."""
    pass


class DocumentProcessingError(KnowledgeBaseError):
    """Raised when document parsing, validation, or text extraction fails."""
    pass


class VectorStoreError(KnowledgeBaseError):
    """Raised when vector database operations fail."""
    pass


class EmbeddingError(KnowledgeBaseError):
    """Raised when embedding generation fails."""
    pass


class RetrievalError(KnowledgeBaseError):
    """Raised when knowledge retrieval fails."""
    pass


class TenantAccessError(KnowledgeBaseError):
    """Raised when tenant data isolation or access permissions are violated."""
    pass


class DocumentNotFoundError(KnowledgeBaseError):
    """Raised when requested document is not found."""
    pass


class KnowledgeBaseNotFoundError(KnowledgeBaseError):
    """Raised when requested knowledge base is not found."""
    pass
