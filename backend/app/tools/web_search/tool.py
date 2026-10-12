from typing import Dict, Any
from pipecat.adapters.schemas.function_schema import FunctionSchema

from app.tools.base import BaseTool
from app.tools.web_search.schemas import WEB_SEARCH_TOOL_SCHEMA
from app.tools.web_search.service import web_search_service
from app.utils.logging import logger


class WebSearchTool(BaseTool):
    """Production-grade WebSearchTool implementing BaseTool interface for live web search."""

    def __init__(self, timeout: float = 8.0):
        super().__init__(
            name="web_search",
            description="Search the live internet for current or externally verifiable information.",
            timeout=timeout,
            permissions="public",
        )

    def get_schema(self, handler: Any = None) -> FunctionSchema:
        schema = FunctionSchema(
            name=self.name,
            description=self.description,
            properties=WEB_SEARCH_TOOL_SCHEMA.properties,
            required=WEB_SEARCH_TOOL_SCHEMA.required,
            handler=handler,
        )
        return schema

    async def execute(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Executes live web search query asynchronously and returns normalized result."""
        query = args.get("query", "").strip()
        max_results = args.get("max_results", 5)

        # Enforce range limits on max_results (1 to 10)
        try:
            max_results = max(1, min(10, int(max_results)))
        except (ValueError, TypeError):
            max_results = 5

        logger.info(f"[TOOL-WEB-SEARCH] Executing tool query: '{query}' (max_results={max_results})")
        try:
            return await web_search_service.execute_search(
                query=query,
                max_results=max_results,
                timeout=self.timeout,
            )
        except Exception as e:
            logger.exception(f"[TOOL-WEB-SEARCH][ERROR] Web search execution failed: {e}")
            return {
                "success": False,
                "tool": "web_search",
                "count": 0,
                "results": [],
                "sources": [],
                "error": f"Web search provider error: {str(e)}",
                "message": "Web search is currently unavailable.",
            }
