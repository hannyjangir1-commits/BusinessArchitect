# ==========================================
# Stage 1: Build React/TypeScript Frontend
# ==========================================
FROM node:22-alpine AS frontend-builder
WORKDIR /build/client

COPY client/package*.json ./
RUN npm ci

COPY client/ ./
RUN npm run build

# ==========================================
# Stage 2: Production Python Backend & Runtime
# ==========================================
FROM python:3.12-slim AS runner

# Avoid buffering Python output and bytecode creation
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PORT=8000

# Install system dependencies (for psycopg2 / cffi / reportlab if needed)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install backend dependencies
COPY server/requirements.txt ./server/requirements.txt
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r ./server/requirements.txt

# Copy server application code
COPY server/ ./server/

# Copy built frontend assets from Stage 1 into the location expected by FastAPI
COPY --from=frontend-builder /build/client/dist ./client/dist

# Create unprivileged application user
RUN useradd -m -u 1001 appuser && \
    chown -R appuser:appuser /app
USER appuser

EXPOSE ${PORT}

# Healthcheck for container orchestration
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
  CMD curl -f http://localhost:${PORT}/health || exit 1

# Start Uvicorn pointing to app.main:app
WORKDIR /app/server
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
