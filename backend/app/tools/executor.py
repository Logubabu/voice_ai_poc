import asyncio
import time
from typing import Dict, Any, Optional
from app.tools.base import BaseTool
from app.utils.logging import logger
from app.utils.audit import audit_logger


class ToolExecutor:
    """Async executor managing tool invocation timeouts, barge-in cancellation, and structured result truncation."""

    def __init__(self):
        self.active_tasks: Dict[str, asyncio.Task] = {}

    async def execute_tool(
        self,
        tool: BaseTool,
        tool_call_id: str,
        args: Dict[str, Any],
        session_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Executes a tool asynchronously with a strict per-tool timeout and cancellation handle."""
        start_time = time.time()
        logger.info(f"[TOOL-EXECUTOR] Starting execution of tool '{tool.name}' (id: {tool_call_id})")

        async def _run():
            return await tool.execute(args)

        task = asyncio.create_task(_run())
        self.active_tasks[tool_call_id] = task

        try:
            result = await asyncio.wait_for(task, timeout=tool.timeout)
            duration_ms = (time.time() - start_time) * 1000

            is_success = bool(result.get("success", True)) if isinstance(result, dict) else True

            audit_logger.log_event(
                event="TOOL_EXECUTION",
                category="tool_calling",
                session_id=session_id,
                actor="llm",
                action=tool.name,
                details={"tool_call_id": tool_call_id, "args": args, "result": result},
                status="SUCCESS" if is_success else "FAILED",
                duration_ms=duration_ms,
            )

            return result

        except asyncio.TimeoutError:
            duration_ms = (time.time() - start_time) * 1000
            logger.error(f"[TOOL-EXECUTOR][TIMEOUT] Tool '{tool.name}' timed out after {duration_ms:.1f}ms")
            audit_logger.log_event(
                event="TOOL_EXECUTION_TIMEOUT",
                category="tool_calling",
                session_id=session_id,
                actor="llm",
                action=tool.name,
                details={"tool_call_id": tool_call_id, "args": args},
                status="FAILED",
                duration_ms=duration_ms,
            )
            return {"success": False, "error": f"Tool execution for '{tool.name}' timed out."}

        except asyncio.CancelledError:
            duration_ms = (time.time() - start_time) * 1000
            logger.warning(f"[TOOL-EXECUTOR][BARGE-IN-CANCEL] Tool '{tool.name}' cancelled due to user interruption")
            audit_logger.log_event(
                event="TOOL_EXECUTION_CANCELLED",
                category="tool_calling",
                session_id=session_id,
                actor="user",
                action=tool.name,
                details={"tool_call_id": tool_call_id},
                status="BLOCKED",
                duration_ms=duration_ms,
            )
            raise

        finally:
            self.active_tasks.pop(tool_call_id, None)

    def cancel_tool_call(self, tool_call_id: str) -> bool:
        """Cancels a running tool call (e.g. on user barge-in / interruption)."""
        task = self.active_tasks.pop(tool_call_id, None)
        if task and not task.done():
            task.cancel()
            logger.info(f"[TOOL-EXECUTOR] Cancelled running tool call task '{tool_call_id}'")
            return True
        return False


tool_executor = ToolExecutor()
