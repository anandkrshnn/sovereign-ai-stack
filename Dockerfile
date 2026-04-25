# 🛡️ Sovereign AI Stack - Production Container
FROM python:3.11-slim

# Install system dependencies for SQLCipher and forensic tools
RUN apt-get update && apt-get install -y \
    build-essential \
    libsqlite3-dev \
    tcl \
    pkg-config \
    git \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install package
COPY . .
RUN pip install --no-cache-dir ".[full]"

# Create data directories for tenant silos
RUN mkdir -p /app/data

# Environment Defaults
ENV SOVEREIGN_DATA_DIR=/app/data
ENV PORT=8000
ENV SOVEREIGN_MODEL=qwen2.5:7b
ENV MASTER_GATEWAY_SECRET=sov-change-me-promptly

# Expose Bridge and Metrics
EXPOSE 8000

# Launch the Sovereign Bridge
CMD ["sovereign-ai", "bridge"]
