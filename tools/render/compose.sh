#!/bin/bash
# Combine the rendered frames into the demo video and the README preview.
# usage: tools/render/compose.sh <frames dir> <output dir>
#   <frames dir>/main, /handle, /top   PNG frames from render_all.sh
#   writes <output dir>/demo.mp4 and <output dir>/demo.webp
set -euo pipefail
FRAMES=$1
OUT=$2
FONT=${FONT:-/System/Library/Fonts/SFNS.ttf}
mkdir -p "$OUT"

# caption <text> <start s> <end s>
caption() {
  local a=$2 b=$3
  printf "drawtext=fontfile=%s:text='%s':fontsize=42:fontcolor=white:x=48:y=56:box=1:boxcolor=black@0.55:boxborderw=20:enable='between(t,%s,%s)':alpha='min(1,min((t-%s)/0.3,(%s-t)/0.3))'," \
    "$FONT" "$1" "$a" "$b" "$a" "$b"
}
# inset label <text> <start s> <end s>
inset_label() {
  printf "drawtext=fontfile=%s:text='%s':fontsize=24:fontcolor=white:x=14:y=14:box=1:boxcolor=black@0.5:boxborderw=10:enable='between(t,%s,%s)'," \
    "$FONT" "$1" "$2" "$3"
}

CAPTIONS=$(
  caption "Window closed" 0.0 1.9
  caption "1  Handle servo turns the handle to tilt" 2.0 5.2
  caption "2  Arm servo pushes the sash open" 5.4 7.6
  caption "Window tilted" 7.7 9.9
  caption "3  Arm pulls the sash shut" 10.0 12.2
  caption "4  Handle turns back, window locked" 12.4 15.6
  caption "Window closed" 15.7 18.0
)
LABELS=$(
  inset_label "Handle unit, cut open" 0 5.45
  inset_label "Top unit, lintel hidden" 5.45 12.15
  inset_label "Handle unit, cut open" 12.15 18
)
NOTE="drawtext=fontfile=$FONT:text='Animation rendered from the STEP files':fontsize=22:fontcolor=white@0.85:x=48:y=h-58"

ffmpeg -v error -y -framerate 30 -i "$FRAMES/main/f_%04d.png" \
  -framerate 30 -i "$FRAMES/handle/f_%04d.png" \
  -framerate 30 -i "$FRAMES/top/f_%04d.png" \
  -filter_complex "
    [1]scale=450:450,format=rgba[h];
    [2]scale=450:450,format=rgba,fade=t=in:st=5.3:d=0.35:alpha=1,fade=t=out:st=11.95:d=0.35:alpha=1[t];
    [h][t]overlay=0:0,${LABELS%,}[ins];
    [ins]pad=w=iw+8:h=ih+8:x=4:y=4:color=white[insb];
    [0][insb]overlay=x=W-w-40:y=H-h-120,${CAPTIONS}${NOTE},format=yuv420p[v]" \
  -map "[v]" -c:v libx264 -preset slow -crf 20 -movflags +faststart "$OUT/demo.mp4"

ffmpeg -v error -y -i "$OUT/demo.mp4" -vf "fps=15,scale=540:-1:flags=lanczos" \
  -c:v libwebp_anim -quality 72 -compression_level 6 -loop 0 "$OUT/demo.webp"

ls -lh "$OUT/demo.mp4" "$OUT/demo.webp"
