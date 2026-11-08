#!/bin/bash
# Render all frames of the demo video (main view + two close-up insets).
# usage: tools/render/render_all.sh <meshes dir> <frames dir> [samples]
set -euo pipefail
MESHES=$1; FRAMES=$2; SAMPLES=${3:-48}
BLENDER=${BLENDER:-/Applications/Blender.app/Contents/MacOS/Blender}
HERE=$(cd "$(dirname "$0")" && pwd)
# Frames that already exist are skipped (see scene.py), so an interrupted run can simply be restarted.
for cam in ${CAMS:-main handle top}; do
  "$BLENDER" -b --factory-startup -P "$HERE/scene.py" -- \
    --meshes "$MESHES" --cam "$cam" --out "$FRAMES/$cam/f_" --frames 1-540 --samples "$SAMPLES" \
    > "$FRAMES/$cam.log" 2>&1
  grep -E "Error|Traceback" "$FRAMES/$cam.log" || true
  echo "done: $cam ($(ls "$FRAMES/$cam" | wc -l | tr -d ' ') frames)"
done
