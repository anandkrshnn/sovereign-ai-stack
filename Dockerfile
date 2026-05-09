# Sovereign AI Stack - Hardware-Native Validation Environment
# Optimized for Linux TPM 2.0 (ESYS) testing

FROM python:3.11-slim-bookworm

# 1. Install System Dependencies (TSS2 Stack)
RUN apt-get update && apt-get install -y \
    build-essential \
    python3-dev \
    libtss2-dev \
    libtss2-esys-3.0.2-0 \
    libtss2-tctildr0 \
    libtss2-rc0 \
    tpm2-tools \
    pkg-config \
    git \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# 2. Install Sovereign AI Stack
COPY . .
RUN pip install --upgrade pip
RUN pip install .[full,dev]

# 3. Environment Config
ENV PYTHONUNBUFFERED=1
ENV SOVEREIGN_CONFIG_PATH=/app/sovereign.yaml

# By default, attempt to use the host's TPM Resource Manager if passed through
# Or expect a simulator at /dev/tpmrm0
ENTRYPOINT ["sovereign"]
CMD ["trust", "status"]
