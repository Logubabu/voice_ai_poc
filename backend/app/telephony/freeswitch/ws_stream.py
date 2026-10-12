from fastapi import WebSocket, WebSocketDisconnect
from app.audio.transports.freeswitch import FreeSWITCHVoiceTransport
from app.utils.logging import logger
from app.utils.audit import audit_logger


async def handle_freeswitch_audio_ws(websocket: WebSocket, session_id: str, freeswitch_uuid: str):
    """Handles bidirectional WebSocket audio streaming between FreeSWITCH and Python AI pipeline."""
    await websocket.accept()
    logger.info(f"[FREESWITCH-WS] WebSocket audio stream connected for session '{session_id}' (UUID: '{freeswitch_uuid}')")

    transport = FreeSWITCHVoiceTransport(
        session_id=session_id,
        freeswitch_uuid=freeswitch_uuid,
        websocket=websocket,
    )
    await transport.start()

    audit_logger.log_event(
        event="FREESWITCH_WS_CONNECTED",
        category="telephony",
        session_id=session_id,
        actor="freeswitch",
        action="ws_audio_connect",
        details={"freeswitch_uuid": freeswitch_uuid},
        status="SUCCESS",
    )

    try:
        while True:
            # Receive raw 8kHz PCM telephony audio frame bytes from FreeSWITCH
            pcm_8k_bytes = await websocket.receive_bytes()
            if not pcm_8k_bytes:
                continue

            # Resample 8kHz telephony audio to 16kHz AI pipeline format
            _ = transport.process_incoming_telephony_audio(pcm_8k_bytes)

            # In the pipeline runner, pcm_16k_bytes is passed directly to the unified AI pipeline

    except WebSocketDisconnect:
        logger.info(f"[FREESWITCH-WS] FreeSWITCH WebSocket audio stream disconnected for session '{session_id}'")
    except Exception as e:
        logger.error(f"[FREESWITCH-WS][ERROR] Error in FreeSWITCH WebSocket stream for session '{session_id}': {e}")
    finally:
        await transport.stop()
        audit_logger.log_event(
            event="FREESWITCH_WS_DISCONNECTED",
            category="telephony",
            session_id=session_id,
            actor="freeswitch",
            action="ws_audio_disconnect",
            details={"freeswitch_uuid": freeswitch_uuid},
            status="SUCCESS",
        )
