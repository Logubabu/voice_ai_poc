import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

from app.tools.registry import ToolRegistry
from app.tools.router import ToolRouter
from app.tools.web_search.service import WebSearchService
from app.tools.web_search.tool import WebSearchTool
from app.services.search.provider import SearchResult, SearchProvider


class DummySearchProvider(SearchProvider):
    def __init__(self, mock_results=None, raise_error=False):
        self.mock_results = mock_results or [
            SearchResult(
                title="Bitcoin Price USD",
                url="https://finance.yahoo.com/quote/BTC-USD",
                snippet="Bitcoin current price is $95,000 USD today.",
                source="Yahoo Finance",
                published_at="2026-10-08",
            )
        ]
        self.raise_error = raise_error

    async def search(self, query: str, max_results: int = 5, timeout: float = 5.0):
        if self.raise_error:
            raise RuntimeError("Network timeout or DNS failure")
        return self.mock_results


@pytest.mark.asyncio
async def test_tool_registry_registration():
    registry = ToolRegistry()
    tool = WebSearchTool()
    registry.register_tool(tool)
    assert registry.get_tool("web_search") is not None
    schemas = registry.get_function_schemas(enable_web_search=True)
    assert len(schemas) >= 1
    assert any(s.name == "web_search" for s in schemas)


@pytest.mark.asyncio
async def test_web_search_service_success():
    provider = DummySearchProvider()
    service = WebSearchService(provider=provider)
    res = await service.execute_search("current Bitcoin price", max_results=3)
    assert res["success"] is True
    assert res["tool"] == "web_search"
    assert res["count"] == 1
    assert "Bitcoin" in res["results"][0]["snippet"]
    assert len(res["sources"]) == 1


@pytest.mark.asyncio
async def test_web_search_service_failure_resilience():
    provider = DummySearchProvider(raise_error=True)
    service = WebSearchService(provider=provider)
    res = await service.execute_search("latest news", max_results=3)
    assert res["success"] is False
    assert "unavailable" in res["error"]
    assert "message" in res


@pytest.mark.asyncio
async def test_tool_router_turn_limit():
    router = ToolRouter()
    session_id = "test_session_turn_limit"

    # Simulate 3 successful tool calls in the same turn
    _ = await router.route_tool_call("web_search", "call_1", {"query": "Bitcoin price 1"}, session_id=session_id)
    _ = await router.route_tool_call("web_search", "call_2", {"query": "Bitcoin price 2"}, session_id=session_id)
    _ = await router.route_tool_call("web_search", "call_3", {"query": "Bitcoin price 3"}, session_id=session_id)

    # 4th call should be blocked by turn limit (MAX_TOOL_CALLS_PER_TURN = 3)
    res4 = await router.route_tool_call("web_search", "call_4", {"query": "Bitcoin price 4"}, session_id=session_id)
    assert res4["success"] is False
    assert "limit" in res4["error"].lower()


@pytest.mark.asyncio
async def test_tool_router_duplicate_prevention():
    router = ToolRouter()
    session_id = "test_session_duplicate"

    _ = await router.route_tool_call("web_search", "call_1", {"query": "Tesla stock price"}, session_id=session_id)
    res2 = await router.route_tool_call("web_search", "call_2", {"query": "Tesla stock price"}, session_id=session_id)
    assert res2.get("duplicate") is True


@pytest.mark.asyncio
async def test_tool_router_barge_in_cancellation():
    router = ToolRouter()
    session_id = "test_barge_in_session"

    async def slow_execution():
        await asyncio.sleep(5.0)
        return {"success": True}

    # Simulate active task in router
    task = asyncio.create_task(slow_execution())
    router.active_tool_tasks[session_id] = {"call_slow": task}

    # User interrupts speaking -> cancel pending tools
    cancelled = router.cancel_pending_tools(session_id)
    assert cancelled == 1
    await asyncio.sleep(0)
    assert task.cancelled() or task.done()


@pytest.mark.asyncio
async def test_webcall_tool_calling_disabled_flag():
    router = ToolRouter()
    with patch("app.tools.router.config.WEBCALL_TOOL_CALLING_ENABLED", False):
        res = await router.route_tool_call("web_search", "call_1", {"query": "test"}, session_id="test_disabled")
        assert res["success"] is False
        assert "disabled" in res["error"]


@pytest.mark.asyncio
async def test_unregistered_tool_rejection():
    router = ToolRouter()
    res = await router.route_tool_call("execute_shell_command", "call_hacker", {"command": "rm -rf /"}, session_id="test_security")
    assert res["success"] is False
    assert "not registered" in res["error"]


@pytest.mark.asyncio
async def test_handler_supports_function_call_params():
    router = ToolRouter()
    mock_provider = DummySearchProvider(mock_results=[SearchResult(title="BTC", url="https://btc.org", snippet="$65000")])
    with patch("app.tools.web_search.service.create_search_provider", return_value=mock_provider):
        tool = WebSearchTool()
        handler = router.create_handler(tool)

        class MockParams:
            function_name = "web_search"
            tool_call_id = "call_pipecat_1"
            arguments = {"query": "current Bitcoin price USD"}
            llm = MagicMock(session_id="test_params_session")
            result_callback = AsyncMock()

        params = MockParams()
        res = await handler(params)
        assert res["success"] is True
        assert params.result_callback.called


@pytest.mark.asyncio
async def test_pipeline_manager_initialization():
    from app.pipeline import VoicePipelineManager
    from app.config import config as app_cfg
    
    mgr = VoicePipelineManager(app_cfg)
    
    mock_transport = MagicMock()
    mock_transport.input.return_value = MagicMock()
    mock_transport.output.return_value = MagicMock()
    
    with patch("app.pipeline.create_stt_service") as mock_stt, \
         patch("app.pipeline.create_llm_service") as mock_llm, \
         patch("app.pipeline.create_tts_service") as mock_tts, \
         patch("app.pipeline.WorkerRunner") as mock_runner:
        
        mock_stt.return_value = MagicMock()
        mock_llm.return_value = MagicMock()
        mock_tts.return_value = MagicMock()
        mock_runner.return_value.run = AsyncMock()
        
        session = await mgr.start_session(
            session_id="test_pipeline_init",
            transport=mock_transport,
            is_webcall=True,
        )
        assert session["session_id"] == "test_pipeline_init"
        assert session["status"] == "connected"

