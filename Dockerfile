FROM python:3.12-slim

RUN apt-get update && apt-get install -y --no-install-recommends git && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY pyproject.toml uv.lock server.py ./
COPY prompts/ prompts/

RUN pip install --no-cache-dir uv && \
    uv pip install --system --no-cache .

ENTRYPOINT ["snipeit-mcp"]
