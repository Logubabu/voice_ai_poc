import time
import asyncio
import numpy as np
import pytest

from app.audio.codec import AudioResampler
from app.noise_cancellation.manager import noise_cancel_manager


def test_performance_audio_resampling_benchmark():
    """Benchmark 8k -> 16k resampling latency across 10,000 audio frames."""
    t = np.linspace(0, 0.02, 160, endpoint=False)
    pcm_8k = (np.sin(2 * np.pi * 440 * t) * 10000).astype(np.int16).tobytes()

    start_time = time.time()
    num_frames = 10000

    for _ in range(num_frames):
        _ = AudioResampler.resample_8k_to_16k(pcm_8k)

    total_time = time.time() - start_time
    avg_per_frame_ms = (total_time / num_frames) * 1000

    print(f"\n[BENCHMARK] Resampled {num_frames} frames in {total_time:.3f}s (avg: {avg_per_frame_ms:.4f}ms/frame)")
    assert avg_per_frame_ms < 0.5  # Sub-millisecond target per frame


def test_performance_noise_cancellation_benchmark():
    """Benchmark noise cancellation manager frame processing latency across 1,000 frames."""
    t = np.linspace(0, 0.02, 320, endpoint=False)
    pcm_16k = (np.sin(2 * np.pi * 440 * t) * 10000).astype(np.int16).tobytes()

    start_time = time.time()
    num_frames = 1000

    for _ in range(num_frames):
        _ = noise_cancel_manager.process_frame(pcm_16k)

    total_time = time.time() - start_time
    avg_per_frame_ms = (total_time / num_frames) * 1000

    print(f"\n[BENCHMARK] Noise cancellation processed {num_frames} frames in {total_time:.3f}s (avg: {avg_per_frame_ms:.4f}ms/frame)")
    assert avg_per_frame_ms < 5.0  # Real-time requirement < 5ms per 20ms frame


@pytest.mark.asyncio
async def test_performance_concurrent_sessions_benchmark():
    """Simulates 100 concurrent audio frame processing tasks to measure throughput and backpressure."""
    t = np.linspace(0, 0.02, 320, endpoint=False)
    pcm_16k = (np.sin(2 * np.pi * 440 * t) * 10000).astype(np.int16).tobytes()

    async def simulate_session(session_id: int):
        for _ in range(50):
            _ = noise_cancel_manager.process_frame(pcm_16k)
            await asyncio.sleep(0.001)

    start_time = time.time()
    num_concurrent_sessions = 100

    tasks = [simulate_session(i) for i in range(num_concurrent_sessions)]
    await asyncio.gather(*tasks)

    total_time = time.time() - start_time
    print(f"\n[BENCHMARK] 100 concurrent voice session streams completed in {total_time:.3f}s")
    assert total_time < 10.0
