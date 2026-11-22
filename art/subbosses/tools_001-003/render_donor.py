"""Render a donor's bind pose (from export_donor.py) with its skinned joints as dots.
blender -b --factory-startup -P render_donor.py -- <asset dir> [extra obj suffix e.g. _prefabrest]
Writes <asset dir>/donor/donor_bind_front.png, _side.png, _top.png (and _rest_* when a prefab-rest OBJ exists)."""
import bpy, sys, os, json, math
from mathutils import Vector

argv = sys.argv[sys.argv.index("--") + 1:]
ASSET = argv[0]
D = os.path.join(ASSET, "donor")
info = json.load(open(os.path.join(D, "donor_bones.json")))


def u2b(v):
    return Vector((v[0], v[2], v[1]))


def load_obj(path, name, col):
    vs, fs = [], []
    for line in open(path):
        p = line.split()
        if not p: continue
        if p[0] == "v": vs.append(u2b([float(x) for x in p[1:4]]))
        elif p[0] == "f": fs.append([int(x) - 1 for x in p[1:]])
    me = bpy.data.meshes.new(name); me.from_pydata(vs, [], fs); me.update()
    ob = bpy.data.objects.new(name, me); bpy.context.scene.collection.objects.link(ob)
    m = bpy.data.materials.new(name + "_m"); m.use_nodes = True
    b = m.node_tree.nodes["Principled BSDF"]; b.inputs["Base Color"].default_value = (*col, 1); b.inputs["Roughness"].default_value = 0.8
    m.use_backface_culling = False
    me.materials.append(m)
    for p in me.polygons: p.use_smooth = True
    return ob


def render_set(objs_suffix, tag):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    sc = bpy.context.scene
    obs = []
    for r in info["renderers"]:
        if not r["renderer_active"]: continue
        fn = os.path.join(D, "donor_" + r["go"].split("/")[-1].replace(" ", "_") + objs_suffix + ".obj")
        if os.path.exists(fn):
            obs.append(load_obj(fn, r["go"].split("/")[-1], (0.55, 0.55, 0.58)))
    if not obs: return
    jm = bpy.data.materials.new("joint"); jm.use_nodes = True
    jb = jm.node_tree.nodes["Principled BSDF"]; jb.inputs["Base Color"].default_value = (1, 0.15, 0.1, 1)
    jb.inputs["Emission Color"].default_value = (1, 0.15, 0.1, 1); jb.inputs["Emission Strength"].default_value = 2
    jm.blend_method = 'BLEND' if hasattr(jm, "blend_method") else None
    size = max(info["active_body_bounds_size"])
    rad = size * 0.008
    if objs_suffix == "":
        bb = info["renderers"][0]["bind_bones"]
        pts = [(b["name"], b["bind_world_pos"]) for b in bb]
    else:
        pts = [(t["name"], t["world_pos"]) for t in info["transforms"] if t["skinned"]]
    for nm, p in pts:
        bpy.ops.mesh.primitive_uv_sphere_add(radius=rad, location=u2b(p), segments=8, ring_count=6)
        o = bpy.context.active_object; o.data.materials.append(jm); o.show_in_front = True
    for e in ("BLENDER_EEVEE_NEXT", "BLENDER_EEVEE"):
        try: sc.render.engine = e; break
        except TypeError: pass
    sc.render.resolution_x = sc.render.resolution_y = 900
    w = bpy.data.worlds.new("w"); sc.world = w; w.use_nodes = True
    w.node_tree.nodes["Background"].inputs[0].default_value = (0.75, 0.77, 0.8, 1)
    sun = bpy.data.objects.new("sun", bpy.data.lights.new("sun", "SUN")); sc.collection.objects.link(sun)
    sun.data.energy = 3; sun.rotation_euler = (math.radians(45), 0, math.radians(30))
    lo = Vector(info["active_body_bounds_min"]); hi = Vector(info["active_body_bounds_max"])
    lo, hi = u2b(lo), u2b(hi)
    c = (lo + hi) / 2
    cam = bpy.data.objects.new("cam", bpy.data.cameras.new("cam")); sc.collection.objects.link(cam); sc.camera = cam
    cam.data.type = 'ORTHO'; cam.data.ortho_scale = size * 1.15
    # ground line
    bpy.ops.mesh.primitive_plane_add(size=size * 3, location=(c.x, c.y, 0))
    g = bpy.context.active_object; gm = bpy.data.materials.new("g"); gm.use_nodes = True
    gm.node_tree.nodes["Principled BSDF"].inputs["Base Color"].default_value = (0.35, 0.33, 0.3, 1); g.data.materials.append(gm)
    for nm, d in (("front", Vector((0, 1, 0))), ("side", Vector((1, 0, 0))), ("top", Vector((0, 0.001, 1)))):
        cam.location = c + d * size * 3
        cam.rotation_euler = (c - cam.location).to_track_quat("-Z", "Y").to_euler()
        g.hide_render = nm == "top"
        sc.render.filepath = os.path.join(D, f"donor_{tag}_{nm}.png")
        bpy.ops.render.render(write_still=True)


render_set("", "bind")
if any(os.path.exists(os.path.join(D, f)) for f in os.listdir(D) if f.endswith("_prefabrest.obj")):
    render_set("_prefabrest", "rest")
print("DONE donor render", ASSET)
