#!/usr/bin/env bash
set -euo pipefail

CONTAINER_NAME="pm-mvp-app"

if docker ps -a --format '{{.Names}}' | awk -v name="${CONTAINER_NAME}" '$0 == name { found = 1 } END { exit !found }'; then
  docker rm -f "${CONTAINER_NAME}" >/dev/null
  echo "Stopped and removed ${CONTAINER_NAME}."
else
  echo "No container named ${CONTAINER_NAME} is running."
fi
