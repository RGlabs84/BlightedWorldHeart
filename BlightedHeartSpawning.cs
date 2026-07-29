using HarmonyLib;
using Jotunn.Managers;
using UnityEngine;

namespace BlightedHeart
{
    [HarmonyPatch(typeof(OfferingBowl))]
    public static class BlightedHeartSpawning
    {
        [HarmonyPatch("Interact")]
        [HarmonyPrefix]
        public static bool InteractPrefix(OfferingBowl __instance, Humanoid user, bool hold, bool alt)
        {
            if (hold) return true;

            // Check if the OfferingBowl is a boss altar
            if (__instance.m_bossPrefab == null) return true;

            // OfferingBowl interaction without holding an item
            return true;
        }

        [HarmonyPatch("UseItem")]
        [HarmonyPrefix]
        public static bool UseItemPrefix(OfferingBowl __instance, Humanoid user, ItemDrop.ItemData item, ref bool __result)
        {
            if (__instance.m_bossPrefab == null) return true;

            Heightmap.Biome currentBiome = Heightmap.FindBiome(__instance.transform.position);
            
            if (!BlightedConfigManager.BiomeConfigs.TryGetValue(currentBiome, out var config))
            {
                return true; // Unconfigured biome, fall back to default logic
            }

            string requiredItem = config.AltarSummonItem.Value;
            int requiredAmount = config.AltarSummonAmount.Value;

            // Check if the used item is our special summon item
            if (item.m_dropPrefab.name == requiredItem)
            {
                if (item.m_stack < requiredAmount)
                {
                    user.Message(MessageHud.MessageType.Center, $"Need {requiredAmount} {item.m_shared.m_name}");
                    __result = true;
                    return false; // Skip original
                }

                // Consume item
                user.GetInventory().RemoveItem(item, requiredAmount);
                user.Message(MessageHud.MessageType.Center, "The Blighted World Heart awakens!");

                // Spawn the boss
                SpawnBlightedHeart(__instance, user);
                
                __result = true;
                return false; // Skip original OfferingBowl logic
            }

            return true; // Proceed with normal offering bowl logic
        }

        private static void SpawnBlightedHeart(OfferingBowl bowl, Humanoid user)
        {
            bowl.StartCoroutine(SpawnBlightedHeartCoroutine(bowl, user));
        }

        private static System.Collections.IEnumerator SpawnBlightedHeartCoroutine(OfferingBowl bowl, Humanoid user)
        {
            GameObject heartPrefab = PrefabManager.Instance.GetPrefab("BlightedWorldHeart");
            if (heartPrefab == null)
            {
                Jotunn.Logger.LogError("Failed to get BlightedWorldHeart prefab for spawning.");
                yield break;
            }

            Vector3 spawnPos = bowl.transform.position + Vector3.up * 1f;

            Heightmap.Biome spawnBiome = Heightmap.FindBiome(spawnPos);

            // If we are in the Swamp, the altar is inside a giant skull. 
            // We want to move the boss outside the skull to avoid it getting stuck.
            // We use the player's position to determine which way is "out".
            if (spawnBiome == Heightmap.Biome.Swamp && user != null)
            {
                Vector3 dirToUser = user.transform.position - bowl.transform.position;
                dirToUser.y = 0; // horizontal only
                spawnPos += dirToUser.normalized * 12f; // Push it 12 units outwards
            }

            float solidHeight;
            if (ZoneSystem.instance.GetSolidHeight(spawnPos, out solidHeight))
            {
                spawnPos.y = solidHeight;
            }
            // Trigger build-up effects (sparkling, lightning, etc.)
            if (bowl.m_spawnBossStartEffects != null)
            {
                bowl.m_spawnBossStartEffects.Create(spawnPos, Quaternion.identity, null, 1f, -1);
            }

            // Wait for the standard vanilla boss delay
            yield return new WaitForSeconds(bowl.m_spawnBossDelay > 0 ? bowl.m_spawnBossDelay : 8f);

            // Instantiate the boss
            GameObject spawnedBoss = UnityEngine.Object.Instantiate(heartPrefab, spawnPos, Quaternion.identity);
            
            // Determine biome
            Heightmap.Biome currentBiome = Heightmap.FindBiome(spawnPos);
            
            // Initialize the AI with the current biome so it can scale and change color
            BlightedWorldHeartAI ai = spawnedBoss.GetComponent<BlightedWorldHeartAI>();
            if (ai != null)
            {
                ai.Initialize(currentBiome);
            }
        }
    }
}
