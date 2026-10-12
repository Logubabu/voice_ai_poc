from typing import Dict, Any
from app.callbacks.service import callback_service
from app.callbacks.models import (
    CallbackCreateRequest,
    CallbackRescheduleRequest,
    CallbackCancelRequest,
)
from app.tools.base import BaseTool
from pipecat.adapters.schemas.function_schema import FunctionSchema


# --- BaseTool Subclasses ---

class ScheduleCallbackTool(BaseTool):
    """Tool for scheduling automated voice callbacks."""
    def __init__(self):
        super().__init__(
            name="schedule_callback",
            description="Schedule an automated voice callback to call the user at a specified natural language future time (e.g., 'tomorrow at 3 PM', 'in 30 minutes', 'next Monday morning'). Use this tool whenever the user requests a callback.",
            permissions="public",
        )

    def get_schema(self, handler: Any = None) -> FunctionSchema:
        return FunctionSchema(
            name=self.name,
            description=self.description,
            properties={
                "phone_number": {
                    "type": "string",
                    "description": "User recipient phone number in E.164 format (e.g. +919876543210 or 10-digit number)."
                },
                "requested_time": {
                    "type": "string",
                    "description": "The natural language callback time requested by user (e.g., 'tomorrow at 3 PM', 'in 30 minutes', 'next Monday at 10 AM'). DO NOT generate unix timestamps."
                },
                "timezone": {
                    "type": "string",
                    "description": "User IANA timezone string (defaults to 'Asia/Kolkata' if unstated)."
                },
                "reason": {
                    "type": "string",
                    "description": "Brief reason for scheduling the callback."
                },
                "customer_name": {
                    "type": "string",
                    "description": "User's full name if provided in conversation."
                },
                "callback_context": {
                    "type": "string",
                    "description": "Key conversation summary context to preserve for the AI during the outbound callback."
                }
            },
            required=["phone_number", "requested_time"],
            handler=handler,
        )

    async def execute(self, args: Dict[str, Any]) -> Dict[str, Any]:
        req = CallbackCreateRequest(
            phone_number=args.get("phone_number", ""),
            requested_time=args.get("requested_time", ""),
            timezone=args.get("timezone", "Asia/Kolkata"),
            reason=args.get("reason", "Customer requested callback"),
            customer_name=args.get("customer_name", "Valued Customer"),
            conversation_id=args.get("conversation_id", ""),
            callback_context=args.get("callback_context", ""),
            tenant_id=args.get("tenant_id", "default_tenant"),
        )
        res = await callback_service.schedule_callback(req)
        return res.model_dump()


class RescheduleCallbackTool(BaseTool):
    """Tool for rescheduling existing voice callbacks."""
    def __init__(self):
        super().__init__(
            name="reschedule_callback",
            description="Reschedule an existing scheduled voice callback to a new requested date/time.",
            permissions="public",
        )

    def get_schema(self, handler: Any = None) -> FunctionSchema:
        return FunctionSchema(
            name=self.name,
            description=self.description,
            properties={
                "callback_id": {
                    "type": "string",
                    "description": "Callback ID, phone number, or conversation ID to reschedule."
                },
                "new_requested_time": {
                    "type": "string",
                    "description": "The new natural language time (e.g., 'tomorrow at 5 PM')."
                },
                "timezone": {
                    "type": "string",
                    "description": "IANA timezone string."
                }
            },
            required=["callback_id", "new_requested_time"],
            handler=handler,
        )

    async def execute(self, args: Dict[str, Any]) -> Dict[str, Any]:
        req = CallbackRescheduleRequest(
            new_requested_time=args.get("new_requested_time", ""),
            timezone=args.get("timezone"),
        )
        res = await callback_service.reschedule_callback(args.get("callback_id", ""), req)
        return res.model_dump()


class CancelCallbackTool(BaseTool):
    """Tool for cancelling existing voice callbacks."""
    def __init__(self):
        super().__init__(
            name="cancel_callback",
            description="Cancel an existing scheduled voice callback.",
            permissions="public",
        )

    def get_schema(self, handler: Any = None) -> FunctionSchema:
        return FunctionSchema(
            name=self.name,
            description=self.description,
            properties={
                "callback_id": {
                    "type": "string",
                    "description": "Callback ID, phone number, or conversation ID to cancel."
                },
                "reason": {
                    "type": "string",
                    "description": "Reason for cancellation."
                }
            },
            required=["callback_id"],
            handler=handler,
        )

    async def execute(self, args: Dict[str, Any]) -> Dict[str, Any]:
        req = CallbackCancelRequest(reason=args.get("reason", "Cancelled by user"))
        res = await callback_service.cancel_callback(args.get("callback_id", ""), req)
        return res.model_dump()


class GetCallbackStatusTool(BaseTool):
    """Tool for checking status of a voice callback."""
    def __init__(self):
        super().__init__(
            name="get_callback_status",
            description="Check current status and scheduled time of a voice callback.",
            permissions="public",
        )

    def get_schema(self, handler: Any = None) -> FunctionSchema:
        return FunctionSchema(
            name=self.name,
            description=self.description,
            properties={
                "callback_id": {
                    "type": "string",
                    "description": "Callback ID, phone number, or conversation ID to query."
                }
            },
            required=["callback_id"],
            handler=handler,
        )

    async def execute(self, args: Dict[str, Any]) -> Dict[str, Any]:
        res = await callback_service.get_callback_status(args.get("callback_id", ""))
        return res.model_dump()


# --- Direct Handler Functions ---

async def handle_schedule_callback(function_name: str, tool_call_id: str, args: Dict[str, Any], llm: Any, context: Any, result_callback: Any):
    tool = ScheduleCallbackTool()
    res_dict = await tool.execute(args)
    try:
        from app.services.tools import broadcast_tool_call
        broadcast_tool_call("schedule_callback", args, res_dict)
    except Exception:
        pass
    await result_callback(res_dict)


async def handle_reschedule_callback(function_name: str, tool_call_id: str, args: Dict[str, Any], llm: Any, context: Any, result_callback: Any):
    tool = RescheduleCallbackTool()
    res_dict = await tool.execute(args)
    try:
        from app.services.tools import broadcast_tool_call
        broadcast_tool_call("reschedule_callback", args, res_dict)
    except Exception:
        pass
    await result_callback(res_dict)


async def handle_cancel_callback(function_name: str, tool_call_id: str, args: Dict[str, Any], llm: Any, context: Any, result_callback: Any):
    tool = CancelCallbackTool()
    res_dict = await tool.execute(args)
    try:
        from app.services.tools import broadcast_tool_call
        broadcast_tool_call("cancel_callback", args, res_dict)
    except Exception:
        pass
    await result_callback(res_dict)


async def handle_get_callback_status(function_name: str, tool_call_id: str, args: Dict[str, Any], llm: Any, context: Any, result_callback: Any):
    tool = GetCallbackStatusTool()
    res_dict = await tool.execute(args)
    try:
        from app.services.tools import broadcast_tool_call
        broadcast_tool_call("get_callback_status", args, res_dict)
    except Exception:
        pass
    await result_callback(res_dict)
