# Twilio Voice AI Integration Guide

## Overview

The Twilio Voice AI integration connects Twilio Phone Calls (Inbound & Outbound PSTN/SIP) bi-directionally to the existing local Pipecat Voice AI agent.

```
Phone <---> Twilio PSTN <---> Public HTTPS/WebSocket Tunnel <---> Local Voice AI Backend (FastAPI + Pipecat)
```

---

## Configuration

Set environment variables in `backend/.env`:

```env
TWILIO_ACCOUNT_SID=account_id
TWILIO_AUTH_TOKEN=auth_token
TWILIO_PHONE_NUMBER=twilio_phone_number
TWILIO_WEBHOOK_BASE_URL=https://your-public-domain.com
TWILIO_VALIDATE_SIGNATURE=false
```

---

## Webhook Endpoints

| Endpoint | Method | Description |
|---|---|---|
| `/api/twilio/voice` | `POST` / `GET` | Twilio Inbound Webhook (returns TwiML XML with WebSocket stream URL) |
| `/api/twilio/call` | `POST` | Outbound call initiation API (`{ "phone_number": "+919876543210" }`) |
| `/api/twilio/media-stream` | `WS` | Bidirectional WebSocket Audio Stream (G.711 mu-law 8kHz) |

---

## Testing Local Calls

### 1. Inbound Call Configuration (Twilio Console)

1. Open [Twilio Console -> Phone Numbers](https://console.twilio.com/).
2. Select your Twilio Number (`+17372508034`).
3. Under **Voice & Fax**, set **A CALL COMES IN** to `Webhook`:
   `https://skp54pvx-8000.inc1.devtunnels.ms/api/twilio/voice` (HTTP POST).
4. Save configuration. When any user dials `+17372508034`, Twilio bridges the audio stream into your local Voice AI pipeline.

### 2. Outbound Call via API

```bash
curl -X POST "https://skp54pvx-8000.inc1.devtunnels.ms/api/twilio/call" \
     -H "Content-Type: application/json" \
     -d '{
           "phone_number": "+919876543210"
         }'
```

---

## Pipeline & Features

- **No Agent Duplication**: Reuses existing Pipecat pipeline (`STT` -> `LLM` -> `TTS`).
- **Tool Calling**: Live tools (`web_search`, `check_order_status`, `book_appointment`, etc.) execute seamlessly during Twilio phone calls.
- **Interruption / Barge-in**: User speech interrupts pending TTS audio.
- **Provider Abstraction**: Decoupled using `BaseTelephonyProvider` (`TwilioTelephonyProvider` / `FreeSwitchTelephonyProvider`).
