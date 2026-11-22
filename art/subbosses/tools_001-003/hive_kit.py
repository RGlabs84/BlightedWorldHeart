"""hive_kit: shared Blender helpers for the BlightedHeart Hive sub-bosses ASSET-001..003 (step 1: shapes only).

Frame: Blender metres, x = Unity x (creature's right), y = Unity z (creature forward), z = Unity y (up).
Ground at z = 0, origin at ground centre. Six material slots by NAME (art/ASSETS.md), flat placeholder colours.
Everything is deterministic: random.Random(seed) and mathutils.noise at seeded offsets.

Imported by ASSET-00N_*/build_*.py (sys.path insert of this folder). Not a stdlib name on purpose.
"""
import bpy, bmesh, math, random, os, json
import numpy as np
from mathutils import Vector, Matrix, noise
from mathutils.bvhtree import BVHTree

SLOTS = ["HiveBark", "HiveTimber", "HiveMoss", "HiveEye", "HiveFoliage", "BlightGlow"]
HEX = {"HiveBark": "5A4630", "HiveTimber": "9C8E78", "HiveMoss": "4F6B2E", "HiveEye": "FF2A40",
       "HiveFoliage": "2F5A2A", "BlightGlow": "7CFF3A"}
EMIT = {"HiveEye": 3.0, "BlightGlow": 2.5}


def srgb2lin(c):
    return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4


def hexcol(h):
    return tuple(srgb2lin(int(h[i:i + 2], 16) / 255.0) for i in (0, 2, 4))


def u2b(v):
    return Vector((v[0], v[2], v[1]))


def rand_unit(rng):
    while True:
        v = Vector((rng.uniform(-1, 1), rng.uniform(-1, 1), rng.uniform(-1, 1)))
        if 0.05 < v.length <= 1.0:
            return v.normalized()


def frame(fwd, up=(0, 0, 1)):
    """4x4 rotation whose +Y is fwd and +Z is as close to up as possible"""
    f = Vector(fwd).normalized()
    u = Vector(up)
    if abs(f.dot(u.normalized())) > 0.98:
        u = Vector((1, 0, 0)) if abs(f.x) < 0.9 else Vector((0, 1, 0))
    x = f.cross(u).normalized()
    z = x.cross(f).normalized()
    m = Matrix((x, f, z)).transposed()
    return m.to_4x4()


def perp_basis(t, ref=None):
    t = Vector(t).normalized()
    r = Vector(ref) if ref is not None else (Vector((0, 0, 1)) if abs(t.z) < 0.9 else Vector((1, 0, 0)))
    n = (r - t * r.dot(t))
    if n.length < 1e-6:
        r = Vector((1, 0, 0)) if abs(t.x) < 0.9 else Vector((0, 1, 0))
        n = r - t * r.dot(t)
    n.normalize()
    return n, t.cross(n)


# ------------------------------------------------------------------ primitives (each returns a bmesh)
def lump(center, radii, rot=None, subdiv=2, seed=0, chops=7, chop=0.16, creases=1, crease=0.14, bump=0.10):
    """faceted fused bark mass: noisy icosphere, deep partial creases, flat chopped facets (like TheHive's 'low' meshes)"""
    rng = random.Random(seed)
    bm = bmesh.new()
    bmesh.ops.create_icosphere(bm, subdivisions=subdiv, radius=1.0)
    off = Vector((rng.uniform(-50, 50), rng.uniform(-50, 50), rng.uniform(-50, 50)))
    for v in bm.verts:
        n = v.co.normalized()
        v.co = n * (1.0 + bump * noise.noise(n * 1.7 + off))
    for _ in range(creases):
        pn = rand_unit(rng); h = rng.uniform(-0.3, 0.3); q = rand_unit(rng)
        for v in bm.verts:
            dd = v.co.dot(pn) - h
            fade = 0.5 + 0.5 * max(-1.0, min(1.0, v.co.dot(q) * 2.0))
            v.co *= (1.0 - crease * math.exp(-(dd / 0.15) ** 2) * fade)
    for _ in range(chops):
        pn = rand_unit(rng); h = rng.uniform(1.0 - chop, 1.0 - chop * 0.35)
        for v in bm.verts:
            s = v.co.dot(pn)
            if s > h:
                v.co -= pn * (s - h)
    R = rot.to_4x4() if rot is not None else Matrix.Identity(4)
    M = Matrix.Translation(Vector(center)) @ R @ Matrix.Diagonal((radii[0], radii[1], radii[2], 1.0))
    bmesh.ops.transform(bm, matrix=M, verts=bm.verts)
    return bm


def tube(pts, radii, sides=8, seed=0, ridge=0.12, jit=0.04, cap0=True, cap1=True, ref=None, twist=0.0, closed_loop=False):
    """lofted tube along a polyline; per-side ridge factor gives bark furrows along the length; twist spirals them"""
    rng = random.Random(seed)
    pts = [Vector(p) for p in pts]
    n = len(pts)
    side_f = [1.0 + ridge * rng.uniform(-1, 1) for _ in range(sides)]
    tans = []
    for i in range(n):
        if closed_loop:
            a, b = pts[(i - 1) % n], pts[(i + 1) % n]
        else:
            a, b = pts[max(i - 1, 0)], pts[min(i + 1, n - 1)]
        tans.append((b - a).normalized())
    N, _ = perp_basis(tans[0], ref)
    bm = bmesh.new()
    rings = []
    for i in range(n):
        t = tans[i]
        N = (N - t * N.dot(t)).normalized()
        B = t.cross(N)
        ring = []
        for k in range(sides):
            a = 2 * math.pi * k / sides + twist * i
            r = radii[i] * side_f[k] * (1.0 + jit * rng.uniform(-1, 1))
            ring.append(bm.verts.new(pts[i] + (N * math.cos(a) + B * math.sin(a)) * r))
        rings.append(ring)
    segs = n if closed_loop else n - 1
    for i in range(segs):
        r0, r1 = rings[i], rings[(i + 1) % n]
        for k in range(sides):
            k2 = (k + 1) % sides
            bm.faces.new((r0[k], r0[k2], r1[k2], r1[k]))
    if not closed_loop:
        if cap0: bm.faces.new(list(reversed(rings[0])))
        if cap1: bm.faces.new(rings[-1])
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    return bm


def limb_pts(joints, radii, ts=(0.0, 0.2, 0.5, 0.8)):
    """points + radii along a bone chain with an edge loop AT each joint and one either side of it (t=0.2 / 0.8)"""
    P, R = [], []
    for i in range(len(joints) - 1):
        a, b = Vector(joints[i]), Vector(joints[i + 1])
        for t in ts:
            P.append(a.lerp(b, t)); R.append(radii[i] + (radii[i + 1] - radii[i]) * t)
    P.append(Vector(joints[-1])); R.append(radii[-1])
    return P, R


def curve_pts(p0, p1, bend, n):
    """n+1 points from p0 to p1 bowed by the vector bend at the middle (quadratic)"""
    p0, p1, bend = Vector(p0), Vector(p1), Vector(bend)
    return [p0.lerp(p1, i / n) + bend * (4 * (i / n) * (1 - i / n)) for i in range(n + 1)]


def beam(p0, p1, w, h, up=(0, 0, 1), seed=0, chamfer=0.28, rings=3, warp=0.015, end_jit=0.35, jit=0.03):
    """hewn timber: chamfered (bevelled) rectangular section, slight warp, uneven saw-cut ends"""
    rng = random.Random(seed)
    p0, p1 = Vector(p0), Vector(p1)
    ax = p1 - p0; L = ax.length; t = ax / L
    N, B = perp_basis(t, up)       # N ~ up (height h), B across (width w)
    c = chamfer * min(w, h)
    prof = [(w / 2 - c, h / 2), (w / 2, h / 2 - c), (w / 2, -h / 2 + c), (w / 2 - c, -h / 2),
            (-w / 2 + c, -h / 2), (-w / 2, -h / 2 + c), (-w / 2, h / 2 - c), (-w / 2 + c, h / 2)]
    wn, wb = rng.uniform(-1, 1), rng.uniform(-1, 1)
    tilt0 = (rng.uniform(-1, 1), rng.uniform(-1, 1)); tilt1 = (rng.uniform(-1, 1), rng.uniform(-1, 1))
    bm = bmesh.new(); R = []
    for i in range(rings + 1):
        s = i / rings
        c0 = p0 + ax * s + (N * wn + B * wb) * warp * L * (4 * s * (1 - s))
        ring = []
        for (x, y) in prof:
            x2 = x * (1 + jit * rng.uniform(-1, 1)); y2 = y * (1 + jit * rng.uniform(-1, 1))
            sh = 0.0
            if i == 0: sh = (x / w * tilt0[0] + y / h * tilt0[1]) * end_jit * min(w, h)
            if i == rings: sh = (x / w * tilt1[0] + y / h * tilt1[1]) * end_jit * min(w, h)
            ring.append(bm.verts.new(c0 + B * x2 + N * y2 + t * sh))
        R.append(ring)
    for i in range(rings):
        for k in range(8):
            k2 = (k + 1) % 8
            bm.faces.new((R[i][k], R[i][k2], R[i + 1][k2], R[i + 1][k]))
    bm.faces.new(list(reversed(R[0]))); bm.faces.new(R[-1])
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    return bm


def lashing(center, axis, hw, hh, width, up=(0, 0, 1), turns=3.0, rope_r=0.02, seg_per_turn=10, sides=4, sink=0.35, seed=0, p=4.0):
    """rope wound round a (rounded-)rectangular section hw x hh (half sizes): a superellipse helix that hugs the
    timber, sunk by sink*rope_r so it never floats"""
    axis = Vector(axis).normalized()
    N, B = perp_basis(axis, up)
    pts = []
    nseg = max(4, int(turns * seg_per_turn))
    for i in range(nseg + 1):
        s = i / nseg; a = 2 * math.pi * turns * s
        ca, sa = math.cos(a), math.sin(a)
        r = (abs(ca / (hw)) ** p + abs(sa / (hh)) ** p) ** (-1.0 / p)
        off = rope_r * (1.0 - sink)
        pts.append(Vector(center) + axis * (s - 0.5) * width + (B * ca + N * sa) * (r + off))
    return tube(pts, [rope_r] * len(pts), sides=sides, ridge=0.0, jit=0.0, seed=seed)


def ring_tube(center, normal, R, rr, segs=10, sides=4, squash=1.0):
    """a torus round `normal`; squash < 1 narrows it along the up-most in-plane axis (a slit socket)"""
    n = Vector(normal).normalized()
    N, B = perp_basis(n, (0, 0, 1) if abs(n.z) < 0.9 else (0, 1, 0))
    pts = [Vector(center) + (N * math.cos(2 * math.pi * i / segs) * squash + B * math.sin(2 * math.pi * i / segs)) * R for i in range(segs)]
    return tube(pts, [rr] * segs, sides=sides, ridge=0, jit=0, closed_loop=True)


def sphere(center, r, segs=8, rings=6, scale=(1, 1, 1)):
    bm = bmesh.new()
    bmesh.ops.create_uvsphere(bm, u_segments=segs, v_segments=rings, radius=r)
    bmesh.ops.transform(bm, matrix=Matrix.Translation(Vector(center)) @ Matrix.Diagonal((*scale, 1)), verts=bm.verts)
    return bm


def ellipsoid(center, radii, normal, segs=7, rings=5):
    """a sphere scaled in the frame of `normal` (x = across, y = up-most in-plane axis, z = normal)"""
    n = Vector(normal).normalized()
    N, B = perp_basis(n, (0, 0, 1) if abs(n.z) < 0.9 else (0, 1, 0))
    R = Matrix((-B, N, n)).transposed().to_4x4()          # right-handed (B = n x N, so (B, N, n) would mirror)
    bm = bmesh.new()
    bmesh.ops.create_uvsphere(bm, u_segments=segs, v_segments=rings, radius=1.0)
    bmesh.ops.transform(bm, matrix=Matrix.Translation(Vector(center)) @ R @ Matrix.Diagonal((radii[0], radii[1], radii[2], 1)), verts=bm.verts)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    return bm


def spike(base, tip, r0, sides=5, seed=0, bend=(0, 0, 0), n=4):
    pts = curve_pts(base, tip, bend, n)
    rad = [r0 * (1 - 0.85 * i / n) for i in range(n + 1)]
    return tube(pts, rad, sides=sides, seed=seed, ridge=0.1, jit=0.05)


# ------------------------------------------------------------------ the model: parts by slot, surface helpers
class Model:
    def __init__(self, name, seed):
        self.name = name
        self.parts = []
        self.rng = random.Random(seed)
        self.notes = []
        self.sharp_angle = math.radians(25)      # v3: sharper cracked-bark edges

    def add(self, name, bm, slot, body=False, closed=True, smooth=False):
        assert slot in SLOTS, slot
        for f in bm.faces:
            f.smooth = smooth
        self.parts.append(dict(name=name, bm=bm, slot=slot, body=body, closed=closed))
        return bm

    def bvh(self, prefixes=None):
        out = bmesh.new()
        for p in self.parts:
            ok = p["body"] if prefixes is None else any(p["name"].startswith(x) for x in prefixes)
            if ok:
                me = bpy.data.meshes.new("_t"); p["bm"].to_mesh(me); out.from_mesh(me); bpy.data.meshes.remove(me)
        t = BVHTree.FromBMesh(out)
        out.free()
        return t

    def bvh_exact(self, names):
        return self.bvh([n for n in names]) if False else self._bvh_names(set(names))

    def _bvh_names(self, names):
        out = bmesh.new()
        for p in self.parts:
            if p["name"] in names:
                me = bpy.data.meshes.new("_t"); p["bm"].to_mesh(me); out.from_mesh(me); bpy.data.meshes.remove(me)
        t = BVHTree.FromBMesh(out)
        out.free()
        return t

    # -- surface details
    def surf(self, bvh, target, out_dir, far=30.0):
        d = Vector(out_dir).normalized()
        loc, nrm, _, _ = bvh.ray_cast(Vector(target) + d * far, -d, far * 2)
        return loc, nrm

    def eye(self, bvh, target, out_dir, r, proud, name="eye", segs=8, slit=1.0):
        """eye node seated in a raised bark socket rim: the rim's top stands `proud` above the bark, the eye sphere
        is sunk 35 % of its radius below the surface"""
        loc, n = self.surf(bvh, target, out_dir)
        if loc is None:
            self.notes.append(f"eye {name}: ray missed at {tuple(round(x, 2) for x in target)}")
            return None
        rr = max(r * 0.3, proud * 1.2)
        # v3: cheaper eye (7x5 sphere, 4-sided rim); slit < 1 narrows the socket and the eye to a horizontal slit
        self.add(name + "_rim", ring_tube(loc + n * (proud - rr), n, r * 1.12, rr, segs=segs, sides=4, squash=slit), "HiveBark", smooth=True)
        self.add(name, ellipsoid(loc - n * (r * 0.35), (r, r * slit, r), n, segs=7, rings=5), "HiveEye", smooth=True)
        return loc, n

    def drape(self, bvh, center, out_dir, radius, thick, name="moss", rings=3, segs=11, seed=0, slot="HiveMoss", up=None, max_drop=0.6):
        """a cap that hugs the surface: rays from a disc above `center` along -out_dir; inner rings stand `thick`
        proud (+ lumpy), the ragged outer ring is tucked under the surface so the cap never floats"""
        rng = random.Random(seed)
        d = Vector(out_dir).normalized()
        N, B = perp_basis(d, up)
        bm = bmesh.new()
        origin = Vector(center) + d * 30.0
        ring_v = []
        c_loc, c_n = None, None
        loc, n, _, _ = bvh.ray_cast(origin, -d, 60)
        if loc is None:
            self.notes.append(f"{name}: centre ray missed"); bm.free(); return None
        top_c = bm.verts.new(loc + n * thick * (1.25 + 0.2 * rng.random()))
        bot_c = bm.verts.new(loc - n * thick * 1.5)
        rag = [rng.uniform(0.75, 1.15) for _ in range(segs)]
        top, bot = [], []
        for ri in range(1, rings + 1):
            f = ri / rings
            rt, rb = [], []
            for k in range(segs):
                a = 2 * math.pi * (k + 0.5 * (ri % 2)) / segs
                rr = radius * f * (rag[k] if ri == rings else (1 + 0.1 * rng.uniform(-1, 1)))
                o = origin + (N * math.cos(a) + B * math.sin(a)) * rr
                hl, hn, _, _ = bvh.ray_cast(o, -d, 60)
                shrink = 1.0
                while (hl is None or (hl - loc).dot(d) < -max_drop * radius) and shrink > 0.25:
                    # missed the mass, or fell down a cliff: pull the vertex inward until it lands on the mass
                    shrink -= 0.15
                    o = origin + (N * math.cos(a) + B * math.sin(a)) * rr * shrink
                    hl, hn, _, _ = bvh.ray_cast(o, -d, 60)
                if hl is None:
                    hl, hn = loc, n
                lift = 0.3 if ri == rings else (0.8 + 0.5 * rng.random())
                rt.append(bm.verts.new(hl + hn * thick * lift))
                rb.append(bm.verts.new(hl - hn * thick * 1.5))
            top.append(rt); bot.append(rb)
        # closed slab: lumpy top, sunk underside, sewn edge (no open back faces anywhere)
        for k in range(segs):
            k2 = (k + 1) % segs
            bm.faces.new((top_c, top[0][k], top[0][k2]))
            bm.faces.new((bot_c, bot[0][k2], bot[0][k]))
        for ri in range(rings - 1):
            for k in range(segs):
                k2 = (k + 1) % segs
                bm.faces.new((top[ri][k], top[ri + 1][k], top[ri + 1][k2], top[ri][k2]))
                bm.faces.new((bot[ri][k2], bot[ri + 1][k2], bot[ri + 1][k], bot[ri][k]))
        for k in range(segs):
            k2 = (k + 1) % segs
            bm.faces.new((top[-1][k], bot[-1][k], bot[-1][k2], top[-1][k2]))
        bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
        bm.normal_update()
        if sum(fc.normal.dot(d) * fc.calc_area() for fc in bm.faces if fc.normal.dot(d) > 0) < 1e-9:
            for fc in bm.faces: fc.normal_flip()
        self.add(name, bm, slot, closed=True)
        return bm

    def vein(self, bvh, path, out_dir, r, name="vein", sub=3, taper=0.45, seed=0, sink=0.4, slot="BlightGlow", sides=4):
        """glowing blight crack: a thin 4-sided strand following the surface, sunk 40 % (stands 0.6 r proud)"""
        pts = []
        P = [Vector(p) for p in path]
        dense = []
        for i in range(len(P) - 1):
            for s in range(sub):
                dense.append(P[i].lerp(P[i + 1], s / sub))
        dense.append(P[-1])
        for p in dense:
            loc, n = self.surf(bvh, p, out_dir)
            if loc is not None:
                pts.append(loc - n * r * sink)
        if len(pts) < 2:
            self.notes.append(f"{name}: too few hits"); return None
        rad = [r * (1 - (1 - taper) * i / (len(pts) - 1)) for i in range(len(pts))]
        self.add(name, tube(pts, rad, sides=sides, ridge=0.15, seed=seed), slot)
        return pts

    def pine(self, base, direction, height, name="pine", seed=0, tiers=4, sink=0.25, droop=0.35, points=9):
        """small pine: bark trunk (base sunk `sink`*height into the body) + star-section foliage cones"""
        rng = random.Random(seed)
        d = Vector(direction).normalized()
        N, B = perp_basis(d)
        base = Vector(base)
        trunk = [base - d * sink * height, base, base + d * height * 0.5, base + d * height * 0.97]
        self.add(name + "_trunk", tube(trunk, [0.05 * height, 0.045 * height, 0.03 * height, 0.008 * height], sides=5, seed=seed),
                 "HiveBark")
        for i in range(tiers):
            s0 = 0.18 + 0.62 * i / tiers
            Rr = 0.34 * height * (1 - 0.62 * i / tiers) * rng.uniform(0.9, 1.1)
            hgt = 0.36 * height
            bm = bmesh.new()
            apex = bm.verts.new(base + d * height * (s0 + hgt / height))
            under = bm.verts.new(base + d * height * (s0 + 0.06))
            rim = []
            rot = rng.uniform(0, 6.28)
            for k in range(points * 2):
                a = rot + 2 * math.pi * k / (points * 2)
                rr = Rr * (1.0 if k % 2 == 0 else 0.55)
                pdroop = droop * rr if k % 2 == 0 else 0.0
                rim.append(bm.verts.new(base + d * (height * s0 - pdroop) + (N * math.cos(a) + B * math.sin(a)) * rr))
            M = len(rim)
            for k in range(M):
                bm.faces.new((apex, rim[k], rim[(k + 1) % M]))
                bm.faces.new((under, rim[(k + 1) % M], rim[k]))
            bm.normal_update()
            for fc in bm.faces:
                ctr = fc.calc_center_median()
                axis_pt = base + d * d.dot(ctr - base)
                if fc.normal.dot(ctr - axis_pt) < -1e-6 and fc.normal.dot(d) < 0.9:
                    pass
            bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
            self.add(f"{name}_tier{i}", bm, "HiveFoliage")

    # ------------------------------------------------------------ v3 menace helpers
    def teeth(self, bases, tips, r0, name, seed=0, broken=0.3, slot="HiveTimber"):
        """uneven splinter teeth: lengths 0.6-1.35x, random lean; `broken` share snapped off short with a blunt end"""
        rng = random.Random(seed)
        for k, (b, t) in enumerate(zip(bases, tips)):
            b, t = Vector(b), Vector(t)
            d = t - b
            L = rng.uniform(0.6, 1.35)
            jit = Vector((rng.uniform(-1, 1), rng.uniform(-1, 1), rng.uniform(-1, 1))) * d.length * 0.12
            tip = b + d * L + jit
            if rng.random() < broken:
                tip = b + (tip - b) * 0.55
                bm = tube([b, b.lerp(tip, 0.5), tip], [r0, r0 * 0.8, r0 * 0.55], sides=4, seed=seed + k, ridge=0.2, jit=0.1)
            else:
                bm = spike(b, tip, r0 * rng.uniform(0.85, 1.2), sides=4, n=2, seed=seed + k)
            self.add(f"{name}_{k}", bm, slot)

    def splinters(self, bvh, targets, out_dir, length, r0, name, seed=0, lean=(0, 0, 0), slot="HiveTimber", sink=0.3):
        """jagged timber splinters driven out of the bark along a row of targets (each sunk 30 % of its length)"""
        rng = random.Random(seed)
        for k, t in enumerate(targets):
            loc, n = self.surf(bvh, t, out_dir)
            if loc is None:
                continue
            L = length * rng.uniform(0.6, 1.3)
            d = (n + Vector(lean) + Vector((rng.uniform(-1, 1), rng.uniform(-1, 1), rng.uniform(-1, 1))) * 0.25).normalized()
            self.add(f"{name}_{k}", spike(loc - d * L * sink, loc + d * L, r0 * rng.uniform(0.8, 1.2), sides=4, n=3, seed=seed + k,
                                          bend=d.cross(n) * L * 0.08), slot)

    def claw(self, base, direction, length, r0, name, seed=0, hook=0.35, down=(0, 0, -1), slot="HiveBark", body=True):
        """a long hooked root claw: tapers to a point, its last third curling toward `down`"""
        b = Vector(base); d = Vector(direction).normalized()
        dn = Vector(down).normalized()
        pts = [b, b + d * length * 0.4, b + d * length * 0.75 + dn * length * hook * 0.35, b + d * length * 0.95 + dn * length * hook]
        self.add(name, tube(pts, [r0, r0 * 0.75, r0 * 0.45, r0 * 0.12], sides=5, seed=seed, ridge=0.15, twist=0.3), slot, body=body)

    # ------------------------------------------------------------ the Hive growth (v3): shaggy needle clumps, no trees
    def frond(self, path, width, side_dir, seed=0, fold=0.32, thick=0.4, serr=0.45):
        """one closed, thin, V-folded needle blade along `path` (root first). The blade's width runs along side_dir (kept
        perpendicular to the path), its face along tangent x side, so it turns smoothly from facing up to facing out as it
        falls. Chevron section (edge, spine, edge, under-spine), serrated width (alternating rings), fine tip. Closed."""
        rng = random.Random(seed)
        bm = bmesh.new()
        n = len(path)
        rings = []
        sd = Vector(side_dir).normalized()
        for i, c in enumerate(path):
            t = i / (n - 1)
            tan = (path[min(i + 1, n - 1)] - path[max(i - 1, 0)]).normalized()
            side = (sd - tan * sd.dot(tan))
            if side.length < 1e-4:
                side = perp_basis(tan)[1]
            side.normalize()
            o = tan.cross(side).normalized()
            w = width * (0.35 + 0.65 * math.sin(math.pi * min(1.0, t * 1.6 + 0.15))) * (1.0 - 0.8 * t ** 2)
            w *= (1.0 if i % 2 == 0 else serr) * rng.uniform(0.85, 1.15)
            if i == 0:
                w = width * 0.4
            f = w * fold
            rings.append([bm.verts.new(c - side * w / 2), bm.verts.new(c + o * f), bm.verts.new(c + side * w / 2),
                          bm.verts.new(c + o * f * (1 - thick))])
        for i in range(n - 1):
            for k in range(4):
                k2 = (k + 1) % 4
                bm.faces.new((rings[i][k], rings[i][k2], rings[i + 1][k2], rings[i + 1][k]))
        bm.faces.new(list(reversed(rings[0]))); bm.faces.new(rings[-1])
        bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
        return bm

    def growth(self, body_bvh, anchors, length, width, name, seed=0, segs=4, clearance=0.02, splay=0.35, sink=0.04, min_len=0.5, fold=0.32,
               serr=0.45):
        """the Hive's growth: a dense clump of drooping needle fronds rooted INTO the bark at each anchor (point, normal),
        pushed out of the body as they fall so they drape over it instead of clipping into it. Varied lengths."""
        rng = random.Random(seed)
        down = Vector((0, 0, -1))
        made = 0
        for ai, (p, nrm) in enumerate(anchors):
            L = length * rng.uniform(min_len, 1.0)
            w = width * rng.uniform(0.75, 1.25)
            hz = Vector((nrm.x, nrm.y, 0))
            if hz.length < 1e-3:
                a_ = rng.uniform(0, 6.283); hz = Vector((math.cos(a_), math.sin(a_), 0))
            hz.normalize()
            out = hz * splay + Vector((rng.uniform(-1, 1), rng.uniform(-1, 1), 0)) * 0.12
            pts = [p - nrm * sink]
            for i in range(1, segs + 1):
                t = i / segs
                q = p + nrm * (L * 0.1 * math.sin(math.pi * 0.5 * t)) + out * (L * 0.55 * math.sin(math.pi * 0.5 * t)) + down * (L * t ** 1.25)
                for _ in range(2):
                    loc, sn, _, dist = body_bvh.find_nearest(q)
                    if loc is not None and (q - loc).dot(sn) < clearance:
                        q = loc + sn * clearance
                pts.append(q)
            side = Vector((0, 0, 1)).cross(hz)
            ang = rng.uniform(-0.35, 0.35)
            side = (side * math.cos(ang) + Vector((0, 0, 1)) * math.sin(ang) * 0.3).normalized()
            self.add(f"{name}_{ai}", self.frond(pts, w, side, seed=seed + ai, fold=fold, serr=serr), "HiveFoliage")
            made += 1
        return made

    def anchors_under(self, bvh, center, radius, n, seed=0, max_nz=0.2):
        """anchor points on the UNDERSIDE of a mass: upward rays from a sunflower disc below `center`"""
        rng = random.Random(seed)
        out = []
        for i in range(n):
            r = radius * math.sqrt((i + 0.5) / n); a = i * 2.39996 + rng.uniform(-0.2, 0.2)
            o = Vector(center) + Vector((r * math.cos(a), r * math.sin(a), -30.0))
            loc, nrm, _, _ = bvh.ray_cast(o, Vector((0, 0, 1)), 60)
            if loc is not None and nrm.z <= max_nz:
                out.append((loc, nrm))
        return out

    def anchors_along(self, bvh, targets, out_dir):
        """anchor points on the surface along a line of targets (rays along -out_dir)"""
        res = []
        for t in targets:
            loc, nrm = self.surf(bvh, t, out_dir)
            if loc is not None:
                res.append((loc, nrm))
        return res

    def muscle(self, a, b, n, r, spread, name, seed=0, mid=None, turn=0.5, steps=8, ref=None, slot="HiveBark", body=True, sides=5,
               taper=(0.45, 0.35)):
        """a bundle of n root strands from a to b (through mid if given) laid side by side across `spread` and twisting
        round each other by `turn` turns: reads as rooty muscle. Each strand swells in the middle (radius r) and
        thins to taper*r at its ends so it blends into the masses it joins"""
        rng = random.Random(seed)
        a, b = Vector(a), Vector(b)
        m_ = Vector(mid) if mid is not None else (a + b) / 2
        path = [(1 - t) ** 2 * a + 2 * (1 - t) * t * m_ + t * t * b for t in [i / steps for i in range(steps + 1)]]
        for k in range(n):
            off0 = (k - (n - 1) / 2) * spread
            pts, rad = [], []
            for i, p in enumerate(path):
                t = i / steps
                tan = (path[min(i + 1, steps)] - path[max(i - 1, 0)]).normalized()
                N, B = perp_basis(tan, ref)
                th = 2 * math.pi * turn * t + k * 0.9
                pts.append(p + B * (off0 * math.cos(th * 0.5)) + N * (spread * 0.35 * math.sin(th)))
                sw = math.sin(math.pi * t)
                end = taper[0] if t < 0.5 else taper[1]
                rad.append(r * (end + (1 - end) * sw) * rng.uniform(0.9, 1.1))
            self.add(f"{name}_{k}", tube(pts, rad, sides=sides, seed=seed + k, ridge=0.18, jit=0.04, twist=0.35), slot, body=body)

    def drake_head(self, base, fwd, size, name="drake", seed=0, up=(0, 0, 1), proud=0.02, neck_len=None, heavy=1.0, slits=(1.0, 1.0)):
        """a Hatchling-style drake head sprouting from the body: bark neck (base sunk), faceted skull, open jaws,
        glowing BlightGlow throat between them, two eye nodes, two timber horn spikes"""
        rng = random.Random(seed)
        F = frame(fwd, up)
        def L(x, y, z):
            return Vector(base) + F @ Vector((x, y, z))
        s = size
        nl = neck_len if neck_len is not None else 1.1 * s
        h = heavy
        neck = [L(0, -0.5 * s, -0.15 * s), L(0, 0, 0), L(0, nl * 0.25, 0.06 * s), L(0, nl * 0.5, 0.12 * s), L(0, nl * 0.75, 0.17 * s), L(0, nl, 0.2 * s)]
        self.add(name + "_neck", tube(neck, [0.42 * s * h, 0.38 * s * h, 0.34 * s * h, 0.31 * s * h, 0.29 * s * h, 0.28 * s * h], sides=9, seed=seed,
                                      ridge=0.18, twist=0.25), "HiveBark", body=True)
        hy = nl + 0.35 * s
        rot = F.to_3x3()
        self.add(name + "_skull", lump(L(0, hy, 0.28 * s), (0.36 * s * min(h, 1.25), 0.55 * s, 0.3 * s * min(h, 1.25)), rot=rot, subdiv=2,
                                       seed=seed + 1, chops=6, chop=0.2, creases=1), "HiveBark", body=True)
        if h > 1.0:
            # dorsal bark plates down the neck, a collar of fused lumps where it leaves the body, brow ridges, cheek masses
            for k in range(3):
                t = 0.2 + 0.28 * k
                self.add(f"{name}_ridge{k}", lump(L(0, nl * t, (0.06 + 0.15 * t) * s + 0.3 * s * h), (0.13 * s, 0.2 * s, 0.11 * s), rot=rot,
                                                  subdiv=1, seed=seed + 20 + k, chops=3), "HiveBark", body=True)
            for k in range(4):
                a_ = 2 * math.pi * k / 4 + 0.4
                self.add(f"{name}_collar{k}", lump(L(math.cos(a_) * 0.42 * s * h, -0.1 * s, math.sin(a_) * 0.42 * s * h), (0.2 * s, 0.2 * s, 0.17 * s),
                                                   subdiv=1, seed=seed + 30 + k, chops=3), "HiveBark", body=True)
            for side in (-1, 1):
                self.add(f"{name}_brow{side}", lump(L(side * 0.17 * s, hy + 0.08 * s, 0.6 * s), (0.13 * s, 0.2 * s, 0.08 * s), rot=rot, subdiv=1,
                                                    seed=seed + 40 + side, chops=3), "HiveBark", body=True)
                self.add(f"{name}_cheek{side}", lump(L(side * 0.3 * s, hy + 0.05 * s, 0.12 * s), (0.12 * s, 0.2 * s, 0.13 * s), rot=rot, subdiv=1,
                                                     seed=seed + 44 + side, chops=3), "HiveBark", body=True)
        # upper jaw (snout) and dropped lower jaw: open mouth
        self.add(name + "_snout", lump(L(0, hy + 0.55 * s, 0.25 * s), (0.25 * s, 0.42 * s, 0.14 * s), rot=rot, subdiv=1, seed=seed + 2, chops=4),
                 "HiveBark", body=True)
        jrot = (F @ Matrix.Rotation(math.radians(-28), 4, 'X')).to_3x3()
        self.add(name + "_jaw", lump(L(0, hy + 0.42 * s, -0.12 * s), (0.22 * s, 0.45 * s, 0.09 * s), rot=jrot, subdiv=1, seed=seed + 3, chops=4),
                 "HiveBark", body=True)
        # glowing throat filling the gap between the jaws, set back inside the mouth
        self.add(name + "_throat", lump(L(0, hy + 0.32 * s, 0.1 * s), (0.17 * s, 0.3 * s, 0.15 * s), rot=rot, subdiv=1, seed=seed + 4,
                                        chops=2, bump=0.15), "BlightGlow")
        # teeth: timber splinters along both jaws
        for side in (-1, 1):
            for k in range(3):
                ty = hy + (0.42 + 0.15 * k) * s
                self.add(f"{name}_tooth{side}{k}", spike(L(side * 0.12 * s, ty, 0.22 * s), L(side * 0.12 * s, ty + 0.03 * s, 0.02 * s), 0.035 * s, sides=4, n=2),
                         "HiveTimber")
        # horns
        for side in (-1, 1):
            self.add(f"{name}_horn{side}", spike(L(side * 0.18 * s, hy - 0.1 * s, 0.4 * s), L(side * 0.42 * s, hy - 0.75 * s, 0.75 * s), 0.09 * s,
                                                 sides=5, seed=seed + 7, bend=F.to_3x3() @ Vector((0, 0, 0.15 * s))), "HiveTimber")
        # eye nodes seated on the skull's flanks (rays against the skull only)
        sk = [p for p in self.parts if p["name"] == name + "_skull"][0]["bm"]
        sbvh = BVHTree.FromBMesh(sk)
        for j, side in enumerate((-1, 1)):
            self.eye(sbvh, L(0, hy + 0.12 * s, 0.38 * s), F.to_3x3() @ Vector((side, 0.35, 0.45)), 0.075 * s * (1.2 if slits[j] < 1 else 1.0), proud,
                     name=f"{name}_eye{j}", segs=8, slit=slits[j])
        return F

    # ---------------------------------------------------------------- finish: one mesh, six slots by name
    def build(self, mats):
        bm = bmesh.new()
        self.part_ranges = []
        for p in self.parts:
            for f in p["bm"].faces:
                f.material_index = SLOTS.index(p["slot"])
            me = bpy.data.meshes.new("_t"); p["bm"].to_mesh(me)
            f0 = len(bm.faces)
            bm.from_mesh(me); bpy.data.meshes.remove(me)
            self.part_ranges.append((p["name"], f0, len(bm.faces)))
        # v2 shading: everything smooth, edges sharper than sharp_angle marked sharp (kept in the mesh as sharp_edge, so
        # the FBX carries it): chopped planes, creases, chamfers and lashings stay crisp, small noise facets blend
        for f in bm.faces:
            f.smooth = True
        for e in bm.edges:
            if (not e.is_manifold) or e.calc_face_angle(0.0) > self.sharp_angle:
                e.smooth = False
        me = bpy.data.meshes.new(self.name)
        bm.to_mesh(me); bm.free()
        ob = bpy.data.objects.new(self.name, me)
        bpy.context.scene.collection.objects.link(ob)
        for s in SLOTS:
            me.materials.append(mats[s])
        # UVs: smart project (fine for step 1; texturing re-unwraps if needed)
        bpy.context.view_layer.objects.active = ob
        for o in bpy.context.scene.objects: o.select_set(o is ob)
        bpy.ops.object.mode_set(mode='EDIT')
        bpy.ops.mesh.select_all(action='SELECT')
        bpy.ops.uv.smart_project(angle_limit=math.radians(60), island_margin=0.004)
        bpy.ops.object.mode_set(mode='OBJECT')
        self.obj = ob
        return ob

    # ---------------------------------------------------------------- measured audit
    def audit(self, budget):
        ob = self.obj; me = ob.data
        tris = sum(len(p.vertices) - 2 for p in me.polygons)
        per_slot = {s: 0 for s in SLOTS}
        for p in me.polygons:
            per_slot[SLOTS[p.material_index]] += len(p.vertices) - 2
        co = np.array([v.co[:] for v in me.vertices])
        lo, hi = co.min(0), co.max(0)
        floating, inside_out, checked = [], [], 0
        trees = [BVHTree.FromBMesh(p["bm"]) for p in self.parts]
        for p in self.parts:
            if p["closed"]:
                vol = 0.0
                for f in p["bm"].faces:
                    vs = [v.co for v in f.verts]
                    for i in range(1, len(vs) - 1):
                        vol += vs[0].dot(vs[i].cross(vs[i + 1])) / 6.0
                if vol < 0:
                    inside_out.append(p["name"])
        # contact graph: a part is attached if it overlaps (or is within 5 mm of) a part that is attached; body parts seed it
        n = len(self.parts)
        bbs = []
        for p in self.parts:
            cs = [v.co for v in p["bm"].verts]
            bbs.append((Vector((min(c.x for c in cs), min(c.y for c in cs), min(c.z for c in cs))) - Vector((0.01,) * 3),
                        Vector((max(c.x for c in cs), max(c.y for c in cs), max(c.z for c in cs))) + Vector((0.01,) * 3)))
        def touch(i, j):
            a, b = bbs[i], bbs[j]
            if any(a[1][k] < b[0][k] or b[1][k] < a[0][k] for k in range(3)):
                return False
            if trees[i].overlap(trees[j]):
                return True
            small, big = (i, j) if len(self.parts[i]["bm"].verts) < len(self.parts[j]["bm"].verts) else (j, i)
            return min(trees[big].find_nearest(v.co)[3] for v in self.parts[small]["bm"].verts) <= 0.005
        attached = {i for i, p in enumerate(self.parts) if p["body"]}
        frontier = list(attached)
        while frontier:
            i = frontier.pop()
            for j in range(n):
                if j not in attached and touch(i, j):
                    attached.add(j); frontier.append(j)
        checked = sum(1 for p in self.parts if not p["body"])
        floating = [self.parts[i]["name"] for i in range(n) if i not in attached]
        body_islands = []
        bidx = [i for i, p in enumerate(self.parts) if p["body"]]
        seen = set()
        for i in bidx:
            if i in seen: continue
            comp, st = {i}, [i]
            while st:
                k = st.pop()
                for j in bidx:
                    if j not in comp and touch(k, j):
                        comp.add(j); st.append(j)
            seen |= comp; body_islands.append(sorted(self.parts[k]["name"] for k in comp))
        # free-standing non-body parts may legitimately touch only other details (rims around eyes, rope on timber)
        # visible back faces: cast rays at every face centroid from 26 directions; a face that is the FIRST hit from a
        # direction its normal points away from is a back face someone can see (inverted or folded face)
        verts = [v.co.copy() for v in me.vertices]
        polys = [list(p.vertices) for p in me.polygons]
        tb = BVHTree.FromPolygons(verts, polys)
        dirs = []
        for i in range(26):
            z = 1 - 2 * (i + 0.5) / 26; r = math.sqrt(1 - z * z); a = i * 2.39996
            dirs.append(Vector((r * math.cos(a), r * math.sin(a), z)))
        back_parts = {}
        rng_names = []
        for nm, f0, f1 in self.part_ranges:
            rng_names.append((f0, f1, nm))
        def part_of(fi):
            for f0, f1, nm in rng_names:
                if f0 <= fi < f1: return nm
            return "?"
        bad_faces = 0
        for p in me.polygons:
            c = p.center; n = p.normal
            for d in dirs:
                if n.dot(d) > -0.2:
                    continue
                hit = tb.ray_cast(c + d * 50.0, -d, 100.0)
                if hit[2] == p.index:
                    bad_faces += 1
                    nm = part_of(p.index); back_parts[nm] = back_parts.get(nm, 0) + 1
                    break
        res = dict(tris=tris, budget=budget, visible_back_faces=bad_faces, visible_back_face_parts=back_parts, verts=len(me.vertices), faces=len(me.polygons), tris_per_slot=per_slot,
                   bounds_min_blender=lo.round(3).tolist(), bounds_max_blender=hi.round(3).tolist(),
                   size_unity_xyz=[round(hi[0] - lo[0], 3), round(hi[2] - lo[2], 3), round(hi[1] - lo[1], 3)],
                   slots=[m.name for m in me.materials], uv_channels=len(me.uv_layers),
                   uv_names=[u.name for u in me.uv_layers], objects=[ob.name], parts=len(self.parts),
                   parts_checked_for_contact=checked, not_touching_body=floating, inside_out_parts=inside_out,
                   body_islands=len(body_islands), body_island_members=[b[:4] for b in body_islands] if len(body_islands) > 1 else [],
                   notes=self.notes)
        return res


# ------------------------------------------------------------------ materials, donor reference, scene
def slot_materials():
    mats = {}
    for s in SLOTS:
        m = bpy.data.materials.new(s)
        m.use_nodes = True
        b = m.node_tree.nodes["Principled BSDF"]
        c = hexcol(HEX[s])
        b.inputs["Base Color"].default_value = (*c, 1)
        b.inputs["Roughness"].default_value = 0.85
        if s in EMIT:
            b.inputs["Emission Color"].default_value = (*c, 1)
            b.inputs["Emission Strength"].default_value = EMIT[s]
        m.diffuse_color = (*c, 1)
        mats[s] = m
    return mats


def load_donor(asset_dir, suffix=""):
    """donor reference into a 'DonorRef' collection (hidden from render): mesh(es) + one empty per skinned bone"""
    D = os.path.join(asset_dir, "donor")
    info = json.load(open(os.path.join(D, "donor_bones.json")))
    col = bpy.data.collections.new("DonorRef"); bpy.context.scene.collection.children.link(col)
    obs = []
    for r in info["renderers"]:
        if not r["renderer_active"]:
            continue
        nm = r["go"].split("/")[-1].replace(" ", "_")
        fn = os.path.join(D, f"donor_{nm}{suffix}.obj")
        if not os.path.exists(fn):
            fn = os.path.join(D, f"donor_{nm}.obj")
        vs, fs = [], []
        for line in open(fn):
            p = line.split()
            if not p: continue
            if p[0] == "v": vs.append(u2b([float(x) for x in p[1:4]]))
            elif p[0] == "f": fs.append([int(x) - 1 for x in p[1:]])
        me = bpy.data.meshes.new("donor_" + nm); me.from_pydata(vs, [], fs); me.update()
        ob = bpy.data.objects.new("donor_" + nm, me); col.objects.link(ob); obs.append(ob)
    bones = []
    for t in info["transforms"]:
        if t["skinned"]:
            e = bpy.data.objects.new("bone_" + t["name"], None); e.empty_display_size = 0.05
            e.location = u2b(t["world_pos"]); col.objects.link(e)
            bones.append((t["name"], u2b(t["world_pos"])))
    col.hide_render = True
    return info, obs, bones, col


def bone_map(info):
    return {t["name"]: u2b(t["world_pos"]) for t in info["transforms"]}


def figure(x, y):
    """a plain 1.8 m human stand-in (blue), feet on z = 0"""
    bm = bmesh.new()
    parts = [tube([(x - 0.11, y, 0.0), (x - 0.11, y, 0.45), (x - 0.11, y, 0.9)], [0.07, 0.065, 0.08], sides=8, ridge=0, jit=0),
             tube([(x + 0.11, y, 0.0), (x + 0.11, y, 0.45), (x + 0.11, y, 0.9)], [0.07, 0.065, 0.08], sides=8, ridge=0, jit=0),
             tube([(x, y, 0.88), (x, y, 1.15), (x, y, 1.45), (x, y, 1.55)], [0.17, 0.15, 0.2, 0.08], sides=10, ridge=0, jit=0),
             tube([(x - 0.24, y, 1.45), (x - 0.27, y, 1.12), (x - 0.28, y, 0.82)], [0.05, 0.045, 0.04], sides=6, ridge=0, jit=0),
             tube([(x + 0.24, y, 1.45), (x + 0.27, y, 1.12), (x + 0.28, y, 0.82)], [0.05, 0.045, 0.04], sides=6, ridge=0, jit=0),
             sphere((x, y, 1.67), 0.12, segs=12, rings=8, scale=(1, 1, 1.1))]
    for p in parts:
        me = bpy.data.meshes.new("_t"); p.to_mesh(me); bm.from_mesh(me); bpy.data.meshes.remove(me); p.free()
    me = bpy.data.meshes.new("Figure_1.8m"); bm.to_mesh(me); bm.free()
    ob = bpy.data.objects.new("Figure_1.8m", me); bpy.context.scene.collection.objects.link(ob)
    m = bpy.data.materials.new("Figure"); m.use_nodes = True
    m.node_tree.nodes["Principled BSDF"].inputs["Base Color"].default_value = (0.2, 0.4, 0.9, 1)
    m.diffuse_color = (0.2, 0.4, 0.9, 1)
    me.materials.append(m)
    zs = [v.co.z for v in me.vertices]
    return ob, max(zs) - min(zs)


def set_engine(sc, kind="EEVEE"):
    if kind == "WORKBENCH":
        sc.render.engine = 'BLENDER_WORKBENCH'; return
    for e in ("BLENDER_EEVEE_NEXT", "BLENDER_EEVEE"):
        try:
            sc.render.engine = e; return
        except TypeError:
            pass


def scene_setup(res=900):
    sc = bpy.context.scene
    set_engine(sc)
    sc.render.resolution_x = sc.render.resolution_y = res
    sc.render.film_transparent = False
    w = bpy.data.worlds.new("w"); sc.world = w; w.use_nodes = True
    w.node_tree.nodes["Background"].inputs[0].default_value = (0.42, 0.45, 0.5, 1)
    w.node_tree.nodes["Background"].inputs[1].default_value = 0.9
    k = bpy.data.objects.new("key", bpy.data.lights.new("key", "SUN")); sc.collection.objects.link(k)
    k.data.energy = 3.2; k.rotation_euler = (math.radians(48), 0, math.radians(35))
    f = bpy.data.objects.new("fill", bpy.data.lights.new("fill", "SUN")); sc.collection.objects.link(f)
    f.data.energy = 1.1; f.rotation_euler = (math.radians(65), 0, math.radians(-150))
    cam = bpy.data.objects.new("cam", bpy.data.cameras.new("cam")); sc.collection.objects.link(cam); sc.camera = cam
    return sc, cam


def ground(size, z=0.0):
    bpy.ops.mesh.primitive_plane_add(size=size, location=(0, 0, z))
    g = bpy.context.active_object; g.name = "Ground"
    m = bpy.data.materials.new("Ground"); m.use_nodes = True
    m.node_tree.nodes["Principled BSDF"].inputs["Base Color"].default_value = (0.3, 0.29, 0.27, 1)
    m.diffuse_color = (0.3, 0.29, 0.27, 1)
    g.data.materials.append(m)
    return g


def aim(cam, target, direction, dist):
    cam.location = Vector(target) + Vector(direction).normalized() * dist
    cam.rotation_euler = (Vector(target) - cam.location).to_track_quat('-Z', 'Y').to_euler()


def render(sc, path):
    sc.render.filepath = path
    bpy.ops.render.render(write_still=True)


def img_array(path):
    im = bpy.data.images.load(path)
    w, h = im.size
    a = np.empty(w * h * 4, dtype=np.float32); im.pixels.foreach_get(a)
    bpy.data.images.remove(im)
    return a.reshape(h, w, 4)


def save_array(path, arr):
    h, w = arr.shape[:2]
    im = bpy.data.images.new(os.path.basename(path), w, h, alpha=True)
    im.pixels.foreach_set(np.ascontiguousarray(arr, dtype=np.float32).ravel())
    im.filepath_raw = path; im.file_format = 'PNG'; im.save()
    bpy.data.images.remove(im)


def grid(paths, cols, out):
    ims = [img_array(p) for p in paths]
    h, w = ims[0].shape[:2]
    rows = (len(ims) + cols - 1) // cols
    canvas = np.ones((rows * h, cols * w, 4), dtype=np.float32)
    for i, im in enumerate(ims):
        r, c = i // cols, i % cols
        rr = rows - 1 - r          # blender rows start at the bottom
        canvas[rr * h:(rr + 1) * h, c * w:(c + 1) * w] = im
    save_array(out, canvas)


# ------------------------------------------------------------------ the preview set
def previews(model, info, donor_obs, bones, outdir, label, wire_scale=1.0):
    """front / side / back / 3/4 (flat slot colours), matcap+wire, backface check, donor ghost overlay, 1.8 m lineup"""
    os.makedirs(outdir, exist_ok=True)
    ob = model.obj
    sc, cam = scene_setup()
    co = np.array([v.co[:] for v in ob.data.vertices])
    lo, hi = Vector(co.min(0)), Vector(co.max(0))
    dco = np.concatenate([np.array([v.co[:] for v in d.data.vertices]) for d in donor_obs])
    lo = Vector(np.minimum(lo, dco.min(0))); hi = Vector(np.maximum(hi, dco.max(0)))
    c = (lo + hi) / 2
    ext = hi - lo
    g = ground(max(ext) * 4)
    cam.data.type = 'ORTHO'
    out = {}
    views = (("front", (0, 1, 0), max(ext.x, ext.z)), ("side", (1, 0, 0), max(ext.y, ext.z)),
             ("back", (0, -1, 0), max(ext.x, ext.z)))
    for nm, d, span in views:
        cam.data.ortho_scale = span * 1.12
        aim(cam, c, d, max(ext) * 3)
        out[nm] = os.path.join(outdir, f"{label}_{nm}.png"); render(sc, out[nm])
    cam.data.type = 'PERSP'; cam.data.lens = 50
    d34 = Vector((0.75, 0.85, 0.42))
    aim(cam, c, d34, max(ext) * 1.9)
    out["34"] = os.path.join(outdir, f"{label}_34.png"); render(sc, out["34"])
    out["sheet"] = os.path.join(outdir, f"{label}_sheet.png")
    grid([out["front"], out["side"], out["back"], out["34"]], 2, out["sheet"])
    # matcap + wire (Workbench): topology and edge loops
    set_engine(sc, "WORKBENCH")
    sh = sc.display.shading
    sh.light = 'MATCAP'
    for mc in ("clay_studio.exr", "basic_1.exr"):
        try:
            sh.studio_light = mc; break
        except TypeError:
            pass
    sh.color_type = 'OBJECT'
    ob.color = (0.85, 0.82, 0.78, 1)
    wire = ob.copy(); wire.data = ob.data; wire.name = "wire_view"
    sc.collection.objects.link(wire)
    wm = wire.modifiers.new("w", 'WIREFRAME'); wm.thickness = 0.006 * wire_scale; wm.use_replace = True; wm.use_even_offset = False
    wire.color = (0.08, 0.06, 0.05, 1)
    g.hide_render = True
    sc.render.film_transparent = False
    sc.world.color = (0.55, 0.57, 0.6)
    cam.data.type = 'PERSP'
    aim(cam, c, d34, max(ext) * 1.9)
    out["matcap"] = os.path.join(outdir, f"{label}_matcap_wire.png"); render(sc, out["matcap"])
    cam.data.type = 'ORTHO'; cam.data.ortho_scale = max(ext.y, ext.z) * 1.12; aim(cam, c, (1, 0, 0), max(ext) * 3)
    render(sc, os.path.join(outdir, f"_{label}_matcap_side.png"))
    grid([out["matcap"], os.path.join(outdir, f"_{label}_matcap_side.png")], 2, out["matcap"])
    os.remove(os.path.join(outdir, f"_{label}_matcap_side.png"))
    wire.hide_render = True
    # backface check (EEVEE, material override): front faces grey, back faces bright red
    set_engine(sc, "EEVEE")
    bf = bpy.data.materials.new("_backface_check"); bf.use_nodes = True
    nt = bf.node_tree; nt.nodes.clear()
    geo = nt.nodes.new("ShaderNodeNewGeometry"); mix = nt.nodes.new("ShaderNodeMix"); mix.data_type = 'RGBA'
    mix.inputs[6].default_value = (0.6, 0.6, 0.6, 1); mix.inputs[7].default_value = (1.0, 0.0, 0.0, 1)
    dif = nt.nodes.new("ShaderNodeBsdfDiffuse"); outn = nt.nodes.new("ShaderNodeOutputMaterial")
    nt.links.new(geo.outputs["Backfacing"], mix.inputs[0]); nt.links.new(mix.outputs[2], dif.inputs["Color"])
    nt.links.new(dif.outputs[0], outn.inputs[0])
    bf.use_backface_culling = False
    vl = bpy.context.view_layer; vl.material_override = bf
    g.hide_render = True
    cam.data.type = 'PERSP'
    paths = []
    for i, dd in enumerate((d34, Vector((-0.8, -0.7, 0.25)), Vector((0.2, 0.3, -0.6)))):
        aim(cam, c, dd, max(ext) * 1.9)
        pth = os.path.join(outdir, f"_{label}_bf{i}.png"); render(sc, pth); paths.append(pth)
    out["backface"] = os.path.join(outdir, f"{label}_backface_check.png")
    grid(paths, 3, out["backface"])
    for pth in paths: os.remove(pth)
    vl.material_override = None
    g.hide_render = False
    # donor ghost overlay: model (EEVEE) + donor wire & joints (Workbench, transparent), composited
    set_engine(sc, "EEVEE"); g.hide_render = False; sc.render.film_transparent = False
    ov = []
    for nm, d, span in (("front", (0, 1, 0), max(ext.x, ext.z)), ("side", (1, 0, 0), max(ext.y, ext.z))):
        cam.data.type = 'ORTHO'; cam.data.ortho_scale = span * 1.12; aim(cam, c, d, max(ext) * 3)
        a_path = os.path.join(outdir, f"_{label}_ov_a_{nm}.png"); render(sc, a_path)
        ov.append((a_path, nm, d, span))
    # donor pass
    set_engine(sc, "WORKBENCH"); sh.light = 'FLAT'; sh.color_type = 'OBJECT'
    sc.render.film_transparent = True
    ob.hide_render = True; g.hide_render = True
    bpy.data.collections["DonorRef"].hide_render = False
    for e in bpy.data.collections["DonorRef"].objects:
        if e.type == 'EMPTY':
            e.hide_render = True
    ghost = []
    for d in donor_obs:
        d.color = (0.1, 0.95, 1.0, 1)
        m = d.modifiers.new("w", 'WIREFRAME'); m.thickness = 0.008 * wire_scale; m.use_replace = True; m.use_even_offset = False
        ghost.append(d)
    jm = []
    for nm_b, p in bones:
        bm = sphere(p, 0.035 * wire_scale, segs=8, rings=6)
        me = bpy.data.meshes.new("j"); bm.to_mesh(me); bm.free()
        j = bpy.data.objects.new("joint_" + nm_b, me); sc.collection.objects.link(j); j.color = (1, 0.9, 0.1, 1)
        j.show_in_front = True
        jm.append(j)
    comp = []
    for a_path, nm, d, span in ov:
        cam.data.type = 'ORTHO'; cam.data.ortho_scale = span * 1.12; aim(cam, c, d, max(ext) * 3)
        b_path = os.path.join(outdir, f"_{label}_ov_b_{nm}.png"); render(sc, b_path)
        A = img_array(a_path); Bm = img_array(b_path)
        al = Bm[..., 3:4] * 0.8
        C = A.copy(); C[..., :3] = A[..., :3] * (1 - al) + Bm[..., :3] * al
        cpath = os.path.join(outdir, f"_{label}_ov_c_{nm}.png"); save_array(cpath, C); comp.append(cpath)
        os.remove(a_path); os.remove(b_path)
    out["overlay"] = os.path.join(outdir, f"{label}_donor_overlay.png")
    grid(comp, 2, out["overlay"])
    for p in comp: os.remove(p)
    for j in jm: bpy.data.objects.remove(j)
    for d in ghost: d.modifiers.clear()
    bpy.data.collections["DonorRef"].hide_render = True
    ob.hide_render = False; g.hide_render = False; sc.render.film_transparent = False
    # lineup: side view with the 1.8 m figure standing behind the creature
    set_engine(sc, "EEVEE")
    fig, fig_h = figure(0, lo.y - 1.2)
    cam.data.type = 'ORTHO'
    span_y = (hi.y - (lo.y - 1.6)); cc = Vector((0, (hi.y + lo.y - 1.6) / 2, max(hi.z, 1.9) / 2))
    cam.data.ortho_scale = max(span_y, max(hi.z, 1.9)) * 1.1
    aim(cam, cc, (1, 0, 0), max(ext) * 3)
    out["lineup"] = os.path.join(outdir, f"{label}_lineup_1.8m.png"); render(sc, out["lineup"])
    bpy.data.objects.remove(fig)
    out["figure_height_measured"] = round(fig_h, 3)
    return out


def write_readme(path, title, card, audit, donor_info, out, extra_lines):
    rel = lambda p: os.path.basename(p)
    sz = audit["size_unity_xyz"]
    dsz = donor_info["active_body_bounds_size"]
    L = [f"# {title}: step 1 previews (shapes only)", "",
         f"Card: `art/ASSETS.md` {card}. Generated by the build script in the parent folder (fixed seed); numbers below are MEASURED",
         "by the same run from the built mesh, unless marked NOT ASSESSED.", "",
         "## Measured", "",
         f"| check | value |", "|---|---|",
         f"| triangles | **{audit['tris']}** of a {audit['budget']} budget ({'PASS' if audit['tris'] <= audit['budget'] else 'FAIL'}) |",
         f"| vertices / faces | {audit['verts']} / {audit['faces']} |",
         f"| triangles per slot | " + ", ".join(f"{k} {v}" for k, v in audit["tris_per_slot"].items()) + " |",
         f"| bounding size (Unity x width, y height, z length) | {sz[0]} x {sz[1]} x {sz[2]} m |",
         f"| donor active-renderer bounds (x, y, z) | {dsz[0]:.3f} x {dsz[1]:.3f} x {dsz[2]:.3f} m |",
         f"| lowest point (ground contact, z) | {audit['bounds_min_blender'][2]} m |",
         f"| material slots (by name) | {', '.join(audit['slots'])} ({len(audit['slots'])}) |",
         f"| UV channels | {audit['uv_channels']} ({', '.join(audit['uv_names'])}, smart-project unwrap) |",
         f"| objects | {', '.join(audit['objects'])} (one mesh, six slots) |",
         f"| parts built | {audit['parts']} |",
         f"| detail parts not connected to the body (no overlap or > 5 mm gap, followed through other parts) | {len(audit['not_touching_body'])} of {audit['parts_checked_for_contact']}" +
         (": " + ", ".join(audit['not_touching_body']) if audit['not_touching_body'] else "") + " |",
         f"| body-mass islands (1 = every mass fused into one) | {audit['body_islands']}" +
         (" " + str(audit['body_island_members']) if audit['body_island_members'] else "") + " |",
         f"| closed parts with inverted normals (signed volume < 0) | {len(audit['inside_out_parts'])}" +
         (": " + ", ".join(audit['inside_out_parts']) if audit['inside_out_parts'] else "") + " |",
         f"| faces seen from their back side (rays from 26 directions at every face) | {audit['visible_back_faces']} of {audit['faces']}" +
         (": " + ", ".join(f"{k} {v}" for k, v in audit['visible_back_face_parts'].items()) if audit['visible_back_faces'] else "") + " |",
         f"| 1.8 m figure height in the lineup | {out.get('figure_height_measured')} m |",
         ]
    L += extra_lines
    L += ["", "## Not assessed", "",
          "- Skinning / deformation under the donor's animations: NOT ASSESSED (step 3).",
          "- Look in game (Valheim lighting, 1.5x spawn scale): NOT ASSESSED (no bundle until step 4).",
          "- UV layout quality / texel density: NOT ASSESSED (smart-project placeholder only).",
          "- Collider: NOT ASSESSED (the donor's own capsule colliders will be kept).",
          "", "## Files", ""]
    for k in ("sheet", "front", "side", "back", "34", "matcap", "overlay", "lineup", "backface"):
        if k in out:
            L.append(f"- `{rel(out[k])}`")
    if audit["notes"]:
        L += ["", "## Build notes", ""] + [f"- {n}" for n in audit["notes"]]
    open(path, "w").write("\n".join(L) + "\n")
