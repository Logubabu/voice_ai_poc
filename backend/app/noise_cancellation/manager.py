from typing import Dict, Any
from app.noise_cancellation.base import BaseNoiseSuppressor
from app.noise_cancellation.rnnoise import RNNoiseSuppressor
from app.noise_cancellation.webrtc_ns import WebRTCAPMNoiseSuppressor
from app.utils.logging import logger


class PassthroughSuppressor(BaseNoiseSuppressor):
    """Passthrough suppressor (no filtering applied)."""

    def __init__(self):
        super().__init__(name="Passthrough", description="Direct audio passthrough without noise filtering.")

    def process(self, pcm_bytes: bytes, sample_rate: int = 16000) -> bytes:
        self.processed_frames_count += 1
        return pcm_bytes


class NoiseCancellationManager:
    """Central manager for selecting and executing noise cancellation algorithms."""

    def __init__(self, default_provider: str = "rnnoise"):
        self.suppressors: Dict[str, BaseNoiseSuppressor] = {
            "passthrough": PassthroughSuppressor(),
            "rnnoise": RNNoiseSuppressor(),
            "webrtc": WebRTCAPMNoiseSuppressor(),
            "deepfilternet": RNNoiseSuppressor(aggressiveness="high"),
        }
        self.active_key = default_provider.lower() if default_provider.lower() in self.suppressors else "rnnoise"
        logger.info(f"[NOISE-CANCEL-MANAGER] Initialized with active algorithm: '{self.active_key}'")

    def get_active_suppressor(self) -> BaseNoiseSuppressor:
        return self.suppressors.get(self.active_key, self.suppressors["rnnoise"])

    def set_active_algorithm(self, algorithm_name: str) -> BaseNoiseSuppressor:
        key = algorithm_name.lower().replace(" ", "").replace("_", "")
        if "rnnoise" in key:
            key = "rnnoise"
        elif "webrtc" in key:
            key = "webrtc"
        elif "pass" in key or "disable" in key:
            key = "passthrough"
        elif "deep" in key or "filter" in key:
            key = "deepfilternet"

        if key in self.suppressors:
            self.active_key = key
            logger.info(f"[NOISE-CANCEL-MANAGER] Switched active algorithm to '{self.active_key}'")
            return self.suppressors[key]
        
        logger.warning(f"[NOISE-CANCEL-MANAGER] Unknown algorithm '{algorithm_name}'. Keeping '{self.active_key}'")
        return self.get_active_suppressor()

    def process_frame(self, pcm_bytes: bytes, sample_rate: int = 16000) -> bytes:
        suppressor = self.get_active_suppressor()
        return suppressor.process(pcm_bytes, sample_rate)

    def get_status(self) -> Dict[str, Any]:
        suppressor = self.get_active_suppressor()
        return {
            "active_algorithm": suppressor.name,
            "description": suppressor.description,
            "metrics": suppressor.get_metrics(),
            "available_algorithms": list(self.suppressors.keys()),
        }


noise_cancel_manager = NoiseCancellationManager()
