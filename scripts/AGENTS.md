# Script catalog

Local run scripts for the Dockerized app, one pair per shell:

- [start.sh](start.sh), [stop.sh](stop.sh): macOS/Linux
- [start.ps1](start.ps1), [stop.ps1](stop.ps1): Windows PowerShell
- [start.bat](start.bat), [stop.bat](stop.bat): Windows Command Prompt

## Start

Each start script:
1. Creates `backend/data/` if missing.
2. Builds image `pm-mvp` from the repo root (rebuilds the frontend and backend every time).
3. Runs container `pm-mvp` detached with `--rm` on port `8000`, mounting `backend/data/` at `/app/backend/data` so the SQLite database persists, and passing the root `.env` via `--env-file` (the file must exist).

The app is then at http://localhost:8000. Starting while the container is already running fails because the name is taken; run the stop script first.

## Stop

Each stop script runs `docker stop pm-mvp` if the container is running and otherwise reports that it is not running. Because the container was started with `--rm`, stopping also removes it; the image and `backend/data/` remain.
