#!/usr/bin/env python3
"""Export vanilla donor creatures for the BlightedHeart sub-bosses (step 1, shapes only).

For each donor prefab (the CREATURE root: the GameObject of that name with no parent and a Rigidbody):
  - every transform: name, parent, path, local TRS, world matrix (prefab rest pose);
  - every SkinnedMeshRenderer (active or not): mesh name, materials, bone list, root bone, bind poses,
    vertices in BIND POSE world space (renderer world @ v) and in PREFAB-REST skinned space
    (sum w * boneWorld @ bindpose @ v), triangles, bone indices/weights;
  - bind-pose bone world positions (renderer world @ inverse(bindpose));
  - bounds of each renderer, and of the active body renderers together.
All coordinates are UNITY world space (x right, y up, z forward), metres, root at the origin.
(UnityPy's OBJ export negates x; this script reads the raw vertex data instead, so nothing is negated.)

Usage: ~/upy/bin/python -I export_donor.py OUTROOT Donor:FolderName [Donor:FolderName ...]
Writes OUTROOT/<FolderName>/donor/donor_bones.json, donor_mesh_<renderer>.json, donor_<renderer>.obj (Unity frame, y up)
"""
import os, sys, json
sys.path.insert(0, os.path.expanduser("~/WubarrkCODING/libs-Tools/UNITY-ASSET-TOOLS"))
import numpy as np
import UnityPy
from UnityPy.helpers.MeshHelper import MeshHandler
from valheim_paths import BUNDLE

OUTROOT = sys.argv[1]
JOBS = [a.split(":") for a in sys.argv[2:]]
WANT = {d for d, _ in JOBS}

env = UnityPy.load(BUNDLE)
cands = {}
for obj in env.objects:
    if obj.type.name != "GameObject":
        continue
    try:
        d = obj.read()
    except Exception:
        continue
    if d.m_Name in WANT:
        cands.setdefault(d.m_Name, []).append(d)


def comps(go):
    out = []
    for c in go.m_Component:
        try:
            out.append(c.component.read() if hasattr(c, "component") else c.read())
        except Exception:
            out.append(None)
    return out


def tname(c):
    return type(c).__name__ if c is not None else "None"


def get_t(go):
    return next((c for c in comps(go) if tname(c) == "Transform"), None)


def trs(t):
    p, q, s = t.m_LocalPosition, t.m_LocalRotation, t.m_LocalScale
    x, y, z, w = q.x, q.y, q.z, q.w
    R = np.array([[1 - 2 * (y * y + z * z), 2 * (x * y - z * w), 2 * (x * z + y * w)],
                  [2 * (x * y + z * w), 1 - 2 * (x * x + z * z), 2 * (y * z - x * w)],
                  [2 * (x * z - y * w), 2 * (y * z + x * w), 1 - 2 * (x * x + y * y)]])
    M = np.eye(4)
    M[:3, :3] = R @ np.diag([s.x, s.y, s.z])
    M[:3, 3] = [p.x, p.y, p.z]
    return M


def m44(m):
    a = np.array([[getattr(m, f"e{r}{c}") for c in range(4)] for r in range(4)], dtype=float)
    if abs(a[3, 0]) + abs(a[3, 1]) + abs(a[3, 2]) > 1e-5:   # stored column-major: transpose
        a = a.T
    return a


def pick_root(name):
    best = None
    for d in cands.get(name, []):
        t = get_t(d)
        try:
            isroot = t.m_Father.path_id == 0
        except Exception:
            isroot = True
        if not isroot:
            continue
        names = [tname(c) for c in comps(d)]
        score = ("Rigidbody" in names) * 10 + len(names)
        if best is None or score > best[0]:
            best = (score, d, names)
    return best


for donor, folder in JOBS:
    best = pick_root(donor)
    assert best, f"{donor} root not found"
    root = best[1]
    out = os.path.join(OUTROOT, folder, "donor")
    os.makedirs(out, exist_ok=True)
    xforms = {}      # path_id -> record
    smrs = []

    def walk(go, parentM, path, parent_name, active):
        t = get_t(go)
        M = np.eye(4) if parent_name is None else parentM @ trs(t)   # root's own TRS dropped (Valheim parks prefab roots at y=50)
        act = active and bool(go.m_IsActive)
        pid = t.object_reader.path_id
        p, q, s = t.m_LocalPosition, t.m_LocalRotation, t.m_LocalScale
        xforms[pid] = {"name": go.m_Name, "path": path + "/" + go.m_Name, "parent": parent_name, "active": act,
                       "local_pos": [p.x, p.y, p.z], "local_rot_xyzw": [q.x, q.y, q.z, q.w], "local_scale": [s.x, s.y, s.z],
                       "world_pos": M[:3, 3].tolist(), "world_matrix": M.tolist()}
        for c in comps(go):
            if tname(c) == "SkinnedMeshRenderer":
                smrs.append((go, c, M, path + "/" + go.m_Name, act))
        for ch in t.m_Children:
            walk(ch.read().m_GameObject.read(), M, path + "/" + go.m_Name, go.m_Name, act)

    walk(root, np.eye(4), "", None, True)
    renderers = []
    allv_active = []
    for go, smr, M, path, act in smrs:
        mesh = smr.m_Mesh.read()
        mh = MeshHandler(mesh)
        mh.process()
        V = np.array(mh.m_Vertices, dtype=float)[:, :3]
        subs = mh.get_triangles()
        tris = [list(t) for sm in subs for t in sm]
        bones = []
        for b in smr.m_Bones:
            try:
                bt = b.read()
                bones.append((bt.object_reader.path_id, bt.m_GameObject.read().m_Name))
            except Exception:
                bones.append((None, None))
        try:
            rb = smr.m_RootBone.read().m_GameObject.read().m_Name
        except Exception:
            rb = None
        BP = [m44(m) for m in mesh.m_BindPose]
        Vh = np.c_[V, np.ones(len(V))]
        bind_world = (M @ Vh.T).T[:, :3]
        # prefab-rest skinning
        bi = np.array(mh.m_BoneIndices, dtype=int) if mh.m_BoneIndices else None
        bw = np.array(mh.m_BoneWeights, dtype=float) if mh.m_BoneWeights else None
        rest = None
        if bi is not None and bw is not None and len(BP) == len(bones):
            skin = []
            for (pid, nm), bp in zip(bones, BP):
                W = np.array(xforms[pid]["world_matrix"]) if pid in xforms else M
                skin.append(W @ bp)
            skin = np.array(skin)
            rest = np.zeros((len(V), 3))
            for k in range(bi.shape[1]):
                Mk = skin[bi[:, k]]                       # (n,4,4)
                pk = np.einsum("nij,nj->ni", Mk, Vh)[:, :3]
                rest += pk * bw[:, k:k + 1]
            wsum = bw.sum(1, keepdims=True)
            wsum[wsum == 0] = 1
            rest /= wsum
        bind_bones = []
        for (pid, nm), bp in zip(bones, BP):
            Wb = M @ np.linalg.inv(bp)
            bind_bones.append({"name": nm, "bind_world_pos": Wb[:3, 3].tolist(),
                               "prefab_world_pos": xforms[pid]["world_pos"] if pid in xforms else None})
        lo, hi = bind_world.min(0), bind_world.max(0)
        rec = {"go": path, "renderer_active": act, "mesh": mesh.m_Name,
               "materials": [m.read().m_Name for m in smr.m_Materials],
               "verts": len(V), "tris": len(tris), "submeshes": [len(s) for s in subs],
               "root_bone": rb, "bone_count": len(bones), "bones": [n for _, n in bones],
               "bind_bones": bind_bones,
               "bounds_bind_min": lo.tolist(), "bounds_bind_max": hi.tolist(), "bounds_bind_size": (hi - lo).tolist(),
               "renderer_world_matrix": M.tolist()}
        if rest is not None:
            rec["rest_vs_bind_max_dev_m"] = float(np.abs(rest - bind_world).max())
        renderers.append(rec)
        safe = go.m_Name.replace(" ", "_")
        uvs = mh.m_UV0
        mj = {"name": go.m_Name, "mesh": mesh.m_Name, "verts_bind_world": np.round(bind_world, 5).tolist(),
              "verts_rest_world": np.round(rest, 5).tolist() if rest is not None else None,
              "tris": tris, "submesh_tri_counts": [len(s) for s in subs],
              "bone_names": [n for _, n in bones],
              "bone_indices": bi.tolist() if bi is not None else None,
              "bone_weights": np.round(bw, 4).tolist() if bw is not None else None,
              "uv0": [list(u) for u in uvs] if uvs else None}
        json.dump(mj, open(os.path.join(out, f"donor_mesh_{safe}.json"), "w"))
        with open(os.path.join(out, f"donor_{safe}.obj"), "w") as f:
            f.write(f"# {donor}/{path} bind pose, Unity world frame (y up, +z forward), metres\n")
            for v in bind_world:
                f.write(f"v {v[0]:.5f} {v[1]:.5f} {v[2]:.5f}\n")
            # Unity is left-handed (clockwise front faces); reverse winding for a right-handed OBJ viewer
            for t in tris:
                f.write(f"f {t[0] + 1} {t[2] + 1} {t[1] + 1}\n")
        if rest is not None and rec.get("rest_vs_bind_max_dev_m", 0) > 0.01:
            with open(os.path.join(out, f"donor_{safe}_prefabrest.obj"), "w") as f:
                f.write(f"# {donor}/{path} PREFAB REST pose (differs from bind), Unity world frame\n")
                for v in rest:
                    f.write(f"v {v[0]:.5f} {v[1]:.5f} {v[2]:.5f}\n")
                for t in tris:
                    f.write(f"f {t[0] + 1} {t[2] + 1} {t[1] + 1}\n")
        if act:
            allv_active.append(bind_world)
    A = np.concatenate(allv_active) if allv_active else np.zeros((1, 3))
    lo, hi = A.min(0), A.max(0)
    # skeleton (the bone set of the main body renderer, ordered by hierarchy walk)
    used = set()
    for r in renderers:
        used.update(r["bones"])
    skel = [dict(name=x["name"], parent=x["parent"], path=x["path"], world_pos=x["world_pos"],
                 local_pos=x["local_pos"], local_rot_xyzw=x["local_rot_xyzw"], local_scale=x["local_scale"],
                 skinned=x["name"] in used, active=x["active"]) for x in xforms.values()]
    rt = get_t(root)
    info = {"donor": donor, "root_local_pos_dropped": [rt.m_LocalPosition.x, rt.m_LocalPosition.y, rt.m_LocalPosition.z], "bundle": BUNDLE, "frame": "Unity world, metres, x right, y up, +z forward; root at origin",
            "root_components": best[2], "renderers": renderers,
            "active_body_bounds_min": lo.tolist(), "active_body_bounds_max": hi.tolist(),
            "active_body_bounds_size": (hi - lo).tolist(),
            "transforms": skel}
    json.dump(info, open(os.path.join(out, "donor_bones.json"), "w"), indent=1)
    print("DONOR", donor, "->", out)
    for r in renderers:
        print("  SMR", r["go"], "active", r["renderer_active"], "mesh", r["mesh"], "mats", r["materials"], "verts", r["verts"],
              "tris", r["tris"], "bones", r["bone_count"], "root", r["root_bone"],
              "size", [round(x, 3) for x in r["bounds_bind_size"]], "min", [round(x, 3) for x in r["bounds_bind_min"]],
              "rest_dev", round(r.get("rest_vs_bind_max_dev_m", -1), 4))
    print("  active bounds min", np.round(lo, 3), "max", np.round(hi, 3), "size", np.round(hi - lo, 3))
