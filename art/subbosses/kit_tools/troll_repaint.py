"""troll_repaint.py - the EARLY REPAINT of the vanilla Troll's own _MainTex for ASSET-001 (owner, 2026-11-21: approved for this
pilot "as long as the end result isn't jank"). Runic style (MagicRunicMod make_armor_repaint.py / apply_armor_repaint.py): we ship
MASKS (our data, in the Troll Body's UV0) + a RECIPE; the runtime recolours the texture it reads back. The repainted texture written
here is a PREVIEW ONLY (derived from vanilla pixels, never shipped).

Mask (RGBA, 512 x 512, Body UV0):
  R = bark: the Hive bark spreading from the crust over chest, shoulders, back and upper arms (noisy edge, ~1 m falloff)
  G = extremity darkening: the sickly, darkened Troll skin towards hands, forearms, shins and feet
  B = blight veins: thin veins radiating from the mouth and the eye clusters (also the EMISSION mask: the runtime drives it with the
      Heart's biome tint, like ApplyBiomeVisuals)
  A = dark: the dark root web from the crust's edges over belly, neck and arms, and the dark mouth slit
Recipe (repaint.json): sick-skin colour, bark tint + the bark texture's triplanar tiling (TheHive_Mat's olivetree_trunk01), root
colour, blight colour. Luminance of the vanilla texture is kept everywhere (so the anatomy still reads).
NOTE: the Troll's UVs are mostly mirrored (left/right share texels, measured 44 of 54 matched pairs), so the paint is symmetric;
the crust's asymmetry comes from the geometry.
"""
import math, random
import numpy as np


def raster_position_map(V, F, UV, size):
    """per-texel 3D position and normal (rest pose) by rasterising the UV triangles; -1 where unused"""
    V = np.asarray(V, dtype=np.float64); UV = np.asarray(UV, dtype=np.float64)
    pos = np.full((size, size, 3), np.nan); nrm = np.zeros((size, size, 3))
    for t in F:
        a, b, c = t
        uv = UV[[a, b, c]] * size - 0.5
        lo = np.floor(uv.min(0)).astype(int); hi = np.ceil(uv.max(0)).astype(int)
        lo = np.clip(lo, 0, size - 1); hi = np.clip(hi, 0, size - 1)
        if hi[0] < lo[0] or hi[1] < lo[1]:
            continue
        xs, ys = np.meshgrid(np.arange(lo[0], hi[0] + 1), np.arange(lo[1], hi[1] + 1))
        p = np.stack([xs.ravel(), ys.ravel()], -1).astype(np.float64)
        v0, v1 = uv[1] - uv[0], uv[2] - uv[0]
        den = v0[0] * v1[1] - v1[0] * v0[1]
        if abs(den) < 1e-12:
            continue
        d = p - uv[0]
        l1 = (d[:, 0] * v1[1] - v1[0] * d[:, 1]) / den
        l2 = (v0[0] * d[:, 1] - d[:, 0] * v0[1]) / den
        l0 = 1 - l1 - l2
        m = (l0 >= -0.02) & (l1 >= -0.02) & (l2 >= -0.02)
        if not m.any():
            continue
        P = l0[m, None] * V[a] + l1[m, None] * V[b] + l2[m, None] * V[c]
        n = np.cross(V[b] - V[a], V[c] - V[a]); n /= (np.linalg.norm(n) + 1e-12)
        X, Y = xs.ravel()[m], ys.ravel()[m]
        pos[Y, X] = P; nrm[Y, X] = n
    return pos, nrm


def smoothstep(e0, e1, x):
    t = np.clip((x - e0) / (e1 - e0), 0, 1)
    return t * t * (3 - 2 * t)


def value_noise3(P, scale, seed):
    """cheap smooth 3D value noise (trilinear over a hashed lattice), in [-1, 1]"""
    rng = np.random.default_rng(seed)
    G = rng.uniform(-1, 1, (32, 32, 32))
    q = P / scale
    i = np.floor(q).astype(int); f = q - i
    f = f * f * (3 - 2 * f)
    out = 0
    for dx in (0, 1):
        for dy in (0, 1):
            for dz in (0, 1):
                w = (f[..., 0] if dx else 1 - f[..., 0]) * (f[..., 1] if dy else 1 - f[..., 1]) * (f[..., 2] if dz else 1 - f[..., 2])
                out = out + w * G[(i[..., 0] + dx) % 32, (i[..., 1] + dy) % 32, (i[..., 2] + dz) % 32]
    return out


def walk_curves(nearest, starts, n_per, length, step, seed, bias=None, branch=0.25, persist=0.0, jitter=0.45):
    """random walks over the body surface: from each start, n_per curves of ~length m; nearest(p) -> (point, normal) projects
    back onto the skin. Returns a list of (polyline, width0)"""
    rng = random.Random(seed)
    curves = []
    for (s, w0, dir_hint) in starts:
        for k in range(n_per):
            p, n = nearest(s)
            if p is None:
                continue
            d = np.array(dir_hint, dtype=float) + np.array([rng.uniform(-1, 1), rng.uniform(-1, 1), rng.uniform(-1, 1)]) * 0.9
            pts = [np.array(p)]
            L = length * rng.uniform(0.5, 1.2)
            while (len(pts) - 1) * step < L:
                n = np.array(n)
                d = d - n * d.dot(n); d /= (np.linalg.norm(d) + 1e-9)
                d = d + np.array([rng.uniform(-1, 1), rng.uniform(-1, 1), rng.uniform(-1, 1)]) * jitter
                if persist:
                    d = d + np.array(dir_hint, dtype=float) * persist     # keep heading away from the source (radiating, no loops)
                if bias is not None:
                    d = d + np.array(bias) * 0.15
                d /= np.linalg.norm(d)
                q, n = nearest(pts[-1] + d * step)
                if q is None:
                    break
                pts.append(np.array(q))
                if rng.random() < branch * step and len(pts) > 2:
                    curves.append((walk_branch(nearest, pts[-1], d, length * 0.45, step, rng), w0 * 0.6))
            curves.append((pts, w0))
    return curves


def walk_branch(nearest, p0, d0, length, step, rng):
    d = np.array(d0) + np.array([rng.uniform(-1, 1), rng.uniform(-1, 1), rng.uniform(-1, 1)]) * 1.2
    pts = [np.array(p0)]
    p, n = nearest(p0)
    while (len(pts) - 1) * step < length * rng.uniform(0.4, 1.0):
        n = np.array(n)
        d = d - n * d.dot(n); d /= (np.linalg.norm(d) + 1e-9)
        d = d + np.array([rng.uniform(-1, 1), rng.uniform(-1, 1), rng.uniform(-1, 1)]) * 0.5
        d /= np.linalg.norm(d)
        q, n = nearest(pts[-1] + d * step)
        if q is None:
            break
        pts.append(np.array(q))
    return pts


def smooth_curves(curves, nearest, it=2):
    """Chaikin corner cutting (no straight segments), re-projected onto the skin"""
    out = []
    for pts, w0 in curves:
        P = [np.array(q) for q in pts]
        for _ in range(it):
            if len(P) < 3:
                break
            Q = [P[0]]
            for a_, b_ in zip(P[:-1], P[1:]):
                Q += [0.75 * a_ + 0.25 * b_, 0.25 * a_ + 0.75 * b_]
            Q.append(P[-1]); P = Q
        P2 = []
        for q in P:
            r_, _ = nearest(q)
            P2.append(np.array(r_) if r_ is not None else q)
        out.append((P2, w0))
    return out


def curves_mask(pos, curves, taper=True, fade=0.0):
    """per texel: 1 on a curve (width tapering along it), 0 off; distance to segments in 3D"""
    valid = ~np.isnan(pos[..., 0])
    P = pos[valid]
    best = np.zeros(len(P))
    for pts, w0 in curves:
        if len(pts) < 2:
            continue
        A = np.array(pts[:-1]); B = np.array(pts[1:])
        n = len(A)
        lo = np.minimum(A, B).min(0) - w0 * 2; hi = np.maximum(A, B).max(0) + w0 * 2
        sel = np.all((P >= lo) & (P <= hi), axis=1)
        if not sel.any():
            continue
        Q = P[sel]
        val = np.zeros(len(Q))
        for i in range(n):
            ab = B[i] - A[i]; L2 = ab.dot(ab) + 1e-12
            t = np.clip(((Q - A[i]) @ ab) / L2, 0, 1)
            d = np.linalg.norm(Q - (A[i] + t[:, None] * ab), axis=1)
            w = w0 * (1 - 0.75 * (i + t) / n) if taper else w0
            f_ = (1 - (i + t) / n) ** fade if fade else 1.0          # intensity fades out along the curve
            val = np.maximum(val, (1 - smoothstep(w * 0.35, w, d)) * f_)
        best[sel] = np.maximum(best[sel], val)
    out = np.zeros(pos.shape[:2]); out[valid] = best
    return out


def dilate_fill(img, valid, n=4):
    """grow painted texels into the unused UV gutter so mip/bilinear sampling does not bleed the old texture at seams"""
    out = img.copy(); v = valid.copy()
    for _ in range(n):
        acc = np.zeros_like(out); cnt = np.zeros(v.shape)
        for dy, dx in ((0, 1), (0, -1), (1, 0), (-1, 0)):
            sv = np.roll(np.roll(v, dy, 0), dx, 1)
            so = np.roll(np.roll(out, dy, 0), dx, 1)
            acc[sv] += so[sv]; cnt[sv] += 1
        grow = (~v) & (cnt > 0)
        out[grow] = acc[grow] / cnt[grow][..., None] if out.ndim == 3 else acc[grow] / cnt[grow]
        v = v | grow
    return out
