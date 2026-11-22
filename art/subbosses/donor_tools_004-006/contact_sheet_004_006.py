"""Contact sheet for ASSET-004..006, made to match contact_sheet_001-003.png (tools_001-003/contact_sheet_001_003.py):
the same scene (hive_kit.scene_setup: EEVEE, grey world, key + fill suns), the same 1.8 m figure (hive_kit.figure) on the
left, the same orthographic front three-quarter row with a label under each model, and the same pure side row (heads
right), fitted to the projected vertices. hive_kit is imported read-only from tools_001-003.

blender -b --factory-startup -P contact_sheet_004_006.py -- <art/subbosses dir>
Writes <dir>/contact_sheet_004-006.png.
The Husk's donor (Draugr) bind pose faces -Y, so its mesh copy is turned 180 deg about Z here so all three face +Y.
"""
import bpy, sys, os, math
import numpy as np
from mathutils import Vector, Matrix

ROOT = sys.argv[sys.argv.index("--") + 1]
sys.path.insert(0, os.path.join(ROOT, "tools_001-003"))
import hive_kit as hk

bpy.ops.wm.read_factory_settings(use_empty=True)
ITEMS = [("ASSET-004_EyeblightSeer", "EyeblightSeer", "ASSET-004\nEyeblight Seer\n(Greydwarf_Shaman)", 0.0),
         ("ASSET-005_BarkboundHusk", "BarkboundHusk", "ASSET-005\nBarkbound Husk\n(Draugr)", math.pi),
         ("ASSET-006_Broodhusk", "Broodhusk", "ASSET-006\nBroodhusk\n(Seeker)", 0.0)]
models = []
for folder, name, label, rot in ITEMS:
    with bpy.data.libraries.load(os.path.join(ROOT, folder, name + ".blend"), link=False) as (src, dst):
        dst.objects = [n for n in src.objects if n == name]
    ob = dst.objects[0]
    bpy.context.scene.collection.objects.link(ob)
    if rot:
        ob.data = ob.data.copy(); ob.data.transform(Matrix.Rotation(rot, 4, 'Z'))
    models.append((ob, label))

sc, cam = hk.scene_setup(res=900)
RX, RY = 2600, 900
sc.render.resolution_x, sc.render.resolution_y = RX, RY
fig, fh = hk.figure(0, 0)
tm = bpy.data.materials.new("label"); tm.use_nodes = True
tm.node_tree.nodes["Principled BSDF"].inputs["Base Color"].default_value = (0.02, 0.02, 0.02, 1)
tm.node_tree.nodes["Principled BSDF"].inputs["Emission Color"].default_value = (0.02, 0.02, 0.02, 1)


def bounds(ob):
    co = np.array([v.co[:] for v in ob.data.vertices])
    return Vector(co.min(0)), Vector(co.max(0))


def label_obj(text, size):
    cu = bpy.data.curves.new("t", "FONT"); cu.body = text; cu.size = size; cu.align_x = 'CENTER'
    t = bpy.data.objects.new("lbl", cu); sc.collection.objects.link(t); cu.materials.append(tm)
    return t


def fit(objs, margin=1.05):
    bpy.context.view_layer.update()
    Mi = cam.matrix_world.inverted()
    pts = []
    for o in objs:
        if o.type == 'MESH':
            pts += [Mi @ (o.matrix_world @ v.co) for v in o.data.vertices]
        else:
            pts += [Mi @ (o.matrix_world @ Vector(c)) for c in o.bound_box]
    xs = [p.x for p in pts]; ys = [p.y for p in pts]
    cx, cy = (min(xs) + max(xs)) / 2, (min(ys) + max(ys)) / 2
    cam.location = cam.matrix_world @ Vector((cx, cy, 0))
    cam.data.ortho_scale = max(max(xs) - min(xs), (max(ys) - min(ys)) * RX / RY) * margin


cam.data.type = 'ORTHO'
d = Vector((0.45, 1.0, 0.32)).normalized()
right = Vector((-d.y, d.x, 0)).normalized()
# ---- row 1: front three-quarter, left to right: figure, 004, 005, 006
pos = 0.0
order = [(fig, "1.8 m\nfigure")] + models
labels = []
for ob, label in order:
    lo, hi = bounds(ob)
    sz = 0.5 if ob is not fig else 0.4
    longest = max(len(x) for x in label.split("\n"))
    half = max(max(hi.x - lo.x, (hi.y - lo.y) * 0.45) / 2, 0.3 * sz * longest)
    pos += half + (0.8 if ob is not fig else 0)
    ob.location = right * pos - Vector(((lo.x + hi.x) / 2, 0, 0))
    t = label_obj(label, sz)
    t.location = right * pos + Vector((0, 0, -1.05))
    t.rotation_euler = (math.radians(90) - math.asin(d.z), 0, math.atan2(d.x, -d.y))
    labels.append(t)
    pos += half + 0.8
hk.aim(cam, Vector((0, 0, 2)), d, 80)
fit([o for o, _ in order] + labels)
a = os.path.join(ROOT, "_cs46_a.png"); hk.render(sc, a)
# ---- row 2: pure side view from the right (heads point right), laid out along y
for t in labels: t.hide_render = True
pos = 0.0
for ob, label in order:
    lo, hi = bounds(ob)
    ob.location = Vector((-(lo.x + hi.x) / 2, pos - lo.y, 0))
    pos += (hi.y - lo.y) + 1.0
hk.aim(cam, Vector((0, pos / 2, 2)), Vector((1, 0, 0)), 80)
fit([o for o, _ in order])
b = os.path.join(ROOT, "_cs46_b.png"); hk.render(sc, b)
A = hk.img_array(a); Bm = hk.img_array(b)
hk.save_array(os.path.join(ROOT, "contact_sheet_004-006.png"), np.concatenate([Bm, A], axis=0))   # rows start at the bottom: A on top
os.remove(a); os.remove(b)
print("DONE contact sheet", [(l.replace("\n", " "), round(bounds(o)[1].z - bounds(o)[0].z, 3)) for o, l in order])
