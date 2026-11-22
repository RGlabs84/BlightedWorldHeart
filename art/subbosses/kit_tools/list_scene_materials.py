"""list_scene_materials.py - every material the APPROVED kit scenes put on their parts, with the node values that matter for the
runtime material table (Principled base colour / roughness / emission, image names, MIX multipliers, hue-saturation).

Run: heavy.sh 4G <label> blender -b --factory-startup -P list_scene_materials.py -- <abs out json>
"""
import bpy, os, sys, json

SUB = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = sys.argv[sys.argv.index("--") + 1]
SCENES = {
    "BlightedSB_HiveBrute": "ASSET-001_HiveBrute/kit/HiveBrute_kitbash.blend",
    "BlightedSB_Rootstalker": "ASSET-002_Rootstalker/kit/Rootstalker_kitbash.blend",
    "BlightedSB_Gorgemaw": "ASSET-003_Gorgemaw/kit/Gorgemaw_kitbash.blend",
    "BlightedSB_EyeblightSeer": "ASSET-004_EyeblightSeer/kit/EyeblightSeer_kitbash_step3.blend",
    "BlightedSB_BarkboundHusk": "ASSET-005_BarkboundHusk/kit/BarkboundHusk_kitbash_step3.blend",
    "BlightedSB_Broodhusk": "ASSET-006_Broodhusk/kit/Broodhusk_kitbash_step3.blend",
}


def val(sock):
    if sock is None or not hasattr(sock, "default_value"):
        return None
    v = sock.default_value
    try:
        return [round(float(x), 4) for x in v]
    except TypeError:
        return round(float(v), 4)


def describe(m):
    d = {"nodes": []}
    if not m.use_nodes:
        return d
    for nd in m.node_tree.nodes:
        e = {"type": nd.type, "name": nd.name}
        if nd.type == "BSDF_PRINCIPLED":
            for k in ("Base Color", "Roughness", "Specular IOR Level", "Emission Color", "Emission Strength", "Alpha"):
                if k in nd.inputs:
                    e[k] = val(nd.inputs[k]); e[k + " linked"] = nd.inputs[k].is_linked
        elif nd.type == "TEX_IMAGE":
            e["image"] = nd.image.name if nd.image else None
        elif nd.type in ("MIX", "MIX_RGB"):
            e["blend"] = getattr(nd, "blend_type", None)
            e["inputs"] = {s.name + str(i): val(s) for i, s in enumerate(nd.inputs) if not s.is_linked and val(s) is not None}
        elif nd.type in ("HUE_SAT", "BRIGHTCONTRAST", "MAP_RANGE", "RGB", "VALUE", "MATH", "VERTEX_COLOR", "ATTRIBUTE"):
            e["inputs"] = {s.name + str(i): val(s) for i, s in enumerate(nd.inputs) if not s.is_linked and val(s) is not None}
            if nd.type == "RGB": e["value"] = val(nd.outputs[0])
            if nd.type == "MATH": e["op"] = nd.operation
            if nd.type in ("VERTEX_COLOR", "ATTRIBUTE"): e["attr"] = getattr(nd, "layer_name", None) or getattr(nd, "attribute_name", None)
        else:
            continue
        d["nodes"].append(e)
    return d


out = {}
for kid, rel in SCENES.items():
    bpy.ops.wm.open_mainfile(filepath=os.path.join(SUB, rel))
    users = {}
    for ob in bpy.data.objects:
        if ob.type != "MESH":
            continue
        for s in ob.material_slots:
            if s.material:
                users.setdefault(s.material.name, []).append(ob.name)
    out[kid] = {name: {"users": len(obs), "objects": sorted(obs)[:6], **describe(bpy.data.materials[name])}
                for name, obs in sorted(users.items())}
    print("SCENE", kid, len(users), "materials")
json.dump(out, open(OUT, "w"), indent=1)
print("WROTE", OUT)
