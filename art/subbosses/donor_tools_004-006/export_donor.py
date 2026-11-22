#!/usr/bin/env python3
"""Export a Valheim creature donor's rig for the sub-boss models (BlightedHeart ASSET-004..006).

    export_donor.py OUTDIR PREFAB [PREFAB ...]      (run with ~/upy/bin/python -I through heavy.sh 4G)

For each PREFAB (the creature root that has a CapsuleCollider, not the Visual-only model prefab):
  OUTDIR/<PREFAB>/donor_bones.json
      - every transform under the prefab: name, parent, world position (Unity frame, metres)
      - every active SkinnedMeshRenderer: mesh, material, root bone, bone list with the BIND-POSE world position
        (smr.localToWorld @ inverse(bindpose[i]) applied to the origin) and the prefab-pose world position
      - bind-pose mesh bounds per renderer and overall, ground contact (min y)
      - MonoBehaviour class names on every node, and VisEquipment / Humanoid fields that name transforms or renderers
  OUTDIR/<PREFAB>/smr_<i>_<mesh>.obj   the bind-pose mesh in WORLD Unity space (x NOT negated: UnityPy's OBJ x-flip is undone)
Unity (x,y,z) -> Blender (x,z,y) is left to the Blender side.
"""
import os, sys, json
sys.path.insert(0, os.path.expanduser("~/WubarrkCODING/libs-Tools/UNITY-ASSET-TOOLS"))
import numpy as np
import UnityPy
from UnityPy.helpers.TypeTreeGenerator import TypeTreeGenerator
from UnityPy.helpers.MeshHelper import MeshHandler
from valheim_paths import BUNDLE, VALHEIM_DIR, UNITY_VERSION, sibling_bundle

OUT = sys.argv[1]
WANT = sys.argv[2:]
env = UnityPy.load(BUNDLE, sibling_bundle("86c3d76e"), sibling_bundle("2c2cce25"))
try:  # optional: resolves MonoBehaviour fields by name; without it PPtrs are found by a raw byte scan
    gen = TypeTreeGenerator(UNITY_VERSION); gen.load_local_game(VALHEIM_DIR); env.typetree_generator = gen; HAVE_TTG = True
except Exception as e:
    print("TypeTreeGenerator unavailable (" + str(e)[:60] + "): raw PPtr scan for MonoBehaviour fields"); HAVE_TTG = False
import struct


def raw_pptrs(c, known):
    """PPtrs (fileID 0, pathID in `known`) in a MonoBehaviour's raw bytes, in field order."""
    try: raw = c.object_reader.get_raw_data()
    except Exception: return "ERR raw"
    out = []
    for off in range(0, len(raw) - 11, 4):
        fid, pid_ = struct.unpack_from("<iq", raw, off)
        if fid == 0 and pid_ in known: out.append([off, known[pid_]])
    return out


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


def mat4(m):
    """UnityPy Matrix4x4f -> numpy (row, col). Unity stores eRC."""
    A = np.zeros((4, 4))
    for r in range(4):
        for c in range(4):
            A[r, c] = getattr(m, f"e{r}{c}")
    return A


def read_obj_verts(text):
    vs, fs = [], []
    for line in text.splitlines():
        p = line.split()
        if not p: continue
        if p[0] == "v": vs.append([float(x) for x in p[1:4]])
        elif p[0] == "f": fs.append([int(c.split("/")[0]) - 1 for c in p[1:]])
    return np.array(vs), fs


def find_root(name):
    for obj in env.objects:
        if obj.type.name != "GameObject": continue
        try: d = obj.read()
        except Exception: continue
        if d.m_Name != name: continue
        cs = comps(d)
        t = next((c for c in cs if type(c).__name__ == "Transform"), None)
        if t is None or t.m_Father.path_id != 0: continue
        if any(type(c).__name__ == "CapsuleCollider" for c in cs):
            return d
    return None


def pptr_name(p):
    try:
        if p is None or p.path_id == 0: return None
        o = p.read()
        n = getattr(o, "m_Name", None)
        if not n and hasattr(o, "m_GameObject"): n = o.m_GameObject.read().m_Name
        return f"{type(o).__name__}:{n}"
    except Exception as e:
        return "ERR"


def summarise_mb(d):
    """Fields of a MonoBehaviour that point to Transforms/Renderers/GameObjects (and a few scalars)."""
    out = {}
    for k, v in vars(d).items():
        if k.startswith("m_") is False or k in ("m_GameObject", "m_Script", "m_Enabled", "m_Name", "m_EditorHideFlags", "m_EditorClassIdentifier"):
            continue
        if hasattr(v, "path_id"):
            n = pptr_name(v)
            if n: out[k] = n
        elif isinstance(v, list) and v and hasattr(v[0], "path_id"):
            out[k] = [pptr_name(x) for x in v]
        elif isinstance(v, (int, float, bool, str)) and k in ("m_isPlayer", "m_useAllTrails", "m_currentRightItemHash"):
            out[k] = v
    return out


for want in WANT:
    root = find_root(want)
    assert root, want + " not found"
    od = os.path.join(OUT, want); os.makedirs(od, exist_ok=True)
    nodes, smrs, mbs = [], [], []
    tmap = {}  # transform path_id -> (name, world M)

    def walk(go, parentM, parent):
        cs = comps(go)
        t = next((c for c in cs if type(c).__name__ == "Transform"), None)
        M = parentM @ trs(t) if parent is not None else np.eye(4)  # frame = the prefab root (vanilla roots sit at y 50)
        if parent is None:
            root_trs.update(pos=[t.m_LocalPosition.x, t.m_LocalPosition.y, t.m_LocalPosition.z],
                            rot_xyzw=[t.m_LocalRotation.x, t.m_LocalRotation.y, t.m_LocalRotation.z, t.m_LocalRotation.w],
                            scale=[t.m_LocalScale.x, t.m_LocalScale.y, t.m_LocalScale.z])
        tmap[t.object_reader.path_id] = (go.m_Name, M)
        nodes.append({"name": go.m_Name, "parent": parent, "active": bool(go.m_IsActive),
                      "world_pos": [round(x, 5) for x in M[:3, 3]],
                      "components": [type(c).__name__ if c is not None else "ERR" for c in cs]})
        for c in cs:
            n = type(c).__name__
            if n == "MonoBehaviour":
                try: cn = c.m_Script.read().m_ClassName
                except Exception: cn = "?"
                ent = {"node": go.m_Name, "class": cn}
                if cn in ("VisEquipment", "Humanoid", "Character", "MonsterAI", "CharacterAnimEvent", "LevelEffects", "FootStep"):
                    if HAVE_TTG:
                        try: ent["fields"] = summarise_mb(c)
                        except Exception as e: ent["fields"] = "ERR " + str(e)[:80]
                    else:
                        late_mbs.append((ent, c))
                mbs.append(ent)
            if n == "SkinnedMeshRenderer":
                smrs.append((go, c, M))
        for ch in t.m_Children:
            walk(ch.read().m_GameObject.read(), M, go.m_Name)

    late_mbs = []; root_trs = {}
    walk(root, np.eye(4), None)
    known = {pid_: "Transform:" + nm for pid_, (nm, _) in tmap.items()}
    for go_, c_, _ in smrs: known[c_.object_reader.path_id] = "SkinnedMeshRenderer:" + go_.m_Name
    for ent, c in late_mbs:
        ent["raw_pptrs(byte_offset,target)"] = raw_pptrs(c, known)
    allv = []
    smr_out = []
    for i, (go, c, M) in enumerate(smrs):
        md = c.m_Mesh.read()
        mats = [pptr_name(m) for m in c.m_Materials]
        bones = [tmap.get(b.path_id, ("?", None)) for b in c.m_Bones]
        bp = [mat4(m) for m in md.m_BindPose]
        h = MeshHandler(md); h.process()  # raw Unity mesh-local data (UnityPy's OBJ export would negate x)
        vs = np.array(h.m_Vertices, dtype=float)
        fs = [list(tri) for sub in h.get_triangles() for tri in sub]
        bw = np.array(h.m_BoneWeights, dtype=float) if h.m_BoneWeights else np.zeros((len(vs), 4))
        bi = np.array(h.m_BoneIndices, dtype=int) if h.m_BoneIndices else np.zeros((len(vs), 4), int)
        world = (M @ np.c_[vs, np.ones(len(vs))].T).T[:, :3]
        entry = {"node": go.m_Name, "active": bool(go.m_IsActive), "mesh": md.m_Name, "materials": mats,
                 "root_bone": tmap.get(c.m_RootBone.path_id, ("?",))[0] if c.m_RootBone.path_id else None,
                 "verts": int(len(vs)), "tris": int(sum(len(f) - 2 for f in fs)),
                 "bounds_min": [round(x, 4) for x in world.min(0)], "bounds_max": [round(x, 4) for x in world.max(0)],
                 "bones": []}
        for j, (bn, bM) in enumerate(bones):
            bind = (M @ np.linalg.inv(bp[j]))[:3, 3] if j < len(bp) else None
            entry["bones"].append({"name": bn, "bind_world": [round(x, 5) for x in bind] if bind is not None else None,
                                   "prefab_world": [round(x, 5) for x in bM[:3, 3]] if bM is not None else None})
        fn = f"smr_{i}_{md.m_Name.replace(' ', '_')}.obj"
        with open(os.path.join(od, fn), "w") as f:
            f.write(f"# {want} {go.m_Name} bind pose, Unity space relative to the prefab root (true x, not UnityPy's flipped OBJ)\n")
            for v in world: f.write(f"v {v[0]:.6f} {v[1]:.6f} {v[2]:.6f}\n")
            for fc in fs: f.write("f " + " ".join(str(k + 1) for k in fc) + "\n")
        entry["obj"] = fn
        # per-vertex skin weights (4 influences) for weight transfer at step 3; bone index -> entry["bones"][k]["name"]
        wfn = f"smr_{i}_{md.m_Name.replace(' ', '_')}_weights.json"
        json.dump({"bone_names": [b[0] for b in bones], "indices": bi.tolist(), "weights": np.round(bw, 4).tolist()},
                  open(os.path.join(od, wfn), "w"))
        entry["weights_file"] = wfn
        # sanity: the vertex at max +x should be weighted to a bone whose bind position is on +x
        k = int(world[:, 0].argmax()); kb = int(bi[k][int(bw[k].argmax())]) if len(bw) else -1
        entry["x_check"] = {"vertex_max_x": [round(x, 3) for x in world[k]], "dominant_bone": bones[kb][0] if kb >= 0 else None,
                            "bone_bind_x": round(float((M @ np.linalg.inv(bp[kb]))[0, 3]), 3) if kb >= 0 else None}
        print("   x_check", entry["x_check"])
        smr_out.append(entry)
        if go.m_IsActive: allv.append(world)
        print(want, go.m_Name, md.m_Name, mats, "verts", len(vs), "bones", len(bones), "bindposes", len(bp))
    allv = np.concatenate(allv)
    attach = [n for n in nodes if "attach" in n["name"].lower()]
    res = {"prefab": want, "bundle": BUNDLE, "frame": "Unity, metres, +Y up, relative to the prefab root (root's own TRS ignored, recorded in root_local_trs)", "root_local_trs": root_trs,
           "bounds_min": [round(x, 4) for x in allv.min(0)], "bounds_max": [round(x, 4) for x in allv.max(0)],
           "size": [round(x, 4) for x in (allv.max(0) - allv.min(0))],
           "attach_nodes": attach, "renderers": smr_out, "monobehaviours": mbs, "nodes": nodes}
    json.dump(res, open(os.path.join(od, "donor_bones.json"), "w"), indent=1, default=str)
    print(want, "root", root_trs, "bounds", res["bounds_min"], res["bounds_max"], "size", res["size"])
    print(want, "attach", [a["name"] for a in attach])
    for m in mbs: print(want, "MB", m["node"], m["class"], json.dumps(m.get("fields", m.get("raw_pptrs(byte_offset,target)", "")), default=str)[:700])
