<div align="center">

# 📜 Changelog
**The Blighted World Heart**

</div>

---

## 🟢 [1.1.0]

### ✨ Added
- **A real Deep North Heart (Valheim 1.0).** The Deep North was a Mountain stand-in until now (wolf waves, Fenring/Golem Sub-Bosses, silver-tier loot, wolf trophies for upgrades). It now uses the Deep North that shipped with Valheim 1.0:
  - **Loot**: Blighted variants of all 12 Frost-Fire gold weapons (sword, mace, axe, atgeir, spear, knife, bow, crossbow, greatsword, battleaxe, fists, sledge) and the Heavy and Medium armor lines (chest, legs, helmet), the Deep North cape and the three gold shields — 76 new Blighted items, all upgraded at the Black Forge. The Mage line is left out, like the Mistlands and Ashlands mage gear.
  - **Waves**: Frozen Greydwarves, Deep North Skeletons and Elakings. **Sub-Bosses**: Jötun Warrior, Jötun Witch, Barka, Frost Troll.
  - **Upgrade trophies**: Elaking and Writhan trophies.
  - **Summoning**: the default sacrifice is now **1x Sacrificial Blood** (Kall Fimbulbringer's drop), following the "local boss's drop" rule every other biome uses; it was Fader's drop as a placeholder. Existing config files keep whatever value they already have.
- **`Allow Refinement Forge Upgrades` config (General, default off).** Valheim 1.0's Refinement Forge upgrades items with Upgrader items — past max quality, with a chance to fail or destroy the item. Off, Blighted items upgrade only at their normal station with trophies + materials, as always. On, they are also refinable there for the same 1 Upgrader per level as their base item, break risk included.

### 🛠️ Fixed
- **Upgrade costs on Valheim 1.0 (all biomes).** Every 1.0 weapon/armor recipe carries an `Upgrader` entry (1, none per level) for the Refinement Forge, and Deep North gear also needs a one-off `Mold`. The material injection turned both into a **1-per-level cost at the forge**, so every Blighted upgrade demanded an Upgrader item (and, for Deep North, a Mold) per level that vanilla never asks for there. Injection now carries over exactly what vanilla charges to *upgrade* the base item: per-level materials only; one-off crafting ingredients are skipped, and Upgrader entries are dropped unless the new config is on.
- **Dead Ashlands entries.** `SwordFlametal` and `MaceFlametal` no longer exist in 1.0, so those six Blighted variants were silently never created (the log's 326 of 332). Removed from the Ashlands list; the seven real Ashlands weapons were already there.
- **Requirement icons.** Picking up a Blighted item is meant to mark its upgrade ingredients as known so the Upgrade tab shows their icons instead of "?"; it was recording the prefab name where the game looks up the display name, so it never took effect.
- **CRITICAL - Free crafting with Wacky's Database installed.** Since 1.0.6, detecting Wacky's Database switched off the Craft-tab filter that keeps Blighted items drop-only. Because every Blighted recipe is built with a zero cost at level 1 (the recipe only exists to power the Upgrade tab), that meant **every one of the 326 Blighted weapons and armors could be crafted for free** at any Workbench / Forge / Black Forge on any server running WackyDB. The filter now always runs. It is still fully YAML-friendly: it only hides Blighted recipes that are literally free at level 1, so a server admin who gives a Blighted item a real level-1 cost in a WackyDB recipe YAML will see it become craftable, exactly as before. If you run WackyDB, update immediately.
- **Upgrade costs with Wacky's Database installed.** The same 1.0.6 compatibility mode also skipped adding the base item's vanilla materials to *every* Blighted upgrade recipe whenever WackyDB was merely present, so upgrades cost two biome trophies and nothing else. Now only Blighted recipes that actually have a WackyDB recipe YAML (`BepInEx/config/wackysDatabase/Recipes/`, matched by the YAML's `name: Recipe_Blighted...` key) are left to the YAML; every other Blighted recipe gets its normal trophies + vanilla materials upgrade cost, exactly as on a server without WackyDB. Clients that receive a server's YAML through WackyDB's own sync (nothing is written to their disk) are covered too: a Blighted recipe that no longer carries the trophy-only requirements this mod registered is treated as YAML-owned and left alone.
- **Heart placement at the Valheim 1.0 Deep North altar.** The Heart is now placed by the same rules vanilla uses for the altar's own boss (the altar's explicit spawn point, its solid-height margin and its Y offset). The 1.0 Deep North altar sits inside an enclosed boss room with a 4 m margin; the old fixed 1000 m ground ray started above that room and would have put the Heart on its roof. The six older altars carry the default 1000 m margin and behave exactly as before, including the Swamp skull push-out.
- **Wave and Sub-Boss placement indoors.** Summoned enemies and Sub-Bosses now try a short ground ray first (so inside a boss room they land on the floor, not the roof) and only fall back to the full-height ray on open terrain, where the short ray can start below an uphill slope. Spawn points are picked on a horizontal disc around the Heart rather than a sphere, so the ground snap no longer depends on a random vertical offset.
- **BarrkBOT export: correct biome on dedicated servers.** The export read each Heart's biome from the loaded terrain heightmap, and a dedicated server only has heightmaps around the world origin - every Heart elsewhere was filed under biome `None`. It now falls back to the world generator's biome (pure seed math, valid anywhere), so defeats are recorded against the right biome. (Live "active / HP%" readings still depend on the Heart being instantiated on the server, which only happens near the origin on a dedicated server - see README.)

---

## 🟢 [1.0.10]

### 🛠️ Fixed
- **Valheim 1.0.7 compatibility.** Rebuilt for Valheim 1.0.7 (client build 25185596 / dedicated server build 25185644, network version 39) against BepInExPack 5.4.2350 and **Jotunn 2.30.0** - the first Jotunn release for Valheim 1.0, which is now the minimum required version. No gameplay code changed and nothing about the mod behaves differently: every hook this mod places on the game (`Character.Damage` / `RPC_Damage` / `OnDeath`, `Player.OnSpawned` / `GetAvailableRecipes` / `AddKnownItem`, `OfferingBowl.Interact` / `UseItem`, `ZNet.Start` / `Shutdown`) resolves on 1.0.7 exactly as before, and the 1.0 engine changes that broke other mods (sector ids, equipment visuals, save paths, `Inventory.Load`) are all in code this mod never touches. Verified on a 1.0.7 dedicated server: the Heart prefab, 326 Blighted items and 326 upgrade recipes register with no errors.
- The Jotunn build reference is pinned to exactly 2.30.0 (it used to float to "any 2.x"), so a rebuild can never silently pick up a pre-1.0 Jotunn and produce a DLL that only fails once it is in the game.

---

## 🟢 [1.0.9]

### 🛠️ Fixed
- **Shadows of Midgard Sub-Boss Compatibility**: Sub-Bosses are now stamped with a networked flag that tells Shadows of Midgard to leave them alone entirely — no stealth detection, no flee/retreat orders — on every connected peer, not just whichever client currently owns the Sub-Boss. Previously the internal fix only worked for whoever spawned the Sub-Boss locally; if ownership of that entity migrated to another player mid-fight (common in multiplayer), SoM could make the Sub-Boss break off and flee like a startled deer. No effect if Shadows of Midgard isn't installed.

---

## 🟢 [1.0.8]

### ✨ Added
- **Massively Expanded Loot Matrix**: Nearly every biome now offers significantly more base weapons and armor pieces to draw Blighted variants from — Ashlands alone grew from 2 weapons to 9 (adding Jötunn-Bane, Krom, Berzerkr, Eldner, Niedhogg, Splitner, and the Ashlands longbow), and Swamp gained four additional shield types. Total unique Blighted items rose from ~210 to 330+.
- **Optional BarrkBOT Server Metrics Export**: Server admins can now enable a lightweight, read-only status export (`BepInEx/config/BlightedHeart/barrkbot_blightedheart.json`) reporting per-biome raid state — whether the Heart is currently active, its health percentage, active Sub-Bosses, and lifetime summon/defeat counts — for external tools like BarrkBOT to read. Off by default is *not* the default here; it's on by default but fully inert (writes nothing) if disabled via the new `BarrkBOT Export` config section. World/event data only — no player data is collected or written.

### 🛠️ Fixed
- **Crafting Station Assignment**: Station selection for Blighted item upgrade recipes (Workbench / Forge / Black Forge) is now determined by the item's biome directly instead of guessing from substrings in the vanilla item's name. The old substring approach silently misrouted certain real vanilla names (e.g. a Mistlands weapon that happens to cost Silver was being routed to the Forge instead of the Black Forge).

---

## 🟢 [1.0.7]

### 🛠️ Fixed
- **Crafting List Blank Page Conflict**: Completely resolved a critical incompatibility with AzuAntiArthriticCrafting (and other UI overhaul mods) where opening a crafting station without materials would result in a completely empty recipe list. The root cause was that BWH's recipe filtering occurred too late in the rendering pipeline, causing UI paginators to draw empty pages. The filtering has been relocated to run at the engine level, seamlessly integrating with third-party pagination and sorting.
- **AAACrafting / No-Cost Mode Compatibility**: Admins and testers with the `nocost` cheat active (or AAACrafting's no-cost mode) can now successfully preview and spawn every Blighted recipe in the Craft tab. Previously, the hiding logic ignored no-cost state.
- **WackyDB Compatibility Gap**: WackyDB installs now correctly bypass BWH's internal UI hiding logic, handing full control to server admins via YAML, as originally intended.
- **Recipe Validation Pass**: Added a strict post-initialization validation sweep that scans all injected custom items for corrupted or missing data (like a null `m_dlc` field), repairing them instantly to prevent vanilla Valheim from throwing exceptions during recipe enumeration.
- **Recipe Resolution Reliability**: Vanilla-material injection for Blighted upgrade recipes now retries on subsequent player spawns if `ObjectDB` is delayed during initial world load, preventing permanent recipe breakage in heavily modded multiplayer servers.
- **Deep North Wave/Sub-Boss Fallback**: Fixed an issue where the Blighted World Heart spawned in the Deep North would silently fall back to spawning trivial Boars. It now correctly falls back to Mountain-tier enemies and bosses, matching the fallback loot table for the biome.

### ⚖️ Changed
- **Magical Damage Mitigation**: Added a new configuration option `Magic Damage Multiplier` (default 0.25). Magic and elemental damage from late-game magical weapons is now calculated separately and heavily reduced against the Blighted World Heart **and its Sub-Bosses**, ensuring they can withstand arcane assaults and don't get instantly obliterated by staves.
- **Boss Vitality Boost**: Increased the default HP configuration values for the main Blighted World Heart and all Sub-Bosses by 15% across all biomes to compensate for high-tier player damage.
- **Configuration Overhaul**: Rewrote the internal configuration descriptors to be much clearer on exactly what each setting does. Also added strict minimum and maximum acceptable value ranges to all numerical configurations to prevent accidental typos from breaking the mod.

---

## 🟢 [1.0.6]
### ✨ Added
- **Wacky's Database Compatibility Mode**: Added seamless, automatic integration with Wacky's Database. Upon startup, if Wacky's Database is detected, BlightedWorldHeart will automatically bypass its internal dynamic recipe modifications and UI hiding logic. This hands over total, unadulterated control to server admins and players who wish to customize Blighted weapon/armor stats and recipes using WackyDB's YAML files, safely preventing any recipe injection conflicts or crashes.

### ⬆️ Updated
- **Dependencies**: Updated Jotunn dependency to v2.29.1.

---

## 🟢 [1.0.5]
### 🛠️ Fixed
- **Multiplayer Sync**: Fixed a multiplayer synchronization issue where players other than the summoner could not see the SubBoss health bars, and the main Heart health bar did not update for them.
- **Localization**: Fixed an issue where SubBoss names would sometimes display their unlocalized internal names (e.g. `$enemy_troll`) on client UI. The UI now dynamically localizes all names for everyone.

---

## 🟢 [1.0.4]
### 🔄 Changed
- **Blighted Item Upgrades & Repairs Fixed**: Blighted weapons and armors can now be properly upgraded and repaired by all players. We completely reworked how the recipes are handled under the hood so they no longer require admin privileges or "nocost" to function.
- **Dynamic Upgrade Costs**: Upgrading a Blighted item now requires the same base materials as its vanilla counterpart, *plus* the biome-specific trophies. They remain entirely uncraftable.
  - *Example*: Upgrading a "Blighted Sword Iron of the Serpent" from Level 1 to Level 2 will cost 20 Iron, 3 Wood, 2 Draugr Trophies, and 2 Leech Trophies (using the base Iron Sword upgrade cost plus Swamp trophies).

---

## 🟢 [1.0.3]
- 🧪 Internal testing build

---

## 🟢 [1.0.2]
- 🩹 Accidently updated v1.0.0 as v1.0.1; this package labelled v1.0.2 is the corrected version

---

## 🟢 [1.0.1]
### ⚖️ Changed
- **Weapon Rebalancing**: Significantly reduced the overall damage scaling and flat elemental damage (Poison/Spirit) bonuses on Blighted weapons to bring them back in line with vanilla progression curves.
- **Shield Categorization**: Fixed an issue where custom shields were incorrectly categorized as weapons. Shields now properly receive the Bastion/Blight defensive armor modifiers instead of weapon damage bonuses.
- **Swamp Boss Altar Spawn**: Adjusted the spawn logic for the Blighted World Heart when summoned in the Swamp biome. The Heart will now properly offset outward from the altar and drop to the ground, preventing it from spawning out of reach on top of the giant skull roof or getting stuck inside.

### 🛠️ Fixed
- **Custom Item Repairs**: Fixed an issue where Blighted custom items (weapons and armors) could not be repaired at normal crafting stations. They now properly tie into the Workbench, Forge, and Black Forge for standard, cost-free repairing.
- **Damage Filtering Fix (Invulnerability)**: Fixed a major oversight where the Blighted World Heart could still be damaged by generic non-player environmental attacks (such as Troll AoE log swings and Abomination body slams). The damage filtering logic has been strictly enforced directly into the Heart's core damage receiver to block all non-player entity damage.
- **Tamed Minion Exception**: Added an explicit exception to the new damage filter allowing players *and* their tamed or summoned creatures (e.g., wolves, lox, Dead Raiser skeletons) to successfully damage the Heart.
