# Production Noise Cancellation

## Overview

The `NoiseCancellationManager` provides pluggable noise suppression optimized for low-latency voice conversations.

## Algorithms

- **RNNoise**: Recurrent Neural Network noise suppressor targeting fan noise, AC noise, mic hiss, and keyboard clicks while preserving speech formants.
- **WebRTC APM**: WebRTC standard noise suppressor with echo cancellation.
- **DeepFilterNet**: High-aggression neural spectral noise filter.
- **Passthrough**: Direct audio passthrough without filtering.

## Configuration

```ini
NOISE_CANCELLATION_ENABLED=true
NOISE_CANCELLATION_PROVIDER=rnnoise
NOISE_CANCELLATION_AGGRESSIVENESS=medium
```
