"""step3_post.py - STEP 3 (texture/material) for agent B's kitbash creatures (Seer, Husk, Broodhusk), done as a POST-PROCESS on the
approved scene so geometry cannot change: it opens <kit>/<Name>_kitbash.blend, applies the surface recipe (crust moss halved, weathered
matte branches), renders the final-look set with kit_tools/final_look.py (day, dusk, close-ups, 10 m read, base repaint, biome panel),
writes materials_recipe.json from the scene's actual materials, and saves <Name>_kitbash_step3.blend (the approved .blend is untouched).

Run: heavy.sh 4G <label> blender -b --factory-startup -P step3_post.py -- <asset key: seer|husk|brood> <abs kit dir>
"""
import bpy, os, sys, json
from mathutils import Vector

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "kit_tools"))
sys.path.insert(0, os.path.join(HERE, "..", "tools_001-003"))     # hive_kit (grid helper) lives here
import final_look as FL
import hive_kit as hk

argv = sys.argv[sys.argv.index("--") + 1:]
KEY, KIT = argv[0], argv[1]
PREV = os.path.join(KIT, "previews")

# per creature: blend, front azimuth (DB.camera: az 0 looks at a +Y-facing creature), framing, which branch material to weather
CFG = {
    "seer": dict(blend="EyeblightSeer_kitbash.blend", fa=0, cen=(0, 0, 1.3), d=(7.5, 8, 7.5, 8),
                 head=((0, 0.55, 1.85), 2.2, 25, 8), wtf=((0, 0.5, 1.56), 1.6, 15, 0), branches=((0.1, -0.8, 2.1), 2.8, 160, 20),
                 read10=((0, 0, 1.3), 10.0, 0, 3), weather_branch=False),
    "husk": dict(blend="BarkboundHusk_kitbash.blend", fa=180, cen=(0, 0, 1.2), d=(6.5, 7, 6.5, 7),
                 head=((0, -0.05, 2.1), 1.8, 200, 8), wtf=((0, 0, 2.08), 1.5, 110, 10), branches=((0.1, 0.2, 2.3), 2.6, 330, 15),
                 read10=((0, 0, 1.2), 10.0, 180, 3), weather_branch=True),
    "brood": dict(blend="Broodhusk_kitbash.blend", fa=0, cen=(0, 0.8, 1.2), d=(10, 11, 10, 11),
                  head=((0, 2.4, 1.3), 3.0, 20, 10), wtf=((0, -0.8, 0.9), 2.4, 150, 18), branches=((0, -0.2, 1.6), 2.8, 120, 20),
                  read10=((0, 0.8, 1.0), 10.0, 90, 3), weather_branch=False),
}[KEY]

bpy.ops.wm.open_mainfile(filepath=os.path.join(KIT, CFG["blend"]))
sc = bpy.context.scene
for e in ("BLENDER_EEVEE_NEXT", "BLENDER_EEVEE"):
    try:
        sc.render.engine = e; break
    except TypeError:
        pass

meshes = [o for o in bpy.data.objects if o.type == 'MESH']
body = next(o for o in meshes if any(s.material and s.material.name.endswith("_repaint") for s in o.material_slots))
rpmat = next(s.material for s in body.material_slots if s.material and s.material.name.endswith("_repaint"))
print("BODY", body.name, rpmat.name)

# ---- surface recipe (materials only)
NOTES = {}
for m in bpy.data.materials:
    if not m.use_nodes or not m.name.startswith("TheHive_Mat"):
        continue
    for nd in m.node_tree.nodes:
        if nd.type == 'MAP_RANGE':
            nd.inputs[4].default_value = 0.5           # moss on the crust at half strength (recipe _MossAlpha 0.5)
    NOTES[m.name] = "crust: _MossAlpha 0.5"

BRANCH_TINT = (0.17, 0.145, 0.115)
for m in {s.material for o in meshes for s in o.material_slots if s.material and "branch" in s.material.name.lower()}:
    b = m.node_tree.nodes.get("Principled BSDF")
    if b is None:
        continue
    if CFG["weather_branch"] and b.inputs["Base Color"].links:
        src = b.inputs["Base Color"].links[0].from_socket
        hs = m.node_tree.nodes.new("ShaderNodeHueSaturation"); hs.inputs["Saturation"].default_value = 0.2
        mx = m.node_tree.nodes.new("ShaderNodeMix"); mx.data_type = 'RGBA'; mx.blend_type = 'MULTIPLY'; mx.inputs[0].default_value = 1.0
        m.node_tree.links.new(src, hs.inputs["Color"]); m.node_tree.links.new(hs.outputs["Color"], mx.inputs[6])
        mx.inputs[7].default_value = (*BRANCH_TINT, 1); m.node_tree.links.new(mx.outputs[2], b.inputs["Base Color"])
        NOTES[m.name] = f"branch: saturation x0.2, then x{BRANCH_TINT} weathered grey-brown (pink pulled out)"
    b.inputs["Roughness"].default_value = 0.95
    b.inputs["Specular IOR Level"].default_value = 0.12          # matte dead wood (runtime _Glossiness ~0.05)
    b.inputs["Emission Strength"].default_value = 0.0
    NOTES[m.name] = NOTES.get(m.name, "branch") + "; matte (glossiness ~0.05), emission off"

# ---- add-ons into one collection so the base-only shot can hide them
col = bpy.data.collections.new("COL_addons"); sc.collection.children.link(col)
for o in meshes:
    if o is body:
        continue
    for c in list(o.users_collection):
        c.objects.unlink(o)
    col.objects.link(o)

# ---- final-look renders
fa = CFG["fa"]
views = (("front", fa % 360, 8, CFG["d"][0]), ("side", (fa + 90) % 360, 8, CFG["d"][1]),
         ("back", (fa + 180) % 360, 10, CFG["d"][2]), ("34", (fa + 40) % 360, 14, CFG["d"][3]))
G = {"hk": hk, "PREV": PREV}
FL.final_set(G, name_prefix="final", cen=CFG["cen"], views=views, head=CFG["head"], wtf=CFG["wtf"], branches=CFG["branches"],
             read10=CFG["read10"], scale=1.5, aim_z=CFG["cen"][2], body=body, rpmat=rpmat, col=col)

# ---- materials_recipe.json from the scene's actual materials
rec = {"_about": f"{KEY} STEP 3 (2026-11-22): material recipe per material (our COPIES of vanilla materials), read back from the "
                 "scene after step3_post.py. Colours are linear multipliers on the albedo; 'notes' say what step 3 changed.",
       "repaint": "see repaint/repaint.json + the masks in repaint/ (body _MainTex repainted at runtime)",
       "biome tint (ApplyBiomeVisuals)": "OWNER DECISION pending: previews/final_biome_blackforest_panel.png (left _Color only, right as coded)"}
for m in sorted({s.material for o in meshes for s in o.material_slots if s.material}, key=lambda x: x.name):
    if not m.use_nodes:
        continue
    b = m.node_tree.nodes.get("Principled BSDF")
    e = {"users": sum(1 for o in meshes if any(s.material == m for s in o.material_slots))}
    mults = [list(map(lambda x: round(x, 3), nd.inputs[7].default_value[:3])) for nd in m.node_tree.nodes
             if nd.type == 'MIX' and getattr(nd, "blend_type", "") == 'MULTIPLY' and not nd.inputs[7].links]
    if mults: e["albedo_multipliers"] = mults
    sats = [round(nd.inputs["Saturation"].default_value, 3) for nd in m.node_tree.nodes if nd.type == 'HUE_SAT']
    if sats: e["saturation"] = sats
    if b is not None:
        e["roughness"] = round(b.inputs["Roughness"].default_value, 3)
        e["emission_strength"] = round(b.inputs["Emission Strength"].default_value, 3)
    if m.name in NOTES: e["notes"] = NOTES[m.name]
    rec[m.name] = e
json.dump(rec, open(os.path.join(KIT, "materials_recipe.json"), "w"), indent=1)

bpy.ops.wm.save_as_mainfile(filepath=os.path.join(KIT, CFG["blend"].replace(".blend", "_step3.blend")), copy=True)
print("STEP3_POST DONE", KEY, "materials", len(rec) - 3)
