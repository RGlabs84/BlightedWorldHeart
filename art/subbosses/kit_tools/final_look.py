"""final_look.py - STEP 3 final-look renders for the kitbash sub-bosses (owner's step-4 gate): a Valheim-ish DAYTIME rig (Runic's
key/fill/rim warmed + a warm sun + a soft sky fill + a little haze), a DUSK/OVERCAST variant, and the Heart's Black Forest BIOME TINT
the way BlightedWorldHeartAI.ApplyBiomeVisuals does it (every renderer: _Color = tint, _EmissionColor = tint x 2 + _EMISSION) - shown
two ways: as coded (with emission) and _Color only, so the owner can decide. Preview lighting only; nothing here ships."""
import math
import os

import bpy
from mathutils import Vector

import donor_base as DB


def _world(color, strength, fog_density, fog_color):
    w = bpy.context.scene.world
    w.use_nodes = True
    nt = w.node_tree
    for nd in list(nt.nodes):
        nt.nodes.remove(nd)
    out = nt.nodes.new("ShaderNodeOutputWorld")
    bg = nt.nodes.new("ShaderNodeBackground"); bg.inputs["Color"].default_value = (*color, 1); bg.inputs["Strength"].default_value = strength
    nt.links.new(bg.outputs[0], out.inputs["Surface"])
    if fog_density > 0:
        vol = nt.nodes.new("ShaderNodeVolumePrincipled")
        vol.inputs["Density"].default_value = fog_density; vol.inputs["Color"].default_value = (*fog_color, 1)
        nt.links.new(vol.outputs[0], out.inputs["Volume"])
    try:
        ee = bpy.context.scene.eevee
        ee.volumetric_end = 200.0; ee.volumetric_tile_size = '8'
    except Exception:
        pass


def _lights(preset, scale, aim_z):
    for ob in list(bpy.data.objects):
        if ob.type == 'LIGHT' and ob.name.startswith("FL_"):
            bpy.data.objects.remove(ob)
    rig = {o.name: o for o in bpy.data.objects if o.type == 'LIGHT' and not o.name.startswith("FL_")}
    if preset == "day":
        tint = {"key": ((1.0, 0.9, 0.78), 1.0), "fill": ((0.75, 0.85, 1.0), 0.8), "rim": ((1.0, 0.97, 0.92), 0.8)}
        sun = ((1.0, 0.93, 0.82), 2.2, math.radians(48), math.radians(-35))
        _world((0.42, 0.5, 0.62), 0.55, 0.0009 if scale >= 2 else 0.0, (0.75, 0.82, 0.9))
    else:   # dusk / overcast
        tint = {"key": ((1.0, 0.62, 0.4), 0.45), "fill": ((0.55, 0.62, 0.85), 0.5), "rim": ((1.0, 0.55, 0.35), 0.9)}
        sun = ((1.0, 0.55, 0.32), 1.1, math.radians(9), math.radians(-70))
        _world((0.13, 0.13, 0.2), 0.4, 0.004 if scale >= 2 else 0.0, (0.45, 0.42, 0.55))
    for nm, o in rig.items():
        key = "key" if "key" in nm else ("fill" if "fill" in nm else "rim")
        c, k = tint[key]
        if "base_energy" not in o:
            o["base_energy"] = o.data.energy; o["base_color"] = list(o.data.color)
        o.data.color = c; o.data.energy = o["base_energy"] * k
    ld = bpy.data.lights.new("FL_sun", 'SUN'); ld.color = sun[0]; ld.energy = sun[1]; ld.angle = math.radians(6)
    so = bpy.data.objects.new("FL_sun", ld); bpy.context.scene.collection.objects.link(so)
    el, az = sun[2], sun[3]
    so.rotation_euler = (math.pi / 2 - el, 0, az)


def _shot(G, name, target, dist, az, el, lens=85, w=900, h=900):
    sc = bpy.context.scene
    sc.render.resolution_x, sc.render.resolution_y = w, h
    DB.camera(target, dist, az, el, lens=lens)
    pth = os.path.join(G["PREV"], name + ".png"); DB.render(pth)
    return pth


def _biome(objs, tint_srgb, with_emission):
    """ApplyBiomeVisuals: _Color = tint (SetColor -> sRGB-decoded), _EmissionColor = tint x 2, _EMISSION on. Returns a restore list."""
    lin = tuple(DB.srgb2lin(c) for c in tint_srgb)
    restore = []
    done = {}
    for ob in objs:
        for i, slot in enumerate(ob.material_slots):
            m = slot.material
            if m is None:
                continue
            if m.name not in done:
                mc = m.copy(); mc.name = m.name + "_biome"
                nt = mc.node_tree; b = nt.nodes.get("Principled BSDF")
                if b is not None:
                    src = b.inputs["Base Color"].links[0].from_socket if b.inputs["Base Color"].links else None
                    mx = nt.nodes.new("ShaderNodeMix"); mx.data_type = 'RGBA'; mx.blend_type = 'MULTIPLY'; mx.inputs[0].default_value = 1.0
                    if src is not None:
                        nt.links.new(src, mx.inputs[6])
                    else:
                        mx.inputs[6].default_value = b.inputs["Base Color"].default_value
                    mx.inputs[7].default_value = (*lin, 1); nt.links.new(mx.outputs[2], b.inputs["Base Color"])
                    if with_emission:
                        for lk in list(b.inputs["Emission Color"].links):
                            nt.links.remove(lk)
                        b.inputs["Emission Color"].default_value = (*lin, 1)
                        b.inputs["Emission Strength"].default_value = 2.0
                done[m.name] = mc
            restore.append((slot, m))
            slot.material = done[m.name]
    return restore


def final_set(G, name_prefix, cen, views, head, wtf, branches, read10, scale, aim_z, body, rpmat, col, biome_tint=(0.5, 0.1, 0.8)):
    hk = G["hk"]; P = name_prefix
    shots = {}
    _lights("day", scale, aim_z)
    for nm, az, el, dist in views:
        shots[nm] = _shot(G, f"{P}_{nm}", cen, dist, az, el)
    hk.grid([shots[v[0]] for v in views], 4, os.path.join(G["PREV"], f"{P}_sheet.png"))
    _shot(G, f"{P}_close_head", head[0], head[1], head[2], head[3], w=900, h=800)
    _shot(G, f"{P}_close_wtf", wtf[0], wtf[1], wtf[2], wtf[3])
    _shot(G, f"{P}_close_branches", branches[0], branches[1], branches[2], branches[3])
    _shot(G, f"{P}_read_10m", read10[0], read10[1], read10[2], read10[3], lens=50, w=1200, h=800)
    col.hide_render = True
    _shot(G, f"{P}_base_repaint_34", cen, views[3][3], views[3][1], views[3][2])
    col.hide_render = False
    _lights("dusk", scale, aim_z)
    d1 = _shot(G, f"{P}_dusk_34", cen, views[3][3], views[3][1], views[3][2])
    d2 = _shot(G, f"{P}_dusk_front", cen, views[0][3], views[0][1], views[0][2])
    hk.grid([d1, d2], 2, os.path.join(G["PREV"], f"{P}_dusk_sheet.png"))
    _lights("day", scale, aim_z)
    objs = [o for o in col.objects] + [body]
    cells = []
    for with_em in (False, True):
        rs = _biome(objs, biome_tint, with_em)
        cells.append(_shot(G, f"{P}_biome_blackforest_{'coded' if with_em else 'color_only'}", cen, views[3][3], views[3][1], views[3][2]))
        for slot, m in rs:
            slot.material = m
    hk.grid(cells, 2, os.path.join(G["PREV"], f"{P}_biome_blackforest_panel.png"))
    # back to the Runic studio rig for the pose test
    for ob in list(bpy.data.objects):
        if ob.type == 'LIGHT' and ob.name.startswith("FL_"):
            bpy.data.objects.remove(ob)
    for o in bpy.data.objects:
        if o.type == 'LIGHT' and "base_energy" in o:
            o.data.energy = o["base_energy"]; o.data.color = tuple(o["base_color"])
    _world((0.045, 0.047, 0.052), 1.0, 0.0, (1, 1, 1))
