FROM python:3.12-slim-bookworm

COPY --from=ghcr.io/astral-sh/uv:0.9.5 /uv /uvx /bin/

# Tesseract with Finnish and English language data; Node.js is needed by pyright.
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        tesseract-ocr tesseract-ocr-fin tesseract-ocr-eng nodejs \
    && rm -rf /var/lib/apt/lists/*

# The virtual environment lives outside /app, because the source folder is mounted over /app.
ENV UV_PROJECT_ENVIRONMENT=/opt/venv \
    UV_LINK_MODE=copy \
    PATH=/opt/venv/bin:$PATH \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# Development tools are installed too: there is one way of running (ADR 0002).
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen \
    && pyright --version
