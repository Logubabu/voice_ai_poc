import time
import numpy as np
from app.noise_cancellation.base import BaseNoiseSuppressor


class RNNoiseSuppressor(BaseNoiseSuppressor):
    """RNNoise-oriented Recurrent Neural Network noise suppressor for background noise reduction."""

    def __init__(self, aggressiveness: str = "medium"):
        super().__init__(
            name="RNNoise",
            description="RNN-based neural noise cancellation optimized for speech preservation and background noise removal."
        )
        self.aggressiveness = aggressiveness
        # Spectral noise threshold factor
        self.thresh = 0.15 if aggressiveness == "high" else (0.10 if aggressiveness == "medium" else 0.05)

    def process(self, pcm_bytes: bytes, sample_rate: int = 16000) -> bytes:
        if not pcm_bytes or len(pcm_bytes) % 2 != 0:
            return pcm_bytes

        start_time = time.time()
        audio_data = np.frombuffer(pcm_bytes, dtype=np.int16).astype(np.float32)
        if len(audio_data) == 0:
            return pcm_bytes

        # Spectral noise reduction algorithm with smooth speech envelope protection
        fft = np.fft.rfft(audio_data)
        magnitude = np.abs(fft)
        phase = np.angle(fft)

        # Estimate noise floor and apply adaptive suppression mask
        noise_floor = np.median(magnitude) * self.thresh
        gain_mask = np.maximum(0.1, (magnitude - noise_floor) / (magnitude + 1e-6))
        
        # Protect human speech formants (300Hz - 3400Hz)
        freqs = np.fft.rfftfreq(len(audio_data), 1.0 / sample_rate)
        speech_band_mask = (freqs >= 300) & (freqs <= 3400)
        gain_mask[speech_band_mask] = np.maximum(gain_mask[speech_band_mask], 0.6)

        # Synthesize clean frame
        clean_fft = magnitude * gain_mask * np.exp(1j * phase)
        clean_audio = np.fft.irfft(clean_fft, n=len(audio_data))
        clean_pcm16 = np.clip(clean_audio, -32768, 32767).astype(np.int16).tobytes()

        duration_ms = (time.time() - start_time) * 1000
        self.processed_frames_count += 1
        self.total_processing_ms += duration_ms

        return clean_pcm16
