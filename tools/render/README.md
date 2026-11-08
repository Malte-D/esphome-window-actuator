# Renders and demo animation

The pictures in [`docs/images`](../../docs/images) and the demo video in [`docs/media`](../../docs/media)
are rendered from the STEP files in [`print-files`](../../print-files). Re-run these steps after a part changes.

Everything printed comes from the STEP files, the PCB layout from `pcb/window-opener.brd`. The window,
the screws, the rod ends, the relay and the step-down converter are simple models.

### Optional models of the bought parts

The servo, the servo horn and the D1 mini look much better with these models from GrabCAD. They are
**not part of this repository** because their licences are unclear; download them yourself and
put them into a folder (e.g. `local/`, which is git-ignored):

| Part | GrabCAD | File in the folder |
|---|---|---|
| DSSERVO DS51150 | [servo-motor-ds51-150kg-…](https://grabcad.com/library/servo-motor-ds51-150kg-80kg-60-kg-servomotor-ds51150-ds5180-ds5160-1) | `DSSERVO/DSSERVO_150kg_80kg_60kg.STEP` |
| DS51 servo horn | [ds51-servo-motor-horn-…](https://grabcad.com/library/ds51-servo-motor-horn-gear-servomotor-1) | `DS51_18T_horn/DS51_18T_horn.STEP` |
| Wemos D1 mini | [wemos-d1-mini-6](https://grabcad.com/library/wemos-d1-mini-6) | `wemos-d1-mini-6.snapshot.1/wemos-mini-d1.stp` |

Pass the folder as the third argument of `prepare_meshes.py`. Without it, simple built-in shapes are used.

## Requirements

- [Blender](https://www.blender.org) 5.x (e.g. `brew install --cask blender`)
- Python 3 with the OpenCascade bindings and Pillow:
  `python3 -m venv .venv && .venv/bin/pip install cadquery-ocp pillow`
- ffmpeg with libx264 and libwebp

The scripts expect Blender at `/Applications/Blender.app/Contents/MacOS/Blender`; set `BLENDER` to override.

## Steps

```bash
# 1. STEP -> STL, including the cut-open halves of the handle unit (+ optional models, see above)
.venv/bin/python tools/render/prepare_meshes.py print-files build/meshes local

# 2. Video frames: main view + two close-ups (540 frames each, takes about an hour)
tools/render/render_all.sh build/meshes build/frames

# 3. Video and README preview
tools/render/compose.sh build/frames docs/media
# overview picture for the assembly guide: frame 1 of the main camera, 810 px wide
python3 -c "from PIL import Image; im = Image.open('build/frames/main/f_0001.png').convert('RGB'); \
  im.resize((810, 1012), Image.LANCZOS).save('docs/images/overview.jpg', quality=85)"

# 4. Pictures for the assembly guide
BLENDER=${BLENDER:-/Applications/Blender.app/Contents/MacOS/Blender}
for l in handle top handle_section top_linkage cables; do
  $BLENDER -b --factory-startup -P tools/render/stills.py -- \
    --meshes build/meshes --layout $l --out build/stills/$l.png --samples 64
done
.venv/bin/python tools/render/annotate.py build/stills/handle.png docs/images/handle-exploded.png
.venv/bin/python tools/render/annotate.py build/stills/top.png docs/images/top-exploded.png
.venv/bin/python tools/render/annotate.py build/stills/handle_section.png docs/images/handle-section.jpg
.venv/bin/python tools/render/annotate.py build/stills/top_linkage.png docs/images/top-linkage.jpg
.venv/bin/python tools/render/annotate.py build/stills/cables.png docs/images/cable-routing.jpg

# 5. PCB picture
$BLENDER -b --factory-startup -P tools/render/pcb.py -- --meshes build/meshes --out build/stills/pcb.png --samples 64
.venv/bin/python tools/render/annotate.py build/stills/pcb.png docs/images/pcb-connections.jpg

# 6. Bayonet close-up (270 frames, a few minutes)
$BLENDER -b --factory-startup -P tools/render/bayonet.py -- \
  --meshes build/meshes --out build/frames/bayonet/f_ --frames 1-270 --samples 32
tools/render/compose_bayonet.sh build/frames/bayonet docs/media
```

## Files

| File | Purpose |
|---|---|
| `prepare_meshes.py` | Converts the STEP files to STL, cuts the handle-unit housings along the spindle axis, converts the optional models to glTF |
| `scene.py` | Builds the window scene, places the parts, animates the sequence, renders one camera |
| `render_all.sh` | Renders all frames of the three cameras (`main`, `handle`, `top`) |
| `compose.sh` | Close-up inset, captions, MP4 and animated WebP |
| `stills.py` | Exploded views and labelled views for the assembly guide |
| `annotate.py` | Draws the labels onto the stills |
| `pcb.py` | Labelled picture of the PCB, built from the EAGLE board file; also builds the PCB in the handle unit |
| `bayonet.py` | Close-up animation of the bayonet coupler |
| `compose_bayonet.sh` | Captions, MP4 and animated WebP for the bayonet animation |

## Linkage geometry

On a real window the coupler length is set with the rod end threads, so there is no single
correct geometry. `scene.py` uses: 80 mm arm, about 110 mm between the two rod ends, pivot 36 mm
next to the servo axis, about 150° of servo travel for 130 mm opening at the top of the sash
(`ARM`, `PHI_CLOSED`, `PHI_OPEN`, `PIVOT_OFFSET`). The bayonet is shown locked, socket on the arm side.
