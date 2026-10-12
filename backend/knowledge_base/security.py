import re

from knowledge_base.exceptions import TenantAccessError
from app.utils.logging import logger


class SecurityManager:
    """Security manager enforcing tenant data isolation and prompt injection mitigation."""

    PROMPT_INJECTION_PATTERNS = [
        re.compile(r"ignore\s+(all\s+)?(previous|above|prior)\s+instructions?", re.IGNORECASE),
        re.compile(r"reveal\s+(system\s+prompt|secret|api\s+key)", re.IGNORECASE),
        re.compile(r"you\s+are\s+now\s+a", re.IGNORECASE),
        re.compile(r"system\s*:\s*", re.IGNORECASE),
    ]

    @staticmethod
    def validate_tenant_access(request_tenant_id: str, resource_tenant_id: str):
        """Strictly validates that request tenant matches resource tenant."""
        if not request_tenant_id or not resource_tenant_id:
            raise TenantAccessError("SECURITY VIOLATION: Missing tenant identification context.")
        if request_tenant_id != resource_tenant_id:
            logger.error(f"[SECURITY][TENANT-VIOLATION] Access denied: Request tenant '{request_tenant_id}' attempted to access resource owned by '{resource_tenant_id}'!")
            raise TenantAccessError(f"SECURITY VIOLATION: Access denied to resource owned by tenant '{resource_tenant_id}'.")

    @classmethod
    def sanitize_retrieved_content(cls, content: str) -> str:
        """Sanitizes retrieved text chunks to prevent prompt injection attempts."""
        clean_text = content
        for pattern in cls.PROMPT_INJECTION_PATTERNS:
            clean_text = pattern.sub("[REDACTED_INSTRUCTION]", clean_text)
        return clean_text
