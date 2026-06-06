# ==========================================
# Stage 1: Builder
# ==========================================
FROM python:3.12-bookworm AS builder

# Set environment variables for build
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /build

# Copy project files
COPY pyproject.toml README.md ./
COPY sovereign_ai/ ./sovereign_ai/

# Create a virtual environment
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Install build dependencies and the package with extras
RUN pip install build && \
    pip install .[full,postgres,demo]

# ==========================================
# Stage 2: Runtime
# ==========================================
FROM python:3.12-slim

# Set strict environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PATH="/opt/venv/bin:$PATH" \
    DATABASE_URI="sqlite+aiosqlite:///:memory:"

WORKDIR /app

# Install runtime dependencies (TSS2 stack for TPM simulator support)
RUN apt-get update && apt-get upgrade -y && apt-get install -y --no-install-recommends \
    curl \
    libtss2-esys-3.0.2-0 \
    libtss2-tctildr0 \
    tpm2-tools \
    && rm -rf /var/lib/apt/lists/*

# Add non-root user for security hardening
RUN addgroup --gid 1001 sovereign && \
    adduser --uid 1001 --gid 1001 --disabled-password --gecos "" sovereign

# Copy virtualenv from builder
COPY --from=builder --chown=sovereign:sovereign /opt/venv /opt/venv

# Copy application code and examples
COPY --chown=sovereign:sovereign examples/ ./examples/
COPY --chown=sovereign:sovereign sovereign_ai/ ./sovereign_ai/

# Switch to non-root user
USER 1001

EXPOSE 7860
EXPOSE 8000

# Healthcheck
HEALTHCHECK --interval=30s --timeout=10s --start-period=10s --retries=3 \
  CMD curl -f http://localhost:7860/ || exit 1

# Default entrypoint
CMD ["python", "-m", "examples.ptv_web_ui"]
