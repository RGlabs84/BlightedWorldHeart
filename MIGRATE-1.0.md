# BlightedHeart — Valheim 1.0.7 migration instructions

> **2026-09-15 — BlightedHeart 1.1.0. The "no source change needed" verdict below was wrong on the DATA side.**
> Every Harmony target and API signature really is unchanged (`Heightmap.FindBiome(Vector3)`,
> `ZoneSystem.GetSolidHeight(Vector3, out float, int = 1000)`, `OfferingBowl.*` — identical pre-1.0 → 1.0.7 → 1.0.12),
> but four things 1.0 changed in *content* broke behaviour without touching a signature:
> 1. **Recipes carry `UpgraderN{Weapon,Armor}` entries** (`m_amount 1, m_amountPerLevel 0, m_upgraderResource true`;
>    82 of the 82 base items with a recipe) for the new `UpgradeStation` ("Refinement Forge", `CraftingStation.m_upgrader`),
>    and Deep North gear carries one-off `Mold*` ingredients. `ResolveVanillaRecipeMaterials`' `max(1, amount/2)` fallback
>    turned both into 1-per-level forge costs. Now: per-level materials only; upgrader entries only behind
>    `General / Allow Refinement Forge Upgrades` (default off), copied verbatim with the flag.
> 2. **`SwordFlametal` / `MaceFlametal` no longer exist** — the "326 of 332 registered" gap. Removed.
> 3. **The Deep North altar (`offeraltar_FrozenKing_bossroom`) is inside an enclosed room** with `m_spawnPoints=[spawnpoint]`,
>    `m_getSolidHeightMargin=4`: the fixed 1000 m ray placed the Heart (and waves) on the roof. Spawn now mirrors
>    `OfferingBowl.GetSpawnPosition/CanSpawnBoss`; waves try a 4 m ray first.
> 4. **`Heightmap.FindBiome` returns `None` without a loaded heightmap**, i.e. everywhere but the origin on a dedicated
>    server (unchanged since pre-1.0, but the BarrkBOT export is new and server-side). Falls back to `WorldGenerator.GetBiome`.
> Plus the 1.0 Deep North content is now wired in (see CHANGELOG 1.1.0). Source of truth for the data claims:
> `/home/rohan/valheim-testbed/profiles/v1012-TheEye/BepInEx/config/WubarrksEye_Dumps/2026-09-11_10-32-25/Values_Dump.json`.

> **Verified 2026-09-11 on Valheim 1.0.12 (build 25253764/25253791, network version 40) - BlightedHeart 1.0.10, no change
> needed.** The 1.0.10 DLL built on 2026-09-09 (md5 `d245a51474abc900c5198134661bce6b`, identical in `bin/Release/net48/`,
> `HexiumDistrib/plugins/` and the staged testbed copy) was re-audited against the 1.0.7 -> 1.0.12 engine delta (37 types,
> 55 body changes, 5 methods added, 1 removed, 6 fields added, 1 removed, `Version.c_networkVersion` 39 -> 40; only
> `assembly_valheim` changed, every other game assembly is IL-identical; Jotunn 2.30.0 and BepInExPack 5.4.2350 are still
> the latest releases). Nothing is broken and nothing needs adapting, so the version was NOT bumped, nothing was rebuilt
> and the csproj was not touched.
>
> Touchpoints and verdicts (source line -> 1.0.12 evidence):
> - **Harmony targets** (10, all attribute-based, no transpilers, no `AccessTools`/reflection-string lookups - grep of the
>   source root confirms): `Character.RPC_Damage` (Plugin.cs:115), `Character.Damage` (BlightedItemsManager.cs:484),
>   `Player.OnSpawned` (:475), `Player.GetAvailableRecipes` (:506), `Player.AddKnownItem(ItemDrop.ItemData)` (:542, pinned
>   `Type[]`), `OfferingBowl.Interact` / `UseItem` (BlightedHeartSpawning.cs:10 / 23), `ZNet.Start` / `Shutdown`
>   (BarrkBotExport.cs:194 / 201): none of these members is in the asmdiff changed list (`ZNet`'s five changes are
>   `OpenServer`, `SendPeerInfo`, `RPC_PeerInfo`, `ListContainsId`, `DelayThenRegisterCoroutine`) - **unaffected**.
>   `Character.OnDeath` (BlightedHeartLoot.cs:8) IS body-changed, but the IL diff
>   (`MigrationStation/diffs/server_assembly_valheim_1.0.7_to_1.0.12.ildiff.txt` line 127) shows exactly one instruction,
>   `ldsfld PlayerProfile::s_bypassCheatChecks` -> `call PlayerProfile::get_s_bypassCheatChecks()`, and the decompiled
>   body (1.0.7 line 3069 vs 1.0.12 line 3076) is identical; the patch is a plain Prefix reading `__instance` only -
>   **unaffected**.
> - **`IDestructible`** (BlightedWorldHeartAI.cs:9, Plugin.cs:86): still `void Damage(HitData)` /
>   `DestructibleType GetDestructibleType()` (1.0.12 decompile line 124139); no interface appears anywhere in the diff; no
>   method gained a non-defaulted parameter (the 5 added methods are three private `ZDOMan` conversion helpers, the
>   private `AchievementUnlockPopup.TryPlaySfx` and the `s_bypassCheatChecks` getter) and no constructor changed shape
>   (`CookingStation`/`PresentManager` `.ctor` changed only in field initialisers) - **unaffected**.
> - **`PlayerProfile.s_bypassCheatChecks` field -> property**: no reference in source (grep `s_bypassCheatChecks|
>   bypassCheat|PlayerProfile`: none) or in the DLL (refcheck, 2543 references OK on client and server) - **unaffected**.
>   The vanilla bodies that changed only by this one read (`Character.ApplyDamage`/`OnDeath`, `Inventory.AddItem`,
>   `InventoryGui.DoCrafting`, `Attack.DoMeleeAttack`, `Container.AddDefaultItems`, `Piece.DropResources`, ...) behave
>   identically unless a player runs the new `yesiuseddevcommandsbutiwantmyachievementsanyway` command, which is
>   vanilla-wide and not specific to Blighted items.
> - **`Player.HaveRequirementItems` discover-path fix** (1.0.12 decompile 12159; the `!discover &&` added to the
>   upgrader-station clause): the Blighted upgrade recipes carry only `m_amount = 0` / `m_amountPerLevel > 0` requirements
>   (BlightedItemsManager.cs:225-231, 345-351, 402-408) with the default `m_upgraderResource = false`; in discover mode
>   every such requirement reaches `if (requirement.m_amount <= 0) continue;` whichever way the moved clause evaluates, so
>   `UpdateKnownRecipesList` auto-knows the recipes exactly as on 1.0.7; the non-discover craft/upgrade path is unchanged
>   and `AddKnownItemPrefix`'s `m_knownMaterial` seeding is untouched - **unaffected**.
> - **`ItemDrop.SaveToZDO` guard flip** (`index < 0` -> `index > -1`, decompile 70766): loot is spawned by
>   `Object.Instantiate` of the registered item prefab (BlightedWorldHeartAI.cs:304, BlightedHeartLoot.cs:46) and saved by
>   vanilla `ItemDrop.Save()` with index -1 onto a fresh ZDO; on 1.0.7 the block read `s_quality`/`s_variant` back with
>   the item's own values as defaults and so never wrote anything on a fresh ZDO, on 1.0.12 it is skipped - same result,
>   and the `s_itemData` blob write is unchanged. `ZDOMan.ConvertContainers` runs only for worlds older than
>   `Version.World.ChunkedSave` and only on ZDOs carrying `s_stack` / `{i}_stack` / `s_items`; the Heart's ZDO holds the
>   `blighted_health` / `blighted_max_health` floats and `blighted_subboss1/2` ZDOIDs, the sub-boss ZDO an int
>   `SoMStealthExempt` (BlightedWorldHeartAI.cs:36-39, 595) - **unaffected**.
> - **Console commands**: none registered (grep `ConsoleCommand|Terminal|hideBehindDevCommands|isCheat`: no hits), so the
>   relaxed `Terminal.ConsoleCommand.IsValid` / `ShowCommand` / `Chat.isAllowedCommand` gating has nothing to act on -
>   **unaffected**. **Version / network version**: the only version strings are the plugin's own `PluginVersion`
>   (Plugin.cs:12/19/47, BarrkBotExport.cs:165 `source` field) and Jotunn's `[NetworkCompatibility(EveryoneMustHaveMod,
>   Minor)]` (Plugin.cs:14), which compares the MOD version between peers, never the game's network version; no
>   `Version.`/`c_networkVersion`/`GetVersionString` anywhere - **unaffected** (the 39 -> 40 bump only means 1.0.7 and
>   1.0.12 peers cannot connect, which is vanilla).
> - **Not referenced at all** (grep): cheated-item flag / `Inventory.Changed` popup / `ItemDrop.OnCreateNew`,
>   `CookingStation.m_spawnFullDurability` / `SpawnItem`, `Smelter`, `Fermenter`, `Container.AddDefaultItems`,
>   `Piece.DropResources`, `MineRock.RPC_Hit`, `ItemSets`, `TerrainComp.PaintCleared`, `GrapplingPoint`, `RuneStone`,
>   `AchievementUnlockPopup`, `Achievements.CanGetAchievements`, `ServerOptionsGUI`, `ZoneSystem.TestSpawnLocation`,
>   `FejdStartup`, `MasterClient`, PlayFab/Steam matchmaking - **unaffected**.
> - **`Character.UpdateGroundContact` / `Attack.DoMeleeAttack` snow clearing**: the Heart has its `Character` stripped at
>   Awake (BlightedWorldHeartAI.cs:65-69) and hooks no `m_onLand`; sub-bosses and wave mobs are unmodified vanilla prefabs
>   (BlightedWorldHeartAI.cs:468, 553) and pick up the vanilla-wide Deep North landing cosmetic like any creature; the
>   `DoMeleeAttack` IL change touches only the snow-shovel branch and the bypass read, not the `IDestructible` dispatch the
>   Heart is hit through - **unaffected**. **`Destructible.Destroy` null guard**: the Heart strips `Destructible`
>   (BlightedWorldHeartAI.cs:87) and takes damage through `IDestructible` on `BlightedDamageForwarder` - **unaffected**.
> - **`ZNet.ListContainsId` (`flag |=`)**: the mod itself checks only `ZNet.instance.IsServer()` (BarrkBotExport.cs:44).
>   The `IsAdminOnly` config attributes (ConfigManager.cs) are resolved by Jotunn's SynchronizationManager, which does
>   reference `ZNet.ListContainsId` / `m_adminList` (strings present in `libs-Tools/Jotunn.dll`, md5 identical to the
>   profile's copy); the change makes old `Steam_` and new `V_` ID forms both match - strictly more permissive, inside
>   unchanged Jotunn code, no adaptation - **unaffected**.
> - **Everything else the mod calls** - `ZDOMan.m_onZDODestroyed`, `ZDO.GetPrefab/GetPosition/GetFloat/Set/GetZDOID`,
>   `InventoryGui.InCraftTab`, `Player.NoCostCheat/m_knownMaterial`, `ObjectDB.m_recipes/GetItemPrefab`,
>   `Inventory.RemoveItem`, `Heightmap.FindBiome`, `ZoneSystem.GetSolidHeight`, `ZNetScene.GetPrefab/FindInstance`,
>   `Character.SetLevel/SetMaxHealth/SetHealth/IsDead/GetHealth/GetMaxHealth/m_boss/m_name`, `HitData.GetAttacker/m_damage`,
>   `BaseAI.Alert`, `MonsterAI.SetTarget`, `Player.GetPlayersInRange/GetClosestPlayer/MessageAllInRange`,
>   `DamageText.ShowText`, `EffectList.Create`, `Humanoid.Message/GetInventory`, `Hud.m_rootObject`,
>   `Localization.Localize`, `StringExtensionMethods.GetStableHashCode`, `ZNetView.*` - none in the changed-member list -
>   **unaffected**.
>
> Evidence: refcheck of the staged DLL against the 1.0.12 client and dedicated-server Managed folders, both `checked 2543
> references, 10 Harmony targets (0 dynamic) - RESULT: OK`
> (`/tmp/claude-1000/-home-rohan-WubarrkCODING/7e501e8a-0a25-46f2-aaca-99a485eceb49/scratchpad/refcheck-1012/final-BlightedHeart-BlightedHeart-{client,server}.txt`).
> Boot on the 1.0.12 Linux dedicated server (`Valheim version: l-1.0.12 (network version 40)`), profile
> `~/valheim-testbed/profiles/final-BlightedHeart`: `BOOTED after 23s`, `Loading [BlightedWorldHeart 1.0.10]`,
> `BlightedWorldHeart v1.0.10 loaded.`, `BlightedWorldHeart prefab registered. Runtime cleanup will happen on spawn.`,
> `Blighted custom items created.`, Jotunn `Adding 327 custom prefabs` / `326 custom items` / `326 custom recipes` /
> `Registering 2 custom RPCs`; `BepInEx/LogOutput.log` is line-for-line identical (timestamps aside) to the same
> profile's 1.0.7 run preserved in `logs-1.0.7-run/LogOutput.log` (42 lines each); no Harmony/Missing*/TypeLoad line in
> either `LogOutput.log` or `server-console.log`, the only warnings are the same eight Jotunn ambiguous-asset notes.
> Result file:
> `/tmp/claude-1000/-home-rohan-WubarrkCODING/7e501e8a-0a25-46f2-aaca-99a485eceb49/scratchpad/boot-1012/final-BlightedHeart.txt`.
> Engine delta consulted: `MigrationStation/diffs/{server,client}_assembly_valheim_1.0.7_to_1.0.12.md` + `.ildiff.txt`,
> the decompile diffs under `.../scratchpad/decomp-diff/`, and the 1.0.7 / 1.0.12 decompiles in `libs-Tools`. Still
> open, unchanged from 09-09: not exercised with a client attached. Pre-existing and unrelated to 1.0.12, noted only:
> the `Character.OnDeath` prefix in BlightedHeartLoot.cs never fires for the Heart (its `Character` is stripped at Awake;
> loot actually drops from `BlightedWorldHeartAI.OnDeath`), and the sub-boss cleanup at BlightedWorldHeartAI.cs:568
> compares against `"DropOnDestroy"` while the vanilla class is `DropOnDestroyed`.

> **Applied 2026-09-09 - BlightedHeart 1.0.10.** Jotunn 2.30.0 (the Valheim 1.0.7 release) landed today, so
> the block in section 1 is lifted. Done: `JotunnLib` pinned to `[2.30.0]` (was `2.*`);
> `obj/project.assets.json` resolves `JotunnLib/2.30.0`; version bumped to 1.0.10 in the csproj, `Plugin.cs`
> and `HexiumDistrib/manifest.json` (manifest dependencies moved to `denikson-BepInExPack_Valheim-5.4.2350`
> and `ValheimModding-Jotunn-2.30.0`); CHANGELOG entry added; DLL staged by hand to `HexiumDistrib/plugins/`
> (the project has no post-build copy step). No source change was needed - exactly as section 2 predicted.
> Re-verified every claim there against the 1.0.7 decompile: `Character.Damage(HitData)`,
> `Character.RPC_Damage(long, HitData)`, `Character.OnDeath()`, `Player.OnSpawned(bool)`,
> `Player.GetAvailableRecipes(ref List<Recipe>)`, `Player.AddKnownItem(ItemDrop.ItemData)` (one overload;
> the pinned `Type[]` still matches), `OfferingBowl.Interact(Humanoid, bool, bool)` / `UseItem(Humanoid,
> ItemDrop.ItemData)`, `ZNet.Start()` (private), `ZNet.Shutdown(bool save = true)` - all present, all
> unchanged. Jotunn API used (`PrefabManager.Instance.CreateClonedPrefab/GetPrefab/AddPrefab`,
> `ItemManager.Instance.AddItem/AddRecipe`, `CustomItem`, `CustomPrefab`, `CustomRecipe(RecipeConfig)`,
> `RequirementConfig`, `ConfigurationManagerAttributes`, `Jotunn.Logger`) confirmed present with the same
> shapes in the 2.30.0 decompile (`ilspycmd libs-Tools/Jotunn.dll`), and the build against it is clean.
>
> Evidence: `dotnet build BlightedHeart.csproj -c Release` - 0 errors (3 pre-existing CS0436 publicizer
> warnings). refcheck against the real 1.0.7 client Managed folder: `checked 2543 references, 10 Harmony
> targets (0 dynamic) - RESULT: OK`; against the dedicated-server Managed folder: same, `RESULT: OK`.
> Boot-check on the 1.0.7 Linux dedicated server (profile `~/valheim-testbed/profiles/blighted`, port 2631,
> BepInEx 5.4.2350 + Jotunn 2.30.0): `BOOTED after 25s`; log has `Loading [Jotunn 2.30.0]`,
> `Loading [BlightedWorldHeart 1.0.10]`, `BlightedWorldHeart v1.0.10 loaded.`, `BlightedWorldHeart prefab
> registered. Runtime cleanup will happen on spawn.`, `Blighted custom items created.`, then Jotunn's
> `Adding 327 custom prefabs to the ZNetScene` / `Adding 326 custom items to the ObjectDB` / `Adding 326
> custom recipes to the ObjectDB` / `Registering 2 custom RPCs`; no Harmony/Missing*/TypeLoad lines in
> either log. The only warnings are eight `Jotunn.Managers.AssetManager` "Ambiguous asset name for path"
> notes - Jotunn indexing vanilla's own duplicate prefab paths, identical in the other two Jotunn profiles
> of this lane, not attributable to this mod. Logs: `~/valheim-testbed/profiles/blighted/BepInEx/LogOutput.log`
> and `.../server-console.log`. No off-game test project exists in this repo.
>
> Jotunn 2.30.0 caveat ("Piece categories are not updated yet"): not applicable - BlightedHeart registers no
> build pieces (no `PieceManager` / `CustomPiece` / `PieceConfig` / `PieceTable` anywhere in the source); it
> registers one creature prefab, items and recipes. Open: not exercised with a client attached (the crafting
> list, the WackyDB branch and `BlightedWorldHeartAI.cs:61`'s `VisEquipment` lookup noted in section 2 are
> client-side); the credential footnote below still stands.

**Status: THIS MOD'S OWN CODE IS 1.0-CLEAN. It is BLOCKED on Jotunn, which is not yet 1.0-ready.**
Audited 2026-09-09 against `libs-Tools/1.0/DECOMPILED/` (client 1.0.7, build 25185596, network 39).

No source change is required in this repository. Every Harmony target resolves on 1.0.7 and every
signature it depends on is unchanged. The one action item is the dependency.

---

## 1. The blocker: Jotunn

`BlightedHeart.csproj` declares:

```xml
<PackageReference Include="JotunnLib" Version="2.*" />
```

This mod uses `Jotunn.Managers.ItemManager`, `Jotunn.Entities.CustomRecipe`, `Jotunn.Configs.RecipeConfig`/`RequirementConfig`, `Jotunn.Logger`.

**Jotunn needs a 1.0 release before this mod can ship against 1.0.7.** Jotunn's `ExtEquipment` reads the
`VisEquipment` `m_*Item` fields, which 1.0 converted from `string` to `int` hashes — so Jotunn itself is
broken on 1.0 until upstream updates. Mists of Avalor is blocked on the same thing.

### The floating version is a hazard right now

`Version="2.*"` resolves to whatever the newest 2.x is **at restore time**. That cuts both ways:

- **Good:** when Jotunn ships a 1.0-compatible 2.x, a plain `dotnet restore` picks it up with no csproj edit.
- **Bad:** until then, a restore silently pulls a **pre-1.0** Jotunn, and the build succeeds. You get a
  DLL that looks fine and fails at runtime inside Jotunn, not inside your code — which is a slow thing
  to diagnose.

Until upstream updates, **pin the version explicitly** so the reference set is honest about what it is:

```xml
<PackageReference Include="JotunnLib" Version="[2.24.3]" />   <!-- replace with the version you actually validated -->
```

Then unpin (or move the pin) when the 1.0-compatible release lands. Also check
`libs-Tools/Jotunn.dll` — the copy there is dated **2026-03-06**, pre-1.0; other mods in the workspace
reference that file directly rather than the NuGet package, so it will need replacing too.

Track this as: **blocked on upstream, no local work outstanding.**

---

## 2. Verified safe — every target checked against the 1.0.7 decompile

- `Character.Damage(HitData)`, `Character.RPC_Damage(long, HitData)`, `Character.OnDeath()` (`public virtual`)
- `Player.AddKnownItem(ItemDrop.ItemData)` — the patch pins `new System.Type[] { typeof(ItemDrop.ItemData) }` and that **still matches exactly** on 1.0.7. Leave it.
- `Player.GetAvailableRecipes(ref List<Recipe>)`, `Player.OnSpawned(bool)`
- `ZNet.Start()`, `ZNet.Shutdown(bool)`
- `OfferingBowl` (class-level patch) — type still present

**Not touched by this mod at all**, so the corresponding 1.0 breakages are irrelevant here: the sector
API (`FindSectorObjects`, `Vector2i` sectors, `ZoneSystem.m_activeArea`/`m_zones`), `ZDOExtraData`'s
per-type readers, `World.GetWorldSavePath`/`FileHelpers.FileSource`, the `Version` class rename,
`ZNet.PlayerInfo`, `ItemStand.m_visualHash`, and `Inventory.Load`'s new second overload.

**`StringExtensionMethods.GetStableHashCode(string)`** is unchanged on the release build — the two-argument
signature that appeared in the public-test build was reverted before ship. No bridge, and no
`Valheim10Compatibility` preloader dependency.

**One thing to re-check when Jotunn lands:** `BlightedWorldHeartAI.cs:61` does
`GetComponentsInChildren<VisEquipment>(true)`. That is a **component lookup only** — it never reads the
`m_*Item` fields that 1.0 converted from `string` to `int` hashes, so it is unaffected. But it sits right
next to the API that Jotunn's `ExtEquipment` gets wrong, so if you see equipment-visual oddities after
the Jotunn update, this is the line to look at first — not because it is broken now, but because it is
where the two systems meet.

---

## 3. When Jotunn updates

```bash
dotnet restore && dotnet build BlightedHeart.csproj -c Release
```

Game DLL `HintPath`s already resolve to `..\libs-Tools\*.dll`, which **is** the 1.0.7 client set as of
2026-09-09 — no csproj edit needed there. `libs-Tools/BepInEx.dll` was updated the same day to the
Valheim 1.0 pack (**5.4.2350**); `0Harmony.dll` is byte-identical to before, so nothing Harmony-side changes.

Re-verify against the new Jotunn API on the first build — Jotunn has broken `PrefabManager`/`ItemManager`
registration and config-attribute shapes across releases before. Then load on a 1.0.7 world and confirm
the mod's registered content actually appears.

---

## Footnote — plaintext credential in `origin`

Found 2026-09-09, unrelated to the 1.0 migration itself: this repo's `origin` remote embeds a live
GitHub fine-grained PAT directly in the URL (`https://RGlabs84:github_pat_...@github.com/...`),
readable in plaintext by `git remote -v` and `.git/config`. The same token is reused across
BlightedHeart, DvergrAllies, Fatty, and Njord. `gh` already ships a credential helper
(`gh auth setup-git`) that authenticates pushes without storing a token in the remote URL — switch to
it (or SSH), strip the token back out of `origin`, and rotate it, since it has already sat in
plaintext in git config.
