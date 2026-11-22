"""check_material_table.py - every part slot's look key (runtime/<Id>.json) has an entry in runtime/materials.json, and every
entry is used (no silent gaps, no dead rows). Exit 1 on a gap. Run: python3 kit_tools/check_material_table.py"""
import json, glob, os, re, sys
HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
T = json.load(open(os.path.join(HERE, "runtime", "materials.json")))["kits"]
gaps, used, slots = [], set(), 0
for f in sorted(glob.glob(os.path.join(HERE, "runtime", "BlightedSB_*.json"))):
    k = json.load(open(f))
    tab = T.get(k["id"], {})
    for p in k["parts"]:
        for look in p.get("looks") or [None]:
            slots += 1
            key = re.sub(r"\.\d{3}$", "", look or "")
            if key not in tab: gaps.append(f"{k['id']}/{p['name']}: {look}")
            else: used.add((k["id"], key))
dead = [f"{kid}/{n}" for kid, t in T.items() for n in t if (kid, n) not in used]
print(f"material table: {slots} part slots, {len(gaps)} without an entry, {len(dead)} unused entries")
for g in gaps[:20]: print("  GAP", g)
for d in dead: print("  UNUSED", d)
sys.exit(1 if gaps else 0)
