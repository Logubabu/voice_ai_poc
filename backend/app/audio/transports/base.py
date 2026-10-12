from abc import ABC, abstractmethod
from typing import Any, Dict


class BaseVoiceTransport(ABC):
    """Abstract Base Class for Voice Transports (WebRTC, FreeSWITCH WebSocket)."""

    def __init__(self, transport_type: str, session_id: str):
        self.transport_type = transport_type
        self.session_id = session_id
        self.is_connected = False

    @abstractmethod
    async def start(self) -> bool:
        """Starts transport connection and media streaming pipeline."""
        pass

    @abstractmethod
    async def stop(self) -> bool:
        """Stops transport connection and cleans up media streams."""
        pass

    @abstractmethod
    async def send_audio_frame(self, pcm_bytes: bytes, sample_rate: int = 16000) -> bool:
        """Sends outgoing audio frame to transport endpoint."""
        pass

    @abstractmethod
    def get_status(self) -> Dict[str, Any]:
        """Returns transport configuration and status metrics."""
        return {
            "transport_type": self.transport_type,
            "session_id": self.session_id,
            "connected": self.is_connected,
        }
