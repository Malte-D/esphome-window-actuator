"""Exploded views of both units for docs/assembly.md.

    blender -b --factory-startup -P tools/render/stills.py -- \
        --meshes build/meshes --layout handle --out build/stills/handle_exploded.png

Writes the PNG plus a JSON file with the screen position of every label
anchor; annotate.py turns both into the labelled picture.
"""

import json
import math
import os
import sys

import bpy
from bpy_extras.object_utils import world_to_camera_view
from mathutils import Matrix, Vector

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import scene  # noqa: E402  (reuses the window scene and its part placement)

LAYOUT = scene.ARGS.get("--layout", "handle")

# Offsets are in world millimetres. Handle unit: the spindle axis is world Y
# (window at +Y). Top unit: the servo axis is world Z.
LAYOUTS = {
    # in-situ views: rendered inside the window scene at a given frame
    "handle_section": {
        "frame": 58, "in_situ": "handle", "res": (1100, 1100),
        "labels": [
            # optional third element: anchor point in the local coordinates of the first object
            ("Window gear in the sash", ["gear"]),
            ("7 mm square spindle", ["spindle"], (-3.5, -55.0, 0.0)),
            ("Base", ["Base_keep"], (0.2, -37.0, 30.0)),
            ("ServoHornAdapter (servo horn inside)", ["ServoHornAdapter"]),
            ("DS51150 servo", ["handle_servo"], (-15.0, 18.0, 20.0)),
            ("Case", ["Case_keep"], (0.2, -1.0, 95.0)),
            ("ServoCover", ["ServoCover_keep"], (0.2, 39.0, -20.0)),
            ("PCB", ["pcb_d1"]),
            ("Original handle screws", ["base_screw0_head"]),
            ("Servo cable to D3", ["servo_cable1"], (0.0, 35.6, 25.0)),
        ],
    },
    "cables": {
        "frame": 1, "in_situ": "main", "res": (1080, 1350),
        "labels": [
            ("Top unit", ["ServoCoverMount"]),
            ("Duct for the servo extension cable", ["duct_top0"]),
            ("Handle unit", ["Case_keep", "Case_gone"]),
            ("Angled plug, ferrite", ["power_ferrite"]),
            ("Duct for the power cable", ["duct_power1"]),
            ("Power cable leaves the sash at the hinge side", ["power_cable_duct"], (866.0, -40.0, 40.0)),
        ],
    },
    "top_linkage": {
        "frame": 236, "in_situ": "top", "res": (1100, 1100),
        "labels": [
            ("TopPivotMount (lintel hidden)", ["TopPivotMount"]),
            ("Rod end on the pin, M4×16", ["rod_b_eye"]),
            ("Bayonet coupler", ["bayonet_socket"]),
            ("Rod end, M6×25", ["rod_a_eye"]),
            ("ServoArm", ["ServoArm"]),
            ("ServoCoverMount", ["ServoCoverMount"]),
            ("Sash, tilted", ["rsash_top"]),
        ],
    },
    "handle": {
        "keep": ["handle_unit"],
        "label_layout": "topbottom",   # texts above and below: the parts are spread out horizontally
        "offsets": {
            "spindle": (0, 135, 0),
            "Base": (0, 82, 0), "PCBHolder": (0, 82, 0), "pcb": (0, 82, 0), "base_screw": (0, 82, 0),
            # on the axis between servo and spindle
            "ServoHornAdapter": (0, 46, 0), "handle_horn": (0, 46, 0),
            # the M4 screws go from the side of the case into the base: shown next to the base
            "Case": (0, 0, 0), "m4_screw0": (-14, 82, 0), "m4_screw1": (-14, 82, 0), "m4_screw2": (14, 82, 0),
            "handle_servo": (0, -50, 0), "grommet": (0, -50, 0), "servo_screw": (0, -112, 0),
            "CoverSnap": (0, -82, 0), "ServoCover": (0, -135, 0),
        },
        "camera": ((-0.50, -0.42, 0.86), (0.080, -0.090, 0.575), 56.0),
        "res": (1500, 950),
        "labels": [
            ("7 mm square spindle", ["spindle"]),
            ("Base", ["Base_keep", "Base_gone"]),
            ("2× original handle screws", ["base_screw0"]),
            ("PCB holder + PCB", ["pcb_board"]),
            ("ServoHornAdapter on the horn, 2× M3×10", ["ServoHornAdapter"]),
            ("Case", ["Case_keep", "Case_gone"]),
            ("3× M4×16 countersunk", ["m4_screw1", "m4_screw1_shaft"]),
            ("DS51150 servo (270°)", ["handle_servo_body"]),
            ("4× rubber grommet", ["grommet3_hi"]),
            ("2× CoverSnap", ["CoverSnap0_keep", "CoverSnap0_gone"]),
            ("4× M3×25", ["servo_screw2_shaft"]),
            ("ServoCover", ["ServoCover_keep", "ServoCover_gone"]),
        ],
    },
    "top": {
        "keep": ["move_unit", "pivot_mount", "coupler"],
        "offsets": {
            # servo, grommets and NutHolders straight down along the servo axis, horn and arm above it
            "move_servo": (0, 0, -85), "top_grommet": (0, 0, -85), "NutHolder": (0, 0, -128),
            "move_horn": (0, 0, 22), "ServoArm": (0, 0, 42), "arm_bolt": (0, 0, 150),
            "coupler": (0, 0, 98), "pivot_screw_head": (0, 0, 58), "TopPivotMount": (0, 0, 150),
        },
        "camera": ((0.20, -0.50, 1.80), (0.548, -0.045, 1.478), 40.0),
        "res": (1500, 1150),
        "labels": [
            ("ServoCoverMount — hot glue", ["ServoCoverMount"]),
            ("DS51150 servo, 4× M3×25", ["move_servo_body"]),
            ("2× NutHolder + M3 nuts", ["NutHolder0"]),
            ("4× rubber grommet", ["top_grommet0_lo"]),
            ("Servo horn, 2× M3×10 countersunk", ["move_horn_body"]),
            ("ServoArm (M6 nut inside)", ["ServoArm"]),
            ("M6×25", ["arm_bolt_head"]),
            ("Rod end M6", ["rod_a_eye"]),
            ("Bayonet coupler: socket, O-ring 10×2, plug", ["bayonet_oring"]),
            ("M4×16, nut in the mount", ["pivot_screw_head"]),
            ("TopPivotMount — hot glue", ["TopPivotMount"]),
        ],
    },
}


def in_tree(obj, roots):
    while obj is not None:
        if obj.name in roots:
            return True
        obj = obj.parent
    return False


def bbox_center(objs):
    pts = [o.matrix_world @ Vector(c) for o in objs for c in o.bound_box]
    return sum(pts, Vector()) / len(pts)


def add_screws(parent):
    """Screws of the handle unit (only drawn in the exploded view)."""
    steel = scene.material("steel", rough=0.3, metal=1.0)
    for i, (x, z) in enumerate(((8.5, -19.7), (-8.5, -19.7), (8.5, 55.3), (-8.5, 55.3))):
        top = 13.0 + scene.COVERSNAP_SHIFT          # head on the CoverSnap
        scene.cylinder(f"servo_screw{i}", 2.75, 3.0, steel, parent, depth_axis="Y", center=(x, top + 1.5, z))
        scene.cylinder(f"servo_screw{i}_shaft", 1.5, 25, steel, parent, depth_axis="Y", center=(x, top - 12.5, z))
    for obj in [o for o in bpy.data.objects if o.name.startswith("case_screw")]:
        obj.hide_render = True
    # M4x16 countersunk, inserted from the sides of the case (sign = direction of insertion along X).
    # The cone of the head is widest at the outer face, where the head sits flush with the case.
    for i, (x, z, sign) in enumerate(((-24.0, 21.5, 1), (-24.0, -21.5, 1), (46.0, 0.0, -1))):
        r_minus_x, r_plus_x = (4.0, 2.0) if sign > 0 else (2.0, 4.0)   # cylinder(): radius at -X, r2 at +X
        scene.cylinder(f"m4_screw{i}", r_minus_x, 2.2, steel, parent, depth_axis="X",
                       center=(x - sign * 1.1, -37.05, z), r2=r_plus_x)
        scene.cylinder(f"m4_screw{i}_shaft", 2.0, 14, steel, parent, depth_axis="X", center=(x + sign * 7, -37.05, z))


def project_labels(cfg):
    sc = bpy.context.scene
    bpy.context.view_layer.update()
    labels = []
    for text, names, *point in cfg["labels"]:
        targets = [bpy.data.objects[n] for n in names if n in bpy.data.objects]
        if not targets:
            print("missing label target", names)
            continue
        anchor = targets[0].matrix_world @ Vector(point[0]) if point else bbox_center(targets)
        p = world_to_camera_view(sc, sc.camera, anchor)
        labels.append({"text": text, "x": p.x * cfg["res"][0], "y": (1 - p.y) * cfg["res"][1]})
    return labels


def write(cfg, labels):
    sc = bpy.context.scene
    out = os.path.abspath(scene.ARGS["--out"])
    os.makedirs(os.path.dirname(out), exist_ok=True)
    sc.render.filepath = out
    bpy.ops.render.render(write_still=True)
    with open(os.path.splitext(out)[0] + ".json", "w") as fh:
        json.dump({"size": cfg["res"], "labels": labels}, fh, indent=1)


def render_in_situ(cfg):
    sc = bpy.context.scene
    if cfg["in_situ"] not in scene.CUTAWAY_CAMS:
        scene.disable_cutaway()
    sc.frame_set(cfg["frame"])
    loc, target, lens, _res, hidden = scene.CAMERAS[cfg["in_situ"]]
    scene.CAMERAS["still"] = (loc, target, lens, cfg["res"], hidden)
    scene.setup_render("still")
    sc.frame_set(cfg["frame"])
    write(cfg, project_labels(cfg))


def main():
    cfg = LAYOUTS[LAYOUT]
    objs = scene.build()
    scene.animate(objs)
    if "in_situ" in cfg:
        render_in_situ(cfg)
        return
    if LAYOUT == "handle":
        add_screws(bpy.data.objects["handle_unit"])
    bpy.context.scene.frame_set(1)
    # freeze the closed pose, otherwise the animation overrides the explode offsets
    for obj in bpy.data.objects:
        if obj.animation_data:
            m = obj.matrix_basis.copy()
            obj.animation_data_clear()
            obj.matrix_basis = m

    # solid materials, no cutaway
    for m in bpy.data.materials:
        if m.name.endswith("_fade"):
            if m.node_tree.animation_data:
                m.node_tree.animation_data_clear()
            m.node_tree.nodes["Principled BSDF"].inputs["Alpha"].default_value = 1.0
            m.surface_render_method = "DITHERED"

    keep_roots = set(cfg["keep"])
    for obj in bpy.data.objects:
        if obj.type in {"MESH", "CURVE"} and not in_tree(obj, keep_roots):
            obj.hide_render = True
    # the cut-away stile and gear are part of the sash, hide them too; cables only in the assembled views
    for obj in bpy.data.objects:
        if obj.name.startswith(("rsash", "gear", "cable", "servo_cable")):
            obj.hide_render = True

    # explode: move every object whose name starts with a key
    bpy.context.view_layer.update()
    moved = set()
    for obj in sorted(bpy.data.objects, key=lambda o: len(o.name)):
        for key, off in cfg["offsets"].items():
            if obj.name.startswith(key) and not any(in_tree(obj.parent, {m}) for m in moved):
                obj.matrix_world = Matrix.Translation(Vector(off) * 0.001) @ obj.matrix_world
                moved.add(obj.name)
                break
    bpy.context.view_layer.update()

    loc, target, lens = cfg["camera"]
    scene.CAMERAS["still"] = (loc, target, lens, cfg["res"], ())
    scene.setup_render("still")
    sc = bpy.context.scene
    sc.world.node_tree.nodes["Background"].inputs["Color"].default_value = (1, 1, 1, 1)
    sc.world.node_tree.nodes["Background"].inputs["Strength"].default_value = 0.9
    sc.render.film_transparent = True
    for name in ("sun",):
        bpy.data.objects[name].hide_render = True
    bpy.data.lights["key"].energy = 160
    bpy.data.lights["fill"].energy = 60

    bpy.context.view_layer.update()
    cam = sc.camera
    labels = []
    for text, names in cfg["labels"]:
        targets = [bpy.data.objects[n] for n in names if n in bpy.data.objects]
        if not targets:
            print("missing label target", names)
            continue
        p = world_to_camera_view(sc, cam, bbox_center(targets))
        labels.append({"text": text, "x": p.x * cfg["res"][0], "y": (1 - p.y) * cfg["res"][1]})

    out = os.path.abspath(scene.ARGS["--out"])
    os.makedirs(os.path.dirname(out), exist_ok=True)
    sc.render.filepath = out
    bpy.ops.render.render(write_still=True)
    with open(os.path.splitext(out)[0] + ".json", "w") as fh:
        json.dump({"size": cfg["res"], "labels": labels, "layout": cfg.get("label_layout", "sides")}, fh, indent=1)


main()
