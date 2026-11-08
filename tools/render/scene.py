"""Blender scene for the demo video and the assembly renders.

Run with Blender 5.x (headless):
    blender -b --factory-startup -P tools/render/scene.py -- \
        --meshes build/meshes --cam main --out build/frames/main_ --frames 1-540

Arguments (after "--"):
    --meshes DIR     STL meshes written by prepare_meshes.py
    --cam NAME       main | handle | top  (see CAMERAS)
    --out PATH       output path prefix (frames) or file (single still)
    --frames A-B     frame range, or a single frame number for a still
    --res WxH        resolution, defaults per camera
    --samples N      Eevee samples (default 32)
    --save FILE      also save the .blend file

All scene geometry is modelled in millimetres below an empty that scales it
to metres. World axes: X to the right (seen from the room), Y towards the
window/outside, Z up. The room-facing surface of the window frame is Y = 0.

The linkage geometry (arm length, pivot position, servo angles) is an
assumption that matches the prototype only roughly: on the real window the
coupler length is set with the rod end threads.
"""

import math
import os
import sys

import bmesh
import bpy
from mathutils import Matrix, Vector

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))   # for pcb.py

# --------------------------------------------------------------------------
# Arguments
# --------------------------------------------------------------------------
argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
ARGS = {"--meshes": "build/meshes", "--cam": "main", "--out": "build/frames/main_",
        "--frames": "1-540", "--res": "", "--samples": "32", "--save": ""}
for i in range(0, len(argv) - 1, 2):
    ARGS[argv[i]] = argv[i + 1]
MESHES = os.path.abspath(ARGS["--meshes"])

# --------------------------------------------------------------------------
# Geometry constants (mm)
# --------------------------------------------------------------------------
SASH_FACE_Y = -15.0          # room face of the sash, 15 mm proud of the frame
SASH = dict(x0=32, x1=878, z0=52, z1=1448, face=80, y1=60)
HINGE = Vector((0, 0, 52))   # tilt axis of the sash (parallel to X)
SPINDLE = Vector((70, 0, 600))  # handle spindle position (X, -, Z)
SERVO_X = 560.0              # movement servo axis (X)
STURZ_Z = 1500.0             # underside of the lintel = top of the frame

# Handle unit: STEP assembly coordinates -> world = (x, -y, -z) + offset
HANDLE_OFFSET = Vector((SPINDLE.x, SASH_FACE_Y - 46.35, SPINDLE.z))

# Movement unit: ServoCoverMount STEP coordinates -> world = (z, x, y) + offset
SHAFT_LOCAL = Vector((81.34, 0, 103.64))       # servo axis in ServoCoverMount coords
MOVE_OFFSET = Vector((SERVO_X - SHAFT_LOCAL.z, SASH_FACE_Y - 97.0, SASH["z1"] - 4.6))
HORN_TOP = 18.3 - 2.25       # local Y of the horn top face / arm pocket floor (servo on grommets)
BALL_A_UP = 12.5             # ball centre above the arm pocket floor

# TopPivotMount STEP coordinates -> world = (-x, z, y) + offset
PIN_LOCAL = Vector((-58.04, -7.5, 43.54))      # ball centre on the pin
PIVOT_OFFSET = Vector((SERVO_X - 36.0 + PIN_LOCAL.x, -66.0, STURZ_Z - 5.0))

ARM = 80.0                   # servo arm length (axis to M6 bolt)
PHI_CLOSED = math.radians(-60)
PHI_OPEN = math.radians(-210)

# --------------------------------------------------------------------------
# Timeline (30 fps)
# --------------------------------------------------------------------------
FPS = 30
T_FADE = (30, 54)            # cutaway fades in
T_HANDLE_OPEN = (60, 150)    # 3 s, like transition_length of servo_handle
T_ARM_OPEN = (165, 225)      # 2 s, like transition_length of servo_movement
T_ARM_CLOSE = (300, 360)
T_HANDLE_CLOSE = (375, 465)
T_UNFADE = (495, 519)
FRAME_END = 540

COLORS = {
    "print": (0.86, 0.85, 0.81), "print_moving": (0.86, 0.85, 0.81),   # moving parts: same colour
    "section": (0.89, 0.30, 0.17), "upvc": (0.95, 0.95, 0.94),
    "wall": (0.82, 0.80, 0.76), "sill": (0.06, 0.06, 0.065),
    "servo": (0.04, 0.04, 0.045), "alu": (0.75, 0.77, 0.80), "steel": (0.55, 0.56, 0.58),
    "pcb": (0.05, 0.30, 0.15), "d1": (0.05, 0.20, 0.55), "relay": (0.10, 0.25, 0.70),
    "cable": (0.65, 0.33, 0.08), "gear": (0.30, 0.31, 0.33), "gasket": (0.08, 0.08, 0.08),
    # DS51150: magenta label band and anodised horn
    "servo_label": (0.38, 0.006, 0.045), "servo_text": (0.70, 0.70, 0.70), "sticker": (0.85, 0.85, 0.85),
    "horn_magenta": (0.38, 0.006, 0.045), "grommet": (0.02, 0.02, 0.02),
}

# --------------------------------------------------------------------------
# Helpers
# --------------------------------------------------------------------------
_mats = {}


def material(name, color=None, rough=0.5, metal=0.0, alpha=1.0, emission=None):
    if name in _mats:
        return _mats[name]
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    bsdf = m.node_tree.nodes["Principled BSDF"]
    bsdf.inputs["Base Color"].default_value = (*(color or COLORS[name]), 1)
    bsdf.inputs["Roughness"].default_value = rough
    bsdf.inputs["Metallic"].default_value = metal
    bsdf.inputs["Alpha"].default_value = alpha
    if alpha < 1.0:
        m.surface_render_method = "BLENDED"
    if emission:
        bsdf.inputs["Emission Color"].default_value = (*emission, 1)
        bsdf.inputs["Emission Strength"].default_value = 1.0
    _mats[name] = m
    return m


def fade_material(base_name):
    """Copy of a material whose alpha is animated for the cutaway."""
    name = base_name + "_fade"
    if name in _mats:
        return _mats[name]
    m = material(base_name).copy()
    m.name = name
    m.surface_render_method = "BLENDED"
    alpha = m.node_tree.nodes["Principled BSDF"].inputs["Alpha"]
    for frame, value in ((1, 1.0), (T_FADE[0], 1.0), (T_FADE[1], 0.0),
                         (T_UNFADE[0], 0.0), (T_UNFADE[1], 1.0)):
        alpha.default_value = value
        alpha.keyframe_insert("default_value", frame=frame)
    _mats[name] = m
    return m


def new_object(name, mesh, parent, mat=None):
    obj = bpy.data.objects.new(name, mesh)
    bpy.context.scene.collection.objects.link(obj)
    obj.parent = parent
    if mat:
        obj.data.materials.append(mat)
    return obj


def empty(name, parent=None, loc=(0, 0, 0), rot=None):
    e = bpy.data.objects.new(name, None)
    bpy.context.scene.collection.objects.link(e)
    e.parent = parent
    e.location = loc
    if rot is not None:
        e.rotation_mode = "QUATERNION"
        e.rotation_quaternion = rot.to_quaternion()
    return e


def box(name, x0, x1, y0, y1, z0, z1, mat, parent, bevel=1.2):
    bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=1.0)
    for v in bm.verts:
        v.co = Vector(((x0 + x1) / 2 + v.co.x * (x1 - x0), (y0 + y1) / 2 + v.co.y * (y1 - y0),
                       (z0 + z1) / 2 + v.co.z * (z1 - z0)))
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    obj = new_object(name, me, parent, mat)
    if bevel:
        mod = obj.modifiers.new("bevel", "BEVEL")
        mod.width = bevel
        mod.segments = 2
        mod.limit_method = "ANGLE"
    return obj


def cylinder(name, radius, length, mat, parent, segments=48, depth_axis="Z", center=(0, 0, 0), r2=None):
    bm = bmesh.new()
    bmesh.ops.create_cone(bm, cap_ends=True, segments=segments, radius1=radius,
                          radius2=radius if r2 is None else r2, depth=length)
    rot = {"Z": Matrix.Identity(4), "X": Matrix.Rotation(math.pi / 2, 4, "Y"),
           "Y": Matrix.Rotation(-math.pi / 2, 4, "X")}[depth_axis]
    bmesh.ops.transform(bm, matrix=Matrix.Translation(center) @ rot, verts=bm.verts)
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    obj = new_object(name, me, parent, mat)
    obj.data.shade_smooth()
    obj.data.set_sharp_from_angle(angle=math.radians(40))
    return obj


def import_stl(stem, name, mat, parent, vertex_xform=None, section=False):
    path = os.path.join(MESHES, stem + ".stl")
    bpy.ops.wm.stl_import(filepath=path, forward_axis="Y", up_axis="Z", global_scale=1.0)
    obj = bpy.context.selected_objects[0]
    obj.name = name
    me = obj.data
    bm = bmesh.new()
    bm.from_mesh(me)
    bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=0.002)
    if section:  # faces lying on the cut plane x = 0 get the section colour
        for f in bm.faces:
            c = f.calc_center_median()
            f.material_index = 1 if abs(c.x) < 0.02 and f.normal.x < -0.99 else 0
    if vertex_xform is not None:
        bmesh.ops.transform(bm, matrix=vertex_xform, verts=bm.verts)
        if vertex_xform.determinant() < 0:   # mirrored: keep the normals pointing outwards
            bmesh.ops.reverse_faces(bm, faces=bm.faces)
    bm.to_mesh(me)
    bm.free()
    me.materials.clear()
    me.materials.append(mat)
    if section:
        me.materials.append(material("section", rough=0.7))
    me.shade_smooth()
    me.set_sharp_from_angle(angle=math.radians(35))
    for c in obj.users_collection:
        c.objects.unlink(obj)
    bpy.context.scene.collection.objects.link(obj)
    obj.parent = parent
    return obj


def import_glb(stem, name, parent, xform=Matrix.Identity(4), mat=None):
    """Optional third-party model converted by prepare_meshes.py (glTF, metres).

    Returns an empty named `name` whose children are the imported objects, placed with
    `xform` (model millimetres -> parent), or None if the model is not available."""
    path = os.path.join(MESHES, stem + ".glb")
    if not os.path.exists(path):
        return None
    before = set(bpy.data.objects)
    bpy.ops.import_scene.gltf(filepath=path)
    new = [o for o in bpy.data.objects if o not in before]
    holder = empty(name, parent)
    holder.matrix_basis = xform @ Matrix.Diagonal((1000.0, 1000.0, 1000.0, 1.0))
    for obj in new:
        for c in list(obj.users_collection):
            c.objects.unlink(obj)
        bpy.context.scene.collection.objects.link(obj)
        if obj.parent is None:
            obj.parent = holder
            obj.matrix_parent_inverse = Matrix.Identity(4)
        obj.name = f"{name}_{obj.name}"
        if mat is not None and obj.type == "MESH":
            obj.data.materials.clear()
            obj.data.materials.append(mat)
            for poly in obj.data.polygons:
                poly.material_index = 0
        if obj.type == "MESH":
            obj.data.set_sharp_from_angle(angle=math.radians(35))
    return holder


def basis(x, y, z):
    """4x4 matrix whose columns are the images of the local X, Y, Z axes."""
    m = Matrix.Identity(4)
    for i, col in enumerate((x, y, z)):
        for r in range(3):
            m[r][i] = col[r]
    return m


def horn_mesh(name, mat, parent, length=30.0, thickness=4.5, hub_r=7.5, tip_r=4.4):
    """Single-arm aluminium servo horn, hub at the origin, arm along +X, thickness along +Y."""
    bm = bmesh.new()
    pts = []
    for i in range(48):
        a = 2 * math.pi * i / 48
        for cx, r in ((0.0, hub_r), (length, tip_r)):
            pts.append(Vector((cx + r * math.cos(a), r * math.sin(a))))
    # convex hull in 2D
    pts.sort(key=lambda p: (p.x, p.y))

    def cross(o, a, b):
        return (a.x - o.x) * (b.y - o.y) - (a.y - o.y) * (b.x - o.x)
    lower, upper = [], []
    for p in pts:
        while len(lower) >= 2 and cross(lower[-2], lower[-1], p) <= 0:
            lower.pop()
        lower.append(p)
    for p in reversed(pts):
        while len(upper) >= 2 and cross(upper[-2], upper[-1], p) <= 0:
            upper.pop()
        upper.append(p)
    hull = lower[:-1] + upper[:-1]
    verts = [bm.verts.new((p.x, 0.0, p.y)) for p in hull]
    face = bm.faces.new(verts)
    ext = bmesh.ops.extrude_face_region(bm, geom=[face])
    bmesh.ops.translate(bm, vec=(0, thickness, 0),
                        verts=[g for g in ext["geom"] if isinstance(g, bmesh.types.BMVert)])
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    obj = new_object(name, me, parent, mat)
    mod = obj.modifiers.new("bevel", "BEVEL")
    mod.width = 0.6
    mod.segments = 2
    return obj


# DS51150 model (DSSERVO/DSSERVO_150kg_80kg_60kg.STEP): output shaft along +Y at x = 19.5,
# z = 0, flange face (shaft side) at y = 34.7. Maps it onto the servo() frame below.
SERVO_MODEL_XF = basis((0, 0, -1), (0, -1, 0), (-1, 0, 0)) @ Matrix.Translation((-19.5, -34.7, 0))
SPLINE_BASE = 14.3           # servo() frame: horn seat 14.3 mm above the flange face (-Y)
# Handle servo: the rubber grommets that come with the servo sit between flange and case. The case
# to CoverSnap distance is 7.5 mm (measured), the flange 3 mm thick -> the flange is 2.25 mm up.
GROMMET_STACK = 7.5
FLANGE_LIFT = (GROMMET_STACK - 3.0) / 2
COVERSNAP_SHIFT = GROMMET_STACK - 5.0     # the STEP assembly has the CoverSnap 5 mm off the case


def servo(name, parent, xform):
    """DSSERVO DS51150 (150 kg·cm), ~61 x 30 x 48 mm, flange 34.7 mm above the bottom.

    Local frame: output shaft at the origin pointing -Y, body along +Z, width along X,
    flange face (shaft side) at Y = 0. Uses the third-party model if it was converted
    (see prepare_meshes.py), otherwise a simple box model.
    """
    g = empty(name, parent)
    g.matrix_parent_inverse = Matrix.Identity(4)
    g.matrix_basis = xform
    dark = material("servo", rough=0.35)
    model = import_glb("ext_servo", name + "_model", g, SERVO_MODEL_XF, dark)
    if model is not None:
        meshes = [o for o in model.children_recursive if o.type == "MESH"]
        meshes[0].name = name + "_body"
        for obj in meshes:
            remove_cable_stub(obj, model)
            color_servo_label(obj, model)
        return g
    box(name + "_body", -15, 15, -13.5, 34.7, -11, 50, dark, g, bevel=1.5)
    box(name + "_label", -15.1, 15.1, 5.0, 24.0, -11.1, 50.1, material("servo_label", rough=0.4), g, bevel=0.5)
    box(name + "_flange", -15, 15, 0, 3.0, -22, 61, dark, g, bevel=0.8)
    cylinder(name + "_boss", 4.0, 6.0, dark, g, depth_axis="Y", center=(0, -17.0, 0))
    return g


SERVO_WIRES = [(0.20, 0.08, 0.03), (0.65, 0.04, 0.03), (0.95, 0.22, 0.02)]   # brown, red, orange


# printed corner for the duct (print-files/Accessories/CableDuctCorner): in its STEP coordinates
# the legs run along -Z and +X from the corner point, the half-round bulges to +Y, base at y = -4.73
CORNER_POINT = Vector((0.06, -4.73, 20.84))
CORNER_LEG = 20.5            # the duct ends this far from the corner point (the spigots go inside)


def duct_corner(name, corner, d_a, d_b, mat, parent):
    """Place the printed corner at `corner` (on the sash face) with its legs along d_a and d_b."""
    out = Vector((0, -1, 0))
    if (-d_a).cross(d_b).dot(out) < 0:     # keep it a rotation: the two legs are interchangeable
        d_a, d_b = d_b, d_a
    rot = basis(d_b, out, -d_a)            # piece +X -> d_b, +Y (bulge) -> room, -Z -> d_a
    xf = Matrix.Translation(corner) @ rot @ Matrix.Translation(-CORNER_POINT)
    return import_stl("Accessories_CableDuctCorner", name, mat, parent, xf)


def duct(name, pts, parent, width=16.0, height=8.0, face_y=SASH_FACE_Y - 0.05, seg=16):
    """Half-round cable duct (like D-Line 16 x 8 mm) on the room side of the sash (y = face_y),
    along the polyline `pts` [(x, z), ...], with the printed corner piece at every bend."""
    mat = material("duct", (0.90, 0.90, 0.88), rough=0.35)
    out = Vector((0, -1, 0))
    for i in range(1, len(pts) - 1):
        c = Vector((pts[i][0], face_y, pts[i][1]))
        d_a = (Vector((pts[i - 1][0], face_y, pts[i - 1][1])) - c).normalized()
        d_b = (Vector((pts[i + 1][0], face_y, pts[i + 1][1])) - c).normalized()
        duct_corner(f"{name}_corner{i}", c, d_a, d_b, mat, parent)
    for i, ((x0, z0), (x1, z1)) in enumerate(zip(pts, pts[1:])):
        d = Vector((x1 - x0, 0, z1 - z0)).normalized()
        a = Vector((x0, face_y, z0)) + (d * CORNER_LEG if i > 0 else Vector())
        b = Vector((x1, face_y, z1)) - (d * CORNER_LEG if i < len(pts) - 2 else Vector())
        side = out.cross(d)
        bm = bmesh.new()
        ra, rb = [], []
        for k in range(seg + 1):
            t = math.pi * k / seg
            off = side * (math.cos(t) * width / 2) + out * (math.sin(t) * height)
            ra.append(bm.verts.new(a + off))
            rb.append(bm.verts.new(b + off))
        for k in range(seg):
            bm.faces.new((ra[k], rb[k], rb[k + 1], ra[k + 1]))
        bm.faces.new(ra)
        bm.faces.new(rb)
        bm.faces.new((ra[0], ra[seg], rb[seg], rb[0]))
        bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
        me = bpy.data.meshes.new(f"{name}{i}")
        bm.to_mesh(me)
        bm.free()
        obj = new_object(f"{name}{i}", me, parent, mat)
        obj.data.shade_smooth()
        obj.data.set_sharp_from_angle(angle=math.radians(40))


def wire(name, points, radius, mat, parent, straight=0):
    """Round cable along `points` (Bezier). The first `straight` points get vector handles, so
    that part runs in straight lines (inside a duct); the rest is smooth."""
    curve = bpy.data.curves.new(name, "CURVE")
    curve.dimensions = "3D"
    curve.bevel_depth = radius
    curve.bevel_resolution = 4
    spl = curve.splines.new("BEZIER")
    spl.bezier_points.add(len(points) - 1)
    for i, (bp, co) in enumerate(zip(spl.bezier_points, points)):
        bp.co = co
        bp.handle_left_type = bp.handle_right_type = "VECTOR" if i < straight else "AUTO"
    obj = bpy.data.objects.new(name, curve)
    bpy.context.scene.collection.objects.link(obj)
    obj.parent = parent
    obj.data.materials.append(mat)
    return obj


def servo_cable(points, parent, pitch=1.05):
    """Flat three-wire servo cable along `points` (the wires side by side along X)."""
    for i, col in enumerate(SERVO_WIRES):
        curve = bpy.data.curves.new(f"servo_cable{i}", "CURVE")
        curve.dimensions = "3D"
        curve.bevel_depth = 0.52
        curve.bevel_resolution = 3
        spl = curve.splines.new("BEZIER")
        spl.bezier_points.add(len(points) - 1)
        for bp, (x, y, z) in zip(spl.bezier_points, points):
            bp.co = (x + (1 - i) * pitch, y, z)     # brown (-) on the +X side, like pin 1 of JP1
            bp.handle_left_type = bp.handle_right_type = "AUTO"
        obj = bpy.data.objects.new(f"servo_cable{i}", curve)
        bpy.context.scene.collection.objects.link(obj)
        obj.parent = parent
        obj.data.materials.append(material(f"servo_wire{i}", col, rough=0.45))


def remove_cable_stub(obj, model):
    """The servo model has a short cable stub at the strain relief (x > 36.6, low y). The real
    cable is drawn as its own curve, so the stub goes."""
    to_model = Matrix.Diagonal((1000.0, 1000.0, 1000.0, 1.0)) @ model.matrix_world.inverted() @ obj.matrix_world
    bm = bmesh.new()
    bm.from_mesh(obj.data)
    stub = [f for f in bm.faces if (lambda c: c.x > 36.6 and c.y < 20.0)(to_model @ f.calc_center_median())]
    bmesh.ops.delete(bm, geom=stub, context="FACES")
    bm.to_mesh(obj.data)
    bm.free()


def color_servo_label(obj, model):
    """Magenta label band with light text and the white sticker on top, like the real DS51150.

    Works in the coordinates of the servo model (mm): band at 10.7 < y < 29.7 on the body,
    recessed 0.1 mm (text at |z| = 15), sticker recessed into the top at y = 48.1."""
    to_model = model.matrix_world.inverted() @ obj.matrix_world
    to_model = Matrix.Diagonal((1000.0, 1000.0, 1000.0, 1.0)) @ to_model
    me = obj.data
    me.materials.append(material("servo_label", rough=0.35, metal=0.5))    # anodised band, like the photo
    for m in ("servo_text", "sticker"):
        me.materials.append(material(m, rough=0.4))
    bm = bmesh.new()
    bm.from_mesh(me)
    for f in bm.faces:
        c = to_model @ f.calc_center_median()
        if 10.7 < c.y < 29.7 and (abs(c.z) > 14.85 or abs(c.x) > 30.4):
            f.material_index = 2 if abs(abs(c.z) - 15.0) < 0.03 and abs(c.x) < 30.4 else 1
        elif abs(c.y - 48.1) < 0.04:
            f.material_index = 3
    bm.to_mesh(me)
    bm.free()


def horn(name, parent, xform):
    """Servo horn that comes with the DS51150, placed with `xform` (horn model -> parent).

    Horn model frame (DS51_18T_horn.STEP): hub on the Y axis, servo side at y = 0, top at
    y = 8, arm along -Z with holes at 20, 24.5 and 30 mm."""
    alu = material("horn_magenta", rough=0.3, metal=0.6)
    holder = import_glb("ext_horn", name, parent, xform, alu)
    if holder is not None:
        [o for o in holder.children_recursive if o.type == "MESH"][0].name = name + "_body"
        return holder
    holder = empty(name, parent)
    holder.matrix_basis = xform
    body = horn_mesh(name + "_body", alu, holder, length=30.0, thickness=8.0, hub_r=6.9, tip_r=4.7)
    # horn_mesh: arm along +X, thickness 0..8 along +Y
    body.matrix_basis = basis((0, 0, -1), (0, 1, 0), (1, 0, 0))
    return holder


def revolve(name, profile, mat, parent, segments=48):
    """Closed (r, z) profile turned around the Z axis."""
    bm = bmesh.new()
    rings = [[bm.verts.new((r * math.cos(a), r * math.sin(a), z)) for r, z in profile]
             for a in (2 * math.pi * i / segments for i in range(segments))]
    n = len(profile)
    for i in range(segments):
        a, b = rings[i], rings[(i + 1) % segments]
        for j in range(n):
            bm.faces.new((a[j], b[j], b[(j + 1) % n], a[(j + 1) % n]))
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    obj = new_object(name, me, parent, mat)
    obj.data.shade_smooth()
    obj.data.set_sharp_from_angle(angle=math.radians(40))
    return obj


# M6 rod end, proportions like a GE6E spherical bearing: ball 10 mm, 6 mm wide, 6 mm bore,
# housing 4 mm wide. The bore stays clear of the housing up to about 17 degrees of tilt.
BALL_R, BALL_HALF_W, BORE_R, HOUSING_HALF_W, HEAD_R = 5.0, 3.0, 3.0, 2.0, 9.5


def rod_end(name, parent, mat, shank=22.0):
    """M6 rod end: eye at the origin (bore axis Z), shank along +X.

    The ball with its bore hangs below `<name>_ball_pivot`, so it can turn in the housing."""
    g = empty(name, parent)
    n = 12
    seat = [(math.sqrt(BALL_R ** 2 - z ** 2), z)
            for z in (-HOUSING_HALF_W + 2 * HOUSING_HALF_W * k / n for k in range(n + 1))]
    revolve(name + "_eye", seat + [(HEAD_R, HOUSING_HALF_W), (HEAD_R, -HOUSING_HALF_W)], mat, g)
    pivot = empty(name + "_ball_pivot", g)
    sphere = [(math.sqrt(BALL_R ** 2 - z ** 2), z)
              for z in (-BALL_HALF_W + 2 * BALL_HALF_W * k / n for k in range(n + 1))]
    revolve(name + "_ball", [(BORE_R, -BALL_HALF_W)] + sphere + [(BORE_R, BALL_HALF_W)],
            material("alu", rough=0.15, metal=1.0), pivot)
    cylinder(name + "_neck", 5.0, 8.0, mat, g, depth_axis="X", center=(12, 0, 0))
    cylinder(name + "_shank", 3.0, shank, mat, g, depth_axis="X", center=(16 + shank / 2, 0, 0))
    return g


# Bayonet coupler (print-files/Movement/BayonetSocket + BayonetPlug), in the STEP
# coordinates of both parts: common axis Z, socket at z -10..20, plug at z 22..51.3.
# The plug's two lugs (z = 23.9) slide down the entry slots of the socket (at 0° and
# 180°), turn by about 48° along the groove, and the O-ring on the plug stem
# pushes them up into the end pocket.
BAYONET_PUSH = -9.6      # plug shift when pushed in (lugs at the bottom of the groove)
BAYONET_LOCK = -9.2      # plug shift when locked (O-ring pushes the lugs into the pocket)
BAYONET_TURN = 48.0      # degrees
BAYONET_CENTER = 15.85   # middle of the locked assembly along Z


def torus(name, major, minor, mat, parent, z=0.0, segments=48, ring=16):
    bm = bmesh.new()
    rings = []
    for i in range(segments):
        a = 2 * math.pi * i / segments
        loop = []
        for j in range(ring):
            b = 2 * math.pi * j / ring
            r = major + minor * math.cos(b)
            loop.append(bm.verts.new((r * math.cos(a), r * math.sin(a), z + minor * math.sin(b))))
        rings.append(loop)
    for i in range(segments):
        for j in range(ring):
            a, b = rings[i], rings[(i + 1) % segments]
            bm.faces.new((a[j], b[j], b[(j + 1) % ring], a[(j + 1) % ring]))
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    obj = new_object(name, me, parent, mat)
    obj.data.shade_smooth()
    return obj


def bayonet(name, parent, mat, push=BAYONET_LOCK, turn=BAYONET_TURN):
    """Locked bayonet coupler; local Z = STEP Z. Returns the root empty.

    Children: <name>_socket, <name>_plug (an empty, so it can be animated) and
    <name>_oring, which sits on the plug stem under the plug shoulder."""
    g = empty(name, parent)
    import_stl("Movement_BayonetSocket", name + "_socket", mat, g)
    plug = empty(name + "_plug", g)
    plug.location = (0, 0, push)
    plug.rotation_euler = (0, 0, math.radians(turn))
    import_stl("Movement_BayonetPlug", name + "_plug_body", mat, plug)
    torus(name + "_oring", 6.0, 0.8, material("gasket", rough=0.6), plug, z=31.0 - 0.8)
    return g


def smoothstep(t):
    t = max(0.0, min(1.0, t))
    return t * t * (3 - 2 * t)


# --------------------------------------------------------------------------
# Scene
# --------------------------------------------------------------------------
def build():
    for obj in list(bpy.data.objects):
        bpy.data.objects.remove(obj, do_unlink=True)
    scene = bpy.context.scene
    scene.render.fps = FPS
    scene.frame_start, scene.frame_end = 1, FRAME_END

    root = empty("mm_root")
    root.scale = (0.001, 0.001, 0.001)

    upvc = material("upvc", rough=0.35)
    wall = material("wall", rough=0.9)
    printed = material("print", rough=0.55)
    moving = material("print_moving", rough=0.5)
    steel = material("steel", rough=0.3, metal=1.0)
    glass = material("glass", color=(0.70, 0.82, 0.86), rough=0.05, alpha=0.07)
    glass.use_transparent_shadow = True

    # ---- room: wall with reveal, lintel, window sill ----------------------
    box("wall_left", -3000, -930, -250, 400, -1200, 2900, wall, root, bevel=0)
    box("wall_right", 930, 3000, -250, 400, -1200, 2900, wall, root, bevel=0)
    box("wall_top", -930, 930, -250, 400, STURZ_Z, 2900, wall, root, bevel=0)
    box("wall_bottom", -930, 930, -250, 400, -1200, -25, wall, root, bevel=0)
    box("sill", -960, 960, -290, 0, -25, 0, material("sill", rough=0.25), root, bevel=2)
    box("floor_out", -6000, 6000, 400, 6000, -1500, -1400, wall, root, bevel=0)
    box("floor_room", -4000, 4000, -4000, -250, -1000, -950, material("floor", color=(0.55, 0.42, 0.30), rough=0.6), root, bevel=0)
    box("ceiling_room", -4000, 4000, -4000, -250, 2550, 2600, wall, root, bevel=0)

    sky = material("sky", color=(0.0, 0.0, 0.0), rough=1.0)
    nt = sky.node_tree
    bsdf = nt.nodes["Principled BSDF"]
    coord = nt.nodes.new("ShaderNodeTexCoord")
    sep = nt.nodes.new("ShaderNodeSeparateXYZ")
    ramp = nt.nodes.new("ShaderNodeValToRGB")
    ramp.color_ramp.elements[0].color = (0.62, 0.72, 0.82, 1)
    ramp.color_ramp.elements[1].color = (0.22, 0.42, 0.72, 1)
    nt.links.new(coord.outputs["Generated"], sep.inputs[0])
    nt.links.new(sep.outputs["Z"], ramp.inputs[0])
    nt.links.new(ramp.outputs["Color"], bsdf.inputs["Emission Color"])
    bsdf.inputs["Emission Strength"].default_value = 0.9
    box("sky", -9000, 9000, 3000, 3100, -3000, 7000, sky, root, bevel=0)

    # ---- fixed window frame and left sash ---------------------------------
    frame = empty("frame", root)
    for name, x0, x1, z0, z1 in (("frame_l", -930, -870, 0, 1500), ("frame_r", 870, 930, 0, 1500),
                                 ("frame_t", -930, 930, 1440, 1500), ("frame_b", -930, 930, 0, 60),
                                 ("mullion", -40, 40, 0, 1500)):
        box(name, x0, x1, 0, 70, z0, z1, upvc, frame, bevel=1.5)

    def sash_geometry(prefix, parent, x0, x1, cut=None):
        z0, z1, w = SASH["z0"], SASH["z1"], SASH["face"]
        y0, y1 = SASH_FACE_Y, SASH["y1"]
        box(prefix + "_top", x0, x1, y0, y1, z1 - w, z1, upvc, parent, bevel=2)
        box(prefix + "_bottom", x0, x1, y0, y1, z0, z0 + w, upvc, parent, bevel=2)
        box(prefix + "_right", x1 - w, x1, y0, y1, z0 + w, z1 - w, upvc, parent, bevel=2)
        if cut is None:
            box(prefix + "_left", x0, x0 + w, y0, y1, z0 + w, z1 - w, upvc, parent, bevel=2)
        else:
            # left stile with a cutaway window around the handle gear
            cz0, cz1, cx = cut
            box(prefix + "_left_lo", x0, x0 + w, y0, y1, z0 + w, cz0, upvc, parent, bevel=2)
            box(prefix + "_left_hi", x0, x0 + w, y0, y1, cz1, z1 - w, upvc, parent, bevel=2)
            box(prefix + "_left_gone", x0, cx, y0, y1, cz0, cz1, fade_material("upvc"), parent, bevel=0)
            sec = material("section", rough=0.7)
            box(prefix + "_left_front", cx, x0 + w, y0, y0 + 3, cz0, cz1, upvc, parent, bevel=0)
            box(prefix + "_left_back", cx, x0 + w, y1 - 3, y1, cz0, cz1, upvc, parent, bevel=0)
            box(prefix + "_left_side", x0 + w - 3, x0 + w, y0, y1, cz0, cz1, upvc, parent, bevel=0)
            box(prefix + "_left_cutf", cx - 0.05, cx, y0, y0 + 3, cz0, cz1, sec, parent, bevel=0)
            box(prefix + "_left_cutb", cx - 0.05, cx, y1 - 3, y1, cz0, cz1, sec, parent, bevel=0)
            # the same stile in one piece, used by the views without cutaway (no seams)
            box(prefix + "_left_full", x0, x0 + w, y0, y1, z0 + w, z1 - w, upvc, parent, bevel=2).hide_render = True
        gx0, gx1, gz0, gz1 = x0 + w, x1 - w, z0 + w, z1 - w
        for i, (gy0, gy1) in enumerate(((14, 18), (36, 40))):
            box(f"{prefix}_glass{i}", gx0 - 6, gx1 + 6, gy0, gy1, gz0 - 6, gz1 + 6, glass, parent, bevel=0)
        gasket = material("gasket", rough=0.6)
        box(prefix + "_gasket_t", gx0, gx1, y0 + 4, y0 + 6, gz1 - 1, gz1 + 1, gasket, parent, bevel=0)
        box(prefix + "_gasket_b", gx0, gx1, y0 + 4, y0 + 6, gz0 - 1, gz0 + 1, gasket, parent, bevel=0)
        box(prefix + "_gasket_l", gx0 - 1, gx0 + 1, y0 + 4, y0 + 6, gz0, gz1, gasket, parent, bevel=0)
        box(prefix + "_gasket_r", gx1 - 1, gx1 + 1, y0 + 4, y0 + 6, gz0, gz1, gasket, parent, bevel=0)

    left = empty("left_sash", frame)
    sash_geometry("lsash", left, -SASH["x1"], -SASH["x0"])
    # ordinary handle on the left sash
    metal = material("handle_metal", color=(0.62, 0.60, 0.56), rough=0.35, metal=1.0)
    box("lhandle_rosette", -84, -56, SASH_FACE_Y - 11, SASH_FACE_Y, 560, 640, metal, left, bevel=4)
    box("lhandle_neck", -79, -61, SASH_FACE_Y - 40, SASH_FACE_Y - 11, 591, 609, metal, left, bevel=3)
    box("lhandle_lever", -79, -61, SASH_FACE_Y - 52, SASH_FACE_Y - 34, 470, 609, metal, left, bevel=4)

    # ---- right sash on its tilt hinge -------------------------------------
    hinge = empty("sash_hinge", root, loc=HINGE)
    sash = empty("sash", hinge, loc=-HINGE)
    sash_geometry("rsash", sash, SASH["x0"], SASH["x1"], cut=(520, 690, SPINDLE.x))
    box("gear", 58, 82, -6, 48, 548, 652, material("gear", rough=0.45, metal=0.6), sash, bevel=1)

    # ---- handle unit -------------------------------------------------------
    hu = empty("handle_unit", sash)
    hu.matrix_basis = Matrix.Translation(HANDLE_OFFSET) @ Matrix.Rotation(math.pi, 4, "X")
    for part in ("Base", "Case", "ServoCover", "PCBHolder"):
        import_stl(f"Handle_{part}_cut_keep", part + "_keep", printed, hu, section=True)
        import_stl(f"Handle_{part}_cut_gone", part + "_gone", fade_material("print"), hu)
    # second CoverSnap on the other flange: mirrored along the servo (z), so that the cut-open
    # half stays on the far side and the snap ridge points away from the servo again
    snap1 = Matrix.Translation((0, COVERSNAP_SHIFT, 0))
    snap2 = Matrix.Translation((0, COVERSNAP_SHIFT, 35.6)) @ Matrix.Diagonal((1.0, 1.0, -1.0, 1.0))
    for i, xf in enumerate((snap1, snap2)):
        import_stl("Handle_CoverSnap_cut_keep", f"CoverSnap{i}_keep", printed, hu, xf, section=True)
        import_stl("Handle_CoverSnap_cut_gone", f"CoverSnap{i}_gone", fade_material("print"), hu, xf)
    servo("handle_servo", hu, Matrix.Translation((0, FLANGE_LIFT, 0)))
    # rubber grommets on the four servo screws, between case (y = 0) and CoverSnap
    rubber = material("grommet", rough=0.8)
    for i, (x, z) in enumerate(((8.5, -19.7), (-8.5, -19.7), (8.5, 55.3), (-8.5, 55.3))):
        cylinder(f"grommet{i}_lo", 4.3, FLANGE_LIFT, rubber, hu, depth_axis="Y", center=(x, FLANGE_LIFT / 2, z))
        cylinder(f"grommet{i}_mid", 2.9, 3.0, rubber, hu, depth_axis="Y", center=(x, FLANGE_LIFT + 1.5, z))
        cylinder(f"grommet{i}_hi", 4.3, FLANGE_LIFT, rubber, hu, depth_axis="Y",
                 center=(x, GROMMET_STACK - FLANGE_LIFT / 2, z))
    # M4 countersunk screws that hold the case on the base (two left, one right)
    for i, (x, z, sign) in enumerate(((-24.0, 21.5, -1), (-24.0, -21.5, -1), (46.0, 0.0, 1))):
        mat = fade_material("steel") if x < 0 else steel
        cylinder(f"case_screw{i}", 3.9, 1.2, mat, hu, depth_axis="X", center=(x - sign * 0.4, -37.05, z))
    # the PCB on the PCB holder (layout from pcb/window-opener.brd, see pcb.py):
    # board x -> -X, board y -> +Z, component side -> +Y; board top at Y = -31.6
    import pcb as pcb_module
    board = empty("pcb", hu)
    board.matrix_basis = Matrix(((-1, 0, 0, 15.0), (0, 0, 1, -31.6), (0, 1, 0, 57.0), (0, 0, 0, 1)))
    pcb_module.build_board(board, prefix="pcb_", wires=False)

    spin = empty("handle_spindle", hu)
    # horn on the servo spline, adapter pocket floor on the horn top (8 mm horn)
    horn_top = -SPLINE_BASE + FLANGE_LIFT - 8.0
    adapter_xf = (Matrix.Translation((0, horn_top, 0)) @ Matrix.Rotation(-math.pi / 2, 4, "Y")
                  @ Matrix.Translation((87.17, 0, -7.8)))
    import_stl("Handle_ServoHornAdapter", "ServoHornAdapter", moving, spin, adapter_xf)
    horn("handle_horn", spin, Matrix.Translation((0, -SPLINE_BASE + FLANGE_LIFT, 0))
         @ basis((1, 0, 0), (0, -1, 0), (0, 0, -1)))
    # 50 mm spindle, ending 1 mm short of the bottom of the square hole
    box("spindle", -3.5, 3.5, horn_top - 1.2 - 50.0, horn_top - 1.2, -3.5, 3.5, steel, spin, bevel=0.4)

    # original handle screws: Base -> window gear, M5 countersunk, flush with the countersinks
    # of the base (5.5 -> 11.2 mm, top at Y = -31.75)
    for i, z in enumerate((-21.5, 21.5)):
        cylinder(f"base_screw{i}_head", 2.5, 2.1, steel, hu, depth_axis="Y", center=(0, -32.8, z), r2=5.4)
        cylinder(f"base_screw{i}", 2.5, 45.0, steel, hu, depth_axis="Y", center=(0, -33.85 - 22.5, z))

    # servo cable: leaves the servo at the shaft end, runs over the servo (under the ServoCover)
    # and through the slot in the front of the case to header D3 on the PCB
    path = [(0, 28.25, -17.0), (0, 29.75, -21.2), (0, 35.2, -21.7), (0, 37.45, -15.0), (0, 37.45, 20.0),
            (0, 37.45, 48.0), (0, 32.5, 57.5), (0, 11.0, 62.6), (0, 1.0, 64.3), (0, -7.0, 64.3),
            (3.0, -8.5, 80.0), (8.0, -8.5, 104.0), (8.52, -11.0, 112.4), (8.52, -14.8, 113.4)]
    servo_cable(path, hu)
    for obj in [o for o in bpy.data.objects if o.name.startswith("pcb_wire_handle")]:
        bpy.data.objects.remove(obj)     # the board's own stubs; the real cable ends in the plug

    # ---- movement unit -----------------------------------------------------
    mu = empty("move_unit", sash)
    mu.matrix_basis = Matrix.Translation(MOVE_OFFSET) @ basis((0, 1, 0), (0, 0, 1), (1, 0, 0))
    import_stl("Movement_ServoCoverMount", "ServoCoverMount", printed, mu)
    # under the plate (Y = -4): rubber grommets, servo flange, grommets, then the NutHolders
    plate = -4.0
    for i, dz in enumerate((0.0, 75.0)):
        import_stl("Movement_NutHolder", f"NutHolder{i}", printed, mu,
                   Matrix.Translation((0, plate - GROMMET_STACK - 4.4, dz)))
    rubber = material("grommet", rough=0.8)
    for i, (x, z) in enumerate(((72.84, 48.34), (89.84, 48.34), (72.84, 123.34), (89.84, 123.34))):
        cylinder(f"top_grommet{i}_hi", 4.3, FLANGE_LIFT, rubber, mu, depth_axis="Y",
                 center=(x, plate - FLANGE_LIFT / 2, z))
        cylinder(f"top_grommet{i}_mid", 2.9, 3.0, rubber, mu, depth_axis="Y", center=(x, plate - FLANGE_LIFT - 1.5, z))
        cylinder(f"top_grommet{i}_lo", 4.3, FLANGE_LIFT, rubber, mu, depth_axis="Y",
                 center=(x, plate - GROMMET_STACK + FLANGE_LIFT / 2, z))
    # servo: shaft at SHAFT_LOCAL pointing +Y (up), body along -Z, flange under the plate
    servo_xf = (Matrix.Translation((SHAFT_LOCAL.x, plate - FLANGE_LIFT, SHAFT_LOCAL.z))
                @ basis((1, 0, 0), (0, -1, 0), (0, 0, -1)))
    servo("move_servo", mu, servo_xf)
    arm_pivot = empty("arm_pivot", mu, loc=(SHAFT_LOCAL.x, HORN_TOP, SHAFT_LOCAL.z))
    horn("move_horn", arm_pivot, Matrix.Translation((0, -8.0, 0)) @ basis((-1, 0, 0), (0, 1, 0), (0, 0, -1)))
    arm_xf = basis((0, 0, 1), (0, -1, 0), (1, 0, 0)) @ Matrix.Translation((86.24, -0.0, 25.44))
    import_stl("Movement_ServoArm", "ServoArm", moving, arm_pivot, arm_xf)
    bolt = cylinder("arm_bolt_head", 5.6, 4.0, steel, arm_pivot, segments=6,
                    depth_axis="Y", center=(0, BALL_A_UP + 7.0, ARM))
    bolt.name = "arm_bolt_head"
    cylinder("arm_bolt", 3.0, 30, steel, arm_pivot, depth_axis="Y", center=(0, BALL_A_UP - 6, ARM))

    # cable ducts on the sash (half-round, white): up to the top unit, and down and along the
    # bottom rail to the hinge side for the power cable (the window still opens)
    duct("duct_top", [(50, 652), (50, 1408), (474, 1408)], sash)
    duct("duct_power", [(74, 428), (74, 92), (840, 92)], sash)

    # servo extension cable to the top unit: leaves the handle unit at the top, on the window side,
    # runs inside the duct (hidden) and into the ServoCoverMount
    cable_pts = [(52, -21, 632), (50, -19.5, 660), (50, -19.5, 1000), (50, -19.5, 1402),
                 (50, -19.5, 1408), (56, -19.5, 1408), (300, -19.5, 1408), (470, -19.5, 1408), (488, -26, 1400)]
    curve = bpy.data.curves.new("cable", "CURVE")
    curve.dimensions = "3D"
    curve.bevel_depth = 1.8
    curve.bevel_resolution = 3
    spl = curve.splines.new("NURBS")
    spl.points.add(len(cable_pts) - 1)
    for p, co in zip(spl.points, cable_pts):
        p.co = (*co, 1)
    spl.use_endpoint_u = True
    spl.order_u = 3
    cable = bpy.data.objects.new("cable", curve)
    scene.collection.objects.link(cable)
    cable.parent = sash
    cable.data.materials.append(material("cable", rough=0.5))

    # power: angled 5.5 x 2.1 mm plug in the jack at the bottom of the case, loop with a ferrite,
    # then in the duct down and along the bottom rail; out at the hinge side to the power supply
    black = material("cable_black", (0.02, 0.02, 0.022), rough=0.4)
    jack = Vector((54.74, -35.75, 480.7))        # jack opening, world coordinates (sash closed)
    cylinder("power_plug_tip", 4.6, 11.0, black, sash, center=jack - Vector((0, 0, 5.5)))
    cylinder("power_plug_body", 5.6, 17.0, black, sash, depth_axis="X", center=jack + Vector((5.0, 0, -15.0)))
    cylinder("power_plug_relief", 3.4, 7.0, black, sash, depth_axis="X", center=jack + Vector((16.5, 0, -15.0)))
    ferrite = Matrix.Translation((78.0, -26.0, 438.0)) @ Matrix.Rotation(math.radians(12), 4, "Y")
    fer = cylinder("power_ferrite", 6.5, 28.0, black, sash)
    fer.matrix_basis = ferrite
    wire("power_cable", [jack + Vector((20.0, 0, -15.0)), (85.0, -33.0, 463.0), (90.0, -29.0, 455.0),
                         (81.0, -26.0, 452.0)], 1.9, black, sash)
    wire("power_cable_duct", [(76.0, -24.0, 426.0), (74.0, -19.0, 414.0), (74.0, -19.0, 98.0), (80.0, -19.0, 92.0),
                              (836.0, -19.0, 92.0), (850.0, -22.0, 90.0), (864.0, -30.0, 70.0),
                              (868.0, -48.0, 12.0), (872.0, -80.0, 2.0), (900.0, -140.0, 2.0),
                              (927.0, -190.0, 2.0)], 1.9, black, sash, straight=5)

    # ---- fixed pivot in the corner between frame and lintel ---------------
    pm = empty("pivot_mount", root)
    pm.matrix_basis = Matrix.Translation(PIVOT_OFFSET) @ basis((-1, 0, 0), (0, 0, 1), (0, 1, 0))
    import_stl("Movement_TopPivotMount", "TopPivotMount", printed, pm)
    cylinder("pivot_screw_head", 3.6, 3.0, steel, pm, depth_axis="Y",
             center=(PIN_LOCAL.x, -13.5, PIN_LOCAL.z))

    # ---- coupler: rod end + bayonet (socket, O-ring, plug) + rod end -------
    coupler = empty("coupler", root)
    rod_a = rod_end("rod_a", coupler, steel)
    rod_b = rod_end("rod_b", coupler, steel)
    body = bayonet("bayonet", coupler, moving)

    return dict(scene=scene, hinge=hinge, sash=sash, spin=spin, arm_pivot=arm_pivot, coupler=coupler,
                rod_a=rod_a, rod_b=rod_b, body=body, mu=mu, pm=pm)


# --------------------------------------------------------------------------
# Kinematics
# --------------------------------------------------------------------------
def ball_a_world(theta, phi):
    """Centre of the arm-side ball for sash tilt theta and arm angle phi (mm, world)."""
    local = Vector((SHAFT_LOCAL.x + ARM * math.sin(phi), HORN_TOP + BALL_A_UP, SHAFT_LOCAL.z + ARM * math.cos(phi)))
    rest = Vector((local.z + MOVE_OFFSET.x, local.x + MOVE_OFFSET.y, local.y + MOVE_OFFSET.z))
    rel = rest - HINGE
    rot = Matrix.Rotation(theta, 3, "X")
    return HINGE + rot @ rel


BALL_B = Vector((-PIN_LOCAL.x + PIVOT_OFFSET.x, PIN_LOCAL.z + PIVOT_OFFSET.y, PIN_LOCAL.y + PIVOT_OFFSET.z))
LINK = (ball_a_world(0.0, PHI_CLOSED) - BALL_B).length


def solve_theta(phi, prev):
    def f(t):
        return (ball_a_world(t, phi) - BALL_B).length - LINK
    grid = [i * 0.0005 for i in range(0, 241)]
    roots = []
    for a, b in zip(grid, grid[1:]):
        fa, fb = f(a), f(b)
        if fa == 0:
            roots.append(a)
        elif fa * fb < 0:
            for _ in range(40):
                m = (a + b) / 2
                if f(a) * f(m) <= 0:
                    b = m
                else:
                    a = m
            roots.append((a + b) / 2)
    if not roots:
        return prev
    return min(roots, key=lambda r: abs(r - prev))


def animate(objs):
    theta = 0.0
    for frame in range(1, FRAME_END + 1):
        # handle: 0 = closed (down), pi = tilt (up)
        if frame <= T_HANDLE_CLOSE[0]:
            h = smoothstep((frame - T_HANDLE_OPEN[0]) / (T_HANDLE_OPEN[1] - T_HANDLE_OPEN[0]))
        else:
            h = 1 - smoothstep((frame - T_HANDLE_CLOSE[0]) / (T_HANDLE_CLOSE[1] - T_HANDLE_CLOSE[0]))
        if frame <= T_ARM_CLOSE[0]:
            a = smoothstep((frame - T_ARM_OPEN[0]) / (T_ARM_OPEN[1] - T_ARM_OPEN[0]))
        else:
            a = 1 - smoothstep((frame - T_ARM_CLOSE[0]) / (T_ARM_CLOSE[1] - T_ARM_CLOSE[0]))
        phi = PHI_CLOSED + a * (PHI_OPEN - PHI_CLOSED)
        theta = solve_theta(phi, theta) if a > 0 else 0.0

        objs["spin"].rotation_euler = (0, h * math.pi, 0)
        objs["spin"].keyframe_insert("rotation_euler", frame=frame)
        objs["arm_pivot"].rotation_euler = (0, phi, 0)
        objs["arm_pivot"].keyframe_insert("rotation_euler", frame=frame)
        objs["hinge"].rotation_euler = (theta, 0, 0)
        objs["hinge"].keyframe_insert("rotation_euler", frame=frame)

        pa = ball_a_world(theta, phi)
        x = (BALL_B - pa).normalized()
        y = Vector((0, 0, 1)).cross(x).normalized()
        z = x.cross(y)
        m = basis(x, y, z)
        m.translation = pa
        objs["coupler"].matrix_basis = m
        objs["coupler"].keyframe_insert("location", frame=frame)
        objs["coupler"].keyframe_insert("rotation_quaternion" if objs["coupler"].rotation_mode == "QUATERNION"
                                        else "rotation_euler", frame=frame)
    # static coupler children
    length = LINK
    objs["rod_a"].location = (0, 0, 0)
    objs["rod_b"].matrix_basis = Matrix.Translation((length, 0, 0)) @ Matrix.Rotation(math.pi, 4, "Z")
    # bayonet axis (STEP Z) along the link, socket on the arm side
    objs["body"].matrix_basis = Matrix.Translation((length / 2 - BAYONET_CENTER, 0, 0)) @ \
        basis((0, 1, 0), (0, 0, 1), (1, 0, 0))
    for fc in _all_fcurves():
        for kp in fc.keyframe_points:
            kp.interpolation = "LINEAR"


def _all_fcurves():
    for obj in bpy.data.objects:
        ad = obj.animation_data
        if ad and ad.action:
            yield from _action_fcurves(ad.action)


def _action_fcurves(action):
    if hasattr(action, "fcurves") and len(action.fcurves):
        return list(action.fcurves)
    curves = []
    for layer in getattr(action, "layers", []):
        for strip in layer.strips:
            for bag in strip.channelbags:
                curves.extend(bag.fcurves)
    return curves


# --------------------------------------------------------------------------
# Cameras, lights, render settings
# --------------------------------------------------------------------------
CAMERAS = {
    # name: (location m, target m, lens mm, default resolution, hidden object name prefixes)
    "main": ((-0.02, -1.02, 0.70), (0.50, 0.0, 0.79), 17.0, (1080, 1350), ()),
    "handle": ((-0.125, -0.175, 0.655), (0.070, -0.050, 0.592), 40.0, (720, 720),
               ("lhandle", "cable")),
    # lintel hidden so the linkage can be seen from above
    "top": ((0.415, -0.36, 1.75), (0.538, -0.085, 1.458), 34.0, (720, 720),
            ("wall_top", "ceiling_room")),
}
# Only the handle close-up shows the handle unit and the sash cut open; in the other
# views the fading halves stay solid.
CUTAWAY_CAMS = {"handle"}


def disable_cutaway():
    for obj in bpy.data.objects:
        if obj.name.startswith("rsash_left_"):
            obj.hide_render = obj.name != "rsash_left_full"
    for m in bpy.data.materials:
        if m.name.endswith("_fade"):
            if m.node_tree.animation_data:
                m.node_tree.animation_data_clear()
            m.node_tree.nodes["Principled BSDF"].inputs["Alpha"].default_value = 1.0
            m.surface_render_method = "DITHERED"


def setup_render(cam_name):
    scene = bpy.context.scene
    loc, target, lens, res, hidden = CAMERAS[cam_name]
    for obj in bpy.data.objects:
        if any(obj.name.startswith(h) for h in hidden):
            obj.hide_render = True
    cam_data = bpy.data.cameras.new(cam_name)
    cam_data.lens = lens
    cam_data.clip_start = 0.01
    cam_data.clip_end = 50
    cam = bpy.data.objects.new("cam_" + cam_name, cam_data)
    scene.collection.objects.link(cam)
    cam.location = loc
    direction = Vector(target) - Vector(loc)
    cam.rotation_euler = direction.to_track_quat("-Z", "Y").to_euler()
    scene.camera = cam

    world = bpy.data.worlds.new("world")
    world.use_nodes = True
    bg = world.node_tree.nodes["Background"]
    bg.inputs["Color"].default_value = (0.82, 0.85, 0.90, 1)
    bg.inputs["Strength"].default_value = 0.35
    scene.world = world

    key = bpy.data.lights.new("key", "AREA")
    key.size = 2.5
    key.energy = 350
    key_obj = bpy.data.objects.new("key", key)
    scene.collection.objects.link(key_obj)
    key_obj.location = (-0.6, -2.6, 2.3)
    key_obj.rotation_euler = (Vector((0.3, 0, 0.9)) - key_obj.location).to_track_quat("-Z", "Y").to_euler()

    fill = bpy.data.lights.new("fill", "AREA")
    fill.size = 3.0
    fill.energy = 90
    fill_obj = bpy.data.objects.new("fill", fill)
    scene.collection.objects.link(fill_obj)
    fill_obj.location = (1.4, -2.2, 0.6)
    fill_obj.rotation_euler = (Vector((0.4, 0, 0.8)) - fill_obj.location).to_track_quat("-Z", "Y").to_euler()

    sun = bpy.data.lights.new("sun", "SUN")
    sun.energy = 1.6
    sun.angle = math.radians(3)
    sun_obj = bpy.data.objects.new("sun", sun)
    scene.collection.objects.link(sun_obj)
    sun_obj.rotation_euler = (math.radians(-55), 0, math.radians(200))

    scene.render.engine = "BLENDER_EEVEE"
    scene.eevee.taa_render_samples = int(ARGS["--samples"])
    try:
        scene.eevee.use_raytracing = True
        scene.eevee.use_shadows = True
    except AttributeError:
        pass
    scene.view_settings.view_transform = "AgX"
    scene.view_settings.exposure = -0.9
    try:
        scene.view_settings.look = "AgX - Medium High Contrast"
    except TypeError:
        pass
    w, h = res
    if ARGS["--res"]:
        w, h = (int(v) for v in ARGS["--res"].split("x"))
    scene.render.resolution_x, scene.render.resolution_y = w, h
    scene.render.resolution_percentage = 100
    scene.render.image_settings.file_format = "PNG"
    scene.render.film_transparent = False


def main():
    objs = build()
    animate(objs)
    if ARGS["--cam"] not in CUTAWAY_CAMS:
        disable_cutaway()
    setup_render(ARGS["--cam"])
    scene = bpy.context.scene
    if ARGS["--save"]:
        bpy.ops.wm.save_as_mainfile(filepath=os.path.abspath(ARGS["--save"]))
    frames = ARGS["--frames"]
    out = os.path.abspath(ARGS["--out"])
    os.makedirs(os.path.dirname(out), exist_ok=True)
    if "-" in frames:
        a, b = (int(v) for v in frames.split("-"))
        scene.frame_start, scene.frame_end = a, b
        scene.render.filepath = out
        # skip frames that already exist, so several processes can share the work
        scene.render.use_overwrite = False
        scene.render.use_placeholder = True
        bpy.ops.render.render(animation=True)
    else:
        scene.frame_set(int(frames))
        scene.render.filepath = out
        bpy.ops.render.render(write_still=True)
    print("LINK length (mm):", round(LINK, 1))


if __name__ == "__main__":
    main()
