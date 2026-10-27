#!/usr/bin/env sh
set -eu

CONTAINER_NAME="pm-mvp"

if docker ps --filter "name=$CONTAINER_NAME" --format '{{.Names}}' | grep -qx "$CONTAINER_NAME"; then
  echo "Stopping container $CONTAINER_NAME ..."
  docker stop "$CONTAINER_NAME" >/dev/null
  echo "Container stopped."
else
  echo "Container $CONTAINER_NAME is not running."
fi
