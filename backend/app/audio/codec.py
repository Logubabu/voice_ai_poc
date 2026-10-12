import numpy as np
from typing import Tuple


class AudioResampler:
    """Efficient, reusable audio resampler for converting between 8kHz telephony and 16kHz AI PCM audio formats."""

    @staticmethod
    def resample_pcm16(audio_bytes: bytes, orig_sr: int, target_sr: int) -> bytes:
        """Resamples 16-bit mono PCM raw bytes from orig_sr to target_sr."""
        if orig_sr == target_sr or not audio_bytes:
            return audio_bytes

        # Convert 16-bit signed PCM bytes to numpy int16 array
        audio_data = np.frombuffer(audio_bytes, dtype=np.int16)
        if len(audio_data) == 0:
            return audio_bytes

        # Compute output length
        num_output_samples = int(round(len(audio_data) * (target_sr / float(orig_sr))))
        if num_output_samples == 0:
            return b""

        # Perform high-quality linear interpolation resampling
        input_indices = np.arange(len(audio_data))
        output_indices = np.linspace(0, len(audio_data) - 1, num_output_samples)
        resampled_data = np.interp(output_indices, input_indices, audio_data)

        # Clip values to 16-bit signed range [-32768, 32767] and convert to int16
        resampled_data = np.clip(resampled_data, -32768, 32767).astype(np.int16)

        return resampled_data.tobytes()

    @classmethod
    def resample_8k_to_16k(cls, pcm_8k: bytes) -> bytes:
        """Converts 8kHz mono PCM16 telephony audio to 16kHz mono PCM16 AI pipeline format."""
        return cls.resample_pcm16(pcm_8k, 8000, 16000)

    @classmethod
    def resample_16k_to_8k(cls, pcm_16k: bytes) -> bytes:
        """Converts 16kHz mono PCM16 AI pipeline audio to 8kHz mono PCM16 telephony format."""
        return cls.resample_pcm16(pcm_16k, 16000, 8000)

    @staticmethod
    def validate_pcm16_frame(audio_bytes: bytes, expected_sample_rate: int = 16000, expected_duration_ms: int = 20) -> Tuple[bool, str]:
        """Validates that incoming raw PCM frame has correct 16-bit alignment and size bounds."""
        if not audio_bytes:
            return False, "Empty audio frame"
        if len(audio_bytes) % 2 != 0:
            return False, f"Invalid 16-bit alignment: frame length {len(audio_bytes)} is odd"
        
        # 2 bytes per sample for 16-bit mono
        bytes_per_sample = 2
        expected_bytes = int((expected_sample_rate * (expected_duration_ms / 1000.0)) * bytes_per_sample)
        
        if len(audio_bytes) > expected_bytes * 5:
            return False, f"Frame size {len(audio_bytes)} bytes exceeds 5x threshold limit ({expected_bytes * 5})"

        return True, "Valid PCM16 frame"


audio_resampler = AudioResampler()
