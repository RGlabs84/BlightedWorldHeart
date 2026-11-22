"""make_repaint_maps.py - the runtime repaint's OWN maps (stage 3b, the Runic playbook: make_armor_repaint.py writes masks, the
runtime applies them). Everything here is our data, in the donor body's UV0 at the shipped mask size (SZO); no vanilla pixel.

Input: the per-texel arrays the APPROVED composites computed, dumped by running copies of the six kitbash scripts in a scratch
mirror (~/valheim-testbed/bh-repaint-mirror, *_DUMP.py cut right after the preview save; the dumped composite equals the approved
preview to <= 0.5/255 for five of six, the Seer's random vein walks differ in ~1% of texels - irrelevant here: the runtime uses
the APPROVED mask files, these maps only carry positions, coverage and region sets, which are deterministic).

Output, art/subbosses/runtime/repaint/<Id>_*.png:
  _bark.png    RGBA: the triplanar bark coordinate, 16 bit: u = (R*256+G)/65536, v = (B*256+A)/65536 (u = (uu / tile) mod 1)
  _regions.png RGBA: R coverage (255 = a texel of the body's UV layout), G seam weight (agent A) or brood halo (Broodhusk),
               B region code (0 none, 1 Lox head plate, 2 Seer antler, 3 wing, 4 wing hole, 5 mandible), A vein albedo weight
  plus copies of the approved masks (hive, moss, mouth) under the same prefix.
Agent A composited at SZ = 2 x SZO: positions, normals, seam and veins are box-averaged over each 2x2 block (any valid sub-texel
counts), the region bits by majority.
Run: python3 -I kit_tools/make_repaint_maps.py
"""
import json, os, shutil
import numpy as np
from PIL import Image

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DUMPS = os.path.expanduser("~/valheim-testbed/bh-repaint-mirror/dumps")
OUT = os.path.join(HERE, "runtime", "repaint")
KITS = {
    "BlightedSB_HiveBrute": dict(asset="ASSET-001_HiveBrute", fmt="A", tile=1.2, masks={"hive": "troll_hive_mask.png", "moss": "troll_moss_mask.png"}),
    "BlightedSB_Rootstalker": dict(asset="ASSET-002_Rootstalker", fmt="A", tile=0.3, masks={"hive": "wolf_hive_mask.png", "moss": "wolf_moss_mask.png", "mouth": "wolf_mouth_mask.png"}),
    "BlightedSB_Gorgemaw": dict(asset="ASSET-003_Gorgemaw", fmt="A", tile=1.2, masks={"hive": "lox_hive_mask.png", "moss": "lox_moss_mask.png"}),
    "BlightedSB_EyeblightSeer": dict(asset="ASSET-004_EyeblightSeer", fmt="B", masks={"hive": "seer_hive_mask.png"}),
    "BlightedSB_BarkboundHusk": dict(asset="ASSET-005_BarkboundHusk", fmt="B", masks={"hive": "husk_hive_mask.png"}),
    "BlightedSB_Broodhusk": dict(asset="ASSET-006_Broodhusk", fmt="B", masks={"hive": "brood_hive_mask.png"}),
}


def scatter(valid, vec, fill=0.0):
    out = np.full(valid.shape + vec.shape[1:], fill, dtype=np.float64)
    out[valid] = vec
    return out


def block_mean(a, valid, f):
    """mean over the valid sub-texels of each f x f block (Blender's bottom-up row order kept)"""
    h, w = valid.shape
    v = valid.reshape(h // f, f, w // f, f).astype(np.float64)
    cnt = v.sum((1, 3))
    if a.ndim == 2:
        s = (a * valid).reshape(h // f, f, w // f, f).sum((1, 3))
        return np.where(cnt > 0, s / np.maximum(cnt, 1), 0.0), cnt
    s = (a * valid[..., None]).reshape(h // f, f, w // f, f, a.shape[-1]).sum((1, 3))
    return np.where(cnt[..., None] > 0, s / np.maximum(cnt, 1)[..., None], 0.0), cnt


def to_png_rows(a):
    """Blender arrays are bottom-up; PNG and Unity's GetPixels are... Unity GetPixels is bottom-up too, PNG files are top-down"""
    return a[::-1]


def u16(x):
    q = np.clip(np.floor(x * 65536.0), 0, 65535).astype(np.uint32)
    return (q >> 8).astype(np.uint8), (q & 255).astype(np.uint8)


os.makedirs(OUT, exist_ok=True)
report = {}
for kid, k in KITS.items():
    z = np.load(os.path.join(DUMPS, k["asset"], "dump.npz"))
    J = json.load(open(os.path.join(DUMPS, k["asset"], "dump.json")))
    sc = J["scalars"]
    if k["fmt"] == "A":
        f = sc["SZ"] // sc["SZO"]
        valid = z["valid"]
        pos, nrm = np.nan_to_num(z["pos"]), z["nrm"]
        P, cnt = block_mean(pos, valid, f)
        N, _ = block_mean(nrm, valid, f)
        cov = cnt > 0
        seam, _ = block_mean(scatter(valid, z["seam"]), valid, f)
        vein, _ = block_mean(z["vein_m"], valid, f)
        code = np.zeros(cov.shape, np.uint8)
        if "head_v" in z.files:
            hv, _ = block_mean(scatter(valid, (z["head_v"] > 0.3).astype(float)), valid, f)
            code[hv >= 0.5] = 1
        tile = k["tile"]
        g = seam
    else:
        cov = z["valid1"]
        P = scatter(cov, z["P1"]); N = z["nrm1"]
        tile = sc["TILE_M"]
        code = np.zeros(cov.shape, np.uint8)
        g = np.zeros(cov.shape)
        if "antler1" in z.files: code[cov] = np.where(z["antler1"], 2, code[cov])
        if "wing1" in z.files:
            c = code[cov]
            c = np.where(z["wing1"], 3, c); c = np.where(z["hole"], 4, c); c = np.where(z["mand1"], 5, c)
            code[cov] = c
            g = scatter(cov, z["halo"])
        # the vein ALBEDO weight: Seer/Husk use the shipped mask's B, Broodhusk the lines before its halo was added (mask_l R)
        vein = z["mask_l"][..., 0] if "wing1" in z.files else z["mask"][..., 2]
    # the triplanar bark coordinate, exactly as the composites: the dominant normal axis picks the plane (Blender axes). It is
    # stored at the COMPOSITE's resolution (agent A: 2 x the masks): the bark is finer than a mask texel, and the approved
    # texture is the box average of those samples (measured: one sample per mask texel was p99 22-35/255 off, the averaged
    # sub-samples p99 0.8-2.5). A sub-texel outside the layout is (0, 0, 0, 0); inside, v's lowest bit is forced to 1.
    if k["fmt"] == "A":
        Pb, Nb, covb = np.nan_to_num(z["pos"]), z["nrm"], z["valid"]
    else:
        Pb, Nb, covb = P, N, cov
    Nn = np.abs(Nb); axis = Nn.argmax(-1)
    uu = np.where(axis == 0, Pb[..., 1], Pb[..., 0]); vv = np.where(axis == 2, Pb[..., 1], Pb[..., 2])
    u = np.mod(uu / tile, 1.0); v = np.mod(vv / tile, 1.0)
    uh, ul = u16(u); vh, vl = u16(v)
    bark = np.stack([uh, ul, vh, vl | 1], -1); bark[~covb] = 0
    reg = np.stack([cov * 255, np.clip(np.round(g * 255), 0, 255), code, np.clip(np.round(vein * 255), 0, 255)], -1).astype(np.uint8)
    reg[~cov, 1:] = 0
    Image.fromarray(to_png_rows(bark), "RGBA").save(os.path.join(OUT, f"{kid}_bark.png"), optimize=True)
    Image.fromarray(to_png_rows(reg), "RGBA").save(os.path.join(OUT, f"{kid}_regions.png"), optimize=True)
    for role, fn in k["masks"].items():
        shutil.copyfile(os.path.join(HERE, k["asset"], "kit", "repaint", fn), os.path.join(OUT, f"{kid}_{role}.png"))
    report[kid] = {"size": int(cov.shape[0]), "bark_size": int(bark.shape[0]), "covered": int(cov.sum()), "tile_m": round(float(tile), 4),
                   "regions": {int(c): int((code == c).sum()) for c in np.unique(code)}, "masks": sorted(k["masks"])}
    print(kid, report[kid])
json.dump(report, open(os.path.join(OUT, "maps_report.json"), "w"), indent=1)
print("sizes", {f: os.path.getsize(os.path.join(OUT, f)) // 1024 for f in sorted(os.listdir(OUT))})
