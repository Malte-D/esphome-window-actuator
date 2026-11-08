"""Close-up animation of the bayonet coupler (connect and release).

    blender -b --factory-startup -P tools/render/bayonet.py -- \
        --meshes build/meshes --out build/frames/bayonet/f_ --frames 1-270
    tools/render/compose_bayonet.sh build/frames/bayonet docs/media

The socket is drawn translucent so that the two lugs of the plug can be seen in
the L-shaped slots. Geometry comes from BayonetSocket/BayonetPlug in print-files.
"""

import math
import os
import sys

import bmesh
import bpy
from mathutils import Matrix, Vector

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import scene  # noqa: E402
from scene import (BAYONET_CENTER, BAYONET_LOCK, BAYONET_PUSH, BAYONET_TURN, basis, bayonet, empty,  # noqa: E402
                   material, rod_end, smoothstep)

FRAME_END = 270
OUT_SHIFT = 10.0   # plug position (along the axis) when the coupler is open

# (frame, plug shift, plug turn in degrees); linear segments, eased with smoothstep
KEYS = [
    (1, OUT_SHIFT, 0.0),
    (24, OUT_SHIFT, 0.0),
    (60, BAYONET_PUSH, 0.0),            # push in
    (96, BAYONET_PUSH, BAYONET_TURN),   # turn
    (106, BAYONET_LOCK, BAYONET_TURN),  # let go: O-ring pushes the lugs into the notch
    (150, BAYONET_LOCK, BAYONET_TURN),
    (162, BAYONET_PUSH, BAYONET_TURN),  # push
    (198, BAYONET_PUSH, 0.0),           # turn back
    (234, OUT_SHIFT, 0.0),              # pull apart
    (FRAME_END, OUT_SHIFT, 0.0),
]


def pose(frame):
    for (f0, s0, t0), (f1, s1, t1) in zip(KEYS, KEYS[1:]):
        if f0 <= frame <= f1:
            k = smoothstep((frame - f0) / max(1, f1 - f0))
            return s0 + k * (s1 - s0), t0 + k * (t1 - t0)
    return KEYS[-1][1], KEYS[-1][2]


def build():
    for obj in list(bpy.data.objects):
        bpy.data.objects.remove(obj)
    root = empty("mm_root")
    root.scale = (0.001, 0.001, 0.001)
    steel = material("steel", rough=0.3, metal=1.0)
    plug_mat = material("print_moving", rough=0.5)
    socket_mat = material("socket_glass", (0.80, 0.80, 0.78), rough=0.35, alpha=0.38)
    socket_mat.use_backface_culling = False

    # Turning the bayonet does not turn the threads: each half turns together with the housing of
    # its rod end, while the balls stay on their bolts. Socket and plug each turn half of the 48
    # degrees, so each ball swings +-12 degrees in its housing, from one stop to the other, and
    # its bore stays clear of the housing (the bolt goes through it).
    twist = empty("twist", root)

    # STEP Z of the bayonet -> world X; turned so that the entry slots point up
    axis = empty("axis", twist)
    axis.matrix_basis = Matrix.Translation((-BAYONET_CENTER, 0, 0)) @ basis((0, 1, 0), (0, 0, 1), (1, 0, 0))
    g = bayonet("bayonet", axis, plug_mat, push=OUT_SHIFT, turn=0.0)
    g.matrix_basis = Matrix.Rotation(math.radians(90), 4, "Z")
    bpy.data.objects["bayonet_socket"].data.materials[0] = socket_mat
    # colour the two lugs of the plug so they can be followed through the socket
    me = bpy.data.objects["bayonet_plug_body"].data
    me.materials.append(material("lug", (0.95, 0.22, 0.05), rough=0.45, emission=(0.6, 0.1, 0.0)))
    bm = bmesh.new()
    bm.from_mesh(me)
    for f in bm.faces:
        c = f.calc_center_median()
        if c.z < 26.0 and math.hypot(c.x, c.y) > 5.25:
            f.material_index = 1
    bm.to_mesh(me)
    bm.free()

    # rod ends: shank 9 mm deep in the printed threads
    rod_a = rod_end("rod_a", twist, steel)
    rod_a.location = (-10 - BAYONET_CENTER + 9 - 38, 0, 0)
    rod_b_carrier = empty("rod_b_carrier", root)
    rod_b = rod_end("rod_b", rod_b_carrier, steel)
    rod_b.matrix_basis = Matrix.Translation((51.3 + BAYONET_LOCK - BAYONET_CENTER - 9 + 38, 0, 0)) @ Matrix.Rotation(math.pi, 4, "Z")
    return bpy.data.objects["bayonet_plug"], rod_b_carrier


BALL_SWING = BAYONET_TURN / 4     # each ball: +-12 degrees relative to its housing


def animate(plug, carrier):
    twist = bpy.data.objects["twist"]
    balls = [bpy.data.objects["rod_a_ball_pivot"], bpy.data.objects["rod_b_ball_pivot"]]
    for frame in range(1, FRAME_END + 1):
        shift, turn = pose(frame)
        plug.location = (0, 0, shift)
        plug.rotation_euler = (0, 0, math.radians(turn))          # relative to the socket
        plug.keyframe_insert("location", frame=frame)
        plug.keyframe_insert("rotation_euler", frame=frame)
        twist.rotation_euler = (math.radians(-turn / 2), 0, 0)    # socket + rod end A housing
        twist.keyframe_insert("rotation_euler", frame=frame)
        carrier.location = (shift - BAYONET_LOCK, 0, 0)
        carrier.rotation_euler = (math.radians(turn / 2), 0, 0)   # plug + rod end B housing
        carrier.keyframe_insert("location", frame=frame)
        carrier.keyframe_insert("rotation_euler", frame=frame)
        for ball in balls:                                        # balls keep their place in the world
            ball.rotation_euler = (math.radians(turn / 2 - BALL_SWING), 0, 0)
            ball.keyframe_insert("rotation_euler", frame=frame)


def setup():
    sc = bpy.context.scene
    cam_data = bpy.data.cameras.new("cam")
    cam_data.lens = 58      # both rod ends in the picture
    cam_data.clip_start = 0.01
    cam = bpy.data.objects.new("cam", cam_data)
    sc.collection.objects.link(cam)
    target = Vector((0.010, 0, 0.0))
    cam.location = target + Vector((-0.05, -0.24, 0.13))
    cam.rotation_euler = (target - cam.location).to_track_quat("-Z", "Y").to_euler()
    sc.camera = cam

    world = bpy.data.worlds.new("world")
    world.use_nodes = True
    world.node_tree.nodes["Background"].inputs["Color"].default_value = (0.93, 0.94, 0.95, 1)
    world.node_tree.nodes["Background"].inputs["Strength"].default_value = 0.6
    sc.world = world
    for name, loc, energy, size in (("key", (-0.15, -0.25, 0.30), 9, 0.25), ("fill", (0.25, -0.1, 0.1), 3, 0.4),
                                    ("rim", (0.05, 0.25, 0.2), 5, 0.3)):
        light = bpy.data.lights.new(name, "AREA")
        light.energy = energy
        light.size = size
        obj = bpy.data.objects.new(name, light)
        sc.collection.objects.link(obj)
        obj.location = loc
        obj.rotation_euler = (Vector((0, 0, 0)) - Vector(loc)).to_track_quat("-Z", "Y").to_euler()

    sc.render.engine = "BLENDER_EEVEE"
    sc.eevee.taa_render_samples = int(scene.ARGS["--samples"])
    try:
        sc.eevee.use_raytracing = True
    except AttributeError:
        pass
    sc.view_settings.view_transform = "AgX"
    sc.view_settings.exposure = -0.6
    try:
        sc.view_settings.look = "AgX - Medium High Contrast"
    except TypeError:
        pass
    w, h = (1280, 720)
    if scene.ARGS["--res"]:
        w, h = (int(v) for v in scene.ARGS["--res"].split("x"))
    sc.render.resolution_x, sc.render.resolution_y = w, h
    sc.render.image_settings.file_format = "PNG"
    sc.render.film_transparent = True      # composited onto white in compose_bayonet.sh
    sc.frame_start, sc.frame_end = 1, FRAME_END


def main():
    plug, carrier = build()
    animate(plug, carrier)
    setup()
    sc = bpy.context.scene
    spec = scene.ARGS["--frames"]
    out = os.path.abspath(scene.ARGS["--out"])
    os.makedirs(os.path.dirname(out), exist_ok=True)
    if "-" in spec:
        a, b = (int(v) for v in spec.split("-"))
        sc.frame_start, sc.frame_end = a, b
        sc.render.filepath = out
        sc.render.use_overwrite = False
        sc.render.use_placeholder = True
        bpy.ops.render.render(animation=True)
    else:
        sc.frame_set(int(spec))
        sc.render.filepath = out
        bpy.ops.render.render(write_still=True)


main()
