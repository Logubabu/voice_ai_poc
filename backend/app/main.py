import uuid
from fastapi import FastAPI, HTTPException, Response
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from app.config import config
from app.pipeline import pipeline_manager
from app.transport import create_webrtc_transport
from app.services.audio_processor import audio_processor_factory
from app.services.freeswitch_esl import freeswitch_esl_service
from app.telephony.twilio_service import twilio_service
from app.utils.logging import logger
from app.utils.patches import apply_aioice_patches, setup_asyncio_exception_handler

# Apply socket teardown patches immediately on module load
apply_aioice_patches()

app = FastAPI(
    title="Voice AI WebCall POC",
    description="Real-time Voice AI WebCall POC Backend powered by Pipecat",
    version="0.1.0",
)

from app.routers.knowledge_base import router as kb_router
from app.routers.callbacks import router as callbacks_router
from app.callbacks.scheduler import callback_scheduler_worker

# Configure CORS
cors_allow_all = getattr(config, "CORS_ALLOW_ALL", True)
cors_origins = ["*"] if cors_allow_all else config.ALLOWED_ORIGINS
cors_origin_regex = (getattr(config, "CORS_ORIGIN_REGEX", None) or r".*") if cors_allow_all else None

app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_origin_regex=cors_origin_regex,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["*"],
    max_age=86400,
)

# Include REST API routers
app.include_router(kb_router)
app.include_router(callbacks_router)


@app.on_event("startup")
async def warm_up_services():
    """Pre-warms service adapters and logs provider configuration status."""
    setup_asyncio_exception_handler()
    logger.info("==================================================")
    logger.info("VOICE AI BACKEND STARTUP")
    sarvam_configured = bool(config.SARVAM_API_KEY or config.STT_API_KEY)
    gemini_configured = bool(config.GEMINI_API_KEY or config.LLM_API_KEY)
    elevenlabs_configured = bool(config.ELEVENLABS_API_KEY or config.TTS_API_KEY)

    logger.info(f"[CONFIG] SARVAM_API_KEY: {'configured' if sarvam_configured else 'NOT CONFIGURED'}")
    logger.info(f"[CONFIG] GEMINI_API_KEY: {'configured' if gemini_configured else 'NOT CONFIGURED'}")
    logger.info(f"[CONFIG] ELEVENLABS_API_KEY: {'configured' if elevenlabs_configured else 'NOT CONFIGURED'}")

    try:
        from app.services.stt import create_stt_service
        from app.services.llm import create_llm_service
        from app.services.tts import create_tts_service
        create_stt_service(config)
        create_llm_service(config)
        create_tts_service(config)
        logger.info("[CONFIG] Voice pipeline pre-warming complete. Backend ready for WebRTC connections.")
    except Exception as e:
        logger.warning(f"[CONFIG] Pre-warming notice: {e}")

    # Start background scheduled callback worker
    if getattr(config, "CALLBACK_WORKER_ENABLED", True):
        await callback_scheduler_worker.start()

    logger.info("==================================================")


@app.on_event("shutdown")
async def shutdown_services():
    """Gracefully shuts down background workers."""
    if getattr(config, "CALLBACK_WORKER_ENABLED", True):
        await callback_scheduler_worker.stop()


from pipecat.transports.smallwebrtc.request_handler import SmallWebRTCRequestHandler, SmallWebRTCRequest
from pipecat.transports.smallwebrtc.connection import SmallWebRTCConnection, IceServer

def _build_ice_servers():
    ice_servers = []
    raw = getattr(config, "ICE_SERVERS", "") or "stun:stun.l.google.com:19302"
    for item in raw.split(","):
        item = item.strip()
        if item:
            ice_servers.append(IceServer(urls=item))
    return ice_servers

webrtc_request_handler = SmallWebRTCRequestHandler(ice_servers=_build_ice_servers())


class CandidateItem(BaseModel):
    candidate: str | None = None
    sdp_mid: str | None = None
    sdp_mline_index: int | None = None


class PatchCandidatesRequest(BaseModel):
    pc_id: str
    candidates: list[CandidateItem]


class StartCallRequest(BaseModel):
    session_id: str | None = None
    tenant_id: str | None = "default_tenant"
    knowledge_base_id: str | None = None


class StopCallRequest(BaseModel):
    session_id: str


class OfferRequest(BaseModel):
    sdp: str
    type: str = "offer"
    pc_id: str | None = None
    session_id: str | None = None
    tenant_id: str | None = "default_tenant"
    knowledge_base_id: str | None = None
    client_host: str | None = None


class NoiseCancellationRequest(BaseModel):
    filter_name: str


class ESLExecuteRequest(BaseModel):
    command: str
    args: str = ""


class OutboundCallRequest(BaseModel):
    phone_number: str
    gateway: str = "default"


class TwilioCallRequest(BaseModel):
    phone_number: str
    from_number: str | None = None
    twiml_url: str | None = None


@app.get("/")
@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "ok"}


@app.get("/api/debug/providers")
@app.get("/api/config/status")
async def get_config_status():
    """Reports configuration status of required providers without revealing secrets."""
    return {
        "stt": {
            "provider": config.STT_PROVIDER,
            "configured": bool(config.SARVAM_API_KEY or config.STT_API_KEY),
        },
        "llm": {
            "provider": config.LLM_PROVIDER,
            "model": config.LLM_MODEL,
            "configured": bool(config.GEMINI_API_KEY or config.LLM_API_KEY),
        },
        "tts": {
            "provider": config.TTS_PROVIDER,
            "configured": bool(config.ELEVENLABS_API_KEY or config.TTS_API_KEY),
        },
        "twilio": {
            "configured": bool(config.TWILIO_ACCOUNT_SID and config.TWILIO_AUTH_TOKEN),
            "from_number": config.TWILIO_FROM_NUMBER,
        },
    }


@app.get("/api/noise-cancellation/status")
async def get_noise_cancellation_status():
    """Gets currently running noise cancellation filter and audio loop metrics."""
    return audio_processor_factory.get_active_filter_status()


@app.post("/api/noise-cancellation/select")
async def select_noise_cancellation(req: NoiseCancellationRequest):
    """Dynamically switches active noise cancellation filter."""
    active_filter = audio_processor_factory.set_active_filter(req.filter_name)
    freeswitch_esl_service.execute_esl_command("noise_cancel", active_filter.display_name)
    return {
        "status": "success",
        "current_running_filter": active_filter.display_name,
        "details": audio_processor_factory.get_active_filter_status(),
    }


@app.get("/api/freeswitch/esl/status")
async def get_freeswitch_status():
    """Gets FreeSWITCH ESL connection status and active channels."""
    return freeswitch_esl_service.get_status()


@app.post("/api/freeswitch/esl/execute")
async def execute_freeswitch_esl(req: ESLExecuteRequest):
    """Executes a FreeSWITCH ESL command."""
    return freeswitch_esl_service.execute_esl_command(req.command, req.args)


from fastapi import Request
from app.telephony.provider import get_telephony_provider


@app.api_route("/api/twilio/voice", methods=["GET", "POST", "HEAD"])
@app.api_route("/api/telephony/twilio/voice", methods=["GET", "POST", "HEAD"])
@app.api_route("/api/telephony/twilio/twiml", methods=["GET", "POST", "HEAD"])
async def get_twilio_voice_twiml(request: Request):
    """Twilio Inbound Call Webhook. Returns TwiML XML payload to connect call audio to Pipecat WebSocket stream."""
    twiml_xml = twilio_service.generate_twiml(request=request)
    return Response(content=twiml_xml, media_type="application/xml")


@app.post("/api/twilio/call")
@app.post("/api/telephony/twilio/outbound-call")
async def twilio_outbound_call(req: TwilioCallRequest, request: Request):
    """Initiates an outbound phone call via Twilio REST API."""
    phone_number = req.phone_number.strip()
    if not phone_number or len(phone_number) < 5:
        raise HTTPException(status_code=400, detail="Invalid phone number format. Provide full E.164 number.")

    provider = get_telephony_provider("twilio")
    res = await provider.initiate_outbound_call(
        to_number=phone_number,
        from_number=req.from_number,
        twiml_url=req.twiml_url,
        request=request,
    )
    if not res.get("success"):
        raise HTTPException(status_code=500, detail=res.get("error", "Twilio call creation failed"))

    return {
        "status": res.get("status", "queued"),
        "call_sid": res.get("call_sid"),
        "session_id": res.get("call_sid"),
        "phone_number": phone_number,
        "raw_response": res.get("raw_response"),
    }


@app.post("/api/telephony/outbound-call")
async def make_outbound_phone_call(req: OutboundCallRequest, request: Request):
    """Initiates an outbound web/telephony call to a phone number via Twilio or FreeSWITCH SIP gateway."""
    logger.info(f"[OUTBOUND-CALL] Dialing phone number '{req.phone_number}' via gateway '{req.gateway}'")
    provider_name = "twilio" if req.gateway.lower() == "twilio" else "freeswitch"
    provider = get_telephony_provider(provider_name)
    res = await provider.initiate_outbound_call(
        to_number=req.phone_number,
        gateway=req.gateway,
        request=request,
    )
    return {
        "status": "initiated",
        "provider": provider_name,
        "phone_number": req.phone_number,
        "gateway": req.gateway,
        "result": res,
    }


from fastapi import WebSocket
from app.telephony.freeswitch.ws_stream import handle_freeswitch_audio_ws
from app.telephony.twilio_ws import handle_twilio_audio_ws


@app.websocket("/api/webrtc/freeswitch/ws")
async def freeswitch_audio_websocket(websocket: WebSocket, session_id: str = "session_phone_001", uuid: str = "uuid_phone_001"):
    """WebSocket endpoint for FreeSWITCH media audio streaming (Mode B Phone Call)."""
    await handle_freeswitch_audio_ws(websocket=websocket, session_id=session_id, freeswitch_uuid=uuid)


@app.websocket("/api/twilio/media-stream")
@app.websocket("/api/telephony/twilio/ws")
async def twilio_audio_websocket(websocket: WebSocket):
    """WebSocket endpoint for Twilio Media Streams (Mode B Phone Call)."""
    await handle_twilio_audio_ws(websocket=websocket)


@app.get("/api/audio/transports/status")
async def get_transports_status():
    """Gets status of active voice transports (WebRTC WebCall vs Phone FreeSWITCH)."""
    from app.telephony.freeswitch.event_listener import freeswitch_event_listener
    return {
        "supported_transports": ["webrtc", "freeswitch"],
        "freeswitch_summary": freeswitch_event_listener.get_session_summary(),
    }



@app.post("/api/start")
async def start_call(req: StartCallRequest | None = None):
    """Initializes a new Voice AI logical session ID without starting an unattached pipeline."""
    session_id = (req and req.session_id) or f"session_{uuid.uuid4().hex[:8]}"
    logger.info("==================================================")
    logger.info("VOICE AI SESSION")
    logger.info(f"[SESSION] Created: {session_id}")

    return {
        "session_id": session_id,
        "status": "ready",
    }


@app.post("/api/webrtc/offer")
async def webrtc_offer(req: OfferRequest):
    """Handles WebRTC SDP offer/answer negotiation and creates the browser-connected Pipecat pipeline."""
    session_id = req.session_id or f"session_{uuid.uuid4().hex[:8]}"
    logger.info(f"[WEBRTC] SDP offer received for session '{session_id}'")

    try:
        request = SmallWebRTCRequest(
            sdp=req.sdp,
            type=req.type,
            pc_id=req.pc_id,
        )

        async def on_connection(connection: SmallWebRTCConnection):
            logger.info(f"[WEBRTC] Browser connection created: {connection.pc_id}")
            
            # Setup WebRTC disconnection listener to stop pipeline and free resources
            @connection.event_handler("closed")
            async def handle_webrtc_closed(conn: SmallWebRTCConnection):
                logger.info(f"[WEBRTC] Connection closed for pc_id: {conn.pc_id}. Stopping session '{session_id}'")
                await pipeline_manager.stop_session(session_id)

            # Wait briefly for aiortc ICE gathering to complete so srflx & host candidates are in answer
            for _ in range(12):
                if hasattr(connection, "pc") and connection.pc.iceGatheringState == "complete":
                    break
                await asyncio.sleep(0.05)

            transport = create_webrtc_transport(connection=connection, cfg=config)
            logger.info(f"[WEBRTC] Transport created for session '{session_id}'")

            # Attach and start the Pipecat pipeline to this actual WebRTC connection
            await pipeline_manager.start_session(
                session_id=session_id,
                transport=transport,
                connection=connection,
                tenant_id=req.tenant_id or "default_tenant",
                knowledge_base_id=req.knowledge_base_id,
            )
            logger.info(f"[WEBRTC] WebRTC session '{session_id}' connected successfully")

        answer = await webrtc_request_handler.handle_web_request(
            request=request,
            webrtc_connection_callback=on_connection,
        )

        # Munge SDP answer candidates to support Docker container-to-host and NAT loopback
        if answer and "sdp" in answer:
            answer_sdp = answer["sdp"]

            # Determine candidate IP addresses reachable from outside the container
            target_ips = ["127.0.0.1"]

            webrtc_host = config.WEBRTC_HOST.strip() if getattr(config, "WEBRTC_HOST", None) else ""
            if webrtc_host and webrtc_host not in target_ips:
                target_ips.append(webrtc_host)

            if req.client_host and req.client_host not in ("localhost", "127.0.0.1") and req.client_host not in target_ips:
                target_ips.append(req.client_host)

            # Extract any host candidate IPs from incoming offer SDP
            if req.sdp:
                for o_line in req.sdp.splitlines():
                    if o_line.startswith("a=candidate:") and " typ host" in o_line:
                        o_parts = o_line.split(" ")
                        if len(o_parts) >= 8:
                            o_ip = o_parts[4]
                            if o_ip and not o_ip.endswith(".local") and not o_ip.startswith("127.") and not o_ip.startswith("172.18.") and o_ip not in target_ips:
                                target_ips.append(o_ip)

            lines = answer_sdp.splitlines()
            new_lines = []
            cand_idx = 1
            for line in lines:
                if line.startswith("c=IN IP4 172.") or line.startswith("c=IN IP4 10."):
                    new_lines.append("c=IN IP4 0.0.0.0")
                    continue

                if line.startswith("a=candidate:") and " typ host" in line:
                    parts = line.split(" ")
                    if len(parts) >= 8:
                        orig_ip = parts[4]
                        orig_port = parts[5]
                        # RFC 8839 compliant foundation (short string <= 32 chars) and descending priorities
                        new_lines.append(f"a=candidate:c{cand_idx} 1 udp 2130706431 {orig_ip} {orig_port} typ host")
                        cand_idx += 1

                        for tip in target_ips:
                            if tip != orig_ip:
                                prio = max(2130706431 - (cand_idx * 256), 1000)
                                new_lines.append(f"a=candidate:c{cand_idx} 1 udp {prio} {tip} {orig_port} typ host")
                                cand_idx += 1
                        continue

                new_lines.append(line)
            answer["sdp"] = "\r\n".join(new_lines) + "\r\n"

        logger.info(f"[WEBRTC] SDP answer returned to browser for session '{session_id}'")
        return answer
    except Exception as e:
        logger.exception(f"[WEBRTC][ERROR] SDP offer negotiation failed: {e}")
        raise HTTPException(status_code=500, detail=f"WebRTC offer failed: {str(e)}")


@app.patch("/api/webrtc/patch")
async def webrtc_patch(req: PatchCandidatesRequest):
    """Handles Trickle ICE candidate updates from browser."""
    try:
        from pipecat.transports.smallwebrtc.request_handler import SmallWebRTCPatchRequest, IceCandidate
        patch_candidates = [
            IceCandidate(
                candidate=c.candidate or "",
                sdp_mid=c.sdp_mid or "",
                sdp_mline_index=c.sdp_mline_index or 0,
            )
            for c in req.candidates
        ]
        patch_req = SmallWebRTCPatchRequest(pc_id=req.pc_id, candidates=patch_candidates)
        await webrtc_request_handler.handle_patch_request(patch_req)
        return {"status": "ok"}
    except Exception as e:
        logger.debug(f"[WEBRTC] Notice handling trickle candidate: {e}")
        return {"status": "ignored"}


@app.post("/api/stop")
async def stop_call(req: StopCallRequest):
    """Terminates an active Voice AI WebCall session."""
    logger.info(f"[SESSION] Received stop_call request for session '{req.session_id}'")
    success = await pipeline_manager.stop_session(req.session_id)
    if not success:
        logger.warning(f"[SESSION] Session '{req.session_id}' was not active or failed to stop.")
    return {"session_id": req.session_id, "status": "disconnected"}


@app.get("/api/status/{session_id}")
async def get_session_status(session_id: str):
    """Gets current status of a voice call session."""
    session = pipeline_manager.active_sessions.get(session_id)
    if not session:
        return {"session_id": session_id, "status": "idle"}
    return {
        "session_id": session_id,
        "status": session.get("status", "connected"),
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)
