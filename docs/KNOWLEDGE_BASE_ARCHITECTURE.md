# Knowledge Base & RAG Architecture Specification

## 1. System Overview & Current Lifecycle

### Current Voice Request Lifecycle (Before KB Integration)
```
Caller (WebCall/Browser or Phone Call via FreeSWITCH / Twilio)
  │
  ├── WebRTC Offer / Media WS Stream
  ▼
FastAPI Application Entry Point (`app/main.py`)
  │
  ├── SmallWebRTC Transport / WS Audio Handler (`app/transport.py`, `app/telephony/*`)
  ▼
Pipecat Pipeline Task (`app/pipeline.py`)
  │
  ├── Audio Frame Received -> Noise Cancellation Processor (`app/services/audio_processor.py`)
  ├── STT Service (`app/services/stt.py` - Sarvam / Groq) -> Text Transcription Frame
  ├── LLM Context Aggregator (`pipecat.processors.aggregators.llm_context`)
  ├── LLM Service (`app/services/llm.py` - Gemini / Groq)
  │     │
  │     ├── Tool Router (`app/tools/router.py`) & Execution (`app/tools/executor.py`)
  │     │     └── `web_search` tool (`app/tools/web_search/`) -> SearXNG / DuckDuckGo / Tavily
  │     │
  │     └── Speech Response Generation -> Text Frame
  │
  ├── TTS Service (`app/services/tts.py` - ElevenLabs / Sarvam / Groq) -> PCM Audio Raw Frames
  └── Transport Output -> Audio back to caller
```

---

## 2. Identified Repository Components

| Component | Component File / Location | Summary / Responsibilities |
|---|---|---|
| **FastAPI App** | `backend/app/main.py` | App entrypoint, HTTP routes, WebRTC SDP offer negotiation (`/api/webrtc/offer`), WebSocket handlers |
| **WebSocket Endpoints** | `backend/app/main.py`, `app/telephony/*` | `/api/webrtc/freeswitch/ws` and `/api/twilio/media-stream` |
| **WebCall Implementation** | `backend/app/transport.py`, `app/pipeline.py` | Pipecat `SmallWebRTC` transport integration |
| **FreeSWITCH Integration** | `backend/app/services/freeswitch_esl.py` | ESL command execution & event channel listeners |
| **STT Implementation** | `backend/app/services/stt.py` | `SarvamSTTService` / `GroqSTTService` |
| **TTS Implementation** | `backend/app/services/tts.py` | `ElevenLabsTTSService` / `SarvamTTSService` |
| **LLM Implementation** | `backend/app/services/llm.py` | `GoogleLLMService` (Gemini) / `GroqLLMService` |
| **Tool Registry** | `backend/app/tools/registry.py` | Singleton `global_tool_registry` registering `BaseTool` subclasses |
| **Tool Router & Executor**| `backend/app/tools/router.py`, `executor.py` | Handles tool permissions, turn limits, barge-in cancellation, timeouts |
| **Session State** | `backend/app/pipeline.py` | `VoicePipelineManager` active sessions, Pipecat `LLMContext` |
| **Prompt Management** | `backend/app/config.py`, `app/pipeline.py` | System prompt formatting with date/time context |
| **Configuration** | `backend/app/config.py` | Pydantic / dataclass-style environment config loader |
| **Logging & Audit** | `backend/app/utils/logging.py`, `audit.py` | Structured logger and JSON audit logger |
| **Docker Configuration** | `docker-compose.yml` | Multi-container setup (`backend`, `frontend`, `freeswitch`, `searxng`) |
| **Frontend** | `frontend/src/` | React + TypeScript + Vite UI with WebRTC WebCall client (`services/voice.ts`) |

---

## 3. Knowledge Base Tool Insertion Point & Flow

The `knowledge_search` tool is integrated cleanly as a standard `BaseTool` inside the existing Tool Calling Architecture:

```
Caller Speech
  │
  ▼
STT -> Transcription
  │
  ▼
LLM Router (Gemini)
  │
  ├── [Tool Decision: Is Internal Knowledge Needed?]
  │     │
  │     ├── YES -> Call `knowledge_search(query, top_k, category)`
  │     │           │
  │     │           ▼
  │     │         `ToolRegistry` -> `ToolRouter` -> `ToolExecutor`
  │     │           │
  │     │           ▼
  │     │         `KnowledgeBaseService.search()`
  │     │           │
  │     │           ├── Normalize Query & Rewrite using Turn Context
  │     │           ├── Embedding Generation (`EmbeddingProvider`)
  │     │           ├── Vector Search in Qdrant with Strict Metadata Filters (`tenant_id`, `kb_id`)
  │     │           ├── Optional Reranking (`Reranker`)
  │     │           ├── Confidence Threshold Evaluation (`KB_MIN_SCORE`)
  │     │           └── Context Budget Trimming (`KB_MAX_CONTEXT_TOKENS`)
  │     │           │
  │     │           ▼
  │     │         Return structured results to LLM
  │     │
  │     └── NO / General Query -> Internal Knowledge Response
  │
  ▼
LLM Grounded Answer Generation
  │
  ▼
TTS -> Voice Output to Caller
```

---

## 4. Multi-Tenant Knowledge Base Components Overview

The `backend/knowledge_base/` package implements:
- `service.py`: High-level Knowledge Base manager and RAG search operations.
- `ingestion.py`: Asynchronous document parsing, chunking, embedding, vector storage pipeline.
- `chunking.py`: Structure-aware document chunkers for PDF, DOCX, TXT, MD, CSV, JSON, HTML.
- `embeddings.py`: Configurable embedding provider abstraction (SentenceTransformers / OpenAI / Qdrant-compatible).
- `retrieval.py`: Semantic vector retrieval and optional hybrid candidate search.
- `reranking.py`: Cross-encoder reranker interface and scoring logic.
- `models.py`: Database models (SQLAlchemy) for `KnowledgeBase`, `Document`, `DocumentChunk`.
- `repository.py`: Async database repository for metadata persistence.
- `security.py`: Multi-tenant isolation enforcement and data sanitization.
- `metrics.py`: Prometheus / JSON latency and hit-rate metrics collector.
- `exceptions.py`: Standardized typed exception hierarchy.
