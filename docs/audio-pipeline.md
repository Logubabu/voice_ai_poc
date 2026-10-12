# Audio Frame Pipeline & Latency

## Overview

Audio frames are processed incrementally in 20ms frames without buffering full seconds of audio.

## Pipeline Stages

1. **Incoming Frame**: 16kHz PCM (WebRTC) or 8kHz PCM (FreeSWITCH).
2. **Resampling**: `AudioResampler.resample_8k_to_16k` if input is 8kHz.
3. **Noise Suppression**: `NoiseCancellationManager.process_frame`.
4. **Voice Activity Detection**: Silero VAD.
5. **Speech-to-Text**: Sarvam / Groq / OpenAI STT.
6. **LLM + Tool Execution**: Gemini LLM with `web_search`.
7. **Text-to-Speech**: ElevenLabs / Sarvam TTS.
8. **Outgoing Transport**: Resampled 16k → 8k for FreeSWITCH or direct 24k/16k for WebRTC.
