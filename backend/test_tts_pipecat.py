import asyncio
from dotenv import load_dotenv
load_dotenv()

import pytest
from app.config import config
from app.services.tts import create_tts_service
from pipecat.frames.frames import TextFrame, LLMFullResponseStartFrame, LLMFullResponseEndFrame

@pytest.mark.asyncio
async def test_pipecat_tts():
    print(f"Configured TTS_PROVIDER: {config.TTS_PROVIDER}")
    tts = create_tts_service(config)
    print(f"Created TTS service: {tts}")

    # Process frames through TTS
    await tts.process_frame(LLMFullResponseStartFrame(), None)
    await tts.process_frame(TextFrame("Hello, how are you?"), None)
    await tts.process_frame(LLMFullResponseEndFrame(), None)

    await asyncio.sleep(3)

if __name__ == "__main__":
    asyncio.run(test_pipecat_tts())
