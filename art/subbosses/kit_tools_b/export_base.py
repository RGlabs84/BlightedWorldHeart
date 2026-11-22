#!/usr/bin/env python3
"""Export a vanilla creature's REAL skinned body for the Runic-method kit previews (adapted from MagicRunicMod's
export_donor_textures.py + our export_donor.py). GAME DATA, a dev reference only: never shipped.

    export_base.py OUTDIR PREFAB RENDERER_NODE      (~/upy/bin/python -I, through heavy.sh 4G)

Writes OUTDIR/:
  base.json   mesh (verts in Unity space relative to the prefab root, true x), triangles, UV0, normals, 4 bone weights,
              bone names, per-bone BIND world matrices (4x4, Unity, root-relative) and prefab-pose world matrices,
              non-skinned nodes (attach points, end bones) with prefab world matrices, the material and its colours/floats
  <material>__MainTex__<tex>.png, <material>__BumpMap__<tex>.png  (RGBA as decoded; normals AG-packed)
"""
import os, sys, json
sys.path.insert(0, os.path.expanduser("~/WubarrkCODING/libs-Tools/UNITY-ASSET-TOOLS"))
import numpy as np
import UnityPy
from UnityPy.helpers.MeshHelper import MeshHandler
from valheim_paths import BUNDLE

OUT, WANT, NODE = sys.argv[1], sys.argv[2], sys.argv[3]
os.makedirs(OUT, exist_ok=True)
env = UnityPy.load(BUNDLE)


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


root = None
for obj in env.objects:
    if obj.type.name != "GameObject": continue
    try: d = obj.read()
    except Exception: continue
    if d.m_Name != WANT: continue
    cs = comps(d)
    t = next((c for c in cs if type(c).__name__ == "Transform"), None)
    if t is not None and t.m_Father.path_id == 0 and any(type(c).__name__ == "CapsuleCollider" for c in cs):
        root = d; break
assert root, WANT

tmap, nodes, smr = {}, {}, None
def walk(go, parentM, parent):
    global smr
    cs = comps(go)
    t = next(c for c in cs if type(c).__name__ == "Transform")
    M = parentM @ trs(t) if parent is not None else np.eye(4)
    tmap[t.object_reader.path_id] = (go.m_Name, M)
    nodes[go.m_Name] = {"parent": parent, "world": M.round(6).tolist()}
    for c in cs:
        if type(c).__name__ == "SkinnedMeshRenderer" and go.m_Name == NODE:
            smr = (go, c, M)
    for ch in t.m_Children:
        walk(ch.read().m_GameObject.read(), M, go.m_Name)
walk(root, np.eye(4), None)
go, c, M = smr
md = c.m_Mesh.read()
h = MeshHandler(md); h.process()
V = np.array(h.m_Vertices, float); N = np.array(h.m_Normals, float) if h.m_Normals else None
UV = np.array(h.m_UV0, float) if h.m_UV0 else None
W = np.array(h.m_BoneWeights, float); I = np.array(h.m_BoneIndices, int)
tris = [list(tr) for sub in h.get_triangles() for tr in sub]
world = (M @ np.c_[V, np.ones(len(V))].T).T[:, :3]
Nw = None
if N is not None:
    Nw = (np.linalg.inv(M[:3, :3]).T @ N.T).T
    Nw /= np.linalg.norm(Nw, axis=1, keepdims=True) + 1e-12
bones = [tmap.get(b.path_id, ("?", None)) for b in c.m_Bones]
bind = []
for j, bp in enumerate(md.m_BindPose):
    B = np.array([[getattr(bp, f"e{r}{cc}") for cc in range(4)] for r in range(4)])
    bind.append((M @ np.linalg.inv(B)).round(6).tolist())
mat = c.m_Materials[0].read()
sp = mat.m_SavedProperties
items = lambda x: x.items() if isinstance(x, dict) else x
minfo = {"name": mat.m_Name, "path_id": c.m_Materials[0].path_id, "textures": {}, "colors": {}, "floats": {}}
try: minfo["shader"] = mat.m_Shader.read().m_ParsedForm.m_Name
except Exception as e: minfo["shader"] = "unresolved (" + str(e)[:40] + ")"
for k, v in items(sp.m_TexEnvs):
    if not v.m_Texture or v.m_Texture.path_id == 0: continue
    td = v.m_Texture.read()
    info = {"tex": td.m_Name, "size": [td.m_Width, td.m_Height], "scale": [v.m_Scale.x, v.m_Scale.y], "offset": [v.m_Offset.x, v.m_Offset.y]}
    if k in ("_MainTex", "_BumpMap", "_EmissionMap", "_MetallicGlossMap"):
        fn = f"{mat.m_Name}__{k.strip('_')}__{td.m_Name}.png"; td.image.save(os.path.join(OUT, fn)); info["png"] = fn
    minfo["textures"][k] = info
minfo["colors"] = {k: [round(x, 4) for x in (cc.r, cc.g, cc.b, cc.a)] for k, cc in items(sp.m_Colors)}
minfo["floats"] = {k: round(f, 4) for k, f in items(sp.m_Floats)}
res = {"prefab": WANT, "renderer": NODE, "mesh": md.m_Name, "frame": "Unity, metres, root-relative (root TRS ignored)",
       "verts": world.round(6).tolist(), "normals": Nw.round(5).tolist() if Nw is not None else None,
       "uv0": UV.round(6).tolist() if UV is not None else None, "tris": tris,
       "weights": W.round(4).tolist(), "indices": I.tolist(), "bone_names": [b[0] for b in bones],
       "bone_bind_world": bind, "bone_prefab_world": [b[1].round(6).tolist() for b in bones],
       "nodes": nodes, "material": minfo}
json.dump(res, open(os.path.join(OUT, "base.json"), "w"))
print("BASE", md.m_Name, "verts", len(world), "tris", len(tris), "uv", UV is not None, "bones", len(bones))
print("MAT", json.dumps(minfo)[:1500])
