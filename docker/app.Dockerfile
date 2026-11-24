# The run image (specs/features/app-container.md, P1): the backend, the built UI and Tesseract,
# without development tools. The build context is the project root, filtered by
# app.Dockerfile.dockerignore.

FROM node:22-bookworm-slim AS ui
WORKDIR /ui
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci --no-fund --no-audit
COPY frontend ./
RUN npm run build

# The same Python base as the final stage, so the environment's interpreter link stays valid.
FROM python:3.12-slim-bookworm AS deps
COPY --from=ghcr.io/astral-sh/uv:0.9.5 /uv /bin/
ENV UV_PROJECT_ENVIRONMENT=/opt/venv \
    UV_LINK_MODE=copy
WORKDIR /app
COPY backend/pyproject.toml backend/uv.lock ./
RUN uv sync --frozen --no-dev

FROM python:3.12-slim-bookworm

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        tesseract-ocr tesseract-ocr-fin tesseract-ocr-eng \
    && rm -rf /var/lib/apt/lists/*

# A new volume at /data/db takes its owner from the image's folder.
RUN groupadd --gid 10001 rrmc \
    && useradd --uid 10001 --gid 10001 --no-create-home rrmc \
    && mkdir -p /data/db /data/import /data/import_done /data/import_failed /data/archived \
    && chown -R 10001:10001 /data

ENV PATH=/opt/venv/bin:$PATH \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app
COPY --from=deps /opt/venv /opt/venv
COPY backend/pyproject.toml backend/uv.lock ./
COPY backend/app ./app
COPY --from=ui /ui/dist ./static

USER rrmc

# prestart exits non-zero on invalid settings or a failed migration, which stops the container.
CMD ["sh", "-c", "python -m app.prestart && exec uvicorn --factory app.main:create_app --host 0.0.0.0 --port 8000 --no-access-log"]

# Last, because a new commit changes it and every layer after it.
ARG RRMC_REVISION=""
LABEL org.opencontainers.image.revision=$RRMC_REVISION
