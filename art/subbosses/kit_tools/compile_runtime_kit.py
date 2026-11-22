"""compile_runtime_kit.py - turn an APPROVED kitbash scene into the runtime data the mod loads (integration stage 2).

The approved Blender scene is the ground truth (both agents' builders did steps their attach.json does not record, e.g. agent B
bent its roots along the body). For every part object in the scene:
  1. find its vanilla source mesh (the exported game data: same vertices, same triangles) - by mesh_path_id or prefab + renderer;
  2. check the vertex correspondence EXACTLY: the scene part's triangles must be the source's triangles (as vertex-index sets),
     after the island remap (sorted unique vertex indices of the kept triangles) for parts cut from a bigger mesh;
  3. express the scene vertices in the parent BONE's local space (the scene's own pose: rest for agent A's kits, bind for B's)
     and fit the affine map L (3x4) from the source mesh's own vertices; the rest goes into per-vertex residuals.
Runtime (C#): v_bone = L * v_vanilla + residual  (no game geometry is shipped: only L, residuals, triangle ids, names).

Run: heavy.sh 4G <label> blender -b --factory-startup -P compile_runtime_kit.py -- <asset folder name> <abs out dir>
"""
import bpy, os, sys, json, glob
import numpy as np

SUB = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
argv = sys.argv[sys.argv.index("--") + 1:]
ASSET, OUT = argv[0], argv[1]
KIT = os.path.join(SUB, ASSET, "kit")

CFG = {
    "ASSET-001_HiveBrute": dict(id="BlightedSB_HiveBrute", donor="Troll", fmt="A", blend="HiveBrute_kitbash.blend", prefix="", hide=["Hair"], body="Body"),
    "ASSET-002_Rootstalker": dict(id="BlightedSB_Rootstalker", donor="Wolf", fmt="A", blend="Rootstalker_kitbash.blend", prefix="", hide=[], body="M"),
    "ASSET-003_Gorgemaw": dict(id="BlightedSB_Gorgemaw", donor="Lox", fmt="A", blend="Gorgemaw_kitbash.blend", prefix="", hide=["Furr1"], body="Body"),
    "ASSET-004_EyeblightSeer": dict(id="BlightedSB_EyeblightSeer", donor="Greydwarf_Shaman", fmt="B", blend="EyeblightSeer_kitbash_step3.blend", prefix="Seer_", hide=["Plane", "Plane.001"]),
    "ASSET-005_BarkboundHusk": dict(id="BlightedSB_BarkboundHusk", donor="Draugr", fmt="B", blend="BarkboundHusk_kitbash_step3.blend", prefix="Husk_", hide=[]),
    "ASSET-006_Broodhusk": dict(id="BlightedSB_Broodhusk", donor="Seeker", fmt="B", blend="Broodhusk_kitbash_step3.blend", prefix="Brood_", hide=[]),
}[ASSET]


# ---------------------------------------------------------------- vanilla source data (exported game data, dev-only)
SRC = {}
for f in glob.glob(os.path.join(SUB, "ASSET-00*", "kit", "vanilla_ref", "*.json")) + \
         glob.glob(os.path.join(SUB, "ASSET-00*", "kit", "_ref", "parts", "*.json")) + \
         glob.glob(os.path.join(SUB, "ASSET-00*", "kit", "_ref", "*.json")) + \
         glob.glob(os.path.join(SUB, "ASSET-00*", "kit", "ref", "*.json")) + \
         glob.glob(os.path.join(SUB, "runtime_src", "*.json")):
    try:
        d = json.load(open(f))
    except Exception:
        continue
    if not isinstance(d, dict) or "verts" not in d:
        continue
    tri = d.get("submeshes") or ([d["tris"]] if isinstance(d.get("tris"), list) and d["tris"] and isinstance(d["tris"][0], list) else None)
    if tri is None:
        continue
    d["_tris"] = [tuple(t) for sm in tri for t in sm]
    d["_file"] = f
    for k in (d.get("mesh_path_id"), (d.get("prefab"), os.path.basename(str(d.get("renderer_path") or d.get("renderer") or "")))):
        if k is not None:
            SRC.setdefault(k, d)
    SRC.setdefault(("prefab", d.get("prefab")), d)
print("SOURCES", len(SRC))


def find_source(prefab, renderer, path_id=None):
    if path_id is not None and path_id in SRC:
        return SRC[path_id]
    return SRC.get((prefab, os.path.basename(renderer or ""))) or SRC.get(("prefab", prefab))


# ---------------------------------------------------------------- bone matrices in the scene's pose (Unity world)
# vanilla material to use instead of the host renderer's own (what the approved look used)
MAT_OVERRIDE = {"eye_globe": "TheHive_Eye", "AshlandsBranch2": "TheHive_Mat"}


def quat_of(R):
    """rotation matrix (column vectors) -> quaternion (x, y, z, w), Unity convention"""
    tr = R[0, 0] + R[1, 1] + R[2, 2]
    if tr > 0:
        s = 2.0 * np.sqrt(tr + 1.0); w = 0.25 * s
        x = (R[2, 1] - R[1, 2]) / s; y = (R[0, 2] - R[2, 0]) / s; z = (R[1, 0] - R[0, 1]) / s
    elif R[0, 0] > R[1, 1] and R[0, 0] > R[2, 2]:
        s = 2.0 * np.sqrt(1.0 + R[0, 0] - R[1, 1] - R[2, 2]); x = 0.25 * s
        w = (R[2, 1] - R[1, 2]) / s; y = (R[0, 1] + R[1, 0]) / s; z = (R[0, 2] + R[2, 0]) / s
    elif R[1, 1] > R[2, 2]:
        s = 2.0 * np.sqrt(1.0 + R[1, 1] - R[0, 0] - R[2, 2]); y = 0.25 * s
        w = (R[0, 2] - R[2, 0]) / s; x = (R[0, 1] + R[1, 0]) / s; z = (R[1, 2] + R[2, 1]) / s
    else:
        s = 2.0 * np.sqrt(1.0 + R[2, 2] - R[0, 0] - R[1, 1]); z = 0.25 * s
        w = (R[1, 0] - R[0, 1]) / s; x = (R[0, 2] + R[2, 0]) / s; y = (R[1, 2] + R[2, 1]) / s
    return (x, y, z, w)


def quat_m(q):
    x, y, z, w = q
    return np.array([[1 - 2 * (y * y + z * z), 2 * (x * y - z * w), 2 * (x * z + y * w)],
                     [2 * (x * y + z * w), 1 - 2 * (x * x + z * z), 2 * (y * z - x * w)],
                     [2 * (x * z - y * w), 2 * (y * z + x * w), 1 - 2 * (x * x + y * y)]])


def bones_A():
    """agent A: the scene is the prefab REST pose, root at the origin (its local position dropped)."""
    db = json.load(open(os.path.join(SUB, ASSET, "donor", "donor_bones.json")))
    T = {t["path"]: t for t in db["transforms"]}
    W = {}

    def world(path):
        if path in W:
            return W[path]
        t = T[path]
        M = np.eye(4)
        if t["parent"] is not None:
            M[:3, :3] = quat_m(t["local_rot_xyzw"]) @ np.diag(t["local_scale"]); M[:3, 3] = t["local_pos"]
            par = path.rsplit("/", 1)[0]
            M = world(par) @ M
        W[path] = M
        return M
    out = {}
    for p in T:
        out.setdefault(p.rsplit("/", 1)[1], world(p))
    return out


def bones_B():
    """agent B: the scene is the BIND pose."""
    b = json.load(open(os.path.join(KIT, "_ref", "base.json")))
    return {n: np.array(M) for n, M in zip(b["bone_names"], b["bone_bind_world"])}


BONES = bones_A() if CFG["fmt"] == "A" else bones_B()


# ---------------------------------------------------------------- STAGE 4: skin weights (our data: bone names + weights per vertex)
TW = {}
if os.path.exists(os.path.join(KIT, "transfer_weights.json")):
    TW = json.load(open(os.path.join(KIT, "transfer_weights.json")))["pieces"]          # agent B: per piece, per scene vertex
BODY = None
if CFG["fmt"] == "A":                                                                   # agent A: the recipe in attach.json "skin"
    BODY = json.load(open(os.path.join(SUB, ASSET, "donor", f"donor_mesh_{CFG['body']}.json")))
    BODY["_V"] = np.array(BODY["verts_rest_world"]); BODY["_I"] = np.array(BODY["bone_indices"]); BODY["_W"] = np.array(BODY["bone_weights"])
PLAYER_TO_DRAUGR = {"Hips": "Hips", "Spine": "Spine0", "Spine1": "Spine1", "Spine2": "Spine2", "Neck": "Head", "Head": "Head", "Jaw": "Head"}
for _s in ("Left", "Right"):
    PLAYER_TO_DRAUGR.update({f"{_s}Shoulder": f"{_s}Shoulder", f"{_s}Arm": f"{_s}Arm", f"{_s}ForeArm": f"{_s}ForeArm", f"{_s}Hand": f"{_s}Hand",
                             f"{_s}UpLeg": f"{_s}UpLeg", f"{_s}Leg": f"{_s}Leg", f"{_s}Foot": f"{_s}Foot", f"{_s}ToeBase": f"{_s}Foot"})


def player_bone(n):                     # hivefit.py pose_test mapb: unmapped fingers/toes follow the hand/foot, else the head
    return PLAYER_TO_DRAUGR.get(n) or next((k for k in ("LeftHand", "RightHand", "LeftFoot", "RightFoot") if n.startswith(k)), "Head")


def weights_A(Vu, own_share):
    """attach.json 'skin' (agent A): the 4 nearest donor-body vertices (rest pose), inverse distance, then
    own_share x per-vertex + (1 - own_share) x the part's average"""
    out = []
    for v in Vu:
        d = np.linalg.norm(BODY["_V"] - v, axis=1); nn = np.argsort(d)[:4]
        acc = {}
        for j in nn:
            w = 1.0 / max(d[j], 1e-4)
            for k in range(4):
                if BODY["_W"][j][k] > 0:
                    b = BODY["bone_names"][BODY["_I"][j][k]]; acc[b] = acc.get(b, 0.0) + w * float(BODY["_W"][j][k])
        t = sum(acc.values()); out.append({b: x / t for b, x in acc.items()})
    mean = {}
    for w in out:
        for b, x in w.items(): mean[b] = mean.get(b, 0.0) + x / len(out)
    return [{b: own_share * w.get(b, 0.0) + (1 - own_share) * mean.get(b, 0.0) for b in set(w) | set(mean)} for w in out]


def pack_skin(wl):
    """per vertex {bone: w} -> {bones, bi (4 indices), bw (4 weights, normalised)}"""
    bones = sorted({b for w in wl for b, x in w.items() if x > 0})
    ix = {b: i for i, b in enumerate(bones)}
    bi, bw = [], []
    for w in wl:
        top = sorted(((x, b) for b, x in w.items() if x > 0), reverse=True)[:4]
        t = sum(x for x, _ in top) or 1.0
        top += [(0.0, bones[0])] * (4 - len(top))
        bi.append([ix[b] for _, b in top]); bw.append([round(x / t, 5) for x, _ in top])
    return {"bones": bones, "bi": bi, "bw": bw}


# ---------------------------------------------------------------- part list from attach.json
att = json.load(open(os.path.join(KIT, "attach.json")))
islands = {}
if CFG["fmt"] == "B":
    for f in glob.glob(os.path.join(KIT, "branches", "*.json")) + glob.glob(os.path.join(KIT, "maw", "*.json")):
        islands[os.path.basename(f)] = json.load(open(f))


def part_source(name, p):
    """(source data, kept triangle ids or None)"""
    if CFG["fmt"] == "A":
        s = att["_sources"][p["source"]]
        d = find_source(s["prefab"], s["renderer"], s.get("mesh_path_id"))
        return d, s.get("triangles")
    for isl in islands.values():                                   # agent B islands: branches/*.json, maw/*.json
        if name in isl:
            prefab, renderer = [x.strip() for x in isl["source"].split(" / ")[:2]]
            return find_source(prefab, renderer), isl[name]
    src = p["source"]
    if isinstance(src, dict):
        return find_source(src.get("prefab", "").split(" ")[0], src.get("renderer")), p.get("kept_tris")
    return None, None


def scene_obj(name):
    for nm in (CFG["prefix"] + name, name):
        if nm in bpy.data.objects:
            return bpy.data.objects[nm]
    return None


bpy.ops.wm.open_mainfile(filepath=os.path.join(KIT, CFG["blend"]))
report = {"ok": [], "no_object": [], "no_source": [], "mismatch": []}
parts = []
for name, p in att.items():
    if name.startswith("_") or name == "base":
        continue
    rebound = str(p.get("mode", "")).startswith("skinned (rebound")
    if rebound and not os.environ.get("BH_KIT_ROOT_ARMOUR"):
        # in game 2026-11-22: ArmorRootChest/Legs ship UNREADABLE (RootArmorSkirt, RootArmorPants.005), so the cut + refit cannot
        # be rebuilt at runtime; left out of the kit until the owner picks a route (BH_KIT_ROOT_ARMOUR=1 compiles it anyway)
        report.setdefault("left_out_unreadable", []).append(name); continue
    ob = scene_obj(name)
    if ob is None:
        report["no_object"].append(name); continue
    if rebound:
        # the Husk's Root armour: the vanilla ArmorRootChest/Legs mesh rebound to the Draugr; kept triangles per submesh
        # (<name>_kept_tris.json); the scene object keeps EVERY source vertex (index = vanilla index), only the kept faces
        d = SRC.get(("prefab", p["source"]["prefab"])) if isinstance(p["source"], dict) else None
        if d is None:
            report["no_source"].append((name, "rebound source")); continue
        kj = json.load(open(os.path.join(KIT, p["kept_tris_file"])))["kept"]
        offs, kept = 0, []
        for si, sm in enumerate(d.get("submeshes") or [d["_tris"]]):
            if si < len(kj): kept += [offs + t for t in kj[si]]
            offs += len(sm)
        p = dict(p); p["parent"] = "Hips"
    else:
        d, kept = part_source(name, p)
    if d is None:
        report["no_source"].append((name, str(p.get("source"))[:80])); continue
    # source triangles and vertices (island remap for kept-triangle parts)
    tris = d["_tris"] if kept is None else [d["_tris"][i] for i in kept]
    vi = sorted({i for t in tris for i in t}) if kept is not None else list(range(len(d["verts"])))
    remap = {o: n for n, o in enumerate(vi)}
    src_faces = sorted(tuple(sorted(remap[i] for i in t)) for t in tris)
    me = ob.data
    scn_faces = sorted(tuple(sorted(pg.vertices)) for pg in me.polygons)
    nv = len(vi)
    full_index = rebound and len(me.vertices) == len(d["verts"])           # scene vertex index = vanilla index
    if full_index:
        scn_faces = sorted(tuple(sorted(remap.get(i, -1) for i in pg.vertices)) for pg in me.polygons)
    if (len(me.vertices) != nv and not full_index) or scn_faces != src_faces:
        # one known case: smooth-subdivided lumps (Gorgemaw DENSE) keep the original vertices first
        if len(me.vertices) > nv and kept is None:
            report["mismatch"].append((name, f"scene {len(me.vertices)} verts vs source {nv}: subdivided? using the first {nv}"))
        else:
            report["mismatch"].append((name, f"scene {len(me.vertices)} verts / {len(scn_faces)} faces vs source {nv} / {len(src_faces)}"))
            continue
    Wb = np.array(ob.matrix_world)
    # STAGE 4: a smooth-subdivided lump (Gorgemaw DENSE): the scene keeps the 137 vanilla vertices first; every added vertex sits
    # on one original edge. Shipped: its parent edge + its offset from that edge's midpoint (bone-local), and the scene triangles.
    subdiv = None
    if len(me.vertices) > nv and kept is None and not full_index:
        adj = {}
        for e in me.edges:
            a_, b_ = e.vertices; adj.setdefault(a_, set()).add(b_); adj.setdefault(b_, set()).add(a_)
        mids, bad_ = [], 0
        for i in range(nv, len(me.vertices)):
            par_ = sorted(j for j in adj.get(i, ()) if j < nv)
            if len(par_) != 2: bad_ += 1; par_ = (par_ + [0, 0])[:2]
            mids.append(par_)
        if bad_ == 0 and all(len(pg.vertices) == 3 for pg in me.polygons):
            subdiv = {"mids": mids, "tris": [i for pg in me.polygons for i in pg.vertices]}
        else:
            report["mismatch"].append((name, f"subdivision not decodable ({bad_} added vertices without 2 original neighbours)"))
    scene_ix = vi if full_index else list(range(nv))
    Vb = np.array([(Wb @ np.array([*me.vertices[i].co, 1.0]))[:3] for i in scene_ix])
    Vu = Vb[:, [0, 2, 1]]                                                    # Blender -> Unity
    bone = p.get("parent")
    if bone not in BONES:
        report["no_source"].append((name, f"bone {bone} not in the donor skeleton")); continue
    Bi = np.linalg.inv(BONES[bone])
    Vl = (np.c_[Vu, np.ones(nv)] @ Bi.T)[:, :3]                              # bone-local
    Vs = np.array(d["verts"])[vi]                                            # vanilla mesh-local
    X = np.c_[Vs, np.ones(nv)]
    L, *_ = np.linalg.lstsq(X, Vl, rcond=None)                               # (4,3): Vl ~ X @ L
    R = Vl - X @ L
    scale = max(np.ptp(Vl, 0).max(), 1e-9)
    rmax = float(np.abs(R).max()) / scale
    trs = None
    if rmax < 1e-4 and kept is None:                                  # whole vanilla mesh, rigid: place it by a transform only
        A3 = L.T[:, :3]; U, s_, Vt = np.linalg.svd(A3); Rm = U @ Vt
        if np.linalg.det(Rm) > 0:
            Sm = Rm.T @ A3
            if np.abs(Sm - np.diag(np.diag(Sm))).max() <= 1e-3 * np.abs(np.diag(Sm)).max():
                trs = {"p": [round(float(x), 7) for x in L.T[:, 3]], "r": [round(float(x), 7) for x in quat_of(Rm)],
                       "s": [round(float(x), 7) for x in np.diag(Sm)]}
    host_mats = [m.get("name") if isinstance(m, dict) else str(m) for m in d.get("materials", [])]
    # STAGE 3: the approved scene's material per RUNTIME submesh (the runtime keeps the source submeshes that have kept
    # triangles, in ascending order; a whole mesh keeps all). Each scene polygon is matched to its source triangle by vertex
    # set; the majority material of a submesh's polygons is its look key into runtime/materials.json.
    sub_of_tri, k_ = [], 0
    for si, sm in enumerate(d.get("submeshes") or [d["_tris"]]):
        sub_of_tri += [si] * len(sm)
    tri_ids = list(range(len(d["_tris"]))) if kept is None else list(kept)
    sub_by_face = {}
    for ti in tri_ids:
        sub_by_face[tuple(sorted(remap[i] for i in d["_tris"][ti]))] = sub_of_tri[ti]
    votes = {}
    for pg in me.polygons:
        si = sub_by_face.get(tuple(sorted(pg.vertices)))
        mat = ob.material_slots[pg.material_index].material.name if ob.material_slots and ob.material_slots[pg.material_index].material else None
        if si is not None and mat:
            votes.setdefault(si, {}).setdefault(mat, 0)
            votes[si][mat] += 1
    used_subs = sorted({sub_of_tri[ti] for ti in tri_ids}) if kept is not None else list(range(len(d.get("submeshes") or [0])))
    if not votes and ob.material_slots:                                    # subdivided lumps: no polygon matches; the object's own
        cnt = {}                                                          # majority material (they are single-material TheHive lumps)
        for pg in me.polygons:
            m_ = ob.material_slots[pg.material_index].material
            if m_: cnt[m_.name] = cnt.get(m_.name, 0) + 1
        if cnt: votes = {s: cnt for s in used_subs}
    looks = [max(votes[s], key=votes[s].get) if s in votes else None for s in used_subs]
    if any(x is None for x in looks):
        report["mismatch"].append((name, f"no scene material for submesh(es) {[s for s, x in zip(used_subs, looks) if x is None]}"))
    skin = None
    if trs is None and (rebound or p.get("mode") != "rigid"):
        if rebound:
            pw, pi_, pn = d["weights"], d["indices"], d["bone_names"]
            wl = []
            for i in vi:
                w = {}
                for k in range(4):
                    if pw[i][k] > 0: b = player_bone(pn[pi_[i][k]]); w[b] = w.get(b, 0.0) + float(pw[i][k])
                bb = TW.get(name + "_below_belt", {}).get(str(i))          # v6: the skirt follows the Draugr's own thighs
                wl.append(bb if bb else w)
        elif name in TW:
            wl = TW[name]
            if isinstance(wl, dict):                                       # one weight set for the whole piece ({bone: w}),
                wl = [wl.get(str(i), {}) for i in range(nv)] if all(k.isdigit() for k in wl) else [wl] * nv   # or index-keyed
            if len(wl) != nv:
                report["mismatch"].append((name, f"{len(wl)} transfer weights for {nv} vertices: left rigid")); wl = None
        elif BODY is not None:
            wl = weights_A(Vu, float(p.get("weight_own_share", 0.5)))
        else:
            wl = None
        if wl is not None:
            if not all(b in BONES for w in wl for b in w):
                report["mismatch"].append((name, "skin bone not in the skeleton: left rigid"))
            else:
                skin = pack_skin(wl)
    if subdiv is not None:                                                  # the added vertices' offsets, bone-local
        Wl = np.array([(Bi @ np.r_[(Wb @ np.array([*v.co, 1.0]))[:3][[0, 2, 1]], 1.0])[:3] for v in me.vertices])
        Lv = np.c_[Vs, np.ones(nv)] @ L + R                                    # = the runtime's baked original vertices
        subdiv["mids"] = [[a_, b_] + [round(float(x), 6) for x in Wl[nv + k] - 0.5 * (Lv[a_] + Lv[b_])] for k, (a_, b_) in enumerate(subdiv["mids"])]
    parts.append({
        "name": name, "bone": bone, "mode": "rigid" if p.get("mode") == "rigid" else "skinned",
        "mesh": {"name": d.get("mesh"), "verts": len(d["verts"]), "path_id": d.get("mesh_path_id"),
                 "prefab": d.get("prefab"), "renderer": d.get("renderer_path") or d.get("renderer")},
        "kept_tris": kept,
        "L": [[round(float(x), 7) for x in row] for row in L.T],             # 3x4 rows
        "residual": None if rmax < 1e-4 else [[round(float(x), 6) for x in r] for r in R],
        "residual_rel_max": round(rmax, 5),
        "trs": trs,
        "materials": [MAT_OVERRIDE.get(d.get("prefab"), m) for m in host_mats] or [MAT_OVERRIDE.get(d.get("prefab"))],
        "looks": looks,
        "skin": skin,
        "subdiv": subdiv,
        "material": p.get("material") if CFG["fmt"] == "A" else (p["source"].get("material") if isinstance(p["source"], dict) else None),
    })
    report["ok"].append(name)

os.makedirs(OUT, exist_ok=True)
json.dump({"_about": "BlightedHeart runtime sub-boss kit (compiled from the approved scene by kit_tools/compile_runtime_kit.py). "
                     "Per part: v_bone = L (3x4) * v_vanilla_mesh_local + residual[i]; mesh found at runtime by name + vertex count.",
           "id": CFG["id"], "donor": CFG["donor"], "hide_renderers": CFG["hide"], "parts": parts},
          open(os.path.join(OUT, CFG["id"] + ".json"), "w"))
print("REPORT", json.dumps({k: (len(v), v[:6]) for k, v in report.items()}))
