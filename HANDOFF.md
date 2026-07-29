# Handoff: BlightedHeart crafting-list regression (2026-07-28)

## Environment / conventions (read this first)

- Repo: `c:\WubarrkCODING\BlightedHeart` — Valheim BepInEx/Jotunn mod, .NET Framework 4.8. **Not a git repo** — there is no commit history or diff to inspect; everything described below is just the current on-disk state of the listed files.
- Reference DLLs live in the **shared** `C:\WubarrkCODING\libs-Tools\` folder, not a per-project `libs\` folder. `BlightedHeart.csproj` references it via `..\libs-Tools\<dll>` HintPaths (migrated this session — do not recreate a local `libs\` or `decompiled\` folder in this project).
- `libs-Tools` already contains a full decompiled dump of the live game assembly at `DECOMPILED ASSEMBLY VALHEIM\assembly_valheim.decompiled.cs` (~145k lines). Grep that before decompiling anything fresh. Key locations already found this session: `InventoryGui` class ~line 41121, `UpdateRecipeList` ~line 42039 (also inside there, the `InCraftTab()`/`else` branch split), `InCraftTab()`/`InUpradeTab()` ~lines 43079–43087, `Player.NoCostCheat()` ~line 21056.
- `ilspycmd` (dotnet global tool) is available for decompiling. It targets .NET 6, which isn't installed — always run it with `DOTNET_ROLL_FORWARD=LatestMajor` prefixed, e.g. `DOTNET_ROLL_FORWARD=LatestMajor ilspycmd -r "<Managed dir>" -t "<TypeName>" "<path>\assembly_valheim.dll"`.
- AAACrafting's own decompiled source (plain C# text, despite the extension) is at `COMPAT DATA\AAACrafting-TS-2.1.6.blob` in this repo — grep it instead of re-decompiling AAACrafting's DLL from scratch.
- Terminology: never say "r2modman" or "Thunderstore" — the mod manager is **Gale**, the ship/distribution flow is **Hexium**. Distribution package lives in `HexiumDistrib\`; the canonical files are the **top-level** ones (`manifest.json`, `CHANGELOG.md`, `README.md`, `icon.png`, `plugins\BlightedHeart.dll`) — `HexiumDistrib\temp_zip\` is a stale, out-of-sync leftover from an old release, ignore it.
- Test profile: Gale profile **`CodeTesterVS-Modpack`** (real folder name — the user sometimes says "CodeVs-Modpack Tester", word order flipped) at `C:\Users\rglmo\AppData\Roaming\com.kesomannen.gale\valheim\profiles\CodeTesterVS-Modpack`. This is Gale's real data directory (`com.kesomannen.gale`), **not** the legacy `r2modmanPlus-local` path that also exists on this machine — don't confuse the two. This profile is a **heavy 50+ mod modpack** (AzuAntiArthriticCrafting/AAACrafting 2.1.6, Jotunn, ServerCharacters, MistsofAvalor, Seasonality, Server Devcommands, Groups, TargetPortal, HildirsBuildPieces, ComfyMods Gizmo/Hygge, MarketplaceAndServerNPCs, and more) — it is not a clean repro environment.

## Original bug (believed fixed, needs re-confirmation once the new regression is resolved)

AAACrafting wasn't displaying Blighted World Heart loot items in its crafting UI, even with AAACrafting's "no cost mode" enabled. Root cause, confirmed by decompiling the real `assembly_valheim.dll` plus AAACrafting's own decompiled source:

`BlightedItemsManager.cs`'s `HideBlightedCrafting` Harmony prefix on `InventoryGui.UpdateRecipeList` unconditionally strips every `"Blighted"`-prefixed recipe from the vanilla Craft tab, because they're intentionally "upgrade only" items (looted from the boss, then upgraded — trophies and injected vanilla materials both cost `0` at level 1 by design, so they always satisfy the removal predicate). That check never consulted `Player.NoCostCheat()` (the vanilla `nocost` admin/debug flag — AAACrafting's own "no cost mode" toggle is a thin wrapper around this same flag, confirmed via a background research pass through AAACrafting's decompiled source), so no-cost mode could never make them reappear.

## Fixes applied this session

1. **`BlightedItemsManager.cs`, `HideBlightedCrafting`** (current code, lines 424–445):
   ```csharp
   [HarmonyPatch(typeof(InventoryGui), nameof(InventoryGui.UpdateRecipeList))]
   [HarmonyPrefix]
   public static void HideBlightedCrafting(List<Recipe> recipes)
   {
       if (BlightedHeartPlugin.IsWackyDBInstalled) return;
       if (Player.m_localPlayer != null && Player.m_localPlayer.NoCostCheat()) return;

       if (recipes != null && InventoryGui.instance != null && InventoryGui.instance.InCraftTab())
       {
           recipes.RemoveAll(r =>
               r != null &&
               r.m_item != null &&
               r.m_item.gameObject.name.StartsWith("Blighted") &&
               IsRecipeFreeAtLevel1(r)
           );
       }
   }
   ```
   Added the two early-return bypasses (WackyDB, NoCostCheat). Everything below that is unchanged from before.

2. **`BlightedItemsManager.cs`, `ResolveVanillaRecipeMaterials`** (current code, lines 162–230): moved `_recipesResolved = true` so a null `ObjectDB.instance` on the first `Player.OnSpawned` call no longer permanently disables vanilla-material injection for the rest of the session — it now retries on the next spawn instead of silently latching "done" on failure.

3. **`BlightedWorldHeartAI.cs`**: added missing `Heightmap.Biome.DeepNorth` cases to `GetWaveEnemiesForBiome`/`GetSubBossForBiome` (previously fell back to trivial `"Boar"`). Unrelated to the crafting UI, included here only for completeness.

4. Version bumped `1.0.7` → `1.0.8` (`Plugin.cs`, `BlightedHeart.csproj`, `HexiumDistrib\manifest.json`), changelog entry added, Release build rebuilt, `HexiumDistrib\BlightedWorldHeart-v1.0.8.zip` repackaged (had to hand-build it via `System.IO.Compression.ZipArchive` — PowerShell's `Compress-Archive` writes backslash-separated entry paths on Windows, which would've been inconsistent with every prior release zip's forward-slash entries), and deployed into the `CodeTesterVS-Modpack` profile's `BepInEx\plugins\Wubarrk-BlightedWorldHeart\` folder (DLL + manifest.json + CHANGELOG.md + README.md + icon.png).

## New regression reported after deploying 1.0.8

User confirms: Blighted items **do** now show under no-cost mode (original bug fix appears to be working). **But**: nothing at all shows in the workbench/forge crafting recipe list — not Blighted items, not vanilla items, nothing. This is a new symptom relative to the original complaint (which implied vanilla items were showing fine before; only Blighted items were the problem).

## Diagnostics already gathered this session (read-only, no code changes made for this part)

Checked `BepInEx\LogOutput.log` in the `CodeTesterVS-Modpack` profile (2609 lines, session ended with a clean shutdown/save at 12:01:42, not a crash):

- `BlightedWorldHeart 1.0.8` loaded successfully.
- `Resolved vanilla recipe materials for 210 blighted items (0 could not be resolved)` logged **exactly once** — rules out the `ResolveVanillaRecipeMaterials` retry fix causing a duplicate run / doubled-up resource requirements.
- `AzuAntiArthriticCrafting 2.1.6` (AAACrafting) loaded fine, ConfigSync registered.
- **No exceptions anywhere** — searched case-insensitively for "exception", "error", "stack trace", "harmony", "missingmethod", "nullreference"; only unrelated `Custom/SkyboxProcedural` shader warnings turned up.
- Forge + `forge_ext1`..`forge_ext6` pieces were placed and leveled up successfully this session. Note this is the **piece/build-hammer system** (`PieceTable`), a different code path from the **item recipe crafting list** (`Recipe` / `InventoryGui.UpdateRecipeList`) that's actually reported broken — so this does NOT confirm the item-crafting list ever worked this session.
- `Setting selected recipe -1` / `Setting selected recipe 0` (vanilla `InventoryGui.SetRecipe` logging) oscillates repeatedly while the crafting panel was open — consistent with the visible recipe count fluctuating between 0 and a very small number, though this could also just be normal UI/category navigation noise. Not conclusive on its own.
- Checked AAACrafting's own config, `BepInEx\config\Azumatt.AzuAntiArthriticCrafting.cfg`: `Limit recipes to station with nocost mode = Off` and `Respect station level with nocost mode = Off` — both disabled, so AAACrafting's own station-limiting no-cost behavior (a real mechanism found earlier this session by research through its decompiled source) is **ruled out** as the cause.
- `Server Devcommands` is installed in this profile, which is how an admin would toggle `nocost` — combined with the user's own "shows in nocost" test, it's very likely `nocost` was actively ON during this test, meaning `Player.NoCostCheat()` returned `true`.

## Why this doesn't cleanly point at the code changed this session — reasoning to hand off

- `HideBlightedCrafting`'s `RemoveAll` predicate hard-requires `r.m_item.gameObject.name.StartsWith("Blighted")`. It is structurally incapable of removing non-Blighted (vanilla) recipes, no matter what else is wrong with it.
- If `nocost` was active during this test (very likely, see above), the new early-return (`if (... NoCostCheat()) return;`) means `HideBlightedCrafting` skipped its `RemoveAll` entirely — i.e., for this specific test, the patch effectively did *nothing* to the list at all.
- Per the decompiled vanilla `InventoryGui.UpdateRecipeList` (confirmed this session, see `libs-Tools` reference above), the Craft-tab branch does **not** filter recipes based on nocost/afford-ability at all — nocost only affects the `canCraft` bool passed to `AddRecipeToList` (green/red highlighting), not whether a recipe appears. Under nocost, vanilla should show every known recipe regardless.
- Conclusion: the empty list is likely **not explained by any of the three fixes made this session**. Two live possibilities: (a) a pre-existing bug in this heavily-modded 50+ mod profile that simply wasn't noticed before, because prior testing was narrowly focused on "are Blighted items visible" rather than "is the list empty entirely"; or (b) a genuine new interaction, but if so its mechanism isn't yet visible in the log and isn't explained by the actual logic of either changed method.

## Concrete next steps

1. **Get a clean, minimal repro.** Test in a profile with just BepInEx + Jotunn + BlightedHeart (no AAACrafting, no other ~48 mods). This is the single highest-value step — it immediately tells you whether AAACrafting or some other mod in the pack is required to reproduce this, or whether it's BlightedHeart alone.
2. If it reproduces with BlightedHeart alone: temporarily disable the `[HarmonyPatch]` on `HideBlightedCrafting` (comment out the attribute) and rebuild, to conclusively confirm or rule out this specific patch as the cause.
3. Add temporary logging at the top of `HideBlightedCrafting` — log `Player.m_localPlayer?.NoCostCheat()` and `recipes.Count` before and after the `RemoveAll` — there is currently zero runtime visibility into this method's actual behavior; the log evidence gathered above is all inference, not direct observation of this method.
4. Enable BlightedHeart's own verbose logging: `BepInEx\config\wubarrk.blightedworldheart.cfg` → `[General] Debug Mode = true`.
5. Check for a Harmony patch-order conflict: AAACrafting patches `InventoryGui.UpdateRecipeList` with **three** of its own patches (`FavoritingPatches.UpdateRecipeListPatch`, `InventoryGui_RemoveVanillaSorting_CodeMatcher` transpiler, `PaginatorPatches.InventoryGuiUpdateRecipeListPatch.Prefix` — all previously located in `COMPAT DATA\AAACrafting-TS-2.1.6.blob`). Neither BlightedHeart's patch nor (as far as found so far) AAACrafting's declare explicit `[HarmonyPriority]`/`Before`/`After` ordering. Try adding explicit priority to `HideBlightedCrafting` and see if that changes anything — but only after step 1 tells you AAACrafting is actually involved.
6. Get exact repro steps from the user before doing anything else if possible: which station, nocost on or off, which UI (vanilla crafting menu vs. AAACrafting's overlay) — and ideally a fresh `LogOutput.log` bounded to just that one repro (rotate/delete the log first).
