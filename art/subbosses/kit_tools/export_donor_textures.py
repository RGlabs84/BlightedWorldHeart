#!/usr/bin/env python3
"""export_donor_textures.py - adapted from MagicRunicMod/unity/blender/export_donor_textures.py (2026-11-21).

Exports the textures (_MainTex, _BumpMap, _EmissionMap, _MetallicTex, ...) and properties of every material on a
vanilla prefab's renderers, offline from the 1.0.21 client bundle. Runic picked materials by path id; here they are found
through the prefab itself (root GameObject with that name and no parent, the creature root = the one with a Rigidbody),
so the material is exactly the one the creature uses. REFERENCE ONLY: game data for the Blender previews, never shipped
(at runtime the sub-boss is the cloned vanilla creature with its own material).

  ~/valheim-testbed/heavy.sh 4G sb-tex ~/upy/bin/python -I export_donor_textures.py OUTDIR Troll

Writes OUTDIR/<material>__<prop>__<texture>.png (RGBA as decoded; normal maps stay AG-packed, see UNITY-ASSET-TOOLS
TRAPS) and OUTDIR/materials.json (renderer -> materials, shader name if resolvable, textures, colours, floats).
"""
import json
import os
import sys

sys.path.insert(0, os.path.expanduser("~/WubarrkCODING/libs-Tools/UNITY-ASSET-TOOLS"))
import UnityPy
from valheim_paths import BUNDLE

OUT, PREFAB = sys.argv[1], sys.argv[2]
os.makedirs(OUT, exist_ok=True)
env = UnityPy.load(BUNDLE)


def comps(go):
    r = []
    for c in go.m_Component:
        try:
            r.append(c.component.read() if hasattr(c, "component") else c.read())
        except Exception:
            r.append(None)
    return r


best = None
for obj in env.objects:
    if obj.type.name != "GameObject":
        continue
    try:
        d = obj.read()
    except Exception:
        continue
    if d.m_Name != PREFAB:
        continue
    cs = comps(d)
    t = next((c for c in cs if type(c).__name__ == "Transform"), None)
    if t is None or t.m_Father.path_id != 0:
        continue
    score = sum(1 for c in cs if type(c).__name__ == "Rigidbody") * 10 + len(cs)
    if best is None or score > best[0]:
        best = (score, d)
assert best, PREFAB + " root not found"

items = lambda x: x.items() if isinstance(x, dict) else x
found, renderers = {}, []


def walk(go, path):
    cs = comps(go)
    for c in cs:
        n = type(c).__name__
        if n in ("SkinnedMeshRenderer", "MeshRenderer"):
            names = []
            for mp in c.m_Materials:
                md = mp.read()
                key = f"{md.m_Name}#{mp.path_id}"
                names.append(key)
                if key in found:
                    continue
                sp = md.m_SavedProperties
                entry = {"textures": {}, "colors": {}, "floats": {}}
                try:
                    entry["shader_path_id"] = md.m_Shader.path_id
                    entry["shader"] = md.m_Shader.read().m_Name
                except Exception as e:
                    entry["shader"] = "unresolved (dependency bundle): " + str(e)[:60]
                for k, v in items(sp.m_TexEnvs):
                    if not v.m_Texture or v.m_Texture.path_id == 0:
                        continue
                    try:
                        td = v.m_Texture.read()
                    except Exception as e:
                        entry["textures"][k] = {"error": str(e)[:80]}
                        continue
                    info = {"tex": td.m_Name, "size": [td.m_Width, td.m_Height], "scale": [v.m_Scale.x, v.m_Scale.y],
                            "offset": [v.m_Offset.x, v.m_Offset.y], "format": str(td.m_TextureFormat)}
                    fn = f"{md.m_Name}__{k.strip('_')}__{td.m_Name}.png"
                    try:
                        td.image.save(os.path.join(OUT, fn))
                        info["png"] = fn
                    except Exception as e:
                        info["error"] = str(e)[:80]
                    entry["textures"][k] = info
                entry["colors"] = {k: [round(c.r, 4), round(c.g, 4), round(c.b, 4), round(c.a, 4)] for k, c in items(sp.m_Colors)}
                entry["floats"] = {k: round(f, 4) for k, f in items(sp.m_Floats)}
                found[key] = entry
                print("ok", key, entry.get("shader"), {k: v.get("tex") for k, v in entry["textures"].items()})
            renderers.append({"go": path + "/" + go.m_Name, "renderer": n, "materials": names, "active": bool(go.m_IsActive)})
    t = next((c for c in cs if type(c).__name__ == "Transform"), None)
    for ch in t.m_Children:
        walk(ch.read().m_GameObject.read(), path + "/" + go.m_Name)


walk(best[1], "")
json.dump({"prefab": PREFAB, "bundle": BUNDLE, "renderers": renderers, "materials": found},
          open(os.path.join(OUT, "materials.json"), "w"), indent=1)
print("renderers", renderers)
