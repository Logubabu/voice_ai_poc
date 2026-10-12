import json
import asyncio
from fastapi import WebSocket, WebSocketDisconnect
from pipecat.transports.websocket.fastapi import FastAPIWebsocketTransport, FastAPIWebsocketParams
from pipecat.serializers.twilio import TwilioFrameSerializer

from app.config import config
from app.pipeline import pipeline_manager
from app.utils.logging import logger
from app.utils.audit import audit_logger


async def handle_twilio_audio_ws(websocket: WebSocket):
    """WebSocket handler for Twilio Media Streams (Inbound & Outbound Phone Calls).
    Connects Twilio G.711 mulaw audio bi-directionally to the Pipecat Voice AI Pipeline.
    """
    await websocket.accept()
    logger.info("[TWILIO-WS] Twilio WebSocket connection accepted")

    stream_sid = None
    call_sid = None

    try:
        # 1. Read initial Twilio metadata handshake messages to extract streamSid and callSid
        start_timeout = 5.0
        start_time = asyncio.get_event_loop().time()
        while not stream_sid:
            elapsed = asyncio.get_event_loop().time() - start_time
            remaining = max(0.1, start_timeout - elapsed)
            try:
                msg_str = await asyncio.wait_for(websocket.receive_text(), timeout=remaining)
                msg_data = json.loads(msg_str)
                event_type = msg_data.get("event")

                if event_type == "start":
                    start_data = msg_data.get("start", {})
                    stream_sid = start_data.get("streamSid") or msg_data.get("streamSid")
                    call_sid = start_data.get("callSid") or msg_data.get("callSid")
                    logger.info(f"[TWILIO-WS] Received start event - streamSid: '{stream_sid}', callSid: '{call_sid}'")
                    break
                elif event_type == "connected":
                    logger.info("[TWILIO-WS] Received connected event from Twilio. Awaiting start event...")
                elif event_type == "media":
                    stream_sid = msg_data.get("streamSid")
                    if stream_sid:
                        logger.warning(f"[TWILIO-WS] Received media event before start event. Inferred streamSid: '{stream_sid}'")
                        break
            except asyncio.TimeoutError:
                logger.warning(f"[TWILIO-WS] Handshake timeout ({start_timeout}s) waiting for start event. Proceeding with fallback IDs.")
                break
            except Exception as e:
                logger.warning(f"[TWILIO-WS] Exception during initial handshake read: {e}")
                break

        if not stream_sid:
            stream_sid = f"stream_{id(websocket)}"
        if not call_sid:
            call_sid = f"twilio_call_{stream_sid[:8]}"

        audit_logger.log_event(
            event="TWILIO_MEDIA_STREAM_CONNECTED",
            category="telephony",
            actor="twilio",
            action="ws_connect",
            session_id=call_sid,
            details={"stream_sid": stream_sid, "call_sid": call_sid},
            status="SUCCESS",
        )

        # 2. Configure TwilioFrameSerializer with actual stream_sid
        serializer = TwilioFrameSerializer(
            stream_sid=stream_sid,
            call_sid=call_sid,
            account_sid=config.TWILIO_ACCOUNT_SID,
            auth_token=config.TWILIO_AUTH_TOKEN,
            params=TwilioFrameSerializer.InputParams(
                twilio_sample_rate=8000,
                sample_rate=8000,
                auto_hang_up=False,
            ),
        )

        # 3. Configure FastAPIWebsocketTransport
        transport_params = FastAPIWebsocketParams(
            audio_out_enabled=True,
            add_wav_header=False,
            serializer=serializer,
        )

        transport = FastAPIWebsocketTransport(
            websocket=websocket,
            params=transport_params,
        )

        # 4. Attach transport and launch Pipecat pipeline (8kHz telephony audio)
        from app.callbacks.repository import callback_repository

        cb = await callback_repository.get_callback(call_sid)
        if not cb:
            active_cbs = await callback_repository.list_callbacks(status="DIALING", limit=5)
            if active_cbs:
                cb = active_cbs[0]
                await callback_repository.update_status(cb.id, target_status="IN_PROGRESS", call_sid=call_sid)

        tenant_id = cb.tenant_id if cb else "default_tenant"
        extra_prompt = None
        if cb:
            extra_prompt = (
                f"OUTBOUND CALLBACK CONTEXT:\n"
                f"- Customer Name: {cb.customer_name}\n"
                f"- Reason: {cb.reason}\n"
                f"- Context: {cb.callback_context or 'N/A'}\n"
                f"Instruction: Greet the customer warmly by name and state that you are calling them back as requested."
            )
            logger.info(f"[TWILIO-WS] Associated active callback '{cb.id}' with call '{call_sid}' for customer '{cb.customer_name}'")

        session = await pipeline_manager.start_session(
            session_id=call_sid,
            transport=transport,
            audio_in_sample_rate=8000,
            audio_out_sample_rate=8000,
            is_webcall=False,
            tenant_id=tenant_id,
            extra_system_prompt=extra_prompt,
        )

        logger.info(f"[TWILIO-WS] Pipecat Voice AI pipeline active for call '{call_sid}' (streamSid: {stream_sid})")

        # 5. Await runner_task to keep WebSocket open until call finishes
        runner_task = session.get("runner_task")
        if runner_task:
            try:
                await runner_task
            except asyncio.CancelledError:
                pass

    except WebSocketDisconnect:
        logger.info(f"[TWILIO-WS] Twilio WebSocket disconnected for call '{call_sid or stream_sid}'")
    except Exception as e:
        logger.exception(f"[TWILIO-WS][ERROR] Exception in Twilio WebSocket handler: {e}")
    finally:
        if call_sid:
            await pipeline_manager.stop_session(call_sid)
            audit_logger.log_event(
                event="TWILIO_MEDIA_STREAM_DISCONNECTED",
                category="telephony",
                actor="twilio",
                action="ws_disconnect",
                session_id=call_sid,
                status="DISCONNECTED",
            )
