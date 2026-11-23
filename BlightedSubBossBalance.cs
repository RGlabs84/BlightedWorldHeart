using HarmonyLib;
using System.Collections.Generic;

namespace BlightedHeart
{
    // 1.2.1 Sub-Boss damage (owner playtest 2026-11-23: "WAYYY TOO MUCH DAMAGE ... normal the values based on the vanilla
    // we cloned from"; owner chose "cap to biome").
    //
    // Vanilla (1.0.21 Attack.ModifyDamage) multiplies every monster hit by GetLevelDamageFactor = 1 + 0.5 per star, and the
    // Heart summons Sub-Bosses at Sub-Boss Level 2 (one star): a Lox clone bit for 195, a Seeker clone clawed for 180. Now a
    // Sub-Boss hits with its donor's own vanilla damage, no star bonus, times the admin's Sub-Boss Damage Multiplier, and
    // never harder than the hardest-hitting vanilla creature of the biome it was summoned in. Today that cap only bites
    // on the Meadows Rootstalker (a Wolf clone: 70 slash, against Eikthyr's 20).
    //
    // All three vanilla attack paths (melee, area, projectile/AoE) go through ModifyDamage -> GetLevelDamageFactor, which
    // runs on the machine that owns the attacker; the biome comes from the Sub-Boss's own ZDO, so it holds on every machine.
    [HarmonyPatch(typeof(Attack), "GetLevelDamageFactor")]
    public static class BlightedSubBossBalance
    {
        // The single hardest hit (sum of an attack's damage types) of the biome's vanilla creatures, read from the game's
        // item data (libs-Tools WubarrksEye Values_Dump): Meadows Eikthyr 20, Black Forest Troll 70, Swamp Abomination 80,
        // Mountain Stone Golem 110, Plains Fuling Brute / Lox 130, Mistlands Seeker 230. Ashlands and the Deep North are
        // not capped: every donor comes from a lower biome. Stale when a game update rebalances those creatures.
        private static readonly Dictionary<Heightmap.Biome, float> BiomeHitCap = new Dictionary<Heightmap.Biome, float>
        {
            { Heightmap.Biome.Meadows, 20f },
            { Heightmap.Biome.BlackForest, 70f },
            { Heightmap.Biome.Swamp, 80f },
            { Heightmap.Biome.Mountain, 110f },
            { Heightmap.Biome.Plains, 130f },
            { Heightmap.Biome.Mistlands, 230f },
        };

        public static void Postfix(Attack __instance, ref float __result)
        {
            Character attacker = __instance.m_character;
            if (attacker == null || attacker.m_nview == null) return;
            ZDO zdo = attacker.m_nview.GetZDO();
            if (zdo == null) return;
            int biome = zdo.GetInt(BlightedSubBosses.ZdoBiome, 0);
            if (biome == 0) return;                              // not a Sub-Boss

            __result = Factor((Heightmap.Biome)biome, BaseHit(__instance.m_weapon));
        }

        // The whole damage factor for one Sub-Boss attack, replacing vanilla's star factor.
        internal static float Factor(Heightmap.Biome biome, float baseHit)
        {
            float mult = BlightedConfigManager.SubBossDamageMultiplier != null ? BlightedConfigManager.SubBossDamageMultiplier.Value : 1f;
            if (baseHit > 0f && BiomeHitCap.TryGetValue(biome, out float cap) && baseHit > cap)
            {
                mult *= cap / baseHit;
            }
            return mult;
        }

        internal static float BaseHit(ItemDrop.ItemData weapon)
        {
            if (weapon == null || weapon.m_shared == null) return 0f;
            HitData.DamageTypes d = weapon.m_shared.m_damages;
            return d.m_damage + d.m_blunt + d.m_slash + d.m_pierce + d.m_fire + d.m_frost + d.m_lightning + d.m_poison + d.m_spirit;
        }
    }
}
