import uuid
import hashlib
from datetime import datetime, timezone
from typing import Optional

from app.callbacks.models import (
    CallbackModel,
    CallbackStatus,
    CallbackCreateRequest,
    CallbackRescheduleRequest,
    CallbackCancelRequest,
    CallbackResponse,
    mask_phone_number,
)
from app.callbacks.repository import callback_repository
from app.callbacks.time_resolver import (
    normalize_e164_phone,
    parse_natural_language_time,
    TimeResolverError,
)
from app.callbacks.metrics import callback_metrics
from app.utils.logging import logger
from app.utils.audit import audit_logger


class CallbackService:
    """Service encapsulating high-level scheduled callback business logic."""

    def __init__(self, repo=callback_repository):
        self.repo = repo

    def _generate_idempotency_key(self, tenant_id: str, conversation_id: str, phone: str, scheduled_at_utc: str) -> str:
        raw = f"{tenant_id}:{conversation_id}:{phone}:{scheduled_at_utc}"
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()

    async def schedule_callback(self, req: CallbackCreateRequest) -> CallbackResponse:
        """Schedules a new voice callback with E.164 normalization, timezone resolution, and idempotency."""
        try:
            raw_time = req.requested_time or req.scheduled_at
            if not raw_time:
                raise TimeResolverError("Scheduled time is required.")

            phone_norm = normalize_e164_phone(req.phone_number)
            time_res = parse_natural_language_time(raw_time, user_tz_str=req.timezone)

            scheduled_at_utc = time_res["scheduled_at_utc"]
            tz_name = time_res["timezone"]
            tenant_id = req.tenant_id or "default_tenant"
            conv_id = req.conversation_id or f"conv_{uuid.uuid4().hex[:8]}"

            idempotency_key = self._generate_idempotency_key(tenant_id, conv_id, phone_norm, scheduled_at_utc)
            cb_id = f"cb_{uuid.uuid4().hex[:12]}"
            now_iso = datetime.now(timezone.utc).isoformat()

            cust_name = req.contact_name if req.contact_name and req.contact_name != "Valued Customer" else (req.customer_name or "Valued Customer")
            cb_reason = req.callback_reason if req.callback_reason and req.callback_reason != "Customer requested callback" else (req.reason or "Customer requested callback")

            cb_model = CallbackModel(
                id=cb_id,
                tenant_id=tenant_id,
                customer_id=cust_name,
                conversation_id=conv_id,
                source_call_id=req.call_id,
                phone_number=phone_norm,
                masked_phone_number=mask_phone_number(phone_norm),
                customer_name=cust_name,
                reason=cb_reason,
                callback_context=req.callback_context or "",
                requested_time_text=req.requested_time,
                scheduled_at_utc=scheduled_at_utc,
                timezone=tz_name,
                status=CallbackStatus.SCHEDULED.value,
                attempt_count=0,
                max_attempts=3,
                telephony_provider="twilio",
                idempotency_key=idempotency_key,
                created_at=now_iso,
                updated_at=now_iso,
                metadata={"display_time": time_res.get("display_time")},
            )

            created_model, is_new = await self.repo.create_callback(cb_model)

            if is_new:
                callback_metrics.record_created(created_model.id, scheduled_at_utc)
                audit_logger.log_event(
                    event="CALLBACK_SCHEDULED",
                    category="callback",
                    session_id=conv_id,
                    actor="backend",
                    action="schedule_callback",
                    details={
                        "callback_id": created_model.id,
                        "masked_phone": created_model.masked_phone_number,
                        "scheduled_at_utc": scheduled_at_utc,
                        "timezone": tz_name,
                    },
                    status="SUCCESS",
                )
                msg = f"Your callback has been scheduled for {time_res.get('display_time', req.requested_time)}."
                if time_res.get("is_ambiguous"):
                    msg = f"Your callback has been scheduled for 10:00 AM tomorrow ({time_res.get('display_time')})."
            else:
                msg = f"Your callback is already scheduled for {created_model.requested_time_text}."

            return CallbackResponse(
                success=True,
                callback_id=created_model.id,
                scheduled_at=created_model.scheduled_at_utc,
                timezone=created_model.timezone,
                status=created_model.status,
                message=msg,
                details={
                    "display_time": time_res.get("display_time"),
                    "is_ambiguous": time_res.get("is_ambiguous"),
                }
            )

        except TimeResolverError as e:
            logger.warning(f"[CALLBACK-SERVICE] Validation error: {e.message}")
            return CallbackResponse(
                success=False,
                error_code=e.error_code,
                message=f"Could not schedule callback: {e.message}",
            )
        except Exception as e:
            logger.exception(f"[CALLBACK-SERVICE][ERROR] Failed to schedule callback: {e}")
            return CallbackResponse(
                success=False,
                error_code="INTERNAL_ERROR",
                message="An error occurred while scheduling your callback. Please try again.",
            )

    async def reschedule_callback(
        self,
        callback_id: str,
        req: CallbackRescheduleRequest,
        tenant_id: Optional[str] = None,
    ) -> CallbackResponse:
        """Reschedules an existing callback if in an eligible state."""
        cb = await self.repo.get_callback(callback_id, tenant_id=tenant_id)
        if not cb:
            # Try looking up by phone or conversation_id if callback_id not found directly
            callbacks = await self.repo.list_callbacks(tenant_id=tenant_id, limit=5)
            cb = next((c for c in callbacks if c.id == callback_id or c.phone_number == callback_id or c.conversation_id == callback_id), None)

        if not cb:
            return CallbackResponse(
                success=False,
                error_code="CALLBACK_NOT_FOUND",
                message=f"Callback '{callback_id}' was not found.",
            )

        if cb.status in (CallbackStatus.IN_PROGRESS.value, CallbackStatus.COMPLETED.value):
            return CallbackResponse(
                success=False,
                error_code="INVALID_STATE",
                message=f"Cannot reschedule callback '{cb.id}' because it is currently in status '{cb.status}'.",
            )

        try:
            time_res = parse_natural_language_time(req.new_requested_time, user_tz_str=req.timezone or cb.timezone)
            new_utc = time_res["scheduled_at_utc"]

            updated = await self.repo.update_status(
                callback_id=cb.id,
                target_status=CallbackStatus.SCHEDULED.value,
            )

            if updated:
                # Update scheduled time in repository
                with self.repo._get_connection() as conn:
                    conn.execute("""
                        UPDATE callbacks SET requested_time_text = ?, scheduled_at_utc = ?, timezone = ?, updated_at = ? WHERE id = ?
                    """, (req.new_requested_time, new_utc, time_res["timezone"], datetime.now(timezone.utc).isoformat(), cb.id))
                    conn.commit()

                callback_metrics.record_rescheduled(cb.id)
                return CallbackResponse(
                    success=True,
                    callback_id=cb.id,
                    scheduled_at=new_utc,
                    timezone=time_res["timezone"],
                    status=CallbackStatus.SCHEDULED.value,
                    message=f"Your callback has been rescheduled for {time_res.get('display_time', req.new_requested_time)}.",
                )
            else:
                return CallbackResponse(
                    success=False,
                    error_code="UPDATE_FAILED",
                    message="Failed to update callback schedule.",
                )

        except Exception as e:
            logger.exception(f"[CALLBACK-SERVICE][ERROR] Reschedule failed: {e}")
            return CallbackResponse(
                success=False,
                error_code="RESCHEDULE_ERROR",
                message=f"Could not reschedule callback: {str(e)}",
            )

    async def cancel_callback(
        self,
        callback_id: str,
        req: Optional[CallbackCancelRequest] = None,
        tenant_id: Optional[str] = None,
    ) -> CallbackResponse:
        """Idempotently cancels a scheduled callback."""
        cb = await self.repo.get_callback(callback_id, tenant_id=tenant_id)
        if not cb:
            # Check by phone or conversation_id
            callbacks = await self.repo.list_callbacks(tenant_id=tenant_id, limit=10)
            cb = next((c for c in callbacks if c.id == callback_id or c.phone_number == callback_id or c.conversation_id == callback_id), None)

        if not cb:
            return CallbackResponse(
                success=False,
                error_code="CALLBACK_NOT_FOUND",
                message=f"Callback '{callback_id}' was not found.",
            )

        if cb.status == CallbackStatus.CANCELLED.value:
            return CallbackResponse(
                success=True,
                callback_id=cb.id,
                status=cb.status,
                message="Callback is already cancelled.",
            )

        reason = (req and req.reason) or "Cancelled by user"
        updated = await self.repo.update_status(
            callback_id=cb.id,
            target_status=CallbackStatus.CANCELLED.value,
            failure_reason=reason,
        )
        if not updated:
            return CallbackResponse(
                success=False,
                error_code="CANCEL_FAILED",
                message="Failed to cancel callback.",
            )

        callback_metrics.record_cancelled(cb.id)
        return CallbackResponse(
            success=True,
            callback_id=cb.id,
            status=CallbackStatus.CANCELLED.value,
            message="Your callback has been cancelled successfully.",
        )

    async def get_callback_status(
        self,
        identifier: str,
        tenant_id: Optional[str] = None,
    ) -> CallbackResponse:
        """Retrieves status details for a callback by ID, phone number, or conversation ID."""
        cb = await self.repo.get_callback(identifier, tenant_id=tenant_id)
        if not cb:
            callbacks = await self.repo.list_callbacks(tenant_id=tenant_id, limit=20)
            cb = next((c for c in callbacks if c.id == identifier or c.phone_number == identifier or c.conversation_id == identifier), None)

        if not cb:
            return CallbackResponse(
                success=False,
                error_code="CALLBACK_NOT_FOUND",
                message=f"No callback found matching '{identifier}'.",
            )

        return CallbackResponse(
            success=True,
            callback_id=cb.id,
            scheduled_at=cb.scheduled_at_utc,
            timezone=cb.timezone,
            status=cb.status,
            message=f"Callback status for {cb.masked_phone_number} is '{cb.status}'. Scheduled for {cb.requested_time_text}.",
            details=cb.model_dump(),
        )


callback_service = CallbackService()
