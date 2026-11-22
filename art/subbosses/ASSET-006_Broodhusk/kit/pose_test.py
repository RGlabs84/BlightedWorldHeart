"""Pose test for the Broodhusk kit (adapted from the Seer's) (the owner's "not jank" check), the Husk's method on the Greydwarf_Shaman rig.
Opens Broodhusk_kitbash.blend, rebuilds the skeleton from its bind matrices (base.json), skins the base with its exported weights,
binds the branches rigidly, the head lumps and eyes as one piece each (the mean of the skin under the lump), each maw fang with its lip to their bone (attach.json), and skins the body lumps (back hunch, shoulders: as ONE piece, the mean of the skin weights under them) and the laid roots (nearest skin weights, 45 % piece mean) - the Husk's
fixes. Poses (the Shaman's own moves):
  cast       both arms thrown up and forward over the head (its spell), spine arched back a little
  walk       a long stride: left thigh forward 35, right thigh back 25, knees bent, arms hanging and swinging opposite
  hunch      spine bent forward 25+20, head down 30, arms hanging (its idle / crouch)
  head_turn  head turned 55 and down 20 (the eye bulb and the jaw against the shoulders)
Measures per pose against the posed base: add-on / body intersecting pairs (change from bind), parts sunk 3+ cm deeper, parts lifted
2+ cm, and parts whose edges squash < 60 % / stretch > 150 % (2nd / 98th pct) with the skin under them for reference.
Writes previews/pose_test.png (2x2), pose_close_*.png, pose_test.json, transfer_weights.json, the README's pose section, and marks
the skinned pieces in attach.json.
Run: heavy.sh 4G sb-pose blender -b <kit>/Broodhusk_kitbash.blend -P pose_test.py -- <kit dir>"""
import bpy, sys, os, json, math
import numpy as np
from mathutils import Vector, Matrix
from mathutils.bvhtree import BVHTree
from mathutils.kdtree import KDTree
KIT = sys.argv[sys.argv.index("--") + 1]
sys.path.insert(0, os.path.join(KIT, "..", "..", "kit_tools_b"))
import hivefit as H
REF = os.path.join(KIT, "_ref"); PV = os.path.join(KIT, "previews")
J = json.load(open(os.path.join(REF, "base.json"))); ATT = json.load(open(os.path.join(KIT, "attach.json")))
FA = 180.0
sc = bpy.context.scene
base = bpy.data.objects["Seeker_base"]
for o in bpy.data.objects:
    if o.name.startswith(("Brood_", "Seeker_base")): o.hide_render = False; o.hide_viewport = False
names = J["bone_names"]; BW = {n: H.m_u2b(M) for n, M in zip(names, J["bone_bind_world"])}
par = {}
for n in names:
    a = J["nodes"][n]["parent"]
    while a is not None and a not in names: a = J["nodes"][a]["parent"]
    par[n] = a
kids = {n: [c for c in names if par[c] == n] for n in names}
def region(b):
    if b in ("head", "neck") or any(k in b for k in ("topant", "botant", "pincer", "tooth")): return "head"
    if b.startswith("l.wing"): return "wingL"
    if b.startswith("r.wing"): return "wingR"
    if b.startswith(("l.frontarm", "l.backleg")): return "legL"
    if b.startswith(("r.frontarm", "r.backleg")): return "legR"
    if b in ("thorax2", "thorax3"): return "rear"
    return "torso"
ENDS = {}
arm_d = bpy.data.armatures.new("SeekerRig"); rig = bpy.data.objects.new("SeekerRig", arm_d); sc.collection.objects.link(rig)
bpy.context.view_layer.objects.active = rig; bpy.ops.object.mode_set(mode='EDIT')
for n in names:
    eb = arm_d.edit_bones.new(n); hd = BW[n].translation.copy()
    if n in ENDS and ENDS[n] in J["nodes"]: tl = H.node_pos(J, ENDS[n])
    elif kids[n]: tl = sum((BW[c].translation for c in kids[n]), Vector()) / len(kids[n])
    else: tl = hd + Vector((0, 0, 0.1))
    if (tl - hd).length < 0.02: tl = hd + Vector((0, 0, 0.08))
    eb.head, eb.tail = hd, tl
for n in names:
    if par[n]: arm_d.edit_bones[n].parent = arm_d.edit_bones[par[n]]
bpy.ops.object.mode_set(mode='OBJECT')
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
_dom = [names[I[i][int(np.argmax(W[i]))]] for i in range(len(W))]
_kd = KDTree(len(BV0))
for i, c in enumerate(BV0): _kd.insert(c, i)
_kd.balance()
_kdr = {}
for rg in ("torso", "rear", "legL", "legR"):
    iv = [i for i in range(len(BV0)) if region(_dom[i]) == rg]
    _kdr[rg] = KDTree(len(iv))
    for i in iv: _kdr[rg].insert(BV0[i], i)
    _kdr[rg].balance()
def nearest_w(co, k=3, reg=None):
    acc, tw = {}, 0.0
    for c, i, d in (_kdr[reg] if reg else _kd).find_n(co, k):
        wt = 1.0 / max(d, 0.005); tw += wt
        for kk in range(4):
            if W[i][kk] > 0: b = names[I[i][kk]]; acc[b] = acc.get(b, 0) + wt * float(W[i][kk])
    return {b: x / tw for b, x in acc.items()}
SKINNED_PREFIX = ("root_", "shoulder_lump", "back_hunch")
TRANSFER = {}; PARTS = {}
# RIGID-FIRST (coordinator): every crust lump, brood cell, eye and branch rides its own bone rigidly; only the laid roots follow
# the skin under them (45 % piece mean). Pieces the test shows failing get fixed by a better bone first, skinning last.
# rigid-first round 1 (bones picked by the skin under each piece) still left the rear crust cutting 85-121 mm into the next segment in
# the strike (the abdomen curls 15 + 20 deg and a mound spans two segments): those mounds move as ONE piece with the mean of the skin
# under them, and every brood cell / eye seated on one moves with it
SKIN_LATER = {"rear_lump_0": "mean", "rear_lump_1": "mean", "rear_lump_2": "mean"}
LUMP_MEAN = {}
for k in SKIN_LATER:
    ob = bpy.data.objects.get("Brood_" + k)
    acc = {}
    for vv in ob.data.vertices:
        for b_, x in nearest_w(vv.co).items(): acc[b_] = acc.get(b_, 0) + x / len(ob.data.vertices)
    LUMP_MEAN[k] = (acc, BVHTree.FromPolygons([v.co for v in ob.data.vertices], [list(p.vertices) for p in ob.data.polygons]))
def centre(ob): return sum((v.co for v in ob.data.vertices), Vector()) / len(ob.data.vertices)
for k, v in ATT.items():
    if k.startswith("_") or k == "base" or "parent" not in v: continue
    ob = bpy.data.objects.get("Brood_" + k)
    if ob is None: continue
    if k.startswith("root_"):
        reg = region(v["parent"]); reg = reg if reg in ("torso", "rear") else None
        wl = [nearest_w(vv.co, reg=reg) for vv in ob.data.vertices]
        mean = {}
        for w in wl:
            for b_, x in w.items(): mean[b_] = mean.get(b_, 0) + x / len(wl)
        wl = [{b_: 0.55 * w.get(b_, 0) + 0.45 * mean.get(b_, 0) for b_ in set(w) | set(mean)} for w in wl]
        skin(ob, wl); PARTS[k] = (ob, "skin"); TRANSFER[k] = [{b: round(x, 4) for b, x in w.items() if x > 0.01} for w in wl]
    elif k.startswith(("brood_cell", "brood_eye")) and any(LUMP_MEAN[h][1].find_nearest(centre(ob))[3] < 0.06 for h in LUMP_MEAN):
        host = min(LUMP_MEAN, key=lambda h: LUMP_MEAN[h][1].find_nearest(centre(ob))[3]); w = LUMP_MEAN[host][0]
        skin(ob, [w for _ in ob.data.vertices]); PARTS[k] = (ob, "skin"); TRANSFER[k] = {"with": host, **{b: round(x, 4) for b, x in w.items() if x > 0.01}}
    elif k in SKIN_LATER or k.startswith(("brood_cell", "brood_eye")):   # round 2: the cells set into the bare carapace (rigid, they cut 86-130 mm into the next segment in the strike): one piece with the skin under them
        acc = {}
        for vv in ob.data.vertices:
            for b_, x in nearest_w(vv.co).items(): acc[b_] = acc.get(b_, 0) + x / len(ob.data.vertices)
        skin(ob, [acc for _ in ob.data.vertices]); PARTS[k] = (ob, "skin"); TRANSFER[k] = {b: round(x, 4) for b, x in acc.items() if x > 0.01}
    else:
        skin(ob, [{v["parent"]: 1.0} for _ in ob.data.vertices]); PARTS[k] = (ob, v["parent"])
FWD = Vector((0, 1, 0))
def dirv(a, b): return (BW[b].translation - BW[a].translation).normalized()
def rot_to(a_dir, b_dir): return a_dir.rotation_difference(b_dir).to_matrix().to_4x4()
def bend(d, ang): ax = d.cross(FWD).normalized(); return Matrix.Rotation(ang, 4, ax)
RX = lambda deg: Matrix.Rotation(math.radians(deg), 4, 'X')
def RW(axis, deg): return Matrix.Rotation(math.radians(deg), 4, axis)
POSES = {   # the Seeker's own moves; forward = +Y
    "wings_spread": {"l.wing1": RW('Y', 35) @ RW('X', 15), "r.wing1": RW('Y', -35) @ RW('X', 15), "l.wing2": RW('Y', 20), "r.wing2": RW('Y', -20)},
    "strike": {"thorax1": RX(-10), "neck": RX(-20), "head": RX(-15), "l.frontarm1": RX(-50), "r.frontarm1": RX(-50),
               "thorax2": RX(15), "thorax3": RX(20)},
    "crouch": {"hip": Matrix.Translation((0, 0, -0.18)), "thorax2": RX(-15), "thorax3": RX(-20),
               "l.backleg1": RW('Y', -25), "r.backleg1": RW('Y', 25), "l.frontarm1": RW('Y', -20), "r.frontarm1": RW('Y', 20)},
    "head_turn": {"neck": RW('Z', 35), "head": RW('Z', 25) @ RX(-15)},
}
order = []
def walk_(n):
    order.append(n)
    for c in kids[n]: walk_(c)
for n in names:
    if par[n] is None: walk_(n)
def set_pose(spec):
    G = {}
    for n in order:
        h = BW[n].translation; R = spec.get(n)
        Lc = (Matrix.Translation(h) @ R @ Matrix.Translation(-h)) if R is not None else Matrix.Identity(4)
        G[n] = (G[par[n]] if par[n] else Matrix.Identity(4)) @ Lc
        if n == "hip" and "hip" in spec and spec["hip"].to_3x3() == Matrix.Identity(3): G[n] = spec["hip"] @ (G[par[n]] if par[n] else Matrix.Identity(4))
    for n in order:
        rig.pose.bones[n].matrix = G[n] @ rig.data.bones[n].matrix_local
        bpy.context.view_layer.update()
def evaluated(ob):
    dg = bpy.context.evaluated_depsgraph_get(); e = ob.evaluated_get(dg); me = e.to_mesh()
    vs = [e.matrix_world @ v.co for v in me.vertices]; fs = [list(p.vertices) for p in me.polygons]; e.to_mesh_clear()
    return vs, fs
EDGE0 = {}; NEAR_E = {}
BASE_E0 = [(e.vertices[0], e.vertices[1], (BV0[e.vertices[0]] - BV0[e.vertices[1]]).length, (BV0[e.vertices[0]] + BV0[e.vertices[1]]) / 2) for e in base.data.edges]
BASE_E0 = [e for e in BASE_E0 if e[2] > 1e-4]
def measure():
    bvs, bfs = evaluated(base)
    solid = BVHTree.FromPolygons(bvs, bfs)
    out = {"pairs": 0, "per_part_pairs": {}, "_min": {}, "_strain": {}, "_bstrain": {}, "_into": {}}
    bkd = KDTree(len(bvs))
    for i, c in enumerate(bvs): bkd.insert(c, i)
    bkd.balance()
    for k, (ob, bone) in PARTS.items():
        vs, fs = evaluated(ob)
        if not fs: continue
        mine = BVHTree.FromPolygons(vs, fs); n = len(mine.overlap(solid)); out["pairs"] += n; out["per_part_pairs"][k] = n
        ds = []
        for p in vs[::2]:
            loc, nn, _, d = solid.find_nearest(p)
            if loc is not None: ds.append(d if (p - loc).dot(nn) >= 0 else -d)
        if ds:
            out["_min"][k] = (min(ds), min(abs(x) for x in ds))
            pm = vs[::2][int(np.argmin(ds))]; out["_into"][k] = _dom[bkd.find(pm)[1]]   # the bone of the body it is in
        E0 = EDGE0.setdefault(k, [(e.vertices[0], e.vertices[1], (ob.data.vertices[e.vertices[0]].co - ob.data.vertices[e.vertices[1]].co).length) for e in ob.data.edges])
        rr = sorted((vs[i] - vs[j]).length / max(L, 1e-6) for i, j, L in E0 if L > 1e-4)
        if rr: out["_strain"][k] = (rr[max(0, len(rr) // 50)], rr[min(len(rr) - 1, len(rr) * 49 // 50)])
        if k not in NEAR_E:
            kd = KDTree(len(ob.data.vertices))
            for i_, v_ in enumerate(ob.data.vertices): kd.insert(v_.co, i_)
            kd.balance(); NEAR_E[k] = [e for e in BASE_E0 if kd.find(e[3])[2] < 0.04]
        rb = sorted((bvs[i] - bvs[j]).length / L for i, j, L, _ in NEAR_E[k])
        if rb: out["_bstrain"][k] = (rb[max(0, len(rb) // 50)], rb[min(len(rb) - 1, len(rb) * 49 // 50)])
    return out
REST = measure()
CLOSE = {"wings_spread": {"rear": ("thorax2", 150, 30)}, "strike": {"head": ("head", 30, 10), "rear": ("thorax3", 110, 10)},
         "crouch": {"rear": ("thorax3", 120, 15)}, "head_turn": {"head": ("head", -40, 10)}}
H.setup_eevee(800, 700); H.lights_and_world(aim=(0, 0, 0.8))
res = {"bind": {"pairs": REST["pairs"]}}; imgs = []
for name, spec in POSES.items():
    set_pose(spec)
    r = measure()
    out = {"pairs": r["pairs"], "pairs_change_from_bind": r["pairs"] - REST["pairs"],
           "deep_parts": {k: f"{round(m[0] * 1000)} (into {r['_into'].get(k, '?')})" for k, m in r["_min"].items() if m[0] < REST["_min"].get(k, (0, 0))[0] - 0.03},
           "lifted_parts": [k for k, m in r["_min"].items() if m[1] > REST["_min"].get(k, (0, 0))[1] + 0.02],
           "part_pairs_up": {k: v - REST["per_part_pairs"].get(k, 0) for k, v in r["per_part_pairs"].items() if v - REST["per_part_pairs"].get(k, 0) > 20},
           "torn_or_crumpled": {k: {"part": [round(lo, 2), round(hi, 2)], "skin_under_it": [round(x, 2) for x in r["_bstrain"].get(k, (0, 0))]}
                                for k, (lo, hi) in r["_strain"].items() if lo < 0.6 or hi > 1.5}}
    res[name] = out
    H.camera(Vector((0, -0.1, 0.8)), 7.0, FA + 145, 18, lens=55); p_ = os.path.join(KIT, f"_pose_{name}.png"); H.render(p_); imgs.append(p_)
    G_ = {n: rig.matrix_world @ rig.pose.bones[n].head for n in names}
    for cname, (bn, az, el) in CLOSE[name].items():
        H.camera(Vector(bn) if isinstance(bn, tuple) else G_[bn], 2.2, FA + az, el, lens=55); H.render(os.path.join(PV, f"pose_close_{name}_{cname}.png"))
    print("POSE", name, json.dumps(out))
json.dump({"about": "skin weights for the pieces skinned by the pose test (nearest-skin transfer, 3 neighbours, inverse distance; body lumps = the "
                    "mean (one piece), roots 45 % mean (arm roots 70 %, arm skin only)); per vertex {bone: weight}", "pieces": TRANSFER},
          open(os.path.join(KIT, "transfer_weights.json"), "w"))
for k in TRANSFER:
    ATT[k]["mode"] = "skinned (weights from the skin under it: transfer_weights.json)"
json.dump(ATT, open(os.path.join(KIT, "attach.json"), "w"), indent=1)
json.dump(res, open(os.path.join(PV, "pose_test.json"), "w"), indent=1)
RM = os.path.join(PV, "README.md"); txt = open(RM).read() if os.path.exists(RM) else ""
txt = txt.split("\n## Pose test")[0].rstrip("\n") + "\n"
L = ["", "## Pose test (`../pose_test.py`, measured on the posed meshes; `pose_test.png`, close-ups `pose_close_*.png`)", "",
     "RIGID-FIRST: base skinned with its own weights; every crust lump, brood cell, eye and branch rides its own bone rigidly (unless listed",
     f"as skinned after failing: {sorted(SKIN_LATER) or 'none'} as one piece each, with the brood cells and eyes seated on them; the cells set into the bare carapace as one piece with the skin under them); the laid roots",
     "follow the skin under them (45 % piece mean).",
     f"Bind pose: {REST['pairs']} add-on/body intersecting triangle pairs (most are the conformed lumps' bottoms, under the carapace by design).", "",
     "| pose | pairs (change) | sunk 3+ cm deeper (mm) | lifted 2+ cm | squash < 60 % / stretch > 150 % (part; skin under it) |", "|---|---|---|---|---|"]
for name in POSES:
    r = res[name]
    tc = "; ".join(f"{k} {v['part'][0]}-{v['part'][1]} (skin {v['skin_under_it'][0]}-{v['skin_under_it'][1]})" for k, v in r["torn_or_crumpled"].items()) or "none"
    L.append(f"| {name} | {r['pairs']} ({r['pairs_change_from_bind']:+d}) | {', '.join(f'{k} {v}' for k, v in r['deep_parts'].items()) or 'none'} | {', '.join(r['lifted_parts']) or 'none'} | {tc} |")
open(RM, "w").write(txt + "\n".join(L) + "\n")
def arr(p):
    im = bpy.data.images.load(p); w, h = im.size; a = np.empty(w * h * 4, np.float32); im.pixels.foreach_get(a); return a.reshape(h, w, 4)
A = [arr(p) for p in imgs]
S = np.concatenate([np.concatenate([A[2], A[3]], 1), np.concatenate([A[0], A[1]], 1)], 0); h, w = S.shape[:2]
im = bpy.data.images.new("pt", w, h, alpha=True); im.pixels.foreach_set(S.ravel()); im.filepath_raw = os.path.join(PV, "pose_test.png"); im.file_format = 'PNG'; im.save()
for p_ in imgs: os.remove(p_)
print("POSETEST done")
