using HarmonyLib;
using UnityEngine;
using System.Collections.Generic;

namespace BlightedHeart
{
    // What the Heart's summons drop (1.2.1, owner playtest 2026-11-23: "they should drop nothing or have a roll chance for
    // 1 piece of blighted gear for the biome they are in"; owner chose a 25% default).
    //
    // Before, the summoner's machine destroyed the CharacterDrop on ITS copy of each summon only. Whichever machine owns a
    // creature when it dies makes the drops, and a copy rebuilt after a zone reload or on another player's machine still
    // had its vanilla CharacterDrop - so Sub-Bosses (and reloaded waves) dropped vanilla loot. Now the summon carries a
    // saved mark, and every machine refuses vanilla drops for it.
    public static class BlightedHeartLoot
    {
        private static bool IsSummon(Character c)
        {
            if (c == null || c.m_nview == null) return false;
            ZDO zdo = c.m_nview.GetZDO();
            if (zdo == null) return false;
            // A Sub-Boss summoned by 1.2.0 carries only the biome mark; it counts too.
            return zdo.GetInt(BlightedWorldHeartAI.ZDO_Summoned, 0) == 1 || zdo.GetInt(BlightedSubBosses.ZdoBiome, 0) != 0;
        }

        // Both vanilla drop paths (straight on death, and the ragdoll's delayed drop) ask GenerateDropList.
        [HarmonyPatch(typeof(CharacterDrop), nameof(CharacterDrop.GenerateDropList))]
        public static class NoVanillaDrops
        {
            public static bool Prefix(CharacterDrop __instance, ref List<KeyValuePair<GameObject, int>> __result)
            {
                if (!IsSummon(__instance.GetComponent<Character>())) return true;
                __result = new List<KeyValuePair<GameObject, int>>();
                return false;
            }
        }

        // A Sub-Boss's own roll: one random Blighted weapon or armour piece of the biome it was summoned in. Runs on the
        // machine that owns it at death (vanilla returns early everywhere else), so it rolls once.
        [HarmonyPatch(typeof(Character), nameof(Character.OnDeath))]
        public static class SubBossGearRoll
        {
            public static void Prefix(Character __instance)
            {
                if (__instance == null || __instance.m_nview == null || !__instance.m_nview.IsOwner()) return;
                ZDO zdo = __instance.m_nview.GetZDO();
                if (zdo == null) return;
                int biome = zdo.GetInt(BlightedSubBosses.ZdoBiome, 0);
                if (biome == 0) return;                                  // not a Sub-Boss

                float chance = BlightedConfigManager.SubBossGearDropChance != null ? BlightedConfigManager.SubBossGearDropChance.Value : 0.25f;
                if (chance <= 0f || Random.value >= chance) return;

                string item = PickGear((Heightmap.Biome)biome);
                if (item == null) return;
                GameObject prefab = ZNetScene.instance != null ? ZNetScene.instance.GetPrefab(item) : null;
                if (prefab == null && ObjectDB.instance != null) prefab = ObjectDB.instance.GetItemPrefab(item);
                if (prefab == null) return;

                Vector3 pos = __instance.GetCenterPoint() + Random.insideUnitSphere * 0.5f;
                Object.Instantiate(prefab, pos, Quaternion.identity);
                Jotunn.Logger.LogInfo($"[BlightedHeart] Sub-Boss {__instance.m_name} dropped {item}.");
            }
        }

        internal static string PickGear(Heightmap.Biome biome)
        {
            var pool = new List<string>();
            if (BlightedItemsManager.BiomeWeaponDrops.TryGetValue(biome, out var weapons)) pool.AddRange(weapons);
            if (BlightedItemsManager.BiomeArmorDrops.TryGetValue(biome, out var armors)) pool.AddRange(armors);
            return pool.Count == 0 ? null : pool[Random.Range(0, pool.Count)];
        }
    }
}
