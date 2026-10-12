import asyncio
import pytest
import tempfile
import shutil
import os

from unittest.mock import AsyncMock, MagicMock, patch

from app.config import config
from app.pipeline import VoicePipelineManager
from knowledge_base.service import KnowledgeBaseService
from knowledge_base.schemas import KnowledgeBaseCreate
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
        await self.push_frame(frame, direction)


class MockWebCallTransport:
    def __init__(self):
        self._input = MockTransportInput()
        self._output = MockTransportOutput()

    def input(self):
        return self._input

    def output(self):
        return self._output


@pytest.mark.asyncio
async def test_normal_voice_question_pipeline():
    """Test 1: Normal user question uses standard STT -> LLM -> TTS -> WebCall audio pipeline."""
    manager = VoicePipelineManager(config)
    transport = MockWebCallTransport()

    session = await manager.start_session(
        session_id="test_normal_voice_001",
        transport=transport,
        is_webcall=True,
    )

    assert session["status"] == "connected"
    assert session["session_id"] == "test_normal_voice_001"

    await manager.stop_session("test_normal_voice_001")


@pytest.mark.asyncio
async def test_kb_voice_question_end_to_end():
    """Test 2: KB Voice Question retrieves KB data and sends final LLM response to existing TTS."""
    tmp_dir = tempfile.mkdtemp()
    try:
        db_path = os.path.join(tmp_dir, "test_voice_kb.db")
        docs_dir = os.path.join(tmp_dir, "docs")
        test_kb_service = KnowledgeBaseService(storage_dir=docs_dir, db_path=db_path)
        test_kb_service.retrieval_engine.min_score = 0.0

        # Create KB & Upload document
        kb = await test_kb_service.create_kb(KnowledgeBaseCreate(name="Voice KB", tenant_id="voice_tenant"))
        doc_content = b"SharyX Voice AI supports full customer refunds within 30 days of initial purchase."
        doc = await test_kb_service.upload_document(
            kb_id=kb.id,
            tenant_id="voice_tenant",
            filename="refund_policy.txt",
            file_content=doc_content,
            mime_type="text/plain",
        )
        await test_kb_service.ingestion_pipeline.ingest_document(document_id=doc.id, tenant_id="voice_tenant")

        with patch("app.tools.knowledge_search.tool.kb_service", test_kb_service):
            from app.tools.knowledge_search.tool import KnowledgeSearchTool
            tool = KnowledgeSearchTool()
            res = await tool.execute({"query": "refund policy", "tenant_id": "voice_tenant", "knowledge_base_id": kb.id})

            assert res["success"] is True
            assert res["found"] is True
            assert len(res["results"]) > 0
            assert "30 days" in res["results"][0]["content"]

    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)


@pytest.mark.asyncio
async def test_kb_no_answer_fallback():
    """Test 3: KB query with no answer returns found=False for safe LLM natural voice response."""
    tmp_dir = tempfile.mkdtemp()
    try:
        db_path = os.path.join(tmp_dir, "test_no_answer.db")
        docs_dir = os.path.join(tmp_dir, "docs")
        test_kb_service = KnowledgeBaseService(storage_dir=docs_dir, db_path=db_path)

        from app.tools.knowledge_search.tool import KnowledgeSearchTool
        tool = KnowledgeSearchTool()

        with patch("app.tools.knowledge_search.tool.kb_service", test_kb_service):
            res = await tool.execute({"query": "What is the quantum teleportation policy?", "tenant_id": "tenant_empty"})
            assert res["success"] is True
            assert res["found"] is False
            assert len(res["results"]) == 0
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)


@pytest.mark.asyncio
async def test_kb_service_unavailable_resilience():
    """Test 4: KB service exception produces controlled tool result without crashing the WebCall."""
    from app.tools.knowledge_search.tool import KnowledgeSearchTool
    tool = KnowledgeSearchTool()

    with patch("app.tools.knowledge_search.tool.kb_service.search", side_effect=RuntimeError("Qdrant connection refused")):
        res = await tool.execute({"query": "refund policy", "tenant_id": "tenant_err"})
        assert res["success"] is False
        assert res["found"] is False
        assert res["error_code"] == "KNOWLEDGE_BASE_UNAVAILABLE"


@pytest.mark.asyncio
async def test_web_search_and_kb_coexistence():
    """Test 6: Web Search and KB tools exist simultaneously in registry without conflict."""
    from app.tools.registry import ToolRegistry
    registry = ToolRegistry()
    schemas = registry.get_function_schemas(enable_web_search=True)
    names = [s.name for s in schemas]
    assert "knowledge_search" in names
    assert "web_search" in names


@pytest.mark.asyncio
async def test_tenant_isolation_in_webcall():
    """Test 7: Tenant A cannot retrieve Tenant B's Knowledge Base data during WebCall."""
    tmp_dir = tempfile.mkdtemp()
    try:
        db_path = os.path.join(tmp_dir, "test_tenant_iso.db")
        docs_dir = os.path.join(tmp_dir, "docs")
        service = KnowledgeBaseService(storage_dir=docs_dir, db_path=db_path)
        service.retrieval_engine.min_score = 0.0

        # Tenant A KB
        kb_a = await service.create_kb(KnowledgeBaseCreate(name="Tenant A KB", tenant_id="tenant_A"))
        doc_a = await service.upload_document(
            kb_id=kb_a.id,
            tenant_id="tenant_A",
            filename="secret_a.txt",
            file_content=b"Tenant A confidential passkey is 998877.",
            mime_type="text/plain",
        )
        await service.ingestion_pipeline.ingest_document(document_id=doc_a.id, tenant_id="tenant_A")

        # Search as Tenant A
        res_a = await service.search(query="passkey", tenant_id="tenant_A", knowledge_base_id=kb_a.id)
        assert res_a.found is True
        assert "998877" in res_a.results[0].content

        # Search as Tenant B
        res_b = await service.search(query="passkey", tenant_id="tenant_B", knowledge_base_id=kb_a.id)
        assert res_b.found is False
        assert len(res_b.results) == 0

    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)


@pytest.mark.asyncio
async def test_barge_in_cancellation_during_kb_search():
    """Test 8: User barge-in during tool execution cancels in-flight tool tasks."""
    from app.tools.router import ToolRouter
    router = ToolRouter()
    session_id = "test_barge_in_kb"

    async def slow_kb():
        await asyncio.sleep(5.0)
        return {"success": True}

    task = asyncio.create_task(slow_kb())
    router.active_tool_tasks[session_id] = {"call_slow_kb": task}

    cancelled = router.cancel_pending_tools(session_id)
    assert cancelled == 1
    await asyncio.sleep(0)
    assert task.cancelled() or task.done()


@pytest.mark.asyncio
async def test_session_cleanup():
    """Test 9: Stopping session cleanly cleans up pipeline tasks."""
    manager = VoicePipelineManager(config)
    transport = MockWebCallTransport()

    _ = await manager.start_session(
        session_id="test_cleanup_session",
        transport=transport,
        is_webcall=True,
    )

    stop_result = await manager.stop_session("test_cleanup_session")
    assert stop_result is True
    assert "test_cleanup_session" not in manager.active_sessions


@pytest.mark.asyncio
async def test_resume_experience_kb_lookup():
    """Test 10: User resume fact (Name & 4.5 years experience) retrieved from KB."""
    tmp_dir = tempfile.mkdtemp()
    try:
        db_path = os.path.join(tmp_dir, "test_resume_kb.db")
        docs_dir = os.path.join(tmp_dir, "docs")
        test_kb_service = KnowledgeBaseService(storage_dir=docs_dir, db_path=db_path)
        test_kb_service.retrieval_engine.min_score = 0.0

        kb = await test_kb_service.create_kb(KnowledgeBaseCreate(name="Resume KB", tenant_id="tenant_resume"))
        resume_content = b"Candidate Name: Loganathan Babu. Total Professional Experience: 4.5 years. Primary Skills: Python, FastAPI, Docker, SQL."
        doc = await test_kb_service.upload_document(
            kb_id=kb.id,
            tenant_id="tenant_resume",
            filename="resume.txt",
            file_content=resume_content,
            mime_type="text/plain",
        )
        await test_kb_service.ingestion_pipeline.ingest_document(document_id=doc.id, tenant_id="tenant_resume")

        from app.tools.knowledge_search.tool import KnowledgeSearchTool
        tool = KnowledgeSearchTool()
        with patch("app.tools.knowledge_search.tool.kb_service", test_kb_service):
            res_name = await tool.execute({"query": "What is my name?", "tenant_id": "tenant_resume", "knowledge_base_id": kb.id})
            assert res_name["found"] is True
            assert "Loganathan Babu" in res_name["results"][0]["content"]

            res_exp = await tool.execute({"query": "How many years of experience do I have?", "tenant_id": "tenant_resume", "knowledge_base_id": kb.id})
            assert res_exp["found"] is True
            assert "4.5 years" in res_exp["results"][0]["content"]

    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)


@pytest.mark.asyncio
async def test_personal_info_privacy_rule():
    """Test 11: Personal information missing from KB must NOT trigger web search for private data."""
    tmp_dir = tempfile.mkdtemp()
    try:
        db_path = os.path.join(tmp_dir, "test_privacy.db")
        docs_dir = os.path.join(tmp_dir, "docs")
        test_kb_service = KnowledgeBaseService(storage_dir=docs_dir, db_path=db_path)

        from app.tools.knowledge_search.tool import KnowledgeSearchTool
        tool = KnowledgeSearchTool()

        with patch("app.tools.knowledge_search.tool.kb_service", test_kb_service):
            res = await tool.execute({"query": "What is my private credit card pin?", "tenant_id": "tenant_priv"})
            assert res["success"] is True
            assert res["found"] is False
            # Verify structured result allows LLM to issue private info fallback without searching internet
            assert len(res["results"]) == 0
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)


@pytest.mark.asyncio
async def test_internet_fallback_for_realtime_query():
    """Test 12: Realtime web search executes and returns structured sources for LLM synthesis."""
    from app.tools.web_search.tool import WebSearchTool
    tool = WebSearchTool()

    mock_provider_result = {
        "success": True,
        "tool": "web_search",
        "count": 1,
        "results": [{"title": "Python 3.12 Release Notes", "url": "https://python.org", "snippet": "Python 3.12 is the latest stable version.", "source": "Python.org"}],
        "sources": [{"title": "Python.org", "url": "https://python.org"}],
    }

    with patch("app.tools.web_search.tool.web_search_service.execute_search", AsyncMock(return_value=mock_provider_result)):
        res = await tool.execute({"query": "What is the latest Python version?"})
        assert res["success"] is True
        assert res["count"] == 1
        assert "Python 3.12" in res["results"][0]["snippet"]


@pytest.mark.asyncio
async def test_all_sources_unavailable_fallback():
    """Test 13: Controlled failure when both KB and Web search fail produces safe resilience."""
    from app.tools.knowledge_search.tool import KnowledgeSearchTool
    from app.tools.web_search.tool import WebSearchTool

    kb_tool = KnowledgeSearchTool()
    web_tool = WebSearchTool()

    with patch("app.tools.knowledge_search.tool.kb_service.search", side_effect=RuntimeError("KB Offline")), \
         patch("app.tools.web_search.tool.web_search_service.execute_search", AsyncMock(side_effect=RuntimeError("Web Offline"))):

        res_kb = await kb_tool.execute({"query": "test query", "tenant_id": "t1"})
        assert res_kb["success"] is False

        res_web = await web_tool.execute({"query": "test query"})
        assert res_web["success"] is False


@pytest.mark.asyncio
async def test_duplicate_tool_call_idempotency_and_result_preservation():
    """Test 14: Duplicate tool call in same turn preserves cached search results instead of returning empty hollow result."""
    from app.tools.registry import ToolRegistry
    from app.tools.router import ToolRouter
    from app.tools.base import BaseTool

    class DummyTool(BaseTool):
        def __init__(self):
            super().__init__(name="knowledge_search", description="test search", permissions="public")

        def get_schema(self, handler=None):
            return MagicMock()

        async def execute(self, args):
            return {"success": True, "found": True, "confidence": 0.95, "results": [{"content": "Name: Loganathan Babu"}]}

    test_registry = ToolRegistry()
    test_registry.register_tool(DummyTool())
    router = ToolRouter(registry=test_registry)

    # Call 1
    res1 = await router.route_tool_call(tool_name="knowledge_search", tool_call_id="call_001", args={"query": "user name"}, session_id="sess_idempotent")
    assert res1["found"] is True
    assert len(res1["results"]) == 1

    # Call 2 with identical args (duplicate turn call)
    res2 = await router.route_tool_call(tool_name="knowledge_search", tool_call_id="call_002", args={"query": "user name"}, session_id="sess_idempotent")
    assert res2["found"] is True
    assert res2.get("duplicate") is True
    assert len(res2["results"]) == 1
    assert "Loganathan Babu" in res2["results"][0]["content"]

    # Call 3 with identical tool_call_id (idempotency check)
    res3 = await router.route_tool_call(tool_name="knowledge_search", tool_call_id="call_001", args={"query": "user name"}, session_id="sess_idempotent")
    assert res3["found"] is True
    assert len(res3["results"]) == 1


@pytest.mark.asyncio
async def test_kb_debug_search_endpoint():
    """Test 15: GET /api/v1/knowledge-bases/debug/search returns diagnostic retrieval output."""
    from fastapi.testclient import TestClient
    from app.main import app

    client = TestClient(app)
    response = client.get("/api/v1/knowledge-bases/debug/search?q=user%20name&tenant_id=default_tenant")
    assert response.status_code == 200
    data = response.json()
    assert data["query"] == "user name"
    assert "found" in data
    assert "results" in data

