import numpy as np
from app.audio.codec import AudioResampler


def test_resample_8k_to_16k():
    # 800 samples at 8kHz = 100ms
    t = np.linspace(0, 0.1, 800, endpoint=False)
    pcm_8k = (np.sin(2 * np.pi * 440 * t) * 10000).astype(np.int16).tobytes()

    pcm_16k = AudioResampler.resample_8k_to_16k(pcm_8k)
    
    # Resampled output should have approximately 1600 samples = 3200 bytes
    assert len(pcm_16k) == 3200
    valid, msg = AudioResampler.validate_pcm16_frame(pcm_16k, expected_sample_rate=16000, expected_duration_ms=100)
    assert valid is True


def test_resample_16k_to_8k():
    # 1600 samples at 16kHz = 100ms
    t = np.linspace(0, 0.1, 1600, endpoint=False)
    pcm_16k = (np.sin(2 * np.pi * 440 * t) * 10000).astype(np.int16).tobytes()

    pcm_8k = AudioResampler.resample_16k_to_8k(pcm_16k)
    
    # Resampled output should have approximately 800 samples = 1600 bytes
    assert len(pcm_8k) == 1600
