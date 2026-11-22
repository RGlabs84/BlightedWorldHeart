"""vanilla_kit.py - vanilla Valheim parts (exported by export_vanilla_parts.py) as Blender objects in their REAL materials,
for kitbash previews. Game data stays in <asset>/kit/vanilla_ref/ (reference only, never shipped).

Material approximation of Valheim's shaders (Custom/Creature, Custom/Vegetation, Standard-like):
  base = _MainTex x _Color (Unity colours are sRGB -> linear), normal = _BumpMap (AG-packed DXT5nm, unpacked),
  emission = (_EmissionMap or _EmissiveTex) x _EmissionColor (HDR, linear-ish), cutout alpha for _Mode 1/3 materials,
  moss (Custom/Vegetation's _MossTex) blended onto upward-facing surfaces when _MossAlpha > 0, roughness = 1 - _Glossiness.
Frame: Unity mesh space -> Blender (x, z, y); the triangle winding is swapped for the axis mirror.
"""
import json, os, math
import bpy
from mathutils import Vector, Matrix
import numpy as np
import donor_base as DB

U2B = Matrix(((1, 0, 0, 0), (0, 0, 1, 0), (0, 1, 0, 0), (0, 0, 0, 1)))       # Unity (x,y,z) -> Blender (x,z,y); self-inverse


class Parts:
    def __init__(self, ref_dir, hive_ref_dir=None):
        self.dir = ref_dir
        self.hive_ref = hive_ref_dir
        self.cache = {}

    def data(self, key):
        if key not in self.cache:
            self.cache[key] = json.load(open(os.path.join(self.dir, key + ".json")))
        return self.cache[key]

    def tex(self, png):
        return os.path.join(self.dir, "tex", png)

    def mesh(self, key, prefab_space=True, name=None):
        """the part as a Blender mesh datablock: vertices in Blender metres, in the prefab's space (as the game places it)
        or raw mesh space"""
        d = self.data(key)
        Mw = np.array(d["world_matrix_in_prefab"]) if prefab_space else np.eye(4)
        V = np.c_[np.array(d["verts"]), np.ones(len(d["verts"]))] @ Mw.T
        verts = [(v[0], v[2], v[1]) for v in V[:, :3]]
        faces, mats = [], []
        for si, sm in enumerate(d["submeshes"]):
            for t in sm:
                faces.append((t[0], t[2], t[1])); mats.append(si)
        me = bpy.data.meshes.new(name or d["mesh"])
        me.from_pydata(verts, [], faces)
        me.update()
        if d["uv0"]:
            uvl = me.uv_layers.new(name="UV0")
            uv = d["uv0"]
            for loop in me.loops:
                u = uv[loop.vertex_index]
                uvl.data[loop.index].uv = (u[0], u[1])
        for p, mi in zip(me.polygons, mats):
            p.material_index = mi
            p.use_smooth = True
        for m in d["materials"]:
            me.materials.append(self.material(m))
        return me

    def material(self, m):
        name = "V_" + m["name"] + "_" + str(m.get("path_id", ""))[-6:]
        if name in bpy.data.materials:
            return bpy.data.materials[name]
        mat = bpy.data.materials.new(name)
        mat.use_nodes = True
        nt = mat.node_tree
        b = nt.nodes["Principled BSDF"]
        T = m["textures"]; C = m["colors"]; F = m["floats"]
        col = C.get("_Color", [1, 1, 1, 1])
        lin = [DB.srgb2lin(c) for c in col[:3]]
        base_out = None
        if "_MainTex" in T and not T["_MainTex"]["png"].startswith("ERR"):
            ti = nt.nodes.new("ShaderNodeTexImage"); ti.image = bpy.data.images.load(self.tex(T["_MainTex"]["png"]), check_existing=True)
            mul = nt.nodes.new("ShaderNodeMix"); mul.data_type = 'RGBA'; mul.blend_type = 'MULTIPLY'; mul.inputs[0].default_value = 1.0
            nt.links.new(ti.outputs["Color"], mul.inputs[6]); mul.inputs[7].default_value = (*lin, 1)
            base_out = mul.outputs[2]
            if F.get("_Mode", 0) in (1.0, 3.0):           # cutout / foliage
                gt = nt.nodes.new("ShaderNodeMath"); gt.operation = 'GREATER_THAN'; gt.inputs[1].default_value = F.get("_Cutoff", 0.5)
                nt.links.new(ti.outputs["Alpha"], gt.inputs[0]); nt.links.new(gt.outputs[0], b.inputs["Alpha"])
                try:
                    mat.surface_render_method = 'DITHERED'
                except Exception:
                    pass
        else:
            b.inputs["Base Color"].default_value = (*lin, 1)
        if base_out is not None and "_MossTex" in T and F.get("_MossAlpha", 0) > 0:
            tm = nt.nodes.new("ShaderNodeTexImage"); tm.image = bpy.data.images.load(self.tex(T["_MossTex"]["png"]), check_existing=True)
            mc = C.get("_MossColor", [1, 1, 1, 1])
            mm = nt.nodes.new("ShaderNodeMix"); mm.data_type = 'RGBA'; mm.blend_type = 'MULTIPLY'; mm.inputs[0].default_value = 1.0
            nt.links.new(tm.outputs["Color"], mm.inputs[6]); mm.inputs[7].default_value = (*[DB.srgb2lin(c) for c in mc[:3]], 1)
            geo = nt.nodes.new("ShaderNodeNewGeometry")
            sep = nt.nodes.new("ShaderNodeSeparateXYZ"); nt.links.new(geo.outputs["Normal"], sep.inputs[0])
            ramp = nt.nodes.new("ShaderNodeMapRange"); ramp.inputs[1].default_value = 0.35; ramp.inputs[2].default_value = 0.75
            nt.links.new(sep.outputs["Z"], ramp.inputs[0])
            mix = nt.nodes.new("ShaderNodeMix"); mix.data_type = 'RGBA'
            nt.links.new(ramp.outputs[0], mix.inputs[0]); nt.links.new(base_out, mix.inputs[6]); nt.links.new(mm.outputs[2], mix.inputs[7])
            base_out = mix.outputs[2]
        if base_out is not None:
            nt.links.new(base_out, b.inputs["Base Color"])
        if "_BumpMap" in T and not T["_BumpMap"]["png"].startswith("ERR"):
            nimg = DB.unpacked_normal(self.tex(T["_BumpMap"]["png"]))
            tn = nt.nodes.new("ShaderNodeTexImage"); tn.image = nimg
            nm = nt.nodes.new("ShaderNodeNormalMap"); nm.inputs["Strength"].default_value = 0.7 * F.get("_BumpScale", 1.0)
            nt.links.new(tn.outputs["Color"], nm.inputs["Color"]); nt.links.new(nm.outputs["Normal"], b.inputs["Normal"])
        em = C.get("_EmissionColor", [0, 0, 0, 1])
        etex = T.get("_EmissionMap") or T.get("_EmissiveTex")
        if max(em[:3]) > 0.01:
            if etex and not etex["png"].startswith("ERR"):
                te = nt.nodes.new("ShaderNodeTexImage"); te.image = bpy.data.images.load(self.tex(etex["png"]), check_existing=True)
                nt.links.new(te.outputs["Color"], b.inputs["Emission Color"])
                s = max(em[:3])
                b.inputs["Emission Strength"].default_value = s
                # tint the emission by the colour's hue
                mixe = nt.nodes.new("ShaderNodeMix"); mixe.data_type = 'RGBA'; mixe.blend_type = 'MULTIPLY'; mixe.inputs[0].default_value = 1.0
                nt.links.new(te.outputs["Color"], mixe.inputs[6]); mixe.inputs[7].default_value = (em[0] / s, em[1] / s, em[2] / s, 1)
                nt.links.new(mixe.outputs[2], b.inputs["Emission Color"])
            else:
                s = max(em[:3])
                b.inputs["Emission Color"].default_value = (em[0] / s, em[1] / s, em[2] / s, 1)
                b.inputs["Emission Strength"].default_value = s
        b.inputs["Roughness"].default_value = 1.0 - F.get("_Glossiness", 0.2)
        mat.use_backface_culling = False
        return mat

    def hive_material(self, which):
        """TheHive_Eye / TheHive_Mat_legs from the Hive reference export (art/subbosses/reference, hive.json)"""
        name = "V_" + which
        if name in bpy.data.materials:
            return bpy.data.materials[name]
        hj = json.load(open(os.path.join(self.hive_ref, "hive.json")))["materials"][which]
        m = {"name": which, "path_id": "", "textures": {}, "colors": hj["colors"], "floats": {"_Glossiness": 0.2}}
        old = self.dir
        self.dir = self.hive_ref
        try:
            for k, png in hj["textures"].items():
                if k in ("_MainTex", "_BumpMap", "_MossTex"):
                    m["textures"][k] = {"png": png}
            if which == "TheHive_Mat_legs":
                m["floats"]["_MossAlpha"] = 1.0
            # the reference PNGs sit in the folder itself, not in tex/
            mat = self._material_flat(m)
        finally:
            self.dir = old
        return mat

    def _material_flat(self, m):
        tex_backup = self.tex
        self.tex = lambda png: os.path.join(self.dir, png)
        try:
            return self.material(m)
        finally:
            self.tex = tex_backup


def builtin_cube(name, mat):
    """Unity's built-in Cube (12 tris, unit size): what TheHive's timber legs and ring are made of"""
    bpy.ops.mesh.primitive_cube_add(size=1.0)
    ob = bpy.context.active_object
    me = ob.data
    me.name = name
    bpy.data.objects.remove(ob)
    me.materials.clear(); me.materials.append(mat)
    for p in me.polygons:
        p.use_smooth = False
    return me
