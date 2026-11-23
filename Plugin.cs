using BepInEx;
using BepInEx.Configuration;
using HarmonyLib;
using Jotunn.Managers;
using Jotunn.Utils;
using Jotunn.Entities;
using UnityEngine;
using System.Reflection;

namespace BlightedHeart
{
    [BepInPlugin(PluginGUID, PluginName, PluginVersion)]
    [BepInDependency(Jotunn.Main.ModGuid)]
    [NetworkCompatibility(CompatibilityLevel.EveryoneMustHaveMod, VersionStrictness.Minor)]
    public class BlightedHeartPlugin : BaseUnityPlugin
    {
        public const string PluginGUID = "wubarrk.blightedworldheart";
        public const string PluginName = "BlightedWorldHeart";
        public const string PluginVersion = "1.2.1";

        public static bool IsWackyDBInstalled = false;
        public static BlightedHeartPlugin Instance;

        private readonly Harmony _harmony = new Harmony(PluginGUID);

        private void Awake()
        {
            Instance = this;

            // Set up config
            BlightedConfigManager.SetupConfig(this);

            // Matched IGNORING CASE - Chainloader.PluginInfos is ordinal/case-sensitive, so a plugin that
            // re-cases its own GUID between releases silently stops being detected. See PluginLookup.
            IsWackyDBInstalled = PluginLookup.IsLoaded("WackyMole.WackysDatabase");
            if (IsWackyDBInstalled)
            {
                Jotunn.Logger.LogInfo("Wacky's Database detected! Blighted recipes that have a WackyDB recipe YAML are left to that YAML; all others get their normal upgrade costs.");
            }

            // Prefab Manager Hook
            PrefabManager.OnVanillaPrefabsAvailable += SetupBlightedHeartPrefab;
            PrefabManager.OnVanillaPrefabsAvailable += BlightedItemsManager.Setup;
            PrefabManager.OnVanillaPrefabsAvailable += BlightedSubBosses.Setup;   // 1.2.0: the six Hive Sub-Bosses

            _harmony.PatchAll();
            
            Jotunn.Logger.LogInfo($"{PluginName} v{PluginVersion} loaded.");
        }

        private void SetupBlightedHeartPrefab()
        {
            PrefabManager.OnVanillaPrefabsAvailable -= SetupBlightedHeartPrefab;
            
            Jotunn.Logger.LogInfo("Setting up Blighted World Heart prefab...");
            
            GameObject go = PrefabManager.Instance.CreateClonedPrefab("BlightedWorldHeart", "TheHive");
            if (go == null)
            {
                Jotunn.Logger.LogError("Could not create cloned prefab BlightedWorldHeart!");
                return;
            }

            CustomPrefab heartPrefab = new CustomPrefab(go, fixReference: true);

            // Scale down the prefab to 10% of its size
            go.transform.localScale = new Vector3(0.1f, 0.1f, 0.1f);

            // Ensure ZNetView exists
            var znet = go.GetComponent<ZNetView>();
            if (znet == null) znet = go.AddComponent<ZNetView>();

            // Add custom AI - all component cleanup happens at RUNTIME in Awake()
            // because prefab-time DestroyImmediate doesn't survive Valheim's serialization
            var ai = go.AddComponent<BlightedWorldHeartAI>();

            PrefabManager.Instance.AddPrefab(heartPrefab);
            Jotunn.Logger.LogInfo("BlightedWorldHeart prefab registered. Runtime cleanup will happen on spawn.");

            // Add UI Manager
            var uiManagerGo = new GameObject("BlightedUIManager");
            DontDestroyOnLoad(uiManagerGo);
            uiManagerGo.AddComponent<BlightedUIManager>();
        }
    }
    
    public class BlightedDamageForwarder : MonoBehaviour, IDestructible
    {
        public BlightedWorldHeartAI m_heart;

        public DestructibleType GetDestructibleType()
        {
            return m_heart != null ? m_heart.GetDestructibleType() : DestructibleType.Default;
        }

        public void Damage(HitData hit)
        {
            if (m_heart != null)
            {
                m_heart.Damage(hit);
            }
        }
    }

    public class BlightedSubBoss : MonoBehaviour
    {
        public Character m_character;
        private void Awake()
        {
            m_character = GetComponent<Character>();
            // Force m_boss to false so Valheim's EnemyHud doesn't try to draw a native Boss Bar and crash
            if (m_character != null) m_character.m_boss = false;
        }
    }

    [HarmonyPatch(typeof(Character), nameof(Character.RPC_Damage))]
    public static class BlightedSubBossDamagePatch
    {
        public static void Prefix(Character __instance, ref HitData hit)
        {
            if (__instance.GetComponent<BlightedSubBoss>() != null && hit != null)
            {
                float magicMultiplier = BlightedConfigManager.MagicDamageMultiplier != null ? BlightedConfigManager.MagicDamageMultiplier.Value : 0.25f;
                
                // Mitigate magical damage
                hit.m_damage.m_fire *= magicMultiplier;
                hit.m_damage.m_frost *= magicMultiplier;
                hit.m_damage.m_lightning *= magicMultiplier;
                hit.m_damage.m_poison *= magicMultiplier;
                hit.m_damage.m_spirit *= magicMultiplier;
                hit.m_damage.m_damage *= magicMultiplier; // Pure damage
            }
        }
    }
}
