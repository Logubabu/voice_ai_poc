from typing import Any, Dict
from app.audio.transports.base import BaseVoiceTransport
from app.utils.logging import logger


class WebRTCVoiceTransport(BaseVoiceTransport):
    """Voice Transport implementation for WebRTC browser WebCall connections."""

    def __init__(self, session_id: str, connection: Any = None, pipecat_transport: Any = None):
        super().__init__(transport_type="webrtc", session_id=session_id)
        self.connection = connection
        self.pipecat_transport = pipecat_transport

    async def start(self) -> bool:
        self.is_connected = True
        logger.info(f"[TRANSPORT-WEBRTC] Started WebRTC transport for session '{self.session_id}'")
        return True

    async def stop(self) -> bool:
        self.is_connected = False
        logger.info(f"[TRANSPORT-WEBRTC] Stopped WebRTC transport for session '{self.session_id}'")
        return True

    async def send_audio_frame(self, pcm_bytes: bytes, sample_rate: int = 16000) -> bool:
        if not self.is_connected or not self.pipecat_transport:
            return False
        # Pipecat WebRTC output handles audio frames automatically
        return True

    def get_status(self) -> Dict[str, Any]:
        status = super().get_status()
        status.update({
            "connection_id": getattr(self.connection, "pc_id", "unknown") if self.connection else None,
            "sample_rate": 16000,
        })
        return status
