"""render_eye_options.py - the eye candidates side by side, each set into the crease between two Hive lumps (the socket it will
have on the Brute), same size, same light, real materials.
  heavy.sh 4G sb-eyes blender -b --factory-startup -P render_eye_options.py -- <ASSET-001 dir>
Writes kit/previews/_eyecells/*.png + cells.json; compose with compose_parts_sheet-style PIL (done at the end of this run's caller)."""
import bpy, sys, os, json, math
from mathutils import Vector, Matrix
import numpy as np

ASSET = sys.argv[sys.argv.index("--") + 1].rstrip("/")
SUB = os.path.dirname(ASSET)
sys.path.insert(0, os.path.join(SUB, "kit_tools"))
import donor_base as DB, vanilla_kit as VK

REF = os.path.join(ASSET, "kit", "vanilla_ref")
OUT = os.path.join(ASSET, "kit", "previews", "_eyecells")
os.makedirs(OUT, exist_ok=True)
CANDS = [("A eye_globe dome + TheHive_Eye (50 tris)", "eye_globe__eye_globe_default", "hive", "z", 1.0),
         ("B Morkhalla eye (low) own material (46 tris)", "Morkhalla_Eye2__Morkhalla_Eye2_GameObject__1__low", None, "-y", 1.0),
         ("C Morkhalla eye (low) + TheHive_Eye (46 tris)", "Morkhalla_Eye2__Morkhalla_Eye2_GameObject__1__low", "hive", "-y", 1.0),
         ("D Eye1 (Morkhalla) own material (102 tris)", "Eye1__Eye1_default", None, "-y", 1.0),
         ("E Hatchling eyes, own glow (80 tris, the pair)", "TheHive__TheHive_Visual_Hatchling_mountain_eyes", None, "z", 1.0),
         ("F built-in Sphere stand-in (768 tris) + TheHive_Eye", "__sphere__", "hive", "z", 1.0),
         ("G GreydwarfEye model (120 tris) own material", "GreydwarfEye__GreydwarfEye_model__1_", None, "-y", 1.0)]
cells, labels = [], []
for label, key, mat, face, _ in CANDS:
    bpy.ops.wm.read_factory_settings(use_empty=True)
    P = VK.Parts(REF, os.path.join(SUB, "reference"))
    lump = P.mesh("TheHive__TheHive_Visual_low", prefab_space=False, name="lump")
    lump.materials[0].node_tree.nodes["Principled BSDF"].inputs["Emission Strength"].default_value = 0.0
    for i, (x, rz) in enumerate(((-0.33, 0.4), (0.33, 2.1))):
        ob = bpy.data.objects.new(f"l{i}", lump); bpy.context.scene.collection.objects.link(ob)
        ob.matrix_world = Matrix.Translation((x, 0, 0)) @ Matrix.Rotation(rz, 4, 'Z') @ Matrix.Diagonal((0.17, 0.17, 0.12, 1))
    if key == "__sphere__":
        bpy.ops.mesh.primitive_uv_sphere_add(segments=24, ring_count=17, radius=0.5)
        e = bpy.context.active_object; me = e.data; bpy.data.objects.remove(e)
        me.materials.append(P.hive_material("TheHive_Eye"))
        for p in me.polygons: p.use_smooth = True
    else:
        me = P.mesh(key, prefab_space=(key.startswith("TheHive__")), name="eye")
        if mat == "hive":
            me.materials.clear(); me.materials.append(P.hive_material("TheHive_Eye"))
    co = np.array([v.co[:] for v in me.vertices]); lo, hi = co.min(0), co.max(0); c = (lo + hi) / 2
    size = max(hi - lo)
    s = 0.34 / size
    R = Matrix.Identity(4)
    if face == "-y":
        R = Matrix.Rotation(math.pi / 2, 4, 'X')       # local -y -> +z (towards the camera above)
    eob = bpy.data.objects.new("eye", me); bpy.context.scene.collection.objects.link(eob)
    eob.matrix_world = Matrix.Translation((0, 0, 0.2)) @ R @ Matrix.Diagonal((s, s, s, 1)) @ Matrix.Translation(Vector(-c))
    DB.lights_and_world(scale=0.6, aim=(0, 0, 0))
    DB.setup_render(520, 440)
    DB.camera((0, 0, 0.12), 3.2, 0, 62, lens=85)
    pth = os.path.join(OUT, f"eye_{len(cells)}.png"); DB.render(pth); cells.append(pth); labels.append(f"{label} | {len(me.polygons)} faces")
    print("EYE", label)
json.dump({"cells": cells, "labels": labels}, open(os.path.join(OUT, "cells.json"), "w"), indent=1)
