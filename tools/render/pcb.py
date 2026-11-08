"""Labelled render of the PCB (which servo goes where).

    blender -b --factory-startup -P tools/render/pcb.py -- --meshes build/meshes --out build/stills/pcb.png
    python tools/render/annotate.py build/stills/pcb.png docs/images/pcb-connections.png

Pad, hole and text positions are read from pcb/window-opener.brd. The D1 mini
uses the optional third-party model (see prepare_meshes.py) when it was converted,
otherwise a simple box. The relay, the step-down converter, the jack and the
servo plugs are simple boxes with roughly the right size. build_board() is also
used by scene.py for the PCB inside the handle unit.
"""

import math
import os
import sys
import json
import xml.etree.ElementTree as ET

import bpy
from bpy_extras.object_utils import world_to_camera_view
from mathutils import Matrix, Vector

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import scene  # noqa: E402  (helpers: material, box, cylinder, empty)
from scene import box, cylinder, empty, material  # noqa: E402

BRD = os.path.join(HERE, "..", "..", "pcb", "window-opener.brd")
OUT = scene.ARGS.get("--out", "build/stills/pcb.png")
RES = (900, 1500)

# servo wire colours: brown = GND (-), red = +, orange = signal (S)
WIRE_COLORS = [(0.20, 0.08, 0.03), (0.65, 0.04, 0.03), (0.95, 0.22, 0.02)]


def parse_board():
    root = ET.parse(BRD).getroot()
    packages = {(lib.get("name"), p.get("name")): p
                for lib in root.iter("library") for p in lib.iter("package")}
    elements = {}
    for e in root.iter("element"):
        rot = e.get("rot") or "R0"
        mirror = rot.startswith("M")
        angle = math.radians(float(rot.lstrip("MSR") or 0))
        ex, ey = float(e.get("x")), float(e.get("y"))
        pads = []
        for q in list(packages[(e.get("library"), e.get("package"))].iter("pad")) + \
                list(packages[(e.get("library"), e.get("package"))].iter("smd")):
            x, y = float(q.get("x")), float(q.get("y"))
            if mirror:
                x = -x
            c, s = math.cos(angle), math.sin(angle)
            pads.append(dict(name=q.get("name"), tag=q.tag, x=ex + c * x - s * y, y=ey + s * x + c * y,
                             drill=float(q.get("drill") or 0), shape=q.get("shape") or "",
                             dx=float(q.get("dx") or 0), dy=float(q.get("dy") or 0), rot=angle))
        elements[e.get("name")] = dict(x=ex, y=ey, mirror=mirror, pads=pads)
    holes = [(float(h.get("x")), float(h.get("y")), float(h.get("drill"))) for h in root.iter("hole")]
    texts = [(float(t.get("x")), float(t.get("y")), float(t.get("size")), t.text)
             for t in root.find("drawing/board/plain").iter("text") if t.get("layer") in ("21", "25")]
    return elements, holes, texts


def text(name, body, x, y, size, mat, parent):
    curve = bpy.data.curves.new(name, "FONT")
    curve.body = body
    curve.size = size * 1.25
    curve.space_line = 1.0
    obj = bpy.data.objects.new(name, curve)
    bpy.context.scene.collection.objects.link(obj)
    obj.parent = parent
    obj.location = (x, y, 0.05)
    obj.data.materials.append(mat)
    return obj


def import_d1_mini(parent, prefix):
    """Third-party D1 mini model (see prepare_meshes.py), or None if it was not converted."""
    # model: board centre at the origin, USB at +X, ESP module on top (+Z), pin rows at Y = +-11.4,
    # board underside at Z = -0.5. On our board the USB end points to -Y and the module sits on
    # 8.5 mm headers.
    xf = Matrix(((0, 1, 0, 20.73), (-1, 0, 0, 17.13), (0, 0, 1, 9.0), (0, 0, 0, 1)))
    holder = scene.import_glb("ext_d1mini", prefix + "d1_model", parent, xf)
    if holder is not None:
        for obj in holder.children_recursive:
            if obj.type == "MESH" and obj.name.split(".")[0].endswith("_PCB"):
                obj.name = prefix + "d1"
    return holder


def step_down(prefix, icx, icy, root, black, metal):
    """3-pin DC-DC module in the 7805 footprint: small board standing upright, parts facing -Y."""
    green = material("stepdown_green", (0.04, 0.30, 0.10), rough=0.35)
    box(prefix + "stepdown_header", icx - 3.8, icx + 3.8, icy - 1.25, icy + 1.25, 0, 2.5, black, root, bevel=0.2)
    for dx in (-2.54, 0, 2.54):
        box(prefix + f"stepdown_pin_{dx}", icx + dx - 0.32, icx + dx + 0.32, icy - 0.32, icy + 0.32, 0, 4.0, metal,
            root, bevel=0)
    box(prefix + "stepdown", icx - 5.6, icx + 5.6, icy - 0.5, icy + 0.5, 3.6, 21.0, green, root, bevel=0.2)
    f = icy - 0.5      # component side
    box(prefix + "stepdown_inductor", icx - 3.1, icx + 3.1, f - 3.0, f, 13.0, 19.6,
        material("inductor", (0.26, 0.26, 0.28), rough=0.5), root, bevel=0.5)
    box(prefix + "stepdown_ic", icx - 4.4, icx + 0.4, f - 1.5, f, 7.0, 11.4, black, root, bevel=0.15)
    box(prefix + "stepdown_cap", icx + 1.2, icx + 4.6, f - 1.9, f, 5.0, 7.8,
        material("cap_dark", (0.06, 0.06, 0.07), rough=0.4), root, bevel=0.2)
    box(prefix + "stepdown_mlcc", icx + 1.4, icx + 4.4, f - 1.5, f, 8.6, 10.4,
        material("mlcc", (0.62, 0.50, 0.35), rough=0.6), root, bevel=0.15)


def build_board(root, prefix="pcb_", wires=True):
    """Populated PCB in board coordinates (mm): origin at the board corner, component side +Z."""
    green = material("pcb_green", (0.03, 0.20, 0.08), rough=0.35)
    pad_mat = material("pad", (0.80, 0.80, 0.78), rough=0.25, metal=1.0)
    hole_mat = material("hole", (0.01, 0.01, 0.01), rough=0.9)
    silk = material("silk", (0.92, 0.92, 0.92), rough=0.6)
    black = material("black_plastic", (0.015, 0.015, 0.017), rough=0.45)
    blue_d1 = material("d1_blue", (0.02, 0.10, 0.40), rough=0.35)
    blue_relay = material("relay_blue", (0.04, 0.18, 0.55), rough=0.3)
    metal = material("tin", (0.82, 0.82, 0.84), rough=0.2, metal=1.0)

    elements, holes, texts = parse_board()
    P = prefix

    box(P + "board", 0, 35, 0, 60, -1.6, 0, green, root, bevel=0.3)
    for e_name, e in elements.items():
        if e["mirror"]:          # parts on the bottom (optional 0 R bridges), not visible
            continue
        for p in e["pads"]:
            if p["tag"] == "smd":
                w, h = (p["dx"], p["dy"]) if abs(math.sin(p["rot"])) < 0.5 else (p["dy"], p["dx"])
                box(f"{P}pad_{e_name}_{p['name']}", p["x"] - w / 2, p["x"] + w / 2, p["y"] - h / 2, p["y"] + h / 2,
                    0, 0.05, pad_mat, root, bevel=0)
            else:
                r = max(p["drill"] / 2 + 0.45, 0.8)
                cylinder(f"{P}pad_{e_name}_{p['name']}", r, 0.06, pad_mat, root, center=(p["x"], p["y"], 0.03))
                cylinder(f"{P}drill_{e_name}_{p['name']}", p["drill"] / 2, 0.08, hole_mat, root,
                         center=(p["x"], p["y"], 0.04))
    for i, (x, y, d) in enumerate(holes):
        cylinder(f"{P}mount_hole_{i}", d / 2, 0.1, hole_mat, root, center=(x, y, 0.05))
    for i, (x, y, size, body) in enumerate(texts):
        # Eagle anchors multi-line text at the last line, line pitch is 1.5 x size
        lines = body.replace("3V\nG", "3V3\nG").split("\n")
        for j, line in enumerate(lines):
            text(f"{P}silk_{i}_{j}", line, x, y + (len(lines) - 1 - j) * size * 1.5, size, silk, root)

    # ---- Wemos D1 mini on two 8-pin headers ---------------------------------
    d1 = elements["WEMOS2"]
    xs = sorted({round(p["x"], 2) for p in d1["pads"]})
    ys = [p["y"] for p in d1["pads"]]
    for x in xs:
        box(f"{P}d1_header_{x}", x - 1.27, x + 1.27, min(ys) - 1.27, max(ys) + 1.27, 0, 8.5, black, root, bevel=0.2)
    if import_d1_mini(root, P) is None:
        cx = sum(xs) / 2
        y0, y1 = min(ys) - 6.6, max(ys) + 9.9          # USB end at the bottom, antenna at the top
        box(P + "d1", cx - 12.8, cx + 12.8, y0, y1, 8.5, 9.5, blue_d1, root, bevel=0.4)
        box(P + "d1_shield", cx - 6.0, cx + 6.0, y1 - 22.5, y1 - 7.5, 9.5, 12.0, metal, root, bevel=0.3)
        box(P + "d1_antenna", cx - 8.0, cx + 8.0, y1 - 6.5, y1 - 1.0, 9.5, 9.55,
            material("antenna", (0.55, 0.42, 0.12), 0.3, 1.0), root, bevel=0)
        box(P + "d1_usb", cx - 3.8, cx + 3.8, y0 - 0.8, y0 + 4.6, 9.5, 12.3, metal, root, bevel=0.4)
        box(P + "d1_chip", cx - 2.0, cx + 2.6, y0 + 7.0, y0 + 11.0, 9.5, 10.6, black, root, bevel=0.2)

    # ---- relay, step-down converter, DC jack ------------------------------------
    rl = elements["U$1"]["pads"]
    rx0, rx1 = min(p["x"] for p in rl) - 3.4, max(p["x"] for p in rl) + 1.6
    ry = sum(p["y"] for p in rl) / len(rl)
    box(P + "relay", rx0, rx1, ry - 7.75, ry + 7.75, 0, 15.3, blue_relay, root, bevel=0.6)

    ic = elements["IC1"]["pads"]
    step_down(P, sum(p["x"] for p in ic) / 3, ic[0]["y"], root, black, metal)

    jack = elements["12V"]
    box(P + "dc_jack", jack["x"] - 4.5, jack["x"] + 4.5, jack["y"] - 14.4, jack["y"], 0, 11.0, black, root, bevel=0.5)
    cylinder(P + "dc_jack_opening", 3.2, 0.6, hole_mat, root, depth_axis="Y", center=(jack["x"], jack["y"] + 0.05, 6.0))
    cylinder(P + "dc_jack_pin", 1.0, 0.8, metal, root, depth_axis="Y", center=(jack["x"], jack["y"] + 0.1, 6.0))

    # ---- small SMD parts ---------------------------------------------------------
    for name in ("Q1", "R1", "R2"):
        pads = elements[name]["pads"]
        px = [p["x"] for p in pads]
        py = [p["y"] for p in pads]
        box(P + name.lower(), min(px) - 0.3, max(px) + 0.3, min(py) - 0.6, max(py) + 0.6, 0.05, 0.9, black, root,
            bevel=0.1)

    # ---- servo headers with plugs and wires -------------------------------------
    for jp, label in (("JP1", "handle"), ("JP2", "arm")):
        pads = sorted(elements[jp]["pads"], key=lambda p: p["name"])
        x0, x1 = pads[0]["x"], pads[-1]["x"]
        y = pads[0]["y"]
        box(f"{P}{jp}_header", x0 - 1.27, x1 + 1.27, y - 1.27, y + 1.27, 0, 2.5, black, root, bevel=0.2)
        box(f"{P}{jp}_plug", x0 - 1.5, x1 + 1.5, y - 1.5, y + 1.5, 2.5, 16.5, black, root, bevel=0.4)
        for i, p in enumerate(pads):
            curve = bpy.data.curves.new(f"{P}wire_{label}_{i}", "CURVE")
            curve.dimensions = "3D"
            curve.bevel_depth = 0.62
            curve.bevel_resolution = 4
            spl = curve.splines.new("BEZIER")
            end = (p["x"] + (i - 1) * 0.2, 95.0, 20.5) if wires else (p["x"], y + 3.0, 19.5)
            pts = [(p["x"], y, 16.0), (p["x"], y + (6.0 if wires else 1.0), 19.2), end]
            spl.bezier_points.add(len(pts) - 1)
            for bp, co in zip(spl.bezier_points, pts):
                bp.co = co
                bp.handle_left_type = bp.handle_right_type = "AUTO"
            obj = bpy.data.objects.new(f"{P}wire_{label}_{i}", curve)
            bpy.context.scene.collection.objects.link(obj)
            obj.parent = root
            obj.data.materials.append(material(f"wire_{i}", WIRE_COLORS[i], rough=0.45))
    return elements


def build():
    for obj in list(bpy.data.objects):
        bpy.data.objects.remove(obj)
    root = empty("mm_root")
    root.scale = (0.001, 0.001, 0.001)
    return build_board(root, prefix="")


def setup(elements):
    sc = bpy.context.scene
    cam_data = bpy.data.cameras.new("pcb_cam")
    cam_data.type = "ORTHO"
    cam_data.ortho_scale = 0.096
    cam = bpy.data.objects.new("pcb_cam", cam_data)
    sc.collection.objects.link(cam)
    target = Vector((0.0185, 0.0420, 0.004))
    direction = Vector((0.30, 0.22, -1.0)).normalized()    # from the front left, slightly tilted
    z = -direction
    x = Vector((0, 1, 0)).cross(z).normalized()
    y = z.cross(x)
    cam.matrix_world = Matrix((
        (x.x, y.x, z.x, target.x - direction.x * 0.4),
        (x.y, y.y, z.y, target.y - direction.y * 0.4),
        (x.z, y.z, z.z, target.z - direction.z * 0.4),
        (0, 0, 0, 1)))
    sc.camera = cam

    world = bpy.data.worlds.new("world")
    world.use_nodes = True
    world.node_tree.nodes["Background"].inputs["Color"].default_value = (1, 1, 1, 1)
    world.node_tree.nodes["Background"].inputs["Strength"].default_value = 0.3
    sc.world = world
    for name, loc, energy, size in (("key", (-0.15, -0.10, 0.35), 6, 0.25), ("fill", (0.25, 0.05, 0.25), 2, 0.4)):
        light = bpy.data.lights.new(name, "AREA")
        light.energy = energy
        light.size = size
        obj = bpy.data.objects.new(name, light)
        sc.collection.objects.link(obj)
        obj.location = loc
        obj.rotation_euler = (Vector((0.018, 0.04, 0)) - Vector(loc)).to_track_quat("-Z", "Y").to_euler()

    sc.render.engine = "BLENDER_EEVEE"
    sc.eevee.taa_render_samples = int(scene.ARGS["--samples"])
    try:
        sc.eevee.use_raytracing = True
    except AttributeError:
        pass
    sc.view_settings.view_transform = "Standard"
    sc.view_settings.exposure = -0.3
    sc.render.resolution_x, sc.render.resolution_y = RES
    sc.render.film_transparent = True
    sc.render.image_settings.file_format = "PNG"


def labels(elements):
    jp1 = elements["JP1"]
    jp2 = elements["JP2"]
    jack = elements["12V"]
    ic = elements["IC1"]
    return [
        ("D3: handle servo", (jp1["x"], 74.0, 20.2)),
        ("D1: arm servo", (jp2["x"], 82.0, 20.3)),
        ("brown (−) left, orange (S) right", (jp2["x"] - 2.54, jp2["y"] + 1.5, 12.0)),
        ("Relay: servo power on/off (D2)", (11.6, 43.8, 15.3)),
        ("Spare pins (not used)", (2.54, 22.86, 0.1)),
        ("12 V in (5.5 × 2.1 mm)", (jack["x"], jack["y"] - 4.0, 11.0)),
        ("Step-down converter 12 V → 5 V", (ic["x"], ic["y"] - 2.0, 18.0)),
        ("Wemos D1 mini (ESP8266)", (20.7, 26.0, 12.0)),
    ]


def main():
    elements = build()
    setup(elements)
    sc = bpy.context.scene
    bpy.context.view_layer.update()
    out = os.path.abspath(OUT)
    os.makedirs(os.path.dirname(out), exist_ok=True)
    meta = []
    for text_, (x, y, z) in labels(elements):
        p = world_to_camera_view(sc, sc.camera, Vector((x, y, z)) * 0.001)
        meta.append({"text": text_, "x": p.x * RES[0], "y": (1 - p.y) * RES[1]})
    sc.render.filepath = out
    bpy.ops.render.render(write_still=True)
    with open(os.path.splitext(out)[0] + ".json", "w") as fh:
        json.dump({"size": RES, "labels": meta}, fh, indent=1)


if __name__ == "__main__":
    main()
