"""Generated blocks for README.src.md (called by libs-Tools/readme-forge/forge_readme.py).

Every number here is read from the C# source, so the store page shows exactly what the DLL ships:
- ConfigManager.cs: the per-biome SetupBiomeConfig(...) defaults and the HP-per-tier constants;
- BlightedWorldHeartAI.cs: the wave lists per biome;
- BlightedSubBosses.cs: the six Hive Sub-Bosses (display names, donors) and which altar calls which (ByBiome);
- BlightedItemsManager.cs: the Blighted base items per biome and the affix formulas.
"""
import os
import re

HERE = os.path.dirname(os.path.abspath(__file__))

RUNE_SEALS = {
    "ᚺ": "the name: hail, the storm that breaks everything",
    "ᛞ": "what is new",
    "ᚾ": "what you need to know first",
    "ᛇ": "the Heart: the yew, death that endures",
    "ᚦ": "the horde: the thorn, a force hostile to all",
    "ᛜ": "the spoils: the seed, treasure stored",
    "ᛃ": "the ledger of numbers",
    "ᚠ": "the toolbox",
    "ᚷ": "multiplayer",
    "ᛗ": "other mods",
    "ᛚ": "the settings",
    "ᛟ": "the credits",
}

BIOMES = ["Meadows", "BlackForest", "Swamp", "Mountain", "Plains", "Mistlands", "AshLands", "DeepNorth"]
BIOME_LABEL = {"Meadows": "🌳 Meadows", "BlackForest": "🌲 Black Forest", "Swamp": "🐸 Swamp", "Mountain": "🏔️ Mountain",
               "Plains": "🌾 Plains", "Mistlands": "🌫️ Mistlands", "AshLands": "🔥 Ashlands", "DeepNorth": "❄️ Deep North"}

# English names of the vanilla prefabs the defaults use (from the game's own item names: libs-Tools
# 1.0/ASSET-DATA/prefab_names_1_0_15.txt, the newest name dump on file). A name missing here fails the forge.
NAMES = {
    "HardAntler": "Hard Antler", "CryptKey": "Swamp Key", "Wishbone": "Wishbone", "DragonTear": "Dragon Tear",
    "YagluthDrop": "Torn Spirit", "QueenDrop": "Majestic Carapace", "FaderDrop": "Kindled Ribs", "FrozenKingDrop": "Sacrificial Blood",
    "Boar": "Boar", "Neck": "Neck", "Greyling": "Greyling", "Greydwarf": "Greydwarf", "Greydwarf_Elite": "Greydwarf Brute",
    "Skeleton": "Skeleton", "Draugr": "Draugr", "Blob": "Blob", "Leech": "Leech", "Wolf": "Wolf", "Hatchling": "Drake",
    "Goblin": "Fuling", "Deathsquito": "Deathsquito", "Seeker": "Seeker", "SeekerBrood": "Seeker Brood",
    "Charred_Melee": "Charred Warrior", "Charred_Archer": "Charred Marksman", "Greydwarf_Frozen": "Frozen Greydwarf",
    "Skeleton_DeepNorth": "Deep North Skeleton", "Elaking": "Elaking", "Troll": "Troll", "Skeleton_Poison": "Rancid Remains",
    "Draugr_Elite": "Draugr Elite", "Wraith": "Wraith", "Abomination": "Abomination", "Fenring": "Fenring",
    "StoneGolem": "Stone Golem", "GoblinBrute": "Fuling Berserker", "GoblinShaman": "Fuling Shaman", "Lox": "Lox",
    "SeekerBrute": "Seeker Soldier", "Morgen": "Morgen", "JotunWarrior": "Jotun Warrior", "JotunWitch": "Jotun Witch",
    "Barka": "Barka", "TrollFrost": "Frost Troll", "Greydwarf_Shaman": "Greydwarf Shaman",
}


def _src(name):
    with open(os.path.join(HERE, name), encoding="utf-8-sig") as fh:
        return fh.read()


def _name(k):
    if k not in NAMES:
        raise SystemExit(f"readme_gen: no English name for '{k}' - add it to NAMES")
    return NAMES[k]


def _config():
    src = _src("ConfigManager.cs")
    unit = {k: float(v) for k, v in re.findall(r"const float (\w+HpPerTier) = ([\d.]+)f;", src)}
    rows = {}
    for b, tier, t1, t2, loot, maxe, timer, item, amt in re.findall(
            r'SetupBiomeConfig\(plugin, Heightmap\.Biome\.(\w+), ([\d.]+)f, ([\d.]+)f, ([\d.]+)f, ([\d.]+)f, (\d+), ([\d.]+)f, "(\w+)", (\d+)\)',
            src):
        t = float(tier)
        rows[b] = dict(tier=t, t1=float(t1), t2=float(t2), loot=float(loot), maxe=int(maxe), timer=float(timer), item=item, amt=int(amt),
                       heart=unit["HeartHpPerTier"] * t, sb1=unit["SubBoss1HpPerTier"] * t, sb2=unit["SubBoss2HpPerTier"] * t)
    if sorted(rows) != sorted(BIOMES):
        raise SystemExit(f"readme_gen: read biomes {sorted(rows)} from ConfigManager.cs")
    return rows


def _lists(fn_name):
    src = _src("BlightedWorldHeartAI.cs")
    body = re.search(fn_name + r"\(Heightmap\.Biome biome\)(.*?)\n        }", src, re.S).group(1)
    out = {}
    for b, lst in re.findall(r"case Heightmap\.Biome\.(\w+):\s*(?:return new\[\]|options = new\[\])\s*\{([^}]*)\}", body):
        out[b] = re.findall(r'"(\w+)"', lst)
    return out


def _hive_subbosses():
    """{biome: [display names]} and {def name: (display, donor)} from BlightedSubBosses.cs (the Sub-Boss pool per altar)."""
    src = _src("BlightedSubBosses.cs")
    defs = {n: (disp, donor) for n, donor, disp in re.findall(
        r'public static readonly Def (\w+) = new Def \{ Id = "\w+", Donor = "(\w+)", DisplayName = "([^"]+)" \};', src)}
    body = re.search(r"ByBiome = new Dictionary<Heightmap\.Biome, Def\[\]>(.*?)\n        \};", src, re.S).group(1)
    pool = {}
    for b, lst in re.findall(r"\{ Heightmap\.Biome\.(\w+), (All|new\[\] \{[^}]*\}) \}", body):
        names = list(defs) if lst == "All" else re.findall(r"(\w+)(?=[ ,}])", lst.split("{", 1)[1])
        pool[b] = [defs[n][0] for n in names]
    if sorted(pool) != sorted(BIOMES) or len(defs) != 6:
        raise SystemExit(f"readme_gen: read {len(defs)} Sub-Boss defs and biomes {sorted(pool)} from BlightedSubBosses.cs")
    return pool, defs


def subbosses(forge):
    pool, defs = _hive_subbosses()
    rows = ["| Sub-Boss | Grown from | Calls at |", "|---|---|---|"]
    for n, (disp, donor) in defs.items():
        at = [BIOME_LABEL[b] for b in BIOMES if disp in pool[b] and len(pool[b]) < 6]
        rows.append(f"| **{disp}** | a {_name(donor)} | {', '.join(at) if at else '—'} · and the Ashlands and Deep North altars |")
    return "\n".join(rows)


def _items():
    src = _src("BlightedItemsManager.cs")
    per = {}
    for b, w, a in re.findall(r"CreateBiomeItems\(Heightmap\.Biome\.(\w+),\s*new\[\] \{([^}]*)\},(?:\s*//[^\n]*)?\s*new\[\] \{([^}]*)\}\)", src):
        per[b] = (len(re.findall(r'"\w+"', w)), len(re.findall(r'"\w+"', a)))
    return per


def _check_items(per):
    if sorted(per) != sorted(BIOMES):
        raise SystemExit(f"readme_gen: read item biomes {sorted(per)} from BlightedItemsManager.cs")


def item_count():
    _check_items(_items())
    return sum(3 * w + 4 * a for w, a in _items().values())


def _fmt(n):
    return f"{int(round(n)):,}"


def hud(forge):
    cfg = _config()
    lo, hi = min(r["heart"] for r in cfg.values()), max(r["heart"] for r in cfg.values())
    return ("| 🫀 **8 altars** | 👹 **6 Hive Sub-Bosses** | 🗡️ **" + str(item_count()) + " items** | ☠️ **One faction** |\n"
            "|:-:|:-:|:-:|:-:|\n"
            f"| every vanilla boss altar | two rise as the Heart bleeds | Blighted gear to loot | the horde turns on everyone |")


def ledger(forge):
    cfg = _config(); waves = _lists("GetWaveEnemiesForBiome"); subs, _ = _hive_subbosses()
    head = "| Altar | Sacrifice | Heart HP | Sub-Bosses at | Sub-Boss HP |\n|---|---|---|---|---|"
    out = [head]
    for b in BIOMES:
        r = cfg[b]
        out.append(f"| **{BIOME_LABEL[b]}** | {r['amt']}× {_name(r['item'])} | **{_fmt(r['heart'])}** | "
                   f"{int(r['t1'] * 100)}% · {int(r['t2'] * 100)}% | {_fmt(r['sb1'])} · {_fmt(r['sb2'])} |")
    out += ["", "<details>", "<summary>📜 <b>The whole ledger</b> — waves, Sub-Boss pools, horde size and loot power per altar</summary>", "",
            "| Altar | Wave creatures | Sub-Boss pool | Horde size | Wave every | Loot power |", "|---|---|---|---|---|---|"]
    for b in BIOMES:
        r = cfg[b]
        out.append(f"| **{BIOME_LABEL[b]}** | {', '.join(_name(k) for k in waves[b])} | {'any of the six' if len(subs[b]) == 6 else ', '.join(subs[b])} | "
                   f"{r['maxe']} | {r['timer']:g} s | ×{r['loot']:g} |")
    out += ["", "</details>"]
    return "\n".join(out)


def affixes(forge):
    cfg = _config()
    s = [cfg[b]["loot"] for b in BIOMES]
    lo, hi = min(s), max(s)

    def rng(f):
        return f"{f(lo):g}–{f(hi):g}"
    return "\n".join([
        "| Affix | On a weapon | On armour or a cape |",
        "|---|---|---|",
        f"| **of the Serpent** 🐍 | +{rng(lambda x: 10 * x)} poison damage | resistant to poison |",
        f"| **of the Wraith** 👻 | +{rng(lambda x: 10 * x)} spirit damage | resistant to spirit |",
        f"| **of the Blight** ☢️ | +{rng(lambda x: 5 * x)} poison **and** spirit, physical +{rng(lambda x: 5 * x)}% more | resistant to poison **and** spirit, armour +{rng(lambda x: 5 * x)}% |",
        f"| **of the Bastion** 🏰 | — | armour +{rng(lambda x: 10 * x)}%, durability ×1.5 |",
        "",
        f"Every Blighted piece also starts stronger than its vanilla twin: weapons hit +{rng(lambda x: 5 * x)}% harder and armour is "
        f"+{rng(lambda x: 5 * x)}% tougher, before the affix. The range runs from the Meadows (×{lo:g}) to the Deep North (×{hi:g}).",
    ])


def count(forge):
    return str(item_count())
