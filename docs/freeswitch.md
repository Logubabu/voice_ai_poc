# FreeSWITCH Integration & Telephony Guide

## Overview

FreeSWITCH operates as the PSTN/SIP gateway for Mode B Phone Call connections.

## Configuration & Ports

- **ESL Port**: `8021` (Event Socket Layer)
- **SIP Port**: `5060` (UDP/TCP)
- **Media WebSocket**: `8086`

## Call Flow

1. FreeSWITCH accepts inbound SIP/PSTN call.
2. Dialplan triggers `mod_event_socket` event `CHANNEL_CREATE`.
3. ESL Client (`FreeSWITCHESLClient`) handles call control asynchronously.
4. Bidirectional 8kHz PCM audio streams over WebSocket to `/api/webrtc/freeswitch/ws`.
5. `FreeSWITCHVoiceTransport` resamples 8kHz ↔ 16kHz for the AI pipeline.
