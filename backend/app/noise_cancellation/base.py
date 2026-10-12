from abc import ABC, abstractmethod
from typing import Dict, Any


class BaseNoiseSuppressor(ABC):
    """Abstract Base Class for noise suppression algorithms (RNNoise, WebRTC NS, Passthrough, DeepFilterNet)."""

    def __init__(self, name: str, description: str):
        self.name = name
        self.description = description
        self.processed_frames_count = 0
        self.total_processing_ms = 0.0

    @abstractmethod
    def process(self, pcm_bytes: bytes, sample_rate: int = 16000) -> bytes:
        """Processes an incoming raw PCM audio frame incrementally and returns noise-suppressed PCM bytes."""
        pass

    def get_metrics(self) -> Dict[str, Any]:
        """Returns processing metrics including latency and frame count."""
        avg_ms = (self.total_processing_ms / self.processed_frames_count) if self.processed_frames_count > 0 else 0.0
        return {
            "algorithm": self.name,
            "description": self.description,
            "processed_frames": self.processed_frames_count,
            "total_processing_ms": round(self.total_processing_ms, 2),
            "avg_latency_ms": round(avg_ms, 3),
        }
