#!/bin/bash
set -euo pipefail

# Build and push the TEMPORARY test image for Sys Clone Project:
# latest hardened base + the unreleased mesh SDK branch installed on top.
# Must match config.json -> "docker_image".
IMAGE="supervisely/sys-clone-project:0.0.2-test-hardened"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

docker build -f "${SCRIPT_DIR}/Dockerfile" -t "${IMAGE}" "${SCRIPT_DIR}"
docker push "${IMAGE}"

echo "Built and pushed ${IMAGE}"
