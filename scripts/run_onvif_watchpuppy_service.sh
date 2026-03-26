#!/usr/bin/env bash
set -euo pipefail

CAMERA_ID="${1:?camera id required}"
CONFIG_PATH="${WATCHPUPPY_CONFIG:-/home/moai/Workspace/Codex/WatchPuppy/configs/watchpuppy.tapo.yaml}"
WSDL_DIR="${WATCHPUPPY_WSDL_DIR:-/tmp/python-onvif-zeep/wsdl}"
LOCK_FILE="${WATCHPUPPY_PIPELINE_LOCK:-/tmp/watchpuppy-pipeline.lock}"
HAILO_PYTHON="${WATCHPUPPY_HAILO_PYTHON:-/home/moai/Workspace/Codex/Runtime/Hailo/.venv/bin/python}"
LOG_DIR="${WATCHPUPPY_LOG_DIR:-/home/moai/Workspace/Codex/WatchPuppy/logs}"
BASE_RESTART_SLEEP="${WATCHPUPPY_RESTART_SLEEP_SECONDS:-10}"
SESSION_DURATION_SECONDS="${WATCHPUPPY_SESSION_DURATION_SECONDS:-86400}"

mkdir -p "${LOG_DIR}"
HEF_LOG_FILE="${LOG_DIR}/hef_camera_${CAMERA_ID}-$(date +%Y%m%d).log"
exec 2>>"${HEF_LOG_FILE}"

camera_jitter_seconds() {
  case "${CAMERA_ID}" in
    a) echo 0 ;;
    b) echo 2 ;;
    c) echo 4 ;;
    *) echo 1 ;;
  esac
}

while true; do
  sleep "$(camera_jitter_seconds)"
  "${HAILO_PYTHON}" \
    /home/moai/Workspace/Codex/WatchPuppy/scripts/run_onvif_watchpuppy_pipeline.py \
    --config "${CONFIG_PATH}" \
    --camera-id "${CAMERA_ID}" \
    --wsdl-dir "${WSDL_DIR}" \
    --duration-seconds "${SESSION_DURATION_SECONDS}" \
    --cooldown-seconds 20 \
    --pipeline-lock-file "${LOCK_FILE}"
  sleep "${BASE_RESTART_SLEEP}"
done
