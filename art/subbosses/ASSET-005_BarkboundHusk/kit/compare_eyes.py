"""close_eye_options.png: the vanilla eye candidates, each seated in a TheHive `low` lump, close up (top row) and at ~7 m (bottom).
A Hatchling eyeball + TheHive_Eye | B Unity built-in Sphere + TheHive_Eye (the Hive's own EYE; preview uses a 24x16 UV sphere,
the built-in at runtime) | C GreydwarfEye (orb + bark shell, own materials) | D GreydwarfEye shell + orb with TheHive_Eye |
E Eye_gib (Gjall eye) | F Morkhalla_Eye1 low.  Run: heavy.sh 4G sb-eyes blender -b --factory-startup -P compare_eyes.py -- <kit dir>"""
import bpy, bmesh, sys, os, json, math
from mathutils import Vector, Matrix, Euler
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "..", "kit_tools_b")); sys.path.insert(0, os.path.join(HERE, "..", "..", "donor_tools_004-006"))
import hivefit as H
OUT = sys.argv[sys.argv.index("--") + 1]; PR = os.path.join(OUT, "_ref", "parts"); PV = os.path.join(OUT, "previews"); os.makedirs(PV, exist_ok=True)
bpy.ops.wm.read_factory_settings(use_empty=True)
H.setup_eevee(1500, 380); H.lights_and_world(aim=(0, 0, 0.0))
L = lambda k: json.load(open(os.path.join(PR, k + ".json")))
hive = L("hivelump"); hive_mat = H.part_material(hive["materials"][0], PR, "TheHive_Mat", moss=True)
em = L("hiveeye")["materials"][0]; eye_mat = H.part_material(em, PR, "TheHive_Eye", emit=em["colors"]["_EmissionColor"][:3])


def norm_bm(P, size, M=Matrix.Identity(4)):
    vs = [H.u2b(v) for v in P["verts"]]; c = sum(vs, Vector()) / len(vs); e = max(max(abs((v - c)[k]) for v in vs) for k in range(3))
    bm = H.part_bm(P, [(v - c) / e * size for v in vs]); bmesh.ops.transform(bm, matrix=M, verts=bm.verts)
    return bm


def obj(bm, mats, name, x):
    ob = H.bm_object(bm, name, mats); ob.location.x = x; return ob


R_FACE = Euler((math.radians(-90), 0, 0)).to_matrix().to_4x4()      # face -Y (toward the camera)
for i, lab in enumerate("ABCDEF"):
    x = (i - 2.5) * 0.55
    obj(norm_bm(hive, 0.2, Matrix.Translation((0, 0.1, 0)) @ Euler((0.4, 1.2, 0.3)).to_matrix().to_4x4()), [hive_mat], "lump" + lab, x)
    if lab == "A":
        P = L("hatcheyes"); vs = [H.u2b(v) for v in P["verts"]]
        obj(norm_bm(P, 0.06, Matrix.Translation((0, -0.08, 0))), [eye_mat], "eyeA", x)   # (both eyeballs of the mesh, as a pair)
    elif lab == "B":
        bm = bmesh.new(); bmesh.ops.create_uvsphere(bm, u_segments=24, v_segments=16, radius=0.065)
        bmesh.ops.translate(bm, vec=Vector((0, -0.08, 0)), verts=bm.verts); obj(bm, [eye_mat], "eyeB", x)
    elif lab in "CD":
        S = L("gdeye_shell"); O = L("gdeye_orb")
        sh = norm_bm(S, 0.1, Matrix.Translation((0, -0.07, 0)) @ R_FACE)
        obj(sh, [H.part_material(S["materials"][0], PR, "gdshell" + lab)], "shell" + lab, x)
        om = O["materials"][0]
        m = H.part_material(om, PR, "gdorb", emit=om["colors"]["_EmissionColor"][:3]) if lab == "C" else eye_mat
        obj(norm_bm(O, 0.05, Matrix.Translation((0, -0.1, 0)) @ R_FACE), [m], "orb" + lab, x)
    elif lab == "E":
        P = L("eye_gib"); obj(norm_bm(P, 0.07, Matrix.Translation((0, -0.08, 0))), [H.part_material(P["materials"][0], PR, "gjall", emit_map=True)], "eyeE", x)
    elif lab == "F":
        P = L("mork_eye_low"); obj(norm_bm(P, 0.08, Matrix.Translation((0, -0.1, 0)) @ R_FACE), [H.part_material(P["materials"][0], PR, "mork")], "eyeF", x)
for nm, dist, lens in (("close", 3.2, 55), ("far", 7.0, 55)):
    H.camera((0, 0, 0.0), dist, 0, 8, lens=lens * (1 if nm == "close" else 2.2 / 1.0 * 0.0 + 1))
    bpy.context.scene.camera.data.type = 'ORTHO'; bpy.context.scene.camera.data.ortho_scale = 3.5 if nm == "close" else 8.0
    H.render(os.path.join(OUT, "_cmp_" + nm + ".png"))
a = H.img_array if hasattr(H, "img_array") else None
import numpy as np
def arr(p):
    im = bpy.data.images.load(p); w, h = im.size; x = np.empty(w * h * 4, np.float32); im.pixels.foreach_get(x); return x.reshape(h, w, 4)
A = arr(os.path.join(OUT, "_cmp_close.png")); B = arr(os.path.join(OUT, "_cmp_far.png"))
S = np.concatenate([B, A], axis=0); h, w = S.shape[:2]
im = bpy.data.images.new("cmp", w, h, alpha=True); im.pixels.foreach_set(S.ravel()); im.filepath_raw = os.path.join(PV, "close_eye_options.png"); im.file_format = 'PNG'; im.save()
os.remove(os.path.join(OUT, "_cmp_close.png")); os.remove(os.path.join(OUT, "_cmp_far.png"))
print("EYES done")
