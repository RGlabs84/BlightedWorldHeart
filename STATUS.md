<!-- CHECKPOINT -->
Updated: 2026-11-23
RELEASED 1.2.1 hotfix (owner: "publish 1.2.1 to hexium ts and gh"), FROZEN: HexiumDistrib/BlightedWorldHeart-v1.2.1.zip
  (md5 eaeb47b5, DLL 27b9a970). Thunderstore Wubarrk-BlightedWorldHeart-1.2.1 (download back 7 of 7 identical); Hexium
  upload 522 (6 of 7: manifest rewritten as usual). GitHub: branch release/1.2.1, release v1.2.1 with the same zip.
Fixed (owner playtest 2026-11-23): Sub-Boss damage = donor's vanilla hit, no star bonus, capped per biome (owner: "cap to
  biome"); no vanilla loot from any summon on any machine + Sub-Boss gear roll 25% (owner's pick); the Heart saves its biome
  and Sub-Boss memory, so it resumes after everyone dies / a reload (was: no waves, Sub-Bosses or loot).
Gate: 7 PASS, 0 FAIL, 4 NOT ASSESSED. Build 0/0; refcheck client+server OK (4654 refs, 16 Harmony targets); server smoke
  PASS (6 of 6 prefabs, 0 errors); client autotest 140 of 140 (new phases D damage/drops, R resume); fold 0 failed of 20,
  26 badges checked, PDB match. NOT ASSESSED: design check (no DESIGN.md), clean Gale install, 1.2.0 saves, multiplayer.
Rollback: players go back to the 1.2.0 zip; 1.2.1 only adds ZDO keys (blighted_biome, blighted_summoned) that 1.2.0 ignores.
Next step: owner's Gale pass (clean install, a 1.2.0 world with a live Heart, two players). PR #1 (1.2.0 -> main) still open;
  release/1.2.1 contains it. Any further change = 1.2.2.
NO SUBAGENTS ("just you"). Batch heavy runs, light work in parallel. Never push or mirror to TheWall / Google Drive.
<!-- /CHECKPOINT -->

# BlightedHeart status

## Checks run 2026-11-21 (faction fix)
- Build (Release, /usr/bin/dotnet via heavy.sh): PASS, 0 errors.
- refcheck vs 1.0.21 client + dedicated server Managed: PASS, 2820 refs and 14 of 14 Harmony targets resolved, both.
- IsEnemy decision table (vanilla 1.0.21 IsEnemy body compiled verbatim + the postfix): PASS, 0 failed of 60 checks.
- Server boot check: NOT ASSESSED (the testbed's boot-check.sh and profiles are not on this machine).
- In-game combat (waves no longer infight, tames fight summons): NOT ASSESSED, needs a Gale pass.

## README: validated against the code and upgraded to schema v3 (2026-11-22)
Source `README.src.md` + `readme_gen.py` (numbers read from ConfigManager.cs / BlightedWorldHeartAI.cs / BlightedItemsManager.cs) ->
forged `HexiumDistrib/README.md` (libs-Tools/readme-forge: 26 badges, 12 runes, every setting name checked against the code).
The old v2-era README (kept at scratchpad README_v2_before_forge.md for this session) failed 9 of 26 claims checked:
| Old claim | Code says | Result |
|---|---|---|
| Black Forest waves "led by towering Trolls" | waves are Greydwarf, Greydwarf Brute, Skeleton; Troll is only in the Sub-Boss pool | FAIL |
| Plains waves "a stampede of ... enraged Loxes" | waves are Fuling, Deathsquito; Lox only in the Sub-Boss pool | FAIL |
| Sub-Bosses are "2-Star" | default Sub-Boss Level 2 = ONE star | FAIL |
| "Blight" weapon affix is "ultra-rare, god-tier" | every affix variant is in the drop pool with equal chance | FAIL |
| "Blight" armour has a "monstrous multiplier" | +5% x scale armour, less than Bastion's +10% x scale | FAIL |
| Serpent armour = "absolute resistance" | Resistant (vanilla's half-damage tier), not immune | FAIL |
| Plains sacrifice "Yagluth Thing" | YagluthDrop = Torn Spirit | FAIL |
| Mistlands "Queen Drop" / Ashlands "Fader Drop" | Majestic Carapace / Kindled Ribs (1.0.15 name data; confirm on 1.0.21) | FAIL |
| (missing) Blighted Faction, Refinement Forge setting, Magic Damage Multiplier | in code | added |
PASS (17): any boss altar; biome tint; 3 + 1 per extra player within 100 m drops; 360+ items (367 defined in code); health bar for Heart
+ both Sub-Bosses; admin-only settings synced via Jotunn; WackyDB YAML behaviour; Sub-Boss Level +50% per level (Attack.cs:1046);
per-biome HP/threshold/wave/sacrifice/loot settings; BarrkBOT export path + section; default sacrifice amount 1; Hard Antler; Swamp Key;
Wishbone; Dragon Tear; Sacrificial Blood; MIT license.
NOT ASSESSED: Thunderstore renderer preview + badge fetch (--check-badges) - do at the release gate; Fader/Queen display names on 1.0.21.
TODO at the sub-boss integration: README.src.md chapter II + ledger Sub-Boss pool -> the six custom Hive sub-bosses, then re-forge.
