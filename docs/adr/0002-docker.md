# 0002. Docker for running and development

- Status: accepted
- Date: 2026-10-26

## Context

[ADR 0001](0001-tech-stack.md) chose Python, FastAPI, React, Tesseract, Ollama and SQLite.
Its consequences assumed that Python, Node.js and Tesseract with `fin` and `eng` are
installed on the user's Windows computer. Installing and keeping these in step by hand is
slow and easy to get wrong. The app has one user, runs on one computer and has no separate
production environment. Ollama needs the GPU, which is simplest to use from Windows.

## Decision

- The app is installed, run and developed with **Docker Compose**: a `backend` container
  (FastAPI with Tesseract `fin` + `eng`) and a `frontend` container (Vite dev server).
- **One way of running** for normal use and development: `docker compose up`, the UI at
  `http://127.0.0.1:5173`. There is no production build.
- **Ollama runs on Windows**, not in a container. The backend reaches it at
  `http://host.docker.internal:11434`.
- Published ports are bound to `127.0.0.1` only.
- **All settings are in one `.env` file** in the project root, read by Compose and the
  backend; `.env.example` is committed.
- **The SQLite database is in a Docker volume**, not in a Windows folder, because SQLite file
  locking is unreliable on Windows folders mounted into Linux containers. The import folders
  are Windows folders mounted into the backend container.
- Tests, lint and type checks run in the containers.

The details are in the [foundation spec](../../specs/features/foundation.md).

## Consequences

- Prerequisites on Windows are Docker Desktop (WSL 2), Git and Ollama. This supersedes the
  installation consequence of ADR 0001; the rest of ADR 0001 stands.
- The first start downloads and builds large images (Tesseract, Node.js, Playwright browsers).
- File changes on mounted Windows folders need polling for reload, which uses some CPU.
- The database file is not visible in Windows Explorer; backups need a documented command.
- Deleting the database is an explicit `docker compose down -v`.
- `host.docker.internal` needs an `extra_hosts` entry outside Docker Desktop.
- Running Ollama in a container instead would need a new ADR.
