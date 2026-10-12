import asyncio
import uuid
import time
from datetime import datetime, timezone, timedelta
from typing import Optional

from app.config import config
from app.callbacks.models import CallbackModel, CallbackStatus
from app.callbacks.repository import callback_repository, CallbackRepository
from app.callbacks.metrics import callback_metrics
from app.telephony.provider import get_telephony_provider
from app.utils.logging import logger
from app.utils.audit import audit_logger


class CallbackSchedulerWorker:
    """Durable background worker for executing scheduled outbound voice callbacks."""

    def __init__(
        self,
        repo: CallbackRepository = callback_repository,
        worker_id: Optional[str] = None,
        poll_interval: float = 5.0,
    ):
        self.repo = repo
        self.worker_id = worker_id or f"worker_{uuid.uuid4().hex[:6]}"
        self.poll_interval = poll_interval
        self._running = False
        self._task: Optional[asyncio.Task] = None
        self.max_attempts = getattr(config, "CALLBACK_MAX_ATTEMPTS", 3)
        retry_delays_str = getattr(config, "CALLBACK_RETRY_DELAYS", "300,900")
        try:
            self.retry_delays = [int(x.strip()) for x in retry_delays_str.split(",") if x.strip()]
        except Exception:
            self.retry_delays = [300, 900]

    async def start(self):
        """Starts the background scheduler polling loop."""
        if self._running:
            return
        self._running = True
        self._task = asyncio.create_task(self._run_loop())
        logger.info(f"[SCHEDULER-WORKER] Started worker '{self.worker_id}' (interval: {self.poll_interval}s)")

    async def stop(self):
        """Stops the background scheduler worker gracefully."""
        if not self._running:
            return
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        logger.info(f"[SCHEDULER-WORKER] Stopped worker '{self.worker_id}'")

    async def _run_loop(self):
        while self._running:
            try:
                await self.process_due_callbacks()
                await self.repo.recover_stale_dialing_callbacks(timeout_seconds=getattr(config, "CALLBACK_RING_TIMEOUT", 30) * 2)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.exception(f"[SCHEDULER-WORKER][ERROR] Error in worker loop: {e}")

            await asyncio.sleep(self.poll_interval)

    async def process_due_callbacks(self) -> int:
        """Finds and claims due callbacks atomically, initiating outbound calls for each claimed item."""
        now_utc = datetime.now(timezone.utc).isoformat()
        claimed = await self.repo.claim_due_callbacks(now_utc_iso=now_utc, limit=10, worker_id=self.worker_id)
        if not claimed:
            return 0

        logger.info(f"[SCHEDULER-WORKER] Worker '{self.worker_id}' claimed {len(claimed)} due callback(s)")

        for cb in claimed:
            asyncio.create_task(self._execute_single_callback(cb))

        return len(claimed)

    async def _execute_single_callback(self, cb: CallbackModel):
        """Executes an individual outbound call for a claimed callback model."""
        start_time = time.time()
        logger.info(f"[SCHEDULER-WORKER] Initiating outbound call for callback '{cb.id}' (to: '{cb.masked_phone_number}')")

        provider_name = cb.telephony_provider or getattr(config, "TELEPHONY_PROVIDER", "twilio")
        provider = get_telephony_provider(provider_name)

        try:
            # Initiate outbound call with attached callback context parameters
            call_res = await provider.initiate_outbound_call(
                to_number=cb.phone_number,
                callback_id=cb.id,
                conversation_id=cb.conversation_id,
                customer_name=cb.customer_name,
                reason=cb.reason,
                callback_context=cb.callback_context,
            )

            duration_s = time.time() - start_time

            if call_res.get("success"):
                call_sid = call_res.get("call_sid") or call_res.get("uuid") or "call_unknown"
                logger.info(f"[SCHEDULER-WORKER] Outbound call initiated successfully. SID: '{call_sid}' for callback '{cb.id}'")

                await self.repo.update_status(
                    callback_id=cb.id,
                    target_status=CallbackStatus.IN_PROGRESS.value,
                    call_sid=call_sid,
                    last_call_status=call_res.get("status", "initiated"),
                )

                callback_metrics.record_success(cb.id, duration_s)
                audit_logger.log_event(
                    event="CALLBACK_DIAL_SUCCESS",
                    category="callback",
                    session_id=cb.conversation_id,
                    actor="scheduler_worker",
                    action="outbound_call",
                    details={"callback_id": cb.id, "call_sid": call_sid, "phone": cb.masked_phone_number},
                    status="SUCCESS",
                )
            else:
                error_msg = call_res.get("error", "Telephony provider initiation failed")
                logger.error(f"[SCHEDULER-WORKER] Outbound call failed for callback '{cb.id}': {error_msg}")
                await self._handle_callback_failure(cb, error_msg)

        except Exception as e:
            duration_s = time.time() - start_time
            logger.exception(f"[SCHEDULER-WORKER][ERROR] Exception during outbound call execution for '{cb.id}': {e}")
            await self._handle_callback_failure(cb, str(e))

    async def _handle_callback_failure(self, cb: CallbackModel, failure_reason: str):
        """Handles callback failure and schedules retry if within max_attempts."""
        if cb.attempt_count < self.max_attempts:
            delay_idx = min(cb.attempt_count - 1, len(self.retry_delays) - 1)
            delay_seconds = self.retry_delays[max(0, delay_idx)]
            next_attempt_dt = datetime.now(timezone.utc) + timedelta(seconds=delay_seconds)
            next_attempt_iso = next_attempt_dt.isoformat()

            logger.info(
                f"[SCHEDULER-WORKER] Scheduling retry #{cb.attempt_count + 1} for callback '{cb.id}' in {delay_seconds}s (at {next_attempt_iso})"
            )

            await self.repo.update_status(
                callback_id=cb.id,
                target_status=CallbackStatus.RETRY_PENDING.value,
                failure_reason=failure_reason,
                next_attempt_at=next_attempt_iso,
            )

            callback_metrics.record_retry(cb.id, cb.attempt_count + 1)
        else:
            logger.error(f"[SCHEDULER-WORKER] Max attempts ({self.max_attempts}) reached for callback '{cb.id}'. Marking as FAILED.")
            await self.repo.update_status(
                callback_id=cb.id,
                target_status=CallbackStatus.FAILED.value,
                failure_reason=f"Max attempts ({self.max_attempts}) exceeded. Last error: {failure_reason}",
            )
            callback_metrics.record_failed(cb.id, failure_reason)


callback_scheduler_worker = CallbackSchedulerWorker()
