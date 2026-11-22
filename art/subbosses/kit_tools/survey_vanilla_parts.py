#!/usr/bin/env python3
"""survey_vanilla_parts.py - one UnityPy pass over the 1.0.21 client bundle: every prefab ROOT whose name matches the
kitbash candidates (Hive, pines, Abomination, Elder, Greydwarfs, swamp trees/roots/guck sacks, Yggdrasil, vines, rocks,
bones, Troll weapons, anything bark/root/eye/growth-like), walked to its renderers.

  heavy.sh 4G sb-survey ~/upy/bin/python -I survey_vanilla_parts.py OUT.tsv

One row per renderer: prefab, renderer path, renderer type, active, mesh name, mesh path_id, verts, tris, submesh tris,
materials (name#path_id), main/bump/emission texture names, local AABB centre and size of the mesh (mesh units), the
renderer's world scale in the prefab (so size_world = size x scale). GAME DATA, a reference only; nothing here ships.
"""
import os, re, sys
import numpy as np
sys.path.insert(0, os.path.expanduser("~/WubarrkCODING/libs-Tools/UNITY-ASSET-TOOLS"))
import UnityPy
from valheim_paths import BUNDLE

OUT = sys.argv[1]
PAT = re.compile(r"(TheHive|Pinetree_01$|Abomination|gd_king|Greydwarf_Elite|Greydwarf_Shaman|SwampTree|swamptree|GuckSack|"
                 r"Yggdrasil|yggdrasil|[Vv]ine|[Rr]oot|BonePile|Bonepile|bonepile|^Troll$|troll_log|TrollLog|[Mm]ossy|Hatchling|"
                 r"[Bb]ark|[Ss]tump|Spore|[Ee]ye|Sac$|sac$|Tentacle|tentacle|Tick$|Leech$|Blob|Skull|skull|Ribcage|ribcage|"
                 r"AncientRoot|ancient|Ancient|Gjall|Seeker|Root)")
env = UnityPy.load(BUNDLE)
roots = []
for obj in env.objects:
    if obj.type.name != "GameObject":
        continue
    try:
        d = obj.read()
    except Exception:
        continue
    if not PAT.search(d.m_Name):
        continue
    t = None
    for c in d.m_Component:
        try:
            cc = c.component.read() if hasattr(c, "component") else c.read()
        except Exception:
            continue
        if type(cc).__name__ == "Transform":
            t = cc
            break
    if t is not None and t.m_Father.path_id == 0:
        roots.append(d)
print("roots", len(roots))


def comps(go):
    r = []
    for c in go.m_Component:
        try:
            r.append(c.component.read() if hasattr(c, "component") else c.read())
        except Exception:
            r.append(None)
    return r


def trs_scale(t):
    return np.array([t.m_LocalScale.x, t.m_LocalScale.y, t.m_LocalScale.z])


items = lambda x: x.items() if isinstance(x, dict) else x
tex_cache = {}


def mat_info(mp):
    key = mp.path_id
    if key in tex_cache:
        return tex_cache[key]
    try:
        md = mp.read()
    except Exception:
        tex_cache[key] = ("?", "", "", "")
        return tex_cache[key]
    tx = {}
    for k, v in items(md.m_SavedProperties.m_TexEnvs):
        if k in ("_MainTex", "_BumpMap", "_EmissionMap", "_EmissiveTex") and v.m_Texture and v.m_Texture.path_id:
            try:
                tx[k] = v.m_Texture.read().m_Name
            except Exception:
                tx[k] = "?"
    tex_cache[key] = (f"{md.m_Name}#{key}", tx.get("_MainTex", ""), tx.get("_BumpMap", ""), tx.get("_EmissionMap", tx.get("_EmissiveTex", "")))
    return tex_cache[key]


rows = []


def walk(prefab, go, path, scale, active):
    cs = comps(go)
    t = next((c for c in cs if type(c).__name__ == "Transform"), None)
    if t is None:
        return
    sc = scale * trs_scale(t)
    act = active and bool(go.m_IsActive)
    mf = next((c for c in cs if type(c).__name__ == "MeshFilter"), None)
    for c in cs:
        n = type(c).__name__
        if n not in ("MeshRenderer", "SkinnedMeshRenderer"):
            continue
        mp = c.m_Mesh if n == "SkinnedMeshRenderer" else (mf.m_Mesh if mf else None)
        mname, mpid, nv, ntri, subs, ctr, size = "", 0, 0, 0, "", "", ""
        try:
            m = mp.read()
            mname, mpid = m.m_Name, mp.path_id
            nv = m.m_VertexData.m_VertexCount
            st = [int(s.indexCount // 3) for s in m.m_SubMeshes]
            ntri, subs = sum(st), "/".join(map(str, st))
            a = m.m_LocalAABB
            ctr = f"{a.m_Center.x:.3f},{a.m_Center.y:.3f},{a.m_Center.z:.3f}"
            size = f"{2 * a.m_Extent.x:.3f},{2 * a.m_Extent.y:.3f},{2 * a.m_Extent.z:.3f}"
        except Exception as e:
            mname = "ERR:" + str(e)[:30]
        mats = [mat_info(x) for x in c.m_Materials]
        rows.append([prefab, path + "/" + go.m_Name, n, str(act), mname, str(mpid), str(nv), str(ntri), subs,
                     ";".join(x[0] for x in mats), ";".join(x[1] for x in mats), ";".join(x[2] for x in mats),
                     ";".join(x[3] for x in mats), ctr, size, ",".join(f"{v:.3f}" for v in sc)])
    for ch in t.m_Children:
        try:
            walk(prefab, ch.read().m_GameObject.read(), path + "/" + go.m_Name, sc, act)
        except Exception:
            pass


seen = set()
for r in roots:
    if r.m_Name in seen:          # several roots can share a name (model + prefab); keep all, but tag duplicates
        pass
    seen.add(r.m_Name)
    walk(r.m_Name, r, "", np.ones(3), True)
hdr = ["prefab", "renderer_path", "renderer", "active", "mesh", "mesh_path_id", "verts", "tris", "submesh_tris", "materials",
       "main_tex", "bump_tex", "emission_tex", "aabb_center", "aabb_size", "world_scale"]
with open(OUT, "w") as f:
    f.write("\t".join(hdr) + "\n")
    for r in rows:
        f.write("\t".join(r) + "\n")
print("rows", len(rows), "prefabs", len(seen))
