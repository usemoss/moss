# Container image for the agora-moss MCP server.
# Target: ghcr.io/usemoss/agora-moss
#
# Build:   docker build -t agora-moss -f apps/agora-moss/Dockerfile .
# Run:     docker run --rm -p 8080:8080 --env-file apps/agora-moss/.env agora-moss

FROM python:3.13-slim-trixie AS base

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    UV_COMPILE_BYTECODE=1

# Install uv from its upstream image.
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

RUN useradd --create-home --shell /bin/bash appuser

WORKDIR /app

# Copy the package + app sources. Monorepo context; build from repo root.
COPY packages/agora-moss/pyproject.toml packages/agora-moss/
COPY packages/agora-moss/README.md packages/agora-moss/
COPY packages/agora-moss/src packages/agora-moss/src

COPY apps/agora-moss/pyproject.toml apps/agora-moss/
COPY apps/agora-moss/README.md apps/agora-moss/
COPY apps/agora-moss/server.py apps/agora-moss/
COPY apps/agora-moss/llm_proxy.py apps/agora-moss/
COPY apps/agora-moss/start_agent.py apps/agora-moss/
COPY apps/agora-moss/create_index.py apps/agora-moss/
COPY apps/agora-moss/moss_docs.json apps/agora-moss/

WORKDIR /app/apps/agora-moss
RUN uv sync --no-dev

USER appuser
EXPOSE 8080
CMD ["uv", "run", "uvicorn", "server:app", "--host", "0.0.0.0", "--port", "8080"]
