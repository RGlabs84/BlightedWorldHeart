"""ASSET-004 Eyeblight Seer, kitbash v1 (Runic method, as the Hive Brute and the Barkbound Husk): VANILLA parts in their real
materials on the real vanilla Greydwarf_Shaman. Approved direction (owner): "yes, with branches".

Base: Greydwarf_Shaman `Cube` + `Cube.001` (merged: same material, same skeleton; 1,418 tris). Its two eye quads (`Plane`,
`Plane.001`, eye_shaman, green emission) are HIDDEN: the Seer's eyes belong to the Hive now (the eye bulb).
Add-ons (all exported from the 1.0.21 bundle into _ref/parts/; game data, never shipped):
- TheHive `low` lumps (TheHive_Mat), CONFORMED with the Hive Brute's lump deformation (per-vertex offsets, deform/lump_offsets.json):
  the EYE BULB on the forehead with a crest and a cheek growth, two on the back hunch, one per shoulder, two maw lips.
- Hive eyes: the Brute's `eye_globe` + TheHive_Eye + our core / slit-pupil mask (eye/eye_globe_core_pupil_mask.png): MANY of them
  in the bulb, varied sizes, one dominant - its identity.
- The WTF (v2): a too-wide maw under the eye bulb - two wide conformed lips, the Troll's own claws and teeth as ragged fangs, a dark gullet painted
  behind it.
- A small root web: catacomb `fi_vil_combs_root07`, laid onto the body, darkened.
- Branches: the Elder's (gd_king.001) own thick bent limbs (kept-triangle lists, branches/elder_branch_tris.json), dark weathered
  grey-brown, rooted into the back hunch and the right shoulder.
- Early repaint of the Shaman's own _MainTex (the Brute's troll_repaint method): masks + recipe in repaint/.
The Shaman FACES +Y (Blender); every camera here is offset by 180 deg from the Husk's.
Run: heavy.sh 4G sb-seer blender -b --factory-startup -P make_seer_kitbash.py -- <abs kit dir>
"""
import bpy, bmesh, sys, os, math, json, random
import numpy as np
from mathutils import Vector, Matrix, Euler
from mathutils.bvhtree import BVHTree
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "..", "kit_tools_b"))
import hivefit as H
sys.path.append(os.path.join(HERE, "..", "..", "kit_tools"))
import troll_repaint as TR

OUT = sys.argv[sys.argv.index("--") + 1] if "--" in sys.argv else HERE
PV = os.path.join(OUT, "previews"); os.makedirs(PV, exist_ok=True)
REF = os.path.join(OUT, "_ref"); PR = os.path.join(REF, "parts")
SEED = 4404; rnd = random.Random(SEED)
FA = 180.0                       # camera azimuth of the creature's front (it faces +Y)
bpy.ops.wm.read_factory_settings(use_empty=True)
base, J, dom = H.load_base(REF, "Shaman_base")
def region(b):
    if b == "head": return "head"
    if b.startswith(("l_shoulder", "l_arm", "l_hand", "l_index", "l_middle", "l_pinky")): return "armL"   # l_shoulder skins the upper arm
    if b.startswith(("r_shoulder", "r_arm", "r_hand", "r_index", "r_middle", "r_pinky")): return "armR"
    if b.startswith(("l_leg", "l_foot", "l_hip")): return "legL"
    if b.startswith(("r_leg", "r_foot", "r_hip")): return "legR"
    return "torso"
VS = [v.co.copy() for v in base.data.vertices]
RV = [region(d) for d in dom]
BONES = H.bone_frames(J)
def P_(n): return BONES[n].translation.copy() if n in BONES else H.node_pos(J, n)
HB = P_("head")
# the Shaman's own antlers are part of its mesh and ride spine3 / spine2 (they grow from the hunch above its face): every polygon
# centred above 2.15 m. The crust never conforms onto them. Its HEAD is the long face block (y 0.25-0.51, z 1.28-2.07: brow to beard).
_hv = [VS[i] for i in range(len(VS)) if RV[i] == "head"]
HC = sum(_hv, Vector()) / len(_hv)                                   # the face block's centre
ANTLER = set()
for p in base.data.polygons:
    c = sum((VS[i] for i in p.vertices), Vector()) / len(p.vertices)
    if c.z > 2.15: ANTLER.add(p.index)
def solid_bvh(regions, exclude=()):
    fs = []
    for p in base.data.polygons:
        if p.index in exclude: continue
        rs = [RV[i] for i in p.vertices]
        if max(set(rs), key=rs.count) in regions: fs.append(list(p.vertices))
    return BVHTree.FromPolygons(VS, fs)
ALLR = {"torso", "head", "armL", "armR", "legL", "legR"}
SOLID = solid_bvh(ALLR)
HEADS = solid_bvh({"head"}, ANTLER)
TORSO = solid_bvh({"torso"}, ANTLER)
REG = {r: solid_bvh({r}, ANTLER) for r in ALLR}
LOAD = lambda k: json.load(open(os.path.join(PR, k + ".json")))
S_ = Matrix(((1, 0, 0, 0), (0, 0, 1, 0), (0, 1, 0, 0), (0, 0, 0, 1)))
PIECES = {}; rigid = []; OFFSETS = {}
print("SKULL", [round(x, 3) for x in HC], "antler polys", len(ANTLER))

# ---------------------------------------------------------------- Hive lumps (conformed: the Brute's lump deformation)
LP = LOAD("hivelump")
lump_local = [H.u2b(v) for v in LP["verts"]]
lc = sum(lump_local, Vector()) / len(lump_local)
lext = max(max(abs((v - lc)[k]) for v in lump_local) for k in range(3))
hive_mat = H.part_material(LP["materials"][0], PR, "TheHive_Mat", moss=True)
HIVE_SRC = {"prefab": "TheHive", "renderer": "Visual/low", "mesh": "default (low) + vertex offsets (deform/lump_offsets.json)", "material": "TheHive_Mat"}
def lump_bm(center, size, rot, squash=(1, 1, 1)):
    bm = H.part_bm(LP, [((v - lc) / lext) for v in lump_local])
    M = Matrix.Translation(center) @ rot.to_matrix().to_4x4() @ Matrix.Diagonal((size * squash[0], size * squash[1], size * squash[2], 1))
    bmesh.ops.transform(bm, matrix=M, verts=bm.verts)
    return bm, M @ Matrix.Translation(-lc) @ Matrix.Scale(1 / lext, 4)
SC = 5.0 / 2.86          # Troll / Shaman size ratio (the Brute's distances scale by it)
UNDER = 0.02 / SC
NZF = SC
def _ss(e0, e1, x):
    t_ = min(1.0, max(0.0, (x - e0) / (e1 - e0))); return t_ * t_ * (3 - 2 * t_)
def conform_bm(label, bm, W, zdir, target, flat=0.55, cfrac=0.55, ridge=0.3, spread=0.6, seed=0):
    """the Hive Brute's conform() (kit_tools/make_brute_kitbash.py), as on the Husk v7b/v8 (wraps vertices beyond the target's edge)"""
    zd = Vector(zdir).normalized(); bm.verts.ensure_lookup_table()
    Wl = [v.co.copy() for v in bm.verts]
    Cc = sum(Wl, Vector()) / len(Wl)
    pz = [w.dot(zd) for w in Wl]; lo, hi = min(pz), max(pz)
    r = random.Random(seed); ph = [r.uniform(0, 6.28) for _ in range(4)]
    Rfoot = max(((w - Cc) - zd * (w - Cc).dot(zd)).length for w in Wl) * (1 + spread)
    Wi = W.inverted(); offs = []
    for v, w, z_ in zip(bm.verts, Wl, pz):
        t_ = (hi - z_) / max(hi - lo, 1e-6)
        rv = (w - Cc) - zd * (w - Cc).dot(zd)
        wt = w + rv * (spread * _ss(0.15, 1.0, t_))
        nz = 0.5 + 0.5 * math.sin(7.3 * NZF * w.x + ph[0]) * math.sin(6.1 * NZF * w.z + ph[1]) * math.cos(5.7 * NZF * w.y + ph[2])
        c = _ss(1.0 - cfrac, 1.0, t_)
        hit = target.ray_cast(wt + zd * 1.5, -zd, 3.0)
        if hit[0] is None:
            loc_, nrm_, _, _ = target.find_nearest(wt); h = (wt - loc_).dot(nrm_)
            hp = max(h, 0.0) * (flat + ridge * (nz - 0.5)) * 0.5; hp = hp * (1 - c) + (-UNDER) * c
            nw = loc_ + nrm_ * hp
        else:
            s_ = hit[0]; h = (wt - s_).dot(zd)
            rr = min(1.0, ((wt - Cc) - zd * (wt - Cc).dot(zd)).length / Rfoot)
            prof = (1 - rr * rr) ** 0.6
            hp = h * (flat + ridge * (nz - 0.5)) * prof if h > 0 else h
            hp = hp * (1 - c) + (-UNDER) * c
            nw = s_ + zd * hp + (wt - s_ - zd * (wt - s_).dot(zd))
        o = Wi @ nw - Wi @ w; offs.append([round(o.x, 5), round(o.z, 5), round(o.y, 5)])
        v.co = nw
    OFFSETS[label] = offs
def R_from(z_axis, y_hint):
    z = Vector(z_axis).normalized(); y = Vector(y_hint) - z * Vector(y_hint).dot(z)
    if y.length < 1e-6:
        y = Vector((0, 1, 0)) if abs(z.y) < 0.9 else Vector((1, 0, 0)); y = y - z * y.dot(z)
    y.normalize(); x = y.cross(z).normalized()
    return Matrix((x, y, z)).transposed()
def spot(bvh, centre, d, reach=1.2):
    d = Vector(d).normalized(); h = bvh.ray_cast(Vector(centre) + d * reach, -d, reach * 1.5)
    if h[0] is None: raise RuntimeError(f"no surface from {centre} along {d}")
    return h[0], h[1]
def conformed_lump(label, bone, bvh, centre, d, size, stretch, squash, spin, seed, flat=0.55, spread=0.6, lift=0.6, out_w=1.0):
    p, n = spot(bvh, centre, d)
    z = (n + Vector(d).normalized() * out_w).normalized()
    rot = (R_from(z, (0, 0, 1) if abs(z.z) < 0.9 else (0, 1, 0)) @ Matrix.Rotation(spin, 3, 'Z')).to_euler()
    bm, W = lump_bm(p + z * size * squash * lift, size, rot, (stretch[0], stretch[1], squash))
    conform_bm(label, bm, W, z, bvh, flat=flat, spread=spread, seed=seed)
    rigid.append((label, bone, bm, hive_mat, HIVE_SRC, W))
    return bm
def bm_bvh(*bms):
    tmp = bmesh.new()
    for b in bms:
        me = bpy.data.meshes.new("t"); b.to_mesh(me); tmp.from_mesh(me); bpy.data.meshes.remove(me)
    return BVHTree.FromBMesh(tmp), tmp
# the head: the EYE BULB grows forward and up out of the brow, a crest over the left antler root, a growth down the right cheek
BROW_C = HC + Vector((0, -0.02, 0.12))                                # behind the brow (v1c: lower and more forward, off the antler roots)
BULB = conformed_lump("helm_bulb", "head", HEADS, BROW_C, (0.05, 0.9, 0.4), 0.15, (1.15, 1.0), 0.9, 0.3, 11, flat=0.95, spread=0.25, lift=1.0)
CREST = conformed_lump("helm_crest_l", "head", HEADS, BROW_C, (-0.75, 0.1, 0.65), 0.08, (1.0, 1.25), 0.7, 1.9, 12, flat=0.8, spread=0.35, lift=0.8)
CHEEK = conformed_lump("helm_cheek_r", "head", HEADS, HC + Vector((0, 0, 0.05)), (0.9, 0.4, -0.05), 0.06, (0.9, 1.3), 0.6, 0.7, 13, flat=0.65, spread=0.45, lift=0.6)
# the back hunch: two big mounds, lopsided
S2, S3 = P_("spine2"), P_("spine3")
BACK0 = conformed_lump("back_hunch_0", "spine2", TORSO, S2 + Vector((0, 0.1, 0.1)), (0.2, -1.0, 0.35), 0.17, (1.1, 1.2), 0.7, 0.8, 21, flat=0.85, spread=0.35, lift=0.8)
BACK1 = conformed_lump("back_hunch_1", "spine3", TORSO, S3 + Vector((0, 0.1, 0)), (-0.45, -1.0, 0.45), 0.12, (1.0, 1.1), 0.7, 2.2, 22, flat=0.8, spread=0.35, lift=0.8)
SHT = {"L": solid_bvh({"torso", "armL"}, ANTLER), "R": solid_bvh({"torso", "armR"}, ANTLER)}   # (v1a conformed onto the antlers: slabs)
SHL = conformed_lump("shoulder_lump_L", "l_arm1", SHT["L"], P_("l_arm1") + Vector((0.05, -0.05, 0)), (-0.4, -0.3, 1.0), 0.095, (1.2, 1.0), 0.6, 0.4, 31, flat=0.65, spread=0.5, lift=0.6)
SHR = conformed_lump("shoulder_lump_R", "r_arm1", SHT["R"], P_("r_arm1") + Vector((-0.05, -0.05, 0)), (0.4, -0.2, 1.0), 0.075, (1.1, 1.0), 0.6, 2.9, 32, flat=0.65, spread=0.5, lift=0.6)

# ---------------------------------------------------------------- the eyes: MANY amber slit eyes in the bulb (the Brute's eye method)
EYE_MAT_SRC = LOAD("hiveeye")["materials"][0]
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
    nt.links.new(ti.outputs["Color"], eme.inputs[6]); eme.inputs[7].default_value = (1.0, 0.28, 0.04, 1)
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
def globe_bm(surface_pt, n, r, sink=0.35, slit=1.0, up=(0, 0, 1)):
    s = 2 * r / GL_W; n = Vector(n).normalized()
    R = R_from(n, up).to_4x4()
    M = Matrix.Translation(Vector(surface_pt) - n * (sink * GL_H * s)) @ R @ Matrix.Diagonal((s, s * slit, s * 0.9, 1)) @ Matrix.Translation(-GL_BASE)
    bm = bmesh.new(); uvl = bm.loops.layers.uv.new("UVMap")
    vv = [bm.verts.new(M @ v) for v in GLV]
    for tr in GLF:
        try: f = bm.faces.new([vv[i] for i in tr])
        except ValueError: continue
        for lp, i in zip(f.loops, tr): lp[uvl].uv = GL["uv0"][i]
    return bm, M
# the Shaman's own eyes: measured from its eye quads (diagonal 40-ish mm); the Seer's eyes run 0.7x-2.6x that
_eq = LOAD("shaman_eye0"); _ev = [H.u2b(v) for v in _eq["verts"]]
SH_EYE = max((a - b).length for a in _ev for b in _ev)
bulb_bvh, _ = bm_bvh(BULB)
bulb_c = sum((v.co for v in BULB.verts), Vector()) / len(BULB.verts)
bulb_out = Vector((0.05, 0.9, 0.4)).normalized()
EYES = [0.06, 0.036, 0.032, 0.03, 0.027, 0.025, 0.023, 0.021, 0.02, 0.019, 0.018, 0.017, 0.016, 0.015, 0.015, 0.014, 0.014, 0.013, 0.013, 0.012]
placed = []
ga = math.pi * (3 - math.sqrt(5)); k_ = 0; cand_i = 0
xa = bulb_out.cross(Vector((0, 0, 1))).normalized(); ya = bulb_out.cross(xa).normalized()
for r in EYES:
    for _try in range(80):
        if r == EYES[0]:
            d = (bulb_out + xa * 0.28 - ya * 0.12).normalized()          # the dominant one: off-centre, to the creature's left, low
        else:
            cand_i += 1
            th = math.acos(1 - (1 - math.cos(math.radians(80))) * (cand_i + 0.5) / 60.0)
            ph_ = cand_i * ga
            d = (bulb_out * math.cos(th) + (xa * math.cos(ph_) + ya * math.sin(ph_)) * math.sin(th)).normalized()
        h = bulb_bvh.ray_cast(bulb_c + d * 0.6, -d, 0.8)
        if h[0] is None: continue
        if any((h[0] - p).length < (r + rp) * 1.05 for p, rp in placed): continue
        placed.append((h[0], r))
        bm, W = globe_bm(h[0], h[1], r, sink=0.35, slit=1.0)
        rigid.append((f"helm_eye_{k_:02d}", "head", bm, eye_mat, SRC_GLOBE, W)); k_ += 1
        break
# two on the crest and one on the cheek growth: the bulb is not the only place they open
for lump_, lab, d0, r in ((CREST, "crest", Vector((-0.5, 0.6, 0.6)), 0.018), (CREST, "crest", Vector((-0.75, 0.3, 0.55)), 0.014), (CHEEK, "cheek", Vector((0.8, 0.6, -0.05)), 0.016)):
    bv, _ = bm_bvh(lump_); cc = sum((v.co for v in lump_.verts), Vector()) / len(lump_.verts)
    h = bv.ray_cast(cc + d0.normalized() * 0.5, -d0.normalized(), 0.7)
    if h[0] is None: continue
    bm, W = globe_bm(h[0], h[1], r, sink=0.35)
    rigid.append((f"helm_eye_{k_:02d}", "head", bm, eye_mat, SRC_GLOBE, W)); k_ += 1
print("EYES", k_, "dominant r", EYES[0], "shaman eye", round(SH_EYE, 3))

# ---------------------------------------------------------------- the WTF (v2): a too-wide MAW opening under the eye bulb
# (coordinator: the pale hugeskull jaw read as a white horseshoe of dentures; the Brute solved it with the creature's own tooth and
# claw pieces). The Shaman's mesh is one piece (no loose teeth or claws), so the fangs are the TROLL's own loose islands (the Brute's
# source): its finger claws (56 tris) and teeth (18 tris), dirty yellow-brown (a tint on a copy of the Troll material). A wide upper
# and lower lip (conformed TheHive lumps) wrap past the sides of the face; between them the face is painted into a dark gullet with a
# faint blight glow in its depth (repaint A + B); ragged fangs point into the slit from both lips.
TB = LOAD("troll_body"); TBV = np.array([H.u2b(v)[:] for v in TB["verts"]]); TBT = [tuple(x) for sm in TB["submeshes"] for x in sm]
_tp = list(range(len(TBV)))
def _tf(a):
    while _tp[a] != a: _tp[a] = _tp[_tp[a]]; a = _tp[a]
    return a
for tr in TBT:
    for i in tr[1:]:
        ra, rb = _tf(i), _tf(tr[0])
        if ra != rb: _tp[ra] = rb
_seen = {}
for i, v in enumerate(TBV):
    kk = tuple(np.round(v, 5))
    if kk in _seen:
        ra, rb = _tf(i), _tf(_seen[kk])
        if ra != rb: _tp[ra] = rb
    else: _seen[kk] = i
_tc = {}
for ti, tr in enumerate(TBT): _tc.setdefault(_tf(tr[0]), []).append(ti)
def canon(tris):
    """an island in the Brute's canonical frame: root (the wider end) at the origin, root->tip +z, bulge +y"""
    vi = sorted({i for k in tris for i in TBT[k]}); P = TBV[vi]; cen = P.mean(0)
    Q = P - cen; ax = np.linalg.svd(Q, full_matrices=False)[2][0]
    pr = Q @ ax; lo, hi = pr.min(), pr.max()
    def wid(m): return np.linalg.norm(Q[m] - np.outer(pr[m], ax), axis=1).mean()
    if wid(pr > hi - 0.25 * (hi - lo)) > wid(pr < lo + 0.25 * (hi - lo)): ax = -ax; pr = -pr; lo, hi = -hi, -lo
    root = cen + ax * lo
    bulge = (cen - root) - ax * ((cen - root) @ ax)
    yv = bulge / (np.linalg.norm(bulge) + 1e-9) if np.linalg.norm(bulge) > 1e-5 else np.cross(ax, [1, 0, 0])
    yv = yv - ax * (yv @ ax); yv /= np.linalg.norm(yv); xv = np.cross(yv, ax)
    Rm = np.array([xv, yv, ax])
    return {"tris": tris, "vi": vi, "V": [Vector(Rm @ (TBV[i] - root)) for i in vi], "L": float(hi - lo),
            "M_src": (Rm, root)}
FANG_SRC = {"claw": [canon(v) for v in _tc.values() if len(v) == 56 and abs(TBV[TBT[v[0]][0]][0]) > 4.5],
            "tooth": [canon(v) for v in _tc.values() if len(v) == 18]}
fang_mat = H.part_material(TB["materials"][0], PR, "TrollFang_dirtyyellow", tint=(0.62, 0.45, 0.22))
FANG_ISLANDS = {}
def fang_bm(isl, root, d, side, length):
    s = length / isl["L"]; d = Vector(d).normalized(); x = Vector(side) - d * Vector(side).dot(d); x.normalize(); y = d.cross(x)
    M = Matrix.Translation(root) @ Matrix((x, y, d)).transposed().to_4x4() @ Matrix.Scale(s, 4)
    bm = bmesh.new(); uvl = bm.loops.layers.uv.new("UVMap"); mp = {}
    for n_, i in enumerate(isl["vi"]): mp[i] = bm.verts.new(M @ isl["V"][n_])
    for k in isl["tris"]:
        tr = TBT[k]
        try: f_ = bm.faces.new([mp[i] for i in reversed(tr)])
        except ValueError: continue
        for lp, i in zip(f_.loops, reversed(tr)): lp[uvl].uv = TB["uv0"][i]
    return bm, M
# the mouth line: on the face front, under the eye bulb
MZ = 1.6
mouth, mn = spot(HEADS, Vector((0, HC.y, MZ)), (0, 1, 0))
throat = mouth                                                           # (the gullet paint, close_maw camera)
LIP_U = conformed_lump("maw_lip_U", "head", HEADS, Vector((0, HC.y, MZ + 0.075)), (0, 1, 0.3), 0.1, (2.6, 0.55), 0.7, 0.0, 41, flat=0.9, spread=0.35, lift=0.9)
LIP_L = conformed_lump("maw_lip_L", "head", HEADS, Vector((0, HC.y, MZ - 0.075)), (0, 1, -0.25), 0.09, (2.5, 0.6), 0.7, 0.0, 42, flat=0.9, spread=0.35, lift=0.9)
MAW_W = 0.0
for lip in (LIP_U, LIP_L):
    xs = [v.co.x for v in lip.verts]; MAW_W = max(MAW_W, max(xs) - min(xs))
frnd = random.Random(SEED + 9); nf = 0
for lip, down in ((LIP_U, -1), (LIP_L, 1)):
    lb, _ = bm_bvh(lip)
    for j, xx in enumerate(sorted(frnd.uniform(-0.17, 0.17) for _ in range(6 if down < 0 else 5))):
        h = (None,)
        for st_ in range(16):   # the lip's inner edge at this x: the first height (from the slit outward) where a ray from the front hits it
            zz = MZ - down * (0.004 + 0.007 * st_)
            h = lb.ray_cast(Vector((xx, mouth.y + 0.6, zz)), Vector((0, -1, 0)), 1.0)
            if h[0] is not None: break
        if h[0] is None: continue
        kind = "tooth" if j % 3 == 1 else "claw"
        isl = FANG_SRC[kind][nf % len(FANG_SRC[kind])]
        Lw = frnd.uniform(0.07, 0.11) if kind == "claw" else frnd.uniform(0.045, 0.06)
        d = Vector((frnd.uniform(-0.3, 0.3) - xx * 0.8, frnd.uniform(0.0, 0.35), down)).normalized()   # into the slit, ragged, toward the centre
        bm, W = fang_bm(isl, h[0] - d * Lw * 0.25, d, (1, 0, 0), Lw)
        rigid.append((f"maw_fang_{nf:02d}", "head", bm, fang_mat, {"prefab": "Troll", "renderer": "Visual/Body", "mesh": f"Body island ({kind}, {len(isl['tris'])} tris)", "material": "troll (tint 0.62/0.45/0.22)"}, W))
        FANG_ISLANDS[f"maw_fang_{nf:02d}"] = isl["tris"]; nf += 1
os.makedirs(os.path.join(OUT, "maw"), exist_ok=True)
json.dump({"about": "triangle indices (into the concatenated submeshes of the Troll's Body SkinnedMeshRenderer) of each fang island; the runtime "
                    "bakes them into a static mesh placed by attach.json (canonical frame: root at the origin, root->tip +z). Our data.",
           "source": "Troll / Visual/Body / Body", **FANG_ISLANDS}, open(os.path.join(OUT, "maw", "troll_fang_tris.json"), "w"))
print("MAW", "fangs", nf, "lip span", round(MAW_W, 3))

# ---------------------------------------------------------------- the root web (small)
R07 = LOAD("root07")
mat07 = H.part_material(R07["materials"][0], PR, "root07_mat", tint=(0.42, 0.32, 0.26))
def frame_of(P):
    vs = [H.u2b(v) for v in P["verts"]]
    mn = [min(v[k] for v in vs) for k in range(3)]; mx = [max(v[k] for v in vs) for k in range(3)]
    ext = [mx[k] - mn[k] for k in range(3)]; o = sorted(range(3), key=lambda k: -ext[k])
    return vs, mn, mx, ext, o
F07 = frame_of(R07)
def root(label, bone, reg, anchor, direction, L, wscale=0.8, tscale=0.9):
    vs, mn, mx, ext, o = F07; bvh = REG[reg]
    loc0, n0, _, _ = bvh.find_nearest(Vector(anchor))
    tdir = Vector(direction); tdir = (tdir - n0 * tdir.dot(n0)).normalized(); side = n0.cross(tdir).normalized()
    s = L / ext[o[0]]; cmid = (mn[o[1]] + mx[o[1]]) / 2
    out = []
    for v in vs:
        x = (v[o[0]] - mn[o[0]]) * s; y = (v[o[1]] - cmid) * s * wscale; z = (v[o[2]] - mn[o[2]]) * s * tscale
        g = loc0 + tdir * x + side * y
        sl, sn, _, _ = bvh.find_nearest(g)
        out.append(sl + sn * (0.008 + z))
    rigid.append((label, bone, H.part_bm(R07, out), mat07, {"prefab": R07["prefab"], "renderer": R07["path"], "mesh": R07["mesh"], "material": R07["materials"][0]["name"]}, Matrix.Identity(4)))
S1 = P_("spine1")
la1, la2, lh = P_("l_arm1"), P_("l_arm2"), P_("l_hand"); ra1, ra2, rh = P_("r_arm1"), P_("r_arm2"), P_("r_hand")
ll1, ll2, lf = P_("l_leg1"), P_("l_leg2"), P_("l_foot"); rl1, rl2, rf = P_("r_leg1"), P_("r_leg2"), P_("r_foot")
WEB = [  # (label, bone, region, anchor, direction, length)
    ("root_back_0", "spine2", "torso", S2 + Vector((0.18, -0.45, -0.05)), (0.3, 0, -1), 0.45),
    ("root_back_1", "spine2", "torso", S2 + Vector((-0.15, -0.45, -0.1)), (-0.35, 0, -1), 0.4),
    ("root_back_2", "spine1", "torso", S1 + Vector((0.05, -0.42, 0.25)), (0.1, 0, -1), 0.35),
    ("root_chest_0", "spine3", "torso", Vector((-0.12, 0.2, 1.6)), (-0.4, 0, -1), 0.38),
    ("root_chest_1", "spine2", "torso", Vector((0.14, 0.2, 1.45)), (0.5, 0, -1), 0.32),
    ("root_fore_L", "l_arm2", "armL", la2 + (lh - la2) * 0.15, lh - la2, 0.36),
    # (v1c: no upper-arm roots - the Shaman's upper arm is skinned l_shoulder + l_arm1 and a root across it tore 3-5x in the pose test)
    ("root_thigh_L", "l_leg1", "legL", ll1 + (ll2 - ll1) * 0.35, ll2 - ll1, 0.36),
    ("root_shin_R", "r_leg2", "legR", rl2 + (rf - rl2) * 0.3, rf - rl2, 0.32),
]
for w in WEB: root(*w)

# ---------------------------------------------------------------- branches: the Elder's thick bent limbs, dark weathered wood
BRANCH_TINT = (0.3, 0.27, 0.24)   # coordinator after the Husk: "dark weathered bark-grey-brown", not pinkish-tan
EL = LOAD("elder"); EL_V = [H.u2b(v) for v in EL["verts"]]; EL_T = [tuple(tr) for sm in EL["submeshes"] for tr in sm]
_par = list(range(len(EL_V)))
def _fe(a_):
    while _par[a_] != a_: _par[a_] = _par[_par[a_]]; a_ = _par[a_]
    return a_
for tr in EL_T:
    for i in tr[1:]: _par[_fe(i)] = _fe(tr[0])
_ec = {}
for kk, tr in enumerate(EL_T): _ec.setdefault(_fe(tr[0]), []).append(kk)
EL_COMPS = list(_ec.values())
def elder_piece(center):
    best = None
    for ks in EL_COMPS:
        vs_ = {i for k in ks for i in EL_T[k]}; c = sum((EL_V[i] for i in vs_), Vector()) / len(vs_)
        d_ = (c - Vector(center)).length
        if best is None or d_ < best[0]: best = (d_, ks)
    return best[1]
br_mat = H.part_material(EL["materials"][0], PR, "Elder_branch", tint=BRANCH_TINT)
br_mat.node_tree.nodes["Principled BSDF"].inputs["Emission Strength"].default_value = 0.0
BR_SRC = {"tint_linear": BRANCH_TINT, "prefab": "gd_king", "renderer": "Visual/gd_king (SkinnedMeshRenderer, baked static)", "mesh": "gd_king.001, kept triangles (branches/elder_branch_tris.json)", "material": "Elder_mat"}
BRANCH_TRIS = {}
def branch(label, bone, piece_center, crust_bm, direction, length, spin, sink=0.04, thick=1.6, tris=None):
    ks = list(tris) if tris is not None else elder_piece(piece_center); BRANCH_TRIS[label] = ks
    vs_ = sorted({i for k in ks for i in EL_T[k]}); P = [EL_V[i] for i in vs_]
    zlo = min(p.z for p in P); ext = max(p.z for p in P) - zlo
    basep = [p for p in P if p.z < zlo + 0.04 * ext]; b0 = sum(basep, Vector()) / len(basep)
    tipc = sum(P, Vector()) / len(P); ax = (tipc - b0).normalized()
    Lsrc = max((p - b0).length for p in P)
    d_ = Vector(direction).normalized()
    cb, cbm = bm_bvh(crust_bm)
    cc = sum((v.co for v in cbm.verts), Vector()) / len(cbm.verts)
    hit = cb.ray_cast(cc + d_ * 0.6, -d_, 0.8)
    root_pt = (hit[0] if hit[0] is not None else cc) - d_ * sink
    s = length / Lsrc
    R = Matrix.Rotation(spin, 4, d_) @ ax.rotation_difference(d_).to_matrix().to_4x4()
    A = Matrix(((ax.x * ax.x, ax.x * ax.y, ax.x * ax.z), (ax.y * ax.x, ax.y * ax.y, ax.y * ax.z), (ax.z * ax.x, ax.z * ax.y, ax.z * ax.z)))
    Sa = (Matrix.Identity(3) * (s * thick) + A * (s * (1 - thick))).to_4x4()
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
# thick bent limbs with short forks only (c27 the twisted limb, c109 / c110 the bent spurs; survey: _ref/parts/elder_components.json)
# v2 (coordinator: the looping limb read as a handle or pipe): Elder island 4 (kit_tools/branch_parts_sheet.png cell 5), a limb that
# rises straight up and back and ends in a short fork - no closed loop from any view
_BI = json.load(open(os.path.join(HERE, "..", "..", "kit_tools", "branch_parts_index.json")))
branch("branch_back_limb", "spine2", None, BACK0, (0.3, -0.65, 0.9), 0.95, 0.9, tris=_BI[4]["tris"], thick=1.9)
branch("branch_back_spur", "spine3", (2.236, 0.983, 19.781), BACK1, (-0.55, -0.6, 0.7), 0.55, 2.6)
os.makedirs(os.path.join(OUT, "branches"), exist_ok=True)
json.dump({"about": "triangle indices (into the concatenated submeshes of gd_king.001) kept per branch; the runtime bakes them into a static mesh "
                    "placed by attach.json. Our data.", "source": "gd_king / Visual/gd_king / gd_king.001", **BRANCH_TRIS},
          open(os.path.join(OUT, "branches", "elder_branch_tris.json"), "w"))

for lab, bone, bm, m, src, W in rigid:
    ob = H.bm_object(bm, "Seer_" + lab, m if isinstance(m, list) else [m], smooth=(m is not hive_mat))
    PIECES[lab] = {"ob": ob, "mode": "rigid", "bone": bone, "source": src, "W": W}

# ---------------------------------------------------------------- fit, attach.json
CARDB = None
def measure(ob, name):
    vs = [v.co.copy() for v in ob.data.vertices]; fs = [list(p.vertices) for p in ob.data.polygons]
    mine = BVHTree.FromPolygons(vs, fs)
    ds = []
    for p in vs:
        loc, n, idx, d = SOLID.find_nearest(p)
        if loc is not None: ds.append(d if (p - loc).dot(n) >= 0 else -d)
    others = [o["ob"] for k, o in PIECES.items() if k != name]
    ov, of, oo = [], [], 0
    for o in others:
        ov += [v.co.copy() for v in o.data.vertices]; of += [[oo + i for i in p.vertices] for p in o.data.polygons]; oo += len(o.data.vertices)
    ob_ = BVHTree.FromPolygons(ov, of)
    touch = any((ob_.find_nearest(p)[3] or 1) < 0.008 for p in vs[::3])
    near = min(abs(x) for x in ds)
    return {"base_pairs": len(mine.overlap(SOLID)), "verts_inside_base": sum(1 for x in ds if x < -0.001), "nearest_to_base_mm": round(near * 1000, 1),
            "touches_other_piece": bool(touch), "floating": bool(near > 0.012 and not touch)}
attach = {"_about": ("ASSET-004 Eyeblight Seer kitbash v1: vanilla parts on the vanilla Greydwarf_Shaman. Rigid parts: the vanilla mesh under a "
                     "child of the named bone with the given local transform (Unity, bind pose); conformed lumps add deform/lump_offsets.json; "
                     "laid roots are their vanilla mesh with per-vertex positions (identity transform). The pose test (pose_test.py) marks the "
                     "pieces it skins with transferred weights."),
          "base": {"prefab": "Greydwarf_Shaman", "renderer": "Visual/Cube + Visual/Cube.001", "hidden": ["Visual/Plane", "Visual/Plane.001 (eye quads)"],
                   "mesh": J["mesh"], "material": J["material"]["name"], "tris": len(J["tris"])}}
total = 0
for name, pc in PIECES.items():
    ob = pc["ob"]; tri = sum(len(p.vertices) - 2 for p in ob.data.polygons); total += tri
    e = {"source": pc["source"], "mode": pc["mode"], "tris": tri, "fit": measure(ob, name)}
    Wu = S_ @ pc["W"] @ S_
    Bu = Matrix(J["bone_bind_world"][J["bone_names"].index(pc["bone"])])
    L = Bu.inverted() @ Wu
    loc, q, sc = L.decompose()
    e.update({"parent": pc["bone"], "localPosition": [round(x, 6) for x in loc], "localRotation": [round(q.x, 6), round(q.y, 6), round(q.z, 6), round(q.w, 6)],
              "localScale": [round(x, 6) for x in sc]})
    if name in OFFSETS: e["vertex_offsets"] = "deform/lump_offsets.json#" + name
    attach[name] = e
os.makedirs(os.path.join(OUT, "deform"), exist_ok=True)
json.dump({"about": "per-vertex offsets (Unity metres, the vanilla mesh's own space; index = vanilla vertex index) added to a clone of TheHive `low` "
                    "for each conformed lump (the Hive Brute's lump deformation). Our data.", "source": "TheHive / Visual/low / default", **OFFSETS},
          open(os.path.join(OUT, "deform", "lump_offsets.json"), "w"))
json.dump(attach, open(os.path.join(OUT, "attach.json"), "w"), indent=1)
ST = {"base_tris": len(J["tris"]), "addon_tris": total, "total_tris": len(J["tris"]) + total, "budget": 12000,
      "pieces": {k: {"tris": v["tris"], "parent": v.get("parent"), **v["fit"]} for k, v in attach.items() if not k.startswith("_") and k != "base"}}
json.dump(ST, open(os.path.join(PV, "stats.json"), "w"), indent=1)
print("KITBASH", json.dumps({k: ST[k] for k in ("base_tris", "addon_tris", "total_tris")}))

# ---------------------------------------------------------------- EARLY REPAINT of the Shaman's own texture (the Brute's method)
RP = os.path.join(OUT, "repaint"); os.makedirs(RP, exist_ok=True)
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
head_tris = [tr for tr in TRI if sum(1 for i in tr if RV[i] == "head") >= 2]
def _cov(tris_, size):
    pp, _ = TR.raster_position_map(VSt, tris_, UV0, size); return ~np.isnan(pp[..., 0])
def _down(a):
    return a.reshape(SZO, SZ // SZO, SZO, SZ // SZO, *a.shape[2:]).mean((1, 3))
pos1, nrm1 = TR.raster_position_map(VSt, TRI, UV0, SZO)
valid1 = ~np.isnan(pos1[..., 0]); P1 = pos1[valid1]
head1 = _cov(head_tris, SZO)[valid1]
src_names = [k for k in PIECES if k.startswith(("helm_", "shoulder_lump", "back_hunch")) and not k.startswith("helm_eye")]
src_names += [k for k in PIECES if k.startswith("root_") and attach[k]["parent"] in ("spine1", "spine2", "spine3", "l_arm1", "r_arm1")]
def _bvh_of(keys):
    sv, sf, so = [], [], 0
    for k in keys:
        o = PIECES[k]["ob"]; sv += [v.co.copy() for v in o.data.vertices]; sf += [[so + i for i in p_.vertices] for p_ in o.data.polygons]; so += len(o.data.vertices)
    return BVHTree.FromPolygons(sv, sf)
SRCB = _bvh_of(src_names)
dist = np.array([SRCB.find_nearest(Vector(q))[3] or 9.0 for q in P1])
nz = TR.value_noise3(P1, 0.5 / SC, 11) * 0.35 / SC + TR.value_noise3(P1, 0.16 / SC, 12) * 0.15 / SC + TR.value_noise3(P1, 0.05 / SC, 13) * 0.05 / SC
bark_v = 1 - TR.smoothstep(0.0, 0.75 / SC, dist + nz)
antler1 = _cov([J["tris"][i] for i in sorted(ANTLER)], SZO)[valid1]
bark_v = np.where(antler1, 0.0, bark_v)                               # its own antlers keep their bone-pale wood
orig1 = _img(os.path.join(REF, J["material"]["textures"]["_MainTex"]["png"]), SZO)
lum1 = orig1[..., :3] @ np.array([0.3, 0.59, 0.11]); lum_n1 = lum1 / max(1e-6, lum1[valid1].mean())
ext_v = np.maximum(TR.smoothstep(abs(la2.x) + 0.05, abs(lh.x) + 0.1, np.abs(P1[:, 0])) * (P1[:, 2] > ll2.z + 0.3),
                   TR.smoothstep(ll2.z, lf.z + 0.05, P1[:, 2]))
pos2, _ = TR.raster_position_map(VSt, TRI, UV0, SZ)
valid2 = ~np.isnan(pos2[..., 0]); P2 = pos2[valid2]
noline2 = _cov(head_tris, SZ)[valid2]
def nearest(pt):
    loc, n, _, _ = SOLID.find_nearest(Vector(tuple(pt)))
    return (np.array(loc[:]), np.array(n[:])) if loc is not None else (None, None)
def centre_of(k): o = PIECES[k]["ob"]; return np.array((sum((v.co for v in o.data.vertices), Vector()) / len(o.data.vertices))[:])
eye_locs = [centre_of(k) for k in PIECES if k.startswith("helm_eye")]
_r = np.random.default_rng(5)
vein_starts = [(centre_of(k), 0.009 / SC * 0.85, (_r.uniform(-1, 1), _r.uniform(-1, 1), -1)) for k in PIECES if k.startswith(("shoulder_lump", "back_hunch", "maw_lip")) for _ in range(3)]
veins = TR.smooth_curves(TR.walk_curves(nearest, vein_starts, 2, 0.75 / SC, 0.03 / SC, 21, branch=3.0 * SC, persist=0.35, jitter=0.45), nearest, 2)
root_starts = [(centre_of(k), 0.03 / SC, (0.0, 0.0, -1.0)) for k in PIECES if k.startswith(("shoulder_lump", "back_hunch", "maw_lip"))]
roots_c = TR.walk_curves(nearest, root_starts, 3, 1.8 / SC, 0.05 / SC, 31, bias=(0, 0, -1), branch=0.8 * SC)
vein2 = TR.curves_mask(pos2, veins, fade=1.2)
halo2 = TR.curves_mask(pos2, [(pts, w0 * 3.5) for pts, w0 in veins], fade=1.6)
root2 = TR.curves_mask(pos2, roots_c)
de = np.min(np.stack([np.linalg.norm(P2 - e, axis=1) for e in eye_locs]), 0)
keep = TR.smoothstep(0.25, 0.5, de)
for a_ in (vein2, halo2, root2):
    vv_ = a_[valid2]; vv_ = np.where(noline2, 0.0, vv_)
    if a_ is not root2: vv_ = vv_ * keep
    a_[valid2] = vv_
# the gullet (v2): the face skin in the slit between the lips, dark, across the maw's width, ragged; a faint glow in its depth
_slit = TR.smoothstep(0.05, 0.02, np.abs(P1[:, 2] - MZ) + 0.012 * TR.value_noise3(P1, 0.03, 7)) * TR.smoothstep(0.24, 0.18, np.abs(P1[:, 0])) * (P1[:, 1] > HC.y)
gul = _slit
gcore = TR.smoothstep(0.018, 0.004, np.abs(P1[:, 2] - MZ)) * TR.smoothstep(0.14, 0.06, np.abs(P1[:, 0])) * (P1[:, 1] > HC.y)
mask2 = np.zeros((SZ, SZ, 2)); mask2[..., 0] = np.maximum(vein2, 0.12 * halo2); mask2[..., 1] = root2 * 0.92
mask_l = _down(mask2)
mask = np.zeros((SZO, SZO, 4))
mask[..., 0][valid1] = bark_v; mask[..., 1][valid1] = ext_v
mask[..., 2] = mask_l[..., 0]; mask[..., 3] = mask_l[..., 1]
_g = np.zeros((SZO, SZO)); _g[valid1] = gul; mask[..., 3] = np.maximum(mask[..., 3], _g)
_gc = np.zeros((SZO, SZO)); _gc[valid1] = gcore; mask[..., 2] = np.maximum(mask[..., 2], 0.1 * _gc)   # faint (0.35 read as a lime stripe)   # the faint glow rides the emission mask
mask = TR.dilate_fill(mask, valid1, 8)
_save(os.path.join(RP, "seer_hive_mask.png"), mask)
REC = {"about": "ASSET-004 early repaint recipe: the Hive Brute's method (kit_tools/troll_repaint.py) scaled to the Shaman (distances / 1.75). "
                "Mask = repaint/seer_hive_mask.png in the Shaman Cube's UV0 (R bark, G extremity darkening, B blight veins = emission, A dark roots + "
                "the gullet behind the jaw), lines computed at 2048 and box-filtered to 1024. The vanilla texture is only 128 px: the runtime "
                "upsamples it to the mask's 1024 before recolouring (a new Texture2D; vanilla pixels are read back, never shipped).",
       "sick_skin": [0.5, 0.53, 0.4], "sick_mix": 0.45, "extremity_darken": 0.4, "bark_tint": [0.85, 0.64, 0.42], "infection_margin_darken": 0.45,
       "bark_texture": "olivetree_trunk01 (TheHive_Mat _MainTex), triplanar in rest-pose metres, tile 0.69 m",
       "root_colour": [0.03, 0.025, 0.02], "vein_albedo": [0.05, 0.06, 0.02], "blight_colour": [0.42, 0.55, 0.12], "emission_strength_preview": 0.85,
       "veins": "off the head; faded out within 0.25-0.5 m of the Hive eyes", "antlers": "its own antlers weathered toward grey-brown bark: 0.45 x vanilla + 0.55 x luminance x [0.62, 0.55, 0.46] (they sat bone-pale next to the dark branches)", "mask_size": "1024 (lines at 2048, box-filtered)",
       "hidden_renderers": ["Plane", "Plane.001"]}
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
ANTLER_WEATHER = [0.62, 0.55, 0.46]
sick = np.where(antler1[:, None], O1 * 0.45 + ln * np.array(ANTLER_WEATHER) * 0.55 * float(O1.mean()), sick)
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
rmat = H.base_material(Jr, REF, "Shaman_repaint")
nt = rmat.node_tree; bsdf = nt.nodes["Principled BSDF"]
vt = nt.nodes.new("ShaderNodeTexImage"); vt.image = bpy.data.images.load(os.path.join(RP, "preview_blight_emission.png")); vt.image.colorspace_settings.name = 'Non-Color'
nt.links.new(vt.outputs["Color"], bsdf.inputs["Emission Color"]); bsdf.inputs["Emission Strength"].default_value = 1.0
ORIG_MAT = base.data.materials[0]; base.data.materials[0] = rmat
REPAINT = {"bark_over_half_pct": round(float((bark_v > 0.5).mean() * 100), 1), "covered_texels": int(valid1.sum()),
           "vein_texels": int((mask[..., 2] > 0.3).sum()), "vein_paths": len(veins), "root_curves": len(roots_c), "extremity_texels": int((ext_v > 0.3).sum())}
print("REPAINT", REPAINT)

# ---------------------------------------------------------------- previews
H.setup_eevee(900, 1000); H.lights_and_world(aim=(0, 0, 1.5))
tgt = Vector((0, 0, 1.45))
def shots(prefix, views):
    for nm, az, el in views:
        H.camera(tgt, 6.2, FA + az, el, lens=55); H.render(os.path.join(PV, f"{prefix}_{nm}.png"))
KV = (("front", 0, 6), ("side", 90, 6), ("back", 180, 6), ("34", 35, 12), ("34back", 145, 12))
shots("kit", KV)
for pc in PIECES.values(): pc["ob"].hide_render = True
base.data.materials[0] = ORIG_MAT; shots("base", (("front", 0, 6), ("34", 35, 12)))
base.data.materials[0] = rmat; shots("base_repaint", (("34", 35, 12),))
for pc in PIECES.values(): pc["ob"].hide_render = False
sc = bpy.context.scene; sc.render.resolution_x = sc.render.resolution_y = 900
H.camera(bulb_c, 1.5, FA + 25, 10, lens=55); H.render(os.path.join(PV, "close_head.png"))
H.camera(bulb_c, 1.5, FA - 70, 10, lens=55); H.render(os.path.join(PV, "close_head_side.png"))
dom_eye = PIECES["helm_eye_00"]["ob"]; de_c = sum((v.co for v in dom_eye.data.vertices), Vector()) / len(dom_eye.data.vertices)
H.camera(de_c, 0.42, FA + 15, 5, lens=55); H.render(os.path.join(PV, "close_eye_1to1.png"))
H.camera(mouth, 1.1, FA + 25, 0, lens=55); H.render(os.path.join(PV, "close_maw.png"))
H.camera(S2 + Vector((0, -0.3, 0.4)), 2.6, FA + 150, 15, lens=55); H.render(os.path.join(PV, "close_branches.png"))
# lineup: a 1.8 m figure, the base, base + parts
bpy.ops.mesh.primitive_cube_add(size=1); fig = bpy.context.active_object; fig.name = "Figure"; fig.scale = (0.45, 0.25, 1.8); fig.location = (-5.2, 0, 0.9)
fm = bpy.data.materials.new("fig"); fm.use_nodes = True; fm.node_tree.nodes["Principled BSDF"].inputs["Base Color"].default_value = (0.4, 0.6, 1, 1); fig.data.materials.append(fm)
bcopy = base.copy(); bcopy.data = base.data.copy(); bcopy.data.materials[0] = ORIG_MAT; bcopy.location.x = -2.3; sc.collection.objects.link(bcopy)
for pc in PIECES.values(): pc["ob"].location.x = 2.3
base.location.x = 2.3
sc.render.resolution_x, sc.render.resolution_y = 1600, 900
H.camera(Vector((-1.2, 0, 1.4)), 14.0, FA, 4, lens=55); H.render(os.path.join(PV, "lineup.png"))
bpy.data.objects.remove(fig, do_unlink=True); bpy.data.objects.remove(bcopy, do_unlink=True)
for pc in PIECES.values(): pc["ob"].location.x = 0
base.location.x = 0
bpy.ops.wm.save_as_mainfile(filepath=os.path.join(OUT, "EyeblightSeer_kitbash.blend"))

# ---------------------------------------------------------------- README (measured numbers only)
att = attach
def grp(pref): return [k for k in att if k.startswith(pref)]
eyes = grp("helm_eye")
L = ["# ASSET-004 Eyeblight Seer: kitbash v1 (vanilla parts on the vanilla Greydwarf_Shaman), step 1", "",
     "Built by `../make_seer_kitbash.py` (deterministic, seed 4404). Base exported by `../../../kit_tools_b/export_base.py` (Cube; Cube.001",
     "merged in: same material and skeleton), parts by `export_part.py`, into `../_ref/` (game data, dev reference, never shipped). Every",
     "number below was measured by that run. The Shaman faces +Y in Blender; `front` renders look at its face.", "",
     "## Triangles (measured)", "",
     f"- Base (Greydwarf_Shaman `Cube` + `Cube.001`): **{ST['base_tris']}** (its two eye quads `Plane` / `Plane.001` are hidden)",
     f"- Vanilla parts on it: **{ST['addon_tris']}**",
     f"- Total: **{ST['total_tris']}** of 12000 ({'PASS' if ST['total_tris'] <= 12000 else 'FAIL'})", "",
     "## What is on it", "",
     f"- **The eyes (identity):** {len(eyes)} Hive eyes (`eye_globe` + TheHive_Eye + our core / slit-pupil mask, the Brute's method): {len(eyes) - 3} in the EYE BULB growing forward out of the brow (one dominant, radius 60 mm; the rest 12-36 mm; the Shaman's own eye quad is {round(SH_EYE * 1000)} mm across), 2 on the left crest, 1 on the right cheek growth. Its own green eye quads are hidden: the eyes are the Hive's now.",
     f"- **The WTF (v2):** a too-wide MAW under the eye bulb: a wide upper and lower lip (conformed TheHive lumps, {round(MAW_W, 2)} m across against the 0.32 m face) wrapping past the sides of the face; between them the face is painted into a dark gullet with a faint blight glow in its depth (repaint A + B); {len(grp('maw_fang'))} ragged fangs point into the slit from both lips: the TROLL's own finger claws and teeth (its loose Body islands, the Brute's source; the Shaman's mesh has none), dirty yellow-brown ({sum(att[k]['tris'] for k in grp('maw_fang'))} tris; triangle lists `../maw/troll_fang_tris.json`). The v1 `hugeskull/jaw` is gone (it read as a pale horseshoe of dentures).",
     f"- **Crust:** {len(OFFSETS)} TheHive `low` lumps CONFORMED with the Hive Brute's lump deformation (per-vertex offsets, `../deform/lump_offsets.json`): the eye bulb, a crest over the left antler root and a growth down the right cheek (head); two mounds on the back hunch (spine2 / spine3); one per shoulder; the two maw lips (head).",
     f"- **Branches:** {len(grp('branch_'))} of the Elder's (gd_king.001) thick bent limbs with short forks ({sum(att[k]['tris'] for k in grp('branch_'))} tris; kept-triangle lists `../branches/elder_branch_tris.json`): a limb out of the big back mound that rises up and back and ends in a short fork (Elder island 4, `kit_tools/branch_parts_sheet.png` cell 5; v1's looping limb read as a handle), a spur out of the upper one; base sunk 4 cm, 1.6x thicker across, dark weathered grey-brown (tint {BRANCH_TINT}). No leaves. The Shaman's own antlers stay, weathered toward grey-brown in the repaint so they sit with the dark branches.",
     f"- **Root web:** {len(grp('root_'))} catacomb `fi_vil_combs_root07` laid onto back, chest, arms and legs, darkened.",
     f"- **Repaint** (the Brute's method; `../repaint/seer_hive_mask.png` + `repaint.json`): bark from the crust over the hunch, shoulders and chest ({REPAINT['bark_over_half_pct']} % of the used texels over half), sickly darkening of hands and feet, {REPAINT['vein_paths']} thin dark veins (off the head, faded within 0.5 m of the eyes), {REPAINT['root_curves']} painted roots, the gullet. The vanilla texture is 128 px: the runtime upsamples it to 1024 before recolouring. `base_repaint_34.png` shows the base alone repainted; `base_front.png` / `base_34.png` the untouched Shaman.", "",
     "## Parts, sources and attach (attach.json has the full transforms)", "",
     "| part | source | rides | mode | tris | base pairs | nearest (mm) | floating |", "|---|---|---|---|---|---|---|---|"]
for k, v in att.items():
    if k.startswith("_") or k == "base": continue
    s = v["source"]; f = v["fit"]
    L.append(f"| {k} | {s['prefab']} / {s['renderer']} | {v['parent']} | {v['mode']} | {v['tris']} | {f['base_pairs']} | {f['nearest_to_base_mm']} | {f['floating']} |")
L += ["", "## New geometry", "", "None. Every triangle is vanilla (TheHive `low`, `eye_globe`, the Troll's own claw and tooth islands, `fi_vil_combs_root07`, gd_king's own branch pieces).",
      "The lumps are conformed (per-vertex offsets), the roots laid onto the body (per-vertex positions), the branches scaled non-uniformly; all our data.", "",
      "## Previews", "",
      "- `kit_front/side/back/34/34back.png`: base + parts; `base_front.png`, `base_34.png`: the untouched Shaman; `base_repaint_34.png`: the base alone repainted",
      "- `close_head.png`, `close_head_side.png` (the eye bulb), `close_eye_1to1.png` (the dominant eye), `close_maw.png` (the WTF), `close_branches.png`",
      "- `lineup.png`: 1.8 m figure, the untouched Shaman, the Seer", ""]
open(os.path.join(PV, "README.md"), "w").write("\n".join(L) + "\n")
print("SEER done")
