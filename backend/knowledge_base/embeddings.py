import asyncio
import hashlib
import math
import re
from abc import ABC, abstractmethod
from typing import List

from knowledge_base.exceptions import EmbeddingError
from app.utils.logging import logger


class EmbeddingProvider(ABC):
    """Abstract interface for text embedding providers."""

    @abstractmethod
    async def embed_documents(self, texts: List[str]) -> List[List[float]]:
        """Generates embedding vectors for a list of document chunk texts."""
        pass

    @abstractmethod
    async def embed_query(self, query: str) -> List[float]:
        """Generates an embedding vector for a single search query."""
        pass

    @property
    @abstractmethod
    def vector_dimension(self) -> int:
        """Returns vector dimension size."""
        pass


class DeterministicHashEmbeddingProvider(EmbeddingProvider):
    """High-speed zero-dependency deterministic hash embedding provider (384-dim normalized) for fast testing and lightweight deployments."""

    def __init__(self, dim: int = 384):
        self._dim = dim

    def _hash_vector(self, text: str) -> List[float]:
        vec = [0.0] * self._dim
        words = re.findall(r"\w+", text.lower())
        if not words:
            return vec

        for word in words:
            # Generate deterministic bucket index for word
            h = hashlib.md5(word.encode("utf-8")).digest()
            idx = int.from_bytes(h[:4], "big") % self._dim
            vec[idx] += 1.0

        # L2 Normalize
        norm = math.sqrt(sum(x * x for x in vec))
        if norm > 0:
            vec = [x / norm for x in vec]
        return vec

    async def embed_documents(self, texts: List[str]) -> List[List[float]]:
        return [self._hash_vector(t) for t in texts]

    async def embed_query(self, query: str) -> List[float]:
        return self._hash_vector(query)

    @property
    def vector_dimension(self) -> int:
        return self._dim


class SentenceTransformersEmbeddingProvider(EmbeddingProvider):
    """SentenceTransformers embedding provider using local lightweight models."""

    def __init__(self, model_name: str = "all-MiniLM-L6-v2"):
        self.model_name = model_name
        self._model = None
        self._dim = 384
        self._init_model()

    def _init_model(self):
        try:
            from sentence_transformers import SentenceTransformer
            self._model = SentenceTransformer(self.model_name)
            self._dim = self._model.get_sentence_embedding_dimension()
            logger.info(f"[EMBEDDING] SentenceTransformer model '{self.model_name}' loaded (dim: {self._dim})")
        except Exception as e:
            logger.warning(f"[EMBEDDING] Could not load SentenceTransformer '{self.model_name}' ({e}). Falling back to DeterministicHashEmbeddingProvider.")
            self._model = None

    async def embed_documents(self, texts: List[str]) -> List[List[float]]:
        if not self._model:
            fallback = DeterministicHashEmbeddingProvider(dim=self._dim)
            return await fallback.embed_documents(texts)

        try:
            def _op():
                embeddings = self._model.encode(texts, convert_to_numpy=True, normalize_embeddings=True)
                return embeddings.tolist()
            return await asyncio.to_thread(_op)
        except Exception as e:
            logger.error(f"[EMBEDDING][ERROR] SentenceTransformers embedding failed: {e}")
            raise EmbeddingError(f"Embedding generation failed: {e}")

    async def embed_query(self, query: str) -> List[float]:
        res = await self.embed_documents([query])
        return res[0]

    @property
    def vector_dimension(self) -> int:
        return self._dim


class EmbeddingProviderFactory:
    """Factory to instantiate configured EmbeddingProvider."""

    @staticmethod
    def create_provider(provider_type: str = "auto", model_name: str = "all-MiniLM-L6-v2") -> EmbeddingProvider:
        p_type = provider_type.lower()
        if p_type in ("sentence-transformers", "local", "auto"):
            try:
                __import__("sentence_transformers")
                return SentenceTransformersEmbeddingProvider(model_name=model_name)
            except ImportError:
                logger.info("[EMBEDDING] sentence_transformers library not installed. Using DeterministicHashEmbeddingProvider.")
                return DeterministicHashEmbeddingProvider()

        if p_type == "hash":
            return DeterministicHashEmbeddingProvider()

        logger.info(f"[EMBEDDING] Provider '{provider_type}' defaulting to DeterministicHashEmbeddingProvider.")
        return DeterministicHashEmbeddingProvider()
