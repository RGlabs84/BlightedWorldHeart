"""ASSET-005 Barkbound Husk, kitbash v2 (owner/coordinator 2026-11-21): the add-ons are VANILLA PARTS in their real game
materials on the real vanilla Draugr, the way TheHive itself is built. No new geometry (see README for the one exception).

Parts (all exported from the 1.0.21 bundle by ../../kit_tools_b/export_part.py into _ref/parts/; game data, never shipped):
- Root armour (ArmorRootChest attach_skin/RootArmorSkirt, ArmorRootLegs attach_skin/RootArmorPants.005, AbominationArmor):
  skinned to the Player rig, RETARGETED onto the Draugr's bones: Player->Draugr bone map, per bone T(draugr) R(segment
  direction) S(segment length) T(-player) after a 180-degree turn (the Player rig faces +Z), plus an affine fit per torso
  bone from the Draugr's own cross-section (its gut). All of it is per-bone affine, so at runtime it is the vanilla mesh
  REBOUND to the Draugr skeleton with new bindposes (attach.json lists the matrices); no vanilla geometry is shipped.
- TheHive `low` bark lumps (TheHive_Mat): the helm (four fused lumps round the skull), a lump on the upper back the growth
  hangs from, and a small lump in the left palm.
- Hive eyes: TheHive's EYE is a Unity built-in sphere (768 tris each, too many for a ring of 12), so the eye GEOMETRY is one
  eyeball of the Hatchling's `eyes` mesh (40 tris) with TheHive_Eye's material (red emission). Both vanilla.
- The growth (v3): no tree meshes (owner: "no pine, drop the trees, second time telling you"). The `vines` leafy drape, three
  plain ThornRoots tendrils and a WrithanRoots clump hang and drape down the back from the back lump.
Run: heavy.sh 4G sb-kitbash blender -b --factory-startup -P make_husk_kitbash.py -- <abs kit dir>
"""
import bpy, bmesh, sys, os, math, json, random
import numpy as np
from mathutils import Vector, Matrix, Euler
from mathutils.bvhtree import BVHTree
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "..", "kit_tools_b")); sys.path.insert(0, os.path.join(HERE, "..", "..", "donor_tools_004-006"))
import hivefit as H

OUT = sys.argv[sys.argv.index("--") + 1] if "--" in sys.argv else HERE
PV = os.path.join(OUT, "previews"); os.makedirs(PV, exist_ok=True)
REF = os.path.join(OUT, "_ref"); PR = os.path.join(REF, "parts")
SEED = 5606; rnd = random.Random(SEED)
bpy.ops.wm.read_factory_settings(use_empty=True)
base, J, dom = H.load_base(REF, "Draugr_base")
CARDS = H.card_tris(base, J, REF)
VS = [v.co.copy() for v in base.data.vertices]
def solid_bvh(regions):
    fs = []
    for p in base.data.polygons:
        if p.index in CARDS: continue
        rs = [H.region_of(dom[i]) for i in p.vertices]
        if max(set(rs), key=rs.count) in regions: fs.append(list(p.vertices))
    return BVHTree.FromPolygons(VS, fs)
SOLID = solid_bvh({"torso", "head", "armL", "armR", "legL", "legR"})
CARDB = BVHTree.FromPolygons(VS, [list(base.data.polygons[i].vertices) for i in sorted(CARDS)])
BONES = H.bone_frames(J)
def P_(n): return BONES[n].translation.copy() if n in BONES else H.node_pos(J, n)
LOAD = lambda k: json.load(open(os.path.join(PR, k + ".json")))
S_ = Matrix(((1, 0, 0, 0), (0, 0, 1, 0), (0, 1, 0, 0), (0, 0, 0, 1)))   # Unity <-> Blender axis swap
PIECES = {}


def mats_for(P, **kw):
    return [H.part_material(m, PR, P["key"] + "_" + m["name"], **kw) for m in P["materials"]]


# ---------------------------------------------------------------- Root armour, retargeted (skinned)
torso_vs = [VS[i] for i in range(len(VS)) if H.region_of(dom[i]) == "torso"]
hips_vs = [VS[i] for i in range(len(VS)) if H.region_of(dom[i]) in ("torso", "legL", "legR")]
def fit_torso(P):
    vs, dm, Ms, srcdom = H.retarget(P, J, return_ms=True)
    adjust, info = {}, {}
    for b in ("Hips", "Spine", "Spine1", "Spine2"):
        sel = [vs[i] for i in range(len(vs)) if srcdom[i] == b]
        if len(sel) < 12: continue
        zs = sorted(p.z for p in sel); zlo, zhi = zs[len(zs) // 10], zs[-len(zs) // 10 - 1]
        body = [p for p in (hips_vs if b == "Hips" else torso_vs) if zlo <= p.z <= zhi]
        if not body: continue
        xs = sorted(abs(p.x) for p in sel); ys = sorted(p.y for p in sel)
        px, py0, py1 = xs[int(len(xs) * 0.95)], ys[int(len(ys) * 0.03)], ys[int(len(ys) * 0.97)]
        bx = max(abs(p.x) for p in body); by0 = min(p.y for p in body); by1 = max(p.y for p in body)
        sx = min(1.5, max(1.0, (bx + 0.02) / max(px, 1e-3)))        # capped: a narrow collar must not stretch the shoulder flaps
        ny0, ny1 = min(py0, by0 - 0.02), max(py1, by1 + 0.02)
        sy = min(1.6, (ny1 - ny0) / max(py1 - py0, 1e-3)); oy = (ny0 + ny1) / 2 - sy * (py0 + py1) / 2 if sy == 1.6 else ny0 - sy * py0
        adjust[b] = Matrix(((sx, 0, 0, 0), (0, sy, 0, oy), (0, 0, 1, 0), (0, 0, 0, 1)))
        info[b] = {"scale_x": round(sx, 3), "scale_y_front_back": round(sy, 3), "offset_y": round(oy, 4)}
    vs, dm, Ms, srcdom = H.retarget(P, J, adjust=adjust, return_ms=True)
    return vs, dm, Ms, info

ROOT_RECOLOUR = {"saturation": 0.3, "tint": [0.95, 0.72, 0.5]}
STRANDS = {}; FLAPS = {}; SKIRT_Z = 1.12; SKIRT_TOP = 1.24; SKIRT_CUT = [0]
for key, label in (("rootchest", "root_chest"), ("rootlegs", "root_legs")):
    P = LOAD(key)
    # v4 (owner: "smaller roots, but more of them"): the Root armour's own THICK root strands are one UV island of
    # AbominationArmor (u < 0.32, v < 0.62); they are dropped, the bark plates and the skirt stay. At runtime this is
    # a kept-triangle list (our data) on the rebound vanilla mesh.
    _uv = P["uv0"]; kept, dropped = [], 0
    for si, sub in enumerate(P["submeshes"]):
        ks = []
        for ti, tr in enumerate(sub):
            u = sum(_uv[i][0] for i in tr) / 3; v = sum(_uv[i][1] for i in tr) / 3
            if u < 0.32 and v < 0.62: dropped += 1
            else: ks.append(ti)
        kept.append(ks)
    P = dict(P); P["submeshes"] = [[sub[i] for i in ks] for sub, ks in zip(P["submeshes"], kept)]
    json.dump({"about": "kept triangle indices per submesh of the vanilla mesh (the thick root-strand UV island is dropped)", "kept": kept},
              open(os.path.join(OUT, f"{label}_kept_tris.json"), "w"))
    STRANDS[label] = dropped
    vs, dm, Ms, info = fit_torso(P)
    flap = 0
    if label == "root_chest":
        # v6 (owner: "yes, strip the shoulder pads"): the bark plates whose connected piece sits above the chest (centroid z > 1.5 m)
        # are the shoulder pads; their triangles leave the kept list too.
        tris_all = [(si, ti, tr) for si, sub in enumerate(P["submeshes"]) for ti, tr in enumerate(sub)]
        par = {}
        def _f(a_):
            while par.setdefault(a_, a_) != a_: par[a_] = par[par[a_]]; a_ = par[a_]
            return a_
        for si, ti, tr in tris_all:
            for i in tr[1:]: par[_f(i)] = _f(tr[0])
        comp = {}
        for k_, (si, ti, tr) in enumerate(tris_all): comp.setdefault(_f(tr[0]), []).append(k_)
        drop = set()
        for c_, ks_ in comp.items():
            cz = sum(vs[i].z for k_ in ks_ for i in tris_all[k_][2]) / (3 * len(ks_))
            if cz > 1.5 or (len(ks_) < 40 and cz > 1.2): drop |= set(ks_)   # the pads, and stray pad fragments in front of the chest
        flap = len(drop)
        # v6 pose-test fix: the long Root skirt (below the belt, triangle centroid z < SKIRT_Z) tore into flat shards in the
        # crouch whatever weights it got (it hangs 10+ cm off the thighs); it is cut, and the Draugr's own loincloth shows.
        for k_, (si, ti, tr) in enumerate(tris_all):
            if k_ not in drop and sum(vs[i].z for i in tr) / 3 < SKIRT_Z: drop.add(k_); SKIRT_CUT[0] += 1
        # what the cut leaves of the skirt's top (loose belt-height strips that stuck out sideways in kit_back / kit_side) goes too
        par2 = {}
        def _f2(a_):
            while par2.setdefault(a_, a_) != a_: par2[a_] = par2[par2[a_]]; a_ = par2[a_]
            return a_
        for k_, (si, ti, tr) in enumerate(tris_all):
            if k_ in drop: continue
            for i in tr[1:]: par2[_f2(i)] = _f2(tr[0])
        comp2 = {}
        for k_, (si, ti, tr) in enumerate(tris_all):
            if k_ not in drop: comp2.setdefault(_f2(tr[0]), []).append(k_)
        for c_, ks_ in comp2.items():
            cz = sum(vs[i].z for k_ in ks_ for i in tris_all[k_][2]) / (3 * len(ks_))
            print("SKIRTCOMP", len(ks_), round(cz, 3), round(min(vs[i].z for k_ in ks_ for i in tris_all[k_][2]), 3))
            if cz < SKIRT_TOP: drop |= set(ks_); SKIRT_CUT[0] += len(ks_)
        newsubs = [[] for _ in P["submeshes"]]; newkept = [[] for _ in P["submeshes"]]
        for k_, (si, ti, tr) in enumerate(tris_all):
            if k_ in drop: continue
            newsubs[si].append(tr); newkept[si].append(kept[si][ti])
        P["submeshes"] = newsubs; kept = newkept
        json.dump({"about": "kept triangle indices per submesh of the vanilla mesh (the thick root strands, the shoulder pads and the skirt below the belt are dropped)", "kept": kept},
                  open(os.path.join(OUT, f"{label}_kept_tris.json"), "w"))
    FLAPS[label] = flap
    bm = H.part_bm(P, vs)
    bm.verts.ensure_lookup_table()
    before = [v.co.copy() for v in bm.verts]
    H.push_out(bm, SOLID, clear=0.004); H.push_out_faces(bm, SOLID, clear=0.004)
    offs = {i: [round(x, 5) for x in (S_.to_3x3() @ (v.co - before[i]))] for i, v in enumerate(bm.verts) if (v.co - before[i]).length > 1e-5}
    json.dump({"about": "per-vertex offsets (Unity metres, Draugr bind-pose world) added to the rebound vanilla mesh so it sits 4 mm off the Draugr; index = vanilla vertex index (part_bm keeps the order)", "offsets": offs},
              open(os.path.join(OUT, f"{label}_offsets.json"), "w"))
    ob = H.bm_object(bm, "Husk_" + label, mats_for(P))
    if label == "root_chest":   # v8: its green plates into the same bark as the repaint (recipe: repaint.json root_armour_recolour)
        for m_ in ob.data.materials:
            nt_ = m_.node_tree; b_ = nt_.nodes["Principled BSDF"]
            if not b_.inputs["Base Color"].links: continue
            src_ = b_.inputs["Base Color"].links[0].from_socket
            hs = nt_.nodes.new("ShaderNodeHueSaturation"); hs.inputs["Saturation"].default_value = ROOT_RECOLOUR["saturation"]
            nt_.links.new(src_, hs.inputs["Color"])
            mt = nt_.nodes.new("ShaderNodeMix"); mt.data_type = 'RGBA'; mt.blend_type = 'MULTIPLY'; mt.inputs[0].default_value = 1.0
            nt_.links.new(hs.outputs["Color"], mt.inputs[6]); mt.inputs[7].default_value = (*ROOT_RECOLOUR["tint"], 1)
            nt_.links.new(mt.outputs[2], b_.inputs["Base Color"])
    rm = {}
    for n, M in Ms.items():
        rm[n] = {"draugr_bone": H.PLAYER_TO_DRAUGR.get(n) or next((k for k in ("LeftHand", "RightHand", "LeftFoot", "RightFoot") if n.startswith(k)), "Head"),
                 "retarget_matrix_unity": [[round(x, 6) for x in row] for row in (S_ @ M @ S_)]}
    PIECES[label] = {"ob": ob, "mode": "skinned (rebound vanilla mesh)", "source": {"prefab": P["prefab"], "renderer": P["path"], "mesh": P["mesh"],
                     "material": [m["name"] for m in P["materials"]]}, "bones_dominant": sorted(set(dm)), "retarget": rm, "torso_fit": info, "offsets_file": f"{label}_offsets.json", "verts_offset": len(offs), "kept_tris_file": f"{label}_kept_tris.json", "dropped_strand_tris": STRANDS[label], "dropped_shoulder_pad_tris": FLAPS[label], "dropped_skirt_tris": SKIRT_CUT[0] if label == "root_chest" else 0}

# ---------------------------------------------------------------- Hive lumps and eyes (rigid)
LP = LOAD("hivelump"); EP = LOAD("hatcheyes"); EYE_MAT_SRC = LOAD("hiveeye")["materials"][0]
lump_local = [H.u2b(v) for v in LP["verts"]]
lc = sum(lump_local, Vector()) / len(lump_local)
lext = max(max(abs((v - lc)[k]) for v in lump_local) for k in range(3))
hive_mat = H.part_material(LP["materials"][0], PR, "TheHive_Mat", moss=True)
eye_mat = H.part_material(EYE_MAT_SRC, PR, "TheHive_Eye", emit=EYE_MAT_SRC["colors"]["_EmissionColor"][:3])
# one eyeball of the Hatchling's `eyes` mesh (connected component)
ev = [H.u2b(v) for v in EP["verts"]]
tris = [t for s in EP["submeshes"] for t in s]
parent = list(range(len(ev)))
def find(a):
    while parent[a] != a: parent[a] = parent[parent[a]]; a = parent[a]
    return a
for t in tris:
    for i in t[1:]: parent[find(i)] = find(t[0])
comp = {}
for i in range(len(ev)): comp.setdefault(find(i), []).append(i)
eyeball = max(comp.values(), key=len)
eb_set = set(eyeball)
eb_tris = [t for t in tris if t[0] in eb_set]
ec = sum((ev[i] for i in eyeball), Vector()) / len(eyeball)
erad = max((ev[i] - ec).length for i in eyeball)


def lump_bm(center, size, rot, squash=(1, 1, 1)):
    """TheHive's `low` lump, centred, scaled to `size` (half extent, metres), rotated, placed (vanilla geometry)."""
    bm = H.part_bm(LP, [((v - lc) / lext) for v in lump_local])
    M = Matrix.Translation(center) @ rot.to_matrix().to_4x4() @ Matrix.Diagonal((size * squash[0], size * squash[1], size * squash[2], 1))
    bmesh.ops.transform(bm, matrix=M, verts=bm.verts)
    return bm, M @ Matrix.Translation(-lc) @ Matrix.Scale(1 / lext, 4)


def eye_bm(center, r, normal):
    bm = bmesh.new(); uvl = bm.loops.layers.uv.new("UVMap")
    idx = {i: bm.verts.new((ev[i] - ec) / erad) for i in eyeball}
    for t in eb_tris:
        try: f = bm.faces.new([idx[i] for i in reversed(t)])
        except ValueError: continue
        for lp, i in zip(f.loops, reversed(t)):
            if EP.get("uv0"): lp[uvl].uv = EP["uv0"][i]
    R = Vector((0, 0, 1)).rotation_difference(Vector(normal)).to_matrix().to_4x4()
    M = Matrix.Translation(center) @ R @ Matrix.Scale(r, 4)
    bmesh.ops.transform(bm, matrix=M, verts=bm.verts)
    return bm, M @ Matrix.Translation(-ec) @ Matrix.Scale(1 / erad, 4)


rigid = []   # (label, bone, bm, material, source, world matrix of the vanilla mesh's local frame)
hc = Vector((0, 0.025, 2.02))
# v7 (coordinator: "the helm reads as a bark bucket hat"): the Hive Brute's lump DEFORMATION (kit_tools/make_brute_kitbash.py
# conform(), the same maths, scaled to the Draugr): each lump is placed on the skull, then its body-facing half is pulled onto the
# skin and 1 cm under it, every height above the skin is flattened (with a ridge noise), and its footprint spreads 60 % wider, so
# the bark GROWS out of the skull, brow, temples, cheeks and nape and the neighbouring mounds run into each other. No enclosing
# mass, no brim: the Draugr's own face shows under the brow. Stored as per-vertex offsets in the vanilla lump's own mesh space
# (deform/lump_offsets.json, our data; the runtime adds them to a clone of TheHive `low`).
OFFSETS = {}
UNDER = 0.01        # the Brute pulls 2 cm under a 5 m Troll's skin; ~1 cm on the 2.2 m Draugr
NZF = 2.3           # the Brute's ridge-noise frequencies, scaled by the Troll / Draugr size ratio
def _ss(e0, e1, x):
    t_ = min(1.0, max(0.0, (x - e0) / (e1 - e0))); return t_ * t_ * (3 - 2 * t_)
def conform_bm(label, bm, W, zdir, target, flat=0.55, cfrac=0.55, ridge=0.3, spread=0.6, seed=0):
    zd = Vector(zdir).normalized(); bm.verts.ensure_lookup_table()
    Wl = [v.co.copy() for v in bm.verts]
    Cc = sum(Wl, Vector()) / len(Wl)
    pz = [w.dot(zd) for w in Wl]; lo, hi = min(pz), max(pz)
    r = random.Random(seed); ph = [r.uniform(0, 6.28) for _ in range(4)]
    Rfoot = max(((w - Cc) - zd * (w - Cc).dot(zd)).length for w in Wl) * (1 + spread)
    Wi = W.inverted(); offs = []
    for v, w, z_ in zip(bm.verts, Wl, pz):
        t_ = (hi - z_) / max(hi - lo, 1e-6)                                     # 0 = crown, 1 = deepest
        rv = (w - Cc) - zd * (w - Cc).dot(zd)
        wt = w + rv * (spread * _ss(0.15, 1.0, t_))
        hit = target.ray_cast(wt + zd * 1.5, -zd, 3.0)
        if hit[0] is None:   # v7b: a vertex beyond the skull's edge (a temple lump's top): wrap it over the skull along the skull's own
            # normal instead of keeping its height (v7a left those as vertical slabs standing above the head)
            loc_, nrm_, _, _ = target.find_nearest(wt); h = (wt - loc_).dot(nrm_)
            nz = 0.5 + 0.5 * math.sin(7.3 * NZF * w.x + ph[0]) * math.sin(6.1 * NZF * w.z + ph[1]) * math.cos(5.7 * NZF * w.y + ph[2])
            hp = max(h, 0.0) * (flat + ridge * (nz - 0.5)) * 0.5
            c = _ss(1.0 - cfrac, 1.0, t_); hp = hp * (1 - c) + (-UNDER) * c
            nw = loc_ + nrm_ * hp
            o = Wi @ nw - Wi @ w; offs.append([round(o.x, 5), round(o.z, 5), round(o.y, 5)]); v.co = nw
            continue
        s_ = hit[0]
        h = (wt - s_).dot(zd)
        nz = 0.5 + 0.5 * math.sin(7.3 * NZF * w.x + ph[0]) * math.sin(6.1 * NZF * w.z + ph[1]) * math.cos(5.7 * NZF * w.y + ph[2])
        rr = min(1.0, ((wt - Cc) - zd * (wt - Cc).dot(zd)).length / Rfoot)
        prof = (1 - rr * rr) ** 0.6                                            # dome envelope: flanks slope to the skin, no ledges
        hp = h * (flat + ridge * (nz - 0.5)) * prof if h > 0 else h
        c = _ss(1.0 - cfrac, 1.0, t_)
        hp = hp * (1 - c) + (-UNDER) * c
        nw = s_ + zd * hp + (wt - s_ - zd * (wt - s_).dot(zd))
        o = Wi @ nw - Wi @ w; offs.append([round(o.x, 5), round(o.z, 5), round(o.y, 5)])     # Unity mesh space (x, y, z)
        v.co = nw
    OFFSETS[label] = offs
def R_from(z_axis, y_hint):
    z = Vector(z_axis).normalized(); y = Vector(y_hint) - z * Vector(y_hint).dot(z)
    if y.length < 1e-6:
        y = Vector((0, 1, 0)) if abs(z.y) < 0.9 else Vector((1, 0, 0)); y = y - z * y.dot(z)
    y.normalize(); x = y.cross(z).normalized()
    return Matrix((x, y, z)).transposed()
def conformed_lump(label, bone, spot, n, size, stretch, squash, spin, target, seed, out=None, flat=0.55, spread=0.6, lift=0.9):
    z = (Vector(n) + (Vector(out) if out else Vector())).normalized()
    rot = (R_from(z, (0, 0, 1) if abs(z.z) < 0.9 else (0, 1, 0)) @ Matrix.Rotation(spin, 3, 'Z')).to_euler()
    bm, W = lump_bm(Vector(spot) + z * size * squash * lift, size, rot, (stretch[0], stretch[1], squash))
    conform_bm(label, bm, W, z, target, flat=flat, spread=spread, seed=seed)
    rigid.append((label, bone, bm, hive_mat, {"prefab": "TheHive", "renderer": "Visual/low", "mesh": "default (low) + vertex offsets (deform/lump_offsets.json)", "material": "TheHive_Mat"}, W))
skull_poly = set(i for p in base.data.polygons if p.index not in CARDS for i in p.vertices)
skull = [VS[i] for i in range(len(VS)) if i in skull_poly and H.region_of(dom[i]) == "head" and VS[i].z > 1.86]
_HP = [p for p in base.data.polygons if sum(1 for i in p.vertices if H.region_of(dom[i]) == "head") * 2 > len(p.vertices)]
HEADB = BVHTree.FromPolygons(VS, [list(p.vertices) for p in _HP])        # skull + its hair cards (finds the spots)
HEADS = BVHTree.FromPolygons(VS, [list(p.vertices) for p in _HP if p.index not in CARDS])   # the SOLID skull: the crust grows from it
# (v7 first try conformed onto the hair / beard cards: the brow and cheeks laid down over the beard as one flat hood with a beak)
HELM = [  # (label, direction from the skull centre, half size, stretch, squash, spin): lopsided, heavier on the creature's left
    # v8 (coordinator: "the helm erupting more"): crown, back and a burst lump rise up and back (less flattened, less spread), the
    # brow is bigger and stands forward over the face (an overhang); the side / cheek / nape crust stays low (v7b)
    ("helm_crown", (0.05, 0.35, 1.0), 0.12, (1.2, 1.0), 0.6, 0.4, dict(flat=0.8, spread=0.35, lift=0.8)),
    ("helm_back", (0.08, 1.0, 0.5), 0.11, (1.1, 0.9), 0.65, 1.3, dict(flat=0.85, spread=0.35, lift=0.8)),
    ("helm_burst", (0.18, 0.75, 1.0), 0.09, (0.9, 1.3), 0.85, 2.2, dict(flat=0.95, spread=0.25, lift=1.0)),
    ("helm_brow", (0.06, -1.0, 0.7), 0.105, (1.5, 0.8), 0.65, 0.0, dict(flat=0.9, spread=0.3, lift=0.9)),   # v8b: higher, so the dimmed green Draugr eyes show under it
    ("helm_temple_l", (0.95, -0.2, 0.35), 0.075, (1.0, 1.15), 0.45, 2.1),
    ("helm_cheek_l", (0.85, -0.5, -0.1), 0.05, (0.9, 1.3), 0.45, 0.9),
    ("helm_temple_r", (-0.95, 0.05, 0.3), 0.065, (1.0, 1.0), 0.45, 2.9),
    ("helm_cheek_r", (-0.9, -0.4, 0.0), 0.04, (0.9, 1.2), 0.45, 0.3),
    ("helm_nape", (0.05, 0.85, -0.45), 0.07, (1.25, 0.9), 0.45, 0.6),
]
for k_, (lab, dd, size, stv, sq, spin, *ov) in enumerate(HELM):
    dd = Vector(dd).normalized(); h = HEADS.ray_cast(hc + dd * 0.6, -dd, 0.6)
    if h[0] is None: print("HELM MISS", lab); continue
    kw = dict(flat=0.5, spread=0.55, lift=0.5); kw.update(ov[0] if ov else {})
    conformed_lump(lab, "Head", h[0], h[1], size, stv, sq, spin, HEADS, seed=31 + k_, out=dd, **kw)
tmp = bmesh.new()
for lab, bone, bm, m, src, W in rigid:
    me = bpy.data.meshes.new("t"); bm.to_mesh(me); tmp.from_mesh(me); bpy.data.meshes.remove(me)
helm_bvh = BVHTree.FromBMesh(tmp)
helm_size = 0.15
helm_out = sum(1 for p in skull if (lambda h: h[0] is None or (p - h[0]).dot(h[1]) > 0)(helm_bvh.find_nearest(p)))   # skull verts NOT under the crust
# v4 eyes (owner: "better eyes"; close_eye_options.png): round glowing orbs SEATED half deep in the bark creases.
# The dominant eye is the Hive's own EYE (Unity's built-in Sphere, 768 tris; the preview uses a 24x16 sphere in its place),
# lopsided to the creature's left under the brow; seven smaller ones are the Gjall eye's round orb (Eye_gib, 112 tris) wearing
# TheHive_Eye's red glow, uneven sizes, set round the helm so it still sees behind itself.
GJ = LOAD("eye_gib"); gv = [H.u2b(v) for v in GJ["verts"]]; gc = sum(gv, Vector()) / len(gv); gr = max((v - gc).length for v in gv)
# v5: the glow is lowered so TheHive_Eye's own texture and the sphere's shading show (a textured red-orange eye with a glow,
# bright core, darker rim), not a flat neon ball
EYE_GLOW = [c * 0.35 for c in EYE_MAT_SRC["colors"]["_EmissionColor"][:3]]
# v6: TheHive_Eye's bark texture darkened under a steep core falloff: a bright red-orange core, a dark textured rim
eye_mat = H.part_material(EYE_MAT_SRC, PR, "TheHive_Eye_v6", emit=EYE_GLOW, emit_facing=True, facing_power=3.0, tint=(0.35, 0.3, 0.3))
_ebv = [ev[i] - ec for i in eyeball]
_cov = [[sum(v[a] * v[b] for v in _ebv) for b in range(3)] for a in range(3)]
_w, _V = np.linalg.eigh(np.array(_cov)); EB_AX = Vector(_V[:, int(np.argmin(_w))])   # the half-dome's axis (its thin direction)
_pr = [v.dot(EB_AX) for v in _ebv]
if abs(min(_pr)) > abs(max(_pr)): EB_AX = -EB_AX                                   # point it at the dome's apex (the far side)
EB_BASE = min(v.dot(EB_AX) for v in _ebv) / erad                                    # the flat base, in normalised units
# v7 (coordinator: "copy the Brute's eye method exactly"): the `eye_globe` dome (50 tris, its own UVs) with TheHive_Eye's texture,
# an amber-red emission CORE and a dark vertical SLIT PUPIL baked into a mask in eye_globe's own UVs (eye/eye_globe_core_pupil_mask.png,
# our data: the eye material's _EmissionMap + a darkening of _MainTex), a darker wet base with a clear coat. Same code as
# kit_tools/make_brute_kitbash.py eye_material(); sizes and clusters are ours (0.8-1.8x the Draugr's eye).
sys.path.append(os.path.join(HERE, "..", "..", "kit_tools"))
import troll_repaint as TR
GL = LOAD("eye_globe")
GLV = [Vector((v[0], v[2], v[1])) for v in GL["verts"]]
GLF = [(tr[0], tr[2], tr[1]) for sm in GL["submeshes"] for tr in sm]
_glo = Vector([min(v[k] for v in GLV) for k in range(3)]); _ghi = Vector([max(v[k] for v in GLV) for k in range(3)])
GL_W = _ghi.x - _glo.x; GL_H = _ghi.z - _glo.z
GL_BASE = Vector(((_glo.x + _ghi.x) / 2, (_glo.y + _ghi.y) / 2, _glo.z))
os.makedirs(os.path.join(OUT, "eye"), exist_ok=True)
def globe_material():
    hj = EYE_MAT_SRC
    m = bpy.data.materials.new("V_TheHive_Eye_core"); m.use_nodes = True
    nt = m.node_tree; b_ = nt.nodes["Principled BSDF"]
    ti = nt.nodes.new("ShaderNodeTexImage"); ti.image = bpy.data.images.load(os.path.join(PR, hj["textures"]["_MainTex"]["png"]))
    col = hj["colors"].get("_Color", [1, 1, 1, 1]); em = hj["colors"].get("_EmissionColor", [1.43, 0, 0.1, 1])
    mul = nt.nodes.new("ShaderNodeMix"); mul.data_type = 'RGBA'; mul.blend_type = 'MULTIPLY'; mul.inputs[0].default_value = 1.0
    nt.links.new(ti.outputs["Color"], mul.inputs[6])
    s_ = max(em[:3])
    eme = nt.nodes.new("ShaderNodeMix"); eme.data_type = 'RGBA'; eme.blend_type = 'MULTIPLY'; eme.inputs[0].default_value = 1.0
    nt.links.new(ti.outputs["Color"], eme.inputs[6]); eme.inputs[7].default_value = (1.0, 0.28, 0.04, 1)     # amber-red iris glow
    nt.links.new(eme.outputs[2], b_.inputs["Emission Color"])
    Vl, UVl, Fl = [], [], []
    for tr in GLF:
        for i in tr:
            Vl.append(tuple(GLV[i])); UVl.append(tuple(GL["uv0"][i]))
        Fl.append((len(Vl) - 3, len(Vl) - 2, len(Vl) - 1))
    cen = np.array((sum(GLV, Vector()) / len(GLV))[:])
    ES = 256
    epos, _ = TR.raster_position_map(Vl, Fl, UVl, ES)
    ev_ = ~np.isnan(epos[..., 0])
    nn = epos[ev_] - cen; nn /= np.linalg.norm(nn, axis=1, keepdims=True)
    core = np.clip(nn[:, 2], 0, 1) ** 5
    pupil = TR.smoothstep(0.07, 0.03, np.abs(nn[:, 0])) * TR.smoothstep(0.35, 0.65, nn[:, 2])
    EMK = np.zeros((ES, ES, 4)); EMK[..., 3] = 1
    EMK[..., 0][ev_] = core * (1 - pupil); EMK[..., 1][ev_] = pupil
    EMK = TR.dilate_fill(EMK, ev_, 4)
    mp = os.path.join(OUT, "eye", "eye_globe_core_pupil_mask.png")
    im = bpy.data.images.new("eyemask", ES, ES, alpha=True); im.pixels.foreach_set(np.ascontiguousarray(EMK, np.float32).ravel())
    im.filepath_raw = mp; im.file_format = 'PNG'; im.save(); bpy.data.images.remove(im)
    mk = nt.nodes.new("ShaderNodeTexImage"); mk.image = bpy.data.images.load(mp); mk.image.colorspace_settings.name = 'Non-Color'
    sep = nt.nodes.new("ShaderNodeSeparateColor"); nt.links.new(mk.outputs["Color"], sep.inputs[0])
    st = nt.nodes.new("ShaderNodeMath"); st.operation = 'MULTIPLY'; st.inputs[1].default_value = 7.0 * s_
    nt.links.new(sep.outputs[0], st.inputs[0]); nt.links.new(st.outputs[0], b_.inputs["Emission Strength"])
    pd = nt.nodes.new("ShaderNodeMath"); pd.operation = 'MULTIPLY_ADD'; pd.inputs[1].default_value = -0.92; pd.inputs[2].default_value = 1.0
    nt.links.new(sep.outputs[1], pd.inputs[0])
    dk = nt.nodes.new("ShaderNodeMix"); dk.data_type = 'RGBA'; dk.blend_type = 'MULTIPLY'; dk.inputs[0].default_value = 1.0
    nt.links.new(mul.outputs[2], dk.inputs[6]); nt.links.new(pd.outputs[0], dk.inputs[7])
    nt.links.new(dk.outputs[2], b_.inputs["Base Color"])
    mul.inputs[7].default_value = (*[0.18 * H.srgb2lin(c) for c in col[:3]], 1)
    b_.inputs["Coat Weight"].default_value = 0.6; b_.inputs["Coat Roughness"].default_value = 0.05
    b_.inputs["Roughness"].default_value = 0.12
    return m
eye_mat = globe_material()
SRC_GLOBE = {"prefab": "eye_globe (mesh) + TheHive (material)", "renderer": "eye_globe/default", "mesh": "default (eye_globe, 50 tris)", "material": "TheHive_Eye + eye/eye_globe_core_pupil_mask.png"}
def globe_bm(surface_pt, n, r, sink=0.4, slit=1.0):
    """an eye_globe dome of radius r set into the bark at surface_pt (its base sunk `sink` of its height), slit vertical"""
    s = 2 * r / GL_W; n = Vector(n).normalized()
    R = R_from(n, (0, 0, 1)).to_4x4()
    M = Matrix.Translation(Vector(surface_pt) - n * (sink * GL_H * s)) @ R @ Matrix.Diagonal((s, s * slit, s * 0.9, 1)) @ Matrix.Translation(-GL_BASE)
    bm = bmesh.new(); uvl = bm.loops.layers.uv.new("UVMap")
    vv = [bm.verts.new(M @ v) for v in GLV]
    for tr in GLF:
        try: f = bm.faces.new([vv[i] for i in tr])
        except ValueError: continue
        for lp, i in zip(f.loops, tr): lp[uvl].uv = GL["uv0"][i]
    return bm, M
def K_frame(z):
    z = Vector(z).normalized(); h = Vector((0, 0, 1)) if abs(z.z) < 0.9 else Vector((1, 0, 0))
    x = h.cross(z).normalized(); return (x, z.cross(x))
def orb(kind, center, r, normal):
    if kind == "hatch":   # one Hatchling eyeball, its long axis along the normal so it shows a round face
        bm = bmesh.new(); uvl = bm.loops.layers.uv.new("UVMap")
        idx = {i: bm.verts.new((ev[i] - ec) / erad) for i in eyeball}
        _F = K_frame(EB_AX)
        for tr in eb_tris:
            try: f = bm.faces.new([idx[i] for i in reversed(tr)])
            except ValueError: continue
            for lp in f.loops:   # v6: spherical UVs over the dome (our UV data) so the eye texture maps onto it
                q = (lp.vert.co).normalized() if lp.vert.co.length > 1e-6 else EB_AX
                lx, ly, lz = q.dot(_F[0]), q.dot(_F[1]), q.dot(EB_AX)
                lp[uvl].uv = (0.5 + math.atan2(ly, lx) / (2 * math.pi), math.acos(max(-1.0, min(1.0, lz))) / math.pi)
        R = EB_AX.rotation_difference(Vector(normal)).to_matrix().to_4x4()
        M = Matrix.Translation(center) @ R @ Matrix.Scale(r, 4) @ Matrix.Translation(-EB_AX * EB_BASE)   # flat base at `center`
        bmesh.ops.transform(bm, matrix=M, verts=bm.verts)
        return bm, M
    if kind == "sphere":
        bm = bmesh.new(); bm.loops.layers.uv.new("UVMap")
        bmesh.ops.create_uvsphere(bm, u_segments=24, v_segments=16, radius=1.0)
        M = Matrix.Translation(center) @ Matrix.Scale(r, 4)
    else:
        bm = H.part_bm(GJ, [(v - gc) / gr for v in gv])
        R = Vector((0, 0, 1)).rotation_difference(Vector(normal)).to_matrix().to_4x4()
        M = Matrix.Translation(center) @ R @ Matrix.Scale(r, 4)
    bmesh.ops.transform(bm, matrix=M, verts=bm.verts)
    return bm, M
def add_lid(label, bone, center, normal, r, open_=1.05):
    """a socket rim: a flattened TheHive `low` lump lying on the bark, overlapping the eye's upper edge like a heavy lid."""
    n = Vector(normal).normalized()
    up = Vector((0, 0, 1)); up = (up - n * up.dot(n)).normalized() if abs(n.z) < 0.95 else Vector((0, 1, 0))
    rot = n.rotation_difference(Vector((0, 0, 1))).inverted().to_euler() if False else Vector((0, 0, 1)).rotation_difference(n).to_euler()
    bm, W = lump_bm(Vector(center) + up * r * open_ + n * r * 0.55, r * 1.6, rot, (1.7, 0.8, 0.5))   # on the surface, over the eyes' upper edges
    rigid.append((label, bone, bm, hive_mat, {"prefab": "TheHive", "renderer": "Visual/low", "mesh": "default (low)", "material": "TheHive_Mat"}, W))
SRC_SPHERE = {"prefab": "TheHive", "renderer": "Visual/EYE", "mesh": "Unity built-in Sphere (768 tris; preview stand-in 24x16)", "material": "TheHive_Eye"}
SRC_GJALL = {"prefab": "Eye_gib (mesh) + TheHive (material)", "renderer": "Eye_gib/default", "mesh": "default (Eye_gib)", "material": "TheHive_Eye"}
# v6 (owner: "wtf is this? 3 big ass whats?"): SMALL eyes at the scale of the Draugr's own (measured from its emission map:
# 38 mm across, at z 2.04, 10 cm apart): radius 15-34 mm, i.e. ~0.8x-1.8x the Draugr's eye. Nine on the helm in four tight,
# lopsided clusters set into the bark under a flattened Hive-lump rim each (spider / Hive eyes: small glinting points, not balls).
# All Hatchling half-domes (40 tris), half-sunk; the largest one (front left) is just the biggest of its cluster.
SRC_HATCH = {"prefab": "Hatchling (eyeball mesh) + TheHive (material)", "renderer": "Hatchling_mountain/eyes", "mesh": "eyes (one eyeball)", "material": "TheHive_Eye"}
CLUSTERS = [  # (name, centre angle deg, dz, [(d angle deg, d z, radius)])
    ("front_l", 22, 0.075, [(0, 0, 0.034), (11, -0.022, 0.02), (-9, -0.026, 0.017), (5, 0.026, 0.015)]),
    ("front_r", -30, 0.085, [(0, 0, 0.022), (9, -0.02, 0.016)]),
    ("side_r", -95, 0.03, [(0, 0, 0.02)]),
    ("back", 175, 0.04, [(0, 0, 0.026), (-10, -0.022, 0.017)]),
]
for cname, ca, cdz, eyes in CLUSTERS:
    rim_pts = []
    for k, (da, ddz, r) in enumerate(eyes):
        a = math.radians(ca + da); d = Vector((math.sin(a), -math.cos(a), 0))
        h = (None,)
        for dzz in (0.0, -0.015, 0.015, -0.03, 0.03, 0.045, 0.06):
            zz = hc.z - 0.01 + cdz + ddz + dzz
            h = helm_bvh.ray_cast(Vector((hc.x, hc.y, zz)) + d * 0.7, -d, 0.7)
            if h[0] is not None: break
        if h[0] is None: continue
        bm, W = globe_bm(h[0], h[1], r * 1.15, sink=0.4)       # v7: the Brute's eye_globe, 40 % of its height sunk in the crust
        rigid.append((f"helm_eye_{cname}_{k}", "Head", bm, eye_mat, SRC_GLOBE, W))
        rim_pts.append((h[0], h[1], r))
# the back lump the growth hangs from (between the shoulder blades)
s2 = P_("Spine2")
d = Vector((0, 1, 0.15)).normalized()
bm, W = lump_bm(s2 + Vector((0, 0.16, 0.05)), 0.17, Euler((0.4, 1.1, 2.0)), (1.2, 0.7, 1.0))
moved = H.rest_on(bm, SOLID, d, clear=0.004) - 0.035; bmesh.ops.translate(bm, vec=-d * 0.035, verts=bm.verts)   # v6: sunk ~30 % into the back
W = Matrix.Translation(d * moved) @ W
back_lump_W = W
rigid.append(("back_lump", "Spine2", bm, hive_mat, {"prefab": "TheHive", "renderer": "Visual/low", "mesh": "default (low)", "material": "TheHive_Mat"}, W))
# ---------------------------------------------------------------- v4 root web (owner: "smaller roots, but more of them"): many
# small vanilla roots conformed onto the body, branching and crossing, each riding the bone it lies on: the catacomb roots
# `fi_vil_combs_root07` (90 tris, a branching root) and the plain ThornRoots strand (116 tris, a thin tendril), scaled down.
# Each root's long axis runs along `direction` from `anchor`; every vertex is laid onto the nearest body surface and lifted by
# its own height in the root + 4 mm (the root bends round the limb). That bend is a per-vertex offset (our data).
R07 = LOAD("root07"); THN = LOAD("thornroot_plain")
mat07 = H.part_material(R07["materials"][0], PR, "root07_mat", tint=(0.42, 0.32, 0.26))   # v5: darkened so the roots read against the camo green
matTh = H.part_material(THN["materials"][0], PR, "thornroot_mat", emit_map=True)
def frame_of(P):
    vs = [H.u2b(v) for v in P["verts"]]
    mn = [min(v[k] for v in vs) for k in range(3)]; mx = [max(v[k] for v in vs) for k in range(3)]
    ext = [mx[k] - mn[k] for k in range(3)]; o = sorted(range(3), key=lambda k: -ext[k])
    return vs, mn, mx, ext, o
F07, FTH = frame_of(R07), frame_of(THN)
REG = {"torso": solid_bvh({"torso"}), "armL": solid_bvh({"armL"}), "armR": solid_bvh({"armR"}), "legL": solid_bvh({"legL"}), "legR": solid_bvh({"legR"})}
def root(label, kind, bone, region, anchor, direction, L, wscale, tscale):
    P, (vs, mn, mx, ext, o), mats = (R07, F07, mat07) if kind == "r07" else (THN, FTH, matTh)
    bvh = REG[region]
    loc0, n0, _, _ = bvh.find_nearest(Vector(anchor))
    tdir = Vector(direction); tdir = (tdir - n0 * tdir.dot(n0)).normalized(); side = n0.cross(tdir).normalized()
    s = L / ext[o[0]]; cmid = (mn[o[1]] + mx[o[1]]) / 2
    out = []
    for v in vs:
        x = (v[o[0]] - mn[o[0]]) * s; y = (v[o[1]] - cmid) * s * wscale; z = (v[o[2]] - mn[o[2]]) * s * tscale
        g = loc0 + tdir * x + side * y
        sl, sn, _, _ = bvh.find_nearest(g)
        out.append(sl + sn * (0.008 + z))   # v5: lifted 8 mm so the roots read as raised
    bm = H.part_bm(P, out)
    rigid.append((label, bone, bm, mats, {"prefab": P["prefab"], "renderer": P["path"], "mesh": P["mesh"], "material": P["materials"][0]["name"]}, Matrix.Identity(4)))
UP = Vector((0, 0, 1))
WEB = [  # torso front (the gut stays partly bare)
    ("root_chest_0", "r07", "Spine2", "torso", (0.12, -0.32, 1.56), (0.35, 0, -1), 0.38, 0.85, 0.95),
    ("root_chest_1", "r07", "Spine2", "torso", (-0.15, -0.32, 1.58), (-0.4, 0, -1), 0.34, 0.85, 0.95),
    ("root_gut_0", "r07", "Spine1", "torso", (0.04, -0.42, 1.3), (1, 0, -0.6), 0.36, 0.8, 0.9),
    ("root_gut_1", "r07", "Spine1", "torso", (-0.08, -0.42, 1.22), (-1, 0, -0.35), 0.32, 0.8, 0.9),
    # torso back, two tendrils hanging from the back lump
    ("root_back_0", "r07", "Spine2", "torso", (0.13, 0.32, 1.62), (0.4, 0, -1), 0.36, 0.85, 0.95),
    ("root_back_1", "r07", "Spine2", "torso", (-0.13, 0.32, 1.6), (-0.4, 0, -1), 0.36, 0.85, 0.95),
    ("root_back_3", "r07", "Spine1", "torso", (0.18, 0.28, 1.26), (0.6, 0, -1), 0.3, 0.8, 0.9),
    # over the shoulders from the neck
    ("root_neck_0", "r07", "Spine2", "torso", (0.2, -0.05, 1.8), (0.5, -0.6, -0.6), 0.2, 0.75, 0.9),   # v8: 0.3 -> 0.2 m (off the armpit)
    ("root_neck_1", "r07", "Spine2", "torso", (-0.2, -0.05, 1.8), (-0.5, -0.6, -0.6), 0.2, 0.75, 0.9),
]
for sd, sx in (("Left", 1), ("Right", -1)):
    rg = "armL" if sx > 0 else "armR"; lg = "legL" if sx > 0 else "legR"
    ua, fa, hd_ = P_(f"{sd}Arm"), P_(f"{sd}ForeArm"), P_(f"{sd}Hand")
    ul, kn, ft = P_(f"{sd}UpLeg"), P_(f"{sd}Leg"), P_(f"{sd}Foot")
    WEB += [(f"root_uparm_{sd[0]}0", "r07", f"{sd}Arm", rg, ua + (fa - ua) * 0.25 + UP * 0.06, fa - ua + Vector((0, -0.2, 0)), 0.26, 0.8, 0.9),   # v7 pose fix: off the shoulder joint
            (f"root_uparm_{sd[0]}1", "r07", f"{sd}Arm", rg, ua + (fa - ua) * 0.35 + Vector((0, 0.1, 0)), fa - ua + Vector((0, 0.3, -0.2)), 0.24, 0.75, 0.9),
            (f"root_fore_{sd[0]}0", "r07", f"{sd}ForeArm", rg, fa + (hd_ - fa) * 0.05 + UP * 0.08, hd_ - fa + Vector((0, 0.25, 0)), 0.26 if sx < 0 else 0.3, 0.8, 0.9),
            (f"root_fore_{sd[0]}1", "r07", f"{sd}ForeArm", rg, fa + (hd_ - fa) * 0.3 + Vector((0, -0.1, 0)), hd_ - fa + Vector((0, -0.3, 0.1)), 0.2, 0.75, 0.9),
            (f"root_thigh_{sd[0]}0", "r07", f"{sd}UpLeg", lg, ul + (kn - ul) * 0.42 + Vector((sx * 0.1, -0.08, 0)), kn - ul + Vector((0, -0.1, 0)), 0.3, 0.8, 0.9),
            (f"root_thigh_{sd[0]}1", "r07", f"{sd}UpLeg", lg, ul + (kn - ul) * 0.4 + Vector((sx * 0.14, 0.03, 0)), kn - ul + Vector((sx * 0.2, 0, 0)), 0.28, 0.8, 0.9),
            (f"root_shin_{sd[0]}0", "r07", f"{sd}Leg", lg, kn + (ft - kn) * 0.25 + Vector((sx * 0.06, -0.08, 0)), ft - kn + Vector((0, -0.15, 0)), 0.28, 0.8, 0.9),
            (f"root_shin_{sd[0]}1", "r07", f"{sd}Leg", lg, kn + (ft - kn) * 0.4 + Vector((sx * 0.1, 0.02, 0)), ft - kn + Vector((sx * 0.3, 0, 0)), 0.22, 0.75, 0.9)]
# v5: a few roots branch into finer tips (smaller catacomb roots leaving the parent's end at an angle)
def tip(parent, ang, L):
    w = next(x for x in WEB if x[0] == parent)
    lab, kind, bone, region, anchor, direction, Lp = w[:7]
    loc0, n0, _, _ = REG[region].find_nearest(Vector(anchor)); d = Vector(direction); d = (d - n0 * d.dot(n0)).normalized()
    end = loc0 + d * Lp * 0.9
    return (parent + "_tip", "r07", bone, region, end, Matrix.Rotation(ang, 3, n0) @ d, L, 0.45, 0.6)
WEB += [tip("root_chest_0", 0.7, 0.14), tip("root_gut_0", -0.6, 0.15)]   # v8: the upper-arm tip dropped (armpit crumple, budget)
# v6: the shoulders after the pads are gone: small fused Hive lumps sunk 30-40 % of their depth into the shoulder (no seam),
# lopsided (four on the left, two on the right); deltoid lumps ride the upper arm, the ones on the trapezius ride Spine2.
def sunk_lump(label, bone, region_bvh, guess, size, sq, spin, sink=0.35):
    loc, n, _, _ = region_bvh.find_nearest(Vector(guess))
    if CONFORM_SHOULDERS:   # v7: the Brute's conform (as the helm) so they merge into the shoulder (no 35 % sink needed)
        conformed_lump(label, bone, loc, n, size * 1.15, (sq[0], sq[1]), sq[2], spin, region_bvh, seed=sum(map(ord, label)) % 97, flat=0.6)
        return
    rot = (Vector((0, 0, 1)).rotation_difference(n).to_matrix() @ Matrix.Rotation(spin, 3, 'Z')).to_euler()
    depth = 2 * size * sq[2]
    bm, W = lump_bm(loc + n * (depth * (0.5 - sink)), size, rot, sq)
    rigid.append((label, bone, bm, hive_mat, {"prefab": "TheHive", "renderer": "Visual/low", "mesh": "default (low)", "material": "TheHive_Mat"}, W))
SHB = {1: solid_bvh({"torso", "armL"}), -1: solid_bvh({"torso", "armR"})}
CONFORM_SHOULDERS = True
for sd, sx, lumps in (("Left", 1, ((0.0, 0.0, 0.07, "Arm", 0.4), (0.06, -0.06, 0.055, "Arm", 1.7), (-0.1, 0.03, 0.06, "Spine2", 2.6))),
                      ("Right", -1, ((0.0, 0.0, 0.06, "Arm", 1.2), (-0.09, 0.04, 0.045, "Spine2", 2.2)))):
    ua = P_(f"{sd}Arm")
    for k, (dx, dy, s_, bn, spin) in enumerate(lumps):
        g = ua + Vector((sx * dx, dy, 0.12)) + ((P_(f"{sd}ForeArm") - ua).normalized() * 0.05 if bn == "Arm" else Vector())   # v7 pose fix: deltoid lumps 5 cm down the arm, off the joint
        sunk_lump(f"shoulder_lump_{sd[0]}{k}", f"{sd}Arm" if bn == "Arm" else "Spine2", SHB[sx], g, s_, (1.25, 1.0, 0.6), spin)
for sd, sx, n_ in (("Left", 1, 2), ("Right", -1, 1)):
    ua, fa = P_(f"{sd}Arm"), P_(f"{sd}ForeArm")
    rg = "armL" if sx > 0 else "armR"
    for k in range(n_):
        WEB.append((f"root_shoulder_{sd[0]}{k}", "r07", f"{sd}Arm", rg, ua + (fa - ua) * 0.14 + Vector((sx * 0.02, (-0.06 if k == 0 else 0.07), 0.07)),   # v7 pose fix: start below the joint
                    fa - ua + Vector((0, (-0.15 if k == 0 else 0.2), 0)), 0.26, 0.8, 0.9))
for w in WEB: root(*w)

# the left palm: a small Hive lump in the palm with a Hive eye set in it (the WTF eye)
hd, he = P_("LeftHand"), P_("LeftHand_end"); ax = (he - hd).normalized()
pn = Vector((-0.55, -0.7, -0.45)).normalized()
palm_c = hd + (he - hd) * 0.45
ARMLB = solid_bvh({"armL"})
hh = ARMLB.ray_cast(palm_c + pn * 0.3, -pn, 0.3)
palm_s = hh[0] if hh[0] is not None else palm_c
bm, W = lump_bm(palm_s + pn * 0.03, 0.05, Euler((1.0, 0.3, 0.7)), (1.0, 1.2, 0.55))
moved = 0.0
for _ in range(10):   # lift out of the hand in 4 mm steps until it no longer cuts it (max 4 cm)
    if not BVHTree.FromBMesh(bm).overlap(ARMLB) or moved >= 0.04: break
    bmesh.ops.translate(bm, vec=pn * 0.004, verts=bm.verts); moved += 0.004
W = Matrix.Translation(pn * moved) @ W
pbvh = BVHTree.FromBMesh(bm)
rigid.append(("palm_lump", "LeftHand", bm, hive_mat, {"prefab": "TheHive", "renderer": "Visual/low", "mesh": "default (low)", "material": "TheHive_Mat"}, W))
h = pbvh.ray_cast(palm_c + pn * 0.5, -pn, 0.6)
if h[0] is not None:
    bm, W = globe_bm(h[0], h[1], 0.026, sink=0.12)   # v8: sunk 12 % (was 40 %: hidden in the lump), a little bigger
    rigid.append(("palm_eye", "LeftHand", bm, eye_mat, SRC_GLOBE, W))
    add_lid("palm_eye_rim", "LeftHand", h[0] + h[1] * 0.004, h[1], 0.024, open_=1.9)   # v8: the rim opened (sits above the eye, not over it)
# v8 (owner: "yes, with branches"): bare, gnarled dead-wood limbs out of the crust - the Elder's (gd_king) own back branches,
# separate pieces of its mesh (kept-triangle lists of gd_king.001, our data; survey in ../_ref/parts/elder_components.json and
# previews/branch_survey.png). No leaves, no needles. Rooted INTO the crust (the base sunk 4 cm), angled up and back, lopsided.
BRANCH_TINT = (0.5, 0.45, 0.4)   # darker dead wood than the Elder's (a runtime _Color on our material copy)
EL = LOAD("elder"); EL_V = [H.u2b(v) for v in EL["verts"]]; EL_T = [tuple(tr) for sm in EL["submeshes"] for tr in sm]
_par = list(range(len(EL_V)))
def _fe(a_):
    while _par[a_] != a_: _par[a_] = _par[_par[a_]]; a_ = _par[a_]
    return a_
for tr in EL_T:
    for i in tr[1:]: _par[_fe(i)] = _fe(tr[0])
_ec = {}
for k_, tr in enumerate(EL_T): _ec.setdefault(_fe(tr[0]), []).append(k_)
EL_COMPS = list(_ec.values())
def elder_piece(center):
    """the gd_king mesh piece whose centre is nearest `center` (Blender coords of the export): its triangle indices"""
    best = None
    for ks in EL_COMPS:
        vs_ = {i for k in ks for i in EL_T[k]}; c = sum((EL_V[i] for i in vs_), Vector()) / len(vs_)
        d_ = (c - Vector(center)).length
        if best is None or d_ < best[0]: best = (d_, ks)
    return best[1]
br_mat = H.part_material(EL["materials"][0], PR, "Elder_branch", tint=BRANCH_TINT)
_bn = br_mat.node_tree.nodes["Principled BSDF"]; _bn.inputs["Emission Strength"].default_value = 0.0
BR_SRC = {"tint_linear": BRANCH_TINT, "prefab": "gd_king", "renderer": "Visual/gd_king (SkinnedMeshRenderer, baked static)", "mesh": "gd_king.001, kept triangles (branches/elder_branch_tris.json)", "material": "Elder_mat"}
BRANCH_TRIS = {}
def branch(label, bone, piece_center, crust_labels, direction, length, spin, sink=0.04):
    ks = elder_piece(piece_center); BRANCH_TRIS[label] = ks
    vs_ = sorted({i for k in ks for i in EL_T[k]})
    P = [EL_V[i] for i in vs_]
    zlo = min(p.z for p in P); ext = max(p.z for p in P) - zlo
    basep = [p for p in P if p.z < zlo + 0.04 * ext]; b0 = sum(basep, Vector()) / len(basep)          # the base: the lowest end
    tipc = sum(P, Vector()) / len(P); ax = (tipc - b0).normalized()
    Lsrc = max((p - b0).length for p in P)
    d_ = Vector(direction).normalized()
    crust = bmesh.new()
    for lab_, bone_, bm_, m_, src_, W_ in rigid:
        if lab_ in crust_labels:
            me_ = bpy.data.meshes.new("t"); bm_.to_mesh(me_); crust.from_mesh(me_); bpy.data.meshes.remove(me_)
    cb = BVHTree.FromBMesh(crust)
    cc = sum((v.co for v in crust.verts), Vector()) / len(crust.verts)
    hit = cb.ray_cast(cc + d_ * 0.6, -d_, 0.8)
    root_pt = (hit[0] if hit[0] is not None else cc) - d_ * sink
    s = length / Lsrc
    R = (ax.rotation_difference(d_).to_matrix().to_4x4())
    R = Matrix.Rotation(spin, 4, d_) @ R
    # thicker than the Elder's twigs (gnarled limbs, not twigs): x1.7 across the branch's own axis, x1 along it
    k_ = 1.7; A = Matrix(((ax.x * ax.x, ax.x * ax.y, ax.x * ax.z), (ax.y * ax.x, ax.y * ax.y, ax.y * ax.z), (ax.z * ax.x, ax.z * ax.y, ax.z * ax.z)))
    Sa = (Matrix.Identity(3) * (s * k_) + A * (s * (1 - k_))).to_4x4()
    M = Matrix.Translation(root_pt) @ R @ Sa @ Matrix.Translation(-b0)
    bm = bmesh.new(); uvl = bm.loops.layers.uv.new("UVMap"); mp = {}
    for k in ks:
        tr = EL_T[k]
        for i in tr:
            if i not in mp: mp[i] = bm.verts.new(M @ EL_V[i])
        try: f_ = bm.faces.new([mp[i] for i in reversed(tr)])
        except ValueError: continue
        for lp, i in zip(f_.loops, reversed(tr)): lp[uvl].uv = EL["uv0"][i]
    rigid.append((label, bone, bm, br_mat, BR_SRC, M))
# (piece centres from the survey, Blender coords of the export: c27 the thick twisted limb, c22 the tall fork, c8 a small fork,
#  c110 a bent spur)
branch("branch_helm_limb", "Head", (1.664, 1.384, 18.929), ("helm_burst", "helm_back"), (0.3, 0.75, 0.95), 0.55, 0.6)
branch("branch_helm_fork", "Head", (2.476, 1.733, 20.011), ("helm_crown", "helm_back"), (-0.5, 0.65, 0.75), 0.36, 2.1)
branch("branch_shoulder_L", "Spine2", (0.818, 2.361, 19.265), ("shoulder_lump_L2",), (0.5, 0.6, 1.0), 0.7, 1.2)
branch("branch_shoulder_R", "Spine2", (0.973, 1.674, 18.634), ("shoulder_lump_R1",), (-0.65, 0.55, 0.6), 0.34, 4.0)
os.makedirs(os.path.join(OUT, "branches"), exist_ok=True)
json.dump({"about": "triangle indices (into the concatenated submeshes of gd_king.001, the Elder's SkinnedMeshRenderer) kept per branch; "
                    "the runtime bakes those triangles into a static mesh and places it with attach.json's transform. Our data.",
           "source": "gd_king / Visual/gd_king / gd_king.001", **BRANCH_TRIS}, open(os.path.join(OUT, "branches", "elder_branch_tris.json"), "w"))
for lab, bone, bm, m, src, W in rigid:
    ob = H.bm_object(bm, "Husk_" + lab, m if isinstance(m, list) else [m], smooth=(m is not hive_mat))
    PIECES[lab] = {"ob": ob, "mode": "rigid", "bone": bone, "source": src, "W": W}

# ---------------------------------------------------------------- fit, attach.json
def measure(ob, name):
    vs = [v.co.copy() for v in ob.data.vertices]; fs = [list(p.vertices) for p in ob.data.polygons]
    mine = BVHTree.FromPolygons(vs, fs)
    ds = []
    for p in vs:
        loc, n, idx, d = SOLID.find_nearest(p)
        if loc is not None: ds.append(d if (p - loc).dot(n) >= 0 else -d)
    ds.sort(); inner = [x for x in ds if 0 <= x < 0.015]
    others = [o["ob"] for k, o in PIECES.items() if k != name]
    ov, of, oo = [], [], 0
    for o in others:
        ov += [v.co.copy() for v in o.data.vertices]; of += [[oo + i for i in p.vertices] for p in o.data.polygons]; oo += len(o.data.vertices)
    ob_ = BVHTree.FromPolygons(ov, of)
    touch = any((ob_.find_nearest(p)[3] or 1) < 0.008 for p in vs[::3])
    near = min(abs(x) for x in ds)
    return {"base_pairs": len(mine.overlap(SOLID)), "hair_card_pairs": len(mine.overlap(CARDB)), "verts_inside_base": sum(1 for x in ds if x < -0.001),
            "inner_clear_median_mm": round(inner[len(inner) // 2] * 1000, 1) if inner else None, "nearest_to_base_mm": round(near * 1000, 1),
            "touches_other_piece": bool(touch), "floating": bool(near > 0.012 and not touch)}

attach = {"_about": ("ASSET-005 Barkbound Husk kitbash v2: vanilla parts on the vanilla Draugr. Rigid parts: the vanilla mesh under a "
                     "child of the named Draugr bone with the given local transform (Unity, bind pose; bones carry a bind scale of 110). "
                     "Skinned parts: the vanilla Player-rig mesh rebound to the Draugr: bones[i] = draugr_bone of the source bone, and "
                     "bindposes[i] = inverse(DraugrBoneBindWorld) * retarget_matrix_unity * PlayerBoneBindWorld * original_bindpose[i]."),
          "base": {"prefab": "Draugr", "renderer": "Cube.001", "mesh": J["mesh"], "material": J["material"]["name"], "tris": len(J["tris"])}}
total = 0
for name, pc in PIECES.items():
    ob = pc["ob"]; tri = sum(len(p.vertices) - 2 for p in ob.data.polygons); total += tri
    e = {"source": pc["source"], "mode": pc["mode"], "tris": tri, "fit": measure(ob, name)}
    if pc["mode"] == "rigid":
        Wu = S_ @ pc["W"] @ S_
        Bu = Matrix(J["bone_bind_world"][J["bone_names"].index(pc["bone"])])
        L = Bu.inverted() @ Wu
        loc, q, sc = L.decompose()
        e.update({"parent": pc["bone"], "localPosition": [round(x, 6) for x in loc], "localRotation": [round(q.x, 6), round(q.y, 6), round(q.z, 6), round(q.w, 6)],
                  "localScale": [round(x, 6) for x in sc]})
    else:
        e.update({"parent": "Draugr skeleton (rebound)", "bones_dominant": pc["bones_dominant"], "torso_fit": pc["torso_fit"], "retarget": pc["retarget"],
                  "offsets_file": pc["offsets_file"], "verts_offset": pc["verts_offset"], "kept_tris_file": pc["kept_tris_file"], "dropped_strand_tris": pc["dropped_strand_tris"], "dropped_shoulder_pad_tris": pc["dropped_shoulder_pad_tris"], "dropped_skirt_tris": pc["dropped_skirt_tris"]})
    if name in OFFSETS: e["vertex_offsets"] = "deform/lump_offsets.json#" + name
    attach[name] = e
os.makedirs(os.path.join(OUT, "deform"), exist_ok=True)
json.dump({"about": "per-vertex offsets (Unity metres, the vanilla mesh's own space; index = vanilla vertex index) added to a clone of TheHive `low` "
                    "for each conformed lump (the Hive Brute's lump deformation: body-facing half pulled 1 cm under the skin, heights flattened, "
                    "footprint spread). Our data; the vanilla mesh is never shipped.", "source": "TheHive / Visual/low / default", **OFFSETS},
          open(os.path.join(OUT, "deform", "lump_offsets.json"), "w"))
json.dump(attach, open(os.path.join(OUT, "attach.json"), "w"), indent=1)
ST = {"base_tris": len(J["tris"]), "addon_tris": total, "total_tris": len(J["tris"]) + total, "budget": 12000,
      "pieces": {k: {"tris": v["tris"], "parent": v.get("parent"), **v["fit"]} for k, v in attach.items() if not k.startswith("_") and k != "base"}}
json.dump(ST, open(os.path.join(PV, "stats.json"), "w"), indent=1)
print("KITBASH", json.dumps({k: ST[k] for k in ("base_tris", "addon_tris", "total_tris")}), "helm size", helm_size, "skull verts outside", helm_out, "of", len(skull))

# ---------------------------------------------------------------- v6 early repaint (owner approved for this pilot): the Draugr's own _MainTex,
# Runic style. Bark creep (R) from where the parts sit (helm, shoulder and back lumps, torso roots), fading out along the
# limbs; thin blight veins (G, BlightGlow emission) radiating from the eye clusters and the chest. Masks + recipe are ours.
# v7 (coordinator: "push it the way the Brute's repaint did"): kit_tools/troll_repaint.py, the Brute's method, scaled from the
# 5 m Troll to the 2.2 m Draugr (distances / 2.3). Mask RGBA in DraugrMesh1 UV0 (our data): R = bark spreading from the helm
# crust, shoulder lumps, back lump and the roots over the upper torso and upper arms (and over the Draugr's pale shoulder plates);
# G = sickly darkening towards hands, forearms, shins and feet; B = blight veins (thin, dark, branching; emission), kept off the
# head and fading out within 0.5 m of the Hive eyes; A = dark painted roots from the crust's edges. Computed at 2048 where it
# carries thin lines, box-filtered to the shipped 1024. The repainted albedo is a PREVIEW (derived from vanilla pixels; never shipped).
RP = os.path.join(OUT, "repaint"); os.makedirs(RP, exist_ok=True)
for _old in ("hive_repaint_mask.png",):   # v6's mask (kept in kit_v6/)
    if os.path.exists(os.path.join(RP, _old)): os.remove(os.path.join(RP, _old))
SC = 2.3                                       # Troll / Draugr size ratio
SZ, SZO = 2048, 1024
def _img(path, size):
    im = bpy.data.images.load(path, check_existing=False)
    if im.size[0] != size or im.size[1] != size: im.scale(size, size)
    a_ = np.empty(size * size * 4, np.float32); im.pixels.foreach_get(a_); bpy.data.images.remove(im)
    return a_.reshape(size, size, 4)
def _save(path, arr):
    h_, w_ = arr.shape[:2]; im = bpy.data.images.new(os.path.basename(path), w_, h_, alpha=True)
    im.pixels.foreach_set(np.ascontiguousarray(arr, np.float32).ravel()); im.filepath_raw = path; im.file_format = 'PNG'; im.save(); bpy.data.images.remove(im)
VSt = [tuple(v) for v in VS]; UV0 = J["uv0"]; TRI = [tuple(x) for x in J["tris"]]
head_tris = [tr for tr in TRI if sum(1 for i in tr if H.region_of(dom[i]) == "head") >= 2]
card_tris_ = [J["tris"][i] for i in sorted(CARDS)]
def _cov(tris_, size):
    pp, _ = TR.raster_position_map(VSt, tris_, UV0, size); return ~np.isnan(pp[..., 0])
def _down(a):
    return a.reshape(SZO, SZ // SZO, SZO, SZ // SZO, *a.shape[2:]).mean((1, 3))
# ---- smooth fields at 1024
pos1, nrm1 = TR.raster_position_map(VSt, TRI, UV0, SZO)
valid1 = ~np.isnan(pos1[..., 0]); P1 = pos1[valid1]
head1 = _cov(head_tris, SZO)[valid1]; card1 = _cov(card_tris_, SZO)[valid1]
src_names = [k for k in PIECES if k.startswith(("helm_", "shoulder_lump", "back_lump")) and not k.startswith("helm_eye")]
src_names += [k for k in PIECES if k.startswith("root_") and k not in ("root_chest", "root_legs") and attach[k]["parent"] in ("Spine1", "Spine2", "LeftArm", "RightArm")]
def _bvh_of(keys):
    sv, sf, so = [], [], 0
    for k in keys:
        o = PIECES[k]["ob"]; sv += [v.co.copy() for v in o.data.vertices]; sf += [[so + i for i in p_.vertices] for p_ in o.data.polygons]; so += len(o.data.vertices)
    return BVHTree.FromPolygons(sv, sf)
SRCB = _bvh_of(src_names); SHLB = _bvh_of([k for k in PIECES if k.startswith("shoulder_lump")])
dist = np.array([SRCB.find_nearest(Vector(q))[3] or 9.0 for q in P1])
dsh = np.array([SHLB.find_nearest(Vector(q))[3] or 9.0 for q in P1])
nz = TR.value_noise3(P1, 0.5 / SC, 11) * 0.35 / SC + TR.value_noise3(P1, 0.16 / SC, 12) * 0.15 / SC + TR.value_noise3(P1, 0.05 / SC, 13) * 0.05 / SC
bark_v = 1 - TR.smoothstep(0.0, 0.75 / SC, dist + nz)
# the Draugr's own pale shoulder plates (bright texels round the shoulder lumps) go fully under the bark, so the lumps merge
orig1 = _img(os.path.join(REF, J["material"]["textures"]["_MainTex"]["png"]), SZO)
lum1 = orig1[..., :3] @ np.array([0.3, 0.59, 0.11]); lum_n1 = lum1 / max(1e-6, lum1[valid1].mean())
plate = TR.smoothstep(0.32, 0.18, dsh + nz) * np.maximum(TR.smoothstep(1.0, 1.25, lum_n1[valid1]), TR.smoothstep(0.24, 0.12, dsh))
bark_v = np.maximum(bark_v, plate)
bark_v = np.where(head1, np.minimum(bark_v, 0.65), bark_v)       # the face stays readable under the brow
bark_v = np.where(card1, bark_v * 0.5, bark_v)                    # hair / beard cards: half (they keep their strands)
eL, hL, kL, fL = P_("LeftForeArm"), P_("LeftHand"), P_("LeftLeg"), P_("LeftFoot")
ext_v = np.maximum(TR.smoothstep(abs(eL.x) - 0.05, abs(hL.x) + 0.05, np.abs(P1[:, 0])) * (P1[:, 2] > kL.z + 0.4),
                   TR.smoothstep(kL.z + 0.12, fL.z, P1[:, 2]))
# ---- lines at 2048
pos2, _ = TR.raster_position_map(VSt, TRI, UV0, SZ)
valid2 = ~np.isnan(pos2[..., 0]); P2 = pos2[valid2]
noline2 = _cov(head_tris, SZ)[valid2] | _cov(card_tris_, SZ)[valid2]
def nearest(pt):
    loc, n, _, _ = SOLID.find_nearest(Vector(tuple(pt)))
    return (np.array(loc[:]), np.array(n[:])) if loc is not None else (None, None)
eye_locs = [np.array((sum((v.co for v in PIECES[k]["ob"].data.vertices), Vector()) / len(PIECES[k]["ob"].data.vertices))[:])
            for k in PIECES if k.startswith(("helm_eye", "palm_eye"))]
_r = np.random.default_rng(5)
s1, s2 = P_("Spine1"), P_("Spine2")
vein_starts = [(np.array((0.17 * sx, -0.36, s2.z + dz)), 0.011 / SC * 0.85, (sx, 0, dz * 4 + _r.uniform(-0.7, 0.7))) for sx in (-1, 1)
               for dz in (-0.22, -0.1, 0.0, 0.1)]
vein_starts += [(np.array((PIECES[k]["ob"].matrix_world @ (sum((v.co for v in PIECES[k]["ob"].data.vertices), Vector()) / len(PIECES[k]["ob"].data.vertices)))[:]),
                 0.009 / SC * 0.85, (_r.uniform(-1, 1), _r.uniform(-1, 1), -1)) for k in PIECES if k.startswith(("shoulder_lump", "back_lump")) for _ in range(2)]
veins = TR.smooth_curves(TR.walk_curves(nearest, vein_starts, 2, 0.75 / SC, 0.03 / SC, 21, branch=3.0 * SC, persist=0.35, jitter=0.45), nearest, 2)
root_starts = []
for k in PIECES:
    if k.startswith(("shoulder_lump", "back_lump", "helm_nape", "helm_back")):
        c = Vector(sum((v.co for v in PIECES[k]["ob"].data.vertices), Vector()) / len(PIECES[k]["ob"].data.vertices))
        out = c - Vector((0, 0.0, 2.05)); out.z = 0; out.normalize()
        root_starts.append((np.array(c[:]), 0.03 / SC, tuple(np.array(out[:]) + np.array([0, 0, -0.5]))))
roots_c = TR.walk_curves(nearest, root_starts, 3, 1.8 / SC, 0.05 / SC, 31, bias=(0, 0, -1), branch=0.8 * SC)
vein2 = TR.curves_mask(pos2, veins, fade=1.2)
halo2 = TR.curves_mask(pos2, [(pts, w0 * 3.5) for pts, w0 in veins], fade=1.6)
root2 = TR.curves_mask(pos2, roots_c)
if eye_locs:
    de = np.min(np.stack([np.linalg.norm(P2 - e, axis=1) for e in eye_locs]), 0)
    keep = TR.smoothstep(0.25, 0.5, de)                            # veins fade out within 0.5 m of the Hive eyes
else:
    keep = np.ones(len(P2))
for a_ in (vein2, halo2, root2):
    vv_ = a_[valid2]; vv_ = np.where(noline2, 0.0, vv_)
    if a_ is not root2: vv_ = vv_ * keep
    a_[valid2] = vv_
mask2 = np.zeros((SZ, SZ, 2)); mask2[..., 0] = np.maximum(vein2, 0.12 * halo2); mask2[..., 1] = root2 * 0.92
mask_l = _down(mask2)
mask = np.zeros((SZO, SZO, 4))
mask[..., 0][valid1] = bark_v; mask[..., 1][valid1] = ext_v
mask[..., 2] = mask_l[..., 0]; mask[..., 3] = mask_l[..., 1]
mask = TR.dilate_fill(mask, valid1, 8)
_save(os.path.join(RP, "husk_hive_mask.png"), mask)
# ---- the recipe and the preview albedo / emission (derived from vanilla pixels: PREVIEW ONLY)
REC = {"about": "ASSET-005 early repaint recipe: the Hive Brute's method (kit_tools/troll_repaint.py) scaled to the Draugr (distances / 2.3). "
                "Mask = repaint/husk_hive_mask.png in DraugrMesh1 UV0 (R bark, G extremity darkening, B blight veins = emission, A dark roots), "
                "lines computed at 2048 and box-filtered to 1024. Colours are linear multipliers on the texture's stored texel values, as the "
                "runtime reads them back; the vanilla luminance is kept (lum / mean lum) so the Draugr still reads.",
       "sick_skin": [0.3, 0.32, 0.24], "sick_mix": 0.55, "extremity_darken": 0.5, "bark_tint": [0.62, 0.46, 0.3], "infection_margin_darken": 0.45,
       "bark_texture": "olivetree_trunk01 (TheHive_Mat _MainTex), triplanar in rest-pose metres, tile 0.52 m",
       "root_colour": [0.03, 0.025, 0.02], "vein_albedo": [0.05, 0.06, 0.02], "blight_colour": [0.42, 0.55, 0.12], "emission_strength_preview": 0.85,
       "draugr_eye_glow": 0.1, "root_armour_recolour": ROOT_RECOLOUR, "draugr_eye_glow_note": "multiplier on the Draugr's own _EmissionColor (its green eyes under the brow), so the Hive eyes lead",
       "veins": "off the head and the hair/beard cards; faded out within 0.25-0.5 m of the Hive eyes", "mask_size": "1024 (lines computed at 2048, box-filtered)"}
json.dump(REC, open(os.path.join(RP, "repaint.json"), "w"), indent=1)
btex = _img(os.path.join(PR, LP["materials"][0]["textures"]["_MainTex"]["png"]), 512)[..., :3]
Nv = np.abs(nrm1[valid1]); axis = Nv.argmax(1)
uu = np.where(axis == 0, P1[:, 1], P1[:, 0]); vv = np.where(axis == 2, P1[:, 1], P1[:, 2])
TILE_M = 1.2 / SC
px = ((uu / TILE_M) % 1.0 * 510).astype(int); py = ((vv / TILE_M) % 1.0 * 510).astype(int)
BKs = (btex[py, px] + btex[py + 1, px] + btex[py, px + 1] + btex[py + 1, px + 1]) * 0.25
ln = np.clip(lum_n1[valid1], 0, 2.5)[:, None]
barkcol = BKs * np.array(REC["bark_tint"]) * (0.45 + 0.55 * np.clip(ln, 0, 2))
O1 = orig1[..., :3][valid1]
sick = O1 * (1 - REC["sick_mix"]) + ln * np.array(REC["sick_skin"]) * REC["sick_mix"]
colv = sick * (1 - bark_v[:, None]) + barkcol * bark_v[:, None]
colv *= (1 - REC["extremity_darken"] * ext_v)[:, None]
colv *= (1 - REC["infection_margin_darken"] * 4 * bark_v * (1 - bark_v))[:, None]
rm_ = mask[..., 3][valid1][:, None]; colv = colv * (1 - rm_) + np.array(REC["root_colour"]) * rm_
vm_ = mask[..., 2][valid1][:, None]; colv = colv * (1 - vm_) + np.array(REC["vein_albedo"]) * vm_
OUTA = orig1.copy(); OUTA[..., :3][valid1] = colv
OUTA = TR.dilate_fill(OUTA, valid1, 8); OUTA[..., 3] = orig1[..., 3]
_save(os.path.join(RP, "preview_albedo_DO_NOT_SHIP.png"), OUTA)
EM = np.zeros((SZO, SZO, 4)); EM[..., 3] = 1
for c_ in range(3): EM[..., c_] = mask[..., 2] * REC["blight_colour"][c_] * REC["emission_strength_preview"]
_save(os.path.join(RP, "preview_blight_emission.png"), EM)
JM = json.loads(json.dumps(J["material"])); JM["textures"]["_MainTex"]["png"] = os.path.join(RP, "preview_albedo_DO_NOT_SHIP.png")
Jr = dict(J); Jr["material"] = JM
rmat = H.base_material(Jr, REF, "Draugr_repaint")
nt = rmat.node_tree; bsdf = nt.nodes["Principled BSDF"]
vt = nt.nodes.new("ShaderNodeTexImage"); vt.image = bpy.data.images.load(os.path.join(RP, "preview_blight_emission.png")); vt.image.colorspace_settings.name = 'Non-Color'
old = bsdf.inputs["Emission Color"].links[0].from_socket if bsdf.inputs["Emission Color"].links else None
if old is not None:      # the Draugr's own emission (its eyes) + the blight veins
    ad = nt.nodes.new("ShaderNodeMix"); ad.data_type = 'RGBA'; ad.blend_type = 'ADD'; ad.inputs[0].default_value = 1.0
    dim = nt.nodes.new("ShaderNodeMix"); dim.data_type = 'RGBA'; dim.blend_type = 'MULTIPLY'; dim.inputs[0].default_value = 1.0
    nt.links.new(old, dim.inputs[6]); dim.inputs[7].default_value = (REC["draugr_eye_glow"],) * 3 + (1,); old = dim.outputs[2]
    nt.links.new(old, ad.inputs[6]); nt.links.new(vt.outputs["Color"], ad.inputs[7]); nt.links.new(ad.outputs[2], bsdf.inputs["Emission Color"])
else:
    nt.links.new(vt.outputs["Color"], bsdf.inputs["Emission Color"]); bsdf.inputs["Emission Strength"].default_value = 1.0
# the Draugr's own emission strength multiplies the summed colour: scale the vein image so the veins land at the recipe's strength
_S = bsdf.inputs["Emission Strength"].default_value or 1.0
if old is not None and abs(_S - 1.0) > 1e-3:
    _save(os.path.join(RP, "preview_blight_emission.png"), np.concatenate([EM[..., :3] / _S, EM[..., 3:]], -1)); vt.image.reload()
ORIG_MAT = base.data.materials[0]; base.data.materials[0] = rmat
paths = veins
REPAINT = {"bark_texels": int((bark_v > 0.05).sum()), "bark_over_half_pct": round(float((bark_v > 0.5).mean() * 100), 1), "covered_texels": int(valid1.sum()),
           "vein_texels": int((mask[..., 2] > 0.3).sum()), "vein_paths": len(veins), "root_curves": len(roots_c), "extremity_texels": int((ext_v > 0.3).sum())}
print("REPAINT", REPAINT)

# ---------------------------------------------------------------- previews (all real game materials, Runic lighting)
H.setup_eevee(900, 1100); H.lights_and_world(aim=(0, 0, 1.15))
tgt = Vector((0, 0, 1.12))
def shots(prefix, views=(("front", 0, 4), ("side", -90, 4), ("back", 180, 4), ("34", -35, 12), ("34back", 145, 12))):
    for nm, az, el in views:
        H.camera(tgt, 4.6, az, el, lens=55); H.render(os.path.join(PV, f"{prefix}_{nm}.png"))
shots("kit")
for pc in PIECES.values(): pc["ob"].hide_render = True
base.data.materials[0] = ORIG_MAT; shots("base", views=(("front", 0, 4), ("34", -35, 12)))   # the untouched Draugr, for the before / after
base.data.materials[0] = rmat; H.camera(tgt, 4.6, -35, 12, lens=55); H.render(os.path.join(PV, "base_repaint_34.png"))
for pc in PIECES.values(): pc["ob"].hide_render = False
sc = bpy.context.scene; sc.render.resolution_x = sc.render.resolution_y = 900
H.camera(hc + Vector((0, 0, -0.02)), 1.4, -25, 8, lens=55); H.render(os.path.join(PV, "close_helm.png"))
H.camera(hc + Vector((0, 0, -0.02)), 1.4, 155, 8, lens=55); H.render(os.path.join(PV, "close_helm_back.png"))
cam = H.camera(hd, 1.0, 0, 0, lens=55); cam.location = palm_c + (pn + Vector((0, -0.3, 0.1))).normalized() * 0.75
cam.rotation_euler = (palm_c - cam.location).normalized().to_track_quat('-Z', 'Y').to_euler(); H.render(os.path.join(PV, "close_palm_eye.png"))
H.camera(Vector((0, 0.15, 1.35)), 2.0, 160, 10, lens=55); H.render(os.path.join(PV, "close_back_growth.png"))
H.camera(P_("RightHand"), 1.2, -60, 5, lens=55); H.render(os.path.join(PV, "close_right_hand_attach.png"))
H.camera(Vector((0, 0, 1.3)), 2.4, -30, 8, lens=55); H.render(os.path.join(PV, "close_torso.png"))
H.camera(P_("LeftArm") + Vector((0, 0, 0.05)), 1.3, 45, 22, lens=55); H.render(os.path.join(PV, "close_shoulder.png"))
H.camera(P_("RightArm") + Vector((0, 0, 0.05)), 1.3, -45, 22, lens=55); H.render(os.path.join(PV, "close_shoulder_right.png"))
_e = [o for k, o in ((k, pc["ob"]) for k, pc in PIECES.items()) if k.startswith("helm_eye_front_l")]
if _e:
    _c = sum((sum((v.co for v in o.data.vertices), Vector()) / len(o.data.vertices) for o in _e), Vector()) / len(_e)
    H.camera(_c, 0.45, 20, 5, lens=55); H.render(os.path.join(PV, "close_eye_1to1.png"))
# lineup: 1.8 m figure | the base | base + parts
import hivekit_b as K
fig = K.figure(-1.4, 0.0)
_fm = fig.data.materials[0]; _fm.use_nodes = True; _fm.node_tree.nodes["Principled BSDF"].inputs["Base Color"].default_value = (0.2, 0.4, 0.9, 1)
twin = base.copy(); twin.data = base.data; sc.collection.objects.link(twin); twin.location.x = 1.3
for pc in PIECES.values():
    o2 = pc["ob"].copy(); o2.data = pc["ob"].data; sc.collection.objects.link(o2); o2.location.x = 1.3
for pc in PIECES.values(): pc["ob"].hide_render = True
sc.render.resolution_x, sc.render.resolution_y = 1600, 900
H.camera(Vector((0, 0, 1.1)), 8.0, -12, 4, lens=55); H.render(os.path.join(PV, "lineup.png"))
for o in list(bpy.data.objects):   # drop the lineup copies and the figure before saving
    if o.name.endswith(".001") or o.name.startswith("Figure"): bpy.data.objects.remove(o, do_unlink=True)
base.location.x = 0
for pc in PIECES.values(): pc["ob"].hide_render = False
bpy.ops.wm.save_as_mainfile(filepath=os.path.join(OUT, "BarkboundHusk_kitbash.blend"))


# ---------------------------------------------------------------- README (measured numbers only)
att = json.load(open(os.path.join(OUT, "attach.json")))
L = ["# ASSET-005 Barkbound Husk: kitbash v2 (vanilla parts on the vanilla Draugr), step 1", "",
     "Built by `../make_husk_kitbash.py` (deterministic, seed 5606). Parts exported from the 1.0.21 bundle `c4210710` by",
     "`../../../kit_tools_b/export_part.py`, the base by `export_base.py`, into `../_ref/` (game data, dev reference, never shipped).",
     "Everything is rendered in its REAL game material (no placeholder colours). Every number below was measured by that run.", "",
     "## Triangles (measured)", "",
     f"- Base (vanilla Draugr `Cube.001` / `{J['mesh']}`): **{ST['base_tris']}**",
     f"- Vanilla parts on it: **{ST['addon_tris']}**",
     f"- Total: **{ST['total_tris']}** of 12000 ({'PASS' if ST['total_tris'] <= 12000 else 'FAIL'})", "",
     "## Parts, sources and attach (attach.json has the full transforms)", "",
     "| part | source prefab / renderer / mesh | material | rides | mode | tris |", "|---|---|---|---|---|---|"]
for k, v in att.items():
    if k.startswith("_") or k == "base": continue
    s = v["source"]
    L.append(f"| {k} | {s['prefab']} / {s['renderer']} / {s['mesh']} | {s['material']} | {v['parent']} | {v['mode']} | {v['tris']} |")
L += ["", "Rigid parts (localPosition / localRotation xyzw / localScale, Unity, bone-relative, bind pose; bones carry a bind scale of 110):", "",
      "| part | bone | localPosition | localRotation | localScale |", "|---|---|---|---|---|"]
for k, v in att.items():
    if k.startswith("_") or k == "base" or v["mode"] != "rigid": continue
    L.append(f"| {k} | {v['parent']} | {v['localPosition']} | {v['localRotation']} | {v['localScale']} |")
L += ["", "Skinned parts (Root armour): the vanilla Player-rig mesh REBOUND to the Draugr skeleton. `retarget` in attach.json gives, per",
      "source bone, the Draugr bone it follows and a 4x4 (Unity) retarget matrix (turn 180 deg, bone-to-bone move, segment direction and",
      "length, plus an affine torso fit from the Draugr's own cross-section: " + ", ".join(f"{b} x{v['scale_x']} / depth x{v['scale_y_front_back']}" for b, v in att["root_chest"]["torso_fit"].items()) + ").",
      "New bindposes = inverse(Draugr bone bind) x retarget x Player bone bind x original bindpose. The remaining fit is a per-vertex offset",
      f"(`root_chest_offsets.json`: {att['root_chest']['verts_offset']} vertices, `root_legs_offsets.json`: {att['root_legs']['verts_offset']}) pushing it 4 mm off the Draugr;",
      "these offsets are our data, applied to the cloned vanilla mesh at runtime, so no vanilla geometry is shipped.", "",
      "## Fit (bind pose, against the Draugr's SOLID body; its hair/beard strand cards counted apart)", "",
      "| part | base pairs | card pairs | inner clearance median (mm) | nearest (mm) | touches another part | floating |", "|---|---|---|---|---|---|---|"]
tp = tc = 0
for k, v in att.items():
    if k.startswith("_") or k == "base": continue
    f = v["fit"]; tp += f["base_pairs"]; tc += f["hair_card_pairs"]
    L.append(f"| {k} | {f['base_pairs']} | {f['hair_card_pairs']} | {f['inner_clear_median_mm']} | {f['nearest_to_base_mm']} | {f['touches_other_piece']} | {f['floating']} |")
L += [f"| **total** | **{tp}** | {tc} | | | | |", "",
      "## v4 (owner: \"smaller roots, but more of them, better eyes\")", "",
      f"- Roots: the Root armour's own thick root strands are dropped (chest {att['root_chest']['dropped_strand_tris']} tris, legs {att['root_legs']['dropped_strand_tris']} tris: one UV island of AbominationArmor); its bark plates stay (v6: the shoulder pads and the skirt go too, below).",
      f"- {sum(1 for k in att if k.startswith('root_') and k not in ('root_chest', 'root_legs'))} small roots (catacomb `fi_vil_combs_root07`, 0.2-0.38 m, laid 8 mm raised and darkened onto the torso, arms and legs, each on the bone it lies on.",
      "- Eyes (v4: close_eye_options.png compared the Hatchling eyeball, the Hive's built-in Sphere, GreydwarfEye, GreydwarfEye with the Hive glow, the Gjall eye and the Morkhalla eye): v5, after the owner's '3 big ass whats?': SMALL eyes at the Draugr's own eye scale (38 mm across, measured from its emission map): nine Hatchling half-domes, radius 15-34 mm (0.8x-1.8x the Draugr's eye), in four tight lopsided clusters (front left 4, front right 2, right side 1, back 2), half-sunk in the bark under one flattened Hive-lump rim per cluster; the palm eye is one small dome sunk in the palm lump under its own rim. TheHive_Eye's texture with a lowered glow (bright core, darker rim). The 768-tri built-in sphere was dropped as overkill at this size.",
      "- Removed for budget: the vines drape, the WrithanRoots clump, the three hanging ThornRoots (the new roots cover the back), the twelve old Hatchling eyes.", "",
      "## v6 (owner: \"yes, strip the shoulder pads, you're allowed to go into, sure, as long as the end result isn't jank\")", "",
      f"- Shoulder pads stripped: {att['root_chest']['dropped_shoulder_pad_tris']} Root armour tris (connected pieces with centroid above 1.5 m, plus pad fragments under 40 tris above 1.2 m) leave the kept-triangle list.",
      f"- Skirt cut (pose-test fix): {att['root_chest']['dropped_skirt_tris']} more tris, everything below the belt (centroid under {SKIRT_Z} m) and the loose belt-height strips the cut left (pieces centred under {SKIRT_TOP} m). In the crouch the 10+ cm hanging skirt tore into flat shards whatever weights it got; the Draugr's own loincloth now shows and deforms with its own vanilla weights.",
      f"- Over the bare shoulders: {sum(1 for k in att if k.startswith('shoulder_lump'))} fused Hive lumps (TheHive `low`), lopsided: 3 left, 2 right; v7: CONFORMED (the Brute's lump deformation, below) so they merge into the shoulder; the Draugr's pale shoulder plates are repainted into the bark under them. Deltoid lumps ride the upper arm, trapezius lumps Spine2. Plus {sum(1 for k in att if k.startswith('root_shoulder'))} small roots over them and down the arm (2 left, 1 right).",
      f"- Helm (v7; coordinator: 'it reads as a bark bucket hat'): no enclosing mass. {sum(1 for k in att if k.startswith('helm_') and not k.startswith('helm_eye'))} TheHive `low` lumps (crown, back, brow, both temples, both cheeks, nape; heavier on the left) CONFORMED with the Hive Brute's lump deformation (kit_tools/make_brute_kitbash.py conform(), same maths, scaled to the Draugr): the body-facing half pulled onto the skull and 1 cm under it, heights flattened with a ridge noise, footprint spread 60 %, so the bark grows out of the skull, brow, temples, cheeks and nape and the mounds run into each other; the Draugr's face shows under the brow. Per-vertex offsets in `../deform/lump_offsets.json` (our data). {helm_out} of {len(skull)} solid skull vertices are left uncovered (the face). The four v5 eye rims are gone (the crust's creases are the sockets; their 952 tris paid for the crust).",
      f"- Leg roots moved off the hip and knee creases to the outer thigh / shin (pose-test fix: in the crouch they sank 23-75 mm into the folded leg).",
      "- Eyes (v7; coordinator: 'copy the Brute's method exactly'): the `eye_globe` dome (50 tris, its own UVs) with TheHive_Eye's texture, an amber-red emission core and a dark vertical slit pupil baked into a mask in eye_globe's own UVs (`../eye/eye_globe_core_pupil_mask.png`, our data: _EmissionMap + a darkening of _MainTex), a darker wet base with a clear coat; the same code as the Brute's eye_material(). Sizes (0.8-1.8x the Draugr's eye) and the four clusters kept; each dome is 40 % sunk into the crust. See `close_eye_1to1.png`.",
      f"- Repaint (v7: the Brute's method, kit_tools/troll_repaint.py, distances scaled / 2.3; masks + recipe in `../repaint/`, our data; the Draugr's own `_MainTex` is read back at runtime): `husk_hive_mask.png` (1024; lines computed at 2048 and box-filtered) R = bark from the helm crust, shoulder lumps, back lump and the torso / upper-arm roots over the upper torso and upper arms ({REPAINT['bark_over_half_pct']} % of the used texels over half) and over the pale shoulder plates; G = sickly darkening of hands, forearms, shins and feet ({REPAINT['extremity_texels']} texels); B = {REPAINT['vein_paths']} thin dark branching veins (emission), off the head and cards and faded out within 0.5 m of the Hive eyes; A = {REPAINT['root_curves']} dark painted roots. The skin is desaturated toward a sick olive (55 %), the bark keeps the Draugr's luminance. `base_repaint_34.png` shows the base alone repainted; `base_front.png` / `base_34.png` are the untouched Draugr.",
      "- Pose test: see the section at the end (written by `../pose_test.py`, which also writes `../transfer_weights.json` and marks the skinned pieces in attach.json).", "",
      "## v8 (owner approved the direction: \"yes, with branches\")", "",
      f"- Branches: {sum(1 for k in att if k.startswith('branch_'))} bare dead-wood limbs ({sum(att[k]['tris'] for k in att if k.startswith('branch_'))} tris), separate pieces of the Elder's own mesh (gd_king.001: its back branches; kept-triangle lists in `../branches/elder_branch_tris.json`; survey `../_ref/parts/elder_components.json`): a thick twisted limb and a small fork out of the back / burst of the helm (Head), a tall fork out of the left trapezius lump and a bent spur out of the right one (Spine2). Base sunk 4 cm into the crust, angled up and back, lopsided; 1.7x thicker across their axis than the Elder's twigs, darkened (tint 0.5 / 0.45 / 0.4). No leaves, no needles.",
      "- Helm erupting: crown, back and a new burst lump rise up and back (less flattened, less spread), the brow is bigger and stands forward as an overhang with the eye clusters on its face; the dimmed green Draugr eyes show under it.",
      "- The Root armour's green belly plates recoloured into the bark (saturation 0.3 x tint 0.95 / 0.72 / 0.5; repaint.json root_armour_recolour).",
      "- Palm eye sunk 12 % (was 40 %: hidden) and its rim opened; arms-up armpit: the neck roots end on the shoulder top (0.2 m), the upper-arm tip root dropped; veins 40 % wider and emission 0.85 (still dark albedo).", "",
      "## New geometry", "", "None. Every triangle is vanilla (TheHive `low`, gd_king's own branch pieces, `eye_globe` (the Hive eyes), `fi_vil_combs_root07`, the plain ThornRoots strand, Root armour chest and legs (bark plates only; v6 drops its pads and skirt); no tree meshes).",
      "Vertex positions of the Root armour are moved (retarget + push-out offsets); the eyes are only placed, rotated and scaled; the helm and shoulder lumps are placed and then conformed (per-vertex offsets, our data); the small roots are laid onto the body (a per-vertex bend, our data); the Root armour keeps its bark plates and drops its own thick root strands, its shoulder pads and its skirt (kept-triangle lists).",
      "The Hive eye uses the `eye_globe` GEOMETRY with TheHive_Eye's MATERIAL (+ our core / slit mask), as the Hive Brute does, because TheHive's own EYE is Unity's built-in sphere (768 tris each). The helm and shoulder lumps carry per-vertex offsets (`deform/lump_offsets.json`).", "",
      "## Previews", "",
      "- `kit_front.png`, `kit_side.png`, `kit_back.png`, `kit_34.png`, `kit_34back.png`: base + parts; `base_front.png`, `base_34.png`: base alone",
      "- `close_helm.png`, `close_helm_back.png` (the eye ring all the way round), `close_palm_eye.png`, `close_back_growth.png`, `close_torso.png`,",
      "  `close_right_hand_attach.png` (nothing on the right hand; the Root armour's own forearm roots stop at the wrist)",
      "- `close_shoulder.png`, `close_shoulder_right.png` (v6 shoulders), `close_eye_1to1.png` (eyes at 1:1)",
      "- `base_repaint_34.png`: the base alone with the early repaint",
      "- `lineup.png`: 1.8 m figure, the base, base + parts", "",
      "Kit v1 (our own fitted geometry in placeholder colours) is kept in `../../kit_v1/`; v2-v5 in `../../kit_v2/` .. `../../kit_v5/`.", ""]
open(os.path.join(PV, "README.md"), "w").write("\n".join(L) + "\n")
