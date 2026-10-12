from enum import Enum
from typing import Dict, Any, Optional
from pydantic import BaseModel, Field


class CallbackStatus(str, Enum):
    PENDING = "PENDING"
    SCHEDULED = "SCHEDULED"
    QUEUED = "QUEUED"
    DIALING = "DIALING"
    RINGING = "RINGING"
    IN_PROGRESS = "IN_PROGRESS"
    ANSWERED = "ANSWERED"
    COMPLETED = "COMPLETED"
    NO_ANSWER = "NO_ANSWER"
    BUSY = "BUSY"
    VOICEMAIL = "VOICEMAIL"
    FAILED = "FAILED"
    RETRY_PENDING = "RETRY_PENDING"
    CANCELLED = "CANCELLED"
    EXPIRED = "EXPIRED"
    WAITING_FOR_CREDITS = "WAITING_FOR_CREDITS"


# Allowed status transitions in the callback state machine
ALLOWED_STATUS_TRANSITIONS = {
    CallbackStatus.PENDING: {CallbackStatus.SCHEDULED, CallbackStatus.CANCELLED, CallbackStatus.FAILED},
    CallbackStatus.SCHEDULED: {CallbackStatus.QUEUED, CallbackStatus.DIALING, CallbackStatus.CANCELLED, CallbackStatus.EXPIRED, CallbackStatus.FAILED, CallbackStatus.WAITING_FOR_CREDITS},
    CallbackStatus.QUEUED: {CallbackStatus.DIALING, CallbackStatus.CANCELLED, CallbackStatus.FAILED, CallbackStatus.SCHEDULED},
    CallbackStatus.DIALING: {CallbackStatus.RINGING, CallbackStatus.IN_PROGRESS, CallbackStatus.ANSWERED, CallbackStatus.NO_ANSWER, CallbackStatus.BUSY, CallbackStatus.VOICEMAIL, CallbackStatus.FAILED, CallbackStatus.RETRY_PENDING},
    CallbackStatus.RINGING: {CallbackStatus.IN_PROGRESS, CallbackStatus.ANSWERED, CallbackStatus.NO_ANSWER, CallbackStatus.BUSY, CallbackStatus.VOICEMAIL, CallbackStatus.FAILED, CallbackStatus.RETRY_PENDING},
    CallbackStatus.IN_PROGRESS: {CallbackStatus.ANSWERED, CallbackStatus.COMPLETED, CallbackStatus.FAILED, CallbackStatus.NO_ANSWER},
    CallbackStatus.ANSWERED: {CallbackStatus.COMPLETED, CallbackStatus.FAILED},
    CallbackStatus.COMPLETED: set(),  # Terminal state
    CallbackStatus.NO_ANSWER: {CallbackStatus.RETRY_PENDING, CallbackStatus.FAILED},
    CallbackStatus.BUSY: {CallbackStatus.RETRY_PENDING, CallbackStatus.FAILED},
    CallbackStatus.VOICEMAIL: {CallbackStatus.RETRY_PENDING, CallbackStatus.COMPLETED, CallbackStatus.FAILED},
    CallbackStatus.FAILED: {CallbackStatus.RETRY_PENDING, CallbackStatus.SCHEDULED},
    CallbackStatus.RETRY_PENDING: {CallbackStatus.SCHEDULED, CallbackStatus.QUEUED, CallbackStatus.DIALING, CallbackStatus.CANCELLED, CallbackStatus.FAILED, CallbackStatus.WAITING_FOR_CREDITS},
    CallbackStatus.CANCELLED: set(),  # Terminal state
    CallbackStatus.EXPIRED: {CallbackStatus.SCHEDULED, CallbackStatus.RETRY_PENDING},
    CallbackStatus.WAITING_FOR_CREDITS: {CallbackStatus.SCHEDULED, CallbackStatus.CANCELLED, CallbackStatus.QUEUED, CallbackStatus.DIALING},
}


def can_transition_status(current: str, target: str) -> bool:
    """Validates if transitioning from current status to target status is valid according to state machine."""
    try:
        curr_enum = CallbackStatus(current)
        target_enum = CallbackStatus(target)
        if curr_enum == target_enum:
            return True
        allowed = ALLOWED_STATUS_TRANSITIONS.get(curr_enum, set())
        return target_enum in allowed
    except Exception:
        return False


def mask_phone_number(phone: str) -> str:
    """Masks phone number for security logging (e.g., +919876543210 -> +919******210)."""
    if not phone or len(phone) < 7:
        return "***"
    return phone[:4] + "*" * (len(phone) - 7) + phone[-3:]


class CallbackModel(BaseModel):
    id: str
    tenant_id: str = "default_tenant"
    customer_id: Optional[str] = None
    conversation_id: str = ""
    source_call_id: Optional[str] = None
    phone_number: str
    masked_phone_number: str = ""
    customer_name: str = "Valued Customer"
    reason: str = "Customer requested callback"
    callback_context: str = ""
    requested_time_text: str
    scheduled_at_utc: str
    timezone: str = "Asia/Kolkata"
    status: str = CallbackStatus.SCHEDULED.value
    attempt_count: int = 0
    max_attempts: int = 3
    last_attempt_at: Optional[str] = None
    next_attempt_at: Optional[str] = None
    call_sid: Optional[str] = None
    telephony_provider: str = "twilio"
    idempotency_key: str
    created_at: str
    updated_at: str
    completed_at: Optional[str] = None
    failure_reason: Optional[str] = None
    last_call_status: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


class CallbackCreateRequest(BaseModel):
    phone_number: str
    requested_time: Optional[str] = None
    scheduled_at: Optional[str] = None
    timezone: Optional[str] = None
    reason: Optional[str] = "Customer requested callback"
    callback_reason: Optional[str] = None
    customer_name: Optional[str] = "Valued Customer"
    contact_name: Optional[str] = None
    conversation_id: Optional[str] = ""
    call_id: Optional[str] = None
    callback_context: Optional[str] = ""
    tenant_id: Optional[str] = "default_tenant"
    priority: Optional[str] = "normal"


class CallbackRescheduleRequest(BaseModel):
    new_requested_time: str
    timezone: Optional[str] = None
    reason: Optional[str] = None


class CallbackCancelRequest(BaseModel):
    reason: Optional[str] = "Cancelled by user"


class CallbackResponse(BaseModel):
    success: bool
    callback_id: Optional[str] = None
    scheduled_at: Optional[str] = None
    timezone: Optional[str] = None
    status: Optional[str] = None
    message: str
    error_code: Optional[str] = None
    details: Optional[Dict[str, Any]] = None
