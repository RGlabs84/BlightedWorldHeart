#!/usr/bin/env python3
"""Survey vanilla prefabs for kitbash parts: every renderer under each named root with mesh, tris, materials (+ _MainTex),
and for skinned renderers the bone names. Writes OUT/parts_survey.json and prints a table.
    survey_parts.py OUT PREFAB [PREFAB ...]      (~/upy/bin/python -I, heavy.sh 4G)"""
import os, sys, json
sys.path.insert(0, os.path.expanduser("~/WubarrkCODING/libs-Tools/UNITY-ASSET-TOOLS"))
import UnityPy
from valheim_paths import BUNDLE

OUT = sys.argv[1]; WANT = set(sys.argv[2:])
os.makedirs(OUT, exist_ok=True)
env = UnityPy.load(BUNDLE)


def comps(go):
    r = []
    for c in go.m_Component:
        try: r.append(c.component.read() if hasattr(c, "component") else c.read())
        except Exception: r.append(None)
    return r


roots = {}
for obj in env.objects:
    if obj.type.name != "GameObject": continue
    try: d = obj.read()
    except Exception: continue
    if d.m_Name not in WANT: continue
    cs = comps(d)
    t = next((c for c in cs if type(c).__name__ == "Transform"), None)
    if t is None or t.m_Father.path_id != 0: continue
    roots.setdefault(d.m_Name, []).append((d, cs, t))

res = {}
for name, lst in roots.items():
    # prefer the root with the most components (the registered prefab, not a bare model)
    d, cs, t = max(lst, key=lambda x: len(x[1]))
    out = []
    def walk(go, t, path, active):
        cs = comps(go)
        for c in cs:
            n = type(c).__name__
            if n in ("MeshRenderer", "SkinnedMeshRenderer"):
                mesh = None
                try:
                    if n == "SkinnedMeshRenderer": mesh = c.m_Mesh.read()
                    else:
                        mf = next((x for x in cs if type(x).__name__ == "MeshFilter"), None)
                        mesh = mf.m_Mesh.read() if mf else None
                except Exception: mesh = None
                tris = None
                if mesh is not None:
                    try: tris = sum(s.indexCount for s in mesh.m_SubMeshes) // 3
                    except Exception: pass
                mats = []
                for m in c.m_Materials:
                    try:
                        md = m.read(); tex = None
                        sp = md.m_SavedProperties; items = sp.m_TexEnvs.items() if isinstance(sp.m_TexEnvs, dict) else sp.m_TexEnvs
                        for k, v in items:
                            if k == "_MainTex" and v.m_Texture and v.m_Texture.path_id:
                                tex = v.m_Texture.read().m_Name
                        mats.append({"mat": md.m_Name, "path_id": m.path_id, "main": tex})
                    except Exception as e: mats.append({"mat": "ERR"})
                bones = None
                if n == "SkinnedMeshRenderer":
                    bones = []
                    for b in c.m_Bones:
                        try: bones.append(b.read().m_GameObject.read().m_Name)
                        except Exception: bones.append("?")
                out.append({"path": path, "active": active, "renderer": n, "mesh": mesh.m_Name if mesh else None,
                            "mesh_path_id": (c.m_Mesh.path_id if n == "SkinnedMeshRenderer" else None), "tris": tris, "materials": mats, "bones": bones})
        for ch in t.m_Children:
            cg = ch.read().m_GameObject.read()
            ct = next((x for x in comps(cg) if type(x).__name__ == "Transform"), None)
            walk(cg, ct, path + "/" + cg.m_Name, active and cg.m_IsActive)
    walk(d, t, d.m_Name, d.m_IsActive)
    res[name] = out
    for r in out:
        print(f"{name:22s} {r['renderer'][:4]} act={int(r['active'])} tris={r['tris']} mesh={r['mesh']} mats={[m.get('mat') + ':' + str(m.get('main')) for m in r['materials']]} path={r['path'][-60:]}"
              + (f" bones={len(r['bones'])}:{r['bones'][:6]}" if r['bones'] else ""))
json.dump(res, open(os.path.join(OUT, "parts_survey.json"), "w"), indent=1)
print("MISSING", sorted(WANT - set(roots)))
