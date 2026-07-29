# Changelog

## [1.0.5] - 2026-06-13
### Fixed
- **Multiplayer Sync**: Fixed a multiplayer synchronization issue where players other than the summoner could not see the SubBoss health bars, and the main Heart health bar did not update for them.
- **Localization**: Fixed an issue where SubBoss names would sometimes display their unlocalized internal names (e.g. `$enemy_troll`) on client UI. The UI now dynamically localizes all names for everyone.

## [1.0.4] - 2026-06-10
### Changed
- **Blighted Item Upgrades & Repairs Fixed**: Blighted weapons and armors can now be properly upgraded and repaired by all players. We completely reworked how the recipes are handled under the hood so they no longer require admin privileges or "nocost" to function.
- **Dynamic Upgrade Costs**: Upgrading a Blighted item now requires the same base materials as its vanilla counterpart, *plus* the biome-specific trophies. They remain entirely uncraftable.
  - *Example*: Upgrading a "Blighted Sword Iron of the Serpent" from Level 1 to Level 2 will cost 20 Iron, 3 Wood, 2 Draugr Trophies, and 2 Leech Trophies (using the base Iron Sword upgrade cost plus Swamp trophies).

## [1.0.3] - 2026-06-09
- Internal testing build

## [1.0.2]
- Accidently updated v1.0.0 as v1.0.1; this package labelled v1.0.2 is the corrected version

## [1.0.1] - 2026-06-09

### Changed
- **Weapon Rebalancing**: Significantly reduced the overall damage scaling and flat elemental damage (Poison/Spirit) bonuses on Blighted weapons to bring them back in line with vanilla progression curves.
- **Shield Categorization**: Fixed an issue where custom shields were incorrectly categorized as weapons. Shields now properly receive the Bastion/Blight defensive armor modifiers instead of weapon damage bonuses.
- **Swamp Boss Altar Spawn**: Adjusted the spawn logic for the Blighted World Heart when summoned in the Swamp biome. The Heart will now properly offset outward from the altar and drop to the ground, preventing it from spawning out of reach on top of the giant skull roof or getting stuck inside.

### Fixed
- **Custom Item Repairs**: Fixed an issue where Blighted custom items (weapons and armors) could not be repaired at normal crafting stations. They now properly tie into the Workbench, Forge, and Black Forge for standard, cost-free repairing.
- **Damage Filtering Fix (Invulnerability)**: Fixed a major oversight where the Blighted World Heart could still be damaged by generic non-player environmental attacks (such as Troll AoE log swings and Abomination body slams). The damage filtering logic has been strictly enforced directly into the Heart's core damage receiver to block all non-player entity damage. 
- **Tamed Minion Exception**: Added an explicit exception to the new damage filter allowing players *and* their tamed or summoned creatures (e.g., wolves, lox, Dead Raiser skeletons) to successfully damage the Heart.
