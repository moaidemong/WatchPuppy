#!/usr/bin/env bash
set -euo pipefail

CAMERA_ID="${1:?camera id required}"
CONFIG_PATH="${WATCHPUPPY_CONFIG:-/home/moai/Workspace/Codex/WatchPuppy/configs/watchpuppy.tapo.yaml}"
WSDL_DIR="${WATCHPUPPY_WSDL_DIR:-/tmp/python-onvif-zeep/wsdl}"
LOCK_FILE="${WATCHPUPPY_PIPELINE_LOCK:-/tmp/watchpuppy-pipeline.lock}"

while true; do
  /home/moai/Workspace/Codex/WatchDog/.venv/bin/python \
    /home/moai/Workspace/Codex/WatchPuppy/scripts/run_onvif_watchpuppy_pipeline.py \
    --config "${CONFIG_PATH}" \
    --camera-id "${CAMERA_ID}" \
    --wsdl-dir "${WSDL_DIR}" \
    --duration-seconds 300 \
    --cooldown-seconds 20 \
    --pipeline-lock-file "${LOCK_FILE}"
  sleep 10
done
