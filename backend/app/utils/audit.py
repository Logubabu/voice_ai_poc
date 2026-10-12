import json
import sys
import time
from typing import Any, Dict, Optional


class AuditLogger:
    """Structured audit logger that outputs audit events exclusively to stdout (console only, no file storage)."""

    def __init__(self, service_name: str = "voice_ai_poc"):
        self.service_name = service_name

    def log_event(
        self,
        event: str,
        category: str = "general",
        actor: str = "system",
        action: str = "unknown",
        session_id: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
        status: str = "SUCCESS",
        duration_ms: Optional[float] = None,
    ):
        """Formats and prints a structured audit log line strictly to stdout without persisting to disk."""
        timestamp = time.strftime("%Y-%m-%d %H:%M:%S", time.gmtime())
        audit_record = {
            "timestamp": timestamp,
            "service": self.service_name,
            "category": category,
            "event": event,
            "actor": actor,
            "action": action,
            "status": status,
            "details": details or {},
        }
        if session_id:
            audit_record["session_id"] = session_id
        if duration_ms is not None:
            audit_record["duration_ms"] = round(duration_ms, 2)

        formatted_output = f"[AUDIT] {json.dumps(audit_record)}"
        print(formatted_output, file=sys.stdout, flush=True)


audit_logger = AuditLogger()
