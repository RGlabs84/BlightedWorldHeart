using HarmonyLib;
using UnityEngine;
using System.Collections.Generic;
using Jotunn.Managers;

namespace BlightedHeart
{
    [HarmonyPatch(typeof(Character), "OnDeath")]
    public static class BlightedHeartLoot
    {
        public static void Prefix(Character __instance)
        {
            var ai = __instance.GetComponent<BlightedWorldHeartAI>();
            if (ai != null && __instance.IsOwner())
            {
                Jotunn.Logger.LogInfo("Blighted World Heart defeated! Dropping loot...");
                DropLoot(ai.CurrentBiome, __instance.transform.position + Vector3.up * 2f);
            }
        }

        private static void DropLoot(Heightmap.Biome biome, Vector3 dropPosition)
        {
            if (!BlightedConfigManager.BiomeConfigs.TryGetValue(biome, out var config)) return;

            float scaleFactor = config.LootScaleFactor.Value;
            
            List<string> potentialDrops = new List<string>();
            if (BlightedItemsManager.BiomeWeaponDrops.TryGetValue(biome, out var weapons))
                potentialDrops.AddRange(weapons);
                
            if (BlightedItemsManager.BiomeArmorDrops.TryGetValue(biome, out var armors))
                potentialDrops.AddRange(armors);

            if (potentialDrops.Count == 0) return;

            int numDrops = Mathf.CeilToInt(2 * scaleFactor);

            for (int i = 0; i < numDrops; i++)
            {
                string itemPrefabName = potentialDrops[UnityEngine.Random.Range(0, potentialDrops.Count)];
                GameObject prefab = ZNetScene.instance.GetPrefab(itemPrefabName);
                if (prefab == null) prefab = ObjectDB.instance.GetItemPrefab(itemPrefabName);
                if (prefab != null)
                {
                    Vector3 spawnPos = dropPosition + UnityEngine.Random.insideUnitSphere * 2f;
                    UnityEngine.Object.Instantiate(prefab, spawnPos, Quaternion.identity);
                }
            }
        }
    }
}
