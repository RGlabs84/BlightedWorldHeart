"""hivefit: Blender helpers for the Runic-method sub-boss kits (BlightedHeart, owner METHOD 2026-11-21).

Adapted from MagicRunicMod/unity/blender (render_armor_previews.py lights/camera, armor_base_tex.py textured base,
make_armor.py fit_grid ray-fitting and overlaps()) for creature donors. Runic's files are not edited.

- load_base(): the REAL vanilla skinned body in its bind pose with its game textures (albedo sRGB with the material's
  alpha cut-out, the AG-packed normal map decoded to RGB, the emission map x _EmissionColor). Never shipped.
- regions: body triangles grouped by their dominant bone, so a plate is fitted against the torso without its rays
  hitting a hanging arm first.
- fit_grid(): radius per (t, angle) = first body hit along a ray toward the axis + clearance (Runic fit_grid, simplified:
  holes filled from neighbours, one smoothing pass that never lowers a value).
- measure(): add-on / base intersecting triangle pairs (BVH overlap, as Runic's overlaps()), signed clearance of the add-on
  vertices from the body (min, median of the contact band), and floating pieces.
- Runic preview lighting (dark background, key / fill / rim area lights), EEVEE.
Frames: Blender x/y/z = Unity x/z/y. Draugr-like donors whose bind pose faces -Y use Runic's camera convention
(az 0 = in front at -Y).
"""
import bpy, bmesh, math, os, json, random
import numpy as np
from mathutils import Vector, Matrix
from mathutils.bvhtree import BVHTree


def u2b(v): return Vector((v[0], v[2], v[1]))


def m_u2b(M):
    """a Unity 4x4 (numpy/list) -> the same transform expressed in Blender axes."""
    P = Matrix(((1, 0, 0, 0), (0, 0, 1, 0), (0, 1, 0, 0), (0, 0, 0, 1)))
    return P @ Matrix(M) @ P


def decode_normal(src, dst):
    """AG-packed (R=255, G=y, A=x) -> an RGB tangent normal PNG (Runic lesson 30 / UNITY-ASSET-TOOLS TRAPS)."""
    img = bpy.data.images.load(src); w, h = img.size
    a = np.empty(w * h * 4, np.float32); img.pixels.foreach_get(a); a = a.reshape(h, w, 4)
    x = a[..., 3] * 2 - 1; y = a[..., 1] * 2 - 1; z = np.sqrt(np.clip(1 - x * x - y * y, 0, 1))
    out = np.stack([x * 0.5 + 0.5, y * 0.5 + 0.5, z * 0.5 + 0.5, np.ones_like(x)], -1).astype(np.float32)
    im = bpy.data.images.new(os.path.basename(dst), w, h, alpha=True); im.pixels.foreach_set(out.ravel())
    im.filepath_raw = dst; im.file_format = 'PNG'; im.save(); bpy.data.images.remove(img)
    return dst


def srgb2lin(c): return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4


def base_material(J, refdir, name="BaseMat", tint=None, emit_tint=None):
    """the donor's material as the game draws it (Custom/Creature-like): _MainTex * _Color, alpha cut-out at _Cutoff,
    normal map, _EmissionMap * _EmissionColor. tint: a linear multiplier on the albedo (biome _Color via SetColor)."""
    mi = J["material"]
    m = bpy.data.materials.new(name); m.use_nodes = True
    nt = m.node_tree; b = nt.nodes["Principled BSDF"]
    tex = nt.nodes.new("ShaderNodeTexImage"); tex.image = bpy.data.images.load(os.path.join(refdir, mi["textures"]["_MainTex"]["png"]), check_existing=True)
    col = mi["colors"].get("_Color", [1, 1, 1, 1])
    mul = nt.nodes.new("ShaderNodeMix"); mul.data_type = 'RGBA'; mul.blend_type = 'MULTIPLY'; mul.inputs[0].default_value = 1.0
    t = tint or (1, 1, 1)
    mul.inputs[7].default_value = (col[0] * t[0], col[1] * t[1], col[2] * t[2], 1)
    nt.links.new(tex.outputs["Color"], mul.inputs[6]); nt.links.new(mul.outputs[2], b.inputs["Base Color"])
    # alpha cut-out (hair and beard strands): alpha > _Cutoff
    cut = mi["floats"].get("_Cutoff", 0.5)
    gt = nt.nodes.new("ShaderNodeMath"); gt.operation = 'GREATER_THAN'; gt.inputs[1].default_value = cut
    nt.links.new(tex.outputs["Alpha"], gt.inputs[0]); nt.links.new(gt.outputs[0], b.inputs["Alpha"])
    try: m.surface_render_method = 'DITHERED'
    except Exception: pass
    try: m.blend_method = 'CLIP'
    except Exception: pass
    if "_BumpMap" in mi["textures"]:
        npng = os.path.join(refdir, "_decoded_" + mi["textures"]["_BumpMap"]["png"])
        if not os.path.exists(npng): decode_normal(os.path.join(refdir, mi["textures"]["_BumpMap"]["png"]), npng)
        nt_ = nt.nodes.new("ShaderNodeTexImage"); nt_.image = bpy.data.images.load(npng, check_existing=True); nt_.image.colorspace_settings.name = 'Non-Color'
        nm = nt.nodes.new("ShaderNodeNormalMap"); nt.links.new(nt_.outputs["Color"], nm.inputs["Color"]); nt.links.new(nm.outputs["Normal"], b.inputs["Normal"])
    if "_EmissionMap" in mi["textures"]:
        et = nt.nodes.new("ShaderNodeTexImage"); et.image = bpy.data.images.load(os.path.join(refdir, mi["textures"]["_EmissionMap"]["png"]), check_existing=True)
        ec = emit_tint or mi["colors"].get("_EmissionColor", [0, 0, 0, 1])[:3]
        k = max(ec) or 1.0
        em = nt.nodes.new("ShaderNodeMix"); em.data_type = 'RGBA'; em.blend_type = 'MULTIPLY'; em.inputs[0].default_value = 1.0
        em.inputs[7].default_value = (ec[0] / k, ec[1] / k, ec[2] / k, 1)
        nt.links.new(et.outputs["Color"], em.inputs[6]); nt.links.new(em.outputs[2], b.inputs["Emission Color"])
        b.inputs["Emission Strength"].default_value = min(k, 4.0)
    b.inputs["Roughness"].default_value = 1.0 - mi["floats"].get("_Glossiness", 0.1)
    b.inputs["Metallic"].default_value = mi["floats"].get("_Metallic", 0.0)
    return m


def load_base(refdir, name="Base", tint=None, emit_tint=None):
    """-> (object, J, region_of_tri list, dominant bone per vertex)."""
    J = json.load(open(os.path.join(refdir, "base.json")))
    vs = [u2b(v) for v in J["verts"]]
    fs = [list(reversed(t)) for t in J["tris"]]          # handedness flip
    me = bpy.data.meshes.new(name); me.from_pydata(vs, [], fs); me.update()
    if J["uv0"]:
        uv = me.uv_layers.new(name="UVMap")
        for poly in me.polygons:
            for li in poly.loop_indices:
                vi = me.loops[li].vertex_index
                uv.data[li].uv = J["uv0"][vi]
    for p in me.polygons: p.use_smooth = True
    ob = bpy.data.objects.new(name, me); bpy.context.scene.collection.objects.link(ob)
    me.materials.append(base_material(J, refdir, name + "Mat", tint=tint, emit_tint=emit_tint))
    W = np.array(J["weights"]); I = np.array(J["indices"])
    dom = [J["bone_names"][I[i][int(np.argmax(W[i]))]] for i in range(len(W))]
    return ob, J, dom


def region_of(bone):
    if bone in ("Head",): return "head"
    if bone.startswith("Left") and any(k in bone for k in ("Arm", "Hand")): return "armL"
    if bone.startswith("Right") and any(k in bone for k in ("Arm", "Hand")): return "armR"
    if bone.startswith("Left") and any(k in bone for k in ("Leg", "Foot", "UpLeg")): return "legL"
    if bone.startswith("Right") and any(k in bone for k in ("Leg", "Foot", "UpLeg")): return "legR"
    return "torso"


def region_bvhs(ob, dom):
    me = ob.data
    vs = [v.co.copy() for v in me.vertices]
    groups = {}
    for p in me.polygons:
        rs = [region_of(dom[i]) for i in p.vertices]
        r = max(set(rs), key=rs.count)
        groups.setdefault(r, []).append(list(p.vertices))
    out = {r: BVHTree.FromPolygons(vs, fs) for r, fs in groups.items()}
    out["all"] = BVHTree.FromPolygons(vs, [list(p.vertices) for p in me.polygons])
    return out


def bone_frames(J):
    """bone name -> (Blender bind world 4x4)."""
    return {n: m_u2b(M) for n, M in zip(J["bone_names"], J["bone_bind_world"])}


def node_pos(J, name):
    """a non-skinned node's bind position: its prefab position shifted by its nearest skinned ancestor's bind-prefab offset."""
    nodes = J["nodes"]; names = J["bone_names"]
    a = name
    while a is not None and a not in names: a = nodes[a]["parent"]
    p = Vector(np.array(nodes[name]["world"])[:3, 3])
    if a is not None:
        i = names.index(a)
        p = p + Vector(np.array(J["bone_bind_world"][i])[:3, 3]) - Vector(np.array(J["bone_prefab_world"][i])[:3, 3])
    return u2b(p)


# ------------------------------------------------------------------ fitting
def fit_grid(bvh, origin, axis, ref, t0, t1, a0, a1, nu, nv, clear, start_r=0.7, default=None):
    """r[i][j] at t = t0..t1 (metres along axis), angle a0..a1 (0 = ref, +90 deg = axis x ref... side = axis.cross(ref)).
    r = first hit of a ray from start_r toward the axis, + clear. Misses are filled from neighbours (or default)."""
    ax = Vector(axis).normalized(); r0 = Vector(ref); r0 = (r0 - ax * r0.dot(ax)).normalized(); side = ax.cross(r0)
    R = [[None] * (nv + 1) for _ in range(nu + 1)]
    for i in range(nu + 1):
        for j in range(nv + 1):
            ang = a0 + (a1 - a0) * i / nu; t = t0 + (t1 - t0) * j / nv
            c = Vector(origin) + ax * t; d = r0 * math.cos(ang) + side * math.sin(ang)
            loc, n, idx, dist = bvh.ray_cast(c + d * start_r, -d, start_r)
            if loc is not None: R[i][j] = start_r - dist + clear
    for _ in range(4):
        for i in range(nu + 1):
            for j in range(nv + 1):
                if R[i][j] is None:
                    nb = [R[ii][jj] for ii in (i - 1, i, i + 1) for jj in (j - 1, j, j + 1)
                          if 0 <= ii <= nu and 0 <= jj <= nv and R[ii][jj] is not None]
                    if nb: R[i][j] = max(nb)
    for i in range(nu + 1):
        for j in range(nv + 1):
            if R[i][j] is None: R[i][j] = default if default is not None else start_r * 0.5
    S = [[0.0] * (nv + 1) for _ in range(nu + 1)]
    for i in range(nu + 1):
        for j in range(nv + 1):
            nb = [R[ii][jj] for ii in (i - 1, i, i + 1) for jj in (j - 1, j, j + 1) if 0 <= ii <= nu and 0 <= jj <= nv]
            S[i][j] = max(R[i][j], sum(nb) / len(nb))      # never lower than the own need
    return S


def grid_fn(S, nu, nv):
    """bilinear lookup S(u, v) for u, v in [0, 1] (clamped)."""
    def f(u, v):
        u = min(max(u, 0.0), 1.0) * nu; v = min(max(v, 0.0), 1.0) * nv
        i = min(int(u), nu - 1); j = min(int(v), nv - 1); fu, fv = u - i, v - j
        return (S[i][j] * (1 - fu) * (1 - fv) + S[i + 1][j] * fu * (1 - fv) + S[i][j + 1] * (1 - fu) * fv + S[i + 1][j + 1] * fu * fv)
    return f


# ------------------------------------------------------------------ measuring
def piece_bvh(bms):
    tmp = bmesh.new()
    for b in bms:
        me = bpy.data.meshes.new("tmp"); b.to_mesh(me); tmp.from_mesh(me); bpy.data.meshes.remove(me)
    vs = [v.co.copy() for v in tmp.verts]; fs = [[v.index for v in f.verts] for f in tmp.faces]
    tmp.free()
    return BVHTree.FromPolygons(vs, fs), vs


def measure(bms, body_bvh, others=None):
    """-> dict: intersecting triangle pairs with the base, signed clearance stats, floating flag."""
    mine, vs = piece_bvh(bms)
    pairs = len(mine.overlap(body_bvh))
    d_signed = []
    for p in vs:
        loc, n, idx, dist = body_bvh.find_nearest(p)
        if loc is None: continue
        s = dist if (p - loc).dot(n) >= 0 else -dist
        d_signed.append(s)
    d_signed.sort()
    contact = [x for x in d_signed if -0.02 < x < 0.05]
    mind = min((abs(x) for x in d_signed), default=None)
    touching_other = False
    if others is not None:
        for p in vs[::3]:
            loc, n, idx, dist = others.find_nearest(p)
            if loc is not None and dist < 0.006: touching_other = True; break
    return {"base_pairs": pairs, "min_signed_mm": round(d_signed[0] * 1000, 1) if d_signed else None,
            "verts_inside_base": sum(1 for x in d_signed if x < -0.001),
            "contact_median_mm": round(contact[len(contact) // 2] * 1000, 1) if contact else None,
            "nearest_mm": round(mind * 1000, 1) if mind is not None else None,
            "floating": bool(mind is not None and mind > 0.012 and not touching_other)}


# ------------------------------------------------------------------ Runic preview lighting / camera (render_armor_previews.py)
BG = (0.045, 0.047, 0.052)


def setup_eevee(w, h):
    sc = bpy.context.scene
    for e in ("BLENDER_EEVEE_NEXT", "BLENDER_EEVEE"):
        try: sc.render.engine = e; break
        except TypeError: pass
    sc.render.resolution_x, sc.render.resolution_y = w, h
    sc.render.film_transparent = False
    sc.view_settings.view_transform = 'Standard'; sc.view_settings.look = 'None'
    try: sc.eevee.taa_render_samples = 32
    except AttributeError: pass
    return sc


def lights_and_world(aim=(0, 0, 1.2), scale=1.0):
    sc = bpy.context.scene
    w = bpy.data.worlds.new("w"); sc.world = w; w.use_nodes = True
    w.node_tree.nodes["Background"].inputs[0].default_value = (*BG, 1)
    w.node_tree.nodes["Background"].inputs[1].default_value = 1.0
    tgt = bpy.data.objects.new("aim", None); sc.collection.objects.link(tgt); tgt.location = aim
    for name, loc, energy, size, col in (("key", (-2.2, -2.6, 3.0), 240, 1.6, (1.0, 0.97, 0.92)),
                                         ("fill", (2.6, -2.0, 1.6), 55, 2.5, (0.88, 0.92, 1.0)),
                                         ("rim", (0.6, 3.0, 2.8), 260, 1.2, (0.95, 0.97, 1.0))):
        L = bpy.data.lights.new(name, 'AREA'); L.energy = energy * scale * scale; L.size = size * scale; L.color = col
        o = bpy.data.objects.new(name, L); sc.collection.objects.link(o)
        o.location = Vector(loc) * scale + Vector((0, 0, aim[2] - 1.2))
        tc = o.constraints.new('TRACK_TO'); tc.target = tgt


def camera(target, dist, az_deg, el_deg, lens=85, ortho=None):
    """az 0 = in front of a figure facing -Y; positive = toward the figure's left (+X)."""
    sc = bpy.context.scene
    cam = sc.camera
    if cam is None:
        cam = bpy.data.objects.new("cam", bpy.data.cameras.new("cam")); sc.collection.objects.link(cam); sc.camera = cam
    az, el = math.radians(az_deg), math.radians(el_deg)
    d = Vector((math.sin(az) * math.cos(el), -math.cos(az) * math.cos(el), math.sin(el)))
    cam.location = Vector(target) + d * dist
    cam.rotation_euler = (Vector(target) - cam.location).normalized().to_track_quat('-Z', 'Y').to_euler()
    if ortho: cam.data.type = 'ORTHO'; cam.data.ortho_scale = ortho
    else: cam.data.type = 'PERSP'; cam.data.lens = lens
    cam.data.clip_start = 0.01
    return cam


def render(path):
    bpy.context.scene.render.filepath = path
    bpy.ops.render.render(write_still=True)


# ------------------------------------------------------------------ cut-out cards (hair, beard) and push-out
def card_tris(ob, J, refdir):
    """indices of base polygons that are alpha cut-out cards (hair / beard strands): mean texture alpha at the corners
    and centroid below 0.9. Plates fit the SOLID body; cards may pass through a piece (reported separately)."""
    mi = J["material"]
    img = bpy.data.images.load(os.path.join(refdir, mi["textures"]["_MainTex"]["png"]), check_existing=True)
    w, h = img.size
    a = np.empty(w * h * 4, np.float32); img.pixels.foreach_get(a); A = a.reshape(h, w, 4)[..., 3]
    uv = J["uv0"]
    def alpha(u, v):
        x = int(min(max(u, 0), 0.9999) * w); y = int(min(max(v, 0), 0.9999) * h)
        return A[y, x]
    out = set()
    for p in ob.data.polygons:
        pts = [uv[i] for i in p.vertices]
        cu = sum(q[0] for q in pts) / len(pts); cv = sum(q[1] for q in pts) / len(pts)
        vals = [alpha(*q) for q in pts] + [alpha(cu, cv)]
        if sum(vals) / len(vals) < 0.9: out.add(p.index)
    return out


def push_out(bm, bvh, clear=0.004, passes=2):
    """every vertex closer than `clear` to (or inside) the solid base is moved out along the base normal to `clear`."""
    moved = 0
    for _ in range(passes):
        for v in bm.verts:
            loc, n, idx, d = bvh.find_nearest(v.co)
            if loc is None: continue
            s = (v.co - loc).dot(n)
            if s < clear:
                v.co = loc + n * clear; moved += 1
    return moved


def push_out_faces(bm, bvh, clear=0.004, iters=4):
    """chords too: a face whose centroid or edge midpoint is inside / closer than `clear` moves its vertices out."""
    n_moved = 0
    for _ in range(iters):
        acc = {}
        for f in bm.faces:
            pts = [f.calc_center_median()] + [(e.verts[0].co + e.verts[1].co) / 2 for e in f.edges]
            worst = None
            for c in pts:
                loc, n, idx, d = bvh.find_nearest(c)
                if loc is None: continue
                s = (c - loc).dot(n)
                if s < clear and (worst is None or s < worst[0]): worst = (s, n)
            if worst:
                for v in f.verts:
                    acc.setdefault(v, []).append(worst[1] * (clear - worst[0]))
        if not acc: break
        for v, ds in acc.items():
            v.co += max(ds, key=lambda x: x.length); n_moved += 1
    return n_moved


def surface_root(bvh, start, direction, length, seed, steps=6, r0=0.014, clear=0.004, wander=0.45, seg=5):
    """a root tendril creeping over the body: walk the surface by raycasts, then a tapering tube lifted r + clear off it."""
    import hivekit_b as K
    rnd = random.Random(seed)
    loc, n, idx, d = bvh.find_nearest(Vector(start))
    if loc is None: return None
    p, dirv = loc, (Vector(direction) - n * Vector(direction).dot(n)).normalized()
    pts, rr = [], []
    for i in range(steps + 1):
        f = i / steps; r = r0 * (1 - 0.8 * f) + 0.002
        pts.append(p + n * (r + clear)); rr.append(r)
        side = n.cross(dirv).normalized()
        dirv = (dirv + side * rnd.uniform(-wander, wander)).normalized()
        q = p + dirv * (length / steps)
        loc, n2, idx, d = bvh.find_nearest(q)
        if loc is None: break
        n = n2; dirv = (dirv - n * dirv.dot(n)).normalized(); p = loc
    if len(pts) < 3: return None
    return K.tube(pts, rr, seg=seg, seed=seed, jitter=0.12, cap0=True, cap1=False)


# ------------------------------------------------------------------ v2 kitbash: vanilla parts in their real materials
def part_material(mi, refdir, name, moss=False, cutout=False, emit=None, tint=None, emit_map=False, emit_facing=False, facing_power=1.5):
    """a vanilla material as the game draws it (approximation): _MainTex (with its tiling) x _Color, the AG normal map,
    alpha cut-out at _Cutoff when `cutout`, the Hive's moss on upward faces when `moss` (_MossTex, world-up blend),
    emission = _EmissionColor (optionally x _EmissionMap)."""
    m = bpy.data.materials.new(name); m.use_nodes = True
    nt = m.node_tree; b = nt.nodes["Principled BSDF"]
    tx = mi["textures"]; col = mi["colors"].get("_Color", [1, 1, 1, 1]); t = tint or (1, 1, 1)
    uvn = nt.nodes.new("ShaderNodeUVMap"); mp = nt.nodes.new("ShaderNodeMapping")
    sc = tx.get("_MainTex", {}).get("scale", [1, 1]); mp.inputs["Scale"].default_value = (sc[0], sc[1], 1)
    nt.links.new(uvn.outputs["UV"], mp.inputs["Vector"])
    base_out = None
    if "_MainTex" in tx and "png" in tx["_MainTex"]:
        tex = nt.nodes.new("ShaderNodeTexImage"); tex.image = bpy.data.images.load(os.path.join(refdir, tx["_MainTex"]["png"]), check_existing=True)
        nt.links.new(mp.outputs["Vector"], tex.inputs["Vector"])
        mul = nt.nodes.new("ShaderNodeMix"); mul.data_type = 'RGBA'; mul.blend_type = 'MULTIPLY'; mul.inputs[0].default_value = 1.0
        mul.inputs[7].default_value = (col[0] * t[0], col[1] * t[1], col[2] * t[2], 1)
        nt.links.new(tex.outputs["Color"], mul.inputs[6]); base_out = mul.outputs[2]
        if cutout:
            gt = nt.nodes.new("ShaderNodeMath"); gt.operation = 'GREATER_THAN'; gt.inputs[1].default_value = mi["floats"].get("_Cutoff", 0.5)
            nt.links.new(tex.outputs["Alpha"], gt.inputs[0]); nt.links.new(gt.outputs[0], b.inputs["Alpha"])
            try: m.surface_render_method = 'DITHERED'
            except Exception: pass
    else:
        b.inputs["Base Color"].default_value = (col[0] * t[0], col[1] * t[1], col[2] * t[2], 1)
    if moss and "_MossTex" in tx and "png" in tx["_MossTex"] and base_out is not None:
        mt = nt.nodes.new("ShaderNodeTexImage"); mt.image = bpy.data.images.load(os.path.join(refdir, tx["_MossTex"]["png"]), check_existing=True)
        nt.links.new(mp.outputs["Vector"], mt.inputs["Vector"])
        geo = nt.nodes.new("ShaderNodeNewGeometry"); sep = nt.nodes.new("ShaderNodeSeparateXYZ"); nt.links.new(geo.outputs["Normal"], sep.inputs[0])
        f = nt.nodes.new("ShaderNodeMapRange"); f.inputs["From Min"].default_value = 0.35; f.inputs["From Max"].default_value = 0.75
        nt.links.new(sep.outputs["Z"], f.inputs["Value"])
        mx = nt.nodes.new("ShaderNodeMix"); mx.data_type = 'RGBA'
        nt.links.new(f.outputs["Result"], mx.inputs[0]); nt.links.new(base_out, mx.inputs[6]); nt.links.new(mt.outputs["Color"], mx.inputs[7])
        base_out = mx.outputs[2]
    if base_out is not None: nt.links.new(base_out, b.inputs["Base Color"])
    if "_BumpMap" in tx and "png" in tx["_BumpMap"]:
        npng = os.path.join(refdir, "_decoded_" + tx["_BumpMap"]["png"])
        if not os.path.exists(npng): decode_normal(os.path.join(refdir, tx["_BumpMap"]["png"]), npng)
        nn = nt.nodes.new("ShaderNodeTexImage"); nn.image = bpy.data.images.load(npng, check_existing=True); nn.image.colorspace_settings.name = 'Non-Color'
        nt.links.new(mp.outputs["Vector"], nn.inputs["Vector"])
        nm = nt.nodes.new("ShaderNodeNormalMap"); nm.inputs["Strength"].default_value = mi["floats"].get("_BumpScale", 1.0)
        nt.links.new(nn.outputs["Color"], nm.inputs["Color"]); nt.links.new(nm.outputs["Normal"], b.inputs["Normal"])
    if emit_map and "_EmissionMap" in tx and "png" in tx["_EmissionMap"]:
        et = nt.nodes.new("ShaderNodeTexImage"); et.image = bpy.data.images.load(os.path.join(refdir, tx["_EmissionMap"]["png"]), check_existing=True)
        nt.links.new(mp.outputs["Vector"], et.inputs["Vector"])
        ec = mi["colors"].get("_EmissionColor", [1, 1, 1, 1])[:3]; k = max(ec) or 1.0
        em = nt.nodes.new("ShaderNodeMix"); em.data_type = 'RGBA'; em.blend_type = 'MULTIPLY'; em.inputs[0].default_value = 1.0
        em.inputs[7].default_value = (ec[0] / k, ec[1] / k, ec[2] / k, 1)
        nt.links.new(et.outputs["Color"], em.inputs[6]); nt.links.new(em.outputs[2], b.inputs["Emission Color"])
        b.inputs["Emission Strength"].default_value = min(k, 3.0)
    if emit is not None:
        k = max(emit) or 1.0
        b.inputs["Emission Color"].default_value = (emit[0] / k, emit[1] / k, emit[2] / k, 1)
        b.inputs["Emission Strength"].default_value = min(k * 2.0, 4.0)
        if emit_facing:   # a bright core and a darker rim: strength x (0.25 + 0.75 (1 - facing)^1.5)
            lw = nt.nodes.new("ShaderNodeLayerWeight"); lw.inputs["Blend"].default_value = 0.5
            inv = nt.nodes.new("ShaderNodeMath"); inv.operation = 'SUBTRACT'; inv.inputs[0].default_value = 1.0
            nt.links.new(lw.outputs["Facing"], inv.inputs[1])
            pw = nt.nodes.new("ShaderNodeMath"); pw.operation = 'POWER'; pw.inputs[1].default_value = facing_power; nt.links.new(inv.outputs[0], pw.inputs[0])
            ma = nt.nodes.new("ShaderNodeMath"); ma.operation = 'MULTIPLY_ADD'; ma.inputs[1].default_value = 0.9 if facing_power > 2 else 0.75; ma.inputs[2].default_value = 0.1 if facing_power > 2 else 0.25
            nt.links.new(pw.outputs[0], ma.inputs[0])
            mu = nt.nodes.new("ShaderNodeMath"); mu.operation = 'MULTIPLY'; mu.inputs[1].default_value = min(k * 2.0, 4.0)
            nt.links.new(ma.outputs[0], mu.inputs[0]); nt.links.new(mu.outputs[0], b.inputs["Emission Strength"])
    b.inputs["Roughness"].default_value = 1.0 - mi["floats"].get("_Glossiness", 0.1)
    return m


def part_bm(P, verts_b=None):
    """a bmesh of a part (Blender frame, winding flipped for the handedness change) with UV0 and material index per submesh."""
    vs = verts_b if verts_b is not None else [u2b(v) for v in P["verts"]]
    bm = bmesh.new(); uvl = bm.loops.layers.uv.new("UVMap")
    bv = [bm.verts.new(v) for v in vs]
    uv = P.get("uv0")
    for si, sub in enumerate(P["submeshes"]):
        for tri in sub:
            ids = list(reversed(tri))
            if len(set(ids)) < 3: continue
            try: f = bm.faces.new([bv[i] for i in ids])
            except ValueError: continue
            f.material_index = si
            if uv:
                for lp, i in zip(f.loops, ids): lp[uvl].uv = uv[i]
    return bm


def bm_object(bm, name, mats, smooth=True):
    me = bpy.data.meshes.new(name); bm.to_mesh(me); bm.free()
    for m in mats: me.materials.append(m)
    for p in me.polygons: p.use_smooth = smooth
    ob = bpy.data.objects.new(name, me); bpy.context.scene.collection.objects.link(ob)
    return ob


PLAYER_TO_DRAUGR = {"Hips": "Hips", "Spine": "Spine0", "Spine1": "Spine1", "Spine2": "Spine2", "Neck": "Head", "Head": "Head", "Jaw": "Head"}
for _s in ("Left", "Right"):
    PLAYER_TO_DRAUGR.update({f"{_s}Shoulder": f"{_s}Shoulder", f"{_s}Arm": f"{_s}Arm", f"{_s}ForeArm": f"{_s}ForeArm", f"{_s}Hand": f"{_s}Hand",
                             f"{_s}UpLeg": f"{_s}UpLeg", f"{_s}Leg": f"{_s}Leg", f"{_s}Foot": f"{_s}Foot", f"{_s}ToeBase": f"{_s}Foot"})


def retarget(P, J, extra_scale=1.0, adjust=None, return_ms=False):
    """move a skinned Player-rig part into the Draugr's bind pose: per mapped bone, T(draugr) R(align the segment) S(length
    ratio) T(-player), blended with the part's own skin weights (linear blend skinning). Returns Blender-frame vertices and
    the list of (part vertex -> dominant Draugr bone)."""
    pb = {n: np.array(M) for n, M in zip(P["bone_names"], P["bone_bind_world"])}
    db = {n: np.array(M) for n, M in zip(J["bone_names"], J["bone_bind_world"])}
    dn = {n: node_pos(J, n) for n in ("LeftHand_end", "RightHand_end", "LeftFoot_end", "RightFoot_end", "Head_end")}
    def pp(n): return u2b(pb[n][:3, 3])
    def dp(n): return u2b(db[n][:3, 3])
    flip = pp("LeftArm").x < 0                          # the Player rig faces +Z (left at -X): turn it 180 about up first
    F = Matrix.Rotation(math.pi, 4, 'Z') if flip else Matrix.Identity(4)
    def ppf(n): return F @ pp(n)
    seg = {}   # player bone -> (player child pos, draugr child pos) for the limb segments
    for s in ("Left", "Right"):
        seg[f"{s}Shoulder"] = (ppf(f"{s}Arm"), dp(f"{s}Arm"))
        seg[f"{s}Arm"] = (ppf(f"{s}ForeArm"), dp(f"{s}ForeArm"))
        seg[f"{s}ForeArm"] = (ppf(f"{s}Hand"), dp(f"{s}Hand"))
        seg[f"{s}Hand"] = (ppf(f"{s}HandMiddle1") if f"{s}HandMiddle1" in pb else ppf(f"{s}Hand") + (ppf(f"{s}Hand") - ppf(f"{s}ForeArm")) * 0.3, dn[f"{s}Hand_end"])
        seg[f"{s}UpLeg"] = (ppf(f"{s}Leg"), dp(f"{s}Leg"))
        seg[f"{s}Leg"] = (ppf(f"{s}Foot"), dp(f"{s}Foot"))
        seg[f"{s}Foot"] = (ppf(f"{s}ToeBase") if f"{s}ToeBase" in pb else ppf(f"{s}Foot") + Vector((0, -0.1, -0.05)), dn[f"{s}Foot_end"])
    torso_s = (dp("Spine2") - dp("Spine0")).length / max((ppf("Spine2") - ppf("Spine")).length, 1e-6)
    Ms = {}
    for n in pb:
        d = PLAYER_TO_DRAUGR.get(n)
        if d is None:   # fingers / toes / anything unmapped: follow the hand / foot (or the head)
            src = next((k for k in ("LeftHand", "RightHand", "LeftFoot", "RightFoot") if n.startswith(k)), "Head")
            d = PLAYER_TO_DRAUGR[src]
        else:
            src = n
        p0, q0 = ppf(src), dp(d)
        if src in seg:
            pc, qc = seg[src]
            vp, vq = pc - p0, qc - q0
            R = vp.normalized().rotation_difference(vq.normalized()).to_matrix().to_4x4()
            s = vq.length / max(vp.length, 1e-6)
        else:
            R = Matrix.Identity(4); s = torso_s
        s *= extra_scale
        Ms[n] = Matrix.Translation(q0) @ R @ Matrix.Scale(s, 4) @ Matrix.Translation(-p0) @ F
        if adjust and src in adjust: Ms[n] = adjust[src] @ Ms[n]
    W = np.array(P["weights"]); I = np.array(P["indices"])
    out, dom = [], []
    for vi, v in enumerate(P["verts"]):
        pv = u2b(v); acc = Vector((0, 0, 0)); tw = 0.0
        for k in range(4):
            w = W[vi][k]
            if w <= 0: continue
            n = P["bone_names"][I[vi][k]]
            acc += (Ms[n] @ pv) * w; tw += w
        out.append(acc / tw if tw > 0 else Ms["Hips"] @ pv)
        n = P["bone_names"][I[vi][int(np.argmax(W[vi]))]]
        dom.append(PLAYER_TO_DRAUGR.get(n) or next((k for k in ("LeftHand", "RightHand", "LeftFoot", "RightFoot") if n.startswith(k)), "Head"))
    if return_ms:
        srcdom = [P["bone_names"][I[vi][int(np.argmax(W[vi]))]] for vi in range(len(W))]
        return out, dom, Ms, srcdom
    return out, dom


def rest_on(bm, bvh, normal, clear=0.003, iters=12):
    """slide a placed part along `normal` until no vertex is closer than `clear` to (or inside) the base."""
    n = Vector(normal).normalized(); moved = 0.0
    for _ in range(iters):
        worst = 1.0
        for v in bm.verts:
            loc, nn, idx, d = bvh.find_nearest(v.co)
            if loc is None: continue
            worst = min(worst, (v.co - loc).dot(nn))
        if worst >= clear: break
        step = clear - worst + 0.001
        for v in bm.verts: v.co += n * step
        moved += step
    return moved
