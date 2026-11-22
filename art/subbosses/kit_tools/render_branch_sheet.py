"""render_branch_sheet.py - (then compose_parts_sheet.py) the BRANCH candidates for the Hive sub-bosses (owner, 2026-11-21: "yes,
with branches" - bare gnarled woody branches, no leaves/needles, never a tree silhouette), in their real game textures.
  heavy.sh 4G sb-branches blender -b --factory-startup -P render_branch_sheet.py -- <ASSET-001 dir>
  ~/upy/bin/python -I compose_parts_sheet.py kit_tools/_branch_cells/cells.json kit_tools/branch_parts_sheet.png
Cells: the Elder's (gd_king) loose branch islands, the branch / log / stub props, the Yggdrasil shoot's trunk (leaf submesh dropped).
"""
import bpy, sys, os, json
from mathutils import Vector
import numpy as np

ASSET = sys.argv[sys.argv.index("--") + 1].rstrip("/")
SUB = os.path.dirname(ASSET)
sys.path.insert(0, os.path.join(SUB, "kit_tools")); sys.path.insert(0, os.path.join(SUB, "tools_001-003"))
import donor_base as DB, vanilla_kit as VK, island_parts as IP

REF = os.path.join(ASSET, "kit", "vanilla_ref")
OUTD = os.path.join(SUB, "kit_tools", "_branch_cells")
os.makedirs(OUTD, exist_ok=True)


def island_mesh(P, key, tris, name, drop_submeshes=()):
    d = P.data(key)
    Mw = np.array(d["world_matrix_in_prefab"])
    T = [(t, si) for si, sm in enumerate(d["submeshes"]) for t in sm]
    sel = [T[i] for i in tris] if tris is not None else [x for x in T if x[1] not in drop_submeshes]
    vi = sorted({i for t, _ in sel for i in t}); remap = {o: n for n, o in enumerate(vi)}
    Vw = np.c_[np.array(d["verts"])[vi], np.ones(len(vi))] @ Mw.T
    me = bpy.data.meshes.new(name)
    me.from_pydata([(v[0], v[2], v[1]) for v in Vw[:, :3]], [], [(remap[t[0]], remap[t[2]], remap[t[1]]) for t, _ in sel])
    me.update()
    if d["uv0"]:
        uvl = me.uv_layers.new(name="UV0")
        for loop in me.loops:
            uvl.data[loop.index].uv = tuple(d["uv0"][vi[loop.vertex_index]])
    sis = sorted({si for _, si in sel}); smap = {si: n for n, si in enumerate(sis)}
    for pg, (_, si) in zip(me.polygons, sel):
        pg.material_index = smap[si]; pg.use_smooth = True
    for si in sis:
        me.materials.append(P.material(d["materials"][si]))
    return me


ITEMS = []
P0 = VK.Parts(REF, os.path.join(SUB, "reference"))
EK = "gd_king__gd_king_Visual_gd_king"
d = P0.data(EK); TT = [t for sm in d["submeshes"] for t in sm]
comp = IP.islands(d["verts"], TT)
eld = []
for tris in comp.values():
    st = IP.island_stats(d["verts"], TT, tris)
    if 120 <= st["tris"] <= 500 and max(st["size"]) >= 0.012:
        eld.append((st, tris))
eld.sort(key=lambda x: -max(x[0]["size"]))
for n, (st, tris) in enumerate(eld[:8]):
    ITEMS.append(("island", EK, tris, f"gd_king (Elder) island {n}: {st['tris']} tris"))
for key in ("BarkaBranch__BarkaBranch_default", "AshlandsBranch1__AshlandsBranch1_default", "AshlandsBranch2__AshlandsBranch2_stub",
            "AshlandsBranch3__AshlandsBranch3_default", "BigBranch__BigBranch_default", "Pickable_Branch__Pickable_Branch_model",
            "swamptree1_stub__swamptree1_stub", "swamptree2_log__swamptree2_log", "troll_log_swing_h__troll_log_swing_h_attach_log",
            "AshlandsBush1__AshlandsBush1_stub", "Greydwarf_Elite__Greydwarf_Elite_Visual_Cube", "YggdrasilRoot__YggdrasilRoot_root1_low",
            "GreyDwarfExtraRoots__GreyDwarfExtraRoots_default"):
    ITEMS.append(("whole", key, None, None))
ITEMS.append(("trunk", "YggaShoot1__YggaShoot1_Lod0", None, "YggaShoot1 Lod0, trunk submesh only (leaves dropped)"))

cells, labels, index = [], [], []
for kind, key, tris, label in ITEMS:
    bpy.ops.wm.read_factory_settings(use_empty=True)
    P = VK.Parts(REF, os.path.join(SUB, "reference"))
    dd = P.data(key)
    if kind == "island":
        me = island_mesh(P, key, tris, "isl")
    elif kind == "trunk":
        me = island_mesh(P, key, None, "trunk", drop_submeshes=(1,))
    else:
        me = P.mesh(key)
        label = f"{dd['prefab']} {dd['renderer_path'].split('/')[-1]} ({dd['mesh']})"
    ntris = len(me.polygons)
    ob = bpy.data.objects.new("p", me); bpy.context.scene.collection.objects.link(ob)
    co = np.array([v.co[:] for v in me.vertices]); lo, hi = co.min(0), co.max(0); size = hi - lo
    s = 3.6 / max(size.max(), 1e-6)
    ob.scale = (s, s, s); ob.location = Vector((-(lo + hi) / 2 * s).tolist())
    DB.lights_and_world(scale=1.0, aim=(0, 0, 0))
    DB.setup_render(500, 560)
    DB.camera((0, 0, -0.15), 9, 35, 18, lens=50)
    p = os.path.join(OUTD, f"cell_{len(cells):02d}.png"); DB.render(p); cells.append(p)
    labels.append(f"{label} | {ntris} tris | {size[0]:.2f} x {size[2]:.2f} x {size[1]:.2f} m")
    index.append({"cell": len(cells), "kind": kind, "key": key, "tris": tris, "label": label, "ntris": ntris,
                  "size_m": [round(float(x), 3) for x in size]})
    print("CELL", len(cells), label, ntris)
json.dump({"cells": cells, "labels": labels}, open(os.path.join(OUTD, "cells.json"), "w"), indent=1)
json.dump(index, open(os.path.join(SUB, "kit_tools", "branch_parts_index.json"), "w"), indent=1)
print("DONE", len(cells))
