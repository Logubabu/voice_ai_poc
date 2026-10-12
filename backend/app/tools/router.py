import asyncio
import hashlib
import json
import time
from typing import Dict, Any, List, Optional, Callable

from app.config import config
from app.tools.base import BaseTool
from app.tools.registry import global_tool_registry, ToolRegistry
from app.tools.executor import tool_executor
from app.utils.logging import logger
from app.utils.audit import audit_logger


class TurnTracker:
    """Tracks tool call counts, duplicate queries, execution state, and cached results within a single conversational turn."""

    def __init__(self, max_calls_per_turn: int = 3):
        self.max_calls = max_calls_per_turn
        self.call_count = 0
        self.turn_history: List[str] = []
        self.turn_results: Dict[str, Dict[str, Any]] = {}

    def can_call(self) -> bool:
        return self.call_count < self.max_calls

    def record_call(self, tool_name: str, args: Dict[str, Any]) -> str:
        self.call_count += 1
        fingerprint_str = f"{tool_name}:{json.dumps(args, sort_keys=True)}"
        fingerprint = hashlib.md5(fingerprint_str.encode("utf-8")).hexdigest()
        self.turn_history.append(fingerprint)
        return fingerprint

    def record_result(self, tool_name: str, args: Dict[str, Any], result: Dict[str, Any]):
        fingerprint_str = f"{tool_name}:{json.dumps(args, sort_keys=True)}"
        fingerprint = hashlib.md5(fingerprint_str.encode("utf-8")).hexdigest()
        self.turn_results[fingerprint] = result

    def is_duplicate(self, tool_name: str, args: Dict[str, Any]) -> bool:
        fingerprint_str = f"{tool_name}:{json.dumps(args, sort_keys=True)}"
        fingerprint = hashlib.md5(fingerprint_str.encode("utf-8")).hexdigest()
        return fingerprint in self.turn_history

    def get_cached_result(self, tool_name: str, args: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        fingerprint_str = f"{tool_name}:{json.dumps(args, sort_keys=True)}"
        fingerprint = hashlib.md5(fingerprint_str.encode("utf-8")).hexdigest()
        return self.turn_results.get(fingerprint)

    def reset(self):
        self.call_count = 0
        self.turn_history.clear()
        self.turn_results.clear()


class ToolRouter:
    """Central Tool Router managing tool authorization, turn limits, duplicate prevention, barge-in cancellation, and DataChannel events."""

    def __init__(self, registry: Optional[ToolRegistry] = None):
        self.registry = registry or global_tool_registry
        self.session_turns: Dict[str, TurnTracker] = {}
        self.session_call_counts: Dict[str, int] = {}
        self.active_tool_tasks: Dict[str, Dict[str, asyncio.Task]] = {}
        self.completed_tool_calls: Dict[str, Dict[str, Dict[str, Any]]] = {}

    def get_turn_tracker(self, session_id: str) -> TurnTracker:
        if session_id not in self.session_turns:
            max_turn = getattr(config, "MAX_TOOL_CALLS_PER_TURN", 3)
            self.session_turns[session_id] = TurnTracker(max_calls_per_turn=max_turn)
        return self.session_turns[session_id]

    def reset_turn(self, session_id: str):
        """Resets single-turn tool counters when a new user turn starts."""
        if session_id in self.session_turns:
            self.session_turns[session_id].reset()

    def cancel_pending_tools(self, session_id: str) -> int:
        """Cancels all in-flight tool execution tasks for a session (e.g. on user barge-in / interruption)."""
        cancelled_count = 0
        tasks_map = self.active_tool_tasks.get(session_id, {})
        for tool_call_id, task in list(tasks_map.items()):
            if task and not task.done():
                task.cancel()
                cancelled_count += 1
                logger.warning(f"[TOOL-ROUTER][BARGE-IN] Cancelled pending tool call task '{tool_call_id}' for session '{session_id}'")
        tasks_map.clear()
        return cancelled_count

    def broadcast_to_session(self, session_id: Optional[str], event: dict):
        """Sends DataChannel UI updates to browser WebCall sessions."""
        try:
            from app.pipeline import pipeline_manager
            target_sessions = []
            if session_id and session_id in pipeline_manager.active_sessions:
                target_sessions.append(pipeline_manager.active_sessions[session_id])
            else:
                target_sessions = list(pipeline_manager.active_sessions.values())

            for sess in target_sessions:
                conn = sess.get("connection")
                if conn and hasattr(conn, "send_app_message"):
                    try:
                        conn.send_app_message(event)
                    except Exception as e:
                        logger.warning(f"[TOOL-ROUTER] Notice sending app message: {e}")
        except Exception as e:
            logger.warning(f"[TOOL-ROUTER] Notice broadcasting event: {e}")

    def create_handler(self, tool: BaseTool) -> Callable:
        """Creates Pipecat-compatible tool execution handler callback supporting FunctionCallParams, positional, and keyword args."""
        async def _handler(*args_pos, **kwargs):
            import inspect
            session_id = "default_webcall"
            result_callback = None
            tool_name = tool.name
            tool_call_id = "call_default"
            tool_args = {}

            if len(args_pos) == 1 and hasattr(args_pos[0], "function_name"):
                params = args_pos[0]
                tool_name = getattr(params, "function_name", tool.name)
                tool_call_id = getattr(params, "tool_call_id", "call_default")
                tool_args = dict(getattr(params, "arguments", {}) or {})
                llm = getattr(params, "llm", None)
                session_id = getattr(llm, "session_id", session_id)
                result_callback = getattr(params, "result_callback", None)
            elif len(args_pos) >= 3:
                tool_name = str(args_pos[0])
                tool_call_id = str(args_pos[1])
                tool_args = dict(args_pos[2] or {})
                if len(args_pos) > 3 and hasattr(args_pos[3], "session_id"):
                    session_id = getattr(args_pos[3], "session_id", session_id)
                if len(args_pos) >= 6:
                    result_callback = args_pos[5]
            else:
                tool_name = kwargs.get("function_name", tool.name)
                tool_call_id = kwargs.get("tool_call_id", "call_default")
                tool_args = dict(kwargs.get("args", kwargs.get("arguments", {})) or {})
                llm = kwargs.get("llm")
                session_id = getattr(llm, "session_id", session_id) if llm else kwargs.get("session_id", session_id)
                result_callback = kwargs.get("result_callback")

            res = await self.route_tool_call(
                tool_name=tool_name,
                tool_call_id=tool_call_id,
                args=tool_args,
                session_id=session_id,
            )

            if result_callback:
                try:
                    res_ret = result_callback(res)
                    if inspect.isawaitable(res_ret):
                        await res_ret
                except Exception as e:
                    logger.warning(f"[TOOL-ROUTER] Notice executing result_callback: {e}")

            return res

        return _handler

    async def route_tool_call(
        self,
        tool_name: str,
        tool_call_id: str,
        args: Dict[str, Any],
        session_id: str = "default_session",
    ) -> Dict[str, Any]:
        """Central tool call routing & execution pipeline."""
        start_time = time.time()
        logger.info(f"[TOOL-ROUTER] Routing tool call '{tool_name}' (id: {tool_call_id}, session: {session_id})")

        # 1. Feature Flag Check
        if not getattr(config, "WEBCALL_TOOL_CALLING_ENABLED", True):
            logger.warning("[TOOL-ROUTER][REJECT] Tool calling disabled by WEBCALL_TOOL_CALLING_ENABLED=false")
            return {
                "tool": tool_name,
                "success": False,
                "error": "Tool calling is disabled.",
                "message": "Tool calling feature is currently disabled.",
            }

        # 2. Tool Authorization / Registry Validation
        target_tool = self.registry.get_tool(tool_name)
        if not target_tool:
            logger.error(f"[TOOL-ROUTER][SECURITY-REJECT] Unregistered tool request: '{tool_name}'")
            audit_logger.log_event(
                event="TOOL_CALL_REJECTED",
                category="security",
                session_id=session_id,
                actor="llm",
                action=tool_name,
                details={"reason": "Unregistered tool name", "args": args},
                status="BLOCKED",
            )
            return {
                "tool": tool_name,
                "success": False,
                "error": f"Tool '{tool_name}' is not registered or authorized.",
                "message": f"Execution of unregistered tool '{tool_name}' was blocked for security reasons.",
            }

        # 3. Argument Validation & Sanitization
        clean_args = self._validate_args(tool_name, args)

        # Inject active session tenant_id and knowledge_base_id if available
        try:
            from app.pipeline import pipeline_manager
            sess_info = pipeline_manager.active_sessions.get(session_id, {})
            if "tenant_id" not in clean_args and sess_info.get("tenant_id"):
                clean_args["tenant_id"] = sess_info["tenant_id"]
            if "knowledge_base_id" not in clean_args and sess_info.get("knowledge_base_id"):
                clean_args["knowledge_base_id"] = sess_info["knowledge_base_id"]
        except Exception:
            pass

        # 3.5. Idempotency Check per (session_id, tool_call_id)
        if session_id in self.completed_tool_calls and tool_call_id in self.completed_tool_calls[session_id]:
            logger.info(f"[TOOL-ROUTER][IDEMPOTENCY] Tool call '{tool_call_id}' already executed for session '{session_id}'. Returning cached result.")
            return self.completed_tool_calls[session_id][tool_call_id]

        # 4. Turn Limit Enforcement (MAX_TOOL_CALLS_PER_TURN)
        tracker = self.get_turn_tracker(session_id)
        if not tracker.can_call():
            max_limit = getattr(config, "MAX_TOOL_CALLS_PER_TURN", 3)
            logger.warning(f"[TOOL-ROUTER][TURN-LIMIT] Exceeded MAX_TOOL_CALLS_PER_TURN ({max_limit}) for session '{session_id}'")
            return {
                "tool": tool_name,
                "success": False,
                "error": "Turn tool call limit reached.",
                "message": f"Maximum tool call limit of {max_limit} reached for this turn.",
            }

        # 5. Session Rate Limit Enforcement (MAX_WEB_SEARCHES_PER_SESSION)
        sess_calls = self.session_call_counts.get(session_id, 0)
        max_sess_limit = getattr(config, "MAX_WEB_SEARCHES_PER_SESSION", 20)
        if sess_calls >= max_sess_limit:
            logger.warning(f"[TOOL-ROUTER][SESSION-LIMIT] Exceeded MAX_WEB_SEARCHES_PER_SESSION ({max_sess_limit}) for session '{session_id}'")
            return {
                "tool": tool_name,
                "success": False,
                "error": "Session tool call quota exceeded.",
                "message": "Maximum tool call limit for this conversation session reached.",
            }

        # 6. Duplicate Call Prevention within turn (preserves cached tool results)
        if tracker.is_duplicate(tool_name, clean_args):
            logger.info(f"[TOOL-ROUTER][DUPLICATE] Detected duplicate tool call in same turn: '{tool_name}' args={clean_args}")
            cached_res = tracker.get_cached_result(tool_name, clean_args)
            if cached_res:
                res_copy = dict(cached_res)
                res_copy["duplicate"] = True
                return res_copy
            return {
                "tool": tool_name,
                "success": True,
                "found": False,
                "duplicate": True,
                "message": "Duplicate query already processed in this turn.",
                "results": [],
            }

        # Record call in tracker
        tracker.record_call(tool_name, clean_args)
        self.session_call_counts[session_id] = sess_calls + 1

        # Broadcast UI state -> searching
        timestamp_str = time.strftime("%I:%M %p")
        self.broadcast_to_session(session_id, {"type": "state", "state": "searching"})

        # 7. Execute Tool asynchronously with task cancellation handle
        try:
            current_task = asyncio.current_task()
            if session_id not in self.active_tool_tasks:
                self.active_tool_tasks[session_id] = {}
            if current_task:
                self.active_tool_tasks[session_id][tool_call_id] = current_task

            result = await tool_executor.execute_tool(
                tool=target_tool,
                tool_call_id=tool_call_id,
                args=clean_args,
                session_id=session_id,
            )

            duration_ms = (time.time() - start_time) * 1000
            logger.info(f"[TOOL-ROUTER] Tool '{tool_name}' executed in {duration_ms:.1f}ms (success={result.get('success')})")

            # Store result in turn tracker and completed_tool_calls map for idempotency
            tracker.record_result(tool_name, clean_args, result)
            if session_id not in self.completed_tool_calls:
                self.completed_tool_calls[session_id] = {}
            self.completed_tool_calls[session_id][tool_call_id] = result

            # Broadcast tool call event and sources to browser DataChannel
            event_payload = {
                "type": "tool_call",
                "tool_name": tool_name,
                "args": clean_args,
                "result": result,
                "timestamp": timestamp_str,
            }
            self.broadcast_to_session(session_id, event_payload)
            self.broadcast_to_session(session_id, {"type": "state", "state": "processing"})

            return result

        except asyncio.CancelledError:
            logger.warning(f"[TOOL-ROUTER][BARGE-IN-CANCEL] Execution of '{tool_name}' cancelled due to user interruption")
            return {
                "tool": tool_name,
                "success": False,
                "cancelled": True,
                "error": "Tool execution cancelled by user interruption.",
            }

        except Exception as e:
            duration_ms = (time.time() - start_time) * 1000
            logger.exception(f"[TOOL-ROUTER][ERROR] Tool '{tool_name}' execution error after {duration_ms:.1f}ms: {e}")
            fallback_res = {
                "tool": tool_name,
                "success": False,
                "error": str(e),
                "message": "Tool execution failed. Responding based on general knowledge.",
            }
            self.broadcast_to_session(session_id, {"type": "tool_call", "tool_name": tool_name, "args": clean_args, "result": fallback_res, "timestamp": timestamp_str})
            self.broadcast_to_session(session_id, {"type": "state", "state": "processing"})
            return fallback_res

        finally:
            if session_id in self.active_tool_tasks:
                self.active_tool_tasks[session_id].pop(tool_call_id, None)

    def _validate_args(self, tool_name: str, args: Dict[str, Any]) -> Dict[str, Any]:
        """Validates and sanitizes tool arguments."""
        clean = dict(args)
        if "query" in clean and isinstance(clean["query"], str):
            clean["query"] = clean["query"][:500].strip()
        if "max_results" in clean:
            try:
                clean["max_results"] = max(1, min(10, int(clean["max_results"])))
            except (ValueError, TypeError):
                clean["max_results"] = 5
        return clean


tool_router = ToolRouter()
