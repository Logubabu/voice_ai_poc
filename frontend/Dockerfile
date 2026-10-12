# ==============================================================================
# Production Dockerfile for Frontend (React + Vite + Tailwind CSS)
# Multi-stage build with lightweight Nginx static web server
# ==============================================================================

# ------------------------------------------------------------------------------
# Stage 1: Build static assets
# ------------------------------------------------------------------------------
FROM node:22-alpine AS builder

WORKDIR /app

# Copy dependency files for caching
COPY package*.json ./
RUN npm ci || npm install

# Copy source code and build production bundle
COPY . ./
ARG VITE_BACKEND_URL=""
ENV VITE_BACKEND_URL=${VITE_BACKEND_URL}
RUN npm run build

# ------------------------------------------------------------------------------
# Stage 2: Production Nginx static web server
# ------------------------------------------------------------------------------
FROM nginx:alpine AS runner

# Remove default Nginx welcome site
RUN rm -rf /etc/nginx/conf.d/default.conf

# Copy custom Nginx configuration
COPY nginx.conf /etc/nginx/conf.d/default.conf

# Copy compiled static assets from builder stage
COPY --from=builder /app/dist /usr/share/nginx/html

# Expose HTTP port 5173
EXPOSE 5173

# Container healthcheck
HEALTHCHECK --interval=30s --timeout=5s --start-period=5s --retries=3 \
    CMD wget -qO- http://localhost:5173/health || exit 1

CMD ["nginx", "-g", "daemon off;"]
