#!/usr/bin/env python3
"""export_vanilla_parts.py - exports chosen vanilla renderers (mesh + its placement in its prefab + its materials and their
textures) offline from the 1.0.21 client bundle, for kitbashing previews in Blender. GAME DATA, a reference only: nothing
here ships; at runtime the mod clones the vanilla meshes/materials from the game itself.

  heavy.sh 4G sb-parts ~/upy/bin/python -I export_vanilla_parts.py OUTDIR 'TheHive|/TheHive/Visual/low' 'GuckSack|/GuckSack/sack' ...

Each argument is prefab|renderer path (as in vanilla_parts.tsv). Writes OUTDIR/<key>.json (verts, normals, uv0, tris per
submesh, materials, renderer world matrix in the prefab, mesh name, prefab) and OUTDIR/tex/<texture>.png (once per texture),
OUTDIR/parts.json (index). Coordinates are Unity mesh space (raw vertex data, nothing negated).
"""
import os, sys, json, re
import numpy as np
sys.path.insert(0, os.path.expanduser("~/WubarrkCODING/libs-Tools/UNITY-ASSET-TOOLS"))
import UnityPy
from UnityPy.helpers.MeshHelper import MeshHandler
from valheim_paths import BUNDLE

OUT = sys.argv[1]
WANT = [a.split("|", 1) for a in sys.argv[2:]]
os.makedirs(os.path.join(OUT, "tex"), exist_ok=True)
env = UnityPy.load(BUNDLE)
names = {p for p, _ in WANT}
roots = {}
for obj in env.objects:
    if obj.type.name != "GameObject":
        continue
    try:
        d = obj.read()
    except Exception:
        continue
    if d.m_Name in names:
        roots.setdefault(d.m_Name, []).append(d)


def comps(go):
    r = []
    for c in go.m_Component:
        try:
            r.append(c.component.read() if hasattr(c, "component") else c.read())
        except Exception:
            r.append(None)
    return r


def trs(t):
    p, q, s = t.m_LocalPosition, t.m_LocalRotation, t.m_LocalScale
    x, y, z, w = q.x, q.y, q.z, q.w
    R = np.array([[1 - 2 * (y * y + z * z), 2 * (x * y - z * w), 2 * (x * z + y * w)],
                  [2 * (x * y + z * w), 1 - 2 * (x * x + z * z), 2 * (y * z - x * w)],
                  [2 * (x * z - y * w), 2 * (y * z + x * w), 1 - 2 * (x * x + y * y)]])
    M = np.eye(4); M[:3, :3] = R @ np.diag([s.x, s.y, s.z]); M[:3, 3] = [p.x, p.y, p.z]
    return M


items = lambda x: x.items() if isinstance(x, dict) else x
saved = set()


def material(mp):
    if getattr(mp, "path_id", 1) == 0:          # a renderer slot with no material (e.g. swamptree2_log)
        return {"name": "none", "path_id": 0, "textures": {}, "colors": {}, "floats": {}}
    md = mp.read()
    sp = md.m_SavedProperties
    e = {"name": md.m_Name, "path_id": mp.path_id, "textures": {}, "colors": {}, "floats": {}}
    for k, v in items(sp.m_TexEnvs):
        if not v.m_Texture or v.m_Texture.path_id == 0:
            continue
        try:
            td = v.m_Texture.read()
        except Exception:
            continue
        fn = re.sub(r"[^A-Za-z0-9_.()-]", "_", td.m_Name) + ".png"
        if fn not in saved:
            try:
                td.image.save(os.path.join(OUT, "tex", fn)); saved.add(fn)
            except Exception as ex:
                fn = "ERR:" + str(ex)[:40]
        e["textures"][k] = {"png": fn, "scale": [v.m_Scale.x, v.m_Scale.y], "offset": [v.m_Offset.x, v.m_Offset.y]}
    e["colors"] = {k: [round(c.r, 4), round(c.g, 4), round(c.b, 4), round(c.a, 4)] for k, c in items(sp.m_Colors)}
    e["floats"] = {k: round(f, 4) for k, f in items(sp.m_Floats)}
    try:
        e["shader"] = md.m_Shader.read().m_Name
    except Exception:
        e["shader"] = "?"
    return e


index = {}


def find(go, M, path, want_path, prefab):
    cs = comps(go)
    t = next((c for c in cs if type(c).__name__ == "Transform"), None)
    Mw = M @ trs(t) if path else np.eye(4)          # the prefab root's own TRS is dropped (roots are parked at y=50 etc.)
    here = path + "/" + go.m_Name
    if here == want_path:
        mf = next((c for c in cs if type(c).__name__ == "MeshFilter"), None)
        for c in cs:
            n = type(c).__name__
            if n not in ("MeshRenderer", "SkinnedMeshRenderer"):
                continue
            mp = c.m_Mesh if n == "SkinnedMeshRenderer" else mf.m_Mesh
            m = mp.read()
            mh = MeshHandler(m); mh.process()
            V = np.array(mh.m_Vertices, dtype=float)[:, :3]
            Nn = np.array(mh.m_Normals, dtype=float)[:, :3] if mh.m_Normals else None
            subs = mh.get_triangles()
            key = re.sub(r"[^A-Za-z0-9_]", "_", prefab + "__" + want_path.strip("/").replace("/", "_"))[:80]
            rec = {"prefab": prefab, "renderer_path": want_path, "renderer": n, "mesh": m.m_Name, "mesh_path_id": mp.path_id,
                   "verts": np.round(V, 6).tolist(), "normals": np.round(Nn, 5).tolist() if Nn is not None else None,
                   "uv0": [list(u) for u in mh.m_UV0] if mh.m_UV0 else None,
                   "submeshes": [[list(tr) for tr in sm] for sm in subs],
                   "materials": [material(x) for x in c.m_Materials],
                   "world_matrix_in_prefab": Mw.tolist(), "tris": sum(len(s) for s in subs)}
            json.dump(rec, open(os.path.join(OUT, key + ".json"), "w"))
            index[key] = {k: rec[k] for k in ("prefab", "renderer_path", "renderer", "mesh", "tris")} | {
                "materials": [x["name"] for x in rec["materials"]],
                "textures": [{k: v["png"] for k, v in x["textures"].items()} for x in rec["materials"]]}
            print("ok", key, rec["tris"], index[key]["materials"])
            return True
    for ch in t.m_Children:
        if find(ch.read().m_GameObject.read(), Mw, here, want_path, prefab):
            return True
    return False


for prefab, rpath in WANT:
    ok = False
    for r in roots.get(prefab, []):
        t = next((c for c in comps(r) if type(c).__name__ == "Transform"), None)
        if t is None or t.m_Father.path_id != 0:
            continue
        if find(r, np.eye(4), "", rpath, prefab):
            ok = True
            break
    if not ok:
        print("MISSING", prefab, rpath)
json.dump(index, open(os.path.join(OUT, "parts.json"), "w"), indent=1)
