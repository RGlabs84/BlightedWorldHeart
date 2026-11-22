#!/usr/bin/env python3
"""Export vanilla renderers as kitbash parts (mesh + UV0 + normals + material textures; skinned: weights, bone names and
per-bone bind world matrices in the prefab frame). GAME DATA, a dev reference only: never shipped.

    export_part.py OUT SPEC [SPEC ...]       SPEC = Prefab:renderer/path/suffix[:key]
e.g. ArmorRootChest:attach_skin/RootArmorSkirt  TheHive:Visual/low  Pinetree_01:trunk/Pinetree_01_lod_02  TheHive:Visual/EYE
Writes OUT/<key>.json and OUT/<material>__<slot>__<tex>.png. Static meshes are exported in the renderer's LOCAL space plus
its prefab-frame matrix; skinned meshes in the prefab frame (root TRS ignored), like export_base.py.
"""
import os, sys, json
sys.path.insert(0, os.path.expanduser("~/WubarrkCODING/libs-Tools/UNITY-ASSET-TOOLS"))
import numpy as np
import UnityPy
from UnityPy.helpers.MeshHelper import MeshHandler
from valheim_paths import BUNDLE

OUT = sys.argv[1]; SPECS = [s.split(":") for s in sys.argv[2:]]
os.makedirs(OUT, exist_ok=True)
env = UnityPy.load(BUNDLE)
items = lambda x: x.items() if isinstance(x, dict) else x


def comps(go):
    r = []
    for c in go.m_Component:
        try: r.append(c.component.read() if hasattr(c, "component") else c.read())
        except Exception: r.append(None)
    return r


def trs(t):
    p = t.m_LocalPosition; q = t.m_LocalRotation; s = t.m_LocalScale
    x, y, z, w = q.x, q.y, q.z, q.w
    R = np.array([[1 - 2 * (y * y + z * z), 2 * (x * y - z * w), 2 * (x * z + y * w)],
                  [2 * (x * y + z * w), 1 - 2 * (x * x + z * z), 2 * (y * z - x * w)],
                  [2 * (x * z - y * w), 2 * (y * z + x * w), 1 - 2 * (x * x + y * y)]])
    M = np.eye(4); M[:3, :3] = R @ np.diag([s.x, s.y, s.z]); M[:3, 3] = [p.x, p.y, p.z]
    return M


roots = {}
want = {s[0] for s in SPECS}
for obj in env.objects:
    if obj.type.name != "GameObject": continue
    try: d = obj.read()
    except Exception: continue
    if d.m_Name not in want: continue
    cs = comps(d)
    t = next((c for c in cs if type(c).__name__ == "Transform"), None)
    if t is None or t.m_Father.path_id != 0: continue
    if d.m_Name not in roots or len(cs) > len(roots[d.m_Name][1]): roots[d.m_Name] = (d, cs)


def material(c):
    mats = []
    for mp in c.m_Materials:
        md = mp.read(); sp = md.m_SavedProperties
        mi = {"name": md.m_Name, "path_id": mp.path_id, "textures": {}, "colors": {}, "floats": {}}
        for k, v in items(sp.m_TexEnvs):
            if not v.m_Texture or v.m_Texture.path_id == 0: continue
            try: td = v.m_Texture.read()
            except Exception: continue
            info = {"tex": td.m_Name, "scale": [v.m_Scale.x, v.m_Scale.y], "offset": [v.m_Offset.x, v.m_Offset.y]}
            if k in ("_MainTex", "_BumpMap", "_EmissionMap", "_MossTex", "_EmissiveTex"):
                fn = f"{md.m_Name}__{k.strip('_')}__{td.m_Name}.png".replace("/", "_").replace(" ", "_")
                p = os.path.join(OUT, fn)
                if not os.path.exists(p): td.image.save(p)
                info["png"] = fn
            mi["textures"][k] = info
        mi["colors"] = {k: [round(x, 4) for x in (cc.r, cc.g, cc.b, cc.a)] for k, cc in items(sp.m_Colors)}
        mi["floats"] = {k: round(f, 4) for k, f in items(sp.m_Floats)}
        mats.append(mi)
    return mats


for spec in SPECS:
    prefab, path = spec[0], spec[1]; key = spec[2] if len(spec) > 2 else (prefab + "_" + path.split("/")[-1]).replace(" ", "_")
    d, cs = roots[prefab]
    tmap = {}; found = []
    def walk(go, parentM, parent, gpath):
        cs = comps(go)
        t = next(c for c in cs if type(c).__name__ == "Transform")
        M = parentM @ trs(t) if parent is not None else np.eye(4)
        tmap[t.object_reader.path_id] = (go.m_Name, M)
        for c in cs:
            n = type(c).__name__
            if n in ("MeshRenderer", "SkinnedMeshRenderer") and gpath.endswith(path):
                found.append((go, c, M, cs, n))
        for ch in t.m_Children:
            cg = ch.read().m_GameObject.read()
            walk(cg, M, go.m_Name, gpath + "/" + cg.m_Name)
    walk(d, np.eye(4), None, d.m_Name)
    assert found, spec
    go, c, M, ccs, n = found[0]
    if n == "SkinnedMeshRenderer": md = c.m_Mesh.read()
    else:
        mf = next(x for x in ccs if type(x).__name__ == "MeshFilter")
        try: md = mf.m_Mesh.read()
        except Exception as e:
            json.dump({"key": key, "builtin": True, "error": str(e)[:120], "matrix": M.round(6).tolist(), "materials": material(c)}, open(os.path.join(OUT, key + ".json"), "w"))
            print("PART", key, "BUILTIN MESH (unity default resources)", str(e)[:60]); continue
    h = MeshHandler(md); h.process()
    V = np.array(h.m_Vertices, float); N = np.array(h.m_Normals, float) if h.m_Normals else None
    UV = np.array(h.m_UV0, float) if h.m_UV0 else None
    subs = [[list(tr) for tr in sub] for sub in h.get_triangles()]
    res = {"key": key, "prefab": prefab, "path": path, "renderer": n, "mesh": md.m_Name, "materials": material(c),
           "uv0": UV.round(6).tolist() if UV is not None else None, "submeshes": subs}
    if n == "SkinnedMeshRenderer":
        world = (M @ np.c_[V, np.ones(len(V))].T).T[:, :3]
        res["frame"] = "prefab frame (root TRS ignored), Unity"
        res["verts"] = world.round(6).tolist()
        res["normals"] = ((np.linalg.inv(M[:3, :3]).T @ N.T).T).round(5).tolist() if N is not None else None
        res["weights"] = np.array(h.m_BoneWeights, float).round(4).tolist(); res["indices"] = np.array(h.m_BoneIndices, int).tolist()
        bones = [tmap.get(b.path_id, ("?", None)) for b in c.m_Bones]
        res["bone_names"] = [b[0] for b in bones]
        bb = []
        for j, bp in enumerate(md.m_BindPose):
            B = np.array([[getattr(bp, f"e{r}{cc}") for cc in range(4)] for r in range(4)])
            bb.append((M @ np.linalg.inv(B)).round(6).tolist())
        res["bone_bind_world"] = bb
    else:
        res["frame"] = "mesh local, Unity; matrix = renderer prefab-frame transform"
        res["verts"] = V.round(6).tolist(); res["normals"] = N.round(5).tolist() if N is not None else None
        res["matrix"] = M.round(6).tolist()
    json.dump(res, open(os.path.join(OUT, key + ".json"), "w"))
    print("PART", key, n, md.m_Name, "verts", len(V), "tris", sum(len(s) for s in subs), "mats", [m["name"] for m in res["materials"]],
          {m["name"]: {k: v.get("tex") for k, v in m["textures"].items()} for m in res["materials"]})
