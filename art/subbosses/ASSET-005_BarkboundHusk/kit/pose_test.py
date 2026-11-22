"""Pose test for the Barkbound Husk kit (the owner's "not jank" check). Opens BarkboundHusk_kitbash.blend, rebuilds the Draugr
skeleton from its bind matrices (base.json), skins the base with its exported weights, skins the rebound Root armour with its
own Player-rig weights mapped to the Draugr bones, binds every rigid part 100 % to its bone (attach.json), then poses:
  arms_up      both upper arms raised above the head
  elbows_120   both elbows bent 120 degrees (forearms folding forward)
  crouch       deep knee bend: thighs forward ~95 deg, shins back ~115 deg, hips lowered, spine leaning forward
  head_turn    head turned 60 degrees and the chin down 25 degrees
and measures per pose, against the posed base: add-on / base intersecting pairs (and the change from the bind pose), rigid
parts sunk deeper than 4 cm (poking through), rigid parts lifted more than 2 cm off the body they touched, and base vertices
that end up inside a closed lump that did not hold them in the bind pose. Writes previews/pose_test.png (2x2) + pose_test.json.
Run: heavy.sh 4G sb-pose blender -b <kit>/BarkboundHusk_kitbash.blend -P pose_test.py -- <kit dir>"""
import bpy, bmesh, sys, os, json, math
import numpy as np
from mathutils import Vector, Matrix
from mathutils.bvhtree import BVHTree
KIT = sys.argv[sys.argv.index("--") + 1]
sys.path.insert(0, os.path.join(KIT, "..", "..", "kit_tools_b"))
import hivefit as H
REF = os.path.join(KIT, "_ref"); PR = os.path.join(REF, "parts"); PV = os.path.join(KIT, "previews")
J = json.load(open(os.path.join(REF, "base.json"))); ATT = json.load(open(os.path.join(KIT, "attach.json")))
sc = bpy.context.scene
base = bpy.data.objects["Draugr_base"]
for o in bpy.data.objects:   # the kitbash leaves its parts hidden after the lineup render
    if o.name.startswith(("Husk_", "Draugr_base")): o.hide_render = False; o.hide_viewport = False
names = J["bone_names"]; BW = {n: H.m_u2b(M) for n, M in zip(names, J["bone_bind_world"])}
par = {}
for n in names:
    a = J["nodes"][n]["parent"]
    while a is not None and a not in names: a = J["nodes"][a]["parent"]
    par[n] = a
kids = {n: [c for c in names if par[c] == n] for n in names}
ENDS = {"LeftHand": "LeftHand_end", "RightHand": "RightHand_end", "LeftFoot": "LeftFoot_end", "RightFoot": "RightFoot_end", "Head": "Head_end"}
TAILCHILD = {"Hips": "Spine0", "Spine2": "Head", "LeftShoulder": "LeftArm", "RightShoulder": "RightArm", "LeftHip": "LeftUpLeg", "RightHip": "RightUpLeg"}
# ---- armature
arm_d = bpy.data.armatures.new("DraugrRig"); rig = bpy.data.objects.new("DraugrRig", arm_d); sc.collection.objects.link(rig)
bpy.context.view_layer.objects.active = rig; bpy.ops.object.mode_set(mode='EDIT')
for n in names:
    eb = arm_d.edit_bones.new(n); hd = BW[n].translation.copy()
    if n in TAILCHILD: tl = BW[TAILCHILD[n]].translation.copy()
    elif n in ENDS: tl = H.node_pos(J, ENDS[n])
    elif kids[n]: tl = BW[kids[n][0]].translation.copy()
    else: tl = hd + Vector((0, 0, 0.1))
    if (tl - hd).length < 0.02: tl = hd + Vector((0, 0, 0.08))
    eb.head, eb.tail = hd, tl
for n in names:
    if par[n]: arm_d.edit_bones[n].parent = arm_d.edit_bones[par[n]]
bpy.ops.object.mode_set(mode='OBJECT')
# ---- skinning
def skin(ob, wl):
    for vi, w in enumerate(wl):
        for b, x in w.items():
            if x <= 0: continue
            g = ob.vertex_groups.get(b) or ob.vertex_groups.new(name=b)
            g.add([vi], x, 'ADD')
    m = ob.modifiers.new("arm", 'ARMATURE'); m.object = rig
W = np.array(J["weights"]); I = np.array(J["indices"])
skin(base, [{names[I[i][k]]: float(W[i][k]) for k in range(4)} for i in range(len(W))])
BV0 = [v.co.copy() for v in base.data.vertices]
from mathutils.kdtree import KDTree
_cards0 = H.card_tris(base, J, REF)
_solidv = sorted({i for p_ in base.data.polygons if p_.index not in _cards0 for i in p_.vertices})   # not the beard / hair cards (skinned to Head)
_kd = KDTree(len(_solidv))
for i in _solidv: _kd.insert(BV0[i], i)
_kd.balance()
_dom = [names[I[i][int(np.argmax(W[i]))]] for i in range(len(W))]
_tv = [i for i in _solidv if H.region_of(_dom[i]) == "torso"]
_kdt = KDTree(len(_tv))
for i in _tv: _kdt.insert(BV0[i], i)
_kdt.balance()
_kdr = {}
for _rg in ("armL", "armR"):
    _rv = [i for i in _solidv if H.region_of(_dom[i]) == _rg]
    _kdr[_rg] = KDTree(len(_rv))
    for i in _rv: _kdr[_rg].insert(BV0[i], i)
    _kdr[_rg].balance()
def nearest_w(co, k=3, torso_only=False, region=None):
    """weights of the nearest Draugr vertices (inverse-distance blend of 3): a part laid on the skin follows the skin.
    torso_only: a root laid on the torso takes torso skin only (near the armpit / hip it picked up arm or thigh weights and stretched)"""
    acc, tw = {}, 0.0
    for c, i, d in (_kdr[region] if region else (_kdt if torso_only else _kd)).find_n(co, k):
        wt = 1.0 / max(d, 0.005); tw += wt
        for kk in range(4):
            if W[i][kk] > 0: b = names[I[i][kk]]; acc[b] = acc.get(b, 0) + wt * float(W[i][kk])
    return {b: x / tw for b, x in acc.items()}
TRANSFER = {}

for label, key in (("root_chest", "rootchest"), ("root_legs", "rootlegs")):
    P = json.load(open(os.path.join(PR, key + ".json"))); pw = np.array(P["weights"]); pi = np.array(P["indices"])
    def mapb(n):
        return H.PLAYER_TO_DRAUGR.get(n) or next((k for k in ("LeftHand", "RightHand", "LeftFoot", "RightFoot") if n.startswith(k)), "Head")
    wl = []
    for i in range(len(pw)):
        d = {}
        for k in range(4):
            if pw[i][k] > 0: b = mapb(P["bone_names"][pi[i][k]]); d[b] = d.get(b, 0) + float(pw[i][k])
        wl.append(d)
    obr = bpy.data.objects["Husk_" + label]
    if label == "root_chest":   # v6 fix: below the belt (the skirt) the weights come from the Draugr's own loincloth / thighs
        for vi, vv in enumerate(obr.data.vertices):
            if vv.co.z < 1.06: wl[vi] = nearest_w(vv.co)
        TRANSFER[label + "_below_belt"] = {vi: {b: round(x, 4) for b, x in wl[vi].items() if x > 0.01} for vi, vv in enumerate(obr.data.vertices) if vv.co.z < 1.06}
    skin(obr, wl)
RIGID = {}
for k, v in ATT.items():
    if k.startswith("_") or k == "base" or k in ("root_chest", "root_legs"): continue
    ob = bpy.data.objects.get("Husk_" + k)
    if ob is None: continue
    if k.startswith(("root_", "shoulder_lump")):     # v6 fix after the pose test: skinned to the skin under them
        _reg = H.region_of(v["parent"])
        # v7: pieces on the upper arm take ARM skin only (shoulder / torso weights made them crumple at the armpit with the arms up)
        wl = [nearest_w(vv.co, torso_only=(_reg == "torso" and not k.startswith("root_neck")), region=(_reg if _reg in ("armL", "armR") and k.startswith("root_") else None)) for vv in ob.data.vertices]
        # (the deltoid lumps keep all the skin under them, as ONE piece: arm-only they dived 58-73 mm into the trapezius with the arms up)   # neck roots run over the shoulder: they keep its arm weights
        # stiffness: each vertex keeps part of the piece's mean weights, so a root or lump follows the skin without crumpling
        # where the skin folds (the left armpit root crumpled with arms up at stiffness 0); lumps are stiffer (keep their shape)
        # roots 45 %; shoulder lumps 100 %: every lump vertex gets the lump's mean weights, so the lump moves as ONE piece with the
        # average motion of the skin under it (no crumple; rigid on the arm bone it dived 72-105 mm into the neck with arms up)
        st = 1.0 if k.startswith("shoulder_lump") else (0.7 if _reg in ("armL", "armR") else 0.45)
        mean = {}
        for w in wl:
            for b_, x in w.items(): mean[b_] = mean.get(b_, 0) + x / len(wl)
        wl = [{b_: (1 - st) * w.get(b_, 0) + st * mean.get(b_, 0) for b_ in set(w) | set(mean)} for w in wl]
        skin(ob, wl); RIGID[k] = (ob, "skin")
        TRANSFER[k] = [{b: round(x, 4) for b, x in w.items() if x > 0.01} for w in wl]
    else:
        skin(ob, [{v["parent"]: 1.0} for _ in ob.data.vertices]); RIGID[k] = (ob, v["parent"])
# ---- poses: world rotations about each bone's own head, composed down the hierarchy
FWD = Vector((0, -1, 0))
def dirv(a, b): return (BW[b].translation - BW[a].translation).normalized()
def rot_to(a_dir, b_dir): return a_dir.rotation_difference(b_dir).to_matrix().to_4x4()
def bend(d, ang): ax = d.cross(FWD).normalized(); return Matrix.Rotation(ang, 4, ax)
POSES = {
    "arms_up": {"LeftArm": rot_to(dirv("LeftArm", "LeftForeArm"), Vector((0.28, 0, 0.96)).normalized()),
                "RightArm": rot_to(dirv("RightArm", "RightForeArm"), Vector((-0.28, 0, 0.96)).normalized())},
    "elbows_120": {"LeftForeArm": bend(dirv("LeftForeArm", "LeftHand"), math.radians(120)),
                   "RightForeArm": bend(dirv("RightForeArm", "RightHand"), math.radians(120))},
    "crouch": {"_hips": Matrix.Translation((0, 0, -0.42)), "Spine0": Matrix.Rotation(math.radians(20), 4, 'X'),
               "LeftUpLeg": bend(dirv("LeftUpLeg", "LeftLeg"), math.radians(95)), "RightUpLeg": bend(dirv("RightUpLeg", "RightLeg"), math.radians(95)),
               "LeftLeg": bend(dirv("LeftLeg", "LeftFoot"), math.radians(-115)), "RightLeg": bend(dirv("RightLeg", "RightFoot"), math.radians(-115))},
    "head_turn": {"Head": Matrix.Rotation(math.radians(60), 4, 'Z') @ Matrix.Rotation(math.radians(25), 4, 'X')},
}
order = []
def walk(n):
    order.append(n)
    for c in kids[n]: walk(c)
for n in names:
    if par[n] is None: walk(n)
def set_pose(spec):
    G = {}
    for n in order:
        h = BW[n].translation
        R = spec.get(n)
        Lc = (Matrix.Translation(h) @ R @ Matrix.Translation(-h)) if R is not None else Matrix.Identity(4)
        G[n] = (G[par[n]] if par[n] else spec.get("_hips", Matrix.Identity(4))) @ Lc
    for n in order:
        pb = rig.pose.bones[n]; pb.matrix = G[n] @ rig.data.bones[n].matrix_local
        bpy.context.view_layer.update()
def evaluated(ob):
    dg = bpy.context.evaluated_depsgraph_get(); e = ob.evaluated_get(dg); me = e.to_mesh()
    vs = [e.matrix_world @ v.co for v in me.vertices]; fs = [list(p.vertices) for p in me.polygons]; e.to_mesh_clear()
    return vs, fs
def body_solid():
    vs, fs = evaluated(base)
    cards = set()
    for p in base.data.polygons:   # the same hair / beard card test as the kit (texture alpha at the UVs)
        pass
    return vs, fs
CARDS = H.card_tris(base, J, REF)
def measure(tag):
    bvs, bfs = evaluated(base)
    solid = BVHTree.FromPolygons(bvs, [f for i, f in enumerate(bfs) if i not in CARDS])
    out = {"pairs": 0, "deep_parts": {}, "lifted_parts": [], "base_verts_inside_lumps": 0, "per_part_pairs": {}}
    for k, (ob, bone) in list(RIGID.items()) + [("root_chest", (bpy.data.objects["Husk_root_chest"], None)), ("root_legs", (bpy.data.objects["Husk_root_legs"], None))]:
        vs, fs = evaluated(ob)
        if not fs: continue
        mine = BVHTree.FromPolygons(vs, fs); n = len(mine.overlap(solid)); out["pairs"] += n; out["per_part_pairs"][k] = n
        E0 = EDGE0.setdefault(k, [(e.vertices[0], e.vertices[1], (ob.data.vertices[e.vertices[0]].co - ob.data.vertices[e.vertices[1]].co).length) for e in ob.data.edges])
        rr = sorted((vs[i] - vs[j]).length / max(L, 1e-6) for i, j, L in E0 if L > 1e-4)
        if rr: out.setdefault("_strain", {})[k] = (rr[max(0, len(rr) // 50)], rr[min(len(rr) - 1, len(rr) * 49 // 50)])   # 2nd / 98th percentile edge length ratio
        if k not in NEAR_E:   # the Draugr's own skin edges within 4 cm of the part (bind): the reference for how much the skin there stretches
            kd = KDTree(len(ob.data.vertices))
            for i_, v_ in enumerate(ob.data.vertices): kd.insert(v_.co, i_)
            kd.balance(); NEAR_E[k] = [e for e in BASE_E0 if kd.find(e[3])[2] < 0.04]
        rb = sorted((bvs[i] - bvs[j]).length / L for i, j, L, _ in NEAR_E[k])
        if rb: out.setdefault("_bstrain", {})[k] = (rb[max(0, len(rb) // 50)], rb[min(len(rb) - 1, len(rb) * 49 // 50)])
        if bone is None: continue
        ds = []
        for p in vs[::2]:
            loc, nn, _, d = solid.find_nearest(p)
            if loc is not None: ds.append(d if (p - loc).dot(nn) >= 0 else -d)
        if ds: out.setdefault("_min", {})[k] = (min(ds), min(abs(x) for x in ds))
        if k.startswith(("helm_crown", "helm_back", "helm_brow", "helm_temple", "helm_cheek", "helm_nape", "shoulder_lump", "back_lump", "palm_lump")):
            lb = mine; cnt = 0
            for p in bvs:
                hits, q = 0, p
                for _ in range(8):
                    h = lb.ray_cast(q, Vector((0, 0, 1)), 3.0)
                    if h[0] is None: break
                    hits += 1; q = h[0] + Vector((0, 0, 1e-4))
                cnt += hits % 2
            out["base_verts_inside_lumps"] += cnt
    return out
EDGE0 = {}; NEAR_E = {}
BASE_E0 = [(e.vertices[0], e.vertices[1], (base.data.vertices[e.vertices[0]].co - base.data.vertices[e.vertices[1]].co).length,
            (base.data.vertices[e.vertices[0]].co + base.data.vertices[e.vertices[1]].co) / 2) for e in base.data.edges]
BASE_E0 = [e for e in BASE_E0 if e[2] > 1e-4]
REST = measure("bind")
CLOSE = {"arms_up": {"shoulder_L": ("LeftArm", -40, 15), "shoulder_R": ("RightArm", 40, 15)},
         "elbows_120": {"elbow_L": ("LeftForeArm", -60, 10), "elbow_R": ("RightForeArm", 60, 10)},
         "crouch": {"hips_34": ((0, -0.1, 0.62), -35, 5), "hips_side": ((0, -0.1, 0.62), -90, 0)},
         "head_turn": {"neck_back": ("Head", 150, 15), "face": ("Head", -20, 5)}}
H.setup_eevee(700, 800); H.lights_and_world(aim=(0, 0, 1.0))
res = {"bind": REST}; imgs = []
for name, spec in POSES.items():
    set_pose(spec)
    r = measure(name)
    r["deep_parts"] = {k: round(m[0] * 1000) for k, m in r["_min"].items() if m[0] < REST["_min"].get(k, (0, 0))[0] - 0.03}     # sank 3+ cm deeper than at bind
    r["lifted_parts"] = [k for k, m in r["_min"].items() if m[1] > REST["_min"].get(k, (0, 0))[1] + 0.02]                       # lifted 2+ cm further off
    r.pop("_min")
    _bs = r.pop("_bstrain", {})
    r["torn_or_crumpled"] = {k: {"part": [round(lo, 2), round(hi, 2)], "draugr_skin_under_it": [round(x, 2) for x in _bs.get(k, (0, 0))]}
                             for k, (lo, hi) in r.pop("_strain").items() if lo < 0.6 or hi > 1.5}   # edges squashed below 60 % or stretched past 150 % (2nd / 98th pct)
    r["pairs_change_from_bind"] = r["pairs"] - REST["pairs"]
    r["part_pairs_up"] = {k: v - REST["per_part_pairs"].get(k, 0) for k, v in r["per_part_pairs"].items() if v - REST["per_part_pairs"].get(k, 0) > 20}
    r["base_verts_inside_lumps_change"] = r["base_verts_inside_lumps"] - REST["base_verts_inside_lumps"]
    r.pop("per_part_pairs")
    res[name] = r
    tgt = Vector((0, 0, 0.85 if name == "crouch" else 1.15))
    H.camera(tgt, 4.0, -35, 10, lens=55); p_ = os.path.join(KIT, f"_pose_{name}.png"); H.render(p_); imgs.append(p_)
    G_ = {n: rig.matrix_world @ rig.pose.bones[n].head for n in names}
    for cname, (bn, az, el) in CLOSE[name].items():   # close-ups of the joint each pose stresses (the jank check is by eye too)
        H.camera(Vector(bn) if isinstance(bn, tuple) else G_[bn], 1.3 if not isinstance(bn, tuple) else 2.0, az, el, lens=55); H.render(os.path.join(PV, f"pose_close_{name}_{cname}.png"))
        if os.environ.get("POSE_DEBUG_HIDE") and name == "arms_up":   # debug only: which piece is that (renders to POSE_DEBUG_DIR)
            for hn in os.environ["POSE_DEBUG_HIDE"].split(","):
                bpy.data.objects["Husk_" + hn].hide_render = True
            H.render(os.path.join(os.environ["POSE_DEBUG_DIR"], f"dbg_{cname}.png"))
            for hn in os.environ["POSE_DEBUG_HIDE"].split(","):
                bpy.data.objects["Husk_" + hn].hide_render = False
        if name == "crouch":   # the vanilla Draugr alone in the same pose: its own tunic is the reference for what is "ours"
            hid = [o for o in bpy.data.objects if o.name.startswith("Husk_")]
            for o in hid: o.hide_render = True
            H.render(os.path.join(PV, f"pose_close_{name}_{cname}_BASE_ONLY.png"))
            for o in hid: o.hide_render = False
    print("POSE", name, json.dumps(r))
REST.pop("per_part_pairs", None); REST.pop("_strain", None); REST.pop("_bstrain", None); REST.pop("_min", None); REST.pop("deep_parts", None); REST.pop("lifted_parts", None)
json.dump({"about": "skin weights for the pieces skinned after the pose test (nearest-Draugr-vertex transfer, 3 neighbours, inverse distance, blended with the piece's mean weights so they do not crumple: 45 % for roots, 100 % for the shoulder lumps, which then move as one piece); per vertex {bone: weight}", "pieces": TRANSFER},
          open(os.path.join(KIT, "transfer_weights.json"), "w"))
for k in TRANSFER:
    if k in ATT: ATT[k]["mode"] = "skinned (weights from the nearest Draugr vertices: transfer_weights.json)"; ATT[k]["why_skinned"] = "pose test: riding one bone it cut into the skin when the joint moved"
if "root_chest" in ATT: ATT["root_chest"]["below_belt_weights"] = "transfer_weights.json root_chest_below_belt (the Draugr's own loincloth / thigh weights)"
json.dump(ATT, open(os.path.join(KIT, "attach.json"), "w"), indent=1)
json.dump(res, open(os.path.join(PV, "pose_test.json"), "w"), indent=1)
# the README's pose-test section (replaced on every run)
RM = os.path.join(PV, "README.md"); txt = open(RM).read() if os.path.exists(RM) else ""
txt = txt.split("\n## Pose test")[0].rstrip("\n") + "\n"
L = ["", "## Pose test (`../pose_test.py`, measured on the posed meshes; `pose_test.png`, close-ups `pose_close_*.png`)", "",
     "Base skinned with its exported Draugr weights; the Root armour with its own Player-rig weights mapped to Draugr bones (its few belt-line",
     "vertices below 1.06 m take the nearest Draugr weights); the small roots take the weights of the nearest 3 solid Draugr vertices (torso roots except the two over the shoulders: torso skin only; upper-arm roots: arm skin only) blended 45 % (arm roots 70 %)",
     "with the piece's mean, the shoulder lumps the mean alone (one piece, no crumple) (`../transfer_weights.json`, our data); helm, eyes, rims, back and palm lumps stay rigid on their bone.",
     f"Bind pose: {REST['pairs']} add-on/body intersecting triangle pairs (most are the deliberate 35 % sink of the lumps and the half-sunk eyes).", "",
     "| pose | pairs (change from bind) | parts sunk 3+ cm deeper (signed mm) | parts lifted 2+ cm | body verts newly inside a lump | parts whose edges squash < 60 % or stretch > 150 % (part 2nd/98th pct; Draugr skin under it) |",
     "|---|---|---|---|---|---|"]
for name in POSES:
    r = res[name]
    tc = "; ".join(f"{k} {v['part'][0]}-{v['part'][1]} (skin {v['draugr_skin_under_it'][0]}-{v['draugr_skin_under_it'][1]})" for k, v in r["torn_or_crumpled"].items()) or "none"
    L.append(f"| {name} | {r['pairs']} ({r['pairs_change_from_bind']:+d}) | {', '.join(f'{k} {v}' for k, v in r['deep_parts'].items()) or 'none'} | {', '.join(r['lifted_parts']) or 'none'} | {r['base_verts_inside_lumps_change']:+d} | {tc} |")
open(RM, "w").write(txt + "\n".join(L) + "\n")
def arr(p):
    im = bpy.data.images.load(p); w, h = im.size; a = np.empty(w * h * 4, np.float32); im.pixels.foreach_get(a); return a.reshape(h, w, 4)
A = [arr(p) for p in imgs]
top = np.concatenate([A[0], A[1]], 1); bot = np.concatenate([A[2], A[3]], 1)
S = np.concatenate([bot, top], 0); h, w = S.shape[:2]
im = bpy.data.images.new("pt", w, h, alpha=True); im.pixels.foreach_set(S.ravel()); im.filepath_raw = os.path.join(PV, "pose_test.png"); im.file_format = 'PNG'; im.save()
for p_ in imgs: os.remove(p_)
print("POSETEST done")
