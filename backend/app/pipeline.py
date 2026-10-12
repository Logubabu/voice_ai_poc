import asyncio
import time
from typing import Any, Dict, Optional

from pipecat.audio.vad.silero import SileroVADAnalyzer
from pipecat.audio.vad.vad_analyzer import VADParams
from pipecat.frames.frames import (
    ErrorFrame,
    Frame,
    InputAudioRawFrame,
    LLMRunFrame,
    TextFrame,
    TranscriptionFrame,
    UserStartedSpeakingFrame,
    UserStoppedSpeakingFrame,
    FunctionCallInProgressFrame,
    FunctionCallResultFrame,
    TTSAudioRawFrame,
    TTSStartedFrame,
    TTSStoppedFrame,
)
from pipecat.pipeline.pipeline import Pipeline
from pipecat.pipeline.runner import WorkerRunner
from pipecat.pipeline.task import PipelineParams, PipelineWorker
from pipecat.processors.aggregators.llm_context import LLMContext
from pipecat.processors.aggregators.llm_response_universal import (
    LLMContextAggregatorPair,
    LLMUserAggregatorParams,
)
from pipecat.processors.frame_processor import FrameDirection, FrameProcessor

from app.config import Config
from app.services.stt import create_stt_service
from app.services.llm import create_llm_service
from app.services.tts import create_tts_service
from app.services.audio_processor import NoiseCancellationFrameProcessor
from app.utils.logging import logger


class AudioDebugProcessor(FrameProcessor):
    """Temporary audio debug processor that counts incoming audio frames from WebRTC and logs periodically."""

    def __init__(self):
        super().__init__()
        self.frame_count = 0

    async def process_frame(self, frame: Frame, direction: FrameDirection):
        await super().process_frame(frame, direction)
        if isinstance(frame, InputAudioRawFrame):
            self.frame_count += 1
            if self.frame_count % 50 == 0 or self.frame_count == 1:
                audio_len = len(getattr(frame, "audio", b""))
                logger.info(f"[CHECKPOINT 1: USER_AUDIO_RECEIVED] frame #{self.frame_count} bytes={audio_len}")
        await self.push_frame(frame, direction)


class DiagnosticEventProcessor(FrameProcessor):
    """Intercepts pipeline frames to produce structured diagnostic logs and real-time DataChannel events."""

    def __init__(self, connection: Any = None, session_id: str = "default_session"):
        super().__init__()
        self.connection = connection
        self.session_id = session_id
        self.current_ai_response = ""

    def _send_app_message(self, data: dict):
        if self.connection and hasattr(self.connection, "send_app_message"):
            try:
                self.connection.send_app_message(data)
            except Exception as e:
                logger.warning(f"[AUDIO] Notice sending app message over data channel: {e}")

    async def process_frame(self, frame: Frame, direction: FrameDirection):
        await super().process_frame(frame, direction)

        if isinstance(frame, UserStartedSpeakingFrame):
            logger.info(f"[CALL] call_id={self.session_id} [VAD] user started speaking (barge-in interruption detected)")
            from app.tools.router import tool_router
            cancelled_count = tool_router.cancel_pending_tools(self.session_id)
            tool_router.reset_turn(self.session_id)
            if cancelled_count > 0:
                logger.info(f"[CALL] call_id={self.session_id} [BARGE-IN] Cancelled {cancelled_count} in-flight tool tasks due to user interruption")
            self._send_app_message({"type": "interruption"})
            self._send_app_message({"type": "state", "state": "listening"})
            self.current_ai_response = ""
            # Immediately push TTSStoppedFrame to stop active transport audio playback
            await self.push_frame(TTSStoppedFrame(), direction)

        elif isinstance(frame, UserStoppedSpeakingFrame):
            logger.info(f"[CALL] call_id={self.session_id} [VAD] user stopped speaking")

        elif isinstance(frame, TranscriptionFrame):
            logger.info(f"[CALL] call_id={self.session_id} [STT] user_text=\"{frame.text}\"")
            self._send_app_message({
                "type": "transcript",
                "sender": "user",
                "text": frame.text,
                "timestamp": time.strftime("%I:%M %p"),
            })
            self._send_app_message({"type": "state", "state": "processing"})
            self.current_ai_response = ""

        elif isinstance(frame, FunctionCallInProgressFrame):
            logger.info(f"[CALL] call_id={self.session_id} [LLM] tool_call={frame.function_name}")
            self._send_app_message({"type": "state", "state": "searching"})

        elif isinstance(frame, FunctionCallResultFrame):
            tool_name = getattr(frame, "function_name", "web_search")
            args = getattr(frame, "arguments", {}) or {}
            result = getattr(frame, "result", {}) or {}
            if tool_name == "knowledge_search":
                res_count = len(result.get("results", []))
                top_score = result.get("confidence", 0.0)
                accuracy_pts = top_score * 100.0
                q_text = result.get("query", args.get("query", ""))
                scores_str = ", ".join([f"chunk_{i+1}={r.get('score', 0.0)*100:.1f}pts" for i, r in enumerate(result.get("results", []))])
                logger.info(
                    f"[CALL] call_id={self.session_id} [KB-ACCURACY] query=\"{q_text}\" results={res_count} "
                    f"top_accuracy={accuracy_pts:.1f}pts (confidence={top_score:.4f}) scores=[{scores_str}]"
                )
            else:
                logger.info(f"[CALL] call_id={self.session_id} [TOOL] name={tool_name} success={result.get('success', True)}")

            self._send_app_message({
                "type": "tool_call",
                "tool_name": tool_name,
                "args": args,
                "result": result,
                "timestamp": time.strftime("%I:%M %p"),
            })
            self._send_app_message({"type": "state", "state": "processing"})

        elif isinstance(frame, TextFrame):
            text_snippet = frame.text.strip()
            if text_snippet:
                if not self.current_ai_response:
                    self._send_app_message({"type": "state", "state": "speaking"})
                self.current_ai_response += frame.text
                logger.info(f"[CALL] call_id={self.session_id} [LLM] final_response=\"{self.current_ai_response}\"")
                self._send_app_message({
                    "type": "transcript",
                    "sender": "ai",
                    "text": self.current_ai_response,
                    "timestamp": time.strftime("%I:%M %p"),
                })

        elif isinstance(frame, ErrorFrame):
            processor = getattr(frame, "processor", "pipeline")
            error_msg = getattr(frame, "error", str(frame))
            logger.error(f"[CALL] call_id={self.session_id} [PIPELINE][ERROR] [{processor}] {error_msg}")
            self._send_app_message({"type": "error", "message": f"[{processor}] {error_msg}"})

        await self.push_frame(frame, direction)


class TTSMonitor(FrameProcessor):
    """Monitors TTS output frames immediately after the TTS service."""

    def __init__(self, connection: Any = None, session_id: str = "default_session"):
        super().__init__()
        self.connection = connection
        self.session_id = session_id
        self.tts_frame_count = 0

    def _send_app_message(self, data: dict):
        if self.connection and hasattr(self.connection, "send_app_message"):
            try:
                self.connection.send_app_message(data)
            except Exception as e:
                logger.warning(f"[AUDIO] Notice sending app message over data channel: {e}")

    async def process_frame(self, frame: Frame, direction: FrameDirection):
        await super().process_frame(frame, direction)

        if isinstance(frame, TTSStartedFrame):
            logger.info(f"[CALL] call_id={self.session_id} [TTS] generating_audio")
            self.tts_frame_count = 0
            self._send_app_message({"type": "state", "state": "speaking"})

        elif isinstance(frame, TTSAudioRawFrame):
            self.tts_frame_count += 1
            audio_bytes = getattr(frame, "audio", b"")
            if self.tts_frame_count == 1:
                logger.info(f"[CALL] call_id={self.session_id} [TTS] audio_stream_started")
            logger.info(f"[CALL] call_id={self.session_id} [WEBCALL] audio_sent frame=#{self.tts_frame_count} bytes={len(audio_bytes)}")

        elif isinstance(frame, TTSStoppedFrame):
            logger.info(f"[CALL] call_id={self.session_id} [TTS] audio_stream_finished frames={self.tts_frame_count}")
            if self.tts_frame_count == 0:
                logger.error(f"[CALL] call_id={self.session_id} [TTS][FATAL] ZERO audio frames produced")
                self._send_app_message({"type": "error", "message": "TTS produced no audio"})
            self._send_app_message({"type": "state", "state": "listening"})

        await self.push_frame(frame, direction)


class VoicePipelineManager:
    """Manages the lifecycle of a real-time Voice AI pipeline session."""

    def __init__(self, cfg: Config):
        self.cfg = cfg
        self.active_sessions: Dict[str, Dict[str, Any]] = {}

    async def start_session(
        self,
        session_id: str,
        transport: Any,
        connection: Any = None,
        audio_in_sample_rate: int = 16000,
        audio_out_sample_rate: int = 24000,
        is_webcall: bool = True,
        tenant_id: str = "default_tenant",
        knowledge_base_id: Optional[str] = None,
        extra_system_prompt: Optional[str] = None,
    ):
        """Builds and starts the Pipecat real-time pipeline attached to a transport."""
        if transport is None:
            logger.error("[PIPELINE][FATAL] start_session called without a connected transport!")
            raise ValueError("A connected SmallWebRTC transport is required")

        # Stop existing session with same session_id or stale webcall sessions
        if session_id in self.active_sessions:
            logger.warning(f"[PIPELINE] Session '{session_id}' is already active. Stopping existing session before starting new pipeline.")
            await self.stop_session(session_id)

        if is_webcall:
            for old_id, sess in list(self.active_sessions.items()):
                if sess.get("is_webcall", True):
                    logger.warning(f"[PIPELINE] Cleaning up previous WebCall session '{old_id}' before starting new call.")
                    await self.stop_session(old_id)

        logger.info("[PIPELINE] Creating STT")
        stt = create_stt_service(self.cfg)

        current_date_info = time.strftime("%A, %B %d, %Y (%I:%M %p)")
        system_content = f"Today's Date and Time: {current_date_info}\n\n{self.cfg.SYSTEM_PROMPT}"
        if tenant_id:
            system_content += f"\nActive Session Tenant ID: {tenant_id}"
        if knowledge_base_id:
            system_content += f"\nActive Session Knowledge Base ID: {knowledge_base_id}"
        if extra_system_prompt:
            system_content += f"\n\n{extra_system_prompt}"

        logger.info(f"[PIPELINE] Creating LLM (is_webcall={is_webcall}, tenant={tenant_id}, kb_id={knowledge_base_id})")
        llm = create_llm_service(self.cfg, is_webcall=is_webcall, system_instruction=system_content)
        setattr(llm, "session_id", session_id)
        setattr(llm, "tenant_id", tenant_id)
        setattr(llm, "knowledge_base_id", knowledge_base_id)

        logger.info("[PIPELINE] Creating TTS")
        tts = create_tts_service(self.cfg)

        from app.tools.registry import global_tool_registry
        from app.tools.router import tool_router

        tool_calling_enabled = self.cfg.WEBCALL_TOOL_CALLING_ENABLED if is_webcall else self.cfg.TOOL_CALLING_ENABLED
        web_search_enabled = self.cfg.WEBCALL_WEB_SEARCH_ENABLED if is_webcall else self.cfg.WEB_SEARCH_ENABLED

        if tool_calling_enabled:
            tools = global_tool_registry.get_function_schemas(enable_web_search=web_search_enabled, router=tool_router)
            logger.info(f"[PIPELINE] Tools configured for WebCall (count={len(tools)}, web_search={web_search_enabled})")
        else:
            tools = []
            logger.info(f"[PIPELINE] Tool calling disabled for session '{session_id}' (is_webcall={is_webcall})")

        context = LLMContext(
            messages=[],
            tools=tools,
        )

        vad_analyzer = SileroVADAnalyzer(
            params=VADParams(
                confidence=0.7,
                start_secs=0.3,
                stop_secs=0.4,
                min_volume=0.05,
            )
        )

        aggregators = LLMContextAggregatorPair(
            context,
            user_params=LLMUserAggregatorParams(vad_analyzer=vad_analyzer),
        )

        audio_debug = AudioDebugProcessor()
        noise_cancellation_processor = NoiseCancellationFrameProcessor(connection=connection)
        diagnostic_processor = DiagnosticEventProcessor(connection=connection, session_id=session_id)
        tts_monitor = TTSMonitor(connection=connection, session_id=session_id)

        logger.info("[PIPELINE] Pipeline created with NoiseCancellationFrameProcessor")

        # Pipeline order: transport.input(), audio_debug, noise_cancellation_processor, stt, aggregators.user(), llm, diagnostic_processor, tts, tts_monitor, aggregators.assistant(), transport.output()
        pipeline_elements = [
            transport.input(),
            audio_debug,
            noise_cancellation_processor,
            stt,
            aggregators.user(),
            llm,
            diagnostic_processor,
            tts,
            tts_monitor,
            aggregators.assistant(),
            transport.output(),
        ]

        pipeline = Pipeline(pipeline_elements)
        task = PipelineWorker(
            pipeline,
            params=PipelineParams(
                audio_in_sample_rate=audio_in_sample_rate,
                audio_out_sample_rate=audio_out_sample_rate,
                enable_metrics=True,
            ),
        )
        runner = WorkerRunner()

        # Run pipeline task in background
        runner_task = asyncio.create_task(runner.run(task))

        self.active_sessions[session_id] = {
            "task": task,
            "runner_task": runner_task,
            "runner": runner,
            "pipeline": pipeline,
            "transport": transport,
            "connection": connection,
            "session_id": session_id,
            "tenant_id": tenant_id,
            "knowledge_base_id": knowledge_base_id,
            "is_webcall": is_webcall,
            "status": "connected",
        }

        logger.info(f"[PIPELINE] Pipeline started for session '{session_id}'")

        # Add initial greeting prompt so context is valid for Gemini (has non-system message)
        context.add_message({"role": "user", "content": "Greet the user in one short sentence."})

        async def trigger_initial_greeting():
            # Allow pipeline worker runner and transport 0.6s to initialize before queueing initial LLMRunFrame
            await asyncio.sleep(0.6)
            if connection:
                # Wait for WebRTC connection to reach connected state before sending initial audio
                for _ in range(25):
                    if hasattr(connection, "is_connected") and connection.is_connected():
                        break
                    await asyncio.sleep(0.1)
            await task.queue_frame(LLMRunFrame())

        asyncio.create_task(trigger_initial_greeting())

        return self.active_sessions[session_id]

    async def stop_session(self, session_id: str) -> bool:
        """Stops and cleans up a voice pipeline session."""
        session = self.active_sessions.pop(session_id, None)
        if not session:
            logger.warning(f"[SESSION] Session '{session_id}' not found for cleanup.")
            return False

        logger.info(f"[SESSION] Cleaning up voice pipeline session '{session_id}'")
        try:
            task: PipelineWorker = session.get("task")
            if task:
                await task.cancel()
                logger.info(f"[SESSION] PipelineWorker for '{session_id}' cancelled cleanly.")

            runner_task = session.get("runner_task")
            if runner_task and not runner_task.done():
                runner_task.cancel()
                try:
                    await runner_task
                except asyncio.CancelledError:
                    pass

            logger.info(f"[SESSION] Session '{session_id}' stopped successfully.")
            return True
        except Exception as e:
            logger.exception(f"[SESSION][ERROR] Error during cleanup of session '{session_id}': {e}")
            return False


pipeline_manager = VoicePipelineManager(Config())
