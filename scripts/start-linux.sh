#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
IMAGE_NAME="pm-mvp"
CONTAINER_NAME="pm-mvp-app"

echo "Building Docker image..."
docker build -t "${IMAGE_NAME}" "${ROOT_DIR}"

if docker ps -a --format '{{.Names}}' | rg -x "${CONTAINER_NAME}" >/dev/null; then
  echo "Removing existing container..."
  docker rm -f "${CONTAINER_NAME}" >/dev/null
fi

echo "Starting container..."
docker run -d --name "${CONTAINER_NAME}" -p 8000:8000 "${IMAGE_NAME}" >/dev/null
echo "App is running at http://127.0.0.1:8000"
