#!/usr/bin/env bash
set -euo pipefail

CAMERA_ID="${1:?camera id required}"
CONFIG_PATH="${WATCHPUPPY_CONFIG:-/home/moai/Workspace/Codex/WatchPuppy/configs/watchpuppy.tapo.yaml}"
HAILO_PYTHON="${WATCHPUPPY_HAILO_PYTHON:-/home/moai/Workspace/Codex/Runtime/Hailo/.venv/bin/python}"
FFMPEG_BIN="${WATCHPUPPY_FFMPEG_BIN:-/usr/bin/ffmpeg}"

stream_port() {
  case "${CAMERA_ID}" in
    a) echo 10111 ;;
    b) echo 10112 ;;
    c) echo 10113 ;;
    *) echo "unsupported camera id: ${CAMERA_ID}" >&2; exit 1 ;;
  esac
}

RTSP_URL="$("${HAILO_PYTHON}" /home/moai/Workspace/Codex/WatchPuppy/scripts/print_camera_rtsp_url.py --config "${CONFIG_PATH}" --camera-id "${CAMERA_ID}")"

exec "${FFMPEG_BIN}" \
  -nostdin \
  -loglevel warning \
  -rtsp_transport tcp \
  -i "${RTSP_URL}" \
  -an \
  -c:v copy \
  -f mpegts \
  -listen 1 \
  "http://0.0.0.0:$(stream_port)/stream.ts"
