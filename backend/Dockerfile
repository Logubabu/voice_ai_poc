# ==============================================================================
# Production Dockerfile for Voice AI Backend (FastAPI / Pipecat / WebRTC)
# Multi-stage build with minimal runtime footprint & non-root user execution
# ==============================================================================

# ------------------------------------------------------------------------------
# Stage 1: Build & Dependency Installation
# ------------------------------------------------------------------------------
FROM python:3.12-slim AS builder

WORKDIR /app

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    VIRTUAL_ENV=/opt/venv \
    PATH="/opt/venv/bin:$PATH"

# Install minimal OS build dependencies for compiling audio/C packages
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libasound2-dev \
    libportaudio2 \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install uv for fast, reliable deterministic dependency installation
COPY --from=ghcr.io/astral-sh/uv:0.6.5 /uv /usr/local/bin/uv

# Copy requirements file first for layer caching
COPY requirements.txt ./requirements.txt

# Create dedicated virtual environment and install dependencies
RUN uv venv /opt/venv && \
    uv pip install --python /opt/venv --no-cache -r requirements.txt

# ------------------------------------------------------------------------------
# Stage 2: Minimal Production Runtime
# ------------------------------------------------------------------------------
FROM python:3.12-slim AS runtime

WORKDIR /app

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PATH="/opt/venv/bin:$PATH" \
    PORT=8000

# Install only required runtime shared libraries (ffmpeg, libasound2, libportaudio2, curl for health checks)
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    libasound2 \
    libportaudio2 \
    curl \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Copy virtual environment from builder stage
COPY --from=builder /opt/venv /opt/venv

# Create unprivileged non-root user and group (appuser:appuser, UID 1000)
RUN groupadd -r appuser -g 1000 && \
    useradd -u 1000 -r -g appuser -s /bin/false -d /app appuser && \
    mkdir -p /app/data && \
    chown -R appuser:appuser /app

# Copy application source code
COPY --chown=appuser:appuser . /app/

# Switch to non-root user
USER appuser

# Expose backend API and WebRTC signaling port
EXPOSE 8000

# Container health check against /health endpoint
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Production startup with uvicorn in exec form (SIGTERM handling & graceful shutdown)
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]
