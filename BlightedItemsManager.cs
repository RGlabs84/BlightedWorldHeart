using HarmonyLib;
using Jotunn.Entities;
using Jotunn.Managers;
using System.Collections.Generic;
using System.Linq;
using UnityEngine;

namespace BlightedHeart
{
    public static class BlightedItemsManager
    {
        public static Dictionary<Heightmap.Biome, List<string>> BiomeWeaponDrops = new Dictionary<Heightmap.Biome, List<string>>();
        public static Dictionary<Heightmap.Biome, List<string>> BiomeArmorDrops = new Dictionary<Heightmap.Biome, List<string>>();

        // Maps blighted prefab name -> base vanilla prefab name, so we can resolve
        // vanilla recipe materials after ObjectDB is fully populated.
        private static Dictionary<string, string> _deferredRecipeLookups = new Dictionary<string, string>();
        private static bool _recipesResolved = false;

        public static void Setup()
        {
            PrefabManager.OnVanillaPrefabsAvailable -= Setup;
            Jotunn.Logger.LogInfo("Setting up Blighted custom items...");

            CreateBiomeItems(Heightmap.Biome.Meadows, 
                new[] { "Club", "SpearFlint", "Bow" }, 
                new[] { "ArmorLeatherChest", "ArmorLeatherLegs", "HelmetLeather", "CapeDeerHide", "ShieldWood" });
                
            CreateBiomeItems(Heightmap.Biome.BlackForest, 
                new[] { "SwordBronze", "MaceBronze", "AxeBronze" }, 
                new[] { "ArmorBronzeChest", "ArmorBronzeLegs", "HelmetBronze", "CapeTrollHide", "ShieldBronzeBuckler" });
                
            CreateBiomeItems(Heightmap.Biome.Swamp, 
                new[] { "SwordIron", "MaceIron", "Battleaxe" }, 
                new[] { "ArmorIronChest", "ArmorIronLegs", "HelmetIron", "ShieldBanded" });
                
            CreateBiomeItems(Heightmap.Biome.Mountain, 
                new[] { "SwordSilver", "BowDraugrFang" }, 
                new[] { "ArmorWolfChest", "ArmorWolfLegs", "HelmetDrake", "CapeWolf", "ShieldSilver" });
                
            CreateBiomeItems(Heightmap.Biome.Plains, 
                new[] { "SwordBlackmetal", "MaceNeedle", "AtgeirBlackmetal" }, 
                new[] { "ArmorPaddedCuirass", "ArmorPaddedGreaves", "HelmetPadded", "CapeLox", "ShieldBlackmetal" });
                
            CreateBiomeItems(Heightmap.Biome.Mistlands, 
                new[] { "SwordMistwalker", "BowSpineSnap" }, 
                new[] { "ArmorCarapaceChest", "ArmorCarapaceLegs", "HelmetCarapace", "CapeFeather", "ShieldCarapace" });
                
            CreateBiomeItems(Heightmap.Biome.AshLands, 
                new[] { "SwordFlametal", "MaceFlametal" }, 
                new[] { "ArmorFlametalChest", "ArmorFlametalLegs", "HelmetFlametal", "CapeAsh", "ShieldFlametal" });
                
            CreateBiomeItems(Heightmap.Biome.DeepNorth, 
                new[] { "SwordSilver", "BowDraugrFang" }, 
                new[] { "ArmorWolfChest", "ArmorWolfLegs", "HelmetDrake", "CapeWolf", "ShieldSilver" }); // Fallback
            
            Jotunn.Logger.LogInfo("Blighted custom items created.");
        }

        private static void CreateBiomeItems(Heightmap.Biome biome, string[] weapons, string[] armors)
        {
            float scale = 1.0f;
            if (BlightedConfigManager.BiomeConfigs.TryGetValue(biome, out var config))
            {
                scale = config.LootScaleFactor.Value;
            }

            BiomeWeaponDrops[biome] = new List<string>();
            BiomeArmorDrops[biome] = new List<string>();

            // --- Weapons & Shields ---
            foreach (string baseWeapon in weapons)
            {
                // 1. Serpent (Poison)
                string wSerpent = CreateWeaponVariant(biome, baseWeapon, "Serpent", "of the Serpent", "Attacks deal additional poison damage.", scale, (shared) => {
                    shared.m_damages.m_poison += 10f * scale;
                });
                if (wSerpent != null) BiomeWeaponDrops[biome].Add(wSerpent);

                // 2. Wraith (Spirit)
                string wWraith = CreateWeaponVariant(biome, baseWeapon, "Wraith", "of the Wraith", "Attacks deal additional spirit damage.", scale, (shared) => {
                    shared.m_damages.m_spirit += 10f * scale;
                });
                if (wWraith != null) BiomeWeaponDrops[biome].Add(wWraith);

                // 3. Blight (Poison + Spirit + Physical)
                string wBlight = CreateWeaponVariant(biome, baseWeapon, "Blight", "of the Blight", "Attacks deal increased physical, poison, and spirit damage.", scale, (shared) => {
                    shared.m_damages.m_poison += 5f * scale;
                    shared.m_damages.m_spirit += 5f * scale;
                    shared.m_damages.m_slash *= (1f + 0.05f * scale);
                    shared.m_damages.m_blunt *= (1f + 0.05f * scale);
                    shared.m_damages.m_pierce *= (1f + 0.05f * scale);
                });
                if (wBlight != null) BiomeWeaponDrops[biome].Add(wBlight);
            }

            // --- Armor & Capes ---
            foreach (string baseArmor in armors)
            {
                // 1. Bastion (Pure Defense)
                string aBastion = CreateArmorVariant(biome, baseArmor, "Bastion", "of the Bastion", "Increased armor rating and durability.", scale, (shared) => {
                    shared.m_armor *= (1f + 0.1f * scale);
                    shared.m_maxDurability *= 1.5f;
                });
                if (aBastion != null) BiomeArmorDrops[biome].Add(aBastion);

                // 2. Serpent (Poison Resist)
                string aSerpent = CreateArmorVariant(biome, baseArmor, "Serpent", "of the Serpent", "Grants resistance to Poison.", scale, (shared) => {
                    if (shared.m_damageModifiers == null) shared.m_damageModifiers = new List<HitData.DamageModPair>();
                    shared.m_damageModifiers.Add(new HitData.DamageModPair { m_type = HitData.DamageType.Poison, m_modifier = HitData.DamageModifier.Resistant });
                });
                if (aSerpent != null) BiomeArmorDrops[biome].Add(aSerpent);

                // 3. Wraith (Spirit Resist)
                string aWraith = CreateArmorVariant(biome, baseArmor, "Wraith", "of the Wraith", "Grants resistance to Spirit damage.", scale, (shared) => {
                    if (shared.m_damageModifiers == null) shared.m_damageModifiers = new List<HitData.DamageModPair>();
                    shared.m_damageModifiers.Add(new HitData.DamageModPair { m_type = HitData.DamageType.Spirit, m_modifier = HitData.DamageModifier.Resistant });
                });
                if (aWraith != null) BiomeArmorDrops[biome].Add(aWraith);

                // 4. Blight (Combo)
                string aBlight = CreateArmorVariant(biome, baseArmor, "Blight", "of the Blight", "Increased armor and resistance to Poison and Spirit.", scale, (shared) => {
                    shared.m_armor *= (1f + 0.05f * scale);
                    if (shared.m_damageModifiers == null) shared.m_damageModifiers = new List<HitData.DamageModPair>();
                    shared.m_damageModifiers.Add(new HitData.DamageModPair { m_type = HitData.DamageType.Poison, m_modifier = HitData.DamageModifier.Resistant });
                    shared.m_damageModifiers.Add(new HitData.DamageModPair { m_type = HitData.DamageType.Spirit, m_modifier = HitData.DamageModifier.Resistant });
                });
                if (aBlight != null) BiomeArmorDrops[biome].Add(aBlight);
            }
        }

        private static string GetStationName(string basePrefab)
        {
            if (basePrefab.Contains("Carapace") || basePrefab.Contains("Flametal") || basePrefab.Contains("Mistwalker") || basePrefab.Contains("SpineSnap") || basePrefab.Contains("Ash") || basePrefab.Contains("Feather"))
                return "blackforge";
            if (basePrefab.Contains("Bronze") || basePrefab.Contains("Iron") || basePrefab.Contains("Silver") || basePrefab.Contains("Blackmetal") || basePrefab.Contains("Banded") || basePrefab.Contains("Padded") || basePrefab.Contains("Needle") || basePrefab.Contains("DraugrFang") || basePrefab.Contains("Battleaxe") || basePrefab.Contains("Drake"))
                return "forge";
            return "piece_workbench";
        }

        private static string[] GetBiomeTrophies(Heightmap.Biome biome)
        {
            switch(biome)
            {
                case Heightmap.Biome.Meadows: return new[] { "TrophyBoar", "TrophyNeck" };
                case Heightmap.Biome.BlackForest: return new[] { "TrophyGreydwarfBrute", "TrophyGreydwarfShaman" };
                case Heightmap.Biome.Swamp: return new[] { "TrophyDraugr", "TrophyLeech" };
                case Heightmap.Biome.Mountain: return new[] { "TrophyWolf", "TrophyHatchling" };
                case Heightmap.Biome.Plains: return new[] { "TrophyGoblin", "TrophyDeathsquito" };
                case Heightmap.Biome.Mistlands: return new[] { "TrophySeeker", "TrophyTick" };
                case Heightmap.Biome.AshLands: return new[] { "TrophyCharredMelee", "TrophyCharredArcher" };
                case Heightmap.Biome.DeepNorth: return new[] { "TrophyWolf", "TrophyHatchling" };
                default: return new[] { "TrophyBoar", "TrophyNeck" };
            }
        }

        /// <summary>
        /// Called after ObjectDB is fully populated to inject vanilla recipe materials
        /// into blighted item upgrade recipes. This is deferred because ObjectDB.m_recipes
        /// is empty during OnVanillaPrefabsAvailable.
        /// </summary>
        public static void ResolveVanillaRecipeMaterials()
        {
            if (_recipesResolved) return;

            if (BlightedHeartPlugin.IsWackyDBInstalled)
            {
                Jotunn.Logger.LogInfo("WackyDB Recipe Compatibility mode is active. Skipping vanilla recipe material injection.");
                _recipesResolved = true;
                return;
            }

            if (ObjectDB.instance == null)
            {
                // Don't latch _recipesResolved here — retry on the next OnSpawned call (e.g. respawn)
                // instead of permanently skipping material injection for the rest of the session.
                Jotunn.Logger.LogWarning("ResolveVanillaRecipeMaterials called but ObjectDB.instance is null!");
                return;
            }

            _recipesResolved = true;
            int resolved = 0;
            int failed = 0;

            foreach (var kvp in _deferredRecipeLookups)
            {
                string blightedName = kvp.Key;
                string basePrefab = kvp.Value;

                // Find the blighted recipe in ObjectDB
                Recipe blightedRecipe = ObjectDB.instance.m_recipes.FirstOrDefault(
                    r => r != null && r.m_item != null && r.m_item.gameObject.name == blightedName);
                if (blightedRecipe == null) continue;

                // Find the vanilla recipe
                Recipe vanillaRecipe = ObjectDB.instance.m_recipes.FirstOrDefault(
                    r => r != null && r.m_item != null && r.m_item.gameObject.name == basePrefab);

                if (vanillaRecipe == null || vanillaRecipe.m_resources == null)
                {
                    Jotunn.Logger.LogWarning($"Could not find vanilla recipe for '{basePrefab}', upgrade for '{blightedName}' will only require trophies.");
                    failed++;
                    continue;
                }

                // Build the new resources array: existing trophy reqs + vanilla base materials
                var existingResources = blightedRecipe.m_resources != null
                    ? new List<Piece.Requirement>(blightedRecipe.m_resources)
                    : new List<Piece.Requirement>();

                foreach (var res in vanillaRecipe.m_resources)
                {
                    if (res.m_resItem == null) continue;
                    int perLevel = res.m_amountPerLevel > 0 ? res.m_amountPerLevel : Mathf.Max(1, res.m_amount / 2);

                    existingResources.Add(new Piece.Requirement()
                    {
                        m_resItem = res.m_resItem,
                        m_amount = 0,           // Cannot be crafted (0 cost at level 1)
                        m_amountPerLevel = perLevel,
                        m_recover = true
                    });
                }

                blightedRecipe.m_resources = existingResources.ToArray();
                resolved++;
            }

            Jotunn.Logger.LogInfo($"Resolved vanilla recipe materials for {resolved} blighted items ({failed} could not be resolved).");

            // Validate all blighted recipes in ObjectDB to ensure none have corrupted
            // fields that would crash vanilla's GetAvailableRecipes foreach loop.
            ValidateBlightedRecipes();
        }

        /// <summary>
        /// Scans ObjectDB.m_recipes for blighted recipes with corrupted fields and
        /// removes them. A single corrupted recipe causes vanilla's GetAvailableRecipes
        /// to throw mid-iteration (no try/catch in the foreach), which leaves the
        /// available-recipes list empty — hiding ALL items, not just blighted ones.
        /// </summary>
        private static void ValidateBlightedRecipes()
        {
            if (ObjectDB.instance == null) return;

            int removed = 0;
            ObjectDB.instance.m_recipes.RemoveAll(r =>
            {
                if (r == null) return false;
                if (r.m_item == null) return false;
                if (!r.m_item.gameObject.name.StartsWith("Blighted")) return false;

                // Check every field that vanilla's GetAvailableRecipes accesses
                // without null-guards. If any are null, this recipe would crash
                // the entire recipe enumeration.
                bool corrupt = false;
                try
                {
                    var itemData = r.m_item.m_itemData;
                    if (itemData == null || itemData.m_shared == null)
                    {
                        corrupt = true;
                    }
                    else if (itemData.m_shared.m_dlc == null)
                    {
                        // Fix in-place rather than removing
                        itemData.m_shared.m_dlc = string.Empty;
                    }

                    if (itemData?.m_shared?.m_name == null)
                    {
                        corrupt = true;
                    }
                }
                catch
                {
                    corrupt = true;
                }

                if (corrupt)
                {
                    Jotunn.Logger.LogWarning($"Removing corrupted blighted recipe for '{r.m_item.gameObject.name}' to prevent crafting list crash.");
                    removed++;
                }
                return corrupt;
            });

            if (removed > 0)
            {
                Jotunn.Logger.LogWarning($"Removed {removed} corrupted blighted recipe(s) from ObjectDB.");
            }
        }

        private static string CreateWeaponVariant(Heightmap.Biome biome, string basePrefab, string suffixId, string suffixName, string effectDescription, float scale, System.Action<ItemDrop.ItemData.SharedData> modify)
        {
            string newName = $"Blighted{biome}_{basePrefab}_{suffixId}";
            GameObject prefab = PrefabManager.Instance.GetPrefab(basePrefab);
            if (prefab == null) return null;

            CustomItem customItem = new CustomItem(newName, basePrefab);
            var shared = customItem.ItemDrop.m_itemData.m_shared;

            // Ensure m_dlc is never null — vanilla GetAvailableRecipes accesses
            // m_dlc.Length without a null check, and a null m_dlc on ANY recipe
            // in ObjectDB.m_recipes causes the entire foreach to throw, leaving
            // the available-recipes list empty for every station.
            if (shared.m_dlc == null) shared.m_dlc = string.Empty;
            
            shared.m_name = $"Blighted {shared.m_name} {suffixName}";
            shared.m_description = $"<color=yellow>{effectDescription}</color>\n{shared.m_description}";
            
            // Base scaling
            shared.m_damages.m_blunt *= (1f + 0.05f * scale);
            shared.m_damages.m_slash *= (1f + 0.05f * scale);
            shared.m_damages.m_pierce *= (1f + 0.05f * scale);

            modify?.Invoke(shared);

            // Apply darker green tint
            TintItemPrefab(customItem);

            Jotunn.Managers.ItemManager.Instance.AddItem(customItem);

            // Build upgrade recipe with trophy requirements only.
            // Vanilla base material requirements are resolved later in ResolveVanillaRecipeMaterials()
            // because ObjectDB.m_recipes is not populated during OnVanillaPrefabsAvailable.
            string[] trophies = GetBiomeTrophies(biome);
            var reqs = new List<Jotunn.Configs.RequirementConfig>();

            // Track for deferred vanilla recipe resolution
            _deferredRecipeLookups[newName] = basePrefab;

            // Add trophy requirements for upgrades
            foreach (string trophy in trophies)
            {
                reqs.Add(new Jotunn.Configs.RequirementConfig()
                {
                    Item = trophy,
                    Amount = 0,
                    AmountPerLevel = 2
                });
            }

            Jotunn.Entities.CustomRecipe recipe = new Jotunn.Entities.CustomRecipe(new Jotunn.Configs.RecipeConfig()
            {
                Item = newName,
                Amount = 1,
                CraftingStation = GetStationName(basePrefab),
                Enabled = true,
                Requirements = reqs.ToArray()
            });
            Jotunn.Managers.ItemManager.Instance.AddRecipe(recipe);

            return newName;
        }

        private static string CreateArmorVariant(Heightmap.Biome biome, string basePrefab, string suffixId, string suffixName, string effectDescription, float scale, System.Action<ItemDrop.ItemData.SharedData> modify)
        {
            string newName = $"Blighted{biome}_{basePrefab}_{suffixId}";
            GameObject prefab = PrefabManager.Instance.GetPrefab(basePrefab);
            if (prefab == null) return null;

            CustomItem customItem = new CustomItem(newName, basePrefab);
            var shared = customItem.ItemDrop.m_itemData.m_shared;

            // Ensure m_dlc is never null (same guard as CreateWeaponVariant)
            if (shared.m_dlc == null) shared.m_dlc = string.Empty;
            
            shared.m_name = $"Blighted {shared.m_name} {suffixName}";
            shared.m_description = $"<color=yellow>{effectDescription}</color>\n{shared.m_description}";
            
            // Base scaling
            shared.m_armor *= (1f + 0.05f * scale);

            modify?.Invoke(shared);

            // Apply darker green tint
            TintItemPrefab(customItem);

            Jotunn.Managers.ItemManager.Instance.AddItem(customItem);

            // Build upgrade recipe with trophy requirements only.
            // Vanilla base material requirements are resolved later in ResolveVanillaRecipeMaterials().
            string[] trophies = GetBiomeTrophies(biome);
            var reqs = new List<Jotunn.Configs.RequirementConfig>();

            // Track for deferred vanilla recipe resolution
            _deferredRecipeLookups[newName] = basePrefab;

            // Add trophy requirements for upgrades
            foreach (string trophy in trophies)
            {
                reqs.Add(new Jotunn.Configs.RequirementConfig()
                {
                    Item = trophy,
                    Amount = 0,
                    AmountPerLevel = 2
                });
            }

            Jotunn.Entities.CustomRecipe recipe = new Jotunn.Entities.CustomRecipe(new Jotunn.Configs.RecipeConfig()
            {
                Item = newName,
                Amount = 1,
                CraftingStation = GetStationName(basePrefab),
                Enabled = true,
                Requirements = reqs.ToArray()
            });
            Jotunn.Managers.ItemManager.Instance.AddRecipe(recipe);

            return newName;
        }

        private static void TintItemPrefab(CustomItem customItem)
        {
            // Dark green tint color
            Color blightedTint = new Color(0.1f, 0.4f, 0.1f, 1.0f);

            // Tint the dropped item model and equipped model explicitly for other items
            // Be sure to include inactive children (true) because equip models are usually inactive on the prefab!
            foreach (var renderer in customItem.ItemPrefab.GetComponentsInChildren<Renderer>(true))
            {
                foreach (var mat in renderer.materials)
                {
                    TintMaterial(mat, blightedTint);
                }
            }

            // Valheim applies armor using the shared m_armorMaterial on the character body
            var shared = customItem.ItemDrop.m_itemData.m_shared;
            if (shared != null && shared.m_armorMaterial != null)
            {
                // Clone the material so we don't accidentally tint the vanilla armor it was cloned from
                shared.m_armorMaterial = new Material(shared.m_armorMaterial);
                TintMaterial(shared.m_armorMaterial, blightedTint);
            }
        }

        private static void TintMaterial(Material mat, Color blightedTint)
        {
            if (mat == null) return;

            if (mat.HasProperty("_Color")) 
            {
                // Blend the color to a dark green without forcing it to glow
                mat.color = Color.Lerp(mat.color, blightedTint, 0.8f);
            }
            
            // If the item already has an emission, just tint it slightly darker green, 
            // but DO NOT force enable emission, as that causes the pale green glow.
            if (mat.HasProperty("_EmissionColor") && mat.IsKeywordEnabled("_EMISSION")) 
            {
                mat.SetColor("_EmissionColor", mat.GetColor("_EmissionColor") * blightedTint);
            }
        }
    }

    // Harmony patches for custom mechanics
    [HarmonyPatch]
    public static class BlightedMechanicsPatches
    {
        // Resolve vanilla recipe materials after the world is fully loaded.
        // During OnVanillaPrefabsAvailable, ObjectDB.m_recipes is empty so we
        // defer the lookup to Player.OnSpawned, which fires after the player
        // loads into the world — guaranteeing ObjectDB is fully populated.
        [HarmonyPatch(typeof(Player), nameof(Player.OnSpawned))]
        [HarmonyPostfix]
        public static void PlayerOnSpawnedPostfix()
        {
            BlightedItemsManager.ResolveVanillaRecipeMaterials();
        }

        // (Diagnostic postfix removed for release)

        [HarmonyPatch(typeof(Character), nameof(Character.Damage))]
        [HarmonyPrefix]
        public static bool DamagePrefix(Character __instance, HitData hit)
        {
            // Protect the Blighted World Heart from non-player damage (e.g. sub-boss AoE, random enemies)
            if (__instance.GetComponent<BlightedWorldHeartAI>() != null)
            {
                if (hit != null && (hit.GetAttacker() == null || !hit.GetAttacker().IsPlayer()))
                {
                    // Block damage
                    return false;
                }
            }

            if (hit == null || hit.GetAttacker() == null || !hit.GetAttacker().IsPlayer())
                return true;

            // Damage logic for crit/leech has been completely removed!
            
            return true;
        }

        [HarmonyPatch(typeof(Player), nameof(Player.GetAvailableRecipes))]
        [HarmonyPostfix]
        [HarmonyPriority(Priority.Last)]
        public static void HideBlightedCrafting(Player __instance, ref List<Recipe> available)
        {
            try
            {
                if (BlightedHeartPlugin.IsWackyDBInstalled) return;
                if (__instance != null && __instance.NoCostCheat()) return;

                if (available != null && InventoryGui.instance != null && InventoryGui.instance.InCraftTab())
                {
                    available.RemoveAll(r => 
                        r != null && 
                        r.m_item != null && 
                        r.m_item.gameObject.name.StartsWith("Blighted") && 
                        IsRecipeFreeAtLevel1(r)
                    );
                }
            }
            catch (System.Exception ex)
            {
                Jotunn.Logger.LogWarning($"HideBlightedCrafting postfix failed (non-fatal): {ex.Message}");
            }
        }

        private static bool IsRecipeFreeAtLevel1(Recipe r)
        {
            if (r.m_resources == null || r.m_resources.Length == 0) return true;
            foreach (var req in r.m_resources)
            {
                if (req != null && req.m_amount > 0) return false;
            }
            return true;
        }

        [HarmonyPatch(typeof(Player), nameof(Player.AddKnownItem), new System.Type[] { typeof(ItemDrop.ItemData) })]
        [HarmonyPrefix]
        public static void AddKnownItemPrefix(Player __instance, ItemDrop.ItemData item)
        {
            // When a player picks up a Blighted item, discover all of the upgrade recipe's
            // ingredient materials so the recipe shows up in the Upgrade tab.
            if (item == null || item.m_dropPrefab == null || !item.m_dropPrefab.name.StartsWith("Blighted"))
                return;

            string prefabName = item.m_dropPrefab.name;
            if (ObjectDB.instance == null) return;

            Recipe recipe = ObjectDB.instance.m_recipes.FirstOrDefault(
                r => r != null && r.m_item != null && r.m_item.gameObject.name == prefabName);
            if (recipe == null || recipe.m_resources == null) return;

            foreach (var res in recipe.m_resources)
            {
                if (res.m_resItem != null)
                {
                    __instance.m_knownMaterial.Add(res.m_resItem.gameObject.name);
                }
            }
        }
    }
}
