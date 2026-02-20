# Build stage: git needed only for snipeit-api dependency
FROM python:3.12-slim AS builder

RUN apt-get update && apt-get install -y --no-install-recommends git && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /build
COPY pyproject.toml uv.lock server.py ./
COPY prompts/ prompts/

RUN pip install --no-cache-dir uv && \
    uv pip install --system --no-cache .

# Runtime stage: no git, no build deps, non-root user
FROM python:3.12-slim

RUN useradd --create-home --shell /bin/bash appuser

COPY --from=builder /usr/local/lib/python3.12/site-packages /usr/local/lib/python3.12/site-packages
COPY --from=builder /usr/local/bin/snipeit-mcp /usr/local/bin/snipeit-mcp

WORKDIR /app
COPY --chown=appuser:appuser server.py ./
COPY --chown=appuser:appuser prompts/ prompts/

USER appuser

ENTRYPOINT ["snipeit-mcp"]
