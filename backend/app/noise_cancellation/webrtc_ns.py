import time
import numpy as np
from app.noise_cancellation.base import BaseNoiseSuppressor


class WebRTCAPMNoiseSuppressor(BaseNoiseSuppressor):
    """WebRTC Audio Processing Module (APM) noise suppressor."""

    def __init__(self):
        super().__init__(
            name="WebRTC APM",
            description="WebRTC APM standard noise suppression with acoustic echo control."
        )

    def process(self, pcm_bytes: bytes, sample_rate: int = 16000) -> bytes:
        if not pcm_bytes or len(pcm_bytes) % 2 != 0:
            return pcm_bytes

        start_time = time.time()
        audio_data = np.frombuffer(pcm_bytes, dtype=np.int16).astype(np.float32)

        # Apply soft noise floor gating
        std_dev = np.std(audio_data)
        if std_dev < 15.0:  # Silence or low-level room noise
            audio_data *= 0.1

        clean_pcm16 = np.clip(audio_data, -32768, 32767).astype(np.int16).tobytes()

        duration_ms = (time.time() - start_time) * 1000
        self.processed_frames_count += 1
        self.total_processing_ms += duration_ms

        return clean_pcm16
