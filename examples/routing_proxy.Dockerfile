# CascadeFlow Routing Proxy - Docker Image
# ==========================================
#
# Multi-stage build for production deployment
#
# Build:
#   docker build -f routing_proxy.Dockerfile -t cascadeflow-proxy:latest .
#
# Run:
#   docker run -p 8000:8000 \
#     -e CASCADEFLOW_API_KEY="your-secret-key" \
#     -e OPENAI_API_KEY="sk-..." \
#     -e ANTHROPIC_API_KEY="sk-ant-..." \
#     cascadeflow-proxy:latest

FROM python:3.11-slim as base

# Set environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Create non-root user
RUN useradd -m -u 1000 cascadeflow && \
    mkdir -p /app && \
    chown -R cascadeflow:cascadeflow /app

WORKDIR /app

# Install Python dependencies
COPY --chown=cascadeflow:cascadeflow requirements-dev.txt pyproject.toml ./
RUN pip install --no-cache-dir \
    fastapi \
    uvicorn[standard] \
    httpx \
    pydantic \
    python-multipart \
    && pip install --no-cache-dir -e .

# Copy application code
COPY --chown=cascadeflow:cascadeflow . .

# Switch to non-root user
USER cascadeflow

# Expose port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Run the application
CMD ["python", "examples/routing_proxy.py"]
