# ==============================================================================
# Multi-Stage All-in-One Dockerfile
# Combines FreeSWITCH 1.10, FastAPI Backend (Python 3.12), and Vite/React Frontend
# Managed via Supervisord
# ==============================================================================

# ------------------------------------------------------------------------------
# Stage 1: Build React/Vite Frontend
# ------------------------------------------------------------------------------
FROM node:22-alpine AS frontend-builder

WORKDIR /app/frontend

COPY frontend/package*.json ./
RUN npm ci || npm install

COPY frontend/ ./
ARG VITE_BACKEND_URL=""
ENV VITE_BACKEND_URL=${VITE_BACKEND_URL}
RUN npm run build

# ------------------------------------------------------------------------------
# Stage 2: Final All-in-One Runtime Container
# ------------------------------------------------------------------------------
FROM bytedesk/freeswitch:latest

ENV DEBIAN_FRONTEND=noninteractive \
    PYTHONUNBUFFERED=1 \
    PATH="/opt/venv/bin:$PATH" \
    FREESWITCH_ESL_PASSWORD=ClueCon \
    BAIDU_MRCP_ENABLE=0 \
    DISABLE_IPV6=true

# Install system dependencies: Nginx, Supervisord, audio codecs, build essentials
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    nginx \
    supervisor \
    ffmpeg \
    libasound2 \
    libasound2-dev \
    libportaudio2 \
    build-essential \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Remove default Debian Nginx site to prevent conflicts on port 80
RUN rm -f /etc/nginx/sites-enabled/default /etc/nginx/conf.d/default.conf

# Create required runtime directories and symlink /etc/freeswitch
RUN mkdir -p /var/log/supervisor /var/run /app/backend/data /usr/share/nginx/html \
    /usr/local/freeswitch/etc/freeswitch /etc/freeswitch && \
    ln -sfn /usr/local/freeswitch/etc/freeswitch /etc/freeswitch

# Install uv for fast, reliable standalone Python 3.12 installation
COPY --from=ghcr.io/astral-sh/uv:0.6.5 /uv /usr/local/bin/uv

# Create Python 3.12 virtual environment and install backend dependencies
WORKDIR /app/backend
RUN uv venv /opt/venv --python 3.12

COPY backend/requirements.txt ./
RUN uv pip install --python /opt/venv --no-cache -r requirements.txt

# Copy backend application source code
COPY backend/ /app/backend/

# Copy FreeSWITCH custom configuration to both expected configuration directories
COPY freeswitch/conf/ /usr/local/freeswitch/etc/freeswitch/
COPY freeswitch/conf/ /etc/freeswitch/

# Copy built frontend assets from builder stage
COPY --from=frontend-builder /app/frontend/dist /usr/share/nginx/html

# Copy Nginx server configuration and Supervisord process management configuration
COPY docker/nginx.conf /etc/nginx/conf.d/voice_ai.conf
COPY docker/supervisord.conf /etc/supervisor/conf.d/supervisord.conf

# Expose all ports:
# 5173      - Frontend UI (Nginx)
# 8000      - Backend FastAPI & WebRTC Signaling
# 5060/udp  - FreeSWITCH SIP UDP
# 5060/tcp  - FreeSWITCH SIP TCP
# 8021      - FreeSWITCH ESL (Event Socket Library)
# 8086      - FreeSWITCH Audio Stream
# 50000-50020/udp - WebRTC Audio RTP/RTCP
EXPOSE 5173 8000 5060/udp 5060/tcp 8021 8086 50000-50020/udp

# Container healthcheck against backend /health endpoint
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Start Supervisord to manage FreeSWITCH, Backend, and Nginx processes
CMD ["/usr/bin/supervisord", "-c", "/etc/supervisor/conf.d/supervisord.conf"]
