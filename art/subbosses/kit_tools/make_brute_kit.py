"""make_brute_kit.py - ASSET-001 Hive Brute, the Runic-armour way (owner, 2026-11-21): OUR Hive add-on pieces fitted onto
the REAL vanilla Troll, step 1 (add-on SHAPES; the base in its real game texture). Adapted from MagicRunicMod
unity/blender/make_armor.py (conformal shells raycast onto the real body with a clearance, a fit loop, rigid pieces on
bones with an anchor per piece, measured overlaps) and render_armor_previews.py (lighting, cameras).

  heavy.sh 4G sb-kit blender -b --factory-startup -P make_brute_kit.py -- <ASSET-001 dir>

Base: the Troll's Body (+ Hair) in its prefab REST pose (= the bind pose turned 180 deg about Y), from donor/, with the
`troll` material's own textures from kit/ref/ (game data, never shipped). The base is NOT modified and NOT shipped.
Add-ons: one piece per bone, each piece one mesh with the six Hive slots it uses (placeholder colours at this step).
Writes kit/HiveBrute_kit.blend, kit/attach.json, kit/fit.json, kit/previews/*.png and kit/previews/README.md.
Deterministic (fixed seeds).
"""
import bpy, bmesh, sys, os, math, json, random, time
from mathutils import Vector, Matrix, noise
from mathutils.bvhtree import BVHTree
import numpy as np

ASSET = sys.argv[sys.argv.index("--") + 1].rstrip("/")
SUB = os.path.dirname(ASSET)
sys.path.insert(0, os.path.join(SUB, "kit_tools"))
sys.path.insert(0, os.path.join(SUB, "tools_001-003"))
import donor_base as DB
import hive_kit as hk
V = Vector

KIT = os.path.join(ASSET, "kit")
PREV = os.path.join(KIT, "previews")
os.makedirs(PREV, exist_ok=True)
SEED = 4001
CLEAR = 0.006            # inner skin of every shell sits 6 mm off the Troll (target 2-10 mm)
PROUD = 0.025            # eye-socket rims (accepted 2026-11-21)
BUDGET = 12000
T0 = time.time()

bpy.ops.wm.read_factory_settings(use_empty=True)
D = DB.Donor(ASSET, os.path.join(KIT, "ref"))
BODY, BVS, BFS = DB.base_bvh(D, ("Body",))
HAIR, _, _ = DB.base_bvh(D, ("Hair",))
BP = lambda n: D.bone_pos_b(n)
TRIS_BODY, TRIS_HAIR = len(D.mesh_data("Body")[1]), len(D.mesh_data("Hair")[1])


def bvh_union(bms, with_body=True):
    vs, fs = (list(BVS), list(BFS)) if with_body else ([], [])
    for bm in bms:
        o = len(vs)
        vs += [tuple(v.co) for v in bm.verts]
        fs += [tuple(v.index + o for v in f.verts) for f in bm.faces]
    return BVHTree.FromPolygons(vs, fs)


def index(bm):
    bm.verts.index_update(); bm.faces.index_update()
    bm.verts.ensure_lookup_table(); bm.faces.ensure_lookup_table()
    return bm


# ---------------------------------------------------------------- the conformal Hive shell
def shell(center, dirv, up, rx, ry, thick, lumps, clear=CLEAR, rings=8, segs=24, seed=0, bark=0.08, floor=0.3, rim=0.14,
          max_drop=0.6, smooth_iter=1, bvh=None):
    """A closed bark mass that sits ON the target surface. Rays from a disc above `center` (along -dirv) find the
    surface; the inner skin is the hit + normal * clear, the outer skin adds a thickness = rounded rim falloff x the UNION
    (max) of soft lump fields (so the masses fuse with creases where they meet) x a little bark noise, offset along a
    blend of the hit normal and dirv, then Laplacian-smoothed. A rounded lip ring sews outer to inner. lumps:
    [(u, v, amplitude, sigma)] in the unit disc (u along the horizontal axis, v along the up-most axis)."""
    bvh = bvh or BODY
    rng = random.Random(seed)
    d = V(dirv).normalized()
    N, Bv = hk.perp_basis(d, up)
    origin = V(center) + d * 25.0
    c_loc, c_n, _, _ = bvh.ray_cast(origin, -d, 60)
    assert c_loc is not None, f"shell centre ray missed at {center}"
    noff = V((rng.uniform(-50, 50), rng.uniform(-50, 50), rng.uniform(-50, 50)))
    pts = []                          # rings of [hit, normal, u, v]
    for i in range(rings + 1):
        f = i / rings
        ring = []
        for k in range(1 if i == 0 else segs):
            a = 2 * math.pi * k / segs
            u, v = math.cos(a) * f, math.sin(a) * f
            s = 1.0
            hl = None
            while s > 0.25:
                hl, hn, _, _ = bvh.ray_cast(origin + Bv * (u * s * rx) + N * (v * s * ry), -d, 60)
                if hl is not None and (hl - c_loc).dot(d) > -max_drop * max(rx, ry):
                    break
                hl = None
                s -= 0.08
            if hl is None:                  # fell off the form: keep the previous ring's hit on this spoke (no fan collapse)
                if i > 1:
                    hl, hn, pu, pv = pts[i - 1][k]
                    ring.append([hl.copy(), hn.copy(), pu, pv]); continue
                hl, hn, s = c_loc, c_n, 0.0
            ring.append([hl, hn, u * s, v * s])
        pts.append(ring)

    def T(u, v, p):
        r = min(1.0, math.hypot(u, v))
        F = max(0.0, 1.0 - r ** 2.2) ** 0.55
        L = floor
        for (cu, cv, amp, sg) in lumps:
            L = max(L, amp * math.exp(-((u - cu) ** 2 + (v - cv) ** 2) / (sg * sg)))
        b = 1.0 + bark * noise.fractal(p * 1.4 + noff, 0.6, 2.0, 3)
        return thick * (rim + (1 - rim) * F) * L * b

    outer, inner, od = [], [], []
    for ring in pts:
        ro, ri, rd = [], [], []
        for (p, n, u, v) in ring:
            r_ = min(1.0, math.hypot(u, v))           # ray direction in the middle (no converging folds), surface normal at the rim (no
            o = (n * (0.3 + 0.7 * r_ ** 2) + d * (0.7 * (1 - r_ ** 2))).normalized()     # sideways slide past the inner skin)
            ro.append(p + o * (clear + T(u, v, p))); ri.append(p + n * clear); rd.append(o)
        outer.append(ro); inner.append(ri); od.append(rd)
    # Laplacian smoothing of the outer skin (ring neighbours + the rings above/below), rim kept
    for _ in range(smooth_iter):
        new = [list(r) for r in outer]
        for i in range(1, rings):
            for k in range(segs):
                nb = [outer[i][(k - 1) % segs], outer[i][(k + 1) % segs], outer[i + 1][k],
                      outer[i - 1][0] if i == 1 else outer[i - 1][k]]
                avg = sum(nb, V()) / 4
                new[i][k] = outer[i][k].lerp(avg, 0.5)
        outer = new
    # never let smoothing pull the outer skin through the inner one (that folded faces near the rim)
    for i, ring in enumerate(pts):
        for k, (p, n, u, v) in enumerate(ring):
            need = clear + 0.5 * T(u, v, p)
            h = (outer[i][k] - p).dot(n)
            if h < need:
                outer[i][k] = outer[i][k] + n * (need - h)
    bm = bmesh.new()
    vo = [[bm.verts.new(p) for p in r] for r in outer]
    vi = [[bm.verts.new(p) for p in r] for r in inner]
    # rounded lip between the outer and inner rims
    lip = []
    for k in range(segs):
        p, n, u, v = pts[-1][k]
        radial = (Bv * u + N * v)
        radial = radial - n * radial.dot(n)          # along the surface
        radial = radial.normalized() if radial.length > 1e-6 else Bv
        tr = (outer[-1][k] - inner[-1][k]).length
        lip.append(bm.verts.new(inner[-1][k].lerp(outer[-1][k], 0.5) + radial * tr * 0.5))
    for k in range(segs):
        k2 = (k + 1) % segs
        bm.faces.new((vo[0][0], vo[1][k], vo[1][k2]))
        bm.faces.new((vi[0][0], vi[1][k2], vi[1][k]))
        for i in range(1, rings):
            bm.faces.new((vo[i][k], vo[i + 1][k], vo[i + 1][k2], vo[i][k2]))
            bm.faces.new((vi[i][k2], vi[i + 1][k2], vi[i + 1][k], vi[i][k]))
        bm.faces.new((vo[-1][k], lip[k], lip[k2], vo[-1][k2]))
        bm.faces.new((lip[k], vi[-1][k], vi[-1][k2], lip[k2]))
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    return bm


def fit_out(bm, step=0.004, iters=60, rigid=False):
    """push a piece off the Troll until no triangle pair intersects (Runic's fit, iterative). rigid: move the whole part"""
    for it in range(iters):
        index(bm)
        pairs = BVHTree.FromBMesh(bm).overlap(BODY)
        if not pairs:
            return it
        if rigid:
            c = sum((v.co for v in bm.verts), V()) / len(bm.verts)
            loc, n, _, _ = BODY.find_nearest(c)
            push = V((n.x, n.y, 0)).normalized() if abs(n.z) < 0.95 else n
            for v in bm.verts:
                v.co += push * step * 2
            continue
        vs = {v for i, _ in pairs for v in bm.faces[i].verts}
        for v in vs:
            loc, n, _, _ = BODY.find_nearest(v.co)
            if loc is not None:
                v.co += n * step
    return iters


# ---------------------------------------------------------------- the pieces (one hk.Model per piece = per bone)
PIECES = []        # (name, bone, model, why)


def piece(name, bone, why):
    pc = hk.Model("HB_" + name, SEED + len(PIECES) * 100)
    pc.sharp_angle = math.radians(60)          # smooth-shaded; only real breaks (lip rims, chamfers) stay sharp
    PIECES.append((name, bone, pc, why))
    return pc


def addp(pc, name, bm, slot, fit=True, rigid=False):
    bmesh.ops.triangulate(bm, faces=bm.faces[:])          # fit and measure the triangles the game will get
    if fit:
        fit_out(bm, rigid=rigid)
    pc.add(name, bm, slot, body=True)
    return bm


def roots(pc, starts, name, seed, r=0.045, length=0.9):
    """bark roots creeping from a mass's edge out over the Troll's skin, riding 4 mm off it (never cutting in)"""
    rng = random.Random(seed)
    for k, (p0, outd) in enumerate(starts):
        p0, outd = V(p0), V(outd).normalized()
        side = outd.cross(V((0, 0, 1))) if abs(outd.z) < 0.9 else outd.cross(V((1, 0, 0)))
        side.normalize()
        path = [p0 + outd * (length * t) + side * (0.12 * math.sin(t * 5 + k)) * t for t in (0.0, 0.25, 0.5, 0.75, 1.0)]
        loc, n = pc.surf(BODY, p0, outd)
        if loc is None:
            continue
        pc.vein(BODY, path, _out_of(p0), r * rng.uniform(0.8, 1.2), name=f"{name}_{k}", seed=seed + k, sink=-1.08, slot="HiveBark",
                sides=4, taper=0.25)
        if pc.parts and pc.parts[-1]["name"] == f"{name}_{k}":
            fit_out(pc.parts[-1]["bm"])


def _out_of(p):
    loc, n, _, _ = BODY.find_nearest(V(p))
    return n


# 1. BACK HUMP (Spine2): fused bark masses over the whole upper back and shoulder blades, a neck mass rising behind the head
#    (the head sits sunk in bark), eye clusters, ridge spikes, creeping roots, the growth hanging from the lower creases
hump = piece("hump", "Spine2", "upper back + neck mass; the spine bends little above Spine2 (the head turns in front of the neck mass)")
hb = addp(hump, "hump_mass", shell((0, -0.7, 5.35), (0, -1, 0.55), (0, 0, 1), 1.95, 1.55, 1.3,
                                   [(-0.4, 0.42, 1.0, 0.28), (0.42, 0.38, 0.92, 0.28), (0.02, 0.05, 0.82, 0.26),
                                    (-0.66, -0.2, 0.72, 0.24), (0.64, -0.25, 0.74, 0.24), (0.05, 0.78, 0.66, 0.22),
                                    (-0.32, -0.6, 0.55, 0.2), (0.32, -0.62, 0.5, 0.2), (-0.75, 0.35, 0.6, 0.2), (0.76, 0.32, 0.62, 0.2)],
                                   rings=8, segs=24, seed=SEED + 1, floor=0.12, rim=0.03), "HiveBark")
nk = addp(hump, "neck_mass", shell((0, 0.05, 6.55), (0, -0.85, 0.9), (0, 0, 1), 0.85, 0.7, 0.85,
                                   [(0.0, 0.35, 1.0, 0.32), (-0.45, 0.0, 0.8, 0.28), (0.45, -0.05, 0.78, 0.28), (0.0, -0.45, 0.7, 0.26)],
                                   rings=5, segs=16, seed=SEED + 2, floor=0.15, rim=0.03), "HiveBark")
hbv = BVHTree.FromBMesh(index(hb))
nkv = BVHTree.FromBMesh(index(nk))
for i, (x, z, r_, sl) in enumerate(((0.65, 6.1, 0.13, 1.0), (1.0, 5.95, 0.09, 0.4), (0.55, 5.85, 0.085, 1.0))):
    hump.eye(hbv, V((x, -0.8, z)), (0.35, -1, 0.45), r_, PROUD, name=f"eye_hump{i}", slit=sl, segs=6)
# the head's eyes peer forward over the skull from the neck mass (lopsided: one big, one small set high, one slit)
for i, (x, z, r_, sl) in enumerate(((-0.3, 7.25, 0.12, 1.0), (0.25, 7.33, 0.08, 1.0), (0.02, 7.5, 0.065, 0.42))):
    hump.eye(nkv, V((x, 0.3, z)), (0, 0.55, 1), r_, PROUD, name=f"eye_neck{i}", slit=sl, segs=6)
hump.splinters(hbv, [V((x, -0.6, 6.5)) for x in (-0.9, -0.35, 0.15, 0.6)], (0, -0.6, 1), 0.9, 0.09, "spike_ridge", seed=SEED + 5,
               lean=(0, -0.5, 0))
roots(hump, [((-1.7, -0.3, 4.6), (-0.6, 0.2, -1)), ((1.7, -0.35, 4.55), (0.6, 0.2, -1)), ((-0.9, -0.95, 4.2), (-0.2, 0, -1)),
             ((0.85, -0.95, 4.15), (0.2, 0, -1)), ((0.0, -1.0, 4.1), (0.05, 0, -1))], "root_back", SEED + 7, r=0.05, length=1.0)
union_back = bvh_union([hb])
back_anchors = hump.anchors_along(hbv, [V((x + 0.1 * (zi % 2), -0.8, z)) for zi, z in enumerate((4.45, 4.75))
                                        for x in (-1.2, -0.6, 0.0, 0.6, 1.2)], (0, -1, -0.35))
hump.growth(union_back, back_anchors, 1.7, 0.66, "growth_back", seed=SEED + 6, segs=4, clearance=0.03, splay=0.25, sink=0.06,
            min_len=0.55, fold=0.2, serr=0.35)

# 2-3. SHOULDER MASSES (LeftArm / RightArm): ride the upper arm like Runic's pauldrons and run down it
for s, side in ((-1, "Left"), (1, "Right")):
    sh = piece(f"shoulder_{side[0].lower()}", f"{side}Arm", "rides the upper arm like a pauldron (Runic precedent)")
    sb = addp(sh, "shoulder_mass", shell((1.95 * s, 0.32, 5.45), (0.3 * s, 0.05, 1), (0, 1, 0), 0.8, 1.15, 0.8,
                                         [(0.0, -0.45, 1.0, 0.3), (0.42, -0.1, 0.8, 0.26), (-0.4, -0.05, 0.78, 0.26),
                                          (0.0, 0.25, 0.72, 0.24), (0.3, 0.6, 0.6, 0.22), (-0.3, 0.62, 0.56, 0.22)],
                                         rings=5, segs=18, seed=SEED + 10 + s, floor=0.12, rim=0.03), "HiveBark")
    sbv = BVHTree.FromBMesh(index(sb))
    sh.drape(sbv, V((1.75 * s, 0.32, 6.0)), (0.3 * s, 0, 1), 0.5, 0.05, name="moss_cap", seed=SEED + 13 + s, rings=2, segs=9)
    sh.splinters(sbv, [V((2.0 * s, 0.1, 6.0))], (0.3 * s, -0.2, 1), 0.75, 0.08, "spike_sh", seed=SEED + 15 + s, lean=(0.2 * s, -0.4, 0),
                 sink=0.12)
    roots(sh, [((2.6 * s, 0.6, 4.9), (0.7 * s, 0.4, -0.6)), ((2.4 * s, -0.1, 4.95), (0.7 * s, -0.3, -0.6))], "root_arm", SEED + 17 + s,
          r=0.045, length=0.8)
    # bark over the forearm (LeftForeArm/RightForeArm): separate piece, it must not ride the upper arm
    fa = piece(f"forearm_{side[0].lower()}", f"{side}ForeArm", "bark over the forearm, rigid on the forearm")
    el, wr = BP(f"{side}ForeArm"), BP(f"{side}Hand")
    addp(fa, "forearm_mass", shell(el.lerp(wr, 0.5) + V((0, 0, 0.35)), (0.15 * s, 0.0, 1), (0, 1, 0), 0.75, 0.38, 0.5,
                                   [(-0.35, 0.0, 1.0, 0.3), (0.3, 0.05, 0.85, 0.3), (0.0, -0.3, 0.6, 0.25)],
                                   rings=4, segs=16, seed=SEED + 18 + s, floor=0.15, rim=0.03), "HiveBark")

# 4. HEAD (Head): a heavy brow shelf the Troll's own eyes glow out from under
head = piece("head", "Head", "rigid on the skull")
brow = addp(head, "brow_shelf", shell((0, 1.45, 6.95), (0, 0.75, 1), (0, 0, 1), 0.7, 0.3, 0.36,
                                      [(-0.45, -0.3, 1.0, 0.36), (0.45, -0.3, 0.95, 0.36), (0.0, -0.4, 0.75, 0.32), (0.0, 0.4, 0.5, 0.3)],
                                      rings=5, segs=16, seed=SEED + 20, floor=0.3, rim=0.05), "HiveBark")
hd = BVHTree.FromBMesh(index(brow))
head.splinters(hd, [V((x, 1.3, 7.2)) for x in (-0.45, 0.45)], (0, 0.3, 1), 0.55, 0.06, "spike_brow", seed=SEED + 22, lean=(0, -0.6, 0))

# 5. WAIST RING (Spine0): the Hive's lashed timber leg ring + a needle-growth skirt where the loincloth hair was
ring = piece("waist_ring", "Spine0", "rides the pelvis; the skirt fronds may brush the thighs in a stride (could be skinned to the thighs in step 3)")
NR, ZR, CY = 8, 3.05, 0.25
rpts = []
for i in range(NR):
    a = 2 * math.pi * (i + 0.5) / NR
    dd = V((math.sin(a), math.cos(a), 0))
    loc, n, _, _ = BODY.ray_cast(V((0, CY, ZR)), dd, 10)       # from inside the belly outward: the outer skin
    rpts.append((loc if loc is not None else V((0, CY, ZR)) + dd * 1.6, dd))
plank_bms = []
for i in range(NR):
    (p0, d0), (p1, d1) = rpts[i], rpts[(i + 1) % NR]
    t = (p1 - p0).normalized()
    out = (d0 + d1).normalized()
    off = out * (0.08 + (0.05 if i % 2 else 0.0)) + V((0, 0, 0.05 if i % 2 else -0.04))
    bm = hk.beam(p0 - t * 0.22 + off, p1 + t * 0.22 + off, 0.13, 0.32, up=(0, 0, 1), seed=SEED + 30 + i, rings=2)
    for _ in range(10):                     # push the plank out by its measured penetration (+ CLEAR) along the ring normal
        worst = 9.0
        for v in bm.verts:
            loc, n, _, dist = BODY.find_nearest(v.co)
            sd = dist if (v.co - loc).dot(n) >= 0 else -dist
            worst = min(worst, sd)
        if worst >= CLEAR:
            break
        for v in bm.verts:
            v.co += out * (CLEAR - worst + 0.002)
    for _ in range(25):                     # body vertices can still poke through a flat plank face: clear the real overlap
        if not BVHTree.FromBMesh(bm).overlap(BODY):
            break
        for v in bm.verts:
            v.co += out * 0.006
    plank_bms.append(addp(ring, f"plank_{i}", bm, "HiveTimber", fit=False))
for i in range(0, NR, 2):
    p, dd = rpts[i]
    c = sum((v.co for v in plank_bms[i].verts), V()) / len(plank_bms[i].verts)
    q = sum((v.co for v in plank_bms[i - 1].verts), V()) / len(plank_bms[i - 1].verts)
    mid = (c + q) / 2
    ax = (c - q).normalized()
    lb = hk.lashing(mid, ax, 0.16, 0.21, 0.2, up=(0, 0, 1), turns=2.0, rope_r=0.026, seg_per_turn=6, sides=4, seed=SEED + 40 + i)
    outd = V((mid.x, mid.y - CY, 0)).normalized()
    for _ in range(10):                     # the rope wraps the plank joint; push it off the belly like the planks
        worst = min((d_ if (v.co - l_).dot(n_) >= 0 else -d_) for v in lb.verts for (l_, n_, _, d_) in [BODY.find_nearest(v.co)])
        if worst >= CLEAR:
            break
        for v in lb.verts:
            v.co += outd * (CLEAR - worst + 0.002)
    addp(ring, f"lash_{i}", lb, "HiveTimber", fit=False)
rbv = bvh_union(plank_bms, with_body=False)
skirt = []
for a_deg in (-24, 0, 24, 156, 180, 204):
    a = math.radians(a_deg)
    dd = V((math.sin(a), math.cos(a), 0))
    loc, n, _, _ = rbv.ray_cast(V((0, CY, ZR - 0.06)) + dd * 4, -dd, 8)
    if loc is not None:
        skirt.append((loc, (dd + V((0, 0, -0.2))).normalized()))
ring.growth(bvh_union(plank_bms), skirt, 1.15, 0.48, "growth_skirt", seed=SEED + 45, segs=4, clearance=0.03, splay=0.15, sink=0.04,
            min_len=0.75, fold=0.2, serr=0.35)

# 6-7. KNUCKLE CAPS (LeftHand / RightHand): spiked bark caps over the backs of the fists
for s, side in ((-1, "Left"), (1, "Right")):
    kn = piece(f"knuckles_{side[0].lower()}", f"{side}Hand", "rigid on the hand; fingers bend under it")
    hand = BP(f"{side}Hand"); mid = BP(f"{side}HandMiddle1")
    c = hand.lerp(mid, 0.55)
    kb = addp(kn, "knuckle_cap", shell(c + V((0, 0, 0.2)), (0.25 * s, 0.0, 1), ((mid - hand).x, 0, 0), 0.46, 0.42, 0.36,
                                       [(0.35, 0.0, 1.0, 0.35), (-0.25, 0.3, 0.8, 0.3), (-0.25, -0.3, 0.8, 0.3)],
                                       rings=4, segs=14, seed=SEED + 50 + s, floor=0.3), "HiveBark")
    kbv = BVHTree.FromBMesh(index(kb))
    kn.splinters(kbv, [c + V((0.15 * s, y, 0.4)) for y in (-0.22, 0.02, 0.24)], (0.35 * s, 0, 1), 0.55, 0.065, "spike_knuckle",
                 seed=SEED + 55 + s, lean=(0.35 * s, 0, 0), sink=0.12)
    if s > 0:        # sinister: one tiny eye in the crease between two knuckle lumps
        kn.eye(kbv, c + V((0.1, 0.0, 0.4)), (0.3, 0, 1), 0.04, 0.012, name="eye_knuckle", segs=6)

# 8. CHEST MOUTH (Spine1): the WTF - a fitted bark plate split by a vertical mouth: raised lips, splinter teeth, glowing gullet
mouth = piece("chest_mouth", "Spine1", "on the chest between Spine1 and Spine2; rides Spine1 (the lower of the two)")
ml, mn, _, _ = BODY.ray_cast(V((0, 6, 4.6)), V((0, -1, 0)), 20)
lips = []
for s in (-1, 1):
    lips.append(addp(mouth, f"lip_{s}", shell(V((0.5 * s, ml.y, 4.6)), (0.15 * s, 1, 0), (0, 0, 1), 0.56, 1.0, 0.5,
                                              [(-0.72 * s, 0.0, 1.0, 0.24), (-0.65 * s, 0.55, 0.85, 0.2), (-0.65 * s, -0.55, 0.85, 0.2),
                                               (0.3 * s, 0.45, 0.45, 0.3), (0.3 * s, -0.45, 0.45, 0.3)],
                                              rings=5, segs=16, seed=SEED + 60 + s, floor=0.2, rim=0.03), "HiveBark"))
addp(mouth, "gullet", shell(V((0, ml.y, 4.6)), (0, 1, 0), (0, 0, 1), 0.2, 0.8, 0.06, [(0, 0, 1.0, 0.8)], rings=3, segs=12,
                            seed=SEED + 63, floor=0.6), "BlightGlow")
lipv = bvh_union(lips, with_body=False)
for s in (-1, 1):
    bases, tips = [], []
    for z in (4.18, 4.38, 4.58, 4.78, 4.98):
        loc, n, _, _ = lipv.ray_cast(V((0.2 * s, 6, z)), V((0, -1, 0)), 20)
        if loc is not None:
            bases.append(loc - V((0.0, 0.03, 0))); tips.append(loc + V((-0.21 * s, 0.08, 0.03 * s)))
    mouth.teeth(bases, tips, 0.05, f"tooth_{s}", seed=SEED + 65 + s, broken=0.3)
roots(mouth, [((x, 1.2, z), (dx, 0, dz)) for (x, z, dx, dz) in ((-0.55, 5.3, -0.7, 0.6), (0.6, 5.25, 0.7, 0.6), (-0.6, 3.95, -0.6, -0.6),
                                                              (0.55, 3.9, 0.6, -0.6))], "root_chest", SEED + 69, r=0.04, length=0.7)

# ---------------------------------------------------------------- build the pieces, measure the fit
mats = hk.slot_materials()
objs = []
for name, bone, pc, why in PIECES:
    ob = pc.build(mats)
    objs.append((name, bone, pc, ob, why))
T_BUILD = time.time() - T0


def tris_of(ob):
    return sum(len(p.vertices) - 2 for p in ob.data.polygons)


def mesh_bvh(ob):
    return BVHTree.FromPolygons([v.co[:] for v in ob.data.vertices], [tuple(p.vertices) for p in ob.data.polygons])


fit = {}
all_clear = []
for name, bone, pc, ob, why in objs:
    mb = mesh_bvh(ob)
    pairs_body = len(mb.overlap(BODY)); pairs_hair = len(mb.overlap(HAIR))
    ds = []
    for v in ob.data.vertices:
        loc, n, _, dist = BODY.find_nearest(v.co)
        sgn = 1.0 if (v.co - loc).dot(n) >= 0 else -1.0
        ds.append(sgn * dist)
    near = sorted(x for x in ds if x < 0.05)        # the skin facing the Troll
    all_clear += near
    byp = {}
    for p in pc.parts:
        n_ = len(BVHTree.FromBMesh(p["bm"]).overlap(BODY))
        if n_:
            byp[p["name"]] = n_
    fit[name] = {"bone": bone, "tris": tris_of(ob), "pairs_body": pairs_body, "pairs_hair": pairs_hair,
                 "pairs_by_part": dict(sorted(byp.items(), key=lambda kv: -kv[1])[:8]),
                 "min_clear_m": round(min(ds), 4), "median_contact_clear_m": round(near[len(near) // 2], 4) if near else None,
                 "contact_verts": len(near), "gap_to_body_m": round(max(0.0, min(ds)), 4)}
# contact graph inside each piece (a part is attached if it touches the Troll or a part that does)
for name, bone, pc, ob, why in objs:
    trees = [BVHTree.FromBMesh(p["bm"]) for p in pc.parts]
    att = set()
    for i, p in enumerate(pc.parts):
        md = min(BODY.find_nearest(v.co)[3] for v in p["bm"].verts)
        if md <= 0.012:
            att.add(i)
    changed = True
    while changed:
        changed = False
        for i in range(len(pc.parts)):
            if i in att:
                continue
            for j in att:
                if trees[i].overlap(trees[j]):
                    att.add(i); changed = True; break
    fit[name]["floating_parts"] = [pc.parts[i]["name"] for i in range(len(pc.parts)) if i not in att]
# back faces anyone can see (rays from 26 directions; the Troll body counts as an occluder)
vs, fs, owner = list(BVS), list(BFS), [None] * len(BFS)
for name, bone, pc, ob, why in objs:
    o = len(vs)
    vs += [v.co[:] for v in ob.data.vertices]
    for p in ob.data.polygons:
        pn = next((nm for nm, f0, f1 in pc.part_ranges if f0 <= p.index < f1), "?")
        fs.append(tuple(i + o for i in p.vertices)); owner.append(name + "/" + pn)
allb = BVHTree.FromPolygons(vs, fs)
dirs = []
for i in range(26):
    z = 1 - 2 * (i + 0.5) / 26; r = math.sqrt(1 - z * z); a = i * 2.39996
    dirs.append(V((r * math.cos(a), r * math.sin(a), z)))
back = {}
for fi in range(len(BFS), len(fs)):
    tri = [V(vs[i]) for i in fs[fi]]
    c = sum(tri, V()) / len(tri)
    nrm = (tri[1] - tri[0]).cross(tri[2] - tri[0])
    if len(tri) > 3:
        nrm = sum(((tri[k] - c).cross(tri[(k + 1) % len(tri)] - c) for k in range(len(tri))), V())
    if nrm.length < 1e-12:
        continue
    nrm.normalize()
    for dd in dirs:
        if nrm.dot(dd) > -0.2:
            continue
        h = allb.ray_cast(c + dd * 50, -dd, 100)
        if h[2] == fi:
            back[owner[fi]] = back.get(owner[fi], 0) + 1
            break
T_FIT = time.time() - T0 - T_BUILD

# ---------------------------------------------------------------- the attach table (Runic armor_attach.json style)
def u_of(b):
    return [b.x, b.z, b.y]


attach = {"_about": "Rigid Hive add-on pieces for ASSET-001 Hive Brute on the vanilla Troll (make_brute_kit.py). For each piece: "
          "create an empty ANCHOR as a child of the bone `parent` with this local transform, then the piece mesh under it at "
          "identity (mesh vertices = Unity metres relative to `pivot_rest_world`, axis-aligned with the Troll root). Units: "
          "Unity, the Troll prefab's REST pose (the bind pose turned 180 deg about Y). localScale 1/130 cancels the bone chain's "
          "x130 (Armature). localRotation undoes the bone's rest rotation, so in the rest pose the anchor is axis-aligned with "
          "the creature. Mesh object in kit/HiveBrute_kit.blend: HB_<piece>.",
          "_donor": "Troll (1.0.21, bundle c4210710)", "_base_tris": {"Body": TRIS_BODY, "Hair": TRIS_HAIR}}
for name, bone, pc, ob, why in objs:
    co = np.array([v.co[:] for v in ob.data.vertices])
    lo, hi = co.min(0), co.max(0)
    pivot_b = V(((lo + hi) / 2).tolist())
    pu = np.array(u_of(pivot_b) + [1.0])
    Bw = D.bone_world_u(bone)
    lp = np.linalg.inv(Bw) @ pu
    R = Bw[:3, :3] / np.linalg.norm(Bw[:3, :3], axis=0)
    q = Matrix(R.tolist()).to_quaternion().inverted()
    eul = q.to_matrix().to_euler('ZXY')
    slot_tris = {}
    for p in ob.data.polygons:
        sn = ob.data.materials[p.material_index].name
        slot_tris[sn] = slot_tris.get(sn, 0) + len(p.vertices) - 2
    attach["HB_" + name] = {"parent": bone, "rigid": True, "why": why,
                            "localPosition": [round(float(x), 6) for x in lp[:3]],
                            "localRotation": [round(q.x, 6), round(q.y, 6), round(q.z, 6), round(q.w, 6)],
                            "localEulerAngles": [round(math.degrees(eul.x) % 360, 3), round(math.degrees(eul.y) % 360, 3),
                                                 round(math.degrees(eul.z) % 360, 3)],
                            "localScale": [round(1 / 130, 7)] * 3,
                            "pivot_rest_world": [round(float(x), 5) for x in pu[:3]],
                            "tris": tris_of(ob), "slot_tris": {k: v for k, v in slot_tris.items() if v},
                            "pairs_body": fit[name]["pairs_body"]}
json.dump(attach, open(os.path.join(KIT, "attach.json"), "w"), indent=1)
TOT_ADD = sum(tris_of(o[3]) for o in objs)
summary = {"tris_base_body": TRIS_BODY, "tris_base_hair": TRIS_HAIR, "tris_addons": TOT_ADD,
           "total_hair_hidden": TRIS_BODY + TOT_ADD, "total_with_hair": TRIS_BODY + TRIS_HAIR + TOT_ADD, "budget": BUDGET,
           "pieces": fit, "visible_back_faces": back,
           "all_contact_clear_min_m": round(min(all_clear), 4) if all_clear else None,
           "all_contact_clear_median_m": round(all_clear[len(all_clear) // 2], 4) if all_clear else None,
           "seconds": {"build": round(T_BUILD, 1), "measure": round(T_FIT, 1)}}
json.dump(summary, open(os.path.join(KIT, "fit.json"), "w"), indent=1)
print("SUMMARY", json.dumps({k: v for k, v in summary.items() if k != "pieces"}))
for k, v in fit.items():
    print("PIECE", k, json.dumps(v))

# ---------------------------------------------------------------- scene, save, previews
col_add = bpy.data.collections.new("COL_HiveAddons"); bpy.context.scene.collection.children.link(col_add)
for name, bone, pc, ob, why in objs:
    for c in ob.users_collection:
        c.objects.unlink(ob)
    col_add.objects.link(ob)
col_base = bpy.data.collections.new("COL_TrollBase_reference_not_shipped"); bpy.context.scene.collection.children.link(col_base)
base_obs = DB.add_base(D, hair=True, collection=col_base)
body_ob, hair_ob = base_obs
hair_ob.hide_render = True
tgt = DB.lights_and_world(scale=4.0, aim=(0, 0, 3.7))
DB.setup_render(900, 1000)
bpy.ops.wm.save_as_mainfile(filepath=os.path.join(KIT, "HiveBrute_kit.blend"))

shots = {}


def shot(name, target, dist, az, el, lens=85, w=900, h=1000):
    bpy.context.scene.render.resolution_x, bpy.context.scene.render.resolution_y = w, h
    DB.camera(target, dist, az, el, lens=lens)
    p = os.path.join(PREV, name + ".png"); DB.render(p); shots[name] = p
    return p


CEN = (0, 0.2, 3.75)
views = (("front", 0, 6, 46), ("side", 90, 6, 34), ("back", 180, 6, 46), ("34", 35, 12, 44))
for nm, az, el, dist in views:
    shot(f"kit_{nm}", CEN, dist, az, el)
col_add.hide_render = True
for nm, az, el, dist in views:
    shot(f"base_{nm}", CEN, dist, az, el)
hair_ob.hide_render = False
shot("base_with_hair_34", CEN, 44, 35, 12)
col_add.hide_render = False
shot("kit_with_hair_34", CEN, 44, 35, 12)
hair_ob.hide_render = True
# close-ups
shot("close_head", (0, 1.1, 6.9), 9, 28, 10, w=900, h=800)
shot("close_chest_mouth", (0, 1.2, 4.6), 9, 18, 4, w=900, h=900)
shot("close_back_growth", (0, -0.9, 4.8), 13, 160, 12, w=900, h=900)
# the Heart's Black Forest tint on the base only (ApplyBiomeVisuals: SetColor("_Color", (0.5, 0.1, 0.8)) - sRGB-decoded)
tint = tuple(DB.srgb2lin(c) for c in (0.5, 0.1, 0.8))
tm = DB.base_material(D, name="TrollTint_BlackForest", tint=tint)
body_ob.data.materials[0] = tm
col_add.hide_render = True
shot("base_tint_blackforest_front", CEN, 46, 0, 6)
shot("base_tint_blackforest_34", CEN, 44, 35, 12)
body_ob.data.materials[0] = DB.base_material(D)
col_add.hide_render = False
# lineup with the 1.8 m figure (orthographic, side)
fig, fh = hk.figure(0, -3.2)
bpy.context.scene.render.resolution_x, bpy.context.scene.render.resolution_y = 1300, 900
DB.camera((0, -0.6, 3.85), 60, 90, 0, ortho=12.5)
p = os.path.join(PREV, "lineup_1.8m.png"); DB.render(p); shots["lineup"] = p
bpy.data.objects.remove(fig)
# sheets
hk.grid([shots["kit_front"], shots["kit_side"], shots["kit_back"], shots["kit_34"]], 4, os.path.join(PREV, "kit_sheet.png"))
hk.grid([shots["base_front"], shots["base_side"], shots["base_back"], shots["base_34"]], 4, os.path.join(PREV, "base_sheet.png"))
T_ALL = time.time() - T0
summary["seconds"]["total_incl_renders"] = round(T_ALL, 1)
summary["figure_height_m"] = round(fh, 3)
json.dump(summary, open(os.path.join(KIT, "fit.json"), "w"), indent=1)
print("DONE", round(T_ALL, 1), "s")
