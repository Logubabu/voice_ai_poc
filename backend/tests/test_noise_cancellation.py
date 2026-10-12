import numpy as np
from app.noise_cancellation.rnnoise import RNNoiseSuppressor
from app.noise_cancellation.manager import NoiseCancellationManager


def test_rnnoise_suppressor():
    suppressor = RNNoiseSuppressor(aggressiveness="medium")
    t = np.linspace(0, 0.02, 320, endpoint=False)
    raw_pcm = (np.sin(2 * np.pi * 440 * t) * 5000 + np.random.normal(0, 500, 320)).astype(np.int16).tobytes()

    clean_pcm = suppressor.process(raw_pcm, sample_rate=16000)
    assert len(clean_pcm) == len(raw_pcm)

    metrics = suppressor.get_metrics()
    assert metrics["processed_frames"] == 1
    assert metrics["avg_latency_ms"] >= 0.0


def test_noise_cancellation_manager_switching():
    manager = NoiseCancellationManager(default_provider="rnnoise")
    assert manager.get_active_suppressor().name == "RNNoise"

    manager.set_active_algorithm("webrtc")
    assert manager.get_active_suppressor().name == "WebRTC APM"

    manager.set_active_algorithm("passthrough")
    assert manager.get_active_suppressor().name == "Passthrough"
