from typing import Dict, Any
from app.utils.logging import logger


class ToolMetrics:
    """Metrics tracking for web search and fetch tools."""

    def __init__(self):
        self.stats: Dict[str, Any] = {
            "web_search_latency_ms": 0.0,
            "web_fetch_latency_ms": 0.0,
            "tool_success_count": 0,
            "tool_failure_count": 0,
            "search_count": 0,
            "fetch_count": 0,
        }

    def record_tool_start(self, tool_name: str, query_or_url: str):
        """Logs TOOL_CALL_STARTED."""
        logger.info(f"[METRICS][TOOL_CALL_STARTED] tool={tool_name} target='{query_or_url[:100]}'")

    def record_tool_completed(
        self,
        tool_name: str,
        duration_ms: float,
        result_count: int = 0,
        success: bool = True,
        error: str = "",
    ):
        """Logs TOOL_CALL_COMPLETED or TOOL_CALL_FAILED and updates internal counters."""
        if success:
            self.stats["tool_success_count"] += 1
            if tool_name == "web_search":
                self.stats["search_count"] += 1
                self.stats["web_search_latency_ms"] = round(duration_ms, 2)
            elif tool_name == "web_fetch":
                self.stats["fetch_count"] += 1
                self.stats["web_fetch_latency_ms"] = round(duration_ms, 2)

            logger.info(
                f"[METRICS][TOOL_CALL_COMPLETED] tool={tool_name} duration_ms={duration_ms:.1f} result_count={result_count} success=True"
            )
        else:
            self.stats["tool_failure_count"] += 1
            logger.warning(
                f"[METRICS][TOOL_CALL_FAILED] tool={tool_name} duration_ms={duration_ms:.1f} error='{error}' success=False"
            )

    def get_summary(self) -> Dict[str, Any]:
        """Returns snapshot of current metrics."""
        return dict(self.stats)


tool_metrics = ToolMetrics()
