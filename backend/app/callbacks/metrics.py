from typing import Dict, Any
from app.utils.logging import logger


class CallbackMetrics:
    """Metrics tracking for callback scheduling lifecycle and call delivery performance."""

    def __init__(self):
        self.stats: Dict[str, Any] = {
            "callback_created_total": 0,
            "callback_success_total": 0,
            "callback_failed_total": 0,
            "callback_cancelled_total": 0,
            "callback_no_answer_total": 0,
            "callback_retry_total": 0,
            "callback_rescheduled_total": 0,
            "callback_latency_seconds": 0.0,
            "callback_dial_duration_seconds": 0.0,
        }

    def record_created(self, callback_id: str, scheduled_at_utc: str):
        self.stats["callback_created_total"] += 1
        logger.info(f"[METRICS][CALLBACK_CREATED] id={callback_id} scheduled_at={scheduled_at_utc}")

    def record_success(self, callback_id: str, duration_seconds: float = 0.0):
        self.stats["callback_success_total"] += 1
        self.stats["callback_dial_duration_seconds"] = round(duration_seconds, 2)
        logger.info(f"[METRICS][CALLBACK_SUCCESS] id={callback_id} duration_s={duration_seconds:.1f}")

    def record_failed(self, callback_id: str, reason: str = ""):
        self.stats["callback_failed_total"] += 1
        logger.warning(f"[METRICS][CALLBACK_FAILED] id={callback_id} reason='{reason}'")

    def record_no_answer(self, callback_id: str):
        self.stats["callback_no_answer_total"] += 1
        logger.info(f"[METRICS][CALLBACK_NO_ANSWER] id={callback_id}")

    def record_retry(self, callback_id: str, attempt: int):
        self.stats["callback_retry_total"] += 1
        logger.info(f"[METRICS][CALLBACK_RETRY_SCHEDULED] id={callback_id} attempt={attempt}")

    def record_cancelled(self, callback_id: str):
        self.stats["callback_cancelled_total"] += 1
        logger.info(f"[METRICS][CALLBACK_CANCELLED] id={callback_id}")

    def record_rescheduled(self, callback_id: str):
        self.stats["callback_rescheduled_total"] += 1
        logger.info(f"[METRICS][CALLBACK_RESCHEDULED] id={callback_id}")

    def get_summary(self) -> Dict[str, Any]:
        return dict(self.stats)


callback_metrics = CallbackMetrics()
