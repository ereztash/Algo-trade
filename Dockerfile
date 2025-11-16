# Multi-stage Dockerfile for Algo-Trade Platform
# Stage 1: Builder - Install dependencies and compile wheels
FROM python:3.9-slim as builder

# Set build arguments
ARG DEBIAN_FRONTEND=noninteractive

# Install build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    g++ \
    gfortran \
    libopenblas-dev \
    liblapack-dev \
    pkg-config \
    git \
    && rm -rf /var/lib/apt/lists/*

# Create virtual environment
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Copy requirements files
COPY requirements.txt requirements-dev.txt /tmp/

# Install Python dependencies
# Install production dependencies first for better layer caching
RUN pip install --no-cache-dir --upgrade pip wheel setuptools && \
    pip install --no-cache-dir -r /tmp/requirements.txt

# Install development dependencies (optional - can be controlled via build arg)
ARG INSTALL_DEV=false
RUN if [ "$INSTALL_DEV" = "true" ]; then \
    pip install --no-cache-dir -r /tmp/requirements-dev.txt; \
    fi

# Install additional runtime dependencies for Kafka and monitoring
RUN pip install --no-cache-dir \
    kafka-python>=2.0.2 \
    confluent-kafka>=2.0.2 \
    prometheus-client>=0.16.0 \
    asyncio \
    aiohttp \
    python-dotenv \
    jsonschema \
    pydantic

# Stage 2: Runtime - Minimal production image
FROM python:3.9-slim

# Set runtime arguments
ARG DEBIAN_FRONTEND=noninteractive

# Install runtime dependencies only
RUN apt-get update && apt-get install -y --no-install-recommends \
    libopenblas0 \
    libgomp1 \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Create non-root user for security
RUN groupadd -r algotrader && \
    useradd -r -g algotrader -u 1000 -m -s /bin/bash algotrader

# Copy virtual environment from builder
COPY --from=builder /opt/venv /opt/venv

# Set environment variables
ENV PATH="/opt/venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONPATH=/app \
    APP_ENV=production

# Create application directory
WORKDIR /app

# Copy application code
COPY --chown=algotrader:algotrader . /app/

# Create necessary directories for data, logs, and configs
RUN mkdir -p /app/data /app/logs /app/config && \
    chown -R algotrader:algotrader /app

# Switch to non-root user
USER algotrader

# Expose ports
# 8000 - Data Plane metrics
# 8001 - Strategy Plane metrics
# 8002 - Order Plane metrics
# 8080 - Health check endpoint
EXPOSE 8000 8001 8002 8080

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD curl -f http://localhost:8080/health || exit 1

# Default command (can be overridden in docker-compose)
CMD ["python", "-m", "data_plane.app.main"]
