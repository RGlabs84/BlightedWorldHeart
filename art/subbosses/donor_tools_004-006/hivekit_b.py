"""Shared helpers for the BlightedHeart sub-boss shape models ASSET-004..006 (art step 1: shapes only).

Imported by each ASSET-00N generator (sys.path insert of this folder). Deterministic: every random choice
takes an explicit seed. Frames: Blender x/y/z = Unity x/z/y, metres. The donor exports (export_donor.py)
are in Unity space relative to the prefab root; load_donor() converts them.

Geometry kit (bmesh): faceted bark lumps, lofted limb tubes with joint loops, bevelled timber beams and
planks, root lashings, eye nodes in raised-rim sockets (BVH-seated on the body), moss caps, blight cracks,
V-folded foliage cards, saplings. Each part is added to a Builder with a material slot name; the Builder
joins them into ONE mesh object with the six Hive slots (assigned by name), smart-UV-projects it and counts.

Previews: Workbench (flat placeholder colour per slot + cavity + outline), a matcap view, a wire view
(wireframe-modifier copy), a donor ghost overlay (x-ray), and a lineup with a 1.8 m figure.
"""
import bpy, bmesh, math, os, json, random
from mathutils import Vector, Matrix, Euler, noise
from mathutils.bvhtree import BVHTree

SLOTS = ["HiveBark", "HiveTimber", "HiveMoss", "HiveEye", "HiveFoliage", "BlightGlow"]
COLOURS = {"HiveBark": "#5A4630", "HiveTimber": "#9C8E78", "HiveMoss": "#4F6B2E", "HiveEye": "#FF2A40",
           "HiveFoliage": "#2F5A2A", "BlightGlow": "#7CFF3A"}


def hex_rgb(h):
    h = h.lstrip("#")
    srgb = [int(h[i:i + 2], 16) / 255 for i in (0, 2, 4)]
    return [c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4 for c in srgb]  # linear for Blender


def reset():
    bpy.ops.wm.read_factory_settings(use_empty=True)


def u2b(v):
    return Vector((v[0], v[2], v[1]))


# ------------------------------------------------------------------ donor
def load_donor(ddir):
    """-> (bones {name: Vector blender}, nodes {name: Vector}, json). Bind-pose bone positions of renderer 0,
    plus every other node (end bones, attach points) at its prefab-pose position."""
    j = json.load(open(os.path.join(ddir, "donor_bones.json")))
    bones, delta = {}, {}
    for r in j["renderers"]:
        for b in r["bones"]:
            if b["bind_world"]:
                bones.setdefault(b["name"], u2b(b["bind_world"]))
                delta.setdefault(b["name"], u2b(b["bind_world"]) - u2b(b["prefab_world"]))
    parent = {n["name"]: n["parent"] for n in j["nodes"]}
    nodes = {}
    for n in j["nodes"]:  # non-skinned nodes (end bones, attach points): shift by the nearest skinned ancestor's bind-prefab offset
        a = n["name"]
        while a is not None and a not in delta: a = parent.get(a)
        nodes[n["name"]] = u2b(n["world_pos"]) + (delta[a] if a else Vector())
    return bones, nodes, j


def import_donor_meshes(ddir, j, name="Donor", active_only=True):
    """bind-pose donor meshes as Blender objects (Unity -> Blender, winding flipped for the handedness change)."""
    obs = []
    for r in j["renderers"]:
        if active_only and not r["active"]: continue
        vs, fs = [], []
        for line in open(os.path.join(ddir, r["obj"])):
            p = line.split()
            if not p: continue
            if p[0] == "v": vs.append(u2b([float(x) for x in p[1:4]]))
            elif p[0] == "f": fs.append([int(x) - 1 for x in reversed(p[1:])])
        me = bpy.data.meshes.new(f"{name}_{r['node']}")
        me.from_pydata(vs, [], fs); me.update()
        ob = bpy.data.objects.new(me.name, me); bpy.context.scene.collection.objects.link(ob)
        obs.append(ob)
    return obs


# ------------------------------------------------------------------ builder
class Builder:
    def __init__(self, name):
        self.name = name
        self.parts = []  # (bm, slot, label)

    def add(self, bm, slot, label=""):
        assert slot in SLOTS, slot
        self.parts.append((bm, slot, label))
        return bm

    def label_tris(self):
        d = {}
        for bm, slot, label in self.parts:
            d[label] = d.get(label, 0) + sum(len(f.verts) - 2 for f in bm.faces)
        return dict(sorted(d.items(), key=lambda kv: -kv[1]))

    def build(self):
        self.labels = self.label_tris()
        out = bmesh.new()
        out.loops.layers.uv.new("UVMap")
        for bm, slot, label in self.parts:
            idx = SLOTS.index(slot)
            for f in bm.faces: f.material_index = idx
            me = bpy.data.meshes.new("tmp"); bm.to_mesh(me); bm.free()
            out.from_mesh(me); bpy.data.meshes.remove(me)
        me = bpy.data.meshes.new(self.name)
        out.to_mesh(me); out.free()
        for s in SLOTS: me.materials.append(slot_material(s))
        ob = bpy.data.objects.new(self.name, me); bpy.context.scene.collection.objects.link(ob)
        for p in me.polygons: p.use_smooth = False  # faceted bark: flat shading like the Hive
        # keep only one UV layer
        while len(me.uv_layers) > 1: me.uv_layers.remove(me.uv_layers[-1])
        if not me.uv_layers: me.uv_layers.new(name="UVMap")
        smart_uv(ob)
        return ob


def slot_material(s):
    m = bpy.data.materials.get(s)
    if m: return m
    m = bpy.data.materials.new(s)
    c = hex_rgb(COLOURS[s]); m.diffuse_color = (*c, 1)
    m.use_nodes = True
    b = m.node_tree.nodes["Principled BSDF"]; b.inputs["Base Color"].default_value = (*c, 1)
    b.inputs["Roughness"].default_value = 0.85
    emit = {"HiveEye": 3.0, "BlightGlow": 2.5}   # same as tools_001-003/hive_kit.py so both contact sheets light alike
    if s in emit:
        b.inputs["Emission Color"].default_value = (*c, 1); b.inputs["Emission Strength"].default_value = emit[s]
    return m


def smart_uv(ob):
    for o in bpy.context.scene.objects: o.select_set(False)
    bpy.context.view_layer.objects.active = ob; ob.select_set(True)
    bpy.ops.object.mode_set(mode='EDIT')
    bpy.ops.mesh.select_all(action='SELECT')
    bpy.ops.uv.smart_project(angle_limit=math.radians(60), island_margin=0.004)
    bpy.ops.object.mode_set(mode='OBJECT')


def stats(ob):
    me = ob.data
    tris = sum(len(p.vertices) - 2 for p in me.polygons)
    per = {s: 0 for s in SLOTS}
    for p in me.polygons: per[SLOTS[p.material_index]] += len(p.vertices) - 2
    vs = [ob.matrix_world @ v.co for v in me.vertices]
    mn = Vector((min(v.x for v in vs), min(v.y for v in vs), min(v.z for v in vs)))
    mx = Vector((max(v.x for v in vs), max(v.y for v in vs), max(v.z for v in vs)))
    return {"tris": tris, "tris_per_slot": per, "verts": len(me.vertices),
            "bounds_min_blender": [round(x, 4) for x in mn], "bounds_max_blender": [round(x, 4) for x in mx],
            "size_unity_xyz_m": [round(mx.x - mn.x, 3), round(mx.z - mn.z, 3), round(mx.y - mn.y, 3)],
            "material_slots": [m.name for m in me.materials], "uv_channels": len(me.uv_layers),
            "uv_layer_names": [u.name for u in me.uv_layers]}


# ------------------------------------------------------------------ geometry primitives
def _bm():
    bm = bmesh.new(); bm.loops.layers.uv.new("UVMap"); return bm


def frame_from(z_axis, hint=Vector((0, 0, 1))):
    z = Vector(z_axis).normalized()
    h = Vector(hint)
    if abs(z.dot(h.normalized())) > 0.95: h = Vector((1, 0, 0)) if abs(z.x) < 0.9 else Vector((0, 1, 0))
    x = h.cross(z).normalized(); y = z.cross(x)
    return Matrix((x, y, z)).transposed()  # columns x, y, z


def lump(center, radii, seed, subdiv=2, amp=0.16, freq=1.5, chops=5, chop_depth=(0.72, 0.9), rot=None):
    """a faceted fused bark mass: icosphere, low-frequency noise, then planar chops (big flat facets like the Hive)."""
    rnd = random.Random(seed)
    bm = _bm()
    bmesh.ops.create_icosphere(bm, subdivisions=subdiv, radius=1.0)
    off = Vector((rnd.uniform(-50, 50), rnd.uniform(-50, 50), rnd.uniform(-50, 50)))
    planes = []
    for _ in range(chops):
        n = Vector((rnd.gauss(0, 1), rnd.gauss(0, 1), rnd.gauss(0, 1))).normalized()
        planes.append((n, rnd.uniform(*chop_depth)))
    for v in bm.verts:
        d = v.co.normalized()
        r = 1 + amp * noise.noise(d * freq + off) + 0.5 * amp * noise.noise(d * freq * 2.7 + off * 1.3)
        p = d * r
        for n, o in planes:
            k = p.dot(n)
            if k > o: p -= n * (k - o) * 0.85
        v.co = p
    R = rot if rot is not None else Matrix.Identity(3)
    for v in bm.verts:
        v.co = Vector(center) + R @ Vector((v.co.x * radii[0], v.co.y * radii[1], v.co.z * radii[2]))
    bm.normal_update()
    return bm


def rmf_frames(pts):
    """rotation-minimising frames along a polyline -> list of (tangent, normal, binormal)."""
    n = len(pts)
    tans = []
    for i in range(n):
        a = pts[max(i - 1, 0)]; b = pts[min(i + 1, n - 1)]
        tans.append((b - a).normalized())
    t0 = tans[0]
    ref = Vector((0, 0, 1)) if abs(t0.z) < 0.9 else Vector((1, 0, 0))
    nrm = (ref - t0 * ref.dot(t0)).normalized()
    out = []
    for i, t in enumerate(tans):
        if i > 0:
            nrm = (nrm - t * nrm.dot(t)).normalized()
        out.append((t, nrm, t.cross(nrm)))
    return out


def tube(points, radii, seg=7, seed=0, jitter=0.12, cap0=True, cap1=True, squash=None, twist=0.0, up_hint=None):
    """a lofted faceted tube through `points` with radius per point (rings at every point = edge loops at joints).
    squash: per-point (sx, sy) ellipse factors; jitter: per-vertex radial noise (bark facets)."""
    rnd = random.Random(seed)
    pts = [Vector(p) for p in points]
    fr = rmf_frames(pts)
    if up_hint is not None:  # re-orient the first normal toward a hint, propagate
        t0 = fr[0][0]; h = Vector(up_hint); nrm = (h - t0 * h.dot(t0)).normalized(); fr2 = []
        for i, (t, _, _) in enumerate(fr):
            nrm = (nrm - t * nrm.dot(t)).normalized(); fr2.append((t, nrm, t.cross(nrm)))
        fr = fr2
    bm = _bm(); uv = bm.loops.layers.uv["UVMap"]
    rings = []
    for i, (p, (t, n, b)) in enumerate(zip(pts, fr)):
        sx, sy = squash[i] if squash else (1, 1)
        ring = []
        for k in range(seg):
            a = 2 * math.pi * k / seg + twist * i + (0.5 * math.pi / seg if i % 2 else 0) * 0.0
            r = radii[i] * (1 + rnd.uniform(-jitter, jitter))
            ring.append(bm.verts.new(p + n * math.cos(a) * r * sx + b * math.sin(a) * r * sy))
        rings.append(ring)
    acc = [0.0]
    for i in range(1, len(pts)): acc.append(acc[-1] + (pts[i] - pts[i - 1]).length)
    for i in range(len(rings) - 1):
        for k in range(seg):
            q = (k + 1) % seg
            f = bm.faces.new((rings[i][k], rings[i][q], rings[i + 1][q], rings[i + 1][k]))
            for lp, (uu, vv) in zip(f.loops, ((k, acc[i]), (k + 1, acc[i]), (k + 1, acc[i + 1]), (k, acc[i + 1]))):
                lp[uv].uv = (uu / seg, vv)
    if cap0: _cap(bm, rings[0], pts[0] - fr[0][0] * radii[0] * 0.35, rev=False)
    if cap1: _cap(bm, rings[-1], pts[-1] + fr[-1][0] * radii[-1] * 0.35, rev=True)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    return bm


def _cap(bm, ring, tip, rev):
    c = bm.verts.new(tip)
    n = len(ring)
    for k in range(n):
        q = (k + 1) % n
        bm.faces.new((ring[q], ring[k], c) if not rev else (ring[k], ring[q], c))


def beam(p0, p1, w, h, seed, bend=0.03, segs=3, chamfer=0.25, chip=0.04, up=Vector((0, 0, 1)), twist=0.0, taper=1.0, point=False, bend_vec=None):
    """a rough timber beam: chamfered rectangular section (8 sides = bevelled edges), slight bend and twist,
    chipped uneven ends."""
    rnd = random.Random(seed)
    p0, p1 = Vector(p0), Vector(p1)
    ax = (p1 - p0); L = ax.length; ax.normalize()
    u = Vector(up); u = (u - ax * u.dot(ax))
    if u.length < 1e-4: u = frame_from(ax).col[0]
    u.normalize(); s = ax.cross(u)
    bendv = (u * rnd.uniform(-1, 1) + s * rnd.uniform(-1, 1)).normalized() * bend * L
    if bend_vec is not None: bendv = Vector(bend_vec)
    cw, ch = w * chamfer, h * chamfer
    sec = [(-w / 2 + cw, -h / 2), (w / 2 - cw, -h / 2), (w / 2, -h / 2 + ch), (w / 2, h / 2 - ch),
           (w / 2 - cw, h / 2), (-w / 2 + cw, h / 2), (-w / 2, h / 2 - ch), (-w / 2, -h / 2 + ch)]
    bm = _bm(); uv = bm.loops.layers.uv["UVMap"]
    rings = []
    for i in range(segs + 1):
        t = i / segs
        c = p0 + ax * L * t + bendv * math.sin(math.pi * t)
        a = twist * (t - 0.5)
        ca, sa = math.cos(a), math.sin(a)
        ring = []
        for k, (x, y) in enumerate(sec):
            xx, yy = x * ca - y * sa, x * sa + y * ca
            d = 0.0
            if i == 0: d = -rnd.uniform(0, chip)
            elif i == segs: d = rnd.uniform(0, chip)
            j = (1 + rnd.uniform(-0.06, 0.06)) * (1 + (taper - 1) * t)
            ring.append(bm.verts.new(c + s * xx * j + u * yy * j + ax * d))
        rings.append(ring)
    n = len(sec)
    for i in range(segs):
        for k in range(n):
            q = (k + 1) % n
            f = bm.faces.new((rings[i][k], rings[i][q], rings[i + 1][q], rings[i + 1][k]))
            for lp, (uu, vv) in zip(f.loops, ((k, i), (k + 1, i), (k + 1, i + 1), (k, i + 1))):
                lp[uv].uv = (uu / n * 0.3, vv / segs * L)
    bm.faces.new(list(reversed(rings[0])))
    if point:  # splinter tip
        _cap(bm, rings[-1], p1 + ax * L * 0.12 + bendv * 0.0, rev=True)
    else:
        bm.faces.new(rings[-1])
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    return bm


def lashing(center, axis, radius, seed, turns=3, thick=0.012, spacing=None, seg=6):
    """root/rope lashing: `turns` faceted rings around an axis, slightly tilted and spaced (each a 4-sided torus)."""
    rnd = random.Random(seed)
    ax = Vector(axis).normalized()
    F = frame_from(ax)
    spacing = spacing or thick * 1.9
    bm = _bm()
    for t in range(turns):
        c = Vector(center) + ax * (t - (turns - 1) / 2) * spacing
        tilt = Matrix.Rotation(rnd.uniform(-0.18, 0.18), 3, F.col[0])
        rings = []
        for k in range(seg):
            a = 2 * math.pi * k / seg
            rr = radius * (1 + rnd.uniform(-0.04, 0.04)) + thick / 2
            dirv = tilt @ (F.col[0] * math.cos(a) + F.col[1] * math.sin(a))
            p = c + dirv * rr
            ax2 = tilt @ ax
            sec = [p + dirv * thick * 0.5, p + ax2 * thick * 0.5, p - dirv * thick * 0.5, p - ax2 * thick * 0.5]
            rings.append([bm.verts.new(x) for x in sec])
        for k in range(seg):
            q = (k + 1) % seg
            for m in range(4):
                m2 = (m + 1) % 4
                bm.faces.new((rings[k][m], rings[q][m], rings[q][m2], rings[k][m2]))
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    return bm


def uvsphere(center, r, seg=8, rings=6, scale=(1, 1, 1)):
    bm = _bm()
    bmesh.ops.create_uvsphere(bm, u_segments=seg, v_segments=rings, radius=r)
    for v in bm.verts:
        v.co = Vector(center) + Vector((v.co.x * scale[0], v.co.y * scale[1], v.co.z * scale[2]))
    return bm


def lathe_ring(center, normal, profile, seg=10, seed=0, jitter=0.0):
    """a ring from a (radius, height) profile, around `normal` (closed profile loop)."""
    rnd = random.Random(seed)
    F = frame_from(normal)
    bm = _bm()
    rows = []
    for k in range(seg):
        a = 2 * math.pi * k / seg
        d = F.col[0] * math.cos(a) + F.col[1] * math.sin(a)
        j = 1 + rnd.uniform(-jitter, jitter)
        rows.append([bm.verts.new(Vector(center) + d * r * j + F.col[2] * h) for r, h in profile])
    m = len(profile)
    for k in range(seg):
        q = (k + 1) % seg
        for i in range(m):
            i2 = (i + 1) % m
            bm.faces.new((rows[k][i], rows[q][i], rows[q][i2], rows[k][i2]))
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    return bm


class Surface:
    """BVH over the parts already built (by label filter) for seating eyes, moss, cracks."""
    def __init__(self, bms):
        tmp = bmesh.new()
        for b in bms:
            me = bpy.data.meshes.new("tmp"); b.to_mesh(me); tmp.from_mesh(me); bpy.data.meshes.remove(me)
        bmesh.ops.recalc_face_normals(tmp, faces=tmp.faces)
        self.bvh = BVHTree.FromBMesh(tmp); tmp.free()

    def hit_toward(self, origin, target):
        """first surface hit from `origin` toward `target` (origin outside) -> (loc, normal) or None"""
        d = (Vector(target) - Vector(origin)); dist = d.length
        loc, nrm, idx, dd = self.bvh.ray_cast(Vector(origin), d.normalized(), dist)
        if loc is None: return None
        if nrm.dot(d) > 0: nrm = -nrm
        return loc, nrm.normalized()

    def project(self, p, from_dir, back=0.6):
        """cast from p + from_dir*back toward p - from_dir*back."""
        fd = Vector(from_dir).normalized()
        return self.hit_toward(Vector(p) + fd * back, Vector(p) - fd * back)


def eye_node(B, loc, nrm, r, seed, proud=0.005, sink=0.03, rim_w=0.45, squash=1.0, squash_axis=None):
    """an eye sphere (HiveEye) seated in a raised bark socket rim (HiveBark).
    The rim's top stands `proud` (2-6 mm) above the surface hit point; its base sinks `sink` into the body so it
    never floats on a curved facet; the sphere sits with ~60% of its radius above the rim top."""
    n = Vector(nrm).normalized()
    ctr = Vector(loc) + n * (proud + 0.25 * r - r * 0.25)  # eye centre near the rim top plane
    ctr = Vector(loc) + n * (proud - 0.05 * r)
    sg = 10 if r >= 0.06 else (8 if r >= 0.035 else 6)
    eye = uvsphere(ctr, r, seg=sg, rings=max(sg - 3, 4))
    SQ = None
    if squash != 1.0:   # a narrowed, slit socket: squash eye and rim across `squash_axis` (default: the vertical tangent)
        ax = Vector(squash_axis) if squash_axis is not None else Vector((0, 0, 1))
        ax = (ax - n * ax.dot(n)).normalized()
        S = Matrix.Identity(4)
        for i in range(3):
            for j in range(3): S[i][j] -= (1 - squash) * ax[i] * ax[j]
        SQ = Matrix.Translation(Vector(loc)) @ S @ Matrix.Translation(-Vector(loc))
        bmesh.ops.transform(eye, matrix=SQ, verts=eye.verts)
    B.add(eye, "HiveEye", "eye")
    # rim profile (radius, height above surface): inner lip overlaps the sphere, outer foot buried
    top = proud
    rin = r * 0.92
    rout = r * (1 + rim_w)
    prof = [(rin, top - 0.002), (rin + (rout - rin) * 0.45, top + 0.001), (rout, top - 0.006),
            (rout * 1.08, -sink), (rin * 0.98, -sink)]
    if r < 0.025:   # small eyes: a 4-point rim profile (same look, fewer triangles)
        prof = [(rin, top - 0.002), (rout, top - 0.004), (rout * 1.08, -sink), (rin * 0.98, -sink)]
    rim = lathe_ring(Vector(loc), n, prof, seg=sg, seed=seed, jitter=0.05)
    if SQ is not None: bmesh.ops.transform(rim, matrix=SQ, verts=rim.verts)
    B.add(rim, "HiveBark", "eyerim")


def moss_cap_from(bm_src, up=Vector((0, 0, 1)), thresh=0.45, thick=0.012, skirt=0.03, seed=0, keep=0.75, nfreq=4.0):
    """a moss shell copied from the upward faces of a lump bmesh: offset `thick` outward, edge skirt sunk inward."""
    rnd = random.Random(seed)
    off = Vector((rnd.uniform(0, 99), rnd.uniform(0, 99), rnd.uniform(0, 99)))
    bm_src.normal_update()
    sel = [f for f in bm_src.faces if f.normal.dot(up) > thresh and noise.noise(f.calc_center_median() * nfreq + off) > (1 - keep * 2) * 0.5 - 0.25]
    out = _bm()
    if not sel: return out
    vmap = {}
    for f in sel:
        for v in f.verts:
            if v not in vmap:
                nv = v.normal if v.normal.length > 0 else f.normal
                vmap[v] = out.verts.new(v.co + nv * thick)
    for f in sel:
        out.faces.new([vmap[v] for v in f.verts])
    out.normal_update()
    # skirt: extrude boundary edges inward (into the body)
    bnd = [e for e in out.edges if e.is_boundary]
    if bnd:
        res = bmesh.ops.extrude_edge_only(out, edges=bnd)
        nv = [g for g in res["geom"] if isinstance(g, bmesh.types.BMVert)]
        for v in nv:
            nn = v.normal if v.normal.length > 0 else up
            v.co -= nn * skirt + up * skirt * 0.5
    bmesh.ops.recalc_face_normals(out, faces=out.faces)
    return out


def crack(surf, start, direction, length, seed, steps=7, width=0.018, proud=0.004, wander=0.5, from_dir=None):
    """a blight crack: walk across the body surface (raycast each step), sweep a raised ridge (triangle section)."""
    rnd = random.Random(seed)
    p = Vector(start); d = Vector(direction).normalized()
    hits = []
    for i in range(steps + 1):
        fd = from_dir if from_dir is not None else None
        h = surf.project(p, fd if fd is not None else (hits[-1][1] if hits else Vector((0, 1, 0))))
        if h is None: break
        hits.append(h)
        n = h[1]
        side = n.cross(d).normalized()
        d = (d + side * rnd.uniform(-wander, wander)).normalized()
        d = (d - n * d.dot(n)).normalized()
        p = h[0] + d * (length / steps)
    bm = _bm()
    if len(hits) < 2: return bm
    rows = []
    for i, (loc, n) in enumerate(hits):
        t = (hits[min(i + 1, len(hits) - 1)][0] - hits[max(i - 1, 0)][0]).normalized()
        side = n.cross(t).normalized()
        wv = width * (0.35 + 0.65 * math.sin(math.pi * (i + 0.5) / len(hits)))
        rows.append([bm.verts.new(loc + side * wv - n * 0.01), bm.verts.new(loc + n * proud + side * wv * 0.25),
                     bm.verts.new(loc + n * proud - side * wv * 0.25), bm.verts.new(loc - side * wv - n * 0.01)])
    for i in range(len(rows) - 1):
        for k in range(3):
            bm.faces.new((rows[i][k], rows[i + 1][k], rows[i + 1][k + 1], rows[i][k + 1]))
    bm.faces.new(list(reversed(rows[0]))); bm.faces.new(rows[-1])
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    return bm


def card_strand(top, length, seed, width=0.05, segs=4, sway=Vector((0, 0.15, 0)), fold=0.35, down=Vector((0, 0, -1))):
    """a hanging foliage strand: a V-folded ribbon of `segs` segments drooping from `top`, tapering, curling with `sway`."""
    rnd = random.Random(seed)
    bm = _bm(); uv = bm.loops.layers.uv["UVMap"]
    rows = []
    dn = Vector(down).normalized()
    side0 = dn.cross(Vector(sway) if Vector(sway).length > 1e-4 else Vector((1, 0, 0))).normalized()
    if side0.length < 1e-4: side0 = Vector((1, 0, 0))
    rot = Matrix.Rotation(rnd.uniform(0, math.pi), 3, dn)
    side0 = rot @ side0
    fdir = dn.cross(side0).normalized()
    for i in range(segs + 1):
        t = i / segs
        c = Vector(top) + dn * length * t + Vector(sway) * (t * t) + Vector((rnd.uniform(-1, 1), rnd.uniform(-1, 1), 0)) * 0.01 * i
        w = width * (1 - 0.75 * t)
        rows.append([bm.verts.new(c - side0 * w), bm.verts.new(c + fdir * w * fold), bm.verts.new(c + side0 * w)])
    for i in range(segs):
        for k in range(2):
            f = bm.faces.new((rows[i][k], rows[i][k + 1], rows[i + 1][k + 1], rows[i + 1][k]))
            for lp, (uu, vv) in zip(f.loops, ((k, i), (k + 1, i), (k + 1, i + 1), (k, i + 1))):
                lp[uv].uv = (uu / 2, vv / segs)
    return bm


def sapling(base, up, height, seed, tiers=3, r0=0.16, trunk_r=0.025, B=None, trunk_slot="HiveTimber"):
    """a small pine: a faceted trunk (tube) and stacked 6-sided cones (HiveFoliage) drooping slightly."""
    rnd = random.Random(seed)
    up = Vector(up).normalized()
    pts = [Vector(base) - up * 0.06, Vector(base) + up * height * 0.45, Vector(base) + up * height]
    B.add(tube(pts, [trunk_r, trunk_r * 0.75, trunk_r * 0.3], seg=5, seed=seed, jitter=0.1), trunk_slot, "sapling_trunk")
    F = frame_from(up)
    for t in range(tiers):
        f = t / max(tiers - 1, 1)
        y0 = height * (0.3 + 0.55 * f); rr = r0 * (1 - 0.55 * f); hh = height * 0.32
        c = Vector(base) + up * y0
        bm = _bm()
        n = 6
        ring = []
        rot0 = rnd.uniform(0, 1)
        for k in range(n):
            a = 2 * math.pi * (k + rot0) / n
            rk = rr * (1 + rnd.uniform(-0.15, 0.15))
            ring.append(bm.verts.new(c + (F.col[0] * math.cos(a) + F.col[1] * math.sin(a)) * rk - up * hh * 0.25))
        tip = bm.verts.new(c + up * hh)
        inner = bm.verts.new(c + up * hh * 0.1)
        for k in range(n):
            q = (k + 1) % n
            bm.faces.new((ring[k], ring[q], tip))
            bm.faces.new((ring[q], ring[k], inner))
        bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
        B.add(bm, "HiveFoliage", "sapling_tier")


def transform(bm, M):
    bmesh.ops.transform(bm, matrix=M, verts=bm.verts)
    return bm


# ------------------------------------------------------------------ rendering (Workbench)
def setup_render(res=(1000, 1000), bg=(0.36, 0.38, 0.41)):
    sc = bpy.context.scene
    sc.render.engine = 'BLENDER_WORKBENCH'
    sc.render.resolution_x, sc.render.resolution_y = res
    sc.render.film_transparent = False
    w = bpy.data.worlds.get("w") or bpy.data.worlds.new("w"); sc.world = w; w.color = bg
    sh = sc.display.shading
    sh.light = 'STUDIO'; sh.color_type = 'MATERIAL'
    try: sh.studio_light = 'paint.sl'
    except Exception: pass
    sc.view_settings.exposure = 0.9
    sh.show_cavity = True; sh.cavity_type = 'BOTH'; sh.curvature_ridge_factor = 1.2; sh.curvature_valley_factor = 1.4
    sh.show_object_outline = True; sh.object_outline_color = (0.05, 0.05, 0.05)
    sh.show_shadows = True; sh.shadow_intensity = 0.45
    sc.display.light_direction = (0.45, -0.55, 0.75)
    sh.show_xray = False
    sc.view_settings.view_transform = 'Standard'
    sc.view_settings.exposure = 0.9
    return sc


def ground(size=80, z=0.0, colour=(0.47, 0.47, 0.45)):
    bm = bmesh.new()
    bmesh.ops.create_grid(bm, x_segments=1, y_segments=1, size=size / 2)
    me = bpy.data.meshes.new("Ground"); bm.to_mesh(me); bm.free()
    ob = bpy.data.objects.new("Ground", me); bpy.context.scene.collection.objects.link(ob)
    ob.location.z = z
    m = bpy.data.materials.new("GroundMat"); m.diffuse_color = (*colour, 1); me.materials.append(m)
    return ob


def figure(x, y=0.0, height=1.8, name="Figure_1.8m"):
    """a 1.8 m scale figure (blue): legs, torso, arms, head."""
    s = height / 1.8
    bm = bmesh.new()
    def box(c, d):
        g = bmesh.ops.create_cube(bm, size=1.0)
        for v in g["verts"]: v.co = Vector((c[0] + v.co.x * d[0], c[1] + v.co.y * d[1], c[2] + v.co.z * d[2])) * 1.0
    for sx in (-1, 1):
        box((x + sx * 0.1 * s, y, 0.42 * s), (0.13 * s, 0.15 * s, 0.84 * s))
        box((x + sx * 0.26 * s, y, 1.12 * s), (0.09 * s, 0.11 * s, 0.6 * s))
    box((x, y, 1.15 * s), (0.4 * s, 0.22 * s, 0.62 * s))
    g = bmesh.ops.create_uvsphere(bm, u_segments=12, v_segments=8, radius=0.12 * s)
    for v in g["verts"]: v.co += Vector((x, y, 1.6 * s))
    # exact 1.8 m top: scale z so the head top is at height
    top = max(v.co.z for v in bm.verts)
    for v in bm.verts: v.co.z *= height / top
    me = bpy.data.meshes.new(name); bm.to_mesh(me); bm.free()
    ob = bpy.data.objects.new(name, me); bpy.context.scene.collection.objects.link(ob)
    m = bpy.data.materials.get("FigureMat") or bpy.data.materials.new("FigureMat"); m.diffuse_color = (0.25, 0.45, 0.95, 1)
    me.materials.append(m)
    return ob


def camera(name="cam"):
    sc = bpy.context.scene
    cam = bpy.data.objects.get(name)
    if cam is None:
        cam = bpy.data.objects.new(name, bpy.data.cameras.new(name)); sc.collection.objects.link(cam)
    sc.camera = cam
    return cam


def shoot(path, target, az, el, dist, ortho=None, lens=50):
    """az 0 = camera on +Y (the creature's front if it faces +Y), 90 = on +X."""
    cam = camera()
    a, e = math.radians(az), math.radians(el)
    cam.location = Vector(target) + Vector((math.sin(a) * math.cos(e), math.cos(a) * math.cos(e), math.sin(e))) * dist
    cam.rotation_euler = (Vector(target) - cam.location).to_track_quat('-Z', 'Y').to_euler()
    if ortho:
        cam.data.type = 'ORTHO'; cam.data.ortho_scale = ortho
    else:
        cam.data.type = 'PERSP'; cam.data.lens = lens
    cam.data.clip_end = 500
    bpy.context.scene.render.filepath = path
    bpy.ops.render.render(write_still=True)


def wire_copy(ob, thick=0.0035):
    me = ob.data.copy()
    w = bpy.data.objects.new(ob.name + "_wire", me); bpy.context.scene.collection.objects.link(w)
    w.matrix_world = ob.matrix_world
    mod = w.modifiers.new("wire", 'WIREFRAME'); mod.thickness = thick; mod.use_replace = True; mod.use_even_offset = True
    m = bpy.data.materials.get("WireMat") or bpy.data.materials.new("WireMat"); m.diffuse_color = (0.06, 0.06, 0.07, 1)
    w.data.materials.clear(); w.data.materials.append(m)
    mod.material_offset = 0
    return w


def ghost_material(obs, colour=(0.1, 0.85, 1.0)):
    m = bpy.data.materials.get("GhostMat") or bpy.data.materials.new("GhostMat"); m.diffuse_color = (*colour, 1)
    for o in obs:
        o.data.materials.clear(); o.data.materials.append(m)


def bone_markers(bones, r=0.022, name="DonorBones"):
    bm = bmesh.new()
    for n, p in bones.items():
        g = bmesh.ops.create_icosphere(bm, subdivisions=1, radius=r)
        for v in g["verts"]: v.co += p
    me = bpy.data.meshes.new(name); bm.to_mesh(me); bm.free()
    ob = bpy.data.objects.new(name, me); bpy.context.scene.collection.objects.link(ob)
    m = bpy.data.materials.get("BoneMat") or bpy.data.materials.new("BoneMat"); m.diffuse_color = (1.0, 0.85, 0.1, 1)
    me.materials.append(m)
    return ob


def bone_sticks(bones, parents, r=0.008, name="DonorSticks"):
    bm = bmesh.new()
    for c, p in parents.items():
        if c in bones and p in bones and (bones[c] - bones[p]).length > 1e-3:
            a, b = bones[p], bones[c]
            g = bmesh.ops.create_cone(bm, cap_ends=True, segments=4, radius1=r, radius2=r * 0.4, depth=(b - a).length)
            R = frame_from(b - a).to_4x4(); M = Matrix.Translation((a + b) / 2) @ R
            bmesh.ops.transform(bm, matrix=M, verts=g["verts"])
    me = bpy.data.meshes.new(name); bm.to_mesh(me); bm.free()
    ob = bpy.data.objects.new(name, me); bpy.context.scene.collection.objects.link(ob)
    m = bpy.data.materials.get("BoneMat") or bpy.data.materials.new("BoneMat"); m.diffuse_color = (1.0, 0.85, 0.1, 1)
    me.materials.append(m)
    return ob


def hide(obs, flag=True):
    for o in obs:
        o.hide_render = flag


def standard_previews(ob, donor_obs, bones, parents, out, tag, facing_az=0.0, extra_ortho=1.0, details=(), overlay_extra=()):
    """front/side/back/3-4 (flat slot colours), matcap, wire, donor ghost overlay, lineup with a 1.8 m figure.
    facing_az: the azimuth (shoot() convention) of the creature's FRONT (0 = it faces +Y / Unity +Z, 180 = -Y)."""
    pv = os.path.join(out, "previews"); os.makedirs(pv, exist_ok=True)
    sc = setup_render()
    gr = ground()
    st = stats(ob)
    mn, mx = Vector(st["bounds_min_blender"]), Vector(st["bounds_max_blender"])
    ctr = (mn + mx) / 2
    span = max(mx.x - mn.x, mx.y - mn.y, mx.z - mn.z) * 1.12 * extra_ortho
    tgt = Vector((ctr.x, ctr.y, (mn.z + mx.z) / 2))
    hide(donor_obs, True)
    files = {}
    for nm, daz, el in (("front", 0, 2), ("side", 90, 2), ("back", 180, 2)):
        p = os.path.join(pv, f"{tag}_{nm}.png"); shoot(p, tgt, facing_az + daz, el, 30, ortho=span); files[nm] = p
    p = os.path.join(pv, f"{tag}_34.png"); shoot(p, tgt, facing_az + 35, 18, span * 1.55, lens=50); files["34"] = p
    p = os.path.join(pv, f"{tag}_34back.png"); shoot(p, tgt, facing_az + 215, 22, span * 1.55, lens=50); files["34back"] = p
    for nm, dt, daz, el, osz in details:  # close-ups (ortho)
        p = os.path.join(pv, f"{tag}_detail_{nm}.png"); shoot(p, Vector(dt), facing_az + daz, el, 20, ortho=osz); files["detail_" + nm] = p
    # inside-out check: back faces culled -> an inside-out closed part shows as a hole (single-sided cards vanish from behind, expected)
    sh = sc.display.shading
    sh.show_backface_culling = True
    p = os.path.join(pv, f"{tag}_backface_cull_34.png"); shoot(p, tgt, facing_az + 35, 18, span * 1.55, lens=50); files["backface_cull_34"] = p
    p = os.path.join(pv, f"{tag}_backface_cull_34back.png"); shoot(p, tgt, facing_az + 215, 22, span * 1.55, lens=50); files["backface_cull_34back"] = p
    sh.show_backface_culling = False
    # matcap
    sh.light = 'MATCAP'; sh.studio_light = 'clay_brown.exr'; sh.color_type = 'SINGLE'; sh.single_color = (0.8, 0.8, 0.8)
    p = os.path.join(pv, f"{tag}_matcap.png"); shoot(p, tgt, facing_az + 35, 18, span * 1.55, lens=50); files["matcap"] = p
    # wire: matcap solid + dark wireframe copy (edge loops at the joints)
    sh.light = 'STUDIO'; sh.color_type = 'MATERIAL'; sh.show_cavity = False
    w = wire_copy(ob)
    saved = [m for m in ob.data.materials]
    pale = bpy.data.materials.get("PaleMat") or bpy.data.materials.new("PaleMat"); pale.diffuse_color = (0.85, 0.83, 0.8, 1)
    for i in range(len(ob.data.materials)): ob.data.materials[i] = pale
    p = os.path.join(pv, f"{tag}_wire_front.png"); shoot(p, tgt, facing_az + 0, 4, 30, ortho=span); files["wire_front"] = p
    p = os.path.join(pv, f"{tag}_wire_34.png"); shoot(p, tgt, facing_az + 35, 18, span * 1.55, lens=50); files["wire_34"] = p
    for i, m in enumerate(saved): ob.data.materials[i] = m
    hide([w], True); sh.show_cavity = True
    # donor ghost overlay: x-ray, donor in cyan, bones yellow
    hide(donor_obs, False)
    bm_ = bone_markers(bones); bs_ = bone_sticks(bones, parents)
    hide(list(overlay_extra), False)
    sh.show_xray = True; sh.xray_alpha = 0.55; sh.show_shadows = False
    for nm, daz, el in (("front", 0, 4), ("side", 90, 4)):
        p = os.path.join(pv, f"{tag}_donor_overlay_{nm}.png"); shoot(p, tgt, facing_az + daz, el, 30, ortho=span); files["overlay_" + nm] = p
    sh.show_xray = False; sh.show_shadows = True
    hide([bm_, bs_] + list(overlay_extra), True)
    # lineup: donor (left), model (centre), 1.8 m figure (right)
    for o in donor_obs: o.location.x -= (mx.x - mn.x) * 1.05 + 0.3
    fig = figure(mx.x + 0.7)
    lmn = Vector((mn.x - (mx.x - mn.x) * 1.05 - 0.3, mn.y, 0)); lmx = Vector((mx.x + 1.2, mx.y, max(mx.z, 1.8)))
    lt = (lmn + lmx) / 2; lt.z = lmx.z / 2
    p = os.path.join(pv, f"{tag}_lineup.png")
    sc.render.resolution_x, sc.render.resolution_y = 1600, 800
    shoot(p, lt, facing_az + 15, 6, 40, ortho=max((lmx.x - lmn.x) * 1.08, lmx.z * 2 * 1.12)); files["lineup"] = p
    for o in donor_obs: o.location.x += (mx.x - mn.x) * 1.05 + 0.3
    sc.render.resolution_x, sc.render.resolution_y = 1000, 1000
    hide([fig, gr], True); hide(donor_obs, True)
    # clean up preview-only objects so the saved .blend holds the model, the donor ghost and the bones
    for o in (w, fig, gr):
        bpy.data.objects.remove(o, do_unlink=True)
    hide([bm_, bs_] + list(donor_obs) + list(overlay_extra), False)
    return files, st


def markers(points, r=0.03, name="AttachMarkers", colour=(1.0, 0.1, 0.9)):
    bm = bmesh.new()
    for p in points:
        g = bmesh.ops.create_icosphere(bm, subdivisions=1, radius=r)
        for v in g["verts"]: v.co += Vector(p)
    me = bpy.data.meshes.new(name); bm.to_mesh(me); bm.free()
    ob = bpy.data.objects.new(name, me); bpy.context.scene.collection.objects.link(ob)
    m = bpy.data.materials.new(name + "Mat"); m.diffuse_color = (*colour, 1); me.materials.append(m)
    ob.hide_render = True
    return ob


def contact(paths, out_path, cols=3, cell=500, labels=None):
    """glue PNGs into a sheet with Blender's image API (no PIL in Blender's python guaranteed)."""
    import numpy as np
    ims = []
    for p in paths:
        im = bpy.data.images.load(p)
        w, h = im.size
        a = np.array(im.pixels[:], dtype=np.float32).reshape(h, w, 4)
        ims.append(a)
    rows = (len(ims) + cols - 1) // cols
    H = max(a.shape[0] for a in ims); W = max(a.shape[1] for a in ims)
    sheet = np.ones((rows * H, cols * W, 4), np.float32)
    for i, a in enumerate(ims):
        r, c = divmod(i, cols)
        r = rows - 1 - r  # blender rows start at the bottom
        sheet[r * H:r * H + a.shape[0], c * W:c * W + a.shape[1]] = a
    img = bpy.data.images.new("sheet", cols * W, rows * H, alpha=True)
    img.pixels.foreach_set(sheet.ravel())
    img.filepath_raw = out_path; img.file_format = 'PNG'; img.save()


def write_readme(out, title, asset_id, st, J, files, notes, extra_lines=()):
    """previews/README.md with MEASURED numbers only (anything else says NOT ASSESSED)."""
    pv = os.path.join(out, "previews")
    rel = lambda p: os.path.relpath(p, pv)
    L = [f"# {asset_id} {title}: step-1 shape previews", "",
         "Generated by the asset's `make_*.py` (deterministic, fixed seed). Everything below was measured by that run",
         "(Blender 5.3, `hivekit_b.stats`, `export_donor.py`); a value that was not measured says NOT ASSESSED.", "",
         "## Model (measured)", "",
         f"- Triangles: **{st['tris']}** (budget {st['budget_tris']}: {'PASS' if st['tris'] <= st['budget_tris'] else 'FAIL'}); vertices {st['verts']}",
         "- Triangles per slot: " + ", ".join(f"{k} {v}" for k, v in st["tris_per_slot"].items()),
         f"- Bounding size (Unity x, y, z = width, height, depth, m): **{st['size_unity_xyz_m'][0]} x {st['size_unity_xyz_m'][1]} x {st['size_unity_xyz_m'][2]}**",
         f"- Bounds (Blender frame, m): min {st['bounds_min_blender']} max {st['bounds_max_blender']} (lowest point z = {st['bounds_min_blender'][2]} m: on the ground plane)",
         f"- Material slots ({len(st['material_slots'])}): " + ", ".join(f"`{m}`" for m in st["material_slots"]),
         f"- UV channels: **{st['uv_channels']}** ({', '.join(st['uv_layer_names'])}; Smart UV Project, 60 deg, margin 0.004; not packed for texturing yet)",
         "- Objects in the .blend: " + ", ".join(f"`{o}`" for o in st["objects"]) + " (the model is the single mesh object named after the asset; `Donor_*` is the donor bind-pose ghost, `DonorBones`/`DonorSticks`/`AttachMarkers` are reference only)",
         "- Triangles per part: " + ", ".join(f"{k} {v}" for k, v in st["tris_per_part"].items()),
         "- Skinning / armature / weights: NOT ASSESSED (step 3). Collider: NOT ASSESSED (the donor's colliders are reused).",
         "- In-game look, FBX export, Unity import: NOT ASSESSED (no Unity in step 1).", "",
         "## Donor (measured from the 1.0.21 bundle `c4210710`)", "",
         f"- Prefab `{J['prefab']}`; root local TRS in the prefab file: {J['root_local_trs']} (the model is built in root-local space)",
         f"- Bind-pose mesh size (Unity x, y, z, m): {J['size']}; bounds min {J['bounds_min']} max {J['bounds_max']}"]
    for r in J["renderers"]:
        L.append(f"- SkinnedMeshRenderer `{r['node']}` (active {r['active']}): mesh `{r['mesh']}`, materials {r['materials']}, {r['verts']} verts / {r['tris']} tris, root bone `{r['root_bone']}`, **{len(r['bones'])} bones**")
    L.append("- Attach nodes: " + (", ".join(f"`{a['name']}`" for a in J["attach_nodes"]) or "none"))
    mbs = [m for m in J["monobehaviours"] if "raw_pptrs(byte_offset,target)" in m and m["raw_pptrs(byte_offset,target)"]]
    for m in mbs:
        L.append(f"- `{m['class']}` on `{m['node']}` references: " + ", ".join(x[1] for x in m["raw_pptrs(byte_offset,target)"]))
    L += ["- Bone list, bind positions and per-vertex weights: `../donor/donor_bones.json`, `../donor/*_weights.json`", ""]
    L += list(extra_lines)
    L += ["", "## Previews", ""]
    for k, p in files.items():
        L.append(f"- {k}: `{rel(p)}`")
    L += ["", "## Notes and what I would still change", ""] + [f"- {n}" for n in notes]
    open(os.path.join(pv, "README.md"), "w").write("\n".join(L) + "\n")


# ------------------------------------------------------------------ v2: armour plates, pegs, honeycomb
def wrap_plate(a, b, t0, t1, ang0, ang1, radius_fn, ref, thick, seed, nu=5, nv=3, bulge=0.012, chip=0.25,
               offset_fn=None, lip=None, flare=0.0, rough=0.35, jag=0.0, blob=0.0):
    """a curved bark armour plate wrapped round the axis a->b: t in [t0,t1] along the axis, angle in [ang0,ang1]
    (radians, 0 = `ref` direction). radius_fn(t, ang) gives the inner radius; the plate is `thick` thick with a closed
    rim, bulges outward in the middle, has chipped (jittered, corner-cut) edges, and its lower edge (t0 side) flares
    out by `flare` so stacked rows shingle. lip: (builder, width) adds a BlightGlow strip tucked under the t0 edge."""
    rnd = random.Random(seed)
    a, b = Vector(a), Vector(b); ax = (b - a); L = ax.length; ax.normalize()
    r0 = Vector(ref); r0 = (r0 - ax * r0.dot(ax)).normalized(); side = ax.cross(r0)
    def pt(t, ang, extra):
        c = a + ax * L * t + (offset_fn(t) if offset_fn else Vector())
        d = r0 * math.cos(ang) + side * math.sin(ang)
        return c + d * (radius_fn(t, ang) + extra)
    bm = _bm(); uv = bm.loops.layers.uv["UVMap"]
    grid_o, grid_i = [], []
    # blob > 0: an organic outline: each row gets its own angular limits (narrower toward the top and bottom rows, noisy)
    lim = []
    for j in range(nv + 1):
        v = j / nv; taper = (1 - math.sin(math.pi * v)) ** 1.3
        sl = blob * (0.5 * taper + 0.22 * (0.5 + 0.5 * noise.noise(Vector((v * 3.3, 0.7, seed * 0.11)))))
        sr = blob * (0.5 * taper + 0.22 * (0.5 + 0.5 * noise.noise(Vector((v * 3.1, 4.2, seed * 0.13)))))
        lim.append((sl, 1 - sr))
    for j in range(nv + 1):
        ro, ri = [], []
        for i in range(nu + 1):
            u, v = i / nu, j / nv
            edge = (i in (0, nu)) or (j in (0, nv))
            du = rnd.uniform(-chip, chip) / nu if edge and j not in (0, nv) else 0.0
            dv = rnd.uniform(-chip, chip) / nv if edge and i not in (0, nu) else 0.0
            if (i in (0, nu)) and (j in (0, nv)):   # cut corners
                du = (0.35 if i == 0 else -0.35) / nu; dv = (0.35 if j == 0 else -0.35) / nv
            uu = min(max(u + du, 0), 1); vv = min(max(v + dv, 0), 1)
            if blob: uu = lim[j][0] + (lim[j][1] - lim[j][0]) * uu
            if jag and j == 0 and 0 < i < nu and i % 2 == 1:   # cracked, sharp lower edge: alternate vertices pulled down to points
                vv -= jag * rnd.uniform(0.7, 1.3)
            t = t0 + (t1 - t0) * vv; ang = ang0 + (ang1 - ang0) * uu
            bul = bulge * math.sin(math.pi * uu) * math.sin(math.pi * vv) + flare * (1 - vv) ** 2
            n_ = noise.noise(Vector((uu * 3.1, vv * 2.7, seed * 0.37))) * thick * rough
            ro.append(bm.verts.new(pt(t, ang, thick + bul + n_)))
            ri.append(bm.verts.new(pt(t, ang, bul * 0.6 + flare * 0.5 * (1 - vv) ** 2)))
        grid_o.append(ro); grid_i.append(ri)
    for j in range(nv):
        for i in range(nu):
            f = bm.faces.new((grid_o[j][i], grid_o[j][i + 1], grid_o[j + 1][i + 1], grid_o[j + 1][i]))
            for lp, (uu, vv) in zip(f.loops, ((i, j), (i + 1, j), (i + 1, j + 1), (i, j + 1))):
                lp[uv].uv = (uu / nu, vv / nv)
            bm.faces.new((grid_i[j][i], grid_i[j + 1][i], grid_i[j + 1][i + 1], grid_i[j][i + 1]))
    ring = [(0, i) for i in range(nu)] + [(j, nu) for j in range(nv)] + [(nv, i) for i in range(nu, 0, -1)] + [(j, 0) for j in range(nv, 0, -1)]
    for k in range(len(ring)):
        (j0, i0), (j1, i1) = ring[k], ring[(k + 1) % len(ring)]
        bm.faces.new((grid_o[j0][i0], grid_i[j0][i0], grid_i[j1][i1], grid_o[j1][i1]))
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    if lip is not None:
        Bld, w = lip
        lb = _bm(); rows = []
        for i in range(nu + 1):
            ang = ang0 + (ang1 - ang0) * (0.08 + 0.84 * i / nu)
            tt = t0 + (t1 - t0) * 0.12
            rows.append([lb.verts.new(pt(tt, ang, thick * 0.2)), lb.verts.new(pt(t0 - w / L, ang, thick * 0.55 + flare * 0.6))])
        for i in range(nu):
            lb.faces.new((rows[i][0], rows[i + 1][0], rows[i + 1][1], rows[i][1]))
        bmesh.ops.recalc_face_normals(lb, faces=lb.faces)
        Bld.add(lb, "BlightGlow", "seamglow")
        # a reversed twin so the glow strip is visible from both sides
        tw = lb.copy(); bmesh.ops.reverse_faces(tw, faces=tw.faces)
        for v in tw.verts: v.co += (v.co - (a + ax * ((v.co - a).dot(ax)))).normalized() * 0.002
        Bld.add(tw, "BlightGlow", "seamglow")
    return bm


def peg(loc, nrm, r=0.012, proud=0.012, sink=0.04, seg=4):
    """a wooden peg: a short square-ish post standing `proud` out of a surface, with a bevelled head."""
    n = Vector(nrm).normalized()
    return lathe_ring(Vector(loc), n, [(r, -sink), (r, proud * 0.7), (0.002, proud), (0.002, -sink)], seg=seg)


def hex_cluster(B, surf, centre, normal, cell_r, rings, seed, proud=0.005, skip=(), taken=None, eye_cells=()):
    """a honeycomb cluster of brood cells: hex-grid offsets in the tangent plane of (centre, normal), each re-seated
    on the body by raycast, each a hexagonal bark rim round a BlightGlow dome. Returns the number of cells placed."""
    rnd = random.Random(seed)
    n = Vector(normal).normalized(); F = frame_from(n)
    pitch = cell_r * 2.45
    placed = 0
    for q in range(-rings, rings + 1):
        for r in range(max(-rings, -q - rings), min(rings, -q + rings) + 1):
            if (q, r) in skip: continue
            x = pitch * (q + r * 0.5); y = pitch * r * 0.8660254
            p = Vector(centre) + F.col[0] * x + F.col[1] * y
            h = surf.hit_toward(p + n * 0.5, p - n * 0.3)
            if h is None: continue
            rr = cell_r * (1 + rnd.uniform(-0.12, 0.1))
            loc, nn = h
            if taken is not None:   # no cell inside another cluster's cell
                if any((loc - q).length < (rr + qr) * 1.15 for q, qr in taken): continue
                taken.append((loc.copy(), rr))
            nn = (nn + n).normalized()
            dome = uvsphere(loc + nn * (proud - 0.3 * rr), rr * 0.9, seg=6, rings=3)
            # orient the dome's pole along the normal
            R = Vector((0, 0, 1)).rotation_difference(nn).to_matrix().to_4x4()
            c0 = loc + nn * (proud - 0.3 * rr)
            bmesh.ops.transform(dome, matrix=Matrix.Translation(c0) @ R @ Matrix.Translation(-c0), verts=dome.verts)
            if placed in eye_cells:   # a brood cell holding an eye instead of glow
                dome.free()
                dome = uvsphere(loc + nn * (proud + 0.15 * rr), rr * 0.95, seg=8, rings=5)
                B.add(dome, "HiveEye", "broodeye")
            else:
                B.add(dome, "BlightGlow", "broodcell")
            rin, rout = rr * 0.92, rr * 1.22
            prof = [(rin, proud), (rout, proud - 0.004), (rout * 1.04, -0.03)]
            rim = lathe_ring(loc, nn, prof, seg=6, seed=seed + placed, jitter=0.03)
            # align the hex to the grid
            B.add(rim, "HiveBark", "broodrim")
            placed += 1
    return placed


# ------------------------------------------------------------------ v3: the Hive "growth" (owner 2026-11-21: "loose the trees, its more of a groth")
def growth_clump(B, surf, centre, cast_dir, radius, seed, n=40, length=(0.15, 0.4), width=(0.035, 0.06), out_push=0.35,
                 segs=4, sink=0.02, gravity=Vector((0, 0, -1)), label="growth"):
    """a dense shaggy clump of needle fronds spilling out of the bark and hanging DOWN (the Hive's buried pines show only
    as this clump under the mass): no trunk, no tiers. Each frond is rooted `sink` inside the surface found by casting
    toward the body along -cast_dir from a disc of `radius` round `centre`, leaves along the surface normal, then droops
    under `gravity`; V-folded ribbon with serrated (alternating-width) edges. Returns the number of fronds placed."""
    rnd = random.Random(seed)
    cd = Vector(cast_dir).normalized(); F = frame_from(cd); g = Vector(gravity).normalized()
    placed = 0
    for i in range(n * 3):
        if placed >= n: break
        a = rnd.uniform(0, 2 * math.pi); r = radius * math.sqrt(rnd.uniform(0, 1))
        p = Vector(centre) + (F.col[0] * math.cos(a) + F.col[1] * math.sin(a)) * r
        h = surf.hit_toward(p + cd * 0.9, p - cd * 0.4)
        if h is None: continue
        loc, nrm = h
        L = rnd.uniform(*length); w = rnd.uniform(*width) * 1.45
        op = out_push
        if rnd.random() < 0.4:     # short bushy fronds pushed outward, layering over the long hanging ones
            L *= 0.45; op = 0.75
        out = (nrm * op + g * (1 - op)).normalized()
        lat = nrm.cross(g)
        if lat.length < 1e-3: lat = F.col[0]
        lat.normalize()
        sway = lat * rnd.uniform(-0.25, 0.25) * L
        pts = []
        for s in range(segs + 1):
            t = s / segs
            q = loc - nrm * sink + out * L * 0.35 * t + g * L * (t ** 1.25) * 0.9 + sway * t * t + nrm * L * 0.08 * math.sin(math.pi * t)
            pts.append(q)
        bm = _bm(); uv = bm.loops.layers.uv["UVMap"]; rows = []
        roll = rnd.uniform(0, math.pi)
        for s, q in enumerate(pts):
            t = s / segs
            tan = (pts[min(s + 1, segs)] - pts[max(s - 1, 0)]).normalized()
            side = (lat * math.cos(roll) + nrm * math.sin(roll)); side = (side - tan * side.dot(tan)).normalized()
            fold = tan.cross(side).normalized()
            ww = w * (1 - 0.7 * t) * (1.0 if s % 2 == 1 else 0.38) * (0.45 if s == 0 else 1.0)
            rows.append([bm.verts.new(q - side * ww), bm.verts.new(q + fold * ww * 0.4), bm.verts.new(q + side * ww)])
        for s in range(segs):
            for k in range(2):
                f = bm.faces.new((rows[s][k], rows[s][k + 1], rows[s + 1][k + 1], rows[s + 1][k]))
                for lp, (uu, vv) in zip(f.loops, ((k, s), (k + 1, s), (k + 1, s + 1), (k, s + 1))):
                    lp[uv].uv = (uu / 2, vv / segs)
        B.add(bm, "HiveFoliage", label)
        placed += 1
    return placed


# ------------------------------------------------------------------ v3 "evil" helpers
def hook_claw(base, direction, length, r0, curl, seg=4, sink=0.02):
    """a hooked claw / root tip: a tapering tube that leaves along `direction` and hooks hard toward `curl` at the end."""
    d = Vector(direction).normalized(); c = Vector(curl).normalized()
    pts = [Vector(base) - d * sink]
    for s in range(1, 6):
        t = s / 5
        pts.append(Vector(base) + d * length * t * (1 - 0.25 * t * t) + c * length * 0.55 * t ** 2.4)
    return tube(pts, [r0, r0 * 0.9, r0 * 0.72, r0 * 0.5, r0 * 0.3, r0 * 0.06], seg=seg, seed=0, jitter=0.05, cap1=False)


def splinter(base, direction, length, w, seed, sink=0.03, bend=0.06):
    """a jagged timber splinter spike driven into the bark."""
    d = Vector(direction).normalized()
    return beam(Vector(base) - d * sink, Vector(base) + d * length, w, w * 0.8, seed, segs=2, taper=0.25, point=True, bend=bend, chip=0.01,
                up=Vector((0, 0, 1)) if abs(d.z) < 0.9 else Vector((1, 0, 0)))
