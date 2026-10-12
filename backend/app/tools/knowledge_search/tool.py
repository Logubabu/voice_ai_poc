from typing import Dict, Any
from pipecat.adapters.schemas.function_schema import FunctionSchema

from app.tools.base import BaseTool
from knowledge_base.service import kb_service
from app.utils.logging import logger


class KnowledgeSearchTool(BaseTool):
    """Production-grade KnowledgeSearchTool implementing BaseTool interface for RAG vector search."""

    def __init__(self, timeout: float = 5.0):
        super().__init__(
            name="knowledge_search",
            description="Search the configured agent knowledge base for accurate company, product, policy, FAQ, documentation, and business information. Use this tool whenever the user's question depends on internal or configured business knowledge.",
            timeout=timeout,
            permissions="public",
        )

    def get_schema(self, handler: Any = None) -> FunctionSchema:
        properties = {
            "query": {
                "type": "string",
                "description": "The user's knowledge question rewritten as a concise semantic search query.",
            },
            "top_k": {
                "type": "integer",
                "minimum": 1,
                "maximum": 10,
                "description": "Number of top matching chunks to retrieve.",
            },
            "category": {
                "type": "string",
                "description": "Optional category filter.",
            },
        }
        return FunctionSchema(
            name=self.name,
            description=self.description,
            properties=properties,
            required=["query"],
            handler=handler,
        )

    async def execute(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Executes knowledge base semantic search asynchronously and returns structured dictionary result."""
        query = str(args.get("query", "")).strip()
        top_k = args.get("top_k", 5)
        category = args.get("category")
        tenant_id = args.get("tenant_id") or getattr(args, "tenant_id", "default_tenant")
        kb_id = args.get("knowledge_base_id") or getattr(args, "knowledge_base_id", None)

        try:
            top_k = max(1, min(10, int(top_k)))
        except (ValueError, TypeError):
            top_k = 5

        logger.info(f"[TOOL-KB-SEARCH] Executing query: '{query}' (tenant: '{tenant_id}', kb_id: '{kb_id}', top_k={top_k})")

        try:
            search_res = await kb_service.search(
                query=query,
                tenant_id=tenant_id,
                knowledge_base_id=kb_id,
                top_k=top_k,
                category=category,
            )
            accuracy_pts = search_res.confidence * 100.0
            logger.info(
                f"[TOOL-KB-SEARCH][ACCURACY] Query: '{query}' | Found: {search_res.found} | "
                f"Overall Match Accuracy: {accuracy_pts:.1f} pts (confidence={search_res.confidence:.4f}) | "
                f"Chunks Count: {len(search_res.results)}"
            )
            for idx, res_item in enumerate(search_res.results, 1):
                chunk_pts = res_item.score * 100.0
                logger.info(
                    f"[TOOL-KB-SEARCH][ACCURACY-CHUNK #{idx}] Doc: '{res_item.document_name}' | "
                    f"Chunk Accuracy Score: {chunk_pts:.1f} pts ({res_item.score:.4f}) | "
                    f"Chunk ID: '{res_item.chunk_id}'"
                )
            return search_res.model_dump()
        except Exception as e:
            logger.exception(f"[TOOL-KB-SEARCH][ERROR] Knowledge base search failed: {e}")
            return {
                "success": False,
                "found": False,
                "confidence": 0.0,
                "error_code": "KNOWLEDGE_BASE_UNAVAILABLE",
                "message": "I'm unable to access that information right now.",
                "results": [],
            }
