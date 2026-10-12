from pipecat.transports.smallwebrtc.connection import SmallWebRTCConnection
from pipecat.transports.smallwebrtc.transport import SmallWebRTCTransport
from pipecat.transports.base_transport import TransportParams

from app.config import Config
from app.utils.logging import logger


def create_webrtc_transport(connection: SmallWebRTCConnection, cfg: Config) -> SmallWebRTCTransport:
    """Creates a SmallWebRTCTransport instance directly using the browser's active SmallWebRTCConnection."""
    logger.info(f"[WEBRTC] Creating SmallWebRTC Transport for connection: {connection.pc_id}")

    return SmallWebRTCTransport(
        webrtc_connection=connection,
        params=TransportParams(
            audio_in_enabled=True,
            audio_out_enabled=True,
        ),
    )
