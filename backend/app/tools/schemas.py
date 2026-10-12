from typing import Dict, Any, List, Optional
from pipecat.adapters.schemas.function_schema import FunctionSchema


def create_function_schema(
    name: str,
    description: str,
    properties: Dict[str, Any],
    required: Optional[List[str]] = None,
    handler: Any = None,
) -> FunctionSchema:
    """Helper factory for creating validated FunctionSchema objects."""
    return FunctionSchema(
        name=name,
        description=description,
        properties=properties,
        required=required or [],
        handler=handler,
    )
