#!/bin/bash
# Bayonet close-up: frames from bayonet.py on a white background, captions, MP4 and animated WebP.
# usage: tools/render/compose_bayonet.sh <frames dir> <output dir>
set -euo pipefail
IN=$1; OUT=$2
FONT=${FONT:-/System/Library/Fonts/SFNS.ttf}
cap() { echo "drawtext=fontfile=$FONT:text='$3':fontsize=40:fontcolor=0x222222:x=(w-text_w)/2:y=h-84:enable='between(t,$1,$2)'"; }
CAPS="$(cap 0.5 2.0 '1  Push the plug into the socket'),$(cap 2.0 3.25 '2  Turn it by about 50°'),$(cap 3.25 5.0 '3  Let go, the O-ring locks the lugs in the notch'),$(cap 5.0 8.6 'To release, push, turn back and pull apart')"
mkdir -p "$OUT"
ffmpeg -y -loglevel error -f lavfi -i color=white:s=1280x720:r=30 -framerate 30 -i "$IN/f_%04d.png" \
  -filter_complex "[0][1]overlay=shortest=1,$CAPS,format=yuv420p" \
  -c:v libx264 -crf 20 -movflags +faststart "$OUT/bayonet.mp4"
ffmpeg -y -loglevel error -i "$OUT/bayonet.mp4" -vf "fps=15,scale=640:-1:flags=lanczos" \
  -c:v libwebp_anim -loop 0 -quality 75 "$OUT/bayonet.webp"
ls -la "$OUT/bayonet.mp4" "$OUT/bayonet.webp"
