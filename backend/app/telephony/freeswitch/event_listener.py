import time
from typing import Dict, Any, Optional
from app.utils.logging import logger
from app.utils.audit import audit_logger


class CallSession:
    """Represents a FreeSWITCH telephony call session state."""

    def __init__(self, call_id: str, freeswitch_uuid: str, caller_number: str = "Unknown", destination_number: str = "Unknown"):
        self.call_id = call_id
        self.freeswitch_uuid = freeswitch_uuid
        self.caller_number = caller_number
        self.destination_number = destination_number
        self.state = "INCOMING"
        self.created_at = time.time()
        self.answered_at: Optional[float] = None
        self.ended_at: Optional[float] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "call_id": self.call_id,
            "freeswitch_uuid": self.freeswitch_uuid,
            "caller_number": self.caller_number,
            "destination_number": self.destination_number,
            "state": self.state,
            "created_at": self.created_at,
            "answered_at": self.answered_at,
            "ended_at": self.ended_at,
            "duration_secs": round(time.time() - self.created_at, 1),
        }


class FreeSWITCHEventListener:
    """Tracks FreeSWITCH event socket events and maintains live call session registry."""

    def __init__(self):
        self.active_sessions: Dict[str, CallSession] = {}

    def handle_event(self, event_name: str, event_data: Dict[str, Any]):
        """Processes FreeSWITCH channel events (CHANNEL_CREATE, CHANNEL_ANSWER, CHANNEL_HANGUP, DTMF)."""
        uuid = event_data.get("Unique-ID") or event_data.get("uuid") or "unknown"
        caller = event_data.get("Caller-Caller-ID-Number", "Unknown")
        destination = event_data.get("Caller-Destination-Number", "Unknown")

        logger.info(f"[FREESWITCH-EVENT] Event: '{event_name}' (UUID: '{uuid}')")

        if event_name == "CHANNEL_CREATE":
            session = CallSession(
                call_id=f"call_{uuid[:8]}",
                freeswitch_uuid=uuid,
                caller_number=caller,
                destination_number=destination,
            )
            self.active_sessions[uuid] = session
            audit_logger.log_event(
                event="CALL_CHANNEL_CREATED",
                category="telephony",
                session_id=session.call_id,
                actor="freeswitch",
                action="channel_create",
                details=session.to_dict(),
                status="SUCCESS",
            )

        elif event_name == "CHANNEL_ANSWER":
            session = self.active_sessions.get(uuid)
            if session:
                session.state = "AI_ACTIVE"
                session.answered_at = time.time()
                audit_logger.log_event(
                    event="CALL_ANSWERED",
                    category="telephony",
                    session_id=session.call_id,
                    actor="freeswitch",
                    action="channel_answer",
                    details=session.to_dict(),
                    status="SUCCESS",
                )

        elif event_name == "CHANNEL_HANGUP":
            session = self.active_sessions.pop(uuid, None)
            if session:
                session.state = "ENDED"
                session.ended_at = time.time()
                audit_logger.log_event(
                    event="CALL_ENDED",
                    category="telephony",
                    session_id=session.call_id,
                    actor="freeswitch",
                    action="channel_hangup",
                    details=session.to_dict(),
                    status="SUCCESS",
                )

    def get_session_summary(self) -> Dict[str, Any]:

        return {
            "active_call_count": len(self.active_sessions),
            "sessions": [s.to_dict() for s in self.active_sessions.values()],
        }


freeswitch_event_listener = FreeSWITCHEventListener()
