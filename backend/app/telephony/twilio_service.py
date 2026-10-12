import httpx
from typing import Dict, Any, Optional
from app.config import config
from app.utils.logging import logger
from app.utils.audit import audit_logger


class TwilioService:
    """Service to handle Twilio REST API outbound calls and TwiML voice media streams."""

    def __init__(self):
        self.account_sid = config.TWILIO_ACCOUNT_SID
        self.auth_token = config.TWILIO_AUTH_TOKEN
        self.from_number = config.TWILIO_FROM_NUMBER
        self.api_url = f"https://api.twilio.com/2010-04-01/Accounts/{self.account_sid}/Calls.json"

    async def make_outbound_call(
        self,
        to_number: str,
        from_number: Optional[str] = None,
        twiml_url: Optional[str] = None,
        timeout: float = 10.0,
    ) -> Dict[str, Any]:
        """Makes an outbound phone call via Twilio REST API.

        Args:
            to_number: Target recipient phone number (e.g. +919876543210)
            from_number: Sender Twilio phone number (defaults to config.TWILIO_FROM_NUMBER)
            twiml_url: Optional TwiML URL for handling call voice/WebSocket stream
        """
        account_sid = config.TWILIO_ACCOUNT_SID or self.account_sid
        auth_token = config.TWILIO_AUTH_TOKEN or self.auth_token
        caller_id = from_number or config.TWILIO_FROM_NUMBER or config.TWILIO_PHONE_NUMBER or self.from_number

        if not account_sid or not auth_token:
            logger.error("[TWILIO][FATAL] Twilio credentials missing (TWILIO_ACCOUNT_SID / TWILIO_AUTH_TOKEN).")
            return {
                "success": False,
                "error": "Twilio API credentials not configured in .env",
            }

        api_url = f"https://api.twilio.com/2010-04-01/Accounts/{account_sid}/Calls.json"
        candidates = [config.PUBLIC_BASE_URL, config.TWILIO_WEBHOOK_BASE_URL]
        public_url = next((u for u in candidates if u and "localhost" not in u and "127.0.0.1" not in u), None)
        base_url = (public_url or config.TWILIO_WEBHOOK_BASE_URL or config.PUBLIC_BASE_URL or "http://localhost:8000").rstrip("/")
        target_url = twiml_url or f"{base_url}/api/twilio/voice"

        if "localhost" in target_url or "127.0.0.1" in target_url:
            logger.warning(f"[TWILIO][WARNING] Twilio webhook URL '{target_url}' is set to localhost. Twilio cloud servers cannot reach localhost! Set PUBLIC_BASE_URL in .env to your devtunnels/ngrok URL.")

        logger.info(f"[TWILIO] Making outbound call to {to_number} from {caller_id} via Twilio REST API (Webhook: {target_url})")

        data = {
            "To": to_number,
            "From": caller_id,
            "Url": target_url,
        }

        try:
            async with httpx.AsyncClient(timeout=timeout) as client:
                response = await client.post(
                    api_url,
                    data=data,
                    auth=(account_sid, auth_token),
                )

                if response.status_code in (200, 201):
                    res_data = response.json()
                    call_sid = res_data.get("sid", "unknown")
                    logger.info(f"[TWILIO] Outbound call initiated successfully. Call SID: {call_sid}")

                    audit_logger.log_event(
                        event="TWILIO_OUTBOUND_CALL_SUCCESS",
                        category="telephony",
                        actor="backend",
                        action="twilio_call",
                        details={"to": to_number, "from": caller_id, "call_sid": call_sid, "url": target_url},
                        status="SUCCESS",
                    )

                    return {
                        "success": True,
                        "call_sid": call_sid,
                        "status": res_data.get("status", "queued"),
                        "to": to_number,
                        "from": caller_id,
                        "raw_response": res_data,
                    }
                else:
                    error_text = response.text
                    logger.error(f"[TWILIO][ERROR] HTTP {response.status_code}: {error_text}")
                    return {
                        "success": False,
                        "error": f"Twilio API Error ({response.status_code}): {error_text}",
                        "status_code": response.status_code,
                    }

        except Exception as e:
            logger.exception(f"[TWILIO][ERROR] Failed to execute Twilio outbound call: {e}")
            return {
                "success": False,
                "error": str(e),
            }

    def generate_twiml(self, websocket_url: Optional[str] = None) -> str:
        """Generates TwiML XML payload to connect call audio to Pipecat WebSocket stream."""
        if not websocket_url:
            base_url = (config.TWILIO_WEBHOOK_BASE_URL or config.PUBLIC_BASE_URL or "http://localhost:8000").rstrip("/")
            is_local = "localhost" in base_url or "127.0.0.1" in base_url
            ws_scheme = "ws" if is_local else "wss"
            clean_host = base_url.replace("wss://", "").replace("ws://", "").replace("https://", "").replace("http://", "").rstrip("/")
            websocket_url = f"{ws_scheme}://{clean_host}/api/twilio/media-stream"

        return f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Connect>
        <Stream url="{websocket_url}" />
    </Connect>
</Response>"""


twilio_service = TwilioService()
