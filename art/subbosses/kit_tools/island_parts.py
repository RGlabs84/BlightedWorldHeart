"""island_parts.py - loose ISLANDS of a vanilla mesh (welded by position), and Blender meshes built from one island: the
Troll's own teeth/claws, the Elder's (gd_king) back branches, the Wolf's fangs ... (vanilla geometry, a triangle SUBSET of the
game's mesh; at runtime the mod builds the same subset from the game's mesh)."""
import numpy as np


def islands(V, T):
    """V (n,3), T list of (a,b,c) -> {root: [triangle indices]}"""
    V = np.asarray(V)
    par = list(range(len(V)))

    def f(a):
        while par[a] != a:
            par[a] = par[par[a]]; a = par[a]
        return a
    for t in T:
        for a, b in ((t[0], t[1]), (t[1], t[2])):
            ra, rb = f(a), f(b)
            if ra != rb:
                par[ra] = rb
    seen = {}
    for i, v in enumerate(V):
        k = tuple(np.round(v, 6))
        if k in seen:
            ra, rb = f(i), f(seen[k])
            if ra != rb:
                par[ra] = rb
        else:
            seen[k] = i
    comp = {}
    for ti, t in enumerate(T):
        comp.setdefault(f(t[0]), []).append(ti)
    return comp


def island_stats(V, T, tris):
    vi = sorted({i for t in tris for i in T[t]})
    P = np.asarray(V)[vi]
    return {"tris": len(tris), "centre": P.mean(0).tolist(), "size": (P.max(0) - P.min(0)).tolist()}


def canonical_frame(P):
    """(root, R) for points P (n,3): principal axis root->tip (the root is the WIDER end) as +z, the bulge as +y"""
    cen = P.mean(0); Q = P - cen
    ax = np.linalg.svd(Q, full_matrices=False)[2][0]
    pr = Q @ ax; lo, hi = pr.min(), pr.max()
    def width(sel):
        return np.linalg.norm(Q[sel] - np.outer(pr[sel], ax), axis=1).mean()
    if width(pr > hi - 0.25 * (hi - lo)) > width(pr < lo + 0.25 * (hi - lo)):
        ax = -ax; pr = -pr; lo, hi = -hi, -lo
    root = cen + ax * lo
    bulge = (cen - root) - ax * ((cen - root) @ ax)
    yv = bulge / np.linalg.norm(bulge) if np.linalg.norm(bulge) > 1e-6 else np.cross(ax, [1.0, 0, 0])
    yv = yv - ax * (yv @ ax); yv /= np.linalg.norm(yv); xv = np.cross(yv, ax)
    return root, np.array([xv, yv, ax]), float(hi - lo)


def island_mesh(P, key, tris, name, canonical=True, drop_submeshes=()):
    """Blender mesh of an island (triangle indices into the concatenated submeshes of vanilla part `key`, Parts P), in prefab
    space metres (Blender axes) or - canonical=True - in the canonical frame (root at the origin, root->tip +z, bulge +y).
    Returns (mesh, info) with info = {root, R (rows = x, y, z axes in prefab-Blender space), length}"""
    import bpy
    d = P.data(key)
    Mw = np.array(d["world_matrix_in_prefab"])
    T = [(t, si) for si, sm in enumerate(d["submeshes"]) for t in sm]
    sel = [T[i] for i in tris] if tris is not None else [x for x in T if x[1] not in drop_submeshes]
    vi = sorted({i for t, _ in sel for i in t}); remap = {o: n for n, o in enumerate(vi)}
    Vw = (np.c_[np.array(d["verts"])[vi], np.ones(len(vi))] @ Mw.T)[:, :3][:, [0, 2, 1]]
    info = {"root": None, "R": None, "length": float(np.ptp(Vw, 0).max())}
    if canonical:
        root, R, L = canonical_frame(Vw)
        Vw = (Vw - root) @ R.T
        info = {"root": root.tolist(), "R": R.tolist(), "length": L}
    me = bpy.data.meshes.new(name)
    me.from_pydata([tuple(v) for v in Vw], [], [(remap[t[0]], remap[t[2]], remap[t[1]]) for t, _ in sel])
    me.update()
    if d["uv0"]:
        uvl = me.uv_layers.new(name="UV0")
        for loop in me.loops:
            uvl.data[loop.index].uv = tuple(d["uv0"][vi[loop.vertex_index]])
    sis = sorted({si for _, si in sel}); smap = {si: n for n, si in enumerate(sis)}
    for pg, (_, si) in zip(me.polygons, sel):
        pg.material_index = smap[si]; pg.use_smooth = True
    for si in sis:
        me.materials.append(P.material(d["materials"][si]))
    return me, info
