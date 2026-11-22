"""make_rootstalker_kitbash.py - ASSET-002 Rootstalker KITBASHED from vanilla parts onto the real vanilla Wolf, with the Brute's
method (derived from make_brute_kitbash.py v6, 2026-11-22): conformed Hive lumps (per-vertex offsets = our data), the Wolf's own
texture repainted in its UV space (masks + recipe), amber slit eyes (eye_globe + our baked mask), the Elder's bare branches, and
the WTF: a second jaw opening in the throat, lined with the Wolf's OWN teeth rows and canines.

  heavy.sh 4G sb-wolf blender -b --factory-startup -P make_rootstalker_kitbash.py -- <ASSET-002 dir>
"""
import bpy, bmesh, sys, os, math, json, random, time
from mathutils import Vector, Matrix
from mathutils.bvhtree import BVHTree
import numpy as np

ASSET = sys.argv[sys.argv.index("--") + 1].rstrip("/")
SUB = os.path.dirname(ASSET)
sys.path.insert(0, os.path.join(SUB, "kit_tools")); sys.path.insert(0, os.path.join(SUB, "tools_001-003"))
import donor_base as DB, vanilla_kit as VK, hive_kit as hk
V = Vector
KIT = os.path.join(ASSET, "kit"); PREV = os.path.join(KIT, "previews")
REF = os.path.join(SUB, "ASSET-001_HiveBrute", "kit", "vanilla_ref")        # the shared vanilla-parts reference (game data, not shipped)
os.makedirs(PREV, exist_ok=True)
T0 = time.time()
SEED = 5001
CLEAR = 0.0015
rng = random.Random(SEED)

bpy.ops.wm.read_factory_settings(use_empty=True)
D = DB.Donor(ASSET, os.path.join(KIT, "ref"))
BODY, BVS, BFS = DB.base_bvh(D, ("M",))
HAIR = BVHTree.FromPolygons([(0, 0, -50), (0.01, 0, -50), (0, 0.01, -50)], [(0, 1, 2)])     # the Wolf has no Hair renderer
BP = D.bone_pos_b
P = VK.Parts(REF, os.path.join(SUB, "reference"))
TRIS_BODY, TRIS_HAIR = len(D.mesh_data("M")[1]), 0

# ---------------------------------------------------------------- the vanilla meshes (shared datablocks)
K_LUMP, K_EYE = "TheHive__TheHive_Visual_low", "eye_globe__eye_globe_default"
K_SACK, K_ROOT = "GuckSack__GuckSack_sack", "HugeRoot1__HugeRoot1_root1_low"
KEYS = {"lump": K_LUMP, "eye": K_EYE, "sack": K_SACK, "root": K_ROOT, "jaw": "hugeskull__hugeskull_jaw",
        "vineh": "vines__vines_New_high", "vinel": "vines__vines_New_low", "thorn": "ThornRoots__ThornRoots_Cube",
        "tenta": "Tentaroots__Tentaroots_Cube", "writhan": "writhanroots__writhanroots_default", "root07": "root07__root07_root07"}
ME = {}
for k, key in KEYS.items():
    ME[k] = P.mesh(key, prefab_space=False, name=k)
hm = ME["lump"].materials[0]
for _nd in hm.node_tree.nodes:                     # STEP 3: moss on the crust at half strength (recipe _MossAlpha 0.5)
    if _nd.type == 'MAP_RANGE':
        _nd.inputs[4].default_value = 0.5
VC = {}


def vc_multiply(mat):
    """material x vertex colour 'Col' (the runtime equivalent: mesh.colors + a vertex-colour-aware shader, or a baked texture copy)"""
    b = mat.node_tree.nodes["Principled BSDF"]
    ca = mat.node_tree.nodes.new("ShaderNodeAttribute"); ca.attribute_type = 'GEOMETRY'; ca.attribute_name = "Col"
    mx = mat.node_tree.nodes.new("ShaderNodeMix"); mx.data_type = 'RGBA'; mx.blend_type = 'MULTIPLY'; mx.inputs[0].default_value = 1.0
    if b.inputs["Base Color"].links:
        mat.node_tree.links.new(b.inputs["Base Color"].links[0].from_socket, mx.inputs[6])
    else:
        mx.inputs[6].default_value = b.inputs["Base Color"].default_value
    mat.node_tree.links.new(ca.outputs["Color"], mx.inputs[7]); mat.node_tree.links.new(mx.outputs[2], b.inputs["Base Color"])
    return mat


def set_vc(me, cols, key):
    ca = me.color_attributes.get("Col") or me.color_attributes.new("Col", 'FLOAT_COLOR', 'POINT')
    for i, c in enumerate(cols):
        ca.data[i].color = (*c, 1.0)
    VC[key] = [[round(x, 3) for x in c] for c in cols]
hm.node_tree.nodes["Principled BSDF"].inputs["Emission Strength"].default_value = 0.0   # see README: emissive mask left off
ME["eye"].materials.clear(); ME["eye"].materials.append(P.hive_material("TheHive_Eye"))
ME["cube"] = VK.builtin_cube("Cube_builtin", P.hive_material("TheHive_Mat_legs"))
bpy.ops.mesh.primitive_uv_sphere_add(segments=24, ring_count=17, radius=0.5)   # Unity's built-in Sphere: 768 tris (the Hive's EYE)
_e = bpy.context.active_object; ME["sphere"] = _e.data; bpy.data.objects.remove(_e)
ME["sphere"].materials.append(P.hive_material("TheHive_Eye"))
for _p in ME["sphere"].polygons:
    _p.use_smooth = True
def eye_material():
    """TheHive_Eye as a textured orb: base = its texture x _Color, emission = its texture x _EmissionColor's hue, strength
    falling off from a bright core (facing the viewer) to a darker rim. Flat pink came from a flat emission swamping the texture."""
    hj = json.load(open(os.path.join(SUB, "reference", "hive.json")))["materials"]["TheHive_Eye"]
    m = bpy.data.materials.new("V_TheHive_Eye_core"); m.use_nodes = True
    nt = m.node_tree; b_ = nt.nodes["Principled BSDF"]
    ti = nt.nodes.new("ShaderNodeTexImage"); ti.image = bpy.data.images.load(os.path.join(SUB, "reference", hj["textures"]["_MainTex"]))
    col = hj["colors"].get("_Color", [1, 1, 1, 1]); em = hj["colors"].get("_EmissionColor", [1.43, 0, 0.1, 1])
    mul = nt.nodes.new("ShaderNodeMix"); mul.data_type = 'RGBA'; mul.blend_type = 'MULTIPLY'; mul.inputs[0].default_value = 1.0
    nt.links.new(ti.outputs["Color"], mul.inputs[6]); mul.inputs[7].default_value = (*[0.3 * DB.srgb2lin(c) for c in col[:3]], 1)
    nt.links.new(mul.outputs[2], b_.inputs["Base Color"])
    s_ = max(em[:3])
    eme = nt.nodes.new("ShaderNodeMix"); eme.data_type = 'RGBA'; eme.blend_type = 'MULTIPLY'; eme.inputs[0].default_value = 1.0
    nt.links.new(ti.outputs["Color"], eme.inputs[6]); eme.inputs[7].default_value = (1.0, 0.28, 0.04, 1)     # amber-red iris glow
    nt.links.new(eme.outputs[2], b_.inputs["Emission Color"])
    # v5: the emission core and a dark vertical SLIT PUPIL are baked into a mask in eye_globe's own UVs (our data, shipped as the
    # eye material's _EmissionMap + a darkening of _MainTex): R = emission core (fixed to the eye's outward axis, local +z),
    # G = pupil. Built by rasterising the eye's UV triangles with their local positions.
    import troll_repaint as TR_
    em_ = ME["eye"]; em_.calc_loop_triangles()
    uvl_ = em_.uv_layers[0].data
    Vl, UVl, Fl = [], [], []
    for lt in em_.loop_triangles:
        for li in lt.loops:
            Vl.append(tuple(em_.vertices[em_.loops[li].vertex_index].co)); UVl.append(tuple(uvl_[li].uv))
        Fl.append((len(Vl) - 3, len(Vl) - 2, len(Vl) - 1))
    vs_ = [v.co for v in em_.vertices]; cen = np.array((sum(vs_, V()) / len(vs_))[:])
    ES = 256
    epos, _ = TR_.raster_position_map(Vl, Fl, UVl, ES)
    ev = ~np.isnan(epos[..., 0])
    nn = epos[ev] - cen; nn /= np.linalg.norm(nn, axis=1, keepdims=True)
    core = np.clip(nn[:, 2], 0, 1) ** 5
    pupil = TR_.smoothstep(0.07, 0.03, np.abs(nn[:, 0])) * TR_.smoothstep(0.35, 0.65, nn[:, 2])
    EMK = np.zeros((ES, ES, 4)); EMK[..., 3] = 1
    EMK[..., 0][ev] = core * (1 - pupil); EMK[..., 1][ev] = pupil
    EMK = TR_.dilate_fill(EMK, ev, 4)
    os.makedirs(os.path.join(KIT, "eye"), exist_ok=True)
    hk.save_array(os.path.join(KIT, "eye", "eye_globe_core_pupil_mask.png"), EMK)
    mk = nt.nodes.new("ShaderNodeTexImage"); mk.image = bpy.data.images.load(os.path.join(KIT, "eye", "eye_globe_core_pupil_mask.png"))
    mk.image.colorspace_settings.name = 'Non-Color'
    sep = nt.nodes.new("ShaderNodeSeparateColor"); nt.links.new(mk.outputs["Color"], sep.inputs[0])
    st = nt.nodes.new("ShaderNodeMath"); st.operation = 'MULTIPLY'; st.inputs[1].default_value = 7.0 * s_
    nt.links.new(sep.outputs[0], st.inputs[0]); nt.links.new(st.outputs[0], b_.inputs["Emission Strength"])
    # wet, darker base, near-black in the pupil
    pd = nt.nodes.new("ShaderNodeMath"); pd.operation = 'MULTIPLY_ADD'; pd.inputs[1].default_value = -0.92; pd.inputs[2].default_value = 1.0
    nt.links.new(sep.outputs[1], pd.inputs[0])
    dk = nt.nodes.new("ShaderNodeMix"); dk.data_type = 'RGBA'; dk.blend_type = 'MULTIPLY'; dk.inputs[0].default_value = 1.0
    nt.links.new(mul.outputs[2], dk.inputs[6]); nt.links.new(pd.outputs[0], dk.inputs[7])
    nt.links.new(dk.outputs[2], b_.inputs["Base Color"])
    mul.inputs[7].default_value = (*[0.18 * DB.srgb2lin(c) for c in col[:3]], 1)
    b_.inputs["Coat Weight"].default_value = 0.6; b_.inputs["Coat Roughness"].default_value = 0.05
    b_.inputs["Roughness"].default_value = 0.12
    return m


ME["eye"].materials.clear(); ME["eye"].materials.append(eye_material())
ROOT_TINT = 0.35          # instance tint on the root materials (the runtime sets _Color on our material copy, like Runic's)
for k in ("root07", "thorn"):
    mcopy = ME[k].materials[0].copy(); mcopy.name = ME[k].materials[0].name + "_dark"
    for nd in mcopy.node_tree.nodes:
        if nd.type == 'MIX' and getattr(nd, "blend_type", "") == 'MULTIPLY' and nd.inputs[7].default_value[0] > 0.2:
            c_ = nd.inputs[7].default_value
            nd.inputs[7].default_value = (c_[0] * ROOT_TINT, c_[1] * ROOT_TINT, c_[2] * ROOT_TINT, 1)
    bnd = mcopy.node_tree.nodes["Principled BSDF"]
    bnd.inputs["Emission Strength"].default_value = bnd.inputs["Emission Strength"].default_value * 0.25
    ME[k].materials[0] = mcopy
bm_ = ME["jaw"].materials[0].copy(); bm_.name = "V_hugeskull_bone_teeth"
_bb = bm_.node_tree.nodes["Principled BSDF"]; _TB = (0.42, 0.33, 0.19)          # yellowed, dirty bone
if _bb.inputs["Base Color"].links:
    _lk = _bb.inputs["Base Color"].links[0]
    _tm = bm_.node_tree.nodes.new("ShaderNodeMix"); _tm.data_type = 'RGBA'; _tm.blend_type = 'MULTIPLY'; _tm.inputs[0].default_value = 1.0
    bm_.node_tree.links.new(_lk.from_socket, _tm.inputs[6]); _tm.inputs[7].default_value = (*_TB, 1)
    bm_.node_tree.links.new(_tm.outputs[2], _bb.inputs["Base Color"])
else:
    _c = _bb.inputs["Base Color"].default_value; _bb.inputs["Base Color"].default_value = (_c[0] * _TB[0], _c[1] * _TB[1], _c[2] * _TB[2], 1)
ME["tooth"] = ME["cube"].copy(); ME["tooth"].name = "Cube_builtin_tooth"; ME["tooth"].materials[0] = bm_
sm_ = ME["sack"].materials[0]; nts = sm_.node_tree; bs_ = nts.nodes["Principled BSDF"]
for nd in nts.nodes:
    if nd.type == 'TEX_IMAGE':
        gm = nts.nodes.new("ShaderNodeMix"); gm.data_type = 'RGBA'; gm.blend_type = 'MULTIPLY'; gm.inputs[0].default_value = 1.0
        nts.links.new(nd.outputs["Color"], gm.inputs[6]); gm.inputs[7].default_value = (0.25, 1.0, 0.06, 1)
        nts.links.new(gm.outputs[2], bs_.inputs["Emission Color"]); bs_.inputs["Emission Strength"].default_value = 2.5
        break
import island_parts as IP


def wolf_teeth():
    """the Wolf M mesh's loose islands in the mouth: 4 teeth ROWS (35 / 42 tris, 16-19 cm arcs) and 4 canines (12 / 21 tris,
    4 cm); each put in its canonical frame (root at origin, root->tip +z). Returns {kind: [(tris, mesh, length)]}"""
    Vb_, Fb_, UV_, _ = D.mesh_data("M")
    Vn = np.array([tuple(v) for v in Vb_])
    comp = IP.islands(Vn, Fb_)
    out = {"wrow": [], "wcanine": []}
    for tris in comp.values():
        vi = sorted({i for t in tris for i in Fb_[t]}); P_ = Vn[vi]; cen = P_.mean(0)
        if not (cen[1] > 1.0 and cen[2] > 0.9):
            continue
        if len(tris) in (35, 42):
            kind = "wrow"
        elif len(tris) in (12, 21):
            kind = "wcanine"
        else:
            continue
        root, Rm, L = IP.canonical_frame(P_)
        remap = {old: new for new, old in enumerate(vi)}
        me = bpy.data.meshes.new(f"Wolf_{kind}")
        me.from_pydata([tuple(Rm @ (Vn[i] - root)) for i in vi], [], [tuple(remap[i] for i in Fb_[t]) for t in tris])
        uvl = me.uv_layers.new(name="UV0")
        for loop in me.loops:
            uvl.data[loop.index].uv = tuple(UV_[vi[loop.vertex_index]])
        for pg in me.polygons:
            pg.use_smooth = True
        out[kind].append((tris, me, L))
    return out


def fang_grad_vc(me, L, key):
    cols = []
    for v in me.vertices:
        t = min(1.0, max(0.0, (v.co.z / max(L, 1e-6) - 0.05) / 0.7)); t = t * t * (3 - 2 * t)
        cols.append([0.07 + 0.93 * t, 0.055 + 0.945 * t, 0.035 + 0.965 * t])
    set_vc(me, cols, key)


def fang_grad(L):
    """bone material with a root-to-tip gradient (canonical z): dark dirty brown at the root, pale at the tip (runtime: vertex colours,
    our data)"""
    m = bm_.copy(); m.name = f"V_fang_gradient_{L:.3f}"
    nt = m.node_tree; b_ = nt.nodes["Principled BSDF"]
    tc = nt.nodes.new("ShaderNodeTexCoord"); sp = nt.nodes.new("ShaderNodeSeparateXYZ"); nt.links.new(tc.outputs["Object"], sp.inputs[0])
    mr = nt.nodes.new("ShaderNodeMapRange"); mr.inputs["From Min"].default_value = 0.0; mr.inputs["From Max"].default_value = L
    nt.links.new(sp.outputs["Z"], mr.inputs["Value"])
    cr = nt.nodes.new("ShaderNodeMix"); cr.data_type = 'RGBA'; cr.inputs[6].default_value = (0.06, 0.045, 0.03, 1); cr.inputs[7].default_value = (0.86, 0.8, 0.66, 1)
    nt.links.new(mr.outputs["Result"], cr.inputs[0]); nt.links.new(cr.outputs[2], b_.inputs["Base Color"])
    b_.inputs["Roughness"].default_value = 0.35
    return m


ISL = wolf_teeth()
CANINE_MAT = vc_multiply(bm_.copy()); CANINE_MAT.name = "V_canine_bone_vc"
CANINE_MAT.node_tree.nodes["Principled BSDF"].inputs["Roughness"].default_value = 0.35
fang_mat = DB.base_material(D, name="WolfFang_dirty", tint=(0.85, 0.74, 0.52))   # instance tint on a copy of the Wolf material
GUM_MAT = vc_multiply(fang_mat.copy()); GUM_MAT.name = "WolfGum_depth_vc"          # STEP 3: the gum rows get painted depth (vertex colours)
for kind, lst in ISL.items():
    for i, (tris, me, L_) in enumerate(lst):
        if kind == "wrow":
            me.materials.append(GUM_MAT)
        else:
            me.materials.append(CANINE_MAT); fang_grad_vc(me, L_, f"{kind}{i}")      # STEP 3: dirty root -> pale tip as vertex colours
        ME[f"{kind}{i}"] = me
print("FANG ISLANDS", {k: [(len(t), round(L_, 3)) for t, _, L_ in v] for k, v in ISL.items()})
BRANCH_SRC = {}
_bi = json.load(open(os.path.join(SUB, "kit_tools", "branch_parts_index.json")))
for n, cell in enumerate((5, 6, 7)):              # Elder islands 4, 5, 6 (sheet cells 5-7): bent limbs with SHORT forks
    e = _bi[cell - 1]
    me, info = IP.island_mesh(P, e["key"], e["tris"], f"branch{n}")
    bm2 = me.materials[0].copy(); bm2.name = "V_Elder_branch_weathered"
    for nd in bm2.node_tree.nodes:
        if nd.type == 'MIX' and getattr(nd, "blend_type", "") == 'MULTIPLY':
            nd.inputs[7].default_value = (0.17, 0.145, 0.115, 1)      # STEP 3: weathered grey-brown (after the desaturation below)
            hs = bm2.node_tree.nodes.new("ShaderNodeHueSaturation"); hs.inputs["Saturation"].default_value = 0.2
            lk = nd.inputs[6].links[0]; bm2.node_tree.links.new(lk.from_socket, hs.inputs["Color"])
            bm2.node_tree.links.new(hs.outputs["Color"], nd.inputs[6])     # the Elder's pink pulled out (desaturated to 20 %)
    _bb = bm2.node_tree.nodes["Principled BSDF"]; _bb.inputs["Roughness"].default_value = 0.85; _bb.inputs["Emission Strength"].default_value = 0.0
    me.materials[0] = bm2
    ME[f"branch{n}"] = me
    BRANCH_SRC[f"branch{n}"] = {"prefab": "gd_king", "renderer": "/gd_king/Visual/gd_king", "mesh": f"gd_king.001 island (sheet cell {cell})",
                                "triangles": e["tris"], "material": "Elder_mat; recolour recipe: saturation x0.2, then x(0.17, 0.145, 0.115) - weathered grey-brown, the pink pulled out; emission off",
                                "scale_note": "placed with x/y scale 2.4x the length scale (thick limbs)",
                                "frame": "root at origin, root->tip +z (computed from the island)", "length_m_in_elder": round(info["length"], 3)}
SRC = {}
SRC.update(BRANCH_SRC)
for kind, lst in ISL.items():
    for i, (tris, me, L_) in enumerate(lst):
        SRC[f"{kind}{i}"] = {"prefab": "Wolf", "renderer": "M", "mesh": f"Wolf M island ({kind}): {len(tris)} triangles",
                             "triangles": tris, "material": "the Wolf's own material, instance tint (0.85, 0.74, 0.52)",
                             "frame": "root at origin, root->tip +z, bulge +y (computed from the island, deterministic)"}
for k, key in KEYS.items():
    dd = P.data(key)
    SRC[k] = {"prefab": dd["prefab"], "renderer": dd["renderer_path"], "mesh": dd["mesh"], "mesh_path_id": dd["mesh_path_id"],
              "material": ", ".join(m["name"] for m in dd["materials"])}
SRC["eye"]["material"] = "TheHive_Eye (from TheHive /Visual/EYE)"
SRC["sphere"] = {"prefab": "TheHive", "renderer": "/TheHive/Visual/EYE", "mesh": "built-in Sphere (unity default resources, 768 tris)",
                 "material": "TheHive_Eye"}
SRC["cube"] = {"prefab": "TheHive", "renderer": "/TheHive/Visual/Cube (4)", "mesh": "built-in Cube (unity default resources)",
               "material": "TheHive_Mat_legs"}


def local_box(me):
    co = np.array([v.co[:] for v in me.vertices]); return co.min(0), co.max(0)


BOX = {k: local_box(m) for k, m in ME.items()}


def anchor_pt(k, where):
    lo, hi = BOX[k]; c = (lo + hi) / 2
    if where == "center":
        return V(c.tolist())
    if where == "base":                       # bottom centre along local z (dome base)
        return V((c[0], c[1], lo[2]))
    if where == "top":                        # top centre along local z (hanging vines)
        return V((c[0], c[1], hi[2]))
    if where == "origin":
        return V((0, 0, 0))
    if where == "y_min":                      # the end at local -y (a strand's root end)
        return V((c[0], lo[1], c[2]))
    raise ValueError(where)


def R_axes(x_dir, z_dir):
    """rotation whose local z = z_dir and local x = x_dir (orthogonalised), right-handed"""
    z = V(z_dir).normalized()
    x = V(x_dir) - z * V(x_dir).dot(z); x.normalize()
    y = z.cross(x)
    return Matrix((x, y, z)).transposed().to_4x4()


def R_from(z_axis, y_hint):
    z = V(z_axis).normalized()
    y = V(y_hint) - z * V(y_hint).dot(z)
    if y.length < 1e-6:
        y = V((0, 1, 0)) if abs(z.y) < 0.9 else V((1, 0, 0))
        y = y - z * y.dot(z)
    y.normalize(); x = y.cross(z).normalized()
    return Matrix((x, y, z)).transposed().to_4x4()


ALIGN = {k: Matrix.Identity(4) for k in list(ME) + ["sphere"]}
ALIGN["sack"] = Matrix.Rotation(-math.pi / 2, 4, 'X')   # the sack's height (local z) -> local y (vertical in the frames used)
PARTS = []


def world_verts(ob):
    M = ob.matrix_world
    return [M @ v.co for v in ob.data.vertices], [tuple(p.vertices) for p in ob.data.polygons]


def overlaps(ob, bvh=BODY):
    vs, fs = world_verts(ob)
    return len(BVHTree.FromPolygons(vs, fs).overlap(bvh))


def inside(pt):
    """ray parity against the Troll body: is the point inside it?"""
    n, o, dd = 0, V(pt), V((0.123, 0.456, 0.88)).normalized()
    for _ in range(40):
        h = BODY.ray_cast(o, dd, 50)
        if h[0] is None:
            break
        n += 1; o = h[0] + dd * 1e-4
    return n % 2 == 1


def seat(ob, d, hi=0.6, clear=CLEAR):
    """move ob along d to the first position (from outside) where it no longer cuts the Body, + clear. The search starts
    at the placed position: if it cuts there, bisect outward; if not, walk inward in 2 cm steps until it first touches
    (so thin limbs are never passed straight through)"""
    d = V(d).normalized()
    M0 = ob.matrix_world.copy()
    vs0, fs = world_verts(ob)
    def cut(t):
        return bool(BVHTree.FromPolygons([v + d * t for v in vs0], fs).overlap(BODY))
    lo = 0.0
    if not cut(0.0) and inside(sum(vs0, V()) / len(vs0)):
        # the whole part starts INSIDE the Troll (its ray hit another limb): walk it out until it cuts, then bisect outward
        t = 0.0
        while t < 0.8 and not cut(t):
            t += 0.005
        if not cut(t):
            print("SEAT inside, never reaches the skin", ob.name); return None
        lo = t
    elif not cut(0.0):
        t = 0.0
        while t > -0.4 and not cut(t):
            t -= 0.005
        if not cut(t):
            print("SEAT never touches", ob.name); return None
        lo, hi = t, t + 0.005
    elif cut(hi):
        print("SEAT still cutting at hi", ob.name); return None
    for _ in range(16):
        mid = (lo + hi) / 2
        if cut(mid):
            lo = mid
        else:
            hi = mid
    ob.matrix_world = Matrix.Translation(d * (hi + clear)) @ M0      # matrix_world directly (location would stay stale)
    return hi + clear


def place(name, k, bone, loc, z_axis, y_hint, scale, at="center", seat_dir=None, spin=0.0, do_seat=True, R=None):
    ob = bpy.data.objects.new("RS_" + name, ME[k])
    bpy.context.scene.collection.objects.link(ob)
    if R is None:
        R = R_from(z_axis, y_hint) @ Matrix.Rotation(spin, 4, 'Z') @ ALIGN[k]
    S = Matrix.Diagonal((*scale, 1.0))
    a = anchor_pt(k, at)
    ob.matrix_world = Matrix.Translation(V(loc)) @ R @ S @ Matrix.Translation(-a)
    moved = seat(ob, seat_dir or z_axis) if do_seat else 0.0
    if do_seat and moved is None:
        print("NOT SEATED", name)
    PARTS.append({"name": name, "k": k, "bone": bone, "ob": ob, "seat": moved})
    return ob


def surf(target, out_dir, bvh=BODY):
    d = V(out_dir).normalized()
    loc, n, _, _ = bvh.ray_cast(V(target) + d * 25, -d, 60)
    return loc, n


def ob_bvh(*obs):
    vs, fs = [], []
    for ob in obs:
        v_, f_ = world_verts(ob); o = len(vs); vs += v_; fs += [tuple(i + o for i in f) for f in f_]
    return BVHTree.FromPolygons(vs, fs)


def far_poke(ob, d):
    """vertices that came out of the FAR side of the Troll (outside the body, nearest skin facing away from the entry direction,
    deeper than the part's centre)"""
    vs, _ = world_verts(ob)
    c = sum(vs, V()) / len(vs)
    n = 0
    for v in vs:
        if inside(v):
            continue
        loc, nrm, _, dist = BODY.find_nearest(v)
        if nrm.dot(d) < -0.3 and (v - c).dot(d) < 0 and dist < 0.15:
            n += 1
    return n


def sink_part(ob, d, frac):
    """push a seated part `frac` of its own depth (along d) INTO the Troll, so the bark grows out of the flesh; back off if it would
    poke out of the far side"""
    d = V(d).normalized()
    SINKDIR[ob.name] = d
    vs, _ = world_verts(ob)
    pr = [v.dot(d) for v in vs]
    ext = max(pr) - min(pr)
    M0 = ob.matrix_world.copy()
    for f in (frac, frac * 0.6, frac * 0.3):
        ob.matrix_world = Matrix.Translation(-d * ext * f) @ M0
        if far_poke(ob, d) == 0:
            return round(f, 3)
    ob.matrix_world = M0
    return 0.0


SUNK = {}
SINKDIR = {}
OFFSETS = {}
CONFORM = True


def _ss(e0, e1, x):
    t = min(1.0, max(0.0, (x - e0) / (e1 - e0))); return t * t * (3 - 2 * t)


UV_OFFSETS = {}


def uv_reproject(ob, offs):
    """STEP 3: per-vertex UV0 offsets dUV = J . dP (smoothed, clamped) so the bark keeps its texel density on the spread flanks"""
    me = ob.data
    uvl = me.uv_layers[0].data
    P1 = [v.co.copy() for v in me.vertices]
    P0 = [p - o for p, o in zip(P1, offs)]
    UV = [None] * len(me.vertices)
    for lp in me.loops:
        if UV[lp.vertex_index] is None:
            UV[lp.vertex_index] = uvl[lp.index].uv.copy()
    Jsum = [np.zeros((2, 3)) for _ in me.vertices]; cnt = [0] * len(me.vertices)
    for pg in me.polygons:
        vs = list(pg.vertices)
        for k in range(1, len(vs) - 1):
            a, b, c = vs[0], vs[k], vs[k + 1]
            e1 = np.array((P0[b] - P0[a])[:]); e2 = np.array((P0[c] - P0[a])[:]); n = np.cross(e1, e2)
            if np.linalg.norm(n) < 1e-12:
                continue
            n /= np.linalg.norm(n)
            d1 = np.array((UV[b] - UV[a])[:]); d2 = np.array((UV[c] - UV[a])[:])
            J = np.column_stack([d1, d2, [0.0, 0.0]]) @ np.linalg.inv(np.column_stack([e1, e2, n]))
            for vi in (a, b, c):
                Jsum[vi] += J; cnt[vi] += 1
    D_ = np.array([(Jsum[i] / max(cnt[i], 1)) @ np.array(offs[i][:]) for i in range(len(me.vertices))])
    nb = [[] for _ in me.vertices]
    for e in me.edges:
        a, b = e.vertices; nb[a].append(b); nb[b].append(a)
    for _ in range(6):
        D_ = np.array([0.5 * D_[i] + 0.5 * (D_[nb[i]].mean(0) if nb[i] else D_[i]) for i in range(len(D_))])
    nrm_ = np.linalg.norm(D_, axis=1, keepdims=True); D_ = D_ * np.minimum(1.0, 0.3 / np.maximum(nrm_, 1e-9))
    duv = [[round(float(d[0]), 5), round(float(d[1]), 5)] for d in D_]
    for lp in me.loops:
        d = duv[lp.vertex_index]
        uvl[lp.index].uv = (UV[lp.vertex_index][0] + d[0], UV[lp.vertex_index][1] + d[1])
    UV_OFFSETS[ob.name] = duv


def conform(ob, zdir, flat=0.45, cfrac=0.6, ridge=0.35, spread=0.7, seed=0):
    """deform a placed lump INTO a mound grown from the Troll: in the lump's frame (outward axis zdir) its lower flanks are pushed
    out along the skin (footprint up to 1+spread wider), every height above the skin is squashed by `flat` (with a ridge noise so
    it stays lumpy), and the body-facing `cfrac` of its depth is pulled onto the skin (2 cm under it) - so the flanks slope into the
    flesh and neighbouring mounds run into each other. Stored as per-vertex offsets in the vanilla mesh's own space (our data;
    the runtime adds them to a clone of the vanilla mesh)"""
    me = ob.data.copy(); me.name = ob.name + "_conformed"; ob.data = me
    M = ob.matrix_world; Mi = M.inverted(); zd = V(zdir).normalized()
    W = [M @ v.co for v in me.vertices]
    Cc = sum(W, V()) / len(W)
    pz = [w.dot(zd) for w in W]; lo, hi = min(pz), max(pz)
    r = random.Random(seed); ph = [r.uniform(0, 6.28) for _ in range(4)]
    RV = [((w - Cc) - zd * (w - Cc).dot(zd)) for w in W]
    Rfoot = max(rv.length for rv in RV) * (1 + spread)
    offs = []
    for v, w, z_ in zip(me.vertices, W, pz):
        t = (hi - z_) / max(hi - lo, 1e-6)                                     # 0 = crown, 1 = deepest
        rv = (w - Cc) - zd * (w - Cc).dot(zd)
        wt = w + rv * (spread * _ss(0.15, 1.0, t))
        s_, ns_, _, _ = BODY.find_nearest(wt)                 # wolf: true shrinkwrap onto the nearest skin (round flanks)
        h = (wt - s_).dot(ns_)
        if h > 0 and inside(wt):
            h = -h
        nz = 0.5 + 0.5 * math.sin(36.0 * w.x + ph[0]) * math.sin(30.0 * w.z + ph[1]) * math.cos(28.0 * w.y + ph[2])
        rr = min(1.0, ((wt - Cc) - zd * (wt - Cc).dot(zd)).length / Rfoot)
        prof = (1 - rr * rr) ** 0.6                                            # dome envelope: flanks slope to the skin, no ledges
        hp = h * (flat + ridge * (nz - 0.5)) * prof if h > 0 else h
        c = _ss(1.0 - cfrac, 1.0, t)
        hp = hp * (1 - c) + (-0.006) * c
        nw = s_ + ns_ * hp
        nl = Mi @ nw
        offs.append(nl - v.co); v.co = nl
    me.update()
    OFFSETS[ob.name] = [[round(o.x, 5), round(o.z, 5), round(o.y, 5)] for o in offs]     # Unity mesh space (x, y, z)
    uv_reproject(ob, offs)
    return ob


def lump(name, bone, target, out, s, squash=0.55, stretch=(1.0, 1.0), y_hint=(0, 0, 1), spin=None, sink=0.0, tilt=None, ray=None,
         hem=False):
    p, n = surf(target, ray or out)     # ray: the direction that FINDS the spot (default: out); out only leans the lump
    if p is None:                       # the ray missed a thin part (tail, neck side): take the nearest skin point instead
        p, n, _, _ = BODY.find_nearest(V(target)); print("LUMP RAY MISS -> nearest", name)
    z = (n + V(out).normalized()).normalized()
    ob = place(name, "lump", bone, p, z, y_hint, (s * stretch[0], s * stretch[1], s * squash),
               spin=rng.uniform(0, 6.28) if spin is None else spin)
    if sink > 0:
        SUNK[name] = sink_part(ob, z, sink)
    if CONFORM:
        if hem:                      # the hem lumps: spread thin, so the crust's edges thin out into the painted roots all round
            conform(ob, z, seed=len(OFFSETS), flat=0.28, spread=1.1)
        else:
            conform(ob, z, seed=len(OFFSETS))
    return ob


def lump_frame(ob):
    M = ob.matrix_world
    c = M @ anchor_pt("lump", "center")
    z = (M.to_3x3() @ V((0, 0, 1))).normalized()
    y = (M.to_3x3() @ V((0, 1, 0))).normalized()
    return c, z, y, z.cross(y).normalized() * -1


def eye(name, bone, lmp, du, dv, r, slit=1.0, sink=0.3, tilt=0.0):
    """an eye dome set into a lump: aimed from the lump's centre, offset du along its x and dv along its y, cast along its
    local z (out of the bark) onto the lump's own surface"""
    c, z, y, x = lump_frame(lmp)
    out = (z + y * tilt).normalized()
    bv = ob_bvh(lmp)
    loc, n = surf(c + x * du + y * dv, out, bv)
    if loc is None:
        print("EYE MISS", name); return None
    lo, hi = BOX["eye"]; w = hi[0] - lo[0]; h = hi[2] - lo[2]
    s = 2 * r / w
    return place(name, "eye", bone, loc - n * (sink * h * s), n, (0, 0, 1), (s, s * slit, s * 0.9), at="base", do_seat=False)


# ---------------------------------------------------------------- the kitbash: the Hive grown INTO the Wolf (Brute method, wolf scale)
# Blender frame: x = right, y = the Wolf's forward, z = up; feet on z = 0. The crust runs over the withers, along the spine and
# over the haunches; small spread-thin HEM lumps all the way round thin its edges into the painted roots (front, sides and back).
def crust(name, bone, target, s, out=(0, 0, 1), ray=(0, 0, 1), hem=False, sink=0.3, stretch=(1.0, 1.0), squash=0.62):
    return lump(name, bone, target, out, s * (1.0 if hem else 0.85), squash=squash, stretch=stretch, y_hint=(0, 1, 0), sink=sink, ray=ray,
                hem=hem)


CR = {}
for nm, bone, tgt, s_, out, ray, st in (
        ("crust_withers_l", "Spine2", (-0.07, 0.24, 0.9), 0.16, (-0.3, 0.1, 1), (0, 0, 1), (1.0, 1.25)),
        ("crust_withers_r", "Spine2", (0.08, 0.13, 0.9), 0.13, (0.3, 0.0, 1), (0, 0, 1), (1.0, 1.1)),
        ("crust_shoulder_l", "Spine2", (-0.2, 0.26, 0.98), 0.12, (-1, 0.1, 0.5), (-1, 0, 0.4), (1.0, 1.0)),
        ("crust_shoulder_r", "Spine2", (0.21, 0.2, 0.96), 0.09, (1, 0.0, 0.4), (1, 0, 0.4), (1.0, 1.0)),
        ("crust_neck", "Neck", (-0.02, 0.45, 0.9), 0.11, (-0.1, 0.4, 1), (0, 0, 1), (1.0, 1.2)),
        ("crust_spine_a", "Spine1", (-0.04, -0.02, 0.9), 0.13, (-0.1, 0, 1), (0, 0, 1), (1.0, 1.3)),
        ("crust_spine_b", "Spine1", (0.05, -0.22, 0.9), 0.11, (0.1, 0, 1), (0, 0, 1), (1.0, 1.2)),
        ("crust_spine_c", "Spine", (-0.03, -0.4, 0.9), 0.13, (-0.1, 0, 1), (0, 0, 1), (1.0, 1.2)),
        ("crust_haunch_l", "Pelvis", (-0.12, -0.6, 0.9), 0.16, (-0.5, -0.2, 1), (0, 0, 1), (1.0, 1.0)),
        ("crust_haunch_r", "Pelvis", (0.12, -0.64, 0.9), 0.12, (0.5, -0.2, 1), (0, 0, 1), (1.0, 1.0)),
        ("crust_thigh_l", "L Thigh", (-0.25, -0.56, 0.85), 0.11, (-1, -0.2, 0.3), (-1, 0, 0.3), (1.0, 1.0)),
        ("crust_tailbase", "Tail", (0.0, -0.8, 0.9), 0.08, (0, -0.5, 1), (0, 0, 1), (1.0, 1.2)),
        ("crust_skull", "Head", (0.0, 0.76, 1.0), 0.07, (0, 0.2, 1), (0, 0, 1), (1.0, 1.3))):
    CR[nm] = crust(nm, bone, tgt, s_, out=out, ray=ray, stretch=st)
for nm, bone, tgt, s_, ray in (
        ("hem_shoulder_l", "Spine2", (-0.24, 0.12, 0.92), 0.075, (-1, 0, 0.2)),
        ("hem_shoulder_r", "Spine2", (0.24, 0.05, 0.92), 0.07, (1, 0, 0.2)),
        ("hem_ribs_l", "Spine1", (-0.2, -0.18, 0.95), 0.07, (-1, 0, 0.3)),
        ("hem_ribs_r", "Spine1", (0.19, -0.33, 0.95), 0.065, (1, 0, 0.3)),
        ("hem_haunch_l", "Pelvis", (-0.24, -0.72, 0.85), 0.07, (-1, 0, 0.2)),
        ("hem_haunch_r", "Pelvis", (0.26, -0.6, 0.8), 0.065, (1, 0, 0.2)),
        ("hem_neck_r", "Neck", (0.1, 0.52, 1.0), 0.06, (1, 0.3, 0.5)),
        ("hem_neck_l", "Neck", (-0.11, 0.42, 1.0), 0.06, (-1, 0.2, 0.5)),
        ("hem_tail", "Tail", (0.04, -0.92, 0.9), 0.055, (0, 0, 1))):
    CR[nm] = crust(nm, bone, tgt, s_, out=ray, ray=ray, hem=True, stretch=(1.2, 1.0))

# ---------------------------------------------------------------- THE WTF: a second jaw opening in the THROAT (Neck): a vertical slit
# down the throat front under the head, two sunk lips curling out, the Wolf's own teeth ROWS lining both edges and its canines at the
# corners, a glowing gullet sack deep inside (and the repaint's dark slit + glowing core)
MAW_H = 0.4
MAW_RAY = (0, 1, -0.12)
ml, mn = surf((0, 0.45, 0.8), MAW_RAY)          # v4b: lower, on the forechest below the head, so it faces the viewer
print("MAW at", tuple(round(c, 3) for c in ml), "normal", tuple(round(c, 2) for c in mn))
CONFORM = False
LIPS = []
for s_ in (-1, 1):
    LIPS.append(lump(f"maw_lip_{'l' if s_ < 0 else 'r'}", "Neck", (0.105 * s_, ml.y, ml.z), (0.6 * s_, 1, -0.3), 0.055,
                     squash=0.62, stretch=(0.55, 1.8), y_hint=(0, 0, 1), spin=0.0, sink=0.22, ray=MAW_RAY))
CONFORM = True
LIP_MAT = None
for lp in LIPS:                          # STEP 3: inner-edge darkening as VERTEX COLOURS (world |x| from the slit centre line)
    lp.data = lp.data.copy()
    if LIP_MAT is None:
        LIP_MAT = vc_multiply(lp.data.materials[0].copy()); LIP_MAT.name = "V_TheHive_lip_vc"
    lp.data.materials[0] = LIP_MAT
    cols = []
    for v in lp.data.vertices:
        w = lp.matrix_world @ v.co
        t = min(1.0, max(0.0, (abs(w.x - ml.x) - 0.03) / 0.055)); t = t * t * (3 - 2 * t)
        f = 0.18 + 0.82 * t; cols.append([f, f * 0.95, f * 0.92])
    set_vc(lp.data, cols, lp.name.replace("RS_", ""))
SACK = place("maw_gullet_sack", "sack", "Neck", ml + mn * 0.004, mn, (0, 0, 1), (0.045, 0.045, 0.1))
SUNK["maw_gullet_sack"] = sink_part(SACK, mn, 0.85)       # deep inside
ROWS = [k for k in ME if k.startswith("wrow")]; CAN = [k for k in ME if k.startswith("wcanine")]
up = (V((0, 0, 1)) - mn * mn.z).normalized()
for i, (s_, lip) in enumerate(((-1, LIPS[0]), (1, LIPS[1]))):
    inner = V((-s_, 0, 0))
    for j, k in enumerate(ROWS[i * 2:i * 2 + 2] or ROWS[:2]):
        lo_, hi_ = BOX[k]; Lk = hi_[2] - lo_[2]; sc = (MAW_H * (0.75 if j else 0.95)) / Lk
        c0 = ml - inner * (0.07 + 0.01 * j) - up * (MAW_H * (0.45 if j else 0.5)) + mn * 0.006
        R0 = R_axes(inner * (1 if j == 0 else -1), up)
        rob = place(f"maw_row_{'lr'[i]}{j}", k, "Neck", c0, None, None, (sc, sc, sc), R=R0, at="origin", do_seat=False)
        cols = []
        for v in rob.data.vertices:
            w_ = rob.matrix_world @ v.co
            dpt = (w_ - ml).dot(mn); ax_ = abs(w_.x - ml.x)
            t = min(1.0, max(0.0, (ax_ - 0.035) / 0.05)) * min(1.0, max(0.0, (dpt + 0.04) / 0.06)); t = t * t * (3 - 2 * t)
            f = 0.06 + 0.32 * t; cols.append([f, f * 0.55, f * 0.6])         # inner (slit-side) and deep parts near-black maroon, the outer edge dark gum
        set_vc(rob.data, cols, f"maw_row_{'lr'[i]}{j} ({k})")
    for j, fz in enumerate((0.38, 0.12, -0.14, -0.38)):          # four canines per side, 9-14 cm, ragged, angled into the slit
        k = CAN[(i * 4 + j) % len(CAN)]
        lo_, hi_ = BOX[k]; Lk = hi_[2] - lo_[2]; L = (0.14, 0.1, 0.12, 0.09)[j]; sc = L / Lk
        root = ml + up * (MAW_H * fz) - inner * 0.075 + mn * 0.01
        dd = (inner + mn * 0.4 + up * (-0.3 * fz)).normalized()
        place(f"maw_canine_{'lr'[i]}{j}", k, "Neck", root - dd * L * 0.15, None, None, (sc * 1.15, sc * 1.15, sc * 1.1),
              R=R_axes(up.cross(dd).normalized(), dd), at="origin", do_seat=False)


# ---------------------------------------------------------------- EYES: amber slit eyes (eye_globe + the baked core/pupil mask) at the
# Wolf's eye scale (its own eye ~0.022 m radius; these 0.018-0.034): three down the left of the snout and two down the right
# (lopsided), plus a tight cluster of three in the crease of the withers / shoulder crust
def eye_socket(name, bone, lumps, w, r, slit=1.0, sink=0.5, out_bias=(0, 0, 0)):
    (c1, z1, _, _), (c2, z2, _, _) = lump_frame(lumps[0]), lump_frame(lumps[1])
    out = (z1 + z2 + V(out_bias)).normalized()
    bvl = ob_bvh(*lumps)
    tgt = c1.lerp(c2, w)
    hl = bvl.ray_cast(tgt + out * 5, -out, 10)
    hb = BODY.ray_cast(tgt + out * 5, -out, 10)
    on_skin = hl[0] is None or (hb[0] is not None and (hb[0] - (tgt + out * 5)).length < (hl[0] - (tgt + out * 5)).length)
    loc, n = (hb[0], hb[1]) if on_skin else (hl[0], hl[1])
    if loc is None:
        print("EYE MISS", name); return None
    lo, hi = BOX["eye"]; wd = hi[0] - lo[0]; h = hi[2] - lo[2]; sc = 2 * r / wd
    return place(name, "eye", bone, loc - n * (sink * h * sc), n, (0, 0, 1), (sc, sc * slit, sc * 0.9), at="base", do_seat=False)


def eye_skin(name, bone, target, ray, r, slit=1.0, sink=0.45):
    loc, n = surf(target, ray)
    if loc is None:
        print("EYE MISS", name); return None
    lo, hi = BOX["eye"]; wd = hi[0] - lo[0]; h = hi[2] - lo[2]; sc = 2 * r / wd
    return place(name, "eye", bone, loc - n * (sink * h * sc), n, (0, 0, 1), (sc, sc * slit, sc * 0.9), at="base", do_seat=False)


for nm, tgt, ray, r in (("eye_snout_l0", (-0.05, 0.93, 1.12), (-1, 0.15, 0.35), 0.03), ("eye_snout_l1", (-0.045, 1.0, 1.13), (-1, 0.2, 0.6), 0.022),
                        ("eye_snout_l2", (-0.04, 1.06, 1.06), (-1, 0.25, 0.25), 0.018),
                        ("eye_snout_r0", (0.05, 0.96, 1.11), (1, 0.15, 0.35), 0.026), ("eye_snout_r1", (0.04, 1.04, 1.07), (1, 0.2, 0.3), 0.019)):
    eye_skin(nm, "Head", tgt, ray, r)
for nm, pair, w, r, sl in (("eye_withers_a", ("crust_withers_l", "crust_shoulder_l"), 0.5, 0.034, 1.0),
                           ("eye_withers_b", ("crust_withers_l", "crust_neck"), 0.55, 0.024, 1.0),
                           ("eye_withers_slit", ("crust_withers_l", "crust_shoulder_l"), 0.25, 0.026, 0.4)):
    eye_socket(nm, "Spine2", [CR[pair[0]], CR[pair[1]]], w, r, slit=sl)


# ---------------------------------------------------------------- ROOTS: three thin dark catacomb roots (root07, darkened) from the crust
# edges down the shoulder, the haunch and the neck; the dense web is painted
def strand(name, k, bone, a, b, out, thick):
    pa, na = surf(a, out); pb, nb = surf(b, out)
    if pa is None or pb is None:
        print("ROOT MISS", name); return None
    ax = (pb - pa); L = ax.length; ya = ax.normalized()
    nrm = (na + nb).normalized()
    nrm = (nrm - ya * nrm.dot(ya)).normalized()
    zl, yl = ya, nrm; xl = yl.cross(zl)
    R = Matrix((xl, yl, zl)).transposed().to_4x4()
    sc = (thick * 2.2 / 1.221, thick / 0.438, L * 1.05 / 1.612)
    ob = place(name, k, bone, pa.lerp(pb, 0.5), None, None, sc, at="center", seat_dir=nrm, R=R)
    SUNK[name] = sink_part(ob, nrm, 0.45)
    return ob


for i, (bone, a, b, out, th) in enumerate((("Spine2", (-0.22, 0.3, 0.88), (-0.23, 0.33, 0.66), (-1, 0.2, 0), 0.014),
                                           ("L Thigh", (-0.25, -0.62, 0.82), (-0.24, -0.66, 0.6), (-1, 0, 0), 0.014),
                                           ("Neck", (0.12, 0.5, 1.0), (0.11, 0.62, 0.93), (1, 0.3, 0.3), 0.012))):
    strand(f"web_root07_{i:02d}", "root07", bone, a, b, out, th)


# ---------------------------------------------------------------- BRANCHES: three thick, bent Elder limbs with short forks, rooted INTO
# the spine and haunch crust, low and swept back (speed); weathered grey (the Elder's pink pulled out); rigid on the host's bone
def branch(name, k, host, d, length, spin):
    hob = bpy.data.objects["RS_" + host]
    d = V(d).normalized()
    c = sum(world_verts(hob)[0], V()) / len(hob.data.vertices)
    loc, n = surf(c, d, ob_bvh(hob))
    if loc is None:
        print("BRANCH MISS", name); return None
    lo_, hi_ = BOX[k]; sc = length / (hi_[2] - lo_[2])
    hb = next(q["bone"] for q in PARTS if q["ob"] is hob)
    return place(name, k, hb, loc - d * 0.05, None, None, (sc * 2.4, sc * 2.4, sc),
                 R=R_axes(V((1, 0, 0)) if abs(d.x) < 0.8 else V((0, 1, 0)), d) @ Matrix.Rotation(spin, 4, 'Z'), at="origin", do_seat=False)


for name, k, host, d, L, sp in (("branch_spine", "branch0", "crust_spine_a", (-0.3, -1.0, 0.55), 0.5, 0.4),
                                ("branch_haunch", "branch1", "crust_haunch_l", (-0.45, -1.0, 0.45), 0.42, -0.7),
                                ("branch_withers", "branch2", "crust_withers_r", (0.25, -1.0, 0.7), 0.36, 1.6)):
    branch(name, k, host, d, L, sp)


# ---------------------------------------------------------------- measure
T_BUILD = time.time() - T0


def tris_of(ob):
    return sum(len(p.vertices) - 2 for p in ob.data.polygons)


fit = {}
allb = []
for p in PARTS:
    ob = p["ob"]
    vs, fs = world_verts(ob)
    bv = BVHTree.FromPolygons(vs, fs)
    ds = []
    for v in vs:
        loc, n, _, dist = BODY.find_nearest(v)
        ds.append(dist if ((v - loc).dot(n) >= 0 or not inside(v)) else -dist)
    c2 = min(bv.find_nearest(V(b))[3] for b in BVS)                 # Troll vertices -> part surface (flat faces resting on a bulge)
    p.update(tris=tris_of(ob), pairs_body=len(bv.overlap(BODY)), pairs_hair=len(bv.overlap(HAIR)), min_clear=min(ds),
             contact=min(min(abs(x) for x in ds), c2), bv=bv)
# contact graph: attached = within 12 mm of the Troll, or overlapping / within 5 mm of an attached part
att = {i for i, p in enumerate(PARTS) if p["contact"] <= 0.004 or p["pairs_body"] > 0}   # sunk parts cut the skin: attached
changed = True
while changed:
    changed = False
    for i, p in enumerate(PARTS):
        if i in att:
            continue
        for j in list(att):
            if p["bv"].overlap(PARTS[j]["bv"]) or min(PARTS[j]["bv"].find_nearest(v)[3] for v in world_verts(p["ob"])[0][::7]) < 0.002:
                att.add(i); changed = True; break
floating = [PARTS[i]["name"] for i in range(len(PARTS)) if i not in att]
# back faces visible from 26 directions (the Troll body as an occluder)
vs, fs, owner = list(BVS), list(BFS), [None] * len(BFS)
for p in PARTS:
    o = len(vs); v_, f_ = world_verts(p["ob"])
    vs += [tuple(v) for v in v_]
    for f in f_:
        fs.append(tuple(i + o for i in f)); owner.append(p["name"])
ab = BVHTree.FromPolygons(vs, fs)
dirs = []
for i in range(26):
    z = 1 - 2 * (i + 0.5) / 26; r = math.sqrt(1 - z * z); a = i * 2.39996
    dirs.append(V((r * math.cos(a), r * math.sin(a), z)))
back = {}
cutout = {"pine"}                     # foliage cards are double-sided in the game (Custom/Vegetation, _Cull 0): skip
for fi in range(len(BFS), len(fs)):
    if owner[fi].startswith(("growth_vines", "growth_vinel", "skirt_vine")):
        continue
    tri = [V(vs[i]) for i in fs[fi]]
    c = sum(tri, V()) / len(tri)
    nrm = (tri[1] - tri[0]).cross(tri[2] - tri[0])
    if nrm.length < 1e-12:
        continue
    nrm.normalize()
    for dd in dirs:
        if nrm.dot(dd) > -0.2:
            continue
        h = ab.ray_cast(c + dd * 50, -dd, 100)
        if h[2] == fi:
            back[owner[fi]] = back.get(owner[fi], 0) + 1
            break
T_MEAS = time.time() - T0 - T_BUILD

# ---------------------------------------------------------------- attach table
U2B = VK.U2B
BSCALE = float(np.linalg.norm(D.bone_world_u("Pelvis")[:3, 0]))
attach = {"_about": "ASSET-002 Rootstalker kitbash: every add-on is a vanilla mesh (Hive lumps with our per-vertex offsets) on one Wolf bone (or skinned, see mode). "
          "For each part: create an ANCHOR as a child of `parent` with localPosition/localRotation/localScale (Runic armor_attach "
          "convention: localScale 1/BSCALE cancels the Wolf's bone-chain scale, localRotation undoes the bone's REST rotation, so the anchor "
          "is world-aligned in the rest pose), then a child carrying the vanilla mesh with `part_localRotation` / `part_localScale` "
          "(Unity axes) at position 0. Units: Unity, the Wolf prefab's REST pose.",
          "_donor": "Wolf (1.0.21, bundle c4210710)", "_bone_chain_scale": BSCALE, "_base_tris": {"M": TRIS_BODY}, "_sources": SRC}
def attach_entry(p, bone, Mb=None):
    Mb = p["ob"].matrix_world if Mb is None else Mb
    Mu = U2B @ Mb @ U2B
    loc, rot, sc = Mu.decompose()
    Bw = D.bone_world_u(bone)
    lp = np.linalg.inv(Bw) @ np.array([loc.x, loc.y, loc.z, 1.0])
    Rb = Bw[:3, :3] / np.linalg.norm(Bw[:3, :3], axis=0)
    q = Matrix(Rb.tolist()).to_quaternion().inverted()
    return {"source": p["k"], "material": p["ob"].data.materials[0].name, "parent": bone,
                                 "localPosition": [round(float(x), 6) for x in lp[:3]],
                                 "localRotation": [round(q.x, 6), round(q.y, 6), round(q.z, 6), round(q.w, 6)],
                                 "localScale": [round(1 / BSCALE, 7)] * 3,
                                 "part_localRotation": [round(rot.x, 6), round(rot.y, 6), round(rot.z, 6), round(rot.w, 6)],
                                 "part_localScale": [round(sc.x, 5), round(sc.y, 5), round(sc.z, 5)],
                                 "rest_world_position": [round(loc.x, 4), round(loc.y, 4), round(loc.z, 4)],
                                 "tris": p["tris"], "pairs_body": p["pairs_body"], "seated_by_m": None if p["seat"] is None else round(p["seat"], 4),
                                 "sunk_frac": SUNK.get(p["name"]),
                                 "vertex_offsets": ("deform/lump_offsets.json#" + p["ob"].name) if p["ob"].name in OFFSETS else None}


os.makedirs(os.path.join(KIT, "deform"), exist_ok=True)
json.dump({"_about": "ASSET-001 v5: per-vertex offsets for the conformed Hive lumps (our data). Add offsets[i] to vertex i of a CLONE of "
                     "the vanilla mesh (TheHive /Visual/TheHive_Visual_low, same vertex order as the game's mesh), in that mesh's own "
                     "space (Unity x, y, z, before the part's localScale), then recalculate normals.",
           "source": KEYS["lump"], **OFFSETS}, open(os.path.join(KIT, "deform", "lump_offsets.json"), "w"))
json.dump({"_about": "ASSET-002 STEP 3: per-vertex UV0 offsets for the conformed Hive lumps (add to mesh.uv[i] of the offset clone).",
           **UV_OFFSETS}, open(os.path.join(KIT, "deform", "lump_uv_offsets.json"), "w"))
os.makedirs(os.path.join(KIT, "vertex_colors"), exist_ok=True)
json.dump({"_about": "ASSET-002 STEP 3 vertex colours (RGB, multiply the albedo). wcanine*: per canine island (root dirt -> pale tip, island "
                     "vertex order = sorted unique vertex indices of the island's Wolf M triangles, see attach.json _sources). maw_row_*: the "
                     "placed gum rows (painted depth: deeper into the slit = darker). maw_lip_*: the two lip lumps (vanilla TheHive low "
                     "vertex order; dark inner edge). Runtime: mesh.colors + a vertex-colour-aware shader, or bake into texture copies.",
           **VC}, open(os.path.join(KIT, "vertex_colors", "maw.json"), "w"))
for p in PARTS:
    attach["RS_" + p["name"]] = attach_entry(p, p["bone"])
json.dump(attach, open(os.path.join(KIT, "attach.json"), "w"), indent=1)
TOT = sum(p["tris"] for p in PARTS)
by_src = {}
for p in PARTS:
    by_src.setdefault(p["k"], [0, 0]); by_src[p["k"]][0] += 1; by_src[p["k"]][1] += p["tris"]
summary = {"tris_base_body": TRIS_BODY, "tris_base_hair": TRIS_HAIR, "tris_addons": TOT, "total_hair_hidden": TRIS_BODY + TOT,
           "total_with_hair": TRIS_BODY + TRIS_HAIR + TOT, "budget": 12000, "parts": len(PARTS), "parts_by_source": by_src,
           "pairs_body_total": sum(p["pairs_body"] for p in PARTS),
           "parts_cutting_body": {p["name"]: p["pairs_body"] for p in PARTS if p["pairs_body"]},
           "parts_with_vertices_inside_body": {p["name"]: round(p["min_clear"], 3) for p in PARTS if p["min_clear"] < 0},
           "min_clear_m": round(min(p["min_clear"] for p in PARTS), 4),
           "sunk_parts": {k: v for k, v in SUNK.items()},
           "far_side_pokes": {p["name"]: far_poke(p["ob"], SINKDIR[p["ob"].name]) for p in PARTS if p["ob"].name in SINKDIR},
           "contact_m_seated_parts": {"min": round(min(p["contact"] for p in PARTS if p["seat"] not in (None, 0.0)), 4),
                                      "median": round(sorted(p["contact"] for p in PARTS if p["seat"] not in (None, 0.0))[
                                          len([1 for p in PARTS if p["seat"] not in (None, 0.0)]) // 2], 4),
                                      "max": round(max(p["contact"] for p in PARTS if p["seat"] not in (None, 0.0)), 4)},
           "not_seated": [p["name"] for p in PARTS if p["seat"] is None], "floating": floating, "visible_back_faces": back,
           "seconds": {"build": round(T_BUILD, 1), "measure": round(T_MEAS, 1)}}
json.dump(summary, open(os.path.join(KIT, "fit.json"), "w"), indent=1)
print("SUMMARY", json.dumps(summary))

# ---------------------------------------------------------------- EARLY REPAINT of the Wolf's own texture (masks + recipe; preview only)
import troll_repaint as TR
T_RP = time.time()
RP = os.path.join(KIT, "repaint"); os.makedirs(os.path.join(RP, "preview"), exist_ok=True)
SZ = 1024          # computed at 2x; the shipped mask is box-filtered to 512 (the runtime paints into a 512 copy of the 256 texture)
SZO = 512
Vb, Fb, UVb, mb = D.mesh_data("M")
pos, nrm = TR.raster_position_map([tuple(v) for v in Vb], Fb, UVb, SZ)
valid = ~np.isnan(pos[..., 0])
Pv = pos[valid]
# bark: distance to the crust (every lump, front and back) with a noisy edge
dist = np.full(len(Pv), 9.0)
for p in PARTS:
    if p["k"] != "lump":
        continue
    vs, _ = world_verts(p["ob"])
    A_ = np.array([v[:] for v in vs]); c_ = A_.mean(0); r_ = 0.42 * (A_.max(0) - A_.min(0)).max()
    dist = np.minimum(dist, np.linalg.norm(Pv - c_, axis=1) - r_)
nz = TR.value_noise3(Pv, 0.1, 11) * 0.07 + TR.value_noise3(Pv, 0.035, 12) * 0.03 + TR.value_noise3(Pv, 0.012, 13) * 0.01
bark_v = 1 - TR.smoothstep(0.0, 0.15, dist + nz)
# the crust runs down over the hips where the loincloth was (Hair hidden), ragged lower edge
pel = (TR.smoothstep(3.6, 3.25, Pv[:, 2]) * TR.smoothstep(2.45, 2.8, Pv[:, 2] + nz * 0.7) * TR.smoothstep(1.55, 1.15, np.abs(Pv[:, 0])))
# (v6: the hip band read as "bark shorts" - the hips go back to sickly skin; only the sunk hip lump carries crust there)
# extremities: forearms/hands (|x| beyond the elbow) and shins/feet
ext_v = np.maximum(TR.smoothstep(0.6, 0.12, Pv[:, 2]), TR.smoothstep(-1.0, -1.45, Pv[:, 1]))     # legs/paws and the tail tip


def nearest(pt):
    loc, n, _, _ = BODY.find_nearest(V(tuple(pt)))
    return (np.array(loc[:]), np.array(n[:])) if loc is not None else (None, None)


ml_ = np.array(ml[:])
eye_locs = [np.array((p["ob"].matrix_world.translation)[:]) for p in PARTS if p["k"] == "eye"]
_r = np.random.default_rng(5)
# v5 veins: thin, tapering, branching, smoothed (no straight runs), fading out within ~0.5-0.8 m of the mouth and the eyes
vein_starts = [(ml_ + np.array([0.04 * sx, 0, dz]), 0.004, (sx, _r.uniform(-0.6, 0.6), dz * 8 + _r.uniform(-0.5, 0.5))) for sx in (-1, 1)
               for dz in (-0.08, -0.03, 0.02, 0.07)]
vein_starts += [(e, 0.0035, (_r.uniform(-1, 1), _r.uniform(-1, 1), _r.uniform(-1, 1))) for e in eye_locs for _ in range(2)]
veins = TR.smooth_curves(TR.walk_curves(nearest, vein_starts, 1, 0.2, 0.008, 21, branch=8.0, persist=0.35, jitter=0.45),
                         nearest, 2)
root_starts = []
for p in PARTS:
    if p["k"] == "lump" and p["name"].startswith(("crust", "hem")):
        c = np.array((p["ob"].matrix_world @ anchor_pt("lump", "center"))[:])
        out = c - np.array([0.0, c[1], 0.85]); out /= (np.linalg.norm(out) + 1e-9)
        root_starts.append((c, 0.007, tuple(out + np.array([0, 0, -0.6]))))
roots_c = TR.walk_curves(nearest, root_starts, 2, 0.35, 0.012, 31, bias=(0, 0, -1), branch=3.0)
vein_m = TR.curves_mask(pos, veins, fade=1.2)
halo = TR.curves_mask(pos, [(pts, w0 * 3.5) for pts, w0 in veins], fade=1.6)     # the soft glow around each vein
root_m = TR.curves_mask(pos, roots_c)
dm = Pv - ml_
mouth_v = (TR.smoothstep(0.05, 0.022, np.abs(dm[:, 0])) * TR.smoothstep(MAW_H * 0.62, MAW_H * 0.48, np.abs(dm[:, 2]))
           * (np.abs(dm[:, 1]) < 0.09))
mouth_core = (TR.smoothstep(0.03, 0.0, np.abs(dm[:, 0])) * TR.smoothstep(MAW_H * 0.42, MAW_H * 0.3, np.abs(dm[:, 2]))
              * (np.abs(dm[:, 1]) < 0.09))
# v2 (owner: "keep it but texture is better to better illustrate that its a mouth"): a dark wet OPENING painted larger than the
# slit, a band of the Wolf's own red-pink gum colour carried out onto the lips, radiating strain folds around it; the glow stays
# deep inside (the sack), no bright line on the surface
upv = np.array(up[:]); acr = np.array([1.0, 0.0, 0.0]); nrmv = np.array(mn[:])
ax_ = dm @ acr; az_ = dm @ upv; ad_ = np.abs(dm @ nrmv)
EA, EBb = 0.085, MAW_H * 0.62
rr_ = np.sqrt((ax_ / EA) ** 2 + (az_ / EBb) ** 2)
near_ = (ad_ < 0.09) & (Pv[:, 1] > 0.3)
open_v = TR.smoothstep(1.0, 0.8, rr_) * near_
gum_v = TR.smoothstep(0.78, 0.96, rr_) * TR.smoothstep(1.4, 1.08, rr_) * near_
th_ = np.arctan2(az_ / EBb, ax_ / EA)
fold_v = ((0.5 + 0.5 * np.cos(th_ * 16 + TR.value_noise3(Pv, 0.03, 41) * 3.0)) ** 6) * TR.smoothstep(1.02, 1.2, rr_) * TR.smoothstep(2.2, 1.35, rr_) * near_
MM = np.zeros((SZ, SZ, 4)); MM[..., 3] = 1
MM[..., 0][valid] = open_v; MM[..., 1][valid] = gum_v; MM[..., 2][valid] = fold_v
MM = TR.dilate_fill(MM, valid, 8)
hk.save_array(os.path.join(RP, "wolf_mouth_mask.png"), MM.reshape(SZO, SZ // SZO, SZO, SZ // SZO, 4).mean((1, 3)))
glow = np.zeros((SZ, SZ))
vein_m = vein_m * 0.55                       # veins dimmer; no surface glow at the mouth (the sack glows deep inside)
mouth_v = open_v   # wolf: veins dimmer, the throat glow + its halo read at 10 m          # the deep glow in the slit rides the same emission mask
mask = np.zeros((SZ, SZ, 4))
mask[..., 0][valid] = bark_v
mask[..., 1][valid] = ext_v
mask[..., 2] = np.maximum(vein_m, 0.3 * halo)
dark = np.zeros((SZ, SZ)); dark[valid] = mouth_v
mask[..., 3] = np.maximum(root_m * 0.92, dark)
mask = TR.dilate_fill(mask, valid, 8)
hk.save_array(os.path.join(RP, "wolf_hive_mask.png"), mask.reshape(SZO, SZ // SZO, SZO, SZ // SZO, 4).mean((1, 3)))
# the recipe, and the repainted albedo + emission (PREVIEW ONLY: derived from vanilla pixels)
REC = {"about": "ASSET-002 early repaint recipe (troll_repaint.py). Mask = kit/repaint/wolf_hive_mask.png in the Wolf M mesh's UV0 "
                "(R bark, G extremity darkening, B blight veins = emission, A dark roots + mouth). Colours are linear multipliers "
                "applied to the texture's stored (sRGB-encoded) texel values, as the runtime reads them back with GetPixels. The vanilla "
                "luminance is kept everywhere (lum / mean lum), so the anatomy still reads.",
       "sick_skin": [0.34, 0.36, 0.29], "extremity_darken": 0.5, "bark_tint": [0.85, 0.6, 0.3], "infection_margin_darken": 0.45,
       "bark_texture": "olivetree_trunk01 (TheHive_Mat _MainTex), triplanar in rest-pose metres, tile 0.3 m",
       "root_colour": [0.03, 0.025, 0.02], "vein_albedo": [0.05, 0.06, 0.02], "blight_colour": [0.42, 0.55, 0.12],
       "emission_strength_preview": 1.6, "mask_size": "512 (computed at 1024, box-filtered); the vanilla Wolf texture is 256, the runtime paints a 512 copy", "blight_emission": "BlightGlow, driven by the biome tint at runtime",
       "mouth_colour": [0.01, 0.008, 0.006], "mouth_opening_colour": [0.03, 0.008, 0.012], "gum_colour": [0.62, 0.2, 0.22],
       "fold_darken": 0.6, "mouth_mask": "kit/repaint/wolf_mouth_mask.png (R opening, G gum band, B radiating folds), same UV0", "fur_note": "the Wolf has ONE renderer (M); its fur is painted in its texture, so it is repainted, nothing hidden"}
json.dump(REC, open(os.path.join(RP, "repaint.json"), "w"), indent=1)
albedo_png, minfo = D.tex_path("_MainTex")
src = bpy.data.images.load(albedo_png); src.scale(SZ, SZ)
A0 = np.empty(SZ * SZ * 4, dtype=np.float32); src.pixels.foreach_get(A0); A0 = A0.reshape(SZ, SZ, 4)
lum = A0[..., :3] @ np.array([0.3, 0.59, 0.11])
lum_n = lum / max(1e-6, lum[valid].mean())
barkimg = bpy.data.images.load(os.path.join(REF, "tex", "olivetree_trunk01.png"))
bw, bh = barkimg.size
BK = np.empty(bw * bh * 4, dtype=np.float32); barkimg.pixels.foreach_get(BK); BK = BK.reshape(bh, bw, 4)[..., :3]
# triplanar sample of the bark at each texel's rest position
Nv = np.abs(nrm[valid]); axis = Nv.argmax(1)
uu = np.where(axis == 0, Pv[:, 1], Pv[:, 0]); vv = np.where(axis == 2, Pv[:, 1], Pv[:, 2])
px = ((uu / 0.3) % 1.0 * (bw - 2)).astype(int); py = ((vv / 0.3) % 1.0 * (bh - 2)).astype(int)
BKs = (BK[py, px] + BK[py + 1, px] + BK[py, px + 1] + BK[py + 1, px + 1]) * 0.25
seam = TR.smoothstep(0.03, 0.005, np.abs(Pv[:, 0]))                              # the mirrored halves meet on x = 0
lum_n_v = lum_n[valid] * (1 - seam) + 0.92 * seam                                   # blend the vanilla shading across the seam
lum_n = lum_n.copy(); lum_n[valid] = lum_n_v
barkcol = BKs * np.array(REC["bark_tint"]) * (0.45 + 0.55 * np.clip(lum_n[valid], 0, 2))[:, None]
sick = np.clip(lum_n[valid], 0, 2.5)[:, None] * np.array(REC["sick_skin"])
colv = sick * (1 - bark_v[:, None]) + barkcol * bark_v[:, None]
moss_v = TR.smoothstep(0.35, 0.8, nrm[valid][:, 2]) * TR.smoothstep(-0.05, 0.25, TR.value_noise3(Pv, 0.12, 51)) * bark_v * 0.6
colv = colv * (1 - moss_v[:, None]) + np.array([0.2, 0.25, 0.1]) * np.clip(lum_n[valid], 0.4, 1.4)[:, None] * moss_v[:, None]
MOSS = np.zeros((SZ, SZ, 4)); MOSS[..., 3] = 1; MOSS[..., 0][valid] = moss_v
MOSS = TR.dilate_fill(MOSS, valid, 8)
hk.save_array(os.path.join(RP, "wolf_moss_mask.png"), MOSS.reshape(SZO, SZ // SZO, SZO, SZ // SZO, 4).mean((1, 3)))
REC["moss"] = {"mask": "kit/repaint/wolf_moss_mask.png (R = moss amount, M UV0)", "colour": [0.2, 0.25, 0.1],
               "how": "albedo = lerp(albedo, moss_colour x vanilla luminance, R)"}
json.dump(REC, open(os.path.join(RP, "repaint.json"), "w"), indent=1)
colv *= (1 - REC["extremity_darken"] * ext_v)[:, None]
colv *= (1 - REC["infection_margin_darken"] * 4 * bark_v * (1 - bark_v))[:, None]     # dark, infected margin where bark meets skin
rm = mask[..., 3][valid][:, None]
colv = colv * (1 - rm) + np.array(REC["root_colour"]) * rm
vm = vein_m[valid][:, None]
colv = colv * (1 - vm) + np.array(REC["vein_albedo"]) * vm
colv *= (1 - REC["fold_darken"] * fold_v)[:, None]
gv = gum_v[:, None]
colv = colv * (1 - gv) + np.array(REC["gum_colour"]) * np.clip(lum_n[valid], 0.5, 1.6)[:, None] * gv
ov = open_v[:, None]
colv = colv * (1 - ov) + np.array(REC["mouth_opening_colour"]) * ov
OUTA = A0.copy(); OUTA[..., :3][valid] = colv
OUTA = TR.dilate_fill(OUTA, valid, 8); OUTA[..., 3] = A0[..., 3]
hk.save_array(os.path.join(RP, "preview", "wolf_repainted_albedo.png"), OUTA)
EB = mask[..., 2]
EM = np.zeros((SZ, SZ, 4)); EM[..., 0] = EB * REC["blight_colour"][0]; EM[..., 1] = EB * REC["blight_colour"][1]
EM[..., 2] = EB * REC["blight_colour"][2]; EM[..., 3] = 1
hk.save_array(os.path.join(RP, "preview", "wolf_blight_emission.png"), EM)


def repaint_material():
    m = DB.base_material(D, name="WolfRepaint")
    nt = m.node_tree
    for nd in nt.nodes:
        if nd.type == 'TEX_IMAGE' and nd.image and "MainTex" in nd.image.name:
            nd.image = bpy.data.images.load(os.path.join(RP, "preview", "wolf_repainted_albedo.png"))
    for nd in nt.nodes:
        if nd.type == 'MIX' and nd.blend_type == 'MULTIPLY':
            nd.inputs[7].default_value = (1, 1, 1, 1)       # the albedo already carries the colour
    te = nt.nodes.new("ShaderNodeTexImage"); te.image = bpy.data.images.load(os.path.join(RP, "preview", "wolf_blight_emission.png"))
    te.image.colorspace_settings.name = 'Non-Color'
    b_ = nt.nodes["Principled BSDF"]
    nt.links.new(te.outputs["Color"], b_.inputs["Emission Color"]); b_.inputs["Emission Strength"].default_value = REC["emission_strength_preview"]
    tm_ = nt.nodes.new("ShaderNodeTexImage"); tm_.image = bpy.data.images.load(os.path.join(RP, "wolf_mouth_mask.png"))
    tm_.image.colorspace_settings.name = 'Non-Color'
    sp_ = nt.nodes.new("ShaderNodeSeparateColor"); nt.links.new(tm_.outputs["Color"], sp_.inputs[0])
    wr_ = nt.nodes.new("ShaderNodeMath"); wr_.operation = 'MULTIPLY_ADD'; wr_.inputs[1].default_value = -0.75; wr_.inputs[2].default_value = 0.85
    nt.links.new(sp_.outputs[0], wr_.inputs[0]); nt.links.new(wr_.outputs[0], b_.inputs["Roughness"])     # the opening is wet
    return m


summary["repaint"] = {"mask": "kit/repaint/wolf_hive_mask.png", "recipe": "kit/repaint/repaint.json", "size": SZ,
                      "texels_used": int(valid.sum()), "bark_cover_pct": round(float((bark_v > 0.5).mean() * 100), 1),
                      "vein_curves": len(veins), "root_curves": len(roots_c), "seconds": round(time.time() - T_RP, 1)}
print("REPAINT", summary["repaint"])

# ---------------------------------------------------------------- scene, previews
col = bpy.data.collections.new("COL_HiveKitbash"); bpy.context.scene.collection.children.link(col)
for p in PARTS:
    for c in p["ob"].users_collection:
        c.objects.unlink(p["ob"])
    col.objects.link(p["ob"])
colb = bpy.data.collections.new("COL_WolfBase_reference_not_shipped"); bpy.context.scene.collection.children.link(colb)
body_ob = DB.add_base(D, collection=colb, names=("M",))[0]
DB.weld_normals(body_ob.data)
RPMAT = repaint_material()
VANMAT = body_ob.data.materials[0]
body_ob.data.materials[0] = RPMAT
DB.lights_and_world(scale=1.0, aim=(0, 0, 0.8))
DB.setup_render(900, 900)
bpy.ops.wm.save_as_mainfile(filepath=os.path.join(KIT, "Rootstalker_kitbash.blend"))
shots = {}


def shot(name, target, dist, az, el, lens=85, w=900, h=900):
    bpy.context.scene.render.resolution_x, bpy.context.scene.render.resolution_y = w, h
    DB.camera(target, dist, az, el, lens=lens)
    pth = os.path.join(PREV, name + ".png"); DB.render(pth); shots[name] = pth


CEN = (0, -0.15, 0.72)
views = (("front", 0, 6, 5.5), ("side", 90, 6, 8.2), ("back", 180, 8, 5.5), ("34", 40, 14, 7.6))
for nm, az, el, dist in views:
    shot(f"kit_{nm}", CEN, dist, az, el)
shot("close_head", (0, 0.85, 1.1), 2.3, 35, 12, w=900, h=800)
_ed = bpy.data.objects["RS_eye_snout_l0"].matrix_world.translation
shot("close_eyes_1to1", tuple(_ed), 0.9, 40, 8, w=900, h=700)
shot("close_wtf_throat", tuple(ml), 1.6, 12, -6, w=900, h=900)
shot("wtf_front_10m", (0, 0.1, 0.75), 10.0, 0, 2, lens=50, w=1200, h=800)
shot("close_branches", (0, -0.35, 1.15), 2.6, 125, 22, w=900, h=900)
col.hide_render = True
shot("base_repaint_34", CEN, 7.6, 40, 14)
shot("base_repaint_side", CEN, 8.2, 90, 6)
shot("base_repaint_top", (0, -0.15, 0.8), 7.0, 90, 70)
body_ob.data.materials[0] = VANMAT
for nm, az, el, dist in views:
    shot(f"base_{nm}", CEN, dist, az, el)
body_ob.data.materials[0] = RPMAT
col.hide_render = False
fig, fh = hk.figure(0.9, -0.2)
bpy.context.scene.render.resolution_x, bpy.context.scene.render.resolution_y = 1300, 900
DB.camera((0.45, -0.2, 0.95), 30, 90, 0, ortho=3.6)
pth = os.path.join(PREV, "lineup_1.8m.png"); DB.render(pth); shots["lineup"] = pth
bpy.data.objects.remove(fig)
hk.grid([shots["kit_front"], shots["kit_side"], shots["kit_back"], shots["kit_34"]], 4, os.path.join(PREV, "kit_sheet.png"))
hk.grid([shots["base_front"], shots["base_side"], shots["base_back"], shots["base_34"]], 4, os.path.join(PREV, "base_sheet.png"))
# ---------------------------------------------------------------- STEP 3 FINAL-LOOK RENDERS
import final_look as FL
FL.final_set(globals(), name_prefix="final", cen=CEN, views=views, head=((0, 0.85, 1.1), 2.3, 35, 12), wtf=(tuple(ml), 1.6, 12, -6),
             branches=((0, -0.35, 1.15), 2.6, 125, 22), read10=((0, 0.1, 0.75), 10.0, 0, 2), scale=1.0, aim_z=0.8,
             body=body_ob, rpmat=RPMAT, col=col)
# ---------------------------------------------------------------- POSE TEST: the Wolf skinned with its own donor weights, the rigid parts on
# their posed bones. Poses as world-space rotations about each joint's rest position (FK down the chain), linear blend skinning.
T_PT = time.time()
TF = D.T
def parent_of(b):
    return TF[b]["parent"]
def rot_about(pivot, R3):
    return Matrix.Translation(V(pivot)) @ R3.to_4x4() @ Matrix.Translation(-V(pivot))
def Rw(axis, deg):
    return Matrix.Rotation(math.radians(deg), 3, V(axis))
POSES = {    # world-axis rotations about each joint (x = right, y = forward, z = up); +x rotation swings a hanging leg forward
    "run stride": {"L UpperArm": Rw((1, 0, 0), 40), "R UpperArm": Rw((1, 0, 0), -30), "L Forearm": Rw((1, 0, 0), -35),
                   "L Thigh": Rw((1, 0, 0), -35), "R Thigh": Rw((1, 0, 0), 30), "R Calf": Rw((1, 0, 0), -30),
                   "Spine1": Rw((1, 0, 0), 6), "Tail": Rw((1, 0, 0), 20)},
    "jump crouch": {"_root": V((0, 0, -0.22)), "L Thigh": Rw((1, 0, 0), 45), "R Thigh": Rw((1, 0, 0), 45),
                    "L Calf": Rw((1, 0, 0), -70), "R Calf": Rw((1, 0, 0), -70), "L HorseLink": Rw((1, 0, 0), 45),
                    "R HorseLink": Rw((1, 0, 0), 45), "L UpperArm": Rw((1, 0, 0), -30), "R UpperArm": Rw((1, 0, 0), -30),
                    "L Forearm": Rw((1, 0, 0), 55), "R Forearm": Rw((1, 0, 0), 55), "Neck": Rw((1, 0, 0), -12)},
    "head low": {"Neck": Rw((1, 0, 0), -38), "Head": Rw((1, 0, 0), -18)},
    "bite": {"Jaw": Rw((1, 0, 0), -35), "Head": Rw((1, 0, 0), 12), "Neck": Rw((1, 0, 0), 15)}}
bone_names = mb["bone_names"]
BI = np.array(mb["bone_indices"]); BWt = np.array(mb["bone_weights"]); BWt = BWt / np.maximum(BWt.sum(1, keepdims=True), 1e-9)
VR = np.c_[np.array([tuple(v) for v in Vb]), np.ones(len(Vb))]
def fk(pose):
    T = {}
    def get(b):
        if b in T:
            return T[b]
        par = parent_of(b)
        base = get(par) if (par is not None and par in TF) else (Matrix.Translation(pose["_root"]) if "_root" in pose else Matrix.Identity(4))
        T[b] = base @ (rot_about(BP(b), pose[b]) if b in pose else Matrix.Identity(4))
        return T[b]
    for b in TF:
        get(b)
    return T
# weight transfer: every add-on vertex takes the inverse-distance blend of the 4 nearest Body vertices' donor weights. The part's
# average decides the FIX: one bone >= 80 % -> stays rigid, re-parented to that bone if it differs; otherwise -> skinned (the
# runtime bakes it into a SkinnedMeshRenderer on the Troll's bones with these transferred weights).
from mathutils.kdtree import KDTree
WSMOOTH_OWN = 0.25


def under_head(b):
    while b is not None and b in TF:
        if b == "Head":
            return True
        b = TF[b]["parent"]
    return False

NB = len(bone_names)
WD = np.zeros((len(Vb), NB))
for k in range(BI.shape[1]):
    np.add.at(WD, (np.arange(len(Vb)), BI[:, k]), BWt[:, k])
KD = KDTree(len(Vb))
for i, v in enumerate(Vb):
    KD.insert(V(tuple(v)), i)
KD.balance()
for p in PARTS:
    vs = [p["ob"].matrix_world @ v.co for v in p["ob"].data.vertices]
    W = np.zeros((len(vs), NB))
    for j, v in enumerate(vs):
        hits = KD.find_n(v, 4)
        w = np.array([1 / max(h[2], 1e-3) for h in hits]); w /= w.sum()
        W[j] = sum(wi * WD[h[1]] for wi, h in zip(w, hits))
    p["W"] = W
    avg = W.mean(0)
    top = int(avg.argmax())
    p["dom_bone"], p["dom_share"] = bone_names[top], float(avg[top])
    p["fix"] = ("rigid" if p["dom_share"] >= 0.8 else "skinned")
    if under_head(p["dom_bone"]) and not under_head(p["bone"]):
        p["fix"] = "skinned"            # a body part next to the jaw/ear/neck skin: follow the skin, never ride the ear rigidly
    p["fix_bone"] = p["dom_bone"] if p["fix"] == "rigid" else p["bone"]
    if p["k"].startswith("branch"):     # branches ride their host's bone (rigid), never bend
        p["fix"], p["fix_bone"] = "rigid", p["bone"]
    # v6: SMOOTHED transferred weights (25 % per-vertex, 75 % the part's average): the crown of a lump 0.3 m off the skin no longer
    # takes the skin's full joint swing, so skinned lumps follow the flesh without stretching into flaps
    p["Wraw"], p["avg"] = W, avg
    p["W"] = WSMOOTH_OWN * W + (1 - WSMOOTH_OWN) * avg[None, :]
    p["VP"] = np.c_[np.array([v[:] for v in vs]), np.ones(len(vs))]
    p["F"] = [tuple(q.vertices) for q in p["ob"].data.polygons]
def inside_b(pt, bvh):
    n_, o_, dd = 0, V(pt), V((0.123, 0.456, 0.88)).normalized()
    for _ in range(30):
        h = bvh.ray_cast(o_, dd, 50)
        if h[0] is None:
            break
        n_ += 1; o_ = h[0] + dd * 1e-4
    return n_ % 2 == 1


for p in PARTS:
    rvs = [V(tuple(x)) for x in p["VP"][:, :3]][::max(1, len(p["VP"]) // 24)]
    p["rest_inside"] = sum(inside_b(v, BODY) for v in rvs) / len(rvs)     # the same parity test as the posed check


def judge(p, vs, PB, rep):
    if "EL" not in p:
        p["E"] = [tuple(e.vertices) for e in p["ob"].data.edges]
        vis = [not inside_b(V(tuple(q[:3])), BODY) for q in p["VP"]]
        p["E"] = [(a, b) for a, b in p["E"] if vis[a] and vis[b]]          # only edges you can see at rest
        p["EL"] = [max((V(tuple(p["VP"][a][:3])) - V(tuple(p["VP"][b][:3]))).length, 1e-6) for a, b in p["E"]]
    worst = max(((vs[a] - vs[b]).length / l0, (vs[a] - vs[b]).length - l0) for (a, b), l0 in zip(p["E"], p["EL"])) if p["E"] else (1, 0)
    if worst[0] > 1.5 and worst[1] > 0.02:
        rep["stretched"].append(f"{p['name']} (visible edge x{worst[0]:.2f}, +{worst[1] * 100:.0f} cm)")
    bv = BVHTree.FromPolygons(vs, p["F"])
    rep["pairs"] += len(bv.overlap(PB))
    samp = vs[::max(1, len(vs) // 24)]
    f_now = sum(inside_b(v, PB) for v in samp) / len(samp)
    gap = min(PB.find_nearest(v)[3] for v in vs[::3])
    if f_now - p["rest_inside"] > 0.3:
        rep["poke_through"].append(f"{p['name']} ({p['rest_inside']:.0%} -> {f_now:.0%} inside)")
    if p["rest_inside"] > 0.05 and f_now < 0.02 and gap > 0.01:
        rep["lifted"].append(f"{p['name']} (gap {gap * 100:.0f} cm)")


def posed_body(pose):
    T = fk(pose)
    TM = np.array([np.array(T[b]) for b in bone_names])
    posed = np.zeros((len(VR), 3))
    for k in range(BI.shape[1]):
        posed += BWt[:, k:k + 1] * np.einsum("nij,nj->ni", TM[BI[:, k]], VR)[:, :3]
    return T, TM, posed


POSED = []
for pname, pose in POSES.items():
    T, TM, posed = posed_body(pose)
    POSED.append((T, TM, BVHTree.FromPolygons([tuple(v) for v in posed], [tuple(f) for f in Fb])))


def passes(p, bone):
    for T, TM, PB in POSED:
        rep = {"poke_through": [], "lifted": [], "stretched": [], "pairs": 0}
        judge(p, [V(tuple(x)) for x in (p["VP"] @ np.array(T[bone]).T)[:, :3]], PB, rep)
        if rep["poke_through"] or rep["lifted"]:
            return False
    return True


# v6 order of preference: rigid on the AUTHORED bone if it passes every pose (simplest at runtime), else rigid on the dominant
# bone, else skinned (with the smoothing search below); branches always rigid on their host's bone
for p in PARTS:
    if p["k"].startswith("branch"):
        continue
    if passes(p, p["bone"]):
        p["fix"], p["fix_bone"] = "rigid", p["bone"]
    elif p["fix"] == "rigid" and not passes(p, p["fix_bone"]):
        p["fix"], p["fix_bone"] = "skinned", p["bone"]
        print("RIGID FIX FAILS -> skinned:", p["name"])
# v6: per-part weight smoothing chosen by the test - for each skinned part, the smoothest blend (own per-vertex weights vs the
# part's average) that passes every pose; if none passes, the one with the fewest failures
for p in PARTS:
    if p["fix"] != "skinned":
        continue
    best = None
    HM = np.array([0.0 if under_head(b) else 1.0 for b in bone_names])
    Wm = p["Wraw"] * HM; Wm /= np.maximum(Wm.sum(1, keepdims=True), 1e-9); am = Wm.mean(0)
    for lvl, masked in ((0.25, False), (0.5, False), (0.75, False), (1.0, False), (0.25, True), (0.5, True), (1.0, True)):
        if masked and under_head(p["bone"]):
            continue
        Wl = lvl * (Wm if masked else p["Wraw"]) + (1 - lvl) * (am if masked else p["avg"])[None, :]
        nf = 0
        for T, TM, PB in POSED:
            rep = {"poke_through": [], "lifted": [], "stretched": [], "pairs": 0}
            judge(p, [V(tuple(x)) for x in np.einsum("nb,bij,nj->ni", Wl, TM, p["VP"])[:, :3]], PB, rep)
            nf += len(rep["poke_through"]) + len(rep["lifted"]) + len(rep["stretched"])
        if best is None or nf < best[0]:
            best = (nf, lvl, Wl, masked)
        if nf == 0:
            break
    p["W"], p["wsmooth"], p["head_masked"] = best[2], best[1], best[3]
    if best[0]:
        print("SKIN FIX STILL FAILS:", p["name"], best)
pose_cells, pose_report = [], {}
body_ob.hide_render = True
col.hide_render = True
for pname, pose in POSES.items():
    T = fk(pose)
    TM = np.array([np.array(T[b]) for b in bone_names])                    # (nb, 4, 4)
    posed = np.zeros((len(VR), 3))
    for k in range(BI.shape[1]):
        posed += BWt[:, k:k + 1] * np.einsum("nij,nj->ni", TM[BI[:, k]], VR)[:, :3]
    me = body_ob.data.copy(); me.name = "posed_body"
    for i, v in enumerate(me.vertices):
        v.co = posed[i]
    me.update(); DB.weld_normals(me)
    pb = bpy.data.objects.new("posed_body", me); bpy.context.scene.collection.objects.link(pb)
    PB = BVHTree.FromPolygons([tuple(v) for v in posed], [tuple(f) for f in Fb])
    before = {"poke_through": [], "lifted": [], "stretched": [], "pairs": 0}
    after = {"poke_through": [], "lifted": [], "stretched": [], "pairs": 0}
    clones = []
    for p in PARTS:
        # as authored: rigid on the authored bone
        Mr = np.array(T[p["bone"]])
        judge(p, [V(tuple(x)) for x in (p["VP"] @ Mr.T)[:, :3]], PB, before)
        # as fixed: rigid on the dominant bone, or skinned
        if p["fix"] == "rigid":
            pv = (p["VP"] @ np.array(T[p["fix_bone"]]).T)[:, :3]
        else:
            pv = np.einsum("nb,bij,nj->ni", p["W"], TM, p["VP"])[:, :3]
        vs = [V(tuple(x)) for x in pv]
        judge(p, vs, PB, after)
        m2 = p["ob"].data.copy()
        for i, v in enumerate(m2.vertices):
            v.co = vs[i]
        o = bpy.data.objects.new("posed_" + p["name"], m2); bpy.context.scene.collection.objects.link(o); clones.append(o)
    pose_report[pname] = {"as_authored_rigid": before, "after_fix": after}
    bpy.context.scene.render.resolution_x, bpy.context.scene.render.resolution_y = 900, 900
    DB.camera((0, -0.1, 0.7), 7.6, 40, 12, lens=85)
    pth = os.path.join(PREV, f"_pose_{len(pose_cells)}.png"); DB.render(pth); pose_cells.append(pth)
    for o in clones:
        me_ = o.data; bpy.data.objects.remove(o); bpy.data.meshes.remove(me_)
    bpy.data.objects.remove(pb); bpy.data.meshes.remove(me)
    print("POSE", pname, json.dumps(pose_report[pname]))
col.hide_render = False; body_ob.hide_render = False
hk.grid(pose_cells, 2, os.path.join(PREV, "pose_test.png"))
for pth in pose_cells:
    os.remove(pth)
fixes = {p["name"]: {"fix": p["fix"], "bone": p["fix_bone"], "authored_bone": p["bone"], "dominant_share": round(p["dom_share"], 2)}
         for p in PARTS if p["fix"] == "skinned" or p["fix_bone"] != p["bone"]}
summary["pose_fixes"] = fixes
for p in PARTS:
    e = attach_entry(p, p["fix_bone"])
    e["mode"] = p["fix"]
    if p["fix"] == "skinned":
        e["skin"] = ("weights transferred at runtime from the 4 nearest Wolf M vertices (inverse distance), rest pose, then "
                     f"blended {p.get('wsmooth', WSMOOTH_OWN):.2f} per-vertex + {1 - p.get('wsmooth', WSMOOTH_OWN):.2f} the part's average")
        e["weight_own_share"] = p.get("wsmooth", WSMOOTH_OWN)
        e["head_bones_masked"] = bool(p.get("head_masked", False))
    attach["RS_" + p["name"]] = e
json.dump(attach, open(os.path.join(KIT, "attach.json"), "w"), indent=1)
summary["pose_test"] = pose_report
summary["seconds"]["pose_test"] = round(time.time() - T_PT, 1)
summary["seconds"]["total_incl_renders"] = round(time.time() - T0, 1)
json.dump(summary, open(os.path.join(KIT, "fit.json"), "w"), indent=1)
summary["figure_height_m"] = round(fh, 3)
json.dump(summary, open(os.path.join(KIT, "fit.json"), "w"), indent=1)
print("DONE", summary["seconds"])
