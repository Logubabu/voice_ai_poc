from abc import ABC, abstractmethod
from typing import Dict, Any
from app.config import config
from app.utils.logging import logger


class BaseTelephonyProvider(ABC):
    """Abstract Telephony Provider interface decoupling Voice AI core from specific carrier providers."""

    @abstractmethod
    def get_provider_name(self) -> str:
        """Returns the provider name identifier (e.g., 'twilio', 'freeswitch')."""
        pass

    @abstractmethod
    async def initiate_outbound_call(self, to_number: str, **kwargs) -> Dict[str, Any]:
        """Initiates an outbound phone call via the provider infrastructure."""
        pass

    @abstractmethod
    def get_status(self) -> Dict[str, Any]:
        """Returns current provider connection health and call state metrics."""
        pass


class TwilioTelephonyProvider(BaseTelephonyProvider):
    """Twilio Carrier Telephony Provider implementation."""

    def __init__(self):
        from app.telephony.twilio_service import twilio_service
        self.service = twilio_service

    def get_provider_name(self) -> str:
        return "twilio"

    async def initiate_outbound_call(self, to_number: str, **kwargs) -> Dict[str, Any]:
        from_number = kwargs.get("from_number")
        twiml_url = kwargs.get("twiml_url")
        return await self.service.make_outbound_call(
            to_number=to_number,
            from_number=from_number,
            twiml_url=twiml_url,
        )

    def get_status(self) -> Dict[str, Any]:
        return {
            "provider": "twilio",
            "account_sid_configured": bool(config.TWILIO_ACCOUNT_SID),
            "auth_token_configured": bool(config.TWILIO_AUTH_TOKEN),
            "phone_number": config.TWILIO_PHONE_NUMBER or config.TWILIO_FROM_NUMBER,
            "webhook_url": config.TWILIO_WEBHOOK_BASE_URL or config.PUBLIC_BASE_URL,
            "signature_validation": config.TWILIO_VALIDATE_SIGNATURE,
        }


class FreeSwitchTelephonyProvider(BaseTelephonyProvider):
    """FreeSWITCH PBX Telephony Provider implementation."""

    def __init__(self):
        from app.services.freeswitch_esl import freeswitch_esl_service
        self.service = freeswitch_esl_service

    def get_provider_name(self) -> str:
        return "freeswitch"

    async def initiate_outbound_call(self, to_number: str, **kwargs) -> Dict[str, Any]:
        gateway = kwargs.get("gateway", "default")
        return self.service.execute_esl_command("originate", f"sofia/gateway/{gateway}/{to_number} &socket(127.0.0.1:8086 async)")

    def get_status(self) -> Dict[str, Any]:
        esl_stat = self.service.get_status()
        return {
            "provider": "freeswitch",
            "esl_connected": esl_stat.get("esl_connected", False),
            "host": esl_stat.get("host"),
            "active_channels": esl_stat.get("active_channels_count", 0),
        }


# Telephony Provider Registry
telephony_providers: Dict[str, BaseTelephonyProvider] = {
    "twilio": TwilioTelephonyProvider(),
    "freeswitch": FreeSwitchTelephonyProvider(),
}


def get_telephony_provider(provider_name: str = "twilio") -> BaseTelephonyProvider:
    """Factory helper to obtain a TelephonyProvider instance by name."""
    name_lower = provider_name.lower().strip()
    provider = telephony_providers.get(name_lower)
    if not provider:
        logger.warning(f"[TELEPHONY-PROVIDER] Unknown provider '{provider_name}'. Defaulting to 'twilio'.")
        return telephony_providers["twilio"]
    return provider
