"""hive_repaint: the early Hive repaint of a vanilla creature's own _MainTex, Runic style (MagicRunicMod make_armor_repaint.py /
apply_armor_repaint.py, adapted): MASKS + a RECIPE are our data; the runtime applies them to the texture it reads back, so no
vanilla pixels are shipped. The repainted texture written here is a PREVIEW only (derived from vanilla pixels, never shipped).

Masks live in the creature's UV0 space:
  R = bark creep (Hive bark palette over the skin, strongest under and around the add-on parts, fading out along the limbs)
  G = blight veins (BlightGlow emission), radiating from given source points over the body surface
Recipe (repaint.json): bark colour (TheHive_Mat _Color), the bark detail texture and its tiling, the luminance-keeping blend
strength, the vein emission colour.
Uses numpy only (called from Blender with Blender's own image I/O).
"""
import math, random
import numpy as np
from mathutils import Vector


def rasterize_positions(verts3d, uvs, tris, size):
    """world position per texel of the UV layout (nearest-triangle coverage), and a coverage mask."""
    pos = np.zeros((size, size, 3), np.float32); cov = np.zeros((size, size), bool)
    V = np.array([[v.x, v.y, v.z] for v in verts3d], np.float32); U = np.array(uvs, np.float32) * size
    for t in tris:
        a, b, c = t
        p = U[[a, b, c]]
        x0, y0 = np.floor(p.min(0)).astype(int); x1, y1 = np.ceil(p.max(0)).astype(int)
        x0, y0 = max(x0, 0), max(y0, 0); x1, y1 = min(x1, size - 1), min(y1, size - 1)
        if x1 < x0 or y1 < y0: continue
        xs, ys = np.meshgrid(np.arange(x0, x1 + 1) + 0.5, np.arange(y0, y1 + 1) + 0.5)
        d = (p[1, 1] - p[2, 1]) * (p[0, 0] - p[2, 0]) + (p[2, 0] - p[1, 0]) * (p[0, 1] - p[2, 1])
        if abs(d) < 1e-9: continue
        l0 = ((p[1, 1] - p[2, 1]) * (xs - p[2, 0]) + (p[2, 0] - p[1, 0]) * (ys - p[2, 1])) / d
        l1 = ((p[2, 1] - p[0, 1]) * (xs - p[2, 0]) + (p[0, 0] - p[2, 0]) * (ys - p[2, 1])) / d
        l2 = 1 - l0 - l1
        inside = (l0 >= -0.02) & (l1 >= -0.02) & (l2 >= -0.02)
        if not inside.any(): continue
        P = l0[..., None] * V[a] + l1[..., None] * V[b] + l2[..., None] * V[c]
        yy, xx = np.nonzero(inside)
        pos[yy + y0, xx + x0] = P[yy, xx]; cov[yy + y0, xx + x0] = True
    return pos, cov


def dilate(m, n=2):
    out = m.copy()
    for _ in range(n):
        o = out.copy()
        o[1:] |= out[:-1]; o[:-1] |= out[1:]; o[:, 1:] |= out[:, :-1]; o[:, :-1] |= out[:, 1:]
        out = o
    return out


def bark_mask(pos, cov, source_bvh, reach=0.2, near=0.015, seed=0, noise_fn=None):
    """1 at / under the add-on parts, fading to 0 at `reach` metres from them, broken up by low-frequency noise."""
    m = np.zeros(cov.shape, np.float32)
    ys, xs = np.nonzero(cov)
    for y, x in zip(ys, xs):
        p = Vector(pos[y, x]); loc, n, idx, d = source_bvh.find_nearest(p)
        if loc is None: continue
        k = 1.0 - (d - near) / (reach - near)
        if noise_fn is not None: k += 0.28 * noise_fn(p * 7.0 + Vector((seed, 0, 0)))
        m[y, x] = min(max(k, 0.0), 1.0)
    m = m * m * (3 - 2 * m)                          # smoothstep: soft creep edges
    return m


def vein_paths(body_bvh, sources, seed, per_source=6, steps=14, step=0.025, branch=0.25):
    """surface random walks, branching, from each source point: a list of polylines (3D points)."""
    rnd = random.Random(seed); paths = []
    for src, main_dir in sources:
        for k in range(per_source):
            loc, n, idx, d = body_bvh.find_nearest(Vector(src))
            if loc is None: continue
            a = 2 * math.pi * k / per_source + rnd.uniform(-0.4, 0.4)
            t = Vector(main_dir) if main_dir is not None else Vector((math.cos(a), math.sin(a), -0.6))
            t = (t + Vector((rnd.uniform(-0.6, 0.6), rnd.uniform(-0.6, 0.6), rnd.uniform(-0.6, 0.3)))).normalized()
            stack = [(loc, n, t, steps, 1.0)]
            while stack:
                p, n, t, left, w = stack.pop()
                pts = [p]
                for i in range(left):
                    t = (t - n * t.dot(n)).normalized()
                    side = n.cross(t).normalized(); t = (t + side * rnd.uniform(-0.5, 0.5)).normalized()
                    loc, n2, idx, d = body_bvh.find_nearest(p + t * step)
                    if loc is None: break
                    p, n = loc, n2; pts.append(p)
                    if rnd.random() < branch * w and i > 2 and len(paths) < 400:
                        stack.append((p, n, (t + side * rnd.choice((-1, 1)) * 0.9).normalized(), max(left - i - 2, 2), w * 0.6))
                if len(pts) > 2: paths.append((pts, w))
    return paths


def vein_mask(pos, cov, paths, width=0.006):
    """1 on the vein polylines (tapering along each), 0 elsewhere."""
    m = np.zeros(cov.shape, np.float32)
    ys, xs = np.nonzero(cov); P = pos[ys, xs]
    for pts, w in paths:
        A = np.array([[p.x, p.y, p.z] for p in pts[:-1]], np.float32); Bp = np.array([[p.x, p.y, p.z] for p in pts[1:]], np.float32)
        for i in range(len(A)):
            ab = Bp[i] - A[i]; L2 = float(ab.dot(ab)) or 1e-9
            tt = np.clip(((P - A[i]) @ ab) / L2, 0, 1)
            d = np.linalg.norm(P - (A[i] + tt[:, None] * ab), axis=1)
            wid = width * w * (1.0 - 0.7 * i / max(len(A), 1))
            v = np.clip(1.0 - d / max(wid, 1e-4), 0, 1)
            m[ys, xs] = np.maximum(m[ys, xs], v)
    return m


def apply(orig_rgb, bark_tex, bark_col, mask, strength=0.85):
    """luminance-keeping blend: the Draugr's own detail survives under the bark palette."""
    lum = (0.299 * orig_rgb[..., 0] + 0.587 * orig_rgb[..., 1] + 0.114 * orig_rgb[..., 2])[..., None]
    hive = bark_tex * np.array(bark_col, np.float32)[None, None] * (0.55 + 0.9 * lum)
    k = (mask * strength)[..., None]
    return orig_rgb * (1 - k) + np.clip(hive, 0, 1) * k
