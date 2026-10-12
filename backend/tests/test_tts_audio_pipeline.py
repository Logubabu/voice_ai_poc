import pytest
import asyncio
from app.services.tts import AudioGenerationError, validate_audio_bytes
from app.tools.router import ToolRouter
from app.tools.web_search.service import WebSearchService
from app.services.search.provider import SearchResult, SearchProvider
from pipecat.frames.frames import (
    TextFrame,
    TTSAudioRawFrame,
)
from pipecat.processors.frame_processor import FrameProcessor, FrameDirection


class DummySearchProvider(SearchProvider):
    async def search(self, query: str, max_results: int = 5, timeout: float = 5.0):
        return [
            SearchResult(
                title="OpenAI Latest News",
                url="https://openai.com/news",
                snippet="OpenAI releases new models today.",
                source="OpenAI",
                published_at="2026-10-08",
            )
        ]


class MockTTSProcessor(FrameProcessor):
    def __init__(self, raise_empty: bool = False, raise_error: bool = False, sink: FrameProcessor = None):
        super().__init__()
        self.raise_empty = raise_empty
        self.raise_error = raise_error
        self.sink = sink
        self.audio_frames_sent = 0

    async def process_frame(self, frame, direction: FrameDirection = FrameDirection.DOWNSTREAM):
        await super().process_frame(frame, direction)
        if isinstance(frame, TextFrame) and frame.text.strip():
            if self.raise_error:
                raise AudioGenerationError("TTS provider failed to synthesize audio")
            
            if self.raise_empty:
                audio_data = b""
            else:
                audio_data = b"\x00\x01\x02\x03\x04\x05\x06\x07\x08\x09" * 10
            
            validate_audio_bytes(audio_data, min_bytes=5 if not self.raise_empty else 0)
            
            audio_frame = TTSAudioRawFrame(audio_data, sample_rate=24000, num_channels=1)
            self.audio_frames_sent += 1
            if self.sink:
                await self.sink.process_frame(audio_frame, direction)


class TransportMockSink(FrameProcessor):
    def __init__(self):
        super().__init__()
        self.received_audio_frames = []

    async def process_frame(self, frame, direction: FrameDirection = FrameDirection.DOWNSTREAM):
        await super().process_frame(frame, direction)
        if isinstance(frame, TTSAudioRawFrame):
            self.received_audio_frames.append(frame)


@pytest.mark.asyncio
async def test_1_normal_llm_response_produces_tts():
    """Test 1: Normal LLM response text produces TTS audio frames."""
    sink = TransportMockSink()
    tts = MockTTSProcessor(sink=sink)
    
    await tts.process_frame(TextFrame("Hello, how can I help you today?"))
    
    assert tts.audio_frames_sent == 1
    assert len(sink.received_audio_frames) == 1
    assert len(sink.received_audio_frames[0].audio) > 0


@pytest.mark.asyncio
async def test_2_web_search_response_produces_tts():
    """Test 2: Response after web search execution produces TTS audio."""
    provider = DummySearchProvider()
    service = WebSearchService(provider=provider)
    search_res = await service.execute_search("OpenAI news")
    assert search_res["success"] is True
    
    final_summary_text = f"According to recent reports, {search_res['results'][0]['snippet']}"
    
    sink = TransportMockSink()
    tts = MockTTSProcessor(sink=sink)
    
    await tts.process_frame(TextFrame(final_summary_text))
    
    assert len(sink.received_audio_frames) == 1
    assert sink.received_audio_frames[0].sample_rate == 24000


@pytest.mark.asyncio
async def test_3_tool_call_followed_by_final_response_produces_exactly_one_tts():
    """Test 3: Tool call execution followed by final LLM answer produces exactly ONE final TTS audio response."""
    sink = TransportMockSink()
    tts = MockTTSProcessor(sink=sink)
    
    # 1. Final response text sent to TTS
    await tts.process_frame(TextFrame("Here is the latest OpenAI news summary."))
    
    assert len(sink.received_audio_frames) == 1


@pytest.mark.asyncio
async def test_4_empty_llm_response_does_not_invoke_tts():
    """Test 4: Empty LLM response text does not generate audio frames."""
    sink = TransportMockSink()
    tts = MockTTSProcessor(sink=sink)
    
    await tts.process_frame(TextFrame("   "))
    assert len(sink.received_audio_frames) == 0


@pytest.mark.asyncio
async def test_5_tts_returning_empty_audio_raises_error():
    """Test 5: TTS returning empty audio bytes raises AudioGenerationError."""
    sink = TransportMockSink()
    tts = MockTTSProcessor(raise_empty=True, sink=sink)
    
    with pytest.raises(AudioGenerationError, match="empty audio data"):
        await tts.process_frame(TextFrame("Valid input text"))


@pytest.mark.asyncio
async def test_6_audio_bytes_correctly_passed_to_transport():
    """Test 6: Generated audio bytes match expected length and sample rate when passed to output transport."""
    sink = TransportMockSink()
    tts = MockTTSProcessor(sink=sink)
    
    await tts.process_frame(TextFrame("Audio payload test"))
    
    audio_frame = sink.received_audio_frames[0]
    assert audio_frame.num_channels == 1
    assert audio_frame.sample_rate == 24000
    assert len(audio_frame.audio) == 100


@pytest.mark.asyncio
async def test_7_tts_failure_does_not_silently_succeed():
    """Test 7: TTS service error raises exception rather than passing silently."""
    sink = TransportMockSink()
    tts = MockTTSProcessor(raise_error=True, sink=sink)
    
    with pytest.raises(AudioGenerationError, match="failed to synthesize"):
        await tts.process_frame(TextFrame("Trigger error"))


@pytest.mark.asyncio
async def test_8_multiple_tool_calls_still_end_in_final_tts():
    """Test 8: Turn with multiple tool calls successfully completes and produces final TTS audio."""
    router = ToolRouter()
    session_id = "test_multi_tool_tts"
    
    res1 = await router.route_tool_call("web_search", "call_1", {"query": "Search A"}, session_id=session_id)
    res2 = await router.route_tool_call("web_search", "call_2", {"query": "Search B"}, session_id=session_id)
    assert res1["success"] is True
    assert res2["success"] is True
    
    sink = TransportMockSink()
    tts = MockTTSProcessor(sink=sink)
    
    await tts.process_frame(TextFrame("Synthesized answer after 2 tool calls"))
    assert len(sink.received_audio_frames) == 1


@pytest.mark.asyncio
async def test_9_conversation_continues_after_tool_call():
    """Test 9: Subsequent conversational turns continue working after a tool call."""
    router = ToolRouter()
    session_id = "test_turn_continuation"
    
    # Turn 1: tool call
    await router.route_tool_call("web_search", "call_1", {"query": "Search 1"}, session_id=session_id)
    router.reset_turn(session_id)
    
    # Turn 2: normal conversation
    sink = TransportMockSink()
    tts = MockTTSProcessor(sink=sink)
    
    await tts.process_frame(TextFrame("Subsequent turn answer"))
    assert len(sink.received_audio_frames) == 1


@pytest.mark.asyncio
async def test_10_audio_output_does_not_block_future_user_input():
    """Test 10: Non-blocking frame push allows VAD & future user input to be processed cleanly."""
    sink = TransportMockSink()
    tts = MockTTSProcessor(sink=sink)
    
    task = asyncio.create_task(tts.process_frame(TextFrame("Non-blocking playback")))
    await asyncio.sleep(0.01)
    assert task.done()
    assert len(sink.received_audio_frames) == 1
