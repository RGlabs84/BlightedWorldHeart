import json, sys
snap, cur = sys.argv[1], sys.argv[2]
GEOM = ("source", "parent", "localPosition", "localRotation", "localScale", "part_localRotation", "part_localScale", "vertex_offsets", "mode", "skin", "weight_own_share", "head_bones_masked")
a = json.load(open(f"{snap}/attach.json")); b = json.load(open(f"{cur}/attach.json"))
diffs = []
ka = {k for k in a if not k.startswith("_")}; kb = {k for k in b if not k.startswith("_")}
if ka != kb: diffs.append(("part list", sorted(ka ^ kb)))
for k in sorted(ka & kb):
    for f in GEOM:
        if a[k].get(f) != b[k].get(f): diffs.append((k, f, a[k].get(f), b[k].get(f)))
# kept triangles / source islands
sa = a.get("_sources", {}); sb = b.get("_sources", {})
for k in set(sa) | set(sb):
    if (sa.get(k) or {}).get("triangles") != (sb.get(k) or {}).get("triangles"): diffs.append(("_sources triangles", k))
oa = json.load(open(f"{snap}/deform/lump_offsets.json")); ob = json.load(open(f"{cur}/deform/lump_offsets.json"))
if {k: v for k, v in oa.items() if not k.startswith("_")} != {k: v for k, v in ob.items() if not k.startswith("_")}: diffs.append(("lump_offsets differ",))
print("parts", len(ka), "geometry fields compared", len(GEOM), "offset sets", len([k for k in oa if not k.startswith('_')]))
print("GEOMETRY IDENTICAL" if not diffs else diffs[:20])
