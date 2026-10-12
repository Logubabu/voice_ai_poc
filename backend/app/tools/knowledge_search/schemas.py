from pydantic import BaseModel, Field
from typing import Optional


class KnowledgeSearchToolInput(BaseModel):
    query: str = Field(..., description="The user's knowledge question rewritten as a concise semantic search query.")
    top_k: int = Field(5, ge=1, le=10, description="Top K candidate chunks to retrieve")
    category: Optional[str] = Field(None, description="Optional document category filter")
