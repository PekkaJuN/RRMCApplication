# 0008. A run environment beside the development environment

- Status: accepted
- Date: 2026-11-24

## Context

[ADR 0002](0002-docker.md) chose one way of running for normal use and development: the
development containers, with the source folders mounted, Uvicorn's reloader and the Vite dev
server. It also put both uses on one database and one set of receipt folders.

With the MVP done, the app is in real use by the family while development goes on. A
half-finished change is then live in the app in use, and trying a change out, for example an
import, writes into the real data. The development images also carry every development tool.

The options were:

1. **Keep one way of running** and be careful: no change, but the risks above stay.
2. **A profile in `compose.yaml`**: one file, but the run service would share the Compose
   project `rrmc` and its volume names, and the development commands and agent guard would
   see it.
3. **A separate Compose file and project** with its own image, data and port: one more file
   and one more image to build, but the two environments cannot touch each other's data.

## Decision

- A **run environment** in `compose.app.yaml`, Compose project `rrmc-app`, one service `app`.
  The development environment in `compose.yaml` stays as it is.
- The run image is built in stages from the repository: the UI is built with `vite build`,
  the backend gets only its runtime dependencies, and the backend serves the built UI and
  the API on one port, `127.0.0.1:8080` by default. No development tools, no source mounts,
  no reloader; the app runs as a user other than root.
- The run environment has **its own data**: receipt folders under
  `C:\MyApps\RRMCApplication\source`, database backups in `C:\MyApps\RRMCApplication\backup`
  and the database volume `rrmc-app-data` (all three can be changed). The folders are outside
  the repository; the database stays in a volume. The development data is copied
  into it **once**, by a script that refuses when app data exists. Data never flows between
  the environments after that.
- The run environment is **updated** by a script that requires a clean working tree, runs
  the backend and frontend tests, backs up the app database, builds an image tagged with the
  commit and restarts the app. Schema changes reach the app database through the existing
  forward-only migrations at start.

This supersedes ADR 0002's "one way of running" and "there is no production build". The rest
of ADR 0002 stands: Docker Compose, Ollama on Windows, ports on `127.0.0.1`, settings in one
`.env` file, databases in Docker volumes.

The details are in the [run container spec](../../specs/features/app-container.md).

## Consequences

- Normal use no longer breaks while code is being edited, and development tries things out on
  its own data.
- Two images and two databases to keep: the run image is rebuilt on every update, and backups
  name their environment (`-Target app`).
- New code reaches the family only through the update script, after the tests pass.
- Disk use grows by the run image, one image per update tag until removed by hand, and the
  copied receipt images.
- The agent guardrails must also protect the run port; only the user changes them.
- Changing the run environment's database volume name to the development one would share the
  database again; the docs warn against it.
