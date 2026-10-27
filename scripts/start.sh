#!/usr/bin/env sh
set -eu

SCRIPT_DIR="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
REPO_ROOT="$(CDPATH= cd -- "$SCRIPT_DIR/.." && pwd)"
DATA_DIR="$REPO_ROOT/backend/data"

mkdir -p "$DATA_DIR"

echo "Building Docker image pm-mvp..."
docker build -t pm-mvp "$REPO_ROOT"

echo "Starting container pm-mvp on http://localhost:8000 ..."
docker run --rm -d --name pm-mvp -p 8000:8000 -v "$DATA_DIR:/app/backend/data" pm-mvp

echo "Container started."
