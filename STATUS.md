<!-- CHECKPOINT -->
Updated: 2026-11-22
RELEASED 1.2.0 (owner: "publish to hexium ts and gh"), FROZEN: HexiumDistrib/BlightedWorldHeart-v1.2.0.zip (md5 2a64161a, DLL d6246458)
  - Thunderstore Wubarrk-BlightedWorldHeart-1.2.0 (download back 7 of 7 files identical); Hexium upload 522 (6 of 7: manifest
    rewritten as usual); store APIs still showed latest 1.1.4 / 1.1.3 right after upload (cache / review) - poll was running.
  - GitHub (public RGlabs84/BlightedWorldHeart): release v1.2.0 with the same zip (md5 checked), branch release/1.2.0 (4790d72),
    PR #1 to main OPEN (not merged: owner's call).
  - Carried forward from TS-only 1.1.4: website https://ravenirongames.com/ + its CHANGELOG entry.
  - Gate: 7 PASS, 0 FAIL, 4 NOT ASSESSED (design check: no DESIGN.md; clean Gale install; 1.1.3 saves; multiplayer).
Next step: confirm both listings show 1.2.0; owner: merge PR #1, Gale pass (clean install, old saves, two players). Any change
  now = 1.2.1 (1.2.0 is frozen). Later: Husk Root armour route, vertex colours (not possible with the game's shaders).
Public repo: art/subbosses is WHITELISTED in .gitignore (our runtime data + scripts + recipes/weights only; .blend, donor
  meshes, renders stay local - the owner backs them up).
Owner decisions 2026-11-22: biome mapping; tint multiplied ("they look fine"); Husk Root armour left off.
NO SUBAGENTS ("just you"). Batch heavy runs, light work in parallel.
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
