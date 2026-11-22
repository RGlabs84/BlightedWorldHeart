"""make_brute_kitbash.py - ASSET-001 Hive Brute KITBASHED from vanilla parts onto the real vanilla Troll (coordinator,
2026-11-21: "make the add-ons VANILLA PARTS too, which is literally how the Hive is built").

  heavy.sh 4G sb-kitbash blender -b --factory-startup -P make_brute_kitbash.py -- <ASSET-001 dir>

Every add-on is an UNMODIFIED vanilla mesh with its own vanilla material, placed (position, rotation, scale - non-uniform
scale allowed, no edits to the geometry) on one Troll bone:
  - TheHive `low` bark lumps (TheHive_Mat) on the hump, shoulders, skull, brow, chest lips and knuckles;
  - the Hive's eyes: the `eye_globe` dome mesh with TheHive_Eye (the Hive itself uses Unity's built-in Sphere, 768 tris;
    the 50-tri dome is the budget stand-in) - a slit eye is the same dome scaled thin;
  - the growth (v2, owner: "no pine, drop the trees, second time telling you"; NO tree meshes of any kind): `vines` (high + low LOD
    cards), two glowing `ThornRoots` strands and a writhing root hanging from the hump creases, and a skirt of vine cards from the
    ring;
  - the maw (v2, owner: "chest looks mid"): two `hugeskull/jaw` jaws on their sides, tooth rows facing across the sternum,
    inside a fused mass of Hive lumps across the chest and collar, the GuckSack glowing in the slit; eyes set into the creases;
  - timber: Unity's built-in Cube with TheHive_Mat_legs (what the Hive's legs and ring are) for the waist ring, the
    splayed struts on the back, the knuckle stakes and the splinter teeth of the chest mouth;
  - roots wrapping the limbs: `HugeRoot1/root1_low` (hugeroot, the olive-trunk bark with moss).
No new geometry. Each part is SEATED onto the Troll: moved along its surface normal by bisection to the first position where
no triangle pair cuts the Troll's Body, plus 4 mm. Writes kit/attach.json, kit/fit.json, kit/HiveBrute_kitbash.blend,
kit/previews/*.png and kit/previews/README.md (the earlier hand-modelled kit is kept in kit/shells_v1/).
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
KIT = os.path.join(ASSET, "kit"); PREV = os.path.join(KIT, "previews"); REF = os.path.join(KIT, "vanilla_ref")
os.makedirs(PREV, exist_ok=True)
T0 = time.time()
SEED = 5001
CLEAR = 0.004
rng = random.Random(SEED)

bpy.ops.wm.read_factory_settings(use_empty=True)
D = DB.Donor(ASSET, os.path.join(KIT, "ref"))
BODY, BVS, BFS = DB.base_bvh(D, ("Body",))
HAIR, _, _ = DB.base_bvh(D, ("Hair",))
BP = D.bone_pos_b
P = VK.Parts(REF, os.path.join(SUB, "reference"))
TRIS_BODY, TRIS_HAIR = len(D.mesh_data("Body")[1]), len(D.mesh_data("Hair")[1])

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
        nts.links.new(gm.outputs[2], bs_.inputs["Emission Color"]); bs_.inputs["Emission Strength"].default_value = 3.0
        break
def body_island_meshes():
    """the Troll Body's loose islands (welded by position): its teeth (18 tris) and finger/toe claws (56 tris) are separate
    tapered pieces. Returns {kind: [(tri_indices, mesh)]}; each mesh is put in a canonical frame: root at the origin, root->tip
    along +z, the curve bulging towards +y"""
    Vb_, Fb_, UV_, _ = D.mesh_data("Body")
    Vn = np.array([tuple(v) for v in Vb_])
    par = list(range(len(Vn)))
    def f(a):
        while par[a] != a:
            par[a] = par[par[a]]; a = par[a]
        return a
    for t in Fb_:
        for a, b in ((t[0], t[1]), (t[1], t[2])):
            ra, rb = f(a), f(b)
            if ra != rb:
                par[ra] = rb
    seen = {}
    for i, v in enumerate(Vn):
        k_ = tuple(np.round(v, 5))
        if k_ in seen:
            ra, rb = f(i), f(seen[k_])
            if ra != rb:
                par[ra] = rb
        else:
            seen[k_] = i
    comp = {}
    for ti, t in enumerate(Fb_):
        comp.setdefault(f(t[0]), []).append(ti)
    out = {"ttooth": [], "claw": []}
    for tris in comp.values():
        vi = sorted({i for t in tris for i in Fb_[t]})
        P_ = Vn[vi]; cen = P_.mean(0)
        if len(tris) == 18 and cen[2] > 5.5:
            kind = "ttooth"
        elif len(tris) == 56 and abs(cen[0]) > 4.5:
            kind = "claw"              # finger claws (toe claws are flatter)
        else:
            continue
        # principal axis; the root is the wider end
        Q = P_ - cen; ax = np.linalg.svd(Q, full_matrices=False)[2][0]
        pr = Q @ ax; lo, hi = pr.min(), pr.max()
        wlo = np.linalg.norm(Q[pr < lo + 0.25 * (hi - lo)] - np.outer(pr[pr < lo + 0.25 * (hi - lo)], ax), axis=1).mean()
        whi = np.linalg.norm(Q[pr > hi - 0.25 * (hi - lo)] - np.outer(pr[pr > hi - 0.25 * (hi - lo)], ax), axis=1).mean()
        if whi > wlo:
            ax = -ax; pr = -pr; lo, hi = -hi, -lo
        root = cen + ax * lo
        bulge = (cen - root) - ax * ((cen - root) @ ax)
        yv = bulge / (np.linalg.norm(bulge) + 1e-9) if np.linalg.norm(bulge) > 1e-5 else np.cross(ax, [1, 0, 0])
        yv = yv - ax * (yv @ ax); yv /= np.linalg.norm(yv); xv = np.cross(yv, ax)
        Rm = np.array([xv, yv, ax])
        remap = {old: new for new, old in enumerate(vi)}
        me = bpy.data.meshes.new(f"Troll_{kind}")
        me.from_pydata([tuple(Rm @ (Vn[i] - root)) for i in vi], [], [tuple(remap[i] for i in Fb_[t]) for t in tris])
        uvl = me.uv_layers.new(name="UV0")
        for loop in me.loops:
            uvl.data[loop.index].uv = tuple(UV_[vi[loop.vertex_index]])
        for pg in me.polygons:
            pg.use_smooth = True
        out[kind].append((tris, me, float(hi - lo)))
    return out


ISL = body_island_meshes()
FANG_VC = {}


def fang_vertex_colours(me, L, key):
    """STEP 3: root-to-tip dirt as vertex colours (canonical z: 0 at the root, L at the tip): dark dirty brown at the root,
    white (= the material as is) from 75 % up. Data: kit/vertex_colors/fangs.json, per island vertex in island order."""
    ca = me.color_attributes.new("Col", 'FLOAT_COLOR', 'POINT')
    cols = []
    for i, v in enumerate(me.vertices):
        t = min(1.0, max(0.0, (v.co.z / max(L, 1e-6) - 0.05) / 0.7)); t = t * t * (3 - 2 * t)
        c = [0.2 + 0.8 * t, 0.15 + 0.85 * t, 0.09 + 0.91 * t]
        ca.data[i].color = (*c, 1.0); cols.append([round(x, 3) for x in c])
    FANG_VC[key] = cols
fang_mat = DB.base_material(D, name="TrollFang_dirtyyellow", tint=(0.62, 0.45, 0.22))   # instance tint on a copy of the Troll material
_fb = fang_mat.node_tree.nodes["Principled BSDF"]                  # STEP 3: x vertex colour (root dirt)
if _fb.inputs["Base Color"].links:
    _lk = _fb.inputs["Base Color"].links[0]
    _ca = fang_mat.node_tree.nodes.new("ShaderNodeAttribute"); _ca.attribute_type = 'GEOMETRY'; _ca.attribute_name = "Col"
    _fm = fang_mat.node_tree.nodes.new("ShaderNodeMix"); _fm.data_type = 'RGBA'; _fm.blend_type = 'MULTIPLY'; _fm.inputs[0].default_value = 1.0
    fang_mat.node_tree.links.new(_lk.from_socket, _fm.inputs[6]); fang_mat.node_tree.links.new(_ca.outputs["Color"], _fm.inputs[7])
    fang_mat.node_tree.links.new(_fm.outputs[2], _fb.inputs["Base Color"])
for kind, lst in ISL.items():
    for i, (tris, me, L_) in enumerate(lst):
        me.materials.append(fang_mat)
        fang_vertex_colours(me, L_, f"{kind}{i}")
        ME[f"{kind}{i}"] = me
print("FANG ISLANDS", {k: [(len(t), round(L_, 3)) for t, _, L_ in v] for k, v in ISL.items()})
import island_parts as IP
BRANCH_SRC = {}
BRANCH_RECIPE = {"saturation": 0.2, "multiply": [0.17, 0.145, 0.115], "emission": "off", "glossiness": 0.15,
                 "how": "on our copy of Elder_mat: _MainTex texels -> HSV saturation x0.2 -> x multiply (read back + rewrite the texture "
                        "copy once, or a tint shader); _Color stays white"}
_bi = json.load(open(os.path.join(SUB, "kit_tools", "branch_parts_index.json")))
for n, cell in enumerate((1, 3, 4, 6)):          # Elder islands 0, 2, 3, 5 on branch_parts_sheet.png: bare forked dead-wood limbs
    e = _bi[cell - 1]
    me, info = IP.island_mesh(P, e["key"], e["tris"], f"branch{n}")
    bm2 = me.materials[0].copy(); bm2.name = "V_Elder_branch_darkened"
    for nd in bm2.node_tree.nodes:
        if nd.type == 'MIX' and getattr(nd, "blend_type", "") == 'MULTIPLY':
            nd.inputs[7].default_value = (1.0, 1.0, 1.0, 1)            # STEP 3: the tint moves to the recipe multiply below
    _bb = bm2.node_tree.nodes["Principled BSDF"]                     # STEP 3: desaturate (pink out) + weathered grey-brown, matte
    if _bb.inputs["Base Color"].links:
        _lk = _bb.inputs["Base Color"].links[0]
        _hs = bm2.node_tree.nodes.new("ShaderNodeHueSaturation"); _hs.inputs["Saturation"].default_value = BRANCH_RECIPE["saturation"]
        bm2.node_tree.links.new(_lk.from_socket, _hs.inputs["Color"])
        _tm = bm2.node_tree.nodes.new("ShaderNodeMix"); _tm.data_type = 'RGBA'; _tm.blend_type = 'MULTIPLY'; _tm.inputs[0].default_value = 1.0
        bm2.node_tree.links.new(_hs.outputs["Color"], _tm.inputs[6]); _tm.inputs[7].default_value = (*BRANCH_RECIPE["multiply"], 1)
        bm2.node_tree.links.new(_tm.outputs[2], _bb.inputs["Base Color"])
    _bb.inputs["Roughness"].default_value = 0.85; _bb.inputs["Emission Strength"].default_value = 0.0
    me.materials[0] = bm2
    ME[f"branch{n}"] = me
    BRANCH_SRC[f"branch{n}"] = {"prefab": "gd_king", "renderer": "/gd_king/Visual/gd_king", "mesh": f"gd_king.001 island (sheet cell {cell})",
                                "triangles": e["tris"], "material": "Elder_mat + STEP 3 recipe (desaturate 0.2, x(0.17, 0.145, 0.115), no emission)", "scale_note": "placed with x/y scale 1.9x the length scale",
                                "frame": "root at origin, root->tip +z (computed from the island)", "length_m_in_elder": round(info["length"], 3)}
SRC = {}
SRC.update(BRANCH_SRC)
for kind, lst in ISL.items():
    for i, (tris, me, L_) in enumerate(lst):
        SRC[f"{kind}{i}"] = {"prefab": "Troll", "renderer": "Body", "mesh": f"Troll Body island ({kind}): {len(tris)} triangles",
                             "triangles": tris, "material": "the Troll's own material, instance tint (0.62, 0.45, 0.22)",
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


def seat(ob, d, hi=2.5, clear=CLEAR):
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
        while t < 3.0 and not cut(t):
            t += 0.02
        if not cut(t):
            print("SEAT inside, never reaches the skin", ob.name); return None
        lo = t
    elif not cut(0.0):
        t = 0.0
        while t > -1.5 and not cut(t):
            t -= 0.02
        if not cut(t):
            print("SEAT never touches", ob.name); return None
        lo, hi = t, t + 0.02
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
    ob = bpy.data.objects.new("HB_" + name, ME[k])
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
        if nrm.dot(d) < -0.3 and (v - c).dot(d) < 0 and dist < 0.6:
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
    """STEP 3 (surface only): the conform moves vertices but not their UVs, so the bark smears where the flanks spread. Per vertex:
    dUV = J . dP, with J (2x3) the UV gradient of the ORIGINAL surface around that vertex (averaged over its triangles, normal
    component dropped) - texel density stays constant (the Hive bark texture tiles, so leaving the island is fine). Data:
    kit/deform/lump_uv_offsets.json (add to mesh.uv[i] of the offset clone)."""
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
            Mi = np.linalg.inv(np.column_stack([e1, e2, n]))
            J = np.column_stack([d1, d2, [0.0, 0.0]]) @ Mi
            for vi in (a, b, c):
                Jsum[vi] += J; cnt[vi] += 1
    D_ = np.zeros((len(me.vertices), 2))
    for i in range(len(me.vertices)):
        J = Jsum[i] / max(cnt[i], 1)
        D_[i] = J @ np.array(offs[i][:])
    # smooth the offsets over the mesh (no jumps between neighbours -> no zig-zag streaks) and clamp them
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


def conform(ob, zdir, flat=0.55, cfrac=0.55, ridge=0.3, spread=0.6, seed=0):
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
        hit = BODY.ray_cast(wt + zd * 1.5, -zd, 3.0)
        s_ = hit[0] if hit[0] is not None else BODY.find_nearest(wt)[0]
        h = (wt - s_).dot(zd)
        nz = 0.5 + 0.5 * math.sin(7.3 * w.x + ph[0]) * math.sin(6.1 * w.z + ph[1]) * math.cos(5.7 * w.y + ph[2])
        rr = min(1.0, ((wt - Cc) - zd * (wt - Cc).dot(zd)).length / Rfoot)
        prof = (1 - rr * rr) ** 0.6                                            # dome envelope: flanks slope to the skin, no ledges
        hp = h * (flat + ridge * (nz - 0.5)) * prof if h > 0 else h
        c = _ss(1.0 - cfrac, 1.0, t)
        hp = hp * (1 - c) + (-0.02) * c
        nw = s_ + zd * hp + (wt - s_ - zd * (wt - s_).dot(zd))
        nl = Mi @ nw
        offs.append(nl - v.co); v.co = nl
    me.update()
    OFFSETS[ob.name] = [[round(o.x, 5), round(o.z, 5), round(o.y, 5)] for o in offs]     # Unity mesh space (x, y, z)
    uv_reproject(ob, offs)
    return ob


def lump(name, bone, target, out, s, squash=0.55, stretch=(1.0, 1.0), y_hint=(0, 0, 1), spin=None, sink=0.0, tilt=None, ray=None):
    p, n = surf(target, ray or out)     # ray: the direction that FINDS the spot (default: out); out only leans the lump
    z = (n + V(out).normalized()).normalized()
    ob = place(name, "lump", bone, p, z, y_hint, (s * stretch[0], s * stretch[1], s * squash),
               spin=rng.uniform(0, 6.28) if spin is None else spin)
    if sink > 0:
        SUNK[name] = sink_part(ob, z, sink)
    if CONFORM:
        if target[2] < 4.1:          # the hem row: spread thinner so the crust's lower edge thins out into the painted roots
            conform(ob, z, seed=len(OFFSETS), flat=0.38, spread=1.0)
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


# ---------------------------------------------------------------- the kitbash (v2: no trees in any form; the front is the Hive grown INTO the Troll)
def eye_crease(name, bone, lumps, w, r, slit=1.0, out_bias=(0, 0, 0)):
    """an eye set into the crease between two lumps: aimed at the weighted midpoint of their centres, cast along their averaged
    outward axes onto the union of both lumps (the first surface the ray meets is the crease)"""
    (c1, z1, _, _), (c2, z2, _, _) = lump_frame(lumps[0]), lump_frame(lumps[1])
    out = (z1 + z2 + V(out_bias)).normalized()
    bv = ob_bvh(*lumps)
    loc, n = surf(c1.lerp(c2, w), out, bv)
    if loc is None:
        print("EYE MISS", name); return None
    lo, hi = BOX["eye"]; wd = hi[0] - lo[0]; h = hi[2] - lo[2]
    sc = 2 * r / wd
    return place(name, "eye", bone, loc - n * (0.3 * h * sc), n, (0, 0, 1), (sc, sc * slit, sc * 0.9), at="base", do_seat=False)


# 1. BACK HUMP (Spine2): three Hive lumps over the shoulder blades and behind the neck (kept from v2, trimmed to pay for the front)
HL = []
for i, (tx, tz, out, sc) in enumerate(((-0.55, 5.6, (0, -1, 0.3), 0.8), (0.55, 5.5, (0, -1, 0.25), 0.78), (0.0, 6.05, (0, -0.55, 1.0), 0.62))):
    HL.append(lump(f"hump_lump_{i + 1}", "Spine2", (tx, 0, tz), out, sc, squash=0.7, sink=0.25))
H1, H2, H4 = HL
eye("eye_hump_0", "Spine2", H1, 0.1, 0.25, 0.13)
# (v4: the splayed struts, the ivy curtain and the vine cards are gone - they read as things hung on him; two more sunk lumps
#  continue the hump down the spine instead)
lump("hump_lump_4", "Spine1", (-0.4, 0, 4.75), (-0.2, -1, 0.0), 0.44, squash=0.62, sink=0.35)
lump("hump_lump_5", "Spine1", (0.45, 0, 4.15), (0.25, -1, -0.1), 0.34, squash=0.62, sink=0.35)
# (v5: the writhan root is gone - it hung like a tail)

# 3. THE FRONT CRUST (v4, owner approved sinking): Hive lumps SUNK 20-50 % into the chest and shoulders so the crust grows out of the
#    flesh, overlapping each other, heavier on the troll's left, parted down the sternum around the maw
CRUST = [  # (x, z, scale, (stretch x, y), squash, bone, out direction, sink) - v5: 9 larger lumps, conformed into one growth
    (-1.15, 5.4, 0.56, (1.1, 0.95), 0.62, "Spine2", (-0.35, 0.8, 0.6), 0.3),      # 0 left shoulder mass
    (-0.5, 3.6, 0.24, (1.2, 0.9), 0.62, "Spine1", (-0.1, 1, -0.3), 0.3),           # 1 hem (v6: the deltoid lump stretched with arms up)
    (-0.92, 4.72, 0.58, (1, 1.05), 0.62, "Spine1", (-0.3, 1, 0), 0.3),            # 2 left pec
    (-0.82, 3.98, 0.44, (1, 1), 0.62, "Spine1", (-0.25, 1, -0.2), 0.3),           # 3 left belly
    (-0.66, 5.05, 0.34, (1, 1), 0.62, "Spine2", (-0.1, 1, 0.3), 0.3),             # 4 left collar (off the chin's path)
    (1.05, 5.33, 0.5, (1.1, 0.95), 0.62, "Spine2", (0.3, 0.9, 0.5), 0.3),         # 5 right shoulder
    (0.95, 4.5, 0.38, (1, 1), 0.62, "Spine1", (0.35, 1, 0), 0.3),                 # 6 right pec
    (0.62, 5.13, 0.28, (1, 1), 0.62, "Spine2", (0, 1, 0.2), 0.3),                 # 7 right collar
    (-1.2, 4.15, 0.36, (1, 1), 0.62, "Spine1", (-0.4, 0.9, 0), 0.3),              # 8 left flank (v6: off the armpit)
    (-0.76, 4.4, 0.22, (1, 1), 0.62, "Spine1", (-0.1, 1, 0), 0.3),                # 9 bridges the left lip into the crust
    (0.76, 4.72, 0.2, (1, 1), 0.62, "Spine1", (0.1, 1, 0), 0.3),                  # 10 bridges the right lip
    (-1.45, 4.95, 0.4, (1, 1), 0.62, "Spine2", (-0.6, 0.8, 0.2), 0.3),            # 11 left shoulder-pec junction
    (1.2, 4.88, 0.32, (1, 1), 0.62, "Spine2", (0.5, 0.85, 0), 0.3),               # 12 right shoulder-pec junction
    (0.58, 3.95, 0.22, (1.2, 0.9), 0.62, "Spine1", (0.1, 1, -0.3), 0.3)]           # 13 hem
CL = []
for i, (x, z, sc, st, sq, bone, out, sk) in enumerate(CRUST):
    CL.append(lump(f"crust_lump_{i + 1:02d}", bone, (x, 0, z), out, sc, squash=sq, stretch=st, y_hint=(0, 0, 1), sink=sk,
                   ray=(0, out[1], out[2])))
# 4. THE MAW (Spine1): the crust parts down the sternum; a sunk lump on each side as the lips, leaning OUT (curling away from the slit);
#    ragged Hive-leg slivers point into the slit from both lips; the GuckSack sits deep in the dark slit (the repaint paints the slit dark)
LIPS = []
CONFORM = False          # the lips keep their shape (they curl out of the crust); everything else is conformed
for s in (-1, 1):
    LIPS.append(lump(f"maw_lip_{'l' if s < 0 else 'r'}", "Spine1", (0.3 * s, 0, 4.6), (0.45 * s, 1, 0), 0.34, squash=0.62, stretch=(0.55, 1.6),
                     y_hint=(0, 0, 1), spin=0.0, sink=0.18, ray=(0, 1, 0)))
CONFORM = True
ml, mn = surf((0, 0, 4.6), (0, 1, 0))
SACK = place("maw_gullet_sack", "sack", "Spine1", ml + V((0, 0.03, 0)), (0, 1, 0), (0, 0, 1), (0.09, 0.09, 0.18))
SUNK["maw_gullet_sack"] = sink_part(SACK, (0, 1, 0), 0.6)
nt = 0
FANGS = [k for k in ME if k.startswith("claw")] + [k for k in ME if k.startswith("ttooth")]
for s_, lip in ((-1, LIPS[0]), (1, LIPS[1])):
    c, z, y, x = lump_frame(lip)
    inner = V((-s_, 0, 0)); sx = 1.0 if x.dot(inner) > 0 else -1.0
    lbv = ob_bvh(lip)
    for j, dv in enumerate(sorted(rng.uniform(-0.7, 0.7) for _ in range(5))):
        loc, n = surf(c + x * (sx * 0.15) + y * (dv * 0.42), (z + inner * 0.8).normalized(), lbv)
        if loc is None:
            continue
        CLAWS_ = [q for q in FANGS if q.startswith("claw")]; TEETH_ = [q for q in FANGS if q.startswith("ttooth")]
        k = CLAWS_[nt % len(CLAWS_)] if j % 3 else TEETH_[nt % len(TEETH_)]         # mostly claws, some of his own teeth
        lo_, hi_ = BOX[k]; Lk = hi_[2] - lo_[2]
        Lw = rng.uniform(0.32, 0.5) if k.startswith("claw") else rng.uniform(0.18, 0.26)     # v6: read at full-body distance
        dd = (inner + V((0, rng.uniform(0.1, 0.5), rng.uniform(-0.6, 0.6)))).normalized()
        sc = Lw / Lk
        bend = V((0, 0, -1 if dv > 0 else 1)) if rng.random() < 0.7 else V((0, 1, 0))      # curving along the slit, some forward
        ob = place(f"maw_fang_{nt:02d}", k, "Spine1", loc - dd * Lw * 0.25, None, None, (sc, sc, sc),
                   R=R_axes(bend.cross(dd).normalized(), dd) @ Matrix.Rotation(rng.uniform(-0.4, 0.4), 4, 'Z'),
                   at="origin", do_seat=False)
        nt += 1


# 5. EYES (v4): small (the Troll's own eye is ~0.08-0.1 m radius; these are 0.04-0.12), in tight lopsided clusters, half-sunk in the
#    creases between sunk lumps so the bark is their rim; textured TheHive_Eye with a bright core and a darker rim (see eye_material)
def eye_socket(name, bone, lumps, w, r, slit=1.0, sink=0.5, out_bias=(0, 0, 0)):
    (c1, z1, _, _), (c2, z2, _, _) = lump_frame(lumps[0]), lump_frame(lumps[1])
    out = (z1 + z2 + V(out_bias)).normalized()
    bvl = ob_bvh(*lumps)
    tgt = c1.lerp(c2, w)
    hl = bvl.ray_cast(tgt + out * 25, -out, 60)
    hb = BODY.ray_cast(tgt + out * 25, -out, 60)
    on_skin = hl[0] is None or (hb[0] is not None and (hb[0] - (tgt + out * 25)).length < (hl[0] - (tgt + out * 25)).length)
    loc, n = (hb[0], hb[1]) if on_skin else (hl[0], hl[1])
    if loc is None:
        print("EYE MISS", name); return None
    lo, hi = BOX["eye"]; wd = hi[0] - lo[0]; h = hi[2] - lo[2]; sc = 2 * r / wd
    ob = place(name, "eye", bone, loc - n * (sink * h * sc), n, (0, 0, 1), (sc, sc * slit, sc * 0.9), at="base", do_seat=False)
    if on_skin:
        SUNK[name] = sink_part(ob, n, 0.3)
    return ob


EYES = [("eye_c1_dominant", "Spine2", (CL[0], CL[2]), 0.45, 0.17, 1.0), ("eye_c1_b", "Spine2", (CL[0], CL[11]), 0.3, 0.11, 1.0),
        ("eye_c1_c", "Spine2", (CL[0], CL[11]), 0.5, 0.09, 1.0), ("eye_c1_slit", "Spine2", (CL[2], CL[8]), 0.5, 0.11, 0.35),
        ("eye_c2_a", "Spine2", (CL[5], CL[6]), 0.5, 0.12, 1.0), ("eye_c2_b", "Spine2", (CL[5], CL[7]), 0.5, 0.085, 1.0),
        ("eye_c3_low", "Spine1", (CL[2], CL[3]), 0.5, 0.08, 1.0)]
for name, bone, pair, w, r, sl in EYES:
    eye_socket(name, bone, list(pair), w, r, slit=sl)


# 6. ROOTS (v4): ten small dark roots (catacomb root07 + ThornRoots, darkened instance tint) from the crust's edges; the dense web of
#    finer roots is in the repaint (dark root veins on the skin)
def strand(name, k, bone, a, b, out, thick):
    pa, na = surf(a, out); pb, nb = surf(b, out)
    if pa is None or pb is None:
        print("ROOT MISS", name); return None
    ax = (pb - pa); L = ax.length; ya = ax.normalized()
    nrm = (na + nb).normalized()
    nrm = (nrm - ya * nrm.dot(ya)).normalized()
    if k == "root07":
        zl, yl = ya, nrm; xl = yl.cross(zl)
        R = Matrix((xl, yl, zl)).transposed().to_4x4()
        sc = (thick * 2.2 / 1.221, thick / 0.438, L * 1.05 / 1.612)
    else:
        yl, zl = ya, nrm; xl = yl.cross(zl)
        R = Matrix((xl, yl, zl)).transposed().to_4x4()
        sc = (thick / 0.004, L * 1.05 / 0.0152, thick / 0.004)
    ob = place(name, k, bone, pa.lerp(pb, 0.5), None, None, sc, at="center", seat_dir=nrm, R=R)
    SUNK[name] = sink_part(ob, nrm, 0.45 if k == "root07" else 0.3)   # root07 is an open shell: bury its rim
    return ob


WEB = [("root07", "Spine1", (-0.7, 0, 3.8), (-0.55, 0, 3.2), (0, 1, 0), 0.06), ("thorn", "Spine1", (-1.15, 0, 3.9), (-1.3, 0, 3.2), (-0.3, 1, 0), 0.05),
       ("root07", "Spine1", (0.95, 0, 4.25), (0.85, 0, 3.35), (0.2, 1, 0), 0.055), ("thorn", "Spine1", (0.2, 0, 3.9), (0.3, 0, 3.25), (0, 1, 0), 0.045),
       ("thorn", "Spine2", (-0.4, 0, 5.75), (-0.3, 0, 6.2), (0, 1, 0.3), 0.04), ("root07", "Spine2", (0.5, 0, 5.6), (0.35, 0, 6.1), (0, 1, 0.3), 0.045),
       ("root07", "LeftArm", (-2.0, 0, 5.15), (-2.7, 0, 4.9), (0, 1, 0), 0.06), ("thorn", "LeftArm", (-1.9, 0.55, 5.2), (-2.6, 0.55, 4.85), (0, 1, 0.3), 0.045),
       ("root07", "RightArm", (1.45, 0.3, 5.5), (2.1, 0.3, 5.15), (0, 0.3, 1), 0.055), ("root07", "Spine1", (-1.2, 0, 4.2), (-1.3, 0, 3.7), (0, 1, 0), 0.05)]
for i, (k, bone, a, b, out, th) in enumerate(WEB):
    if k == "root07":
        strand(f"web_{k}_{i:02d}", k, bone, a, b, out, th)


# 6b. BRANCHES (v6, owner: "yes, with branches"): bare Elder dead-wood forks rooted INTO the back hump and the left shoulder
#     crust, angled up and back, asymmetric; rigid on the host's bone
def branch(name, k, host, d, length, spin):
    hob = bpy.data.objects["HB_" + host]
    d = V(d).normalized()
    c = sum(world_verts(hob)[0], V()) / len(hob.data.vertices)
    loc, n = surf(c, d, ob_bvh(hob))
    if loc is None:
        print("BRANCH MISS", name); return None
    lo_, hi_ = BOX[k]; sc = length / (hi_[2] - lo_[2])
    hb = next(q["bone"] for q in PARTS if q["ob"] is hob)
    return place(name, k, hb, loc - d * 0.3, None, None, (sc * 1.9, sc * 1.9, sc),      # thickened x1.9: gnarled limbs, not twigs
                 R=R_axes(V((1, 0, 0)) if abs(d.x) < 0.8 else V((0, 1, 0)), d) @ Matrix.Rotation(spin, 4, 'Z'), at="origin", do_seat=False)


for name, k, host, d, L, sp in (("branch_back_l", "branch0", "hump_lump_1", (-0.45, -0.75, 1.0), 2.7, 0.3),
                                ("branch_back_r", "branch1", "hump_lump_2", (0.6, -0.95, 0.55), 1.9, -0.6),
                                ("branch_neck", "branch3", "hump_lump_3", (0.1, -0.7, 1.0), 1.5, 1.3),
                                ("branch_shoulder_l", "branch2", "crust_lump_01", (-0.65, -0.35, 1.0), 1.7, 2.1)):
    branch(name, k, host, d, L, sp)

# 7. (v4) no waist ring / vine skirt: the repaint carries the bark down over the hips where the loincloth was; one sunk lump on
#    the left hip ties the crust to it
lump("crust_lump_hip", "Spine0", (-0.85, 0, 3.25), (-0.35, 1, -0.15), 0.3, squash=0.6, sink=0.4)


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
att = {i for i, p in enumerate(PARTS) if p["contact"] <= 0.012 or p["pairs_body"] > 0}   # sunk parts cut the skin: attached
changed = True
while changed:
    changed = False
    for i, p in enumerate(PARTS):
        if i in att:
            continue
        for j in list(att):
            if p["bv"].overlap(PARTS[j]["bv"]) or min(PARTS[j]["bv"].find_nearest(v)[3] for v in world_verts(p["ob"])[0][::7]) < 0.005:
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
attach = {"_about": "ASSET-001 Hive Brute kitbash: every add-on is an UNMODIFIED vanilla mesh + its vanilla material on one Troll bone. "
          "For each part: create an ANCHOR as a child of `parent` with localPosition/localRotation/localScale (Runic armor_attach "
          "convention: localScale 1/130 cancels the Troll's x130 bone chain, localRotation undoes the bone's REST rotation, so the anchor "
          "is world-aligned in the rest pose), then a child carrying the vanilla mesh with `part_localRotation` / `part_localScale` "
          "(Unity axes) at position 0. Units: Unity, the Troll prefab's REST pose (= bind turned 180 deg about Y).",
          "_donor": "Troll (1.0.21, bundle c4210710)", "_base_tris": {"Body": TRIS_BODY, "Hair": TRIS_HAIR}, "_sources": SRC}
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
                                 "localScale": [round(1 / 130, 7)] * 3,
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
json.dump({"_about": "ASSET-001 STEP 3: per-vertex UV0 offsets for the conformed Hive lumps (surface only). After adding lump_offsets.json "
                     "to the clone's vertices, add uv_offsets[i] to mesh.uv[i] (same vertex order). Keeps the bark texel density where "
                     "the lump flanks were spread (the Hive bark texture tiles).", **UV_OFFSETS},
          open(os.path.join(KIT, "deform", "lump_uv_offsets.json"), "w"))
os.makedirs(os.path.join(KIT, "vertex_colors"), exist_ok=True)
json.dump({"_about": "ASSET-001 STEP 3: fang vertex colours (RGB, multiply the material's albedo): dark dirty root -> white tip. Keys = "
                     "fang source islands (see attach.json _sources: Troll Body triangles); one colour per island vertex in the order of "
                     "the sorted unique vertex indices of those triangles. Runtime: mesh.colors + a shader that multiplies vertex colour "
                     "(or bake into a texture copy).", **FANG_VC}, open(os.path.join(KIT, "vertex_colors", "fangs.json"), "w"))
for p in PARTS:
    attach["HB_" + p["name"]] = attach_entry(p, p["bone"])
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

# ---------------------------------------------------------------- EARLY REPAINT of the Troll's own texture (masks + recipe; preview only)
import troll_repaint as TR
T_RP = time.time()
RP = os.path.join(KIT, "repaint"); os.makedirs(os.path.join(RP, "preview"), exist_ok=True)
SZ = 2048          # v5: computed at 2x; the shipped mask is box-filtered to 1024 (anti-aliased veins/roots)
SZO = 1024
Vb, Fb, UVb, mb = D.mesh_data("Body")
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
nz = TR.value_noise3(Pv, 0.5, 11) * 0.35 + TR.value_noise3(Pv, 0.16, 12) * 0.15 + TR.value_noise3(Pv, 0.05, 13) * 0.05
bark_v = 1 - TR.smoothstep(0.0, 0.75, dist + nz)
# the crust runs down over the hips where the loincloth was (Hair hidden), ragged lower edge
pel = (TR.smoothstep(3.6, 3.25, Pv[:, 2]) * TR.smoothstep(2.45, 2.8, Pv[:, 2] + nz * 0.7) * TR.smoothstep(1.55, 1.15, np.abs(Pv[:, 0])))
# (v6: the hip band read as "bark shorts" - the hips go back to sickly skin; only the sunk hip lump carries crust there)
# extremities: forearms/hands (|x| beyond the elbow) and shins/feet
ext_v = np.maximum(TR.smoothstep(2.3, 4.3, np.abs(Pv[:, 0])) * (Pv[:, 2] > 2.8), TR.smoothstep(2.2, 0.4, Pv[:, 2]))


def nearest(pt):
    loc, n, _, _ = BODY.find_nearest(V(tuple(pt)))
    return (np.array(loc[:]), np.array(n[:])) if loc is not None else (None, None)


ml_ = np.array(ml[:])
eye_locs = [np.array((p["ob"].matrix_world.translation)[:]) for p in PARTS if p["k"] == "eye"]
_r = np.random.default_rng(5)
# v5 veins: thin, tapering, branching, smoothed (no straight runs), fading out within ~0.5-0.8 m of the mouth and the eyes
vein_starts = [(ml_ + np.array([0.2 * sx, 0, dz]), 0.011, (sx, 0, dz * 1.8 + _r.uniform(-0.7, 0.7))) for sx in (-1, 1)
               for dz in (-0.5, -0.25, 0.0, 0.25, 0.5)]
vein_starts += [(e, 0.009, (_r.uniform(-1, 1), 0, _r.uniform(-1, 1))) for e in eye_locs for _ in range(2)]
veins = TR.smooth_curves(TR.walk_curves(nearest, vein_starts, 1, 0.75, 0.03, 21, branch=2.0, persist=0.35, jitter=0.45),
                         nearest, 2)
root_starts = []
for p in PARTS:
    if p["k"] == "lump" and p["bone"] in ("Spine1", "Spine2", "LeftArm", "RightArm") and p["name"].startswith(("crust", "maw_lip", "hump")):
        c = np.array((p["ob"].matrix_world @ anchor_pt("lump", "center"))[:])
        out = c - np.array([0.0, 0.2, 4.7]); out[1] = 0; out /= (np.linalg.norm(out) + 1e-9)
        root_starts.append((c, 0.03, tuple(out + np.array([0, 0, -0.5]))))
roots_c = TR.walk_curves(nearest, root_starts, 3, 1.8, 0.05, 31, bias=(0, 0, -1), branch=0.8)
vein_m = TR.curves_mask(pos, veins, fade=1.2)
halo = TR.curves_mask(pos, [(pts, w0 * 3.5) for pts, w0 in veins], fade=1.6)     # the soft glow around each vein
root_m = TR.curves_mask(pos, roots_c)
mouth_v = (TR.smoothstep(0.19, 0.09, np.abs(Pv[:, 0])) * TR.smoothstep(3.9, 4.05, Pv[:, 2]) * TR.smoothstep(5.3, 5.15, Pv[:, 2])
           * (Pv[:, 1] > 0.5))
mouth_core = (TR.smoothstep(0.05, 0.0, np.abs(Pv[:, 0])) * TR.smoothstep(4.15, 4.4, Pv[:, 2]) * TR.smoothstep(4.95, 4.75, Pv[:, 2])
              * (Pv[:, 1] > 0.5))
glow = np.zeros((SZ, SZ)); glow[valid] = mouth_core
vein_m = np.maximum(vein_m, glow * 0.35)          # the deep glow in the slit rides the same emission mask
mask = np.zeros((SZ, SZ, 4))
mask[..., 0][valid] = bark_v
mask[..., 1][valid] = ext_v
mask[..., 2] = np.maximum(vein_m, 0.3 * halo)
dark = np.zeros((SZ, SZ)); dark[valid] = mouth_v
mask[..., 3] = np.maximum(root_m * 0.92, dark)
mask = TR.dilate_fill(mask, valid, 8)
hk.save_array(os.path.join(RP, "troll_hive_mask.png"), mask.reshape(SZO, SZ // SZO, SZO, SZ // SZO, 4).mean((1, 3)))
# the recipe, and the repainted albedo + emission (PREVIEW ONLY: derived from vanilla pixels)
REC = {"about": "ASSET-001 early repaint recipe (troll_repaint.py). Mask = kit/repaint/troll_hive_mask.png in the Troll Body's UV0 "
                "(R bark, G extremity darkening, B blight veins = emission, A dark roots + mouth). Colours are linear multipliers "
                "applied to the texture's stored (sRGB-encoded) texel values, as the runtime reads them back with GetPixels. The vanilla "
                "luminance is kept everywhere (lum / mean lum), so the anatomy still reads.",
       "sick_skin": [0.34, 0.36, 0.29], "extremity_darken": 0.5, "bark_tint": [0.85, 0.6, 0.3], "infection_margin_darken": 0.45,
       "bark_texture": "olivetree_trunk01 (TheHive_Mat _MainTex), triplanar in rest-pose metres, tile 1.2 m",
       "root_colour": [0.03, 0.025, 0.02], "vein_albedo": [0.05, 0.06, 0.02], "blight_colour": [0.42, 0.55, 0.12],
       "emission_strength_preview": 0.9, "mask_size": "1024 (computed at 2048, box-filtered)", "blight_emission": "BlightGlow, driven by the biome tint at runtime",
       "mouth_colour": [0.01, 0.008, 0.006], "uv_note": "the Troll's UVs are mostly mirrored, so the paint is symmetric"}
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
px = ((uu / 1.2) % 1.0 * (bw - 2)).astype(int); py = ((vv / 1.2) % 1.0 * (bh - 2)).astype(int)
BKs = (BK[py, px] + BK[py + 1, px] + BK[py, px + 1] + BK[py + 1, px + 1]) * 0.25
seam = TR.smoothstep(0.14, 0.02, np.abs(Pv[:, 0])) * (Pv[:, 2] > 2.7)          # v6: the mirrored halves meet on x = 0
lum_n_v = lum_n[valid] * (1 - seam) + 0.92 * seam                                   # blend the vanilla shading across the seam
lum_n = lum_n.copy(); lum_n[valid] = lum_n_v
barkcol = BKs * np.array(REC["bark_tint"]) * (0.45 + 0.55 * np.clip(lum_n[valid], 0, 2))[:, None]
sick = np.clip(lum_n[valid], 0, 2.5)[:, None] * np.array(REC["sick_skin"])
colv = sick * (1 - bark_v[:, None]) + barkcol * bark_v[:, None]
moss_v = TR.smoothstep(0.35, 0.8, nrm[valid][:, 2]) * TR.smoothstep(-0.05, 0.25, TR.value_noise3(Pv, 0.45, 51)) * bark_v * 0.6
colv = colv * (1 - moss_v[:, None]) + np.array([0.2, 0.25, 0.1]) * np.clip(lum_n[valid], 0.4, 1.4)[:, None] * moss_v[:, None]
MOSS = np.zeros((SZ, SZ, 4)); MOSS[..., 3] = 1; MOSS[..., 0][valid] = moss_v
MOSS = TR.dilate_fill(MOSS, valid, 8)
hk.save_array(os.path.join(RP, "troll_moss_mask.png"), MOSS.reshape(SZO, SZ // SZO, SZO, SZ // SZO, 4).mean((1, 3)))
REC["moss"] = {"mask": "kit/repaint/troll_moss_mask.png (R = moss amount, Body UV0)", "colour": [0.2, 0.25, 0.1],
               "how": "albedo = lerp(albedo, moss_colour x vanilla luminance, R)"}
json.dump(REC, open(os.path.join(RP, "repaint.json"), "w"), indent=1)
colv *= (1 - REC["extremity_darken"] * ext_v)[:, None]
colv *= (1 - REC["infection_margin_darken"] * 4 * bark_v * (1 - bark_v))[:, None]     # dark, infected margin where bark meets skin
rm = mask[..., 3][valid][:, None]
colv = colv * (1 - rm) + np.array(REC["root_colour"]) * rm
vm = vein_m[valid][:, None]
colv = colv * (1 - vm) + np.array(REC["vein_albedo"]) * vm
OUTA = A0.copy(); OUTA[..., :3][valid] = colv
OUTA = TR.dilate_fill(OUTA, valid, 8); OUTA[..., 3] = A0[..., 3]
hk.save_array(os.path.join(RP, "preview", "troll_repainted_albedo.png"), OUTA)
EB = mask[..., 2]
EM = np.zeros((SZ, SZ, 4)); EM[..., 0] = EB * REC["blight_colour"][0]; EM[..., 1] = EB * REC["blight_colour"][1]
EM[..., 2] = EB * REC["blight_colour"][2]; EM[..., 3] = 1
hk.save_array(os.path.join(RP, "preview", "troll_blight_emission.png"), EM)


def repaint_material():
    m = DB.base_material(D, name="TrollRepaint")
    nt = m.node_tree
    for nd in nt.nodes:
        if nd.type == 'TEX_IMAGE' and nd.image and nd.image.name.startswith("troll__MainTex"):
            nd.image = bpy.data.images.load(os.path.join(RP, "preview", "troll_repainted_albedo.png"))
    for nd in nt.nodes:
        if nd.type == 'MIX' and nd.blend_type == 'MULTIPLY':
            nd.inputs[7].default_value = (1, 1, 1, 1)       # the albedo already carries the colour
    te = nt.nodes.new("ShaderNodeTexImage"); te.image = bpy.data.images.load(os.path.join(RP, "preview", "troll_blight_emission.png"))
    te.image.colorspace_settings.name = 'Non-Color'
    b_ = nt.nodes["Principled BSDF"]
    nt.links.new(te.outputs["Color"], b_.inputs["Emission Color"]); b_.inputs["Emission Strength"].default_value = REC["emission_strength_preview"]
    return m


summary["repaint"] = {"mask": "kit/repaint/troll_hive_mask.png", "recipe": "kit/repaint/repaint.json", "size": SZ,
                      "texels_used": int(valid.sum()), "bark_cover_pct": round(float((bark_v > 0.5).mean() * 100), 1),
                      "vein_curves": len(veins), "root_curves": len(roots_c), "seconds": round(time.time() - T_RP, 1)}
print("REPAINT", summary["repaint"])

# ---------------------------------------------------------------- scene, previews
col = bpy.data.collections.new("COL_HiveKitbash"); bpy.context.scene.collection.children.link(col)
for p in PARTS:
    for c in p["ob"].users_collection:
        c.objects.unlink(p["ob"])
    col.objects.link(p["ob"])
colb = bpy.data.collections.new("COL_TrollBase_reference_not_shipped"); bpy.context.scene.collection.children.link(colb)
body_ob, hair_ob = DB.add_base(D, hair=True, collection=colb)
hair_ob.hide_render = True
DB.weld_normals(body_ob.data)            # v6: smooth across the mirrored-UV split (the sternum seam was a shading split)
RPMAT = repaint_material()
VANMAT = body_ob.data.materials[0]
body_ob.data.materials[0] = RPMAT
DB.lights_and_world(scale=4.0, aim=(0, 0, 3.7))
DB.setup_render(900, 1000)
bpy.ops.wm.save_as_mainfile(filepath=os.path.join(KIT, "HiveBrute_kitbash.blend"))
shots = {}


def shot(name, target, dist, az, el, lens=85, w=900, h=1000):
    bpy.context.scene.render.resolution_x, bpy.context.scene.render.resolution_y = w, h
    DB.camera(target, dist, az, el, lens=lens)
    pth = os.path.join(PREV, name + ".png"); DB.render(pth); shots[name] = pth


CEN = (0, 0.2, 3.75)
views = (("front", 0, 6, 33), ("side", 90, 6, 26), ("back", 180, 6, 33), ("34", 35, 12, 31))
for nm, az, el, dist in views:
    shot(f"kit_{nm}", CEN, dist, az, el)
shot("close_head", (0, 1.0, 6.9), 9, 28, 10, w=900, h=800)
_ed = bpy.data.objects["HB_eye_c1_dominant"].matrix_world.translation
shot("close_eyes_1to1", tuple(_ed), 4.0, 12, 6, w=900, h=700)
shot("close_chest_mouth", (0, 1.2, 4.6), 9, 18, 4, w=900, h=900)
shot("close_chest_front", (-0.2, 1.2, 4.75), 8.5, 0, 3, w=1000, h=900)
shot("close_back_growth", (0, -1.0, 5.0), 13, 155, 14, w=900, h=900)
col.hide_render = True
shot("base_repaint_34", CEN, 31, 35, 12)
shot("base_repaint_front", CEN, 33, 0, 6)
shot("base_repaint_back", CEN, 33, 180, 6)
body_ob.data.materials[0] = VANMAT
for nm, az, el, dist in views:
    shot(f"base_{nm}", CEN, dist, az, el)
tint = tuple(DB.srgb2lin(c) for c in (0.5, 0.1, 0.8))
body_ob.data.materials[0] = DB.base_material(D, name="TrollTint_BlackForest", tint=tint)
shot("base_tint_blackforest_front", CEN, 33, 0, 6)
shot("base_tint_blackforest_34", CEN, 31, 35, 12)
body_ob.data.materials[0] = RPMAT
col.hide_render = False
fig, fh = hk.figure(0, -3.4)
bpy.context.scene.render.resolution_x, bpy.context.scene.render.resolution_y = 1300, 900
DB.camera((0, -0.6, 3.85), 60, 90, 0, ortho=12.5)
pth = os.path.join(PREV, "lineup_1.8m.png"); DB.render(pth); shots["lineup"] = pth
bpy.data.objects.remove(fig)
hk.grid([shots["kit_front"], shots["kit_side"], shots["kit_back"], shots["kit_34"]], 4, os.path.join(PREV, "kit_sheet.png"))
hk.grid([shots["base_front"], shots["base_side"], shots["base_back"], shots["base_34"]], 4, os.path.join(PREV, "base_sheet.png"))
# ---------------------------------------------------------------- STEP 3 FINAL-LOOK RENDERS
import final_look as FL
FL.final_set(globals(), name_prefix="final", cen=CEN, views=views, head=((0, 1.0, 6.9), 9, 28, 10), wtf=((-0.2, 1.2, 4.75), 8.5, 18, 3),
             branches=((0, -1.0, 5.0), 13, 155, 14), read10=((0, 0.2, 3.6), 10.0, 0, 3), scale=4.0, aim_z=3.7,
             body=body_ob, rpmat=RPMAT, col=col)
# ---------------------------------------------------------------- POSE TEST: the Troll skinned with its own donor weights, the rigid parts on
# their posed bones. Poses as world-space rotations about each joint's rest position (FK down the chain), linear blend skinning.
T_PT = time.time()
TF = D.T
def parent_of(b):
    return TF[b]["parent"]
def rot_about(pivot, R3):
    return Matrix.Translation(V(pivot)) @ R3.to_4x4() @ Matrix.Translation(-V(pivot))
def Rw(axis, deg):
    return Matrix.Rotation(math.radians(deg), 3, V(axis))
POSES = {
    "arms raised": {"LeftArm": Rw((0, 1, 0), 70), "RightArm": Rw((0, 1, 0), -70)},
    "elbows bent 120": {"LeftForeArm": Rw((0, 0, 1), -120), "RightForeArm": Rw((0, 0, 1), 120)},
    "crouch": {"_root": V((0, 0, -1.0)), "Spine0": Rw((1, 0, 0), -22), "LeftUpLeg": Rw((1, 0, 0), 62), "RightUpLeg": Rw((1, 0, 0), 62),
               "LeftLeg": Rw((1, 0, 0), -95), "RightLeg": Rw((1, 0, 0), -95), "LeftFoot": Rw((1, 0, 0), 33), "RightFoot": Rw((1, 0, 0), 33)},
    "head turned, chin down": {"Head": Rw((0, 0, 1), 45) @ Rw((1, 0, 0), -30)}}
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
    if worst[0] > 1.5 and worst[1] > 0.06:
        rep["stretched"].append(f"{p['name']} (visible edge x{worst[0]:.2f}, +{worst[1] * 100:.0f} cm)")
    bv = BVHTree.FromPolygons(vs, p["F"])
    rep["pairs"] += len(bv.overlap(PB))
    samp = vs[::max(1, len(vs) // 24)]
    f_now = sum(inside_b(v, PB) for v in samp) / len(samp)
    gap = min(PB.find_nearest(v)[3] for v in vs[::3])
    if f_now - p["rest_inside"] > 0.3:
        rep["poke_through"].append(f"{p['name']} ({p['rest_inside']:.0%} -> {f_now:.0%} inside)")
    if p["rest_inside"] > 0.05 and f_now < 0.02 and gap > 0.03:
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
    DB.camera((0, 0.2, 4.1), 30, 30, 10, lens=85)
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
        e["skin"] = ("weights transferred at runtime from the 4 nearest Troll Body vertices (inverse distance), rest pose, then "
                     f"blended {p.get('wsmooth', WSMOOTH_OWN):.2f} per-vertex + {1 - p.get('wsmooth', WSMOOTH_OWN):.2f} the part's average")
        e["weight_own_share"] = p.get("wsmooth", WSMOOTH_OWN)
        e["head_bones_masked"] = bool(p.get("head_masked", False))
    attach["HB_" + p["name"]] = e
json.dump(attach, open(os.path.join(KIT, "attach.json"), "w"), indent=1)
summary["pose_test"] = pose_report
summary["seconds"]["pose_test"] = round(time.time() - T_PT, 1)
summary["seconds"]["total_incl_renders"] = round(time.time() - T0, 1)
json.dump(summary, open(os.path.join(KIT, "fit.json"), "w"), indent=1)
summary["figure_height_m"] = round(fh, 3)
json.dump(summary, open(os.path.join(KIT, "fit.json"), "w"), indent=1)
print("DONE", summary["seconds"])
