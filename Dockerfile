# ==========================================
# Stage 1: Build React/TypeScript Frontend
# ==========================================
FROM node:22-slim AS frontend-builder
WORKDIR /build/client

# Install frontend dependencies using committed package-lock.json
COPY client/package*.json ./
RUN npm ci

# Copy client source code and compile production SPA bundle
COPY client/ ./
RUN npm run build

# ==========================================
# Stage 2: Production Python Backend & Runtime
# ==========================================
FROM python:3.12-slim AS runner

# Avoid buffering Python output and bytecode creation
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PORT=8000 \
    PYTHONPATH=/app/server

# Install minimal OS dependencies:
# - curl: required for container healthcheck probe
# - libpq-dev / build-essential: PostgreSQL client compilation/runtime compatibility
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install backend dependencies with layer caching
COPY server/requirements.txt ./server/requirements.txt
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r ./server/requirements.txt

# Copy backend application source and Alembic migrations
COPY server/ ./server/

# Copy built frontend assets from Stage 1 into the location expected by FastAPI
COPY --from=frontend-builder /build/client/dist ./client/dist

# Create unprivileged application user and set ownership
RUN useradd -m -u 1001 appuser && \
    chown -R appuser:appuser /app
USER appuser

EXPOSE ${PORT}

# Healthcheck for container orchestration (uses PORT env var with safe fallback)
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
  CMD curl -f http://localhost:${PORT:-8000}/health || exit 1

# Start Uvicorn pointing to app.main:app
# Runs database migrations automatically on startup so deployment works even without manual Pre-Deploy commands
WORKDIR /app/server
CMD ["sh", "-c", "alembic upgrade head && exec uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000} --no-proxy-headers"]
