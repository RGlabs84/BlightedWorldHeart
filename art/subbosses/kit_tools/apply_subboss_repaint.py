"""apply_subboss_repaint.py - the REFERENCE body repaint (stage 3b, the Runic playbook: MagicRunicMod apply_armor_repaint.py).
BlightedSubBossRepaint.cs is its line-for-line port. It rebuilds each APPROVED repaint from our maps (runtime/repaint/<Id>_*.png),
the recipe table (runtime/repaint/repaint.json), the donor's vanilla albedo and TheHive's bark texture, and prints how far the
result is from the approved preview (the composite the owner signed off).

Inputs it shares with the runtime: the maps, the table. Inputs the runtime reads back from the game instead: the vanilla albedo and
the bark (here: the exact arrays the approved composites used, from the dumps in ~/valheim-testbed/bh-repaint-mirror/dumps; the
agent-A albedo was composited at 2x and is box-averaged to the mask size, the runtime reads the game texture at that size).
All arrays bottom-up (Unity GetPixels / Blender image order); colours are the stored texel values (0..1), as the composites used.
Run: python3 -I kit_tools/apply_subboss_repaint.py [--write <dir>]   (writes our rebuilt previews for a look; never shipped)
"""
import json, os, sys
import numpy as np
from PIL import Image

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RT = os.path.join(HERE, "runtime", "repaint")
DUMPS = os.path.expanduser("~/valheim-testbed/bh-repaint-mirror/dumps")
ASSET = {"BlightedSB_HiveBrute": "ASSET-001_HiveBrute", "BlightedSB_Rootstalker": "ASSET-002_Rootstalker", "BlightedSB_Gorgemaw": "ASSET-003_Gorgemaw",
         "BlightedSB_EyeblightSeer": "ASSET-004_EyeblightSeer", "BlightedSB_BarkboundHusk": "ASSET-005_BarkboundHusk", "BlightedSB_Broodhusk": "ASSET-006_Broodhusk"}
LUMW = np.array([0.3, 0.59, 0.11])


def png(path):
    """a map as floats 0..1, bottom-up (as Unity's GetPixels32 hands it back)"""
    return np.asarray(Image.open(path).convert("RGBA")).astype(np.float64)[::-1] / 255.0


def smooth01(x):
    return np.clip(x, 0.0, 1.0)


def dilate_fill(img, valid, n=8):
    """troll_repaint.dilate_fill: grow the painted texels into the gutter, 4-neighbour mean, wrapping at the edges (np.roll)"""
    out = img.copy(); v = valid.copy()
    for _ in range(n):
        acc = np.zeros_like(out); cnt = np.zeros(v.shape)
        for dy, dx in ((0, 1), (0, -1), (1, 0), (-1, 0)):
            sv = np.roll(np.roll(v, dy, 0), dx, 1)
            so = np.roll(np.roll(out, dy, 0), dx, 1)
            acc[sv] += so[sv]; cnt[sv] += 1
        grow = (~v) & (cnt > 0)
        out[grow] = acc[grow] / cnt[grow][..., None]
        v = v | grow
    return out


def repaint(kid, R, albedo, bark, own_emission=None):
    """albedo: (S, S, 4) the donor's _MainTex at the map size; bark: (512, 512, 3) TheHive_Mat _MainTex. Returns (albedo, emission)."""
    hive = png(os.path.join(RT, f"{kid}_hive.png"))
    reg = png(os.path.join(RT, f"{kid}_regions.png"))
    bk = np.asarray(Image.open(os.path.join(RT, f"{kid}_bark.png")).convert("RGBA")).astype(np.float64)[::-1]
    S = hive.shape[0]
    cov = reg[..., 0] > 0.5
    code = np.round(reg[..., 2] * 255).astype(int)
    # the bark: the composites' 4-tap sample at each stored coordinate, px = int(u * 510); the bark map may be finer than the
    # masks (f x f sub-samples per texel): their mean over the sub-samples inside the layout, as the approved box average
    f = bk.shape[0] // S
    inb = (bk[..., 0] + bk[..., 1] + bk[..., 2] + bk[..., 3]) > 0
    u = (bk[..., 0] * 256 + bk[..., 1]) / 65536.0; v = (bk[..., 2] * 256 + bk[..., 3]) / 65536.0
    px = (u * R["bark_px"]).astype(int); py = (v * R["bark_px"]).astype(int)
    B4 = (bark[py, px] + bark[py + 1, px] + bark[py, px + 1] + bark[py + 1, px + 1]) * 0.25
    n = inb.reshape(S, f, S, f).sum((1, 3))
    BKs = (B4 * inb[..., None]).reshape(S, f, S, f, 3).sum((1, 3)) / np.maximum(n, 1)[..., None]
    O = albedo[..., :3]
    lum = O @ LUMW
    mlum = lum[cov].mean()
    ln = lum / max(1e-6, mlum)
    b = hive[..., 0][..., None]; ext = hive[..., 1][..., None]; rm = hive[..., 3][..., None]; vm = reg[..., 3][..., None]
    k = R
    if k["formula"] == "A":
        seam = reg[..., 1]
        ln = ln * (1 - seam) + 0.92 * seam                                   # the mirrored halves' shading blended across x = 0
        if k.get("head_cap"):
            ln = np.where(code == 1, np.minimum(ln, 1.0), ln)               # the Lox's pale head plate capped
        lnc = ln[..., None]
        barkcol = BKs * np.array(k["bark_tint"]) * (0.45 + 0.55 * np.clip(lnc, 0, 2))
        sick = np.clip(lnc, 0, 2.5) * np.array(k["sick_skin"])
        col = sick * (1 - b) + barkcol * b
        moss = png(os.path.join(RT, f"{kid}_moss.png"))[..., 0][..., None]
        col = col * (1 - moss) + np.array(k["moss_colour"]) * np.clip(lnc, 0.4, 1.4) * moss
        col = col * (1 - k["extremity_darken"] * ext)
        col = col * (1 - k["infection_margin_darken"] * 4 * b * (1 - b))
        col = col * (1 - rm) + np.array(k["root_colour"]) * rm
        col = col * (1 - vm) + np.array(k["vein_albedo"]) * vm
        if "fold_darken" in k:
            mouth = png(os.path.join(RT, f"{kid}_mouth.png"))
            ov = mouth[..., 0][..., None]; gv = mouth[..., 1][..., None]; fv = mouth[..., 2][..., None]
            col = col * (1 - k["fold_darken"] * fv)
            col = col * (1 - gv) + np.array(k["gum_colour"]) * np.clip(lnc, 0.5, 1.6) * gv
            col = col * (1 - ov) + np.array(k["mouth_opening_colour"]) * ov
    else:
        lnc = np.clip(ln, 0, 2.5)[..., None]
        barkcol = BKs * np.array(k["bark_tint"]) * (0.45 + 0.55 * np.clip(lnc, 0, 2))
        if k["formula"] == "brood":
            sick = O * (1 - k["sick_mix"]) + lnc * mlum * np.array(k["sick_skin"]) / 0.4 * k["sick_mix"]
        else:
            sick = O * (1 - k["sick_mix"]) + lnc * np.array(k["sick_skin"]) * k["sick_mix"]
        if "antler_weather" in k:
            mO = O[cov].mean()
            sick = np.where((code == 2)[..., None], O * 0.45 + lnc * np.array(k["antler_weather"]) * 0.55 * mO, sick)
        col = sick * (1 - b) + barkcol * b
        col = col * (1 - k["extremity_darken"] * ext)
        col = col * (1 - k["infection_margin_darken"] * 4 * b * (1 - b))
        if k["formula"] == "brood":
            mbk = BKs[cov].mean()
            wingcol = lnc * mlum * np.array(k["wing_colour"]) / 0.4 * (0.6 + 0.4 * BKs.mean(-1, keepdims=True) / max(1e-6, mbk))
            col = np.where(((code == 3) | (code == 4))[..., None], wingcol, col)
            mandcol = np.clip(lnc, 0, 1.3) * np.array(k["mandible_colour"])
            col = np.where((code == 5)[..., None], mandcol, col)
        col = col * (1 - rm) + np.array(k["root_colour"]) * rm
        col = col * (1 - vm) + np.array(k["vein_albedo"]) * vm
    out = albedo.copy()
    out[..., :3] = np.where(cov[..., None], col, albedo[..., :3])
    out = dilate_fill(out, cov, 8)
    out[..., 3] = albedo[..., 3]
    if k["formula"] == "brood":
        out[..., 3] = np.where(code == 4, 0.0, out[..., 3])                 # the torn wings' ragged holes
    # emission (linear values): blight veins x colour [x strength baked into the map] (+ brood halo) + the donor's own glow
    em = np.clip(hive[..., 2], 0, 1)[..., None] * np.array(k["blight_colour"]) * k["strength_in_map"]
    if k["formula"] == "brood":
        em = np.maximum(em, reg[..., 1][..., None] * 0.5 * np.array(k["halo_colour"]))
    if own_emission is not None and k["own_emission"] > 0:
        em = em + own_emission * k["own_emission"]
    return out, em, cov


def compare(a, b, cov):
    d = np.abs(a - b)[cov].max(-1) * 255
    return {"max": round(float(d.max()), 2), "p99": round(float(np.percentile(d, 99)), 2), "mean": round(float(d.mean()), 3),
            "over_8": int((d > 8).sum()), "texels": int(cov.sum())}


if __name__ == "__main__":
    T = json.load(open(os.path.join(RT, "repaint.json")))
    W = sys.argv[sys.argv.index("--write") + 1] if "--write" in sys.argv else None
    worst = 0.0
    for kid, a in ASSET.items():
        R = dict(T["kits"][kid]); R["bark_px"] = T["bark_px"]
        z = np.load(os.path.join(DUMPS, a, "dump.npz")); J = json.load(open(os.path.join(DUMPS, a, "dump.json")))
        S = Image.open(os.path.join(RT, f"{kid}_hive.png")).size[0]
        if R["formula"] == "A":
            A0 = z["A0"]; f = A0.shape[0] // S
            albedo = A0.reshape(S, f, S, f, 4).mean((1, 3))
            bark = z["BK"]
            prevA = z["OUTA"].reshape(S, f, S, f, 4).mean((1, 3))
            prevE = z["EM"][..., :3].reshape(S, f, S, f, 3).mean((1, 3))
        else:
            albedo = z["orig1"]; bark = z["btex"]
            prevA = png(os.path.join(HERE, a, "kit", "repaint", "preview_albedo_DO_NOT_SHIP.png")); prevE = z["EM"][..., :3]
        out, em, cov = repaint(kid, R, albedo, bark)
        ca = compare(np.clip(out[..., :3], 0, 1), np.clip(prevA[..., :3], 0, 1), cov)
        ce = compare(np.clip(em, 0, 1), np.clip(prevE, 0, 1), cov)
        worst = max(worst, ca["p99"])
        print(f"{kid:26s} {S}px  albedo vs approved: {ca}  emission: {ce}")
        if W:
            os.makedirs(W, exist_ok=True)
            Image.fromarray((np.clip(out, 0, 1)[::-1] * 255 + 0.5).astype(np.uint8), "RGBA").save(os.path.join(W, f"{kid}_rebuilt.png"))
            Image.fromarray((np.clip(prevA, 0, 1)[::-1] * 255 + 0.5).astype(np.uint8), "RGBA").save(os.path.join(W, f"{kid}_approved.png"))
    print(f"worst 99th-percentile albedo difference: {worst:.2f}/255")
