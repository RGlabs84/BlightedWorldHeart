"""donor_base.py - the REAL vanilla donor as the preview base (adapted from MagicRunicMod/unity/blender/armor_base_tex.py
and render_armor_previews.py, 2026-11-21).

The base is the donor's own skinned meshes in their prefab REST pose (the pose the game shows before animation; for the
Troll that is the bind pose turned 180 deg about Y, see ASSET-001 donor/donor_bones.json) with the game's own textures
(exported by export_donor_textures.py into <asset>/kit/ref/, game data, never shipped). It is NOT modified and NOT shipped:
at runtime the sub-boss is the cloned vanilla creature.

Frame: Blender metres, x = Unity x, y = Unity z (creature forward), z = Unity y (up); root at the origin, feet on z = 0.
"""
import json
import math
import os

import bpy
import numpy as np
from mathutils import Vector, Matrix
from mathutils.bvhtree import BVHTree


def u2b(v):
    return Vector((v[0], v[2], v[1]))


def srgb2lin(c):
    return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4


# ---------------------------------------------------------------- donor data
class Donor:
    def __init__(self, asset_dir, ref_dir):
        self.dir = os.path.join(asset_dir, "donor")
        self.ref = ref_dir
        self.info = json.load(open(os.path.join(self.dir, "donor_bones.json")))
        self.mats = json.load(open(os.path.join(ref_dir, "materials.json")))
        self.T = {t["name"]: t for t in self.info["transforms"]}

    def mesh_data(self, name):
        """(verts_blender, tris (Blender winding), uv0) of a renderer, in the prefab REST pose"""
        m = json.load(open(os.path.join(self.dir, f"donor_mesh_{name}.json")))
        vs = m["verts_rest_world"] or m["verts_bind_world"]
        V = [u2b(v) for v in vs]
        F = [(t[0], t[2], t[1]) for t in m["tris"]]        # Unity left-handed winding -> Blender (the axis swap mirrors)
        return V, F, m["uv0"], m

    # bone frames (Unity), from the local TRS chain with the creature root dropped (it is parked at y=50)
    def _trs(self, t):
        x, y, z, w = t["local_rot_xyzw"]; s = t["local_scale"]; p = t["local_pos"]
        R = np.array([[1 - 2 * (y * y + z * z), 2 * (x * y - z * w), 2 * (x * z + y * w)],
                      [2 * (x * y + z * w), 1 - 2 * (x * x + z * z), 2 * (y * z - x * w)],
                      [2 * (x * z - y * w), 2 * (y * z + x * w), 1 - 2 * (x * x + y * y)]])
        M = np.eye(4); M[:3, :3] = R @ np.diag(s); M[:3, 3] = p
        return M

    def bone_world_u(self, name):
        t = self.T[name]
        if t["parent"] is None:
            return np.eye(4)
        return self.bone_world_u(t["parent"]) @ self._trs(t)

    def bone_pos_b(self, name):
        return u2b(self.T[name]["world_pos"])

    def tex_path(self, prop):
        m = list(self.mats["materials"].values())[0]
        return os.path.join(self.ref, m["textures"][prop]["png"]), m


def base_material(donor, name="TrollBase", tint=None, normal_strength=0.6):
    """The donor material as the game draws it (approximately): _MainTex x _Color, its normal map (AG-packed DXT5nm,
    unpacked here), cutout alpha, gloss -> roughness. tint: the Heart's _Color replacement (already linear)."""
    m = bpy.data.materials.get(name)
    if m:
        return m
    albedo_png, info = donor.tex_path("_MainTex")
    normal_png, _ = donor.tex_path("_BumpMap")
    col = info["colors"].get("_Color", [1, 1, 1, 1])
    mult = tint if tint is not None else tuple(srgb2lin(c) for c in col[:3])   # Unity SetColor values are sRGB
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    nt = m.node_tree
    b = nt.nodes["Principled BSDF"]
    ti = nt.nodes.new("ShaderNodeTexImage"); ti.image = bpy.data.images.load(albedo_png, check_existing=True)
    mul = nt.nodes.new("ShaderNodeMix"); mul.data_type = 'RGBA'; mul.blend_type = 'MULTIPLY'; mul.inputs[0].default_value = 1.0
    nt.links.new(ti.outputs["Color"], mul.inputs[6]); mul.inputs[7].default_value = (*mult, 1)
    nt.links.new(mul.outputs[2], b.inputs["Base Color"])
    # cutout (Mode 1, _Cutoff)
    cut = info["floats"].get("_Cutoff", 0.29)
    gt = nt.nodes.new("ShaderNodeMath"); gt.operation = 'GREATER_THAN'; gt.inputs[1].default_value = cut
    nt.links.new(ti.outputs["Alpha"], gt.inputs[0]); nt.links.new(gt.outputs[0], b.inputs["Alpha"])
    try:
        m.surface_render_method = 'DITHERED'
    except Exception:
        pass
    # normal map: unpack DXT5nm (x = A, y = G) into a proper RGB normal image
    nimg = unpacked_normal(normal_png)
    tn = nt.nodes.new("ShaderNodeTexImage"); tn.image = nimg; nimg.colorspace_settings.name = 'Non-Color'
    nm = nt.nodes.new("ShaderNodeNormalMap"); nm.inputs["Strength"].default_value = normal_strength
    nt.links.new(tn.outputs["Color"], nm.inputs["Color"]); nt.links.new(nm.outputs["Normal"], b.inputs["Normal"])
    b.inputs["Roughness"].default_value = 1.0 - info["floats"].get("_Glossiness", 0.24)
    m.use_backface_culling = False
    return m


def unpacked_normal(path):
    name = os.path.basename(path).replace(".png", "_rgb")
    if name in bpy.data.images:
        return bpy.data.images[name]
    src = bpy.data.images.load(path, check_existing=True)
    w, h = src.size
    a = np.empty(w * h * 4, dtype=np.float32); src.pixels.foreach_get(a); a = a.reshape(h, w, 4)
    x = a[..., 3] * 2 - 1; y = a[..., 1] * 2 - 1
    z = np.sqrt(np.clip(1 - x * x - y * y, 0, 1))
    out = np.stack([x * 0.5 + 0.5, y * 0.5 + 0.5, z * 0.5 + 0.5, np.ones_like(x)], -1)
    img = bpy.data.images.new(name, w, h, alpha=False, float_buffer=False)
    img.colorspace_settings.name = 'Non-Color'
    img.pixels.foreach_set(out.astype(np.float32).ravel())
    img.pack()
    return img


def add_base(donor, hair=True, material=None, collection=None, names=None):
    """The donor's Body (+ Hair) as Blender objects with UV0 and the game material (names: the renderers to add, e.g. ("M",)
    for the Wolf; default Troll Body/Hair)"""
    col = collection or bpy.context.scene.collection
    obs = []
    for nm in (names or (("Body", "Hair") if hair else ("Body",))):
        V, F, uv, _ = donor.mesh_data(nm)
        me = bpy.data.meshes.new("Base_" + nm)
        me.from_pydata([tuple(v) for v in V], [], F)
        me.update()
        uvl = me.uv_layers.new(name="UV0")
        for loop in me.loops:
            u = uv[loop.vertex_index]
            uvl.data[loop.index].uv = (u[0], u[1])
        for p in me.polygons:
            p.use_smooth = True
        me.materials.append(material or base_material(donor))
        ob = bpy.data.objects.new("Base_" + nm, me)
        col.objects.link(ob)
        obs.append(ob)
    return obs


def base_bvh(donor, names=("Body",)):
    vs, fs = [], []
    for nm in names:
        V, F, _, _ = donor.mesh_data(nm)
        o = len(vs)
        vs += [tuple(v) for v in V]
        fs += [tuple(i + o for i in t) for t in F]
    return BVHTree.FromPolygons(vs, fs), vs, fs


# ---------------------------------------------------------------- Runic-style lighting (render_armor_previews.py), x4 scale
BG = (0.045, 0.047, 0.052)


def lights_and_world(scale=4.0, aim=(0, 0, 4.0)):
    """Runic's key/fill/rim area rig on a near-black background, scaled for a creature `scale` times a player.
    Runic's figure faces -Y; ours faces +Y, so the rig is mirrored in y."""
    sc = bpy.context.scene
    w = bpy.data.worlds.new("w"); sc.world = w; w.use_nodes = True
    w.node_tree.nodes["Background"].inputs[0].default_value = (*BG, 1)
    w.node_tree.nodes["Background"].inputs[1].default_value = 1.0
    tgt = bpy.data.objects.new("aim", None); sc.collection.objects.link(tgt); tgt.location = aim
    for name, loc, energy, size, colr in (("key", (-2.2, 2.6, 3.0), 240, 1.6, (1.0, 0.97, 0.92)),
                                          ("fill", (2.6, 2.0, 1.6), 55, 2.5, (0.88, 0.92, 1.0)),
                                          ("rim", (0.6, -3.0, 2.8), 260, 1.2, (0.95, 0.97, 1.0))):
        L = bpy.data.lights.new(name, 'AREA'); L.energy = energy * scale * scale; L.size = size * scale; L.color = colr
        o = bpy.data.objects.new(name, L); sc.collection.objects.link(o)
        o.location = Vector(loc) * scale + Vector((0, 0, aim[2] - 1.3 * scale))
        tc = o.constraints.new('TRACK_TO'); tc.target = tgt
    return tgt


def setup_render(w, h):
    sc = bpy.context.scene
    for e in ("BLENDER_EEVEE_NEXT", "BLENDER_EEVEE"):
        try:
            sc.render.engine = e; break
        except TypeError:
            pass
    sc.render.resolution_x, sc.render.resolution_y = w, h
    sc.render.film_transparent = False
    sc.view_settings.view_transform = 'Standard'
    sc.view_settings.look = 'None'
    try:
        sc.eevee.taa_render_samples = 32
    except AttributeError:
        pass


def camera(target, dist, az_deg, el_deg, lens=85, ortho=None):
    """az 0 = in front of the creature (which faces +Y), positive = toward the creature's left (-X)"""
    sc = bpy.context.scene
    cam = sc.camera
    if cam is None:
        cam = bpy.data.objects.new("cam", bpy.data.cameras.new("cam")); sc.collection.objects.link(cam); sc.camera = cam
    az, el = math.radians(az_deg), math.radians(el_deg)
    d = Vector((-math.sin(az) * math.cos(el), math.cos(az) * math.cos(el), math.sin(el)))
    cam.location = Vector(target) + d * dist
    cam.rotation_euler = (Vector(target) - cam.location).normalized().to_track_quat('-Z', 'Y').to_euler()
    if ortho:
        cam.data.type = 'ORTHO'; cam.data.ortho_scale = ortho
    else:
        cam.data.type = 'PERSP'; cam.data.lens = lens
    cam.data.clip_end = 500
    return cam


def render(path):
    bpy.context.scene.render.filepath = path
    bpy.ops.render.render(write_still=True)


def weld_normals(me, digits=4):
    """smooth shading across UV/material seams: the vanilla mesh is split there (duplicate vertices), and Blender's computed
    normals then break along the split (the sternum 'seam' in the previews). Unity uses the mesh's own smooth normals, so the
    preview averages the normals of coincident vertices into custom normals (preview only)."""
    import numpy as _np
    co = _np.array([v.co[:] for v in me.vertices]); nr = _np.array([v.normal[:] for v in me.vertices])
    key = {}
    for i, c in enumerate(co):
        key.setdefault(tuple(_np.round(c, digits)), []).append(i)
    out = nr.copy()
    for ids in key.values():
        if len(ids) > 1:
            n = nr[ids].sum(0); n /= (_np.linalg.norm(n) + 1e-9); out[ids] = n
    me.normals_split_custom_set_from_vertices([tuple(n) for n in out])
