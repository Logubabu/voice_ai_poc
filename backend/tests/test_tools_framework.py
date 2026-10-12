from app.tools.registry import ToolRegistry
from app.tools.web_search import WebSearchTool


def test_tool_registry():
    registry = ToolRegistry()
    tool = registry.get_tool("web_search")
    assert tool is not None
    assert isinstance(tool, WebSearchTool)

    schemas = registry.get_function_schemas()
    assert len(schemas) >= 1
    assert schemas[0].name == "web_search"
    assert schemas[0].handler is not None
