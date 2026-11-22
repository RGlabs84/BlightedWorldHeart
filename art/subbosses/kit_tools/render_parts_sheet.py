"""render_parts_sheet.py - (then compose_parts_sheet.py with PIL) contact sheet of the exported vanilla kitbash candidates in their REAL game textures.
  heavy.sh 4G sb-sheet blender -b --factory-startup -P render_parts_sheet.py -- <ASSET-001 dir>
Writes art/subbosses/kit_tools/vanilla_parts_sheet.png (+ _cells/). Each cell: the part in its prefab scale, normalised to
the cell, three-quarter view, label = source prefab / renderer, tris and real size (m)."""
import bpy, sys, os, json, math
from mathutils import Vector
import numpy as np

ASSET = sys.argv[sys.argv.index("--") + 1].rstrip("/")
SUB = os.path.dirname(ASSET)
sys.path.insert(0, os.path.join(SUB, "kit_tools")); sys.path.insert(0, os.path.join(SUB, "tools_001-003"))
import donor_base as DB, vanilla_kit as VK, hive_kit as hk

REF = os.path.join(ASSET, "kit", "vanilla_ref")
OUTD = os.path.join(SUB, "kit_tools", "_cells")
os.makedirs(OUTD, exist_ok=True)
idx = json.load(open(os.path.join(REF, "parts.json")))
cells = []
LABELS = []
items = list(idx.keys()) + ["__hive_eye__", "__hive_leg__"]
for key in items:
    bpy.ops.wm.read_factory_settings(use_empty=True)
    P = VK.Parts(REF, os.path.join(SUB, "reference"))
    if key == "__hive_eye__":
        me = P.mesh("eye_globe__eye_globe_default", name="eye"); me.materials.clear(); me.materials.append(P.hive_material("TheHive_Eye"))
        label, tris = "eye_globe mesh + TheHive_Eye (Hive eyes are the built-in Sphere, 768 tris)", 50
    elif key == "__hive_leg__":
        me = VK.builtin_cube("leg", P.hive_material("TheHive_Mat_legs"))
        label, tris = "built-in Cube + TheHive_Mat_legs (the Hive's timber legs)", 12
    else:
        me = P.mesh(key)
        d = idx[key]; label, tris = f"{d['prefab']} {d['renderer_path'].split('/')[-1]} ({d['mesh']})", d["tris"]
    ob = bpy.data.objects.new("p", me); bpy.context.scene.collection.objects.link(ob)
    co = np.array([v.co[:] for v in me.vertices]); lo, hi = co.min(0), co.max(0); size = hi - lo
    s = 3.6 / max(size.max(), 1e-6)
    ob.scale = (s, s, s); ob.location = Vector((-(lo + hi) / 2 * s).tolist())
    DB.lights_and_world(scale=1.0, aim=(0, 0, 0))
    DB.setup_render(500, 560)
    cu = bpy.data.curves.new("t", "FONT"); cu.body = f"{label[:44]}\n{label[44:88]}\n{tris} tris, {size[0]:.2f} x {size[2]:.2f} x {size[1]:.2f} m"
    cu.size = 0.14; cu.align_x = 'CENTER'
    tm = bpy.data.materials.new("lbl"); tm.use_nodes = True
    tm.node_tree.nodes["Principled BSDF"].inputs["Emission Color"].default_value = (0.9, 0.9, 0.9, 1)
    tm.node_tree.nodes["Principled BSDF"].inputs["Emission Strength"].default_value = 1.0
    cu.materials.append(tm)
    t = bpy.data.objects.new("lbl", cu); bpy.context.scene.collection.objects.link(t)
    cam = DB.camera((0, 0, -0.15), 9, 35, 18, lens=50)
    t.location = (0, 0, 0); t.rotation_euler = cam.rotation_euler
    t.location = cam.matrix_world @ Vector((0, -1.05, -5.0)) if False else Vector((0, 0, 0))
    # place the label below the part in camera space
    t.matrix_world = cam.matrix_world @ __import__("mathutils").Matrix.Translation((0, -1.38, -6.0))
    t.hide_render = True                 # labels are drawn by compose (PIL); Blender text did not show in the cells
    p = os.path.join(OUTD, f"cell_{len(cells):02d}.png"); DB.render(p); cells.append(p)
    LABELS.append(f"{label} | {tris} tris | {size[0]:.2f} x {size[2]:.2f} x {size[1]:.2f} m in its prefab")
    print("CELL", len(cells), label, tris)
json.dump({"cells": cells, "labels": LABELS}, open(os.path.join(OUTD, "cells.json"), "w"), indent=1)
print("DONE", len(cells))
