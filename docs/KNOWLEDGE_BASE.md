# Production-Grade Multi-Tenant Knowledge Base (RAG) Documentation

## 1. Overview & Architecture

The SharyX Voice AI Knowledge Base (RAG) system provides high-performance, multi-tenant document indexing and real-time semantic vector retrieval directly integrated with the voice AI tool-calling pipeline.

### System Architecture
```
Caller (WebCall / Telephony)
   │
   ▼
Audio Stream & STT Transcription
   │
   ▼
LLM Tool Router (Gemini) ──[Decides tool]──► `knowledge_search` Tool
                                                   │
                                                   ▼
                                         `KnowledgeBaseService`
                                                   │
                                         ┌─────────┴─────────┐
                                         ▼                   ▼
                                 Query Embedding       Qdrant Vector DB
                                 (384-dim normalized) (Metadata Filters)
                                         │                   │
                                         └─────────┬─────────┘
                                                   ▼
                                        Confidence Gate (>= 0.70)
                                                   │
                                                   ▼
                                        Context Token Budget (< 2500)
                                                   │
                                                   ▼
                                     LLM Spoken Answer & TTS Output
```

---

## 2. Data Model & Database Schema

### Relational Entities (SQLite / PostgreSQL)
1. **`KnowledgeBase`**: Logical document collection owned by a tenant.
   - `id` (UUID string, PK)
   - `tenant_id` (String, Indexed)
   - `name`, `description`, `status`, `created_at`, `updated_at`

2. **`Document`**: Single ingested document file.
   - `id` (UUID string, PK)
   - `knowledge_base_id` (FK to `KnowledgeBase`)
   - `tenant_id` (String, Indexed)
   - `filename`, `original_filename`, `mime_type`, `size_bytes`, `checksum` (SHA-256)
   - `storage_path`, `status` (`uploaded` | `processing` | `indexed` | `failed` | `deleted`)
   - `version`, `language`, `page_count`, `chunk_count`, `error_message`, `created_at`, `updated_at`

3. **`DocumentChunk`**: Structure-aware text snippet with embedding vectors.
   - `id` (UUID string, PK)
   - `document_id` (FK to `Document`)
   - `tenant_id` (String, Mandatory Filter)
   - `chunk_index`, `content`, `page_number`, `section_title`, `token_count`, `content_hash`, `metadata`

---

## 3. Document Ingestion Pipeline

Ingestion occurs **completely asynchronously** outside live voice calls via controlled worker queues (`INGESTION_MAX_CONCURRENCY=2`):

```
File Upload -> Validation -> Checksum (SHA-256) -> Duplicate Detection
   -> Text Parsing -> Structure-Aware Chunking -> Embedding Generation
   -> Qdrant Vector Upsert -> Metadata DB Persistence -> Status INDEXED
```

### Supported Document Parsers:
- **PDF**: `PDFParser` (page-by-page extraction via `pypdf`)
- **DOCX**: `DocxParser` (paragraph and XML structure extraction via `python-docx`)
- **TXT & Markdown**: `TextParser`, `MarkdownParser` (heading & section splitters)
- **CSV & JSON**: `CSVParser`, `JSONParser` (header key-value formatting)
- **HTML**: `HTMLParser` (DOM clean & text extraction via `BeautifulSoup`)

---

## 4. RAG Retrieval & Tool Calling Contract

### `knowledge_search` Tool Schema
```json
{
  "name": "knowledge_search",
  "description": "Search the configured agent knowledge base for accurate company, product, policy, FAQ, documentation, and business information.",
  "parameters": {
    "type": "object",
    "properties": {
      "query": {
        "type": "string",
        "description": "The user's knowledge question rewritten as a concise semantic search query."
      },
      "top_k": {
        "type": "integer",
        "minimum": 1,
        "maximum": 10
      },
      "category": {
        "type": "string"
      }
    },
    "required": ["query"]
  }
}
```

---

## 5. Security & Multi-Tenant Data Isolation

1. **Mandatory Tenant Filtering**: Every Qdrant vector search and metadata query **MUST** enforce `tenant_id` metadata filtering. Global vector searches are explicitly forbidden.
2. **Prompt Injection Protection**: Retrieved document chunks are treated as **UNTRUSTED DATA**. System prompt rules prevent execution of embedded instructions.
3. **Secrets & PII Redaction**: Logs do not write full raw document contents or sensitive credentials.

---

## 6. Configuration & Environment Variables

| Variable | Default Value | Description |
|---|---|---|
| `KB_ENABLED` | `true` | Enables or disables Knowledge Base features |
| `VECTOR_DB` | `qdrant` | Vector store backend (`qdrant`) |
| `QDRANT_URL` | `http://localhost:6333` | Qdrant gRPC/HTTP endpoint |
| `KB_TOP_K` | `5` | Maximum top candidate chunks |
| `KB_MIN_SCORE` | `0.70` | Minimum similarity score confidence gate |
| `KB_MAX_CONTEXT_TOKENS` | `2500` | Context token budget limit |
| `EMBEDDING_PROVIDER` | `auto` | Embedding provider (`sentence-transformers` / `auto` / `hash`) |
| `INGESTION_MAX_CONCURRENCY` | `2` | Max concurrent background document indexers |

---

## 7. REST API Endpoints

- `POST /api/v1/knowledge-bases`: Create Knowledge Base
- `GET /api/v1/knowledge-bases`: List Knowledge Bases for tenant
- `GET /api/v1/knowledge-bases/{kb_id}`: Get Knowledge Base details
- `PATCH /api/v1/knowledge-bases/{kb_id}`: Update Knowledge Base metadata
- `DELETE /api/v1/knowledge-bases/{kb_id}`: Delete Knowledge Base
- `POST /api/v1/knowledge-bases/{kb_id}/documents`: Upload document
- `GET /api/v1/knowledge-bases/{kb_id}/documents`: List documents
- `GET /api/v1/knowledge-bases/{kb_id}/documents/{document_id}`: Get document status
- `DELETE /api/v1/knowledge-bases/{kb_id}/documents/{document_id}`: Delete document
- `POST /api/v1/knowledge-bases/{kb_id}/documents/{document_id}/reindex`: Reindex document
- `POST /api/v1/knowledge-bases/{kb_id}/search`: Non-voice test endpoint
- `GET /api/v1/knowledge-bases/health`: System health & metrics
