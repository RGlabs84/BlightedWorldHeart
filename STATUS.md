<!-- CHECKPOINT -->
Updated: 2026-11-22
Current task: 1.2.0 RELEASE GATE run (mod-release). Verdict NOT ASSESSED: 7 PASS, 0 FAIL, 4 NOT ASSESSED of 11 steps.
  PASS: 1 build 0 err / 0 warn (CS0436 publicizer suppressed by name) | 2 refcheck client + server OK | 3 server smoke
  (tools/server-smoke.sh, fake HOME, prefs untouched, 6 of 6 prefabs, 0 errors; note: no 'World saved' line seen) | 4 autotest
  97 of 97 on DLL md5 d6246458 | 6 leftovers none in 16 .cs | 7 credits | 8 fold (tools/fold.py) 0 failed of 20, 26 badges
  checked, PDB match, zip HexiumDistrib/BlightedWorldHeart-v1.2.0.zip (7 entries, DLL = the tested md5).
  NOT ASSESSED: 5 design check (no DESIGN.md) | 9 clean Gale install | 10 1.1.3 saves | 11 multiplayer (second client).
Next step: owner: Gale pass with the zip (clean install, a 1.1.3 world/character, a two-player Heart fight), then upload the SAME
  zip to Hexium AND Thunderstore (plain X.Y.Z). Commit/tag/upload only when the owner asks. The zip is not frozen until uploaded.
Blocked on: the owner's Gale pass / upload decision.
Files changed (uncommitted): *.cs (faction, sub-bosses, kit, materials, repaint), BlightedHeart.csproj (PDB, embeds, tools/**
  excluded), art/subbosses/{runtime,kit_tools}, tools/{bh-autotest,fold.py,server-smoke.sh}, README.src.md, readme_gen.py,
  HexiumDistrib/{README.md,CHANGELOG.md,plugins/*.dll+pdb,BlightedWorldHeart-v1.2.0.zip}, art/ASSETS.md, STATUS.md.
Owner decisions 2026-11-22: biome mapping (BlightedSubBosses.ByBiome); tint multiplied ("they look fine"); Husk Root armour left off.
NO SUBAGENTS ("just you"). Batch heavy runs, light work in parallel. Repaint dumps: ~/valheim-testbed/bh-repaint-mirror.
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
