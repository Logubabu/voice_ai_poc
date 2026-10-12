from pipecat.adapters.schemas.function_schema import FunctionSchema

WEB_SEARCH_TOOL_SCHEMA = FunctionSchema(
    name="web_search",
    description="Search the live internet for current or externally verifiable information.",
    properties={
        "query": {
            "type": "string",
            "description": "Search query string optimized for live web search, removing conversational filler while preserving entities, locations, dates, and intent.",
        },
        "max_results": {
            "type": "integer",
            "description": "Maximum number of search results to return (between 1 and 10, default 5).",
            "minimum": 1,
            "maximum": 10,
        },
    },
    required=["query"],
)
