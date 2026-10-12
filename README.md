# SharyX Voice AI Platform

Production-Grade Real-Time Voice AI WebCall Assistant, Multi-Tenant Knowledge Base (RAG), and Scheduled Callback Management System built with **Pipecat**, **FastAPI**, **SQLite WAL**, **Qdrant Vector DB**, **FreeSWITCH ESL**, **WebRTC**, and **React + Vite + Tailwind CSS**.

---

## 🚀 Key Features

- 🎙 **WebRTC Real-Time Audio Streaming**: Streaming STT, LLM generation, and TTS audio synthesis with low-latency barge-in/interruption.
- 📚 **Knowledge Base (RAG)**: Multi-tenant document vector search, semantic chunking, and live match accuracy scoring (pts / 100.0).
- 📅 **Scheduled Callback System**: Production-grade scheduled callback system operating in `SCHEDULE_ONLY` (no call credits mode) or `LIVE_CALL` mode.
- 🤖 **LLM Tool Calling**: AI Assistant automatically schedules callbacks via `schedule_callback` tool when users say "Call me tomorrow at 10 AM".
- 🛡️ **Race-Condition & Multi-Worker Safe**: Concurrency-safe SQLite WAL transaction locking (`BEGIN IMMEDIATE`) for polling schedulers.
- ⚡ **Zero Call Credit Guarantee**: Server-side enforced `CALLBACK_EXECUTION_MODE=SCHEDULE_ONLY` mode guarantees zero outbound telephony charges while transitioning due callbacks to `WAITING_FOR_CREDITS`.

---

## 📅 Scheduled Callback Management Architecture

### Lifecycle & State Machine

```
User / Voice AI Tool
        │
        ▼
POST /api/callbacks ──► Database Transaction ──► Scheduled Callback Created (SCHEDULED)
                                                        │
                                                        ▼
                                                Scheduler Polls (every 15s)
                                                        │
                                    ┌───────────────────┴───────────────────┐
                                    ▼                                       ▼
                       CALLBACK_EXECUTION_MODE                CALLBACK_EXECUTION_MODE
                            = SCHEDULE_ONLY                         = LIVE_CALL
                                    │                                       │
                                    ▼                                       ▼
                         WAITING_FOR_CREDITS                   PSTN / Telephony Call
                         (No call credits used)                 (Twilio / FreeSWITCH)
```

### Supported Callback Statuses
- `SCHEDULED`: Callback created and waiting for scheduled execution time.
- `WAITING_FOR_CREDITS`: Scheduled time arrived in `SCHEDULE_ONLY` mode. No call initiated due to zero credits.
- `READY`: Claimed for execution in `LIVE_CALL` mode.
- `IN_PROGRESS`: Outbound call active.
- `COMPLETED`: Call successfully completed.
- `CANCELLED`: Cancelled by user or API request.
- `FAILED`: Telephony execution failed.
- `EXPIRED`: Overdue callback exceeding `CALLBACK_MAX_LATE_MINUTES` window.

---

## ⚙️ Environment Configuration

Add the following settings to `backend/.env`:

```ini
# Callback System Settings
CALLBACK_ENABLED=true
CALLBACK_EXECUTION_MODE=SCHEDULE_ONLY   # Set to SCHEDULE_ONLY or LIVE_CALL
CALLBACK_SCHEDULER_ENABLED=true
CALLBACK_SCHEDULER_INTERVAL=15          # Polling interval in seconds
CALLBACK_MAX_LATE_MINUTES=60            # Overdue threshold before EXPIRED status
CALLBACK_DEFAULT_TIMEZONE=Asia/Kolkata
```

---

## 📡 Callback API Endpoints

| Method | Endpoint | Description |
| :--- | :--- | :--- |
| `POST` | `/api/callbacks` | Schedule a new callback (supports `Idempotency-Key` header) |
| `GET` | `/api/callbacks` | List callbacks with pagination (`page`, `limit`, `status`, `search`, `sort`) |
| `GET` | `/api/callbacks/{id}` | Get detailed callback record |
| `PATCH` | `/api/callbacks/{id}` | Reschedule callback timestamp, timezone, or reason |
| `PATCH` | `/api/callbacks/{id}/cancel` | Cancel scheduled callback |

### Example Request (`POST /api/callbacks`)

```json
{
  "phone_number": "+919876543210",
  "contact_name": "John Doe",
  "scheduled_at": "2026-10-10T10:30:00+05:30",
  "timezone": "Asia/Kolkata",
  "callback_reason": "Follow up regarding enterprise Voice AI demo",
  "priority": "normal"
}
```

## 🐳 Docker Quick Start (Single Container Run)

The default Docker setup builds and runs the entire Voice AI platform (FreeSWITCH 1.10, FastAPI backend, and React/Vite UI proxied via Nginx) in a single production-ready container:

### 1. Build the All-in-One Docker Image
```bash
docker build -t voice-ai-poc .
```

### 2. Single Docker Run Command
```bash
docker run -d \
  --name voice-ai \
  -p 5173:5173 \
  -p 8000:8000 \
  -p 5060:5060/udp \
  -p 5060:5060/tcp \
  -p 8021:8021 \
  -p 8086:8086 \
  --env-file .env \
  voice-ai-poc
```

### 3. Or Run with Docker Compose (includes Qdrant & SearXNG)
```bash
docker compose up -d
```

| Service | Port | Description |
| :--- | :--- | :--- |
| **Frontend UI** | `5173` | React / Vite UI (Nginx reverse proxy) |
| **Backend API** | `8000` | FastAPI WebRTC Signaling & REST API (`/health`, `/api/*`) |
| **SIP Telephony** | `5060/udp`, `5060/tcp` | FreeSWITCH SIP Signaling |
| **FreeSWITCH ESL**| `8021` | FreeSWITCH Event Socket Layer |
| **Audio Stream** | `8086` | Real-time audio stream |

---

## 🛠️ Local Development & Quick Start

### Backend

```bash
cd backend
python -m venv .venv
.venv\Scripts\activate   # Windows
pip install -r requirements.txt
python -m app.main
```
Backend runs on `http://localhost:8000`.

### Frontend

```bash
cd frontend
npm install
npm run dev
```
Frontend runs on `http://localhost:5173`.

---

## 🧪 Testing

Run backend test suite including callback models, scheduler, time resolver, concurrency, and API tests:

```bash
cd backend
pytest tests
```
