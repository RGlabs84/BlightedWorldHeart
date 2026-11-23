using System.Collections.Generic;
using Jotunn.Entities;
using Jotunn.Managers;
using UnityEngine;

namespace BlightedHeart
{
    // The six Hive Sub-Bosses (1.2.0). Each is a CLONE of a vanilla creature (its mesh, rig, animations, attacks and AI),
    // registered as its own network prefab, so every peer builds the same thing. The art (repaint, vanilla Hive parts on
    // the bones) is applied by BlightedSubBossLook on top; the art data lives in art/subbosses/ (owner-approved 2026-11-22).
    //
    // Biome mapping (owner, 2026-11-22):
    //   Meadows: Rootstalker | Black Forest: Eyeblight Seer, Hive Brute | Swamp: Barkbound Husk | Mountain: Rootstalker,
    //   Hive Brute | Plains: Gorgemaw | Mistlands: Broodhusk | Ashlands, Deep North: any of the six.
    // Sub-Boss HP per biome stays the existing per-altar config (Sub-Boss 1 HP / Sub-Boss 2 HP), so the Ashlands and Deep North
    // picks are "scaled up" by those values.
    public static class BlightedSubBosses
    {
        public sealed class Def
        {
            public string Id;          // our prefab name
            public string Donor;       // the vanilla creature it is cloned from
            public string DisplayName; // shown on the health bar
        }

        public static readonly Def HiveBrute = new Def { Id = "BlightedSB_HiveBrute", Donor = "Troll", DisplayName = "Hive Brute" };
        public static readonly Def Rootstalker = new Def { Id = "BlightedSB_Rootstalker", Donor = "Wolf", DisplayName = "Rootstalker" };
        public static readonly Def Gorgemaw = new Def { Id = "BlightedSB_Gorgemaw", Donor = "Lox", DisplayName = "Gorgemaw" };
        public static readonly Def EyeblightSeer = new Def { Id = "BlightedSB_EyeblightSeer", Donor = "Greydwarf_Shaman", DisplayName = "Eyeblight Seer" };
        public static readonly Def BarkboundHusk = new Def { Id = "BlightedSB_BarkboundHusk", Donor = "Draugr", DisplayName = "Barkbound Husk" };
        public static readonly Def Broodhusk = new Def { Id = "BlightedSB_Broodhusk", Donor = "Seeker", DisplayName = "Broodhusk" };

        public static readonly Def[] All = { HiveBrute, Rootstalker, Gorgemaw, EyeblightSeer, BarkboundHusk, Broodhusk };

        private static readonly Dictionary<Heightmap.Biome, Def[]> ByBiome = new Dictionary<Heightmap.Biome, Def[]>
        {
            { Heightmap.Biome.Meadows, new[] { Rootstalker } },
            { Heightmap.Biome.BlackForest, new[] { EyeblightSeer, HiveBrute } },
            { Heightmap.Biome.Swamp, new[] { BarkboundHusk } },
            { Heightmap.Biome.Mountain, new[] { Rootstalker, HiveBrute } },
            { Heightmap.Biome.Plains, new[] { Gorgemaw } },
            { Heightmap.Biome.Mistlands, new[] { Broodhusk } },
            { Heightmap.Biome.AshLands, All },
            { Heightmap.Biome.DeepNorth, All },
        };

        // ZDO keys on a spawned Sub-Boss (read on every peer by BlightedSubBossLook).
        public static readonly int ZdoBiome = "blighted_sb_biome".GetStableHashCode();

        private static readonly HashSet<string> Registered = new HashSet<string>();

        // Called from OnVanillaPrefabsAvailable. A donor that is missing (renamed in a game update) is skipped with a warning,
        // and that biome falls back to the vanilla Sub-Boss list.
        public static void Setup()
        {
            PrefabManager.OnVanillaPrefabsAvailable -= Setup;
            foreach (Def d in All)
            {
                GameObject go = PrefabManager.Instance.CreateClonedPrefab(d.Id, d.Donor);
                if (go == null)
                {
                    Jotunn.Logger.LogWarning($"[BlightedHeart] Sub-Boss {d.Id}: donor '{d.Donor}' not found; this Sub-Boss is disabled.");
                    continue;
                }

                Character ch = go.GetComponent<Character>();
                if (ch != null)
                {
                    ch.m_name = d.DisplayName;
                    ch.m_boss = false;        // our own health bar draws it (see BlightedSubBoss)
                }

                // A Sub-Boss is never a pet, a mount or a breeder: the Wolf and the Lox carry taming and breeding.
                StripTaming(go);
                // Never vanilla loot (1.2.1): its drops are BlightedHeartLoot's gear roll.
                foreach (var c in go.GetComponentsInChildren<CharacterDrop>(true)) Object.DestroyImmediate(c, true);

                go.AddComponent<BlightedSubBossLook>().DefId = d.Id;

                // The approved Hive art on the prefab itself (clients only; instances inherit it).
                BlightedSubBossKit.Apply(go, d.Id);
                BlightedSubBossRepaint.Apply(go, d.Id);       // stage 3b: the donor body repainted from our maps

                PrefabManager.Instance.AddPrefab(new CustomPrefab(go, false));
                Registered.Add(d.Id);
                Jotunn.Logger.LogInfo($"[BlightedHeart] Sub-Boss prefab {d.Id} registered (clone of {d.Donor}).");
            }
        }

        public static void StripTaming(GameObject go)
        {
            foreach (var c in go.GetComponentsInChildren<Tameable>(true)) Object.DestroyImmediate(c, true);
            foreach (var c in go.GetComponentsInChildren<Procreation>(true)) Object.DestroyImmediate(c, true);
            foreach (var c in go.GetComponentsInChildren<Growup>(true)) Object.DestroyImmediate(c, true);
        }

        // The prefab name for a Sub-Boss in this biome, or null to use the vanilla list.
        public static string PickFor(Heightmap.Biome biome)
        {
            if (!ByBiome.TryGetValue(biome, out Def[] options)) return null;
            var live = new List<Def>();
            foreach (Def d in options)
            {
                if (Registered.Contains(d.Id)) live.Add(d);
            }
            if (live.Count == 0) return null;
            return live[Random.Range(0, live.Count)].Id;
        }

        public static bool IsOurs(string prefabName) => prefabName != null && prefabName.StartsWith("BlightedSB_");
    }

    // Applied on every peer when a Sub-Boss instance wakes: the biome tint (base colour only, like the Heart: owner,
    // 2026-11-22; multiplied, as the approved panel was rendered). The Hive art kit itself is on the prefab (BlightedSubBossKit). Purely cosmetic and client-side; nothing here is networked except
    // the biome, which the Heart's owner writes to the ZDO at spawn.
    public class BlightedSubBossLook : MonoBehaviour
    {
        public string DefId;
        private ZNetView _nview;
        private bool _applied;

        private void Awake()
        {
            _nview = GetComponent<ZNetView>();
            // Belt and braces: taming components stripped on the prefab are stripped again on the live instance.
            BlightedSubBosses.StripTaming(gameObject);
        }

        private void Update()
        {
            if (_applied) return;
            if (_nview == null || !_nview.IsValid()) return;
            int biome = _nview.GetZDO().GetInt(BlightedSubBosses.ZdoBiome, 0);
            if (biome == 0) return;                   // the spawning owner has not written it yet
            _applied = true;
            if (SystemInfo.graphicsDeviceType == UnityEngine.Rendering.GraphicsDeviceType.Null) return;   // headless server
            ApplyBiomeTint((Heightmap.Biome)biome);
        }

        // The approved "colour only" look (art/subbosses/kit_tools/final_look.py _biome, previews/final_biome_blackforest_panel.png
        // left): the Heart's biome colour MULTIPLIED onto each material's own colour, in linear space - the crust stays bark, the
        // eyes stay dark, everything leans to the biome. Raw Get/SetVector (Runic DESIGN 9.25). No emission override.
        internal static Vector4 Tinted(Vector4 own, Color tint)
        {
            Color lin = tint.linear;
            return new Vector4(own.x * lin.r, own.y * lin.g, own.z * lin.b, own.w);
        }

        private void ApplyBiomeTint(Heightmap.Biome biome)
        {
            Color tint = BlightedWorldHeartAI.GetBiomeColor(biome);
            foreach (Renderer r in GetComponentsInChildren<Renderer>(true))
            {
                if (r is ParticleSystemRenderer) continue;
                foreach (Material m in r.materials)              // instance copies: the shared Sub-Boss and vanilla materials are untouched
                {
                    if (m != null && m.HasProperty("_Color")) m.SetVector("_Color", Tinted(m.GetVector("_Color"), tint));
                }
            }
        }
    }
}
