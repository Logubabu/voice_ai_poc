import asyncio
import time
from app.config import config
from app.pipeline import VoicePipelineManager
from pipecat.frames.frames import TranscriptionFrame
from pipecat.processors.frame_processor import FrameProcessor, FrameDirection

class MockTransportInput(FrameProcessor):
    async def process_frame(self, frame, direction: FrameDirection = FrameDirection.DOWNSTREAM):
        await super().process_frame(frame, direction)
        await self.push_frame(frame, direction)

class MockTransportOutput(FrameProcessor):
    def __init__(self):
        super().__init__()
        self.received_frames = []

    async def process_frame(self, frame, direction: FrameDirection = FrameDirection.DOWNSTREAM):
        await super().process_frame(frame, direction)
        self.received_frames.append(frame)
        print(f"[MOCK TRANSPORT OUT] Received frame: {type(frame).__name__} details={getattr(frame, 'text', '') or (getattr(frame, 'audio', b'')[:20] if hasattr(frame, 'audio') else '')}")
        await self.push_frame(frame, direction)

class DummyTransport:
    def __init__(self):
        self._input = MockTransportInput()
        self._output = MockTransportOutput()

    def input(self):
        return self._input

    def output(self):
        return self._output

async def run_trace():
    print("=== STARTING PIPELINE TRACE ===")
    manager = VoicePipelineManager(config)
    transport = DummyTransport()

    session = await manager.start_session(
        session_id="trace_session_001",
        transport=transport,
        is_webcall=True
    )

    task = session["task"]

    # Wait for pipeline start frame to reach end
    await asyncio.sleep(2)

    print("\n--- TEST 1: Sending user text 'Hello, how are you?' ---")
    ts_str = time.strftime("%I:%M %p")
    await task.queue_frame(TranscriptionFrame(text="Hello, how are you?", user_id="user", timestamp=ts_str))

    await asyncio.sleep(8)

    print("\n--- TEST 2: Sending user text 'Search the web for the latest OpenAI news.' ---")
    await task.queue_frame(TranscriptionFrame(text="Search the web for the latest OpenAI news.", user_id="user", timestamp=ts_str))

    await asyncio.sleep(12)

    print("\n=== TRACE COMPLETE ===")

    await manager.stop_session("trace_session_001")

if __name__ == "__main__":
    asyncio.run(run_trace())
