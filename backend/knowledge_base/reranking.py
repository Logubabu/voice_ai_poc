import asyncio
import math
from abc import ABC, abstractmethod
from typing import List, Dict, Any

from app.utils.logging import logger


class Reranker(ABC):
    @abstractmethod
    async def rerank(self, query: str, candidate_chunks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Reranks retrieved candidate chunks against user query and returns updated list with revised scores."""
        pass


class PassThroughReranker(Reranker):
    """Default high-speed pass-through reranker using original vector similarity scores."""

    async def rerank(self, query: str, candidate_chunks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        return candidate_chunks


class CrossEncoderReranker(Reranker):
    """Optional Cross-Encoder reranker using sentence-transformers CrossEncoder."""

    def __init__(self, model_name: str = "cross-encoder/ms-marco-MiniLM-L-6-v2"):
        self.model_name = model_name
        self._model = None
        self._init_model()

    def _init_model(self):
        try:
            from sentence_transformers import CrossEncoder
            self._model = CrossEncoder(self.model_name)
            logger.info(f"[RERANKER] CrossEncoder '{self.model_name}' loaded.")
        except Exception as e:
            logger.warning(f"[RERANKER] Failed to load CrossEncoder '{self.model_name}' ({e}). Using PassThroughReranker.")
            self._model = None

    async def rerank(self, query: str, candidate_chunks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        if not candidate_chunks or not self._model:
            return candidate_chunks

        try:
            pairs = [[query, chunk["payload"].get("content", "")] for chunk in candidate_chunks]
            def _op():
                scores = self._model.predict(pairs)
                return scores
            scores = await asyncio.to_thread(_op)

            reranked = []
            for score, chunk in zip(scores, candidate_chunks):
                chunk_copy = dict(chunk)
                # Sigmoid float normalization
                norm_score = 1.0 / (1.0 + math.exp(-float(score))) if hasattr(score, "item") else float(score)
                chunk_copy["score"] = round(norm_score, 4)
                reranked.append(chunk_copy)

            reranked.sort(key=lambda x: x["score"], reverse=True)
            return reranked
        except Exception as e:
            logger.warning(f"[RERANKER] Reranking failed ({e}). Returning original candidates.")
            return candidate_chunks
