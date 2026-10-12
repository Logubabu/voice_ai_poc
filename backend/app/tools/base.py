from abc import ABC, abstractmethod
from typing import Dict, Any
from pipecat.adapters.schemas.function_schema import FunctionSchema


class BaseTool(ABC):
    """Abstract Base Class for modular Voice AI tools."""

    def __init__(self, name: str, description: str, timeout: float = 8.0, permissions: str = "public"):
        self.name = name
        self.description = description
        self.timeout = timeout
        self.permissions = permissions

    @abstractmethod
    def get_schema(self, handler: Any = None) -> FunctionSchema:
        """Returns the Pipecat FunctionSchema definition for LLM tool advertising."""
        pass

    @abstractmethod
    async def execute(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Executes tool logic asynchronously and returns structured dictionary result."""
        pass
