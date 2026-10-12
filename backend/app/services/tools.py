from typing import Any, Dict, Callable
from app.utils.logging import logger
from app.services.audio_processor import audio_processor_factory
from app.services.freeswitch_esl import freeswitch_esl_service

import time

# In-memory mock database for tool call demonstrations
MOCK_DATABASE = {
    "orders": {
        "ORD-101": {"status": "Shipped", "item": "Voice AI Hardware Kit", "delivery_date": "Tomorrow, 2:00 PM", "carrier": "FedEx"},
        "ORD-102": {"status": "Processing", "item": "Smart Speaker Hub", "delivery_date": "Friday", "carrier": "UPS"},
    },
    "customers": {
        "9876543210": {"name": "Loganathan R", "plan": "PRO Voice AI", "vip": True},
        "1234567890": {"name": "Alex Johnson", "plan": "Enterprise Voice AI", "vip": True},
        "default": {"name": "Valued Customer", "plan": "Standard", "vip": False}
    },
    "appointments": []
}

TOOL_CALL_HISTORY = []


def broadcast_tool_call(tool_name: str, args: dict, result: dict):
    """Broadcasts tool call execution event over active DataChannels and logs to history."""
    try:
        from app.pipeline import pipeline_manager
        timestamp = time.strftime("%I:%M %p")
        event = {
            "type": "tool_call",
            "tool_name": tool_name,
            "args": args,
            "result": result,
            "timestamp": timestamp,
        }
        TOOL_CALL_HISTORY.append(event)
        if len(TOOL_CALL_HISTORY) > 50:
            TOOL_CALL_HISTORY.pop(0)

        for session_id, session in list(pipeline_manager.active_sessions.items()):
            conn = session.get("connection")
            if conn and hasattr(conn, "send_app_message"):
                try:
                    conn.send_app_message(event)
                    logger.info(f"[TOOL-REGISTRY] Broadcasted tool_call event '{tool_name}' to browser connection")
                except Exception as e:
                    logger.warning(f"[TOOL-REGISTRY] Notice broadcasting tool_call: {e}")
    except Exception as e:
        logger.warning(f"[TOOL-REGISTRY] Notice in broadcast_tool_call: {e}")


# --- Tool Handlers ---

async def handle_check_order_status(function_name: str, tool_call_id: str, args: Dict[str, Any], llm: Any, context: Any, result_callback: Callable):
    """Tool Handler: Checks order status in database."""
    order_id = args.get("order_id", "").upper().strip()
    logger.info(f"[TOOL-REGISTRY] Executing check_order_status for order_id: {order_id}")
    
    order = MOCK_DATABASE["orders"].get(order_id)
    if order:
        result = {
            "success": True,
            "order_id": order_id,
            "status": order["status"],
            "item": order["item"],
            "estimated_delivery": order["delivery_date"],
            "carrier": order["carrier"]
        }
    else:
        result = {
            "success": False,
            "order_id": order_id,
            "message": f"Order ID {order_id} was not found. Valid IDs for testing include ORD-101 and ORD-102."
        }
    
    logger.info(f"[TOOL-REGISTRY] check_order_status result: {result}")
    broadcast_tool_call("check_order_status", args, result)
    await result_callback(result)


async def handle_get_customer_info(function_name: str, tool_call_id: str, args: Dict[str, Any], llm: Any, context: Any, result_callback: Callable):
    """Tool Handler: Looks up CRM customer info."""
    phone = args.get("phone", "default")
    logger.info(f"[TOOL-REGISTRY] Executing get_customer_info for phone: {phone}")
    
    info = MOCK_DATABASE["customers"].get(phone, MOCK_DATABASE["customers"]["default"])
    result = {"success": True, "customer": info}
    logger.info(f"[TOOL-REGISTRY] get_customer_info result: {result}")
    broadcast_tool_call("get_customer_info", args, result)
    await result_callback(result)


async def handle_transfer_call(function_name: str, tool_call_id: str, args: Dict[str, Any], llm: Any, context: Any, result_callback: Callable):
    """Tool Handler: Triggers FreeSWITCH / Telephony call transfer."""
    department = args.get("department", "Support")
    reason = args.get("reason", "Customer requested escalation")
    logger.info(f"[TOOL-REGISTRY] Executing transfer_call to department: {department} ({reason})")
    
    # Also notify FreeSWITCH ESL service
    esl_res = freeswitch_esl_service.execute_esl_command("uuid_transfer", f"channel-webcall-01 {department.lower()}_queue")
    
    result = {
        "success": True,
        "action": "TELEPHONY_TRANSFER",
        "department": department,
        "transfer_target": f"SIP/freeswitch/{department.lower()}_queue",
        "esl_status": esl_res["body"],
        "message": f"Transferring your call to the {department} team. Please hold."
    }
    logger.info(f"[TOOL-REGISTRY] transfer_call result: {result}")
    broadcast_tool_call("transfer_call", args, result)
    await result_callback(result)


async def handle_book_appointment(function_name: str, tool_call_id: str, args: Dict[str, Any], llm: Any, context: Any, result_callback: Callable):
    """Tool Handler: Schedules appointment in database."""
    date = args.get("date")
    time_slot = args.get("time_slot")
    service = args.get("service_type", "Voice AI Consultation")
    logger.info(f"[TOOL-REGISTRY] Executing book_appointment for {date} at {time_slot}")
    
    appt = {"id": f"APT-{len(MOCK_DATABASE['appointments'])+1:03d}", "date": date, "time": time_slot, "service": service}
    MOCK_DATABASE["appointments"].append(appt)
    
    result = {"success": True, "appointment": appt, "message": f"Appointment booked successfully for {date} at {time_slot}."}
    logger.info(f"[TOOL-REGISTRY] book_appointment result: {result}")
    broadcast_tool_call("book_appointment", args, result)
    await result_callback(result)


async def handle_set_noise_cancellation(function_name: str, tool_call_id: str, args: Dict[str, Any], llm: Any, context: Any, result_callback: Callable):
    """Tool Handler: Switches active noise cancellation algorithm (Passthrough, WebRTC APM, RNNoise, DeepFilterNet)."""
    filter_name = args.get("filter_name", "DeepFilterNet")
    logger.info(f"[TOOL-REGISTRY] Executing set_noise_cancellation with filter: '{filter_name}'")
    
    active_filter = audio_processor_factory.set_active_filter(filter_name)
    # Also notify FreeSWITCH ESL
    freeswitch_esl_service.execute_esl_command("noise_cancel", active_filter.display_name)
    
    result = {
        "success": True,
        "currently_running_filter": active_filter.display_name,
        "filter_type": active_filter.filter_type,
        "description": active_filter.description,
        "message": f"Noise cancellation filter updated to '{active_filter.display_name}'."
    }
    logger.info(f"[TOOL-REGISTRY] set_noise_cancellation result: {result}")
    broadcast_tool_call("set_noise_cancellation", args, result)
    await result_callback(result)


async def handle_freeswitch_esl_command(function_name: str, tool_call_id: str, args: Dict[str, Any], llm: Any, context: Any, result_callback: Callable):
    """Tool Handler: Executes FreeSWITCH ESL commands (uuid_transfer, uuid_setvar, status, originate, etc)."""
    command = args.get("command", "status")
    command_args = args.get("args", "")
    logger.info(f"[TOOL-REGISTRY] Executing freeswitch_esl_command: {command} {command_args}")
    
    esl_result = freeswitch_esl_service.execute_esl_command(command, command_args)
    result = {
        "success": esl_result["success"],
        "command": command,
        "args": command_args,
        "response": esl_result["body"],
        "message": f"FreeSWITCH ESL command executed: {esl_result['body']}"
    }
    logger.info(f"[TOOL-REGISTRY] freeswitch_esl_command result: {result}")
    broadcast_tool_call("freeswitch_esl_command", args, result)
    await result_callback(result)


async def handle_get_audio_processor_status(function_name: str, tool_call_id: str, args: Dict[str, Any], llm: Any, context: Any, result_callback: Callable):
    """Tool Handler: Gets current running noise cancellation filter and audio loop metrics."""
    logger.info("[TOOL-REGISTRY] Executing get_audio_processor_status")
    status = audio_processor_factory.get_active_filter_status()
    esl_status = freeswitch_esl_service.get_status()
    
    result = {
        "success": True,
        "currently_running_noise_cancellation": status["current_running_filter"],
        "description": status["description"],
        "stats": status["stats"],
        "freeswitch_esl": {
            "connected": esl_status["esl_connected"],
            "channels": len(esl_status["channels"]),
        },
        "message": f"Currently running noise cancellation filter is '{status['current_running_filter']}'."
    }
    logger.info(f"[TOOL-REGISTRY] get_audio_processor_status result: {result}")
    broadcast_tool_call("get_audio_processor_status", args, result)
    await result_callback(result)


class VoiceToolRegistry:
    """Central registry holding tool definitions and execution dispatch logic."""

    def __init__(self):
        self.tools = {}
        self._register_default_tools()

    def _register_default_tools(self):
        from app.services.search.tools import WEB_SEARCH_SCHEMA, WEB_FETCH_SCHEMA, handle_web_search, handle_web_fetch

        self.tools["web_search"] = {
            "schema": WEB_SEARCH_SCHEMA,
            "definition": {
                "type": "function",
                "function": {
                    "name": "web_search",
                    "description": WEB_SEARCH_SCHEMA.description,
                    "parameters": {
                        "type": "object",
                        "properties": WEB_SEARCH_SCHEMA.properties,
                        "required": WEB_SEARCH_SCHEMA.required,
                    }
                }
            },
            "handler": handle_web_search,
        }

        self.tools["web_fetch"] = {
            "schema": WEB_FETCH_SCHEMA,
            "definition": {
                "type": "function",
                "function": {
                    "name": "web_fetch",
                    "description": WEB_FETCH_SCHEMA.description,
                    "parameters": {
                        "type": "object",
                        "properties": WEB_FETCH_SCHEMA.properties,
                        "required": WEB_FETCH_SCHEMA.required,
                    }
                }
            },
            "handler": handle_web_fetch,
        }

        self.tools["check_order_status"] = {
            "definition": {
                "type": "function",
                "function": {
                    "name": "check_order_status",
                    "description": "Look up tracking details, delivery status, and item info for a customer order ID (e.g. ORD-101).",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "order_id": {"type": "string", "description": "The customer order ID to check (e.g. ORD-101, ORD-102)"}
                        },
                        "required": ["order_id"]
                    }
                }
            },
            "handler": handle_check_order_status
        }

        self.tools["get_customer_info"] = {
            "definition": {
                "type": "function",
                "function": {
                    "name": "get_customer_info",
                    "description": "Retrieve customer account profile and subscription status.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "phone": {"type": "string", "description": "Customer phone number"}
                        },
                        "required": []
                    }
                }
            },
            "handler": handle_get_customer_info
        }

        self.tools["transfer_call"] = {
            "definition": {
                "type": "function",
                "function": {
                    "name": "transfer_call",
                    "description": "Transfer the live voice call or FreeSWITCH SIP session to a human agent department.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "department": {"type": "string", "description": "Department name (e.g., Billing, Technical Support, Sales)"},
                            "reason": {"type": "string", "description": "Brief reason for escalation"}
                        },
                        "required": ["department"]
                    }
                }
            },
            "handler": handle_transfer_call
        }

        self.tools["book_appointment"] = {
            "definition": {
                "type": "function",
                "function": {
                    "name": "book_appointment",
                    "description": "Schedule a consultation or service appointment.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "date": {"type": "string", "description": "Date of appointment (e.g. 2026-10-10)"},
                            "time_slot": {"type": "string", "description": "Time slot (e.g. 10:00 AM)"},
                            "service_type": {"type": "string", "description": "Service or consultation type"}
                        },
                        "required": ["date", "time_slot"]
                    }
                }
            },
            "handler": handle_book_appointment
        }

        self.tools["set_noise_cancellation"] = {
            "definition": {
                "type": "function",
                "function": {
                    "name": "set_noise_cancellation",
                    "description": "Switch active noise cancellation filter. Options: Passthrough, WebRTC APM, RNNoise, DeepFilterNet.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "filter_name": {
                                "type": "string",
                                "description": "Noise cancellation filter name: 'Passthrough', 'WebRTC APM', 'RNNoise', or 'DeepFilterNet'"
                            }
                        },
                        "required": ["filter_name"]
                    }
                }
            },
            "handler": handle_set_noise_cancellation
        }

        self.tools["freeswitch_esl_command"] = {
            "definition": {
                "type": "function",
                "function": {
                    "name": "freeswitch_esl_command",
                    "description": "Execute a FreeSWITCH ESL Event Socket command (e.g. uuid_transfer, uuid_setvar, status, originate).",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "command": {"type": "string", "description": "FreeSWITCH command (e.g. uuid_transfer, uuid_setvar, status, originate)"},
                            "args": {"type": "string", "description": "Command arguments"}
                        },
                        "required": ["command"]
                    }
                }
            },
            "handler": handle_freeswitch_esl_command
        }

        self.tools["get_audio_processor_status"] = {
            "definition": {
                "type": "function",
                "function": {
                    "name": "get_audio_processor_status",
                    "description": "Check which noise cancellation filter is currently running and get real-time audio statistics.",
                    "parameters": {
                        "type": "object",
                        "properties": {},
                        "required": []
                    }
                }
            },
            "handler": handle_get_audio_processor_status
        }

    def get_function_schemas(self, enable_web_search: bool = True, router: Any = None):
        """Returns schemas for LLM context registration."""
        from app.tools.registry import global_tool_registry
        return global_tool_registry.get_function_schemas(enable_web_search=enable_web_search, router=router)

    def get_tool_definitions(self, enable_web_search: bool = True):
        """Returns JSON schema definitions for LLM registration."""
        from app.tools.registry import global_tool_registry
        return global_tool_registry.get_function_schemas(enable_web_search=enable_web_search)

    def register_tools_on_llm(self, llm_service: Any, enable_web_search: bool = True, router: Any = None):
        """Registers all tool handlers directly on the LLM service instance."""
        from app.tools.registry import global_tool_registry
        return global_tool_registry.register_tools_on_llm(llm_service, enable_web_search=enable_web_search, router=router)

tool_registry = VoiceToolRegistry()
