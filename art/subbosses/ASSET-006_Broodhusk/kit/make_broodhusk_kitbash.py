"""ASSET-006 Broodhusk, kitbash v1 (the Runic method, as the Hive Brute, the Barkbound Husk and the Eyeblight Seer): VANILLA parts in
their real materials on the real vanilla Seeker. Approved direction (owner): "yes, with branches".

Base: Seeker `Visual/Plane.004` (5,353 tris, one SkinnedMeshRenderer; its wings are part of it and stay its own).
Add-ons (exported from the 1.0.21 bundle into _ref/parts/; game data, never shipped):
- CRUST: TheHive `low` lumps CONFORMED with the Brute's deformation on the rear segments (thorax2 / thorax3) and the dorsal ridge,
  their rims thinned all the way round (no shelves, no shingles).
- BROOD (its WTF): brood cells set into the rear crust - `eye_globe` domes with a glowing brood material (our emission mask), some
  of them holding the amber slit eyes (the Brute's eye_globe + core / slit-pupil mask); a glow halo painted on the skin round them.
- BRANCHES: the Elder's thick dead-wood limbs with short forks (kit_tools/branch_parts_index.json) out of the dorsal ridge.
- Mouth parts: its OWN mandibles / pincers, repainted dirty yellow-brown (no added bone).
- Wings: its own, repainted toward torn bark-skin (darkened, bark-grained, ragged holes in the membrane's alpha), never leafy.
- Repaint of its own _MainTex (the Brute's troll_repaint method): bark spreading from the crust.
The Seeker FACES +Y (Blender), like the Shaman; cameras are offset by 180 deg.
Run: heavy.sh 4G sb-brood blender -b --factory-startup -P make_broodhusk_kitbash.py -- <abs kit dir>
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
SEED = 6606; rnd = random.Random(SEED)
FA = 180.0
bpy.ops.wm.read_factory_settings(use_empty=True)
base, J, dom = H.load_base(REF, "Seeker_base")
def region(b):
    if b in ("head", "neck") or any(k in b for k in ("topant", "botant", "pincer", "tooth")): return "head"
    if b.startswith("l.wing"): return "wingL"
    if b.startswith("r.wing"): return "wingR"
    if b.startswith(("l.frontarm", "l.backleg")): return "legL"
    if b.startswith(("r.frontarm", "r.backleg")): return "legR"
    if b in ("thorax2", "thorax3"): return "rear"
    return "torso"
VS = [v.co.copy() for v in base.data.vertices]
RV = [region(d) for d in dom]
BONES = H.bone_frames(J)
def P_(n): return BONES[n].translation.copy() if n in BONES else H.node_pos(J, n)
CARDS = H.card_tris(base, J, REF)              # the wing membranes' cut-out parts and the antennae
def solid_bvh(regions, exclude=()):
    fs = []
    for p in base.data.polygons:
        if p.index in exclude or p.index in CARDS: continue
        rs = [RV[i] for i in p.vertices]
        if max(set(rs), key=rs.count) in regions: fs.append(list(p.vertices))
    return BVHTree.FromPolygons(VS, fs)
ALLR = {"torso", "rear", "head", "wingL", "wingR", "legL", "legR"}
SOLID = solid_bvh(ALLR)
BODY = solid_bvh({"torso", "rear"})
REARB = solid_bvh({"rear"})
REG = {r: solid_bvh({r}) for r in ALLR}
LOAD = lambda k: json.load(open(os.path.join(PR, k + ".json")))
S_ = Matrix(((1, 0, 0, 0), (0, 0, 1, 0), (0, 1, 0, 0), (0, 0, 0, 1)))
PIECES = {}; rigid = []; OFFSETS = {}
from mathutils.kdtree import KDTree
_skd = KDTree(len(VS))
for i, v in enumerate(VS): _skd.insert(v, i)
_skd.balance()
def skin_bone(points):
    """rigid-first, the right bone (pose test v1: rear lumps and brood cells picked by distance to a bone head cut 50-160 mm into the
    next segment when the abdomen curled): the bone that dominates the skin UNDER the piece"""
    cnt = {}
    for p in points:
        for _, i, _ in _skd.find_n(Vector(p), 3): cnt[dom[i]] = cnt.get(dom[i], 0) + 1
    return max(cnt, key=cnt.get)
_bv = [VS[i] for i in range(len(VS)) if RV[i] in ("torso", "rear")]
BC = sum(_bv, Vector()) / len(_bv)
print("BODY centre", [round(x, 3) for x in BC], "cards", len(CARDS))

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
SC = 5.0 / 2.0           # Troll height / Seeker body length (the Brute's distances scale by it)
UNDER = 0.02 / SC
NZF = SC
def _ss(e0, e1, x):
    t_ = min(1.0, max(0.0, (x - e0) / (e1 - e0))); return t_ * t_ * (3 - 2 * t_)
def conform_bm(label, bm, W, zdir, target, flat=0.55, cfrac=0.55, ridge=0.3, spread=0.6, seed=0, edge=0.6):
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
            prof = (1 - rr * rr) ** edge                                 # edge > 0.6 thins the rim (no shelves)
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
def conformed_lump(label, bone, bvh, centre, d, size, stretch, squash, spin, seed, flat=0.55, spread=0.6, lift=0.6, out_w=1.0, edge=1.4):
    p, n = spot(bvh, centre, d)
    z = (n + Vector(d).normalized() * out_w).normalized()
    rot = (R_from(z, (0, 0, 1) if abs(z.z) < 0.9 else (0, 1, 0)) @ Matrix.Rotation(spin, 3, 'Z')).to_euler()
    bm, W = lump_bm(p + z * size * squash * lift, size, rot, (stretch[0], stretch[1], squash))
    conform_bm(label, bm, W, z, bvh, flat=flat, spread=spread, seed=seed, edge=edge)
    rigid.append((label, bone, bm, hive_mat, HIVE_SRC, W))
    return bm
def bm_bvh(*bms):
    tmp = bmesh.new()
    for b in bms:
        me = bpy.data.meshes.new("t"); b.to_mesh(me); tmp.from_mesh(me); bpy.data.meshes.remove(me)
    return BVHTree.FromBMesh(tmp), tmp
# the crust: three mounds over the rear segments (lopsided), two along the dorsal ridge; rims thinned (edge 1.4) so they grow out of
# the carapace with no shelf
T2, T3, T1, AB = P_("thorax2"), P_("thorax3"), P_("thorax1"), P_("abdomen")
REAR0 = conformed_lump("rear_lump_0", "thorax2", BODY, T2 + Vector((0, -0.1, 0.05)), (0.15, -0.3, 1.0), 0.2, (1.0, 1.35), 0.6, 0.3, 11, flat=0.8, spread=0.4, lift=0.7)
REAR1 = conformed_lump("rear_lump_1", "thorax3", REARB, T3 + Vector((0, -0.15, 0.0)), (-0.4, -0.6, 0.7), 0.15, (1.0, 1.2), 0.6, 1.7, 12, flat=0.8, spread=0.4, lift=0.7)
REAR2 = conformed_lump("rear_lump_2", "thorax2", BODY, T2 + Vector((0, -0.2, 0.0)), (0.85, -0.3, 0.4), 0.13, (1.0, 1.2), 0.6, 2.6, 13, flat=0.75, spread=0.45, lift=0.7)
RIDGE0 = conformed_lump("ridge_lump_0", "thorax1", BODY, T1 + Vector((0, -0.25, 0.05)), (0.05, 0.0, 1.0), 0.15, (0.9, 1.5), 0.55, 0.0, 21, flat=0.75, spread=0.4, lift=0.6)
RIDGE1 = conformed_lump("ridge_lump_1", "abdomen", BODY, AB + Vector((0, 0.25, 0.1)), (-0.1, 0.1, 1.0), 0.12, (0.9, 1.4), 0.55, 0.2, 22, flat=0.75, spread=0.4, lift=0.6)

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
_seer_mask_ok = True
for _n, (lab_, bone_, bm_, m_, src_, W_) in enumerate(list(rigid)):
    if lab_.startswith(("rear_lump", "ridge_lump")):
        rigid[_n] = (lab_, skin_bone([v.co for v in bm_.verts][::3]), bm_, m_, src_, W_)
print("LUMP BONES", {r[0]: r[1] for r in rigid})
# ---------------------------------------------------------------- BROOD (the WTF): glowing cells in the rear crust, some holding eyes
def brood_material():
    """a brood cell: the eye_globe dome, a thin dark-amber membrane over a glowing core (our mask: eye/brood_cell_glow_mask.png = the
    eye mask's R core with no pupil), blight-yellow emission, a wet clear coat"""
    m = bpy.data.materials.new("V_Brood_cell"); m.use_nodes = True
    nt = m.node_tree; b_ = nt.nodes["Principled BSDF"]
    ti = nt.nodes.new("ShaderNodeTexImage"); ti.image = bpy.data.images.load(os.path.join(PR, EYE_MAT_SRC["textures"]["_MainTex"]["png"]))
    mul = nt.nodes.new("ShaderNodeMix"); mul.data_type = 'RGBA'; mul.blend_type = 'MULTIPLY'; mul.inputs[0].default_value = 1.0
    nt.links.new(ti.outputs["Color"], mul.inputs[6]); mul.inputs[7].default_value = (0.16, 0.11, 0.04, 1)
    nt.links.new(mul.outputs[2], b_.inputs["Base Color"])
    mk = nt.nodes.new("ShaderNodeTexImage"); mk.image = bpy.data.images.load(os.path.join(OUT, "eye", "eye_globe_core_pupil_mask.png")); mk.image.colorspace_settings.name = 'Non-Color'
    sep = nt.nodes.new("ShaderNodeSeparateColor"); nt.links.new(mk.outputs["Color"], sep.inputs[0])
    gl = nt.nodes.new("ShaderNodeMath"); gl.operation = 'ADD'; nt.links.new(sep.outputs[0], gl.inputs[0]); nt.links.new(sep.outputs[1], gl.inputs[1])   # core + (no) pupil
    pw = nt.nodes.new("ShaderNodeMath"); pw.operation = 'POWER'; pw.inputs[1].default_value = 0.45; nt.links.new(gl.outputs[0], pw.inputs[0])       # a wide soft glow
    st = nt.nodes.new("ShaderNodeMath"); st.operation = 'MULTIPLY'; st.inputs[1].default_value = BROOD_GLOW; nt.links.new(pw.outputs[0], st.inputs[0])
    nt.links.new(st.outputs[0], b_.inputs["Emission Strength"]); b_.inputs["Emission Color"].default_value = (*BROOD_COL, 1)
    b_.inputs["Coat Weight"].default_value = 0.7; b_.inputs["Coat Roughness"].default_value = 0.05; b_.inputs["Roughness"].default_value = 0.2
    return m
BROOD_COL = (0.75, 0.62, 0.08); BROOD_GLOW = 6.0
brood_mat = brood_material()
SRC_BROOD = {"prefab": "eye_globe (mesh) + TheHive (texture)", "renderer": "eye_globe/default", "mesh": "default (eye_globe, 50 tris)", "material": "TheHive_Eye texture, brood emission (our eye mask's core)"}
rear_bvh, rear_bm = bm_bvh(REAR0, REAR1, REAR2)
rc = sum((v.co for v in rear_bm.verts), Vector()) / len(rear_bm.verts)
CELLS = []; BROOD_N = {"cell": 0, "eye": 0}
crnd = random.Random(SEED + 3)
# v1b: candidate seats = the rear crust's own vertices facing up / out / back, then the rear carapace's (the ray-cast placement of
# v1a found room for only 5-9); greedy, biggest first, never overlapping, lopsided by the shuffle
cands = []
for b_ in (REAR0, REAR1, REAR2):
    b_.normal_update()
    for v in b_.verts:
        if v.normal.z > -0.15 and v.normal.y < 0.6: cands.append((v.co.copy(), v.normal.copy(), 0))
for i, v in enumerate(base.data.vertices):
    if RV[i] == "rear" and v.normal.z > 0.0 and v.co.z > 0.45: cands.append((v.co.copy(), v.normal.copy(), 1))
crnd.shuffle(cands); cands.sort(key=lambda c: c[2])                       # the crust first, the bare carapace after
SIZES = [0.11, 0.1, 0.095, 0.09, 0.085, 0.08, 0.078, 0.075, 0.072, 0.07, 0.066, 0.064, 0.06, 0.058, 0.055, 0.052, 0.05, 0.048, 0.046, 0.044, 0.042, 0.04]
EYE_IN = {1, 4, 7, 10, 13, 16, 19}                                      # 7 of the 22 cells hold an amber slit eye
for si, r in enumerate(SIZES):
    for p_, n_, src_ in cands:
        if any((p_ - q).length < (r + rq) * 0.95 for q, rq in CELLS): continue
        CELLS.append((p_, r)); break
    else:
        continue
    is_eye = si in EYE_IN
    bm, W = globe_bm(p_, n_, r, sink=0.45 if not is_eye else 0.4)
    lab = f"brood_eye_{BROOD_N['eye']:02d}" if is_eye else f"brood_cell_{BROOD_N['cell']:02d}"
    BROOD_N["eye" if is_eye else "cell"] += 1
    rigid.append((lab, skin_bone([p_ - n_ * 0.01]), bm, eye_mat if is_eye else brood_mat, SRC_GLOBE if is_eye else SRC_BROOD, W))
print("BROOD", BROOD_N)

# ---------------------------------------------------------------- a small root web: down the flanks from the crust, onto the leg roots
R07 = LOAD("root07")
mat07 = H.part_material(R07["materials"][0], PR, "root07_mat", tint=(0.42, 0.32, 0.26))
def frame_of(P):
    vs = [H.u2b(v) for v in P["verts"]]
    mn = [min(v[k] for v in vs) for k in range(3)]; mx = [max(v[k] for v in vs) for k in range(3)]
    ext = [mx[k] - mn[k] for k in range(3)]; o = sorted(range(3), key=lambda k: -ext[k])
    return vs, mn, mx, ext, o
F07 = frame_of(R07)
def root(label, bone, bvh, anchor, direction, L, wscale=0.8, tscale=0.9):
    vs, mn, mx, ext, o = F07
    loc0, n0, _, _ = bvh.find_nearest(Vector(anchor))
    tdir = Vector(direction); tdir = (tdir - n0 * tdir.dot(n0)).normalized(); side = n0.cross(tdir).normalized()
    s = L / ext[o[0]]; cmid = (mn[o[1]] + mx[o[1]]) / 2
    out = []
    for v in vs:
        x = (v[o[0]] - mn[o[0]]) * s; y = (v[o[1]] - cmid) * s * wscale; z = (v[o[2]] - mn[o[2]]) * s * tscale
        g = loc0 + tdir * x + side * y
        sl, sn, _, _ = bvh.find_nearest(g)
        out.append(sl + sn * (0.006 + z))
    rigid.append((label, bone, H.part_bm(R07, out), mat07, {"prefab": R07["prefab"], "renderer": R07["path"], "mesh": R07["mesh"], "material": R07["materials"][0]["name"]}, Matrix.Identity(4)))
WEB = [("root_flank_L", "thorax1", BODY, T1 + Vector((-0.3, -0.2, -0.05)), (-0.2, 0.3, -1), 0.32),
       ("root_flank_R", "thorax2", BODY, T2 + Vector((0.28, 0.0, -0.05)), (0.2, -0.3, -1), 0.3),
       ("root_rear_0", "thorax3", REARB, T3 + Vector((0.12, -0.25, 0.05)), (0.1, -1, -0.5), 0.28),
       ("root_ridge_0", "abdomen", BODY, AB + Vector((0.15, 0.15, 0.3)), (0.4, 0.6, -0.6), 0.28)]
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
# from the dorsal ridge: the Elder's limbs that rise and end in SHORT forks (branch sheet cells 5 and 7), thick, up and back, lopsided
_BI = json.load(open(os.path.join(HERE, "..", "..", "kit_tools", "branch_parts_index.json")))
# v1c (coordinator: "dark weathered limbs with short forks, no loops, no antler forks"; the Elder twigs read antler-thin here): the
# AshlandsBranch2 stub (kit_tools/branch_parts_sheet.png cell 10: a thick limb ending in one SHORT fork), its geometry with TheHive's
# own bark (olivetree_trunk01 - its own charred Ashlands texture reads as charcoal) tinted dark weathered grey-brown, no emission
ASHB = LOAD("ashbranch2")
ash_mat = H.part_material(LP["materials"][0], PR, "AshBranch_barked", tint=(0.42, 0.36, 0.3))
ash_mat.node_tree.nodes["Principled BSDF"].inputs["Emission Strength"].default_value = 0.0
_av = np.array([H.u2b(v)[:] for v in ASHB["verts"]]); _ac = _av.mean(0)
_Q = _av - _ac; _ax = np.linalg.svd(_Q, full_matrices=False)[2][0]; _pr = _Q @ _ax
def _spread(m): return np.linalg.norm(_Q[m] - np.outer(_pr[m], _ax), axis=1).mean()
_lo, _hi = _pr.min(), _pr.max()
if _spread(_pr < _lo + 0.2 * (_hi - _lo)) > _spread(_pr > _hi - 0.2 * (_hi - _lo)): _ax = -_ax; _pr = -_pr; _lo, _hi = -_hi, -_lo   # root = the single (narrow) end, the fork at the tip
ASH_ROOT = Vector((_ac + _ax * _lo).tolist()); ASH_AX = Vector(_ax.tolist()); ASH_L = float(_hi - _lo)
def ash_branch(label, bone, crust_bm, direction, length, spin, sink=0.05, thick=1.4):
    d_ = Vector(direction).normalized()
    cb, cbm = bm_bvh(crust_bm); cc = sum((v.co for v in cbm.verts), Vector()) / len(cbm.verts)
    hit = cb.ray_cast(cc + d_ * 0.6, -d_, 0.8)
    root_pt = (hit[0] if hit[0] is not None else cc) - d_ * sink
    s = length / ASH_L; ax = ASH_AX
    R = Matrix.Rotation(spin, 4, d_) @ ax.rotation_difference(d_).to_matrix().to_4x4()
    A = Matrix(((ax.x * ax.x, ax.x * ax.y, ax.x * ax.z), (ax.y * ax.x, ax.y * ax.y, ax.y * ax.z), (ax.z * ax.x, ax.z * ax.y, ax.z * ax.z)))
    Sa = (Matrix.Identity(3) * (s * thick) + A * (s * (1 - thick))).to_4x4()
    M = Matrix.Translation(root_pt) @ R @ Sa @ Matrix.Translation(-ASH_ROOT)
    bm = H.part_bm(ASHB, [M @ H.u2b(v) for v in ASHB["verts"]])
    rigid.append((label, bone, bm, ash_mat, {"prefab": "AshlandsBranch2", "renderer": "stub", "mesh": "default (200 tris)", "material": "TheHive_Mat bark (olivetree_trunk01), tint 0.42/0.36/0.3"}, M))
_bone_of = lambda lab: next(r[1] for r in rigid if r[0] == lab)          # a branch rides the bone of the lump it grows from
ash_branch("branch_ridge_0", _bone_of("ridge_lump_0"), RIDGE0, (0.35, -0.6, 0.85), 0.9, 0.5)
ash_branch("branch_ridge_1", _bone_of("ridge_lump_1"), RIDGE1, (-0.5, -0.35, 0.9), 0.65, 2.0)
os.makedirs(os.path.join(OUT, "branches"), exist_ok=True)
json.dump({"about": "triangle indices (into the concatenated submeshes of gd_king.001) kept per branch; the runtime bakes them into a static mesh "
                    "placed by attach.json. Our data.", "source": "gd_king / Visual/gd_king / gd_king.001", **BRANCH_TRIS},
          open(os.path.join(OUT, "branches", "elder_branch_tris.json"), "w"))

for lab, bone, bm, m, src, W in rigid:
    ob = H.bm_object(bm, "Brood_" + lab, m if isinstance(m, list) else [m], smooth=(m is not hive_mat))
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
attach = {"_about": ("ASSET-006 Broodhusk kitbash v1: vanilla parts on the vanilla Seeker. Rigid parts: the vanilla mesh under a child of the "
                     "named bone with the given local transform (Unity, bind pose); conformed lumps add deform/lump_offsets.json; laid roots are "
                     "their vanilla mesh with per-vertex positions (identity transform). The pose test (pose_test.py) marks the pieces it skins."),
          "base": {"prefab": "Seeker", "renderer": "Visual/Plane.004", "mesh": J["mesh"], "material": J["material"]["name"], "tris": len(J["tris"])}}
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

# ---------------------------------------------------------------- EARLY REPAINT of the Seeker's own texture (the Brute's method)
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
def _cov(tris_, size):
    pp, _ = TR.raster_position_map(VSt, tris_, UV0, size); return ~np.isnan(pp[..., 0])
def _down(a):
    return a.reshape(SZO, SZ // SZO, SZO, SZ // SZO, *a.shape[2:]).mean((1, 3))
def _tris_of(pred): return [tr for tr in TRI if sum(1 for i in tr if pred(i)) >= 2]
pos1, nrm1 = TR.raster_position_map(VSt, TRI, UV0, SZO)
valid1 = ~np.isnan(pos1[..., 0]); P1 = pos1[valid1]
wing1 = _cov(_tris_of(lambda i: RV[i] in ("wingL", "wingR")), SZO)[valid1]
mand1 = _cov(_tris_of(lambda i: any(k in dom[i] for k in ("pincer", "tooth", "botant"))), SZO)[valid1]
head1 = _cov(_tris_of(lambda i: RV[i] == "head"), SZO)[valid1]
src_names = [k for k in PIECES if k.startswith(("rear_lump", "ridge_lump"))]
def _bvh_of(keys):
    sv, sf, so = [], [], 0
    for k in keys:
        o = PIECES[k]["ob"]; sv += [v.co.copy() for v in o.data.vertices]; sf += [[so + i for i in p_.vertices] for p_ in o.data.polygons]; so += len(o.data.vertices)
    return BVHTree.FromPolygons(sv, sf)
SRCB = _bvh_of(src_names)
dist = np.array([SRCB.find_nearest(Vector(q))[3] or 9.0 for q in P1])
nz = TR.value_noise3(P1, 0.5 / SC, 11) * 0.35 / SC + TR.value_noise3(P1, 0.16 / SC, 12) * 0.15 / SC + TR.value_noise3(P1, 0.05 / SC, 13) * 0.05 / SC
bark_v = 1 - TR.smoothstep(0.0, 1.2 / SC, dist + nz)
bark_v = np.where(head1 | wing1, 0.0, bark_v)                          # the head and the wings get their own treatment
orig1 = _img(os.path.join(REF, J["material"]["textures"]["_MainTex"]["png"]), SZO)
lum1 = orig1[..., :3] @ np.array([0.3, 0.59, 0.11]); lum_n1 = lum1 / max(1e-6, lum1[valid1].mean())
ext_v = TR.smoothstep(0.45, 0.08, P1[:, 2]) * (~wing1)                  # the legs' lower ends darken
# brood glow halo on the skin round the cells (emission), and the veins out of the brood
cell_pts = [np.array(p[:]) for p, r in CELLS]
dc = np.min(np.stack([np.linalg.norm(P1 - c, axis=1) for c in cell_pts]), 0) if cell_pts else np.full(len(P1), 9.0)
halo = TR.smoothstep(0.16, 0.04, dc)
pos2, _ = TR.raster_position_map(VSt, TRI, UV0, SZ)
valid2 = ~np.isnan(pos2[..., 0]); P2 = pos2[valid2]
noline2 = _cov(_tris_of(lambda i: RV[i] in ("head", "wingL", "wingR")), SZ)[valid2]
def nearest(pt):
    loc, n, _, _ = SOLID.find_nearest(Vector(tuple(pt)))
    return (np.array(loc[:]), np.array(n[:])) if loc is not None else (None, None)
_r = np.random.default_rng(6)
vein_starts = [(c, 0.009 / SC * 0.85, (_r.uniform(-1, 1), _r.uniform(-1, 1), -0.6)) for c in cell_pts[::2] for _ in range(2)]
veins = TR.smooth_curves(TR.walk_curves(nearest, vein_starts, 2, 0.75 / SC, 0.03 / SC, 21, branch=3.0 * SC, persist=0.35, jitter=0.45), nearest, 2)
root_starts = [(np.array((sum((v.co for v in PIECES[k]["ob"].data.vertices), Vector()) / len(PIECES[k]["ob"].data.vertices))[:]), 0.03 / SC, (0, 0, -1)) for k in src_names]
roots_c = TR.walk_curves(nearest, root_starts, 3, 1.8 / SC, 0.05 / SC, 31, bias=(0, 0, -1), branch=0.8 * SC)
vein2 = TR.curves_mask(pos2, veins, fade=1.2); halo2 = TR.curves_mask(pos2, [(pts, w0 * 3.5) for pts, w0 in veins], fade=1.6); root2 = TR.curves_mask(pos2, roots_c)
for a_ in (vein2, halo2, root2):
    vv_ = a_[valid2]; a_[valid2] = np.where(noline2, 0.0, vv_)
mask2 = np.zeros((SZ, SZ, 2)); mask2[..., 0] = np.maximum(vein2, 0.12 * halo2); mask2[..., 1] = root2 * 0.92
mask_l = _down(mask2)
mask = np.zeros((SZO, SZO, 4))
mask[..., 0][valid1] = bark_v; mask[..., 1][valid1] = np.maximum(ext_v, wing1 * 1.0)
mask[..., 2] = mask_l[..., 0]; mask[..., 3] = mask_l[..., 1]
_h = np.zeros((SZO, SZO)); _h[valid1] = halo; mask[..., 2] = np.maximum(mask[..., 2], 0.5 * _h)
mask = TR.dilate_fill(mask, valid1, 8)
_save(os.path.join(RP, "brood_hive_mask.png"), mask)
REC = {"about": "ASSET-006 early repaint recipe: the Hive Brute's method (kit_tools/troll_repaint.py) scaled to the Seeker (distances / 2.5). "
                "Mask = repaint/brood_hive_mask.png in the Seeker's UV0 (R bark from the crust, G: the wings (1) and the darkened leg ends, B blight "
                "veins + the brood glow halo = emission, A dark roots); lines at 2048, box-filtered to 1024.",
       "sick_mix": 0.35, "sick_skin": [0.42, 0.4, 0.28], "bark_tint": [0.75, 0.56, 0.36], "infection_margin_darken": 0.45, "extremity_darken": 0.4,
       "bark_texture": "olivetree_trunk01 (TheHive_Mat _MainTex), triplanar in rest-pose metres, tile 0.48 m",
       "wings": {"recolour": "torn bark-skin: luminance x [0.36, 0.27, 0.19] (the orange membrane goes dark leathery brown) x the bark grain at 40 %, ragged holes: "
                             "alpha 0 where a 3-octave noise > 0.42 within the outer half of the wing", "hole_threshold": 0.42},
       "seeker_emission": 0.15, "seeker_emission_note": "multiplier on its own blood-orange _EmissionColor (it lit the pincers and wing veins orange)",
       "mandibles": {"recolour": "its own pincers and teeth: min(luminance / mean, 1.3) x [0.36, 0.27, 0.14] (dirty yellow-brown)"},
       "root_colour": [0.03, 0.025, 0.02], "vein_albedo": [0.05, 0.06, 0.02], "blight_colour": [0.42, 0.55, 0.12], "emission_strength_preview": 0.85,
       "brood_halo": "0.5 x smoothstep(0.16, 0.04 m) round each brood cell, in the emission mask", "mask_size": "1024 (lines at 2048)"}
json.dump(REC, open(os.path.join(RP, "repaint.json"), "w"), indent=1)
btex = _img(os.path.join(PR, LP["materials"][0]["textures"]["_MainTex"]["png"]), 512)[..., :3]
Nv = np.abs(nrm1[valid1]); axis = Nv.argmax(1)
uu = np.where(axis == 0, P1[:, 1], P1[:, 0]); vv = np.where(axis == 2, P1[:, 1], P1[:, 2])
TILE_M = 1.2 / SC
px = ((uu / TILE_M) % 1.0 * 510).astype(int); py = ((vv / TILE_M) % 1.0 * 510).astype(int)
BKs = (btex[py, px] + btex[py + 1, px] + btex[py, px + 1] + btex[py + 1, px + 1]) * 0.25
ln = np.clip(lum_n1[valid1], 0, 2.5)[:, None]
O1 = orig1[..., :3][valid1]; mlum = float(lum1[valid1].mean())
barkcol = BKs * np.array(REC["bark_tint"]) * (0.45 + 0.55 * np.clip(ln, 0, 2))
sick = O1 * (1 - REC["sick_mix"]) + ln * mlum * np.array(REC["sick_skin"]) / 0.4 * REC["sick_mix"]
colv = sick * (1 - bark_v[:, None]) + barkcol * bark_v[:, None]
colv *= (1 - REC["extremity_darken"] * ext_v)[:, None]
colv *= (1 - REC["infection_margin_darken"] * 4 * bark_v * (1 - bark_v))[:, None]
wingcol = ln * mlum * np.array([0.36, 0.27, 0.19]) / 0.4 * (0.6 + 0.4 * BKs.mean(1, keepdims=True) / max(1e-6, BKs.mean()))
colv = np.where(wing1[:, None], wingcol, colv)
mandcol = np.clip(ln, 0, 1.3) * np.array([0.36, 0.27, 0.14])          # dirty yellow-brown (v1a: the bright pincers went orange-tan)
colv = np.where(mand1[:, None], mandcol, colv)
rm_ = mask[..., 3][valid1][:, None]; colv = colv * (1 - rm_) + np.array(REC["root_colour"]) * rm_
vm_ = np.minimum(mask[..., 2][valid1][:, None], 1.0) * (1 - _h[valid1][:, None] * 0.0); colv = colv * (1 - mask_l[..., 0][valid1][:, None]) + np.array(REC["vein_albedo"]) * mask_l[..., 0][valid1][:, None]
OUTA = orig1.copy(); OUTA[..., :3][valid1] = colv
# torn wings: ragged holes in the outer half of the membrane (alpha), from noise
wn = TR.value_noise3(P1, 0.07, 41) * 0.6 + TR.value_noise3(P1, 0.025, 42) * 0.3 + TR.value_noise3(P1, 0.01, 43) * 0.1
outer = TR.smoothstep(1.3, 2.0, np.abs(P1[:, 0]))
hole = wing1 & (wn * outer > REC["wings"]["hole_threshold"] * 0.5)
al = orig1[..., 3][valid1].copy(); al = np.where(hole, 0.0, al); OUTA[..., 3][valid1] = al
OUTA = TR.dilate_fill(OUTA, valid1, 8); OUTA[..., 3][valid1] = al
_save(os.path.join(RP, "preview_albedo_DO_NOT_SHIP.png"), OUTA)
EM = np.zeros((SZO, SZO, 4)); EM[..., 3] = 1
emv = np.clip(mask[..., 2], 0, 1)
for c_ in range(3): EM[..., c_] = emv * REC["blight_colour"][c_] * REC["emission_strength_preview"]
_hh = np.zeros((SZO, SZO)); _hh[valid1] = halo
for c_ in range(3): EM[..., c_] = np.maximum(EM[..., c_], _hh * 0.5 * BROOD_COL[c_])      # the halo glows brood-yellow
_save(os.path.join(RP, "preview_blight_emission.png"), EM)
JM = json.loads(json.dumps(J["material"])); JM["textures"]["_MainTex"]["png"] = os.path.join(RP, "preview_albedo_DO_NOT_SHIP.png")
Jr = dict(J); Jr["material"] = JM
rmat = H.base_material(Jr, REF, "Seeker_repaint")
nt = rmat.node_tree; bsdf = nt.nodes["Principled BSDF"]
vt = nt.nodes.new("ShaderNodeTexImage"); vt.image = bpy.data.images.load(os.path.join(RP, "preview_blight_emission.png")); vt.image.colorspace_settings.name = 'Non-Color'
old = bsdf.inputs["Emission Color"].links[0].from_socket if bsdf.inputs["Emission Color"].links else None
if old is not None:
    ad = nt.nodes.new("ShaderNodeMix"); ad.data_type = 'RGBA'; ad.blend_type = 'ADD'; ad.inputs[0].default_value = 1.0
    dim = nt.nodes.new("ShaderNodeMix"); dim.data_type = 'RGBA'; dim.blend_type = 'MULTIPLY'; dim.inputs[0].default_value = 1.0
    nt.links.new(old, dim.inputs[6]); dim.inputs[7].default_value = (REC["seeker_emission"],) * 3 + (1,); old = dim.outputs[2]
    nt.links.new(old, ad.inputs[6]); nt.links.new(vt.outputs["Color"], ad.inputs[7]); nt.links.new(ad.outputs[2], bsdf.inputs["Emission Color"])
    _S = bsdf.inputs["Emission Strength"].default_value or 1.0
    if abs(_S - 1.0) > 1e-3:
        _save(os.path.join(RP, "preview_blight_emission.png"), np.concatenate([EM[..., :3] / _S, EM[..., 3:]], -1)); vt.image.reload()
else:
    nt.links.new(vt.outputs["Color"], bsdf.inputs["Emission Color"]); bsdf.inputs["Emission Strength"].default_value = 1.0
ORIG_MAT = base.data.materials[0]; base.data.materials[0] = rmat
REPAINT = {"bark_over_half_pct": round(float((bark_v > 0.5).mean() * 100), 1), "covered_texels": int(valid1.sum()), "wing_texels": int(wing1.sum()),
           "wing_hole_texels": int(hole.sum()), "mandible_texels": int(mand1.sum()), "vein_paths": len(veins), "root_curves": len(roots_c)}
print("REPAINT", REPAINT)

# ---------------------------------------------------------------- previews
H.setup_eevee(900, 800); H.lights_and_world(aim=(0, 0, 0.8))
tgt = Vector((0, -0.1, 0.8))
def shots(prefix, views, dist=7.5):
    for nm, az, el in views:
        H.camera(tgt, dist, FA + az, el, lens=55); H.render(os.path.join(PV, f"{prefix}_{nm}.png"))
KV = (("front", 0, 8), ("side", 90, 8), ("back", 180, 8), ("34", 35, 15), ("34back", 145, 15))
shots("kit", KV)
for pc in PIECES.values(): pc["ob"].hide_render = True
base.data.materials[0] = ORIG_MAT; shots("base", (("front", 0, 8), ("34", 35, 15)))
base.data.materials[0] = rmat; shots("base_repaint", (("34", 35, 15),))
for pc in PIECES.values(): pc["ob"].hide_render = False
# the brood from 10 m at the side and the 3/4 (the coordinator's read test)
sc = bpy.context.scene
H.camera(tgt, 10.0, FA + 90, 8, lens=55); H.render(os.path.join(PV, "read10m_side.png"))
H.camera(tgt, 10.0, FA + 145, 15, lens=55); H.render(os.path.join(PV, "read10m_34back.png"))
sc.render.resolution_x = sc.render.resolution_y = 900
H.camera(rc, 1.6, FA + 140, 25, lens=55); H.render(os.path.join(PV, "close_brood.png"))
eyes_ = [k for k in PIECES if k.startswith("brood_eye")]
if eyes_:
    o = PIECES[eyes_[0]]["ob"]; ec = sum((v.co for v in o.data.vertices), Vector()) / len(o.data.vertices)
    H.camera(ec, 0.5, FA + 150, 25, lens=55); H.render(os.path.join(PV, "close_brood_eye_1to1.png"))
H.camera(P_("head") + Vector((0, 0.15, 0)), 1.6, FA + 30, 10, lens=55); H.render(os.path.join(PV, "close_head.png"))
H.camera(T1 + Vector((0, -0.2, 0.5)), 2.6, FA + 120, 20, lens=55); H.render(os.path.join(PV, "close_branches.png"))
H.camera(P_("l.wing2"), 2.6, FA + 160, 50, lens=55); H.render(os.path.join(PV, "close_wing.png"))
bpy.ops.mesh.primitive_cube_add(size=1); fig = bpy.context.active_object; fig.name = "Figure"; fig.scale = (0.45, 0.25, 1.8); fig.location = (5.2, 0, 0.9)
fm = bpy.data.materials.new("fig"); fm.use_nodes = True; fm.node_tree.nodes["Principled BSDF"].inputs["Base Color"].default_value = (0.4, 0.6, 1, 1); fig.data.materials.append(fm)
bcopy = base.copy(); bcopy.data = base.data.copy(); bcopy.data.materials[0] = ORIG_MAT; bcopy.location.x = 0.0; sc.collection.objects.link(bcopy)
for pc in PIECES.values(): pc["ob"].location.x = -6.2
base.location.x = -6.2
sc.render.resolution_x, sc.render.resolution_y = 1600, 800
H.camera(Vector((-0.5, 0, 1.0)), 17.0, FA, 6, lens=55); H.render(os.path.join(PV, "lineup.png"))
bpy.data.objects.remove(fig, do_unlink=True); bpy.data.objects.remove(bcopy, do_unlink=True)
for pc in PIECES.values(): pc["ob"].location.x = 0
base.location.x = 0
bpy.ops.wm.save_as_mainfile(filepath=os.path.join(OUT, "Broodhusk_kitbash.blend"))

# ---------------------------------------------------------------- README (measured numbers only)
att = attach
def grp(pref): return [k for k in att if k.startswith(pref)]
L = ["# ASSET-006 Broodhusk: kitbash v1 (vanilla parts on the vanilla Seeker), step 1", "",
     "Built by `../make_broodhusk_kitbash.py` (deterministic, seed 6606; its helper sections are the Seer's, verbatim). Base exported by",
     "`../../../kit_tools_b/export_base.py`, parts by `export_part.py` (into `../_ref/`: game data, dev reference, never shipped). Every number",
     "below was measured by that run. The Seeker faces +Y in Blender; `front` renders look at its face.", "",
     "## Triangles (measured)", "",
     f"- Base (Seeker `Plane.004`): **{ST['base_tris']}**", f"- Vanilla parts on it: **{ST['addon_tris']}**",
     f"- Total: **{ST['total_tris']}** of 12000 ({'PASS' if ST['total_tris'] <= 12000 else 'FAIL'})", "",
     "## What is on it", "",
     f"- **Crust:** {len(grp('rear_lump')) + len(grp('ridge_lump'))} TheHive `low` lumps CONFORMED (the Brute's deformation, rims thinned all the way round: edge profile 1.4, no shelves): three over the rear segments (thorax2 / thorax3, lopsided), two along the dorsal ridge (thorax1 / abdomen). Offsets: `../deform/lump_offsets.json`.",
     f"- **Brood (the WTF):** {BROOD_N['cell'] + BROOD_N['eye']} brood cells set into the rear crust (`eye_globe` domes, radius 40-110 mm, 40-45 % sunk; on the crust, and past its edge in the carapace): {BROOD_N['cell']} glowing brood-yellow cells (our emission: the eye mask's core, widened) and {BROOD_N['eye']} holding the Brute's amber slit eye (eye_globe + TheHive_Eye + core / slit-pupil mask). A brood-yellow glow halo is painted on the skin round them (emission mask). Read test: `read10m_side.png`, `read10m_34back.png` (10 m).",
     f"- **Branches:** {len(grp('branch_'))} thick dead limbs ending in ONE short fork (the AshlandsBranch2 stub, branch sheet cell 10, {sum(att[k]['tris'] for k in grp('branch_'))} tris) out of the two dorsal-ridge lumps, rising up and back, lopsided; dressed in TheHive's own bark (olivetree_trunk01, tint 0.42 / 0.36 / 0.3) because its charred Ashlands texture reads as charcoal; no emission, no loops, no antler forks (the Elder twigs read antler-thin on the Seeker).",
     f"- **Mouth parts:** its OWN pincers, teeth and lower feelers, repainted dirty yellow-brown ({REPAINT['mandible_texels']} texels); nothing added.",
     f"- **Wings:** its own, repainted toward torn bark-skin: the orange membrane goes dark leathery brown with the bark grain, and {REPAINT['wing_hole_texels']} texels of ragged holes are cut into its alpha (outer half). Never leafy.",
     f"- **Root web:** {len(grp('root_'))} catacomb roots down the flanks and the rear.",
     f"- **Repaint** (`../repaint/brood_hive_mask.png` + `repaint.json`): bark spreading from the crust ({REPAINT['bark_over_half_pct']} % of the used texels over half), {REPAINT['vein_paths']} thin dark veins out of the brood, {REPAINT['root_curves']} painted roots, the brood halo. `base_repaint_34.png` shows the base alone repainted; `base_front.png` / `base_34.png` the untouched Seeker.", "",
     "## Parts, sources and attach (attach.json has the full transforms)", "",
     "| part | source | rides | mode | tris | base pairs | nearest (mm) | floating |", "|---|---|---|---|---|---|---|---|"]
for k, v in att.items():
    if k.startswith("_") or k == "base": continue
    s_ = v["source"]; f = v["fit"]
    L.append(f"| {k} | {s_['prefab']} / {s_['renderer']} | {v['parent']} | {v['mode']} | {v['tris']} | {f['base_pairs']} | {f['nearest_to_base_mm']} | {f['floating']} |")
L += ["", "## New geometry", "", "None. Every triangle is vanilla (TheHive `low`, `eye_globe`, `fi_vil_combs_root07`, the AshlandsBranch2 stub).",
      "The lumps are conformed (per-vertex offsets), the roots laid onto the body (per-vertex positions), the branches scaled non-uniformly; all our data.", "",
      "## Previews", "",
      "- `kit_front/side/back/34/34back.png`; `base_front.png`, `base_34.png` (untouched); `base_repaint_34.png`",
      "- `close_brood.png`, `close_brood_eye_1to1.png`, `close_head.png` (its own mandibles), `close_branches.png`, `close_wing.png`",
      "- `read10m_side.png`, `read10m_34back.png`: the brood read at 10 m", "- `lineup.png`: the Broodhusk, the untouched Seeker, a 1.8 m figure (front view: right to left)", ""]
open(os.path.join(PV, "README.md"), "w").write("\n".join(L) + "\n")
print("BROOD done")
