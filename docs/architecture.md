# Sharyx Voice AI Architecture Specification

## Overview

The Sharyx Voice AI system supports two selectable voice transport modes while sharing a single, unified AI pipeline:

### Mode A: WebCall (Browser WebRTC)
```
Browser → WebRTC → WebRTCVoiceTransport → NoiseCancellationManager → STT → LLM + Tool Calling → TTS → WebRTC → Browser
```

### Mode B: Phone Call (FreeSWITCH SIP/PSTN)
```
PSTN/SIP → FreeSWITCH → WebSocket Audio Stream → FreeSWITCHVoiceTransport → Resampler (8k↔16k) → NoiseCancellationManager → STT → LLM + Tool Calling → TTS → WebSocket → FreeSWITCH → PSTN/SIP
```

## Key Components

1. **Audio Transports (`backend/app/audio/transports/`)**: Clean abstraction for WebRTC and FreeSWITCH WebSocket audio streaming.
2. **Audio Codec (`backend/app/audio/codec.py`)**: High-performance linear interpolation 8kHz ↔ 16kHz PCM audio resampling.
3. **Noise Cancellation (`backend/app/noise_cancellation/`)**: Pluggable noise suppression manager supporting RNNoise, WebRTC APM, DeepFilterNet, and Passthrough.
4. **Tool Calling Framework (`backend/app/tools/`)**: ToolRegistry and ToolExecutor managing real-time web search (`web_search`) and custom tools with barge-in cancellation.
5. **Telephony & FreeSWITCH (`backend/app/telephony/freeswitch/`)**: Event Socket Layer (ESL) client and CallSession event listener for SIP/PSTN call management.
