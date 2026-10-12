from typing import Any, Dict
from app.audio.transports.base import BaseVoiceTransport
from app.audio.codec import AudioResampler
from app.utils.logging import logger


class FreeSWITCHVoiceTransport(BaseVoiceTransport):
    """Voice Transport implementation for FreeSWITCH SIP/PSTN telephony calls over WebSocket audio streaming."""

    def __init__(self, session_id: str, freeswitch_uuid: str, websocket: Any = None):
        super().__init__(transport_type="freeswitch", session_id=session_id)
        self.freeswitch_uuid = freeswitch_uuid
        self.websocket = websocket
        self.telephony_sample_rate = 8000
        self.ai_sample_rate = 16000

    async def start(self) -> bool:
        self.is_connected = True
        logger.info(
            f"[TRANSPORT-FREESWITCH] Started FreeSWITCH transport (UUID: '{self.freeswitch_uuid}') for session '{self.session_id}'"
        )
        return True

    async def stop(self) -> bool:
        self.is_connected = False
        logger.info(
            f"[TRANSPORT-FREESWITCH] Stopped FreeSWITCH transport (UUID: '{self.freeswitch_uuid}') for session '{self.session_id}'"
        )
        return True

    async def send_audio_frame(self, pcm_bytes: bytes, sample_rate: int = 16000) -> bool:
        if not self.is_connected or not self.websocket:
            return False

        try:
            # Resample outgoing 16kHz AI audio to 8kHz telephony format if needed
            if sample_rate == 16000:
                pcm_out = AudioResampler.resample_16k_to_8k(pcm_bytes)
            else:
                pcm_out = pcm_bytes

            await self.websocket.send_bytes(pcm_out)
            return True
        except Exception as e:
            logger.warning(f"[TRANSPORT-FREESWITCH] Error sending audio frame over WebSocket: {e}")
            return False

    def process_incoming_telephony_audio(self, pcm_8k_bytes: bytes) -> bytes:
        """Resamples 8kHz incoming FreeSWITCH PCM audio frame to 16kHz AI pipeline format."""
        return AudioResampler.resample_8k_to_16k(pcm_8k_bytes)

    def get_status(self) -> Dict[str, Any]:
        status = super().get_status()
        status.update({
            "freeswitch_uuid": self.freeswitch_uuid,
            "telephony_sample_rate": self.telephony_sample_rate,
            "ai_sample_rate": self.ai_sample_rate,
        })
        return status
