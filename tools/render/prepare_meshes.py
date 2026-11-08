"""Convert the STEP print files to STL meshes for the Blender scene.

Also produces the two halves of every handle-unit housing part, cut along the
spindle axis, which the animation uses for its cutaway view.

Needs the OpenCascade bindings from CadQuery:
    python3 -m venv .venv && .venv/bin/pip install cadquery-ocp
    .venv/bin/python tools/render/prepare_meshes.py print-files build/meshes [local]

Optional third argument: a folder with third-party models of the bought parts
(servo, servo horn, D1 mini; see EXTERNAL_MODELS). They are not part of the
repository because of their licences. When they are found, they are converted
to glTF (with their colours) and the renders use them instead of the simple
built-in shapes.
"""

import glob
import os
import sys

from OCP.BRepAlgoAPI import BRepAlgoAPI_Common, BRepAlgoAPI_Cut
from OCP.BRepMesh import BRepMesh_IncrementalMesh
from OCP.BRepPrimAPI import BRepPrimAPI_MakeBox
from OCP.gp import gp_Pnt
from OCP.STEPControl import STEPControl_Reader
from OCP.StlAPI import StlAPI_Writer

# Housing parts of the handle unit that get cut open in the animation.
# All of them share one coordinate system in the STEP export: the spindle axis
# is the Y axis, the window is on the -Y side.
CUT_PARTS = ["Base", "Case", "ServoCover", "CoverSnap", "PCBHolder"]

# Third-party models (GrabCAD), relative to the optional models folder.
EXTERNAL_MODELS = {
    # https://grabcad.com/library/servo-motor-ds51-150kg-80kg-60-kg-servomotor-ds51150-ds5180-ds5160-1
    "ext_servo": "DSSERVO/DSSERVO_150kg_80kg_60kg.STEP",
    # https://grabcad.com/library/ds51-servo-motor-horn-gear-servomotor-1
    "ext_horn": "DS51_18T_horn/DS51_18T_horn.STEP",
    # https://grabcad.com/library/wemos-d1-mini-6
    "ext_d1mini": "wemos-d1-mini-6.snapshot.1/wemos-mini-d1.stp",
}


def load(path):
    reader = STEPControl_Reader()
    reader.ReadFile(path)
    reader.TransferRoots()
    return reader.OneShape()


def write_stl(shape, path):
    BRepMesh_IncrementalMesh(shape, 0.03, False, 0.15, True)
    writer = StlAPI_Writer()
    writer.ASCIIMode = False
    writer.Write(shape, path)


def write_glb(step_path, glb_path, deflection=0.05):
    """STEP with colours -> binary glTF. Blender imports it Z-up, in metres."""
    from OCP.RWGltf import RWGltf_CafWriter
    from OCP.RWMesh import RWMesh_CoordinateSystem
    from OCP.STEPCAFControl import STEPCAFControl_Reader
    from OCP.TCollection import TCollection_AsciiString, TCollection_ExtendedString
    from OCP.TDocStd import TDocStd_Document
    from OCP.XCAFDoc import XCAFDoc_DocumentTool
    from OCP.Message import Message_ProgressRange
    try:
        from OCP.collections import IndexedDataMap_TCollection_AsciiString_TCollection_AsciiString as InfoMap
    except ImportError:  # older OCP builds
        from OCP.TColStd import TColStd_IndexedDataMapOfStringString as InfoMap
    doc = TDocStd_Document(TCollection_ExtendedString("XmlOcaf"))
    reader = STEPCAFControl_Reader()
    reader.SetColorMode(True)
    reader.SetNameMode(True)
    reader.ReadFile(step_path)
    reader.Transfer(doc)
    shape = XCAFDoc_DocumentTool.ShapeTool_s(doc.Main()).GetOneShape()
    BRepMesh_IncrementalMesh(shape, deflection, False, 0.3, True)
    writer = RWGltf_CafWriter(TCollection_AsciiString(glb_path), True)
    conv = writer.ChangeCoordinateSystemConverter()
    conv.SetInputCoordinateSystem(RWMesh_CoordinateSystem.RWMesh_CoordinateSystem_Zup)
    conv.SetOutputCoordinateSystem(RWMesh_CoordinateSystem.RWMesh_CoordinateSystem_glTF)
    writer.Perform(doc, InfoMap(), Message_ProgressRange())


def main(src, out, ext=None):
    os.makedirs(out, exist_ok=True)
    # Half space x < 0, i.e. the half that faces the camera.
    near_half = BRepPrimAPI_MakeBox(gp_Pnt(-1000, -1000, -1000), gp_Pnt(0, 1000, 1000)).Shape()
    for path in sorted(glob.glob(os.path.join(src, "*", "*.step"))):
        group = os.path.basename(os.path.dirname(path))
        name = os.path.splitext(os.path.basename(path))[0]
        shape = load(path)
        write_stl(shape, os.path.join(out, f"{group}_{name}.stl"))
        if group == "Handle" and name in CUT_PARTS:
            keep = BRepAlgoAPI_Cut(shape, near_half).Shape()
            gone = BRepAlgoAPI_Common(shape, near_half).Shape()
            write_stl(keep, os.path.join(out, f"{group}_{name}_cut_keep.stl"))
            write_stl(gone, os.path.join(out, f"{group}_{name}_cut_gone.stl"))
        print("meshed", group, name)
    for stem, rel in EXTERNAL_MODELS.items():
        path = os.path.join(ext, rel) if ext else ""
        if path and os.path.exists(path):
            write_glb(path, os.path.join(out, stem + ".glb"))
            print("converted", rel)
        else:
            print("not found, using the built-in shape:", rel)


if __name__ == "__main__":
    main(*sys.argv[1:4])
