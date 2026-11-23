<!--
  SOURCE of the store README (README schema v3). Edit THIS file, never HexiumDistrib/README.md. Forge it with:
    python3 ../libs-Tools/readme-forge/forge_readme.py README.src.md HexiumDistrib/README.md --manifest HexiumDistrib/manifest.json --code-root .
  Numbers come from readme_gen.py (read from the C# source); every setting name goes through {{key ...}} and is checked against the code.
  The six Hive Sub-Bosses and their altars come from BlightedSubBosses.cs (the generated sub-boss table and the ledger pool column).
-->
# 🫀 The Blighted World Heart

{{rune ᚺ | THE BLIGHTED WORLD HEART | A RAID AT EVERY ALTAR | 5b2a6e}}
{{badge VERSION | {{version}} | 8b1e1e}}
{{badge CLIENT + SERVER | EVERYONE NEEDS IT | 1f4e79}}

{{gen hud}}

> *The skalds say the Hive was never killed, only scattered. Feed a boss's altar the wrong offering and a shard of it takes root there, beats once, and calls everything with teeth.*

### Turn any boss altar into a siege.

Offer a boss's own trophy-drop at its vanilla altar and a Blighted World Heart erupts in its place: a shrunken shard of the Hive that never stops calling the local monsters down on you. Break it while the horde keeps coming.

As it bleeds it summons Sub-Bosses. When it dies it scatters Blighted gear, stronger cousins of the biome's own weapons and armour, one more piece for every Viking who stood there with you.

---

{{rune ᛞ | NEW IN {{version}} | THE HIVE'S OWN · ONE FACTION | 8b1e1e}}

**The Heart no longer borrows its Sub-Bosses. Six of its own crawl out of the Hive, and everything it calls now fights on one side.**

| You | It |
|---|---|
| **wear a Heart down** | calls one of six Hive Sub-Bosses: vanilla creatures overgrown with the Hive's bark crust, roots, branches and staring eyes |
| **fight at different altars** | meet different ones: each altar has its own (the Ledger names them), the Ashlands and Deep North can call any of the six |
| **fight a Black Forest Heart** | Greydwarfs and Skeletons come for you together instead of brawling with each other |
| **bring tames** | your wolves and boars fight the horde, and the horde fights them |
| **fight near wild creatures or another boss** | the horde attacks them too: the Heart is an enemy of everything |
| **are the server admin** | {{key Blighted Faction}} turns the faction off and gives the summons their vanilla factions back |

🔹 Each Sub-Boss takes on the Heart's biome colour, and keeps its faction when someone logs off mid-fight and the area changes hands.

---

{{rune ᚾ | BEFORE YOU INSTALL | READ THIS | b8860b}}

| | If… | Then… |
|---|---|---|
| 🤝 | you play on a **server** | the server and every player need the mod, on the same version. Jotunn checks this when you join. |
| 🧩 | you **install it** | you also need **Jotunn**. |
| 📜 | you run **Wacky's Database** | it is detected on start, and any Blighted recipe you give a YAML is yours to control (see Compatibility). |
| 🏰 | you **summon a Heart** | it uses the boss altar, not the boss: the vanilla boss is not summoned by the same offering. |

---

{{rune ᛇ | I | THE HEART AWAKENS | 5b2a6e}}

**Place the biome boss's own drop on its altar, and the Heart rises after the altar's usual build-up.**

| You | The Heart |
|---|---|
| **offer the sacrifice** | erupts at the altar's spawn point, tinted to the biome it infests |
| **strike it** | takes physical damage in full, and elemental or magic damage at a quarter by default ({{key Magic Damage Multiplier}}) |
| **wear it down** | summons its first Sub-Boss at half health and its second at a fifth (per altar: {{key Sub-Boss Threshold 1}}, {{key Sub-Boss Threshold 2}}) |
| **break it** | drops 3 Blighted items, plus 1 for every other player within 100 m |

A health bar tracks the Heart and both Sub-Bosses on screen.

---

{{rune ᚦ | II | THE HORDE | 5b2a6e}}

**Every few seconds the Heart refills its horde with the local monsters, up to a cap per altar, and points them at the nearest player.**

| Wave | |
|---|---|
| 🧟 **The creatures** | drawn from the biome: Greydwarfs and Skeletons in the Black Forest, Draugr and Blobs in the Swamp, Fulings in the Plains |
| 💰 **Their loot** | the waves drop nothing, so the fight cannot be farmed; each Sub-Boss has a {{key Sub-Boss Gear Drop Chance}} (25%) to drop one Blighted piece of its altar's biome |
| 👹 **The Sub-Bosses** | the Hive's own six, half again the size of the creature they grew from, starred, with their own health set per altar |
| ⚔️ **Sub-Boss damage** | the creature they grew from hits just as hard, no more, and never harder than the hardest-hitting vanilla creature of the altar's biome; {{key Sub-Boss Damage Multiplier}} scales it (1) |

{{gen subbosses}}

The full lists per altar are in the Ledger.

---

{{rune ᛜ | III | THE SPOILS | 5b2a6e}}

**Blighted gear: the biome's own weapons, shields, armour and capes, reforged with one of four affixes. {{gen count}} pieces in all, Meadows to Deep North.**

{{gen affixes}}

Blighted gear drops only from the Heart. You upgrade it at the usual station with the biome's trophies plus the base item's own materials, so it grows with you.

---

{{rune ᛃ | THE LEDGER | DEFAULTS PER ALTAR | 3d3d3d}}

{{gen ledger}}

---

{{rune ᚠ | THE TOOLBOX | QUICK START · HOW-TO | 1b1b1b | 8b1e1e | e8c35a}}

<details>
<summary>⚡ <b>Your first Heart</b></summary>

1. Kill the biome's boss once and keep its drop (the Ledger names it per altar).
2. Go back to that boss's altar with a group: the horde scales with nobody, but the loot does.
3. Use the drop on the altar. Step back: the Heart takes a few seconds to rise.
4. Clear the first wave, then commit to the Heart. The Sub-Bosses come at half health and at a fifth.

</details>

<details>
<summary>🛠️ <b>Upgrade a Blighted item</b></summary>

Pick it up and it appears in the station's **Upgrade** tab, never the Craft tab: Blighted gear is loot, not a recipe. Each level costs the biome's trophies plus the base item's own materials. With {{key Allow Refinement Forge Upgrades}} on, the Refinement Forge can push it further, with vanilla's chance to fail.

</details>

---

{{rune ᚷ | MULTIPLAYER | WHO NEEDS WHAT | 1f4e79}}

| Without the mod | The server | Each player |
|---|---|---|
| a player cannot join a server that runs it (Jotunn refuses the version mismatch) | owns every setting; all of them are admin-only and sync to players | sees the Heart and the health bar; whoever owns the Heart's area runs its waves and Sub-Bosses |

The **minor** version must match: 1.2.x joins 1.2.x.

---

{{rune ᛗ | COMPATIBILITY | OTHER MODS | 2e5e3a}}

| Mod | |
|---|---|
| 📜 **Wacky's Database** | a Blighted recipe with a WackyDB YAML (`name: Recipe_Blighted…`) is left entirely to that YAML; the rest keep their normal upgrade cost. Give one a real level-1 cost and it becomes craftable. |
| ⚒️ **No-cost / creative modes** | the vanilla `nocost` cheat (and crafting mods built on it) shows Blighted recipes in the Craft tab too. |
| 🌑 **Shadows of Midgard** | Sub-Bosses are exempt from its stealth senses and retreat orders. |
| 📡 **BarrkBOT** | an optional read-only status file, `BepInEx/config/BlightedHeart/barrkbot_blightedheart.json`: per altar, active or not, Heart health, live Sub-Bosses and lifetime summons and kills. World data only, no player data. |

---

{{rune ᛚ | SETTINGS | CONFIGURATION MANAGER · F1 | b8860b}}

Every setting is 🔒 **server-only**: the admin sets it and it syncs to everyone.

<details>
<summary>🔒 <b>General</b></summary>

| Setting | |
|---|---|
| {{key Blighted Faction}} | the horde is one faction, hostile to everything (on) |
| {{key Sub-Boss Level}} | Sub-Boss star level, 1–5 (2); since 1.2.1 the stars add no damage |
| {{key Sub-Boss Damage Multiplier}} | Sub-Boss damage as a multiple of the vanilla creature's hit, 0.1–3 (1) |
| {{key Sub-Boss Gear Drop Chance}} | chance a slain Sub-Boss drops one Blighted piece of its biome, 0–1 (0.25) |
| {{key Magic Damage Multiplier}} | how much elemental and magic damage the Heart and Sub-Bosses take (0.25) |
| {{key Allow Refinement Forge Upgrades}} | Blighted items can also be upgraded at the Refinement Forge (off) |
| {{key Enable Wave Announcement}} · {{key Wave Announcement Location}} | the wave message and where it shows |
| {{key Debug Mode}} | verbose logging |

</details>

<details>
<summary>🔒 <b>Per altar</b> — one section per biome</summary>

| Setting | |
|---|---|
| {{key Boss HP}} | the Heart's health |
| {{key Sub-Boss Threshold 1}} · {{key Sub-Boss Threshold 2}} | the Heart's health fraction that calls each Sub-Boss |
| {{key Sub-Boss 1 HP}} · {{key Sub-Boss 2 HP}} | each Sub-Boss's health |
| {{key Max Enemies Per Wave}} · {{key Wave Timer Seconds}} | horde cap and refill interval |
| {{key Altar Summon Item}} · {{key Altar Summon Amount}} | the sacrifice |
| {{key Loot Scale Factor}} | how strong this altar's Blighted gear is |

</details>

<details>
<summary>🔒 <b>BarrkBOT Export</b></summary>

| Setting | |
|---|---|
| {{key Enable BarrkBOT Export}} | write the status file (on, server-side) |
| {{key Export Interval Seconds}} | how often it is rewritten (30 s) |

</details>

---

{{rune ᛟ | CREDITS | THANK YOU | 1b1b1b | c9a227 | 1b1b1b}}

Made by **Wubarrk** for Raven Iron. Built on **Jotunn** and **BepInEx**. MIT licensed: use, change and share it, keeping the copyright notice.

<details>
<summary>ᛟ <b>The runes on this page</b></summary>

{{runes}}

</details>
