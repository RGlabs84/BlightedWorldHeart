<div align="center">

# 📜 Changelog
**The Blighted World Heart**

</div>

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
