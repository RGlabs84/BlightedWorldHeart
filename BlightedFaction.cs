using HarmonyLib;
using UnityEngine;

namespace BlightedHeart
{
    // The Heart's own faction (1.2.0). Every wave creature and Sub-Boss the Heart summons joins it, so they are
    // allies of each other and enemies of everyone and everything else: players, their tames, and every vanilla
    // creature, other bosses included.
    //
    // Why: the waves mix vanilla factions (Black Forest = Greydwarfs + Skeletons, ForestMonsters vs Undead), and
    // vanilla BaseAI.IsEnemy makes different monster factions enemies of each other, so the summons fought each
    // other instead of the players - worst at the Elder's altar.
    //
    // How (read off the 1.0.21 decompile, BaseAI.IsEnemy / Character.IsMonsterFaction):
    //  - IsEnemy returns false when both factions are EQUAL, so one shared value makes every summon an ally of
    //    every other summon with no patch at all. That also covers friendly fire: Attack, Projectile and Aoe all
    //    ask IsEnemy before hitting.
    //  - The value is not a vanilla enum member, so IsEnemy's switch falls to `default: return false` when the
    //    Blighted creature is the one ASKING (its own target search). The IsEnemy postfix below turns that into
    //    "enemy". When the other side asks, every vanilla case already answers true, except Boss (the switch
    //    only lets Boss fight Players/PlayerSpawned), which the same postfix covers.
    //  - Tamed creatures are handled by IsEnemy before the faction switch (tame vs non-tame = enemy), so a
    //    player's wolves fight the summons with no special case.
    //  - m_faction is a plain field, not networked. The owner stamps a ZDO int when it spawns a summon, and a
    //    Character.Awake postfix re-applies the faction on every peer that loads the creature, so it survives
    //    ownership moving to another client (a player logging off mid-fight) and zone reloads.
    public static class BlightedFaction
    {
        // Far outside vanilla's 0..13 so a future vanilla faction cannot collide with it.
        public const Character.Faction Value = (Character.Faction)66;

        private static readonly int ZdoKey = "blighted_faction".GetStableHashCode();

        public static bool Is(Character c) => c != null && c.m_faction == Value;

        // Called by the Heart's owner right after it instantiates a wave creature or Sub-Boss.
        public static void Join(GameObject go)
        {
            if (go == null) return;
            if (BlightedConfigManager.UseBlightedFaction != null && !BlightedConfigManager.UseBlightedFaction.Value) return;

            Character character = go.GetComponent<Character>();
            if (character == null) return;
            character.m_faction = Value;

            ZNetView nview = go.GetComponent<ZNetView>();
            if (nview != null && nview.GetZDO() != null)
            {
                nview.GetZDO().Set(ZdoKey, 1);
            }
        }

        [HarmonyPatch(typeof(Character), nameof(Character.Awake))]
        public static class CharacterAwakePatch
        {
            // Humanoid.Awake and Player.Awake call base.Awake(), so this runs for every Character subclass.
            public static void Postfix(Character __instance)
            {
                ZNetView nview = __instance.m_nview;
                if (nview == null) return;
                ZDO zdo = nview.GetZDO();
                if (zdo != null && zdo.GetInt(ZdoKey) == 1)
                {
                    __instance.m_faction = Value;
                }
            }
        }

        [HarmonyPatch(typeof(BaseAI), nameof(BaseAI.IsEnemy), typeof(Character), typeof(Character))]
        public static class IsEnemyPatch
        {
            // Hot path (every AI target scan, every hit): two field compares before anything else.
            public static void Postfix(Character a, Character b, ref bool __result)
            {
                if (__result) return;
                if (a is null || b is null) return;
                bool aBlighted = a.m_faction == Value;
                bool bBlighted = b.m_faction == Value;
                if (aBlighted == bBlighted) return; // neither, or both (allies)
                if (!a || !b || a == b) return;

                Character other = aBlighted ? b : a;
                // A training dummy is a player's practice target; summons chasing it would be a free distraction.
                if (other.m_faction == Character.Faction.TrainingDummy) return;

                __result = true;
            }
        }

        [HarmonyPatch(typeof(Character), nameof(Character.IsMonsterFaction))]
        public static class IsMonsterFactionPatch
        {
            // Vanilla lists the monster factions by name, so a Blighted summon would not count as a monster for
            // checks like "is a monster near" (LootSpawner). It is one.
            public static void Postfix(Character __instance, float time, ref bool __result)
            {
                if (!__result && __instance.m_faction == Value && !__instance.IsTamed(time))
                {
                    __result = true;
                }
            }
        }
    }
}
