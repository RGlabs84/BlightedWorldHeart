using BepInEx;
using HarmonyLib;
using Newtonsoft.Json;
using System;
using System.Collections;
using System.Collections.Generic;
using System.Globalization;
using System.IO;
using UnityEngine;

namespace BlightedHeart
{
    // A live answer to "is the Heart up anywhere, and how's the fight going" — written where an admin,
    // or BarrkBOT off the same /BepInEx/config tree it already reads every other mod's export from, can
    // read it without being in the game. Modelled on TortalPortal's PortalExport.cs: server-side only,
    // atomic tmp+replace, generated_at/source header.
    //
    // World/event-keyed, not player-keyed — there's no per-player identity in a raid, just "what is the
    // Heart doing in each biome right now, and what has it done historically." A biome that has never had
    // a Heart summoned is OMITTED entirely, never written with zeroed fields — BarrkBOT has been burned
    // before by a fabricated zero reading as a real fact (see BARRKBOT_CONTRACT.md).
    public static class BarrkBotExport
    {
        private static string ExportDir => Path.Combine(Paths.ConfigPath, "BlightedHeart");
        private static string ExportPath => Path.Combine(ExportDir, "barrkbot_blightedheart.json");

        private static Coroutine _routine;

        // Biomes with a live Heart as of the previous tick. Comparing against this each tick is how we
        // detect a NEW summon without hooking the spawn call itself — the spawn flow runs on whichever
        // client used the altar, not necessarily this process, so a live-state scan here (which only ever
        // runs where ZNet.instance.IsServer() is true) is the one place a summon is guaranteed to be
        // observed on the server's own machine.
        private static HashSet<Heightmap.Biome> _previouslyActive = new HashSet<Heightmap.Biome>();

        private static readonly int BlightedHeartPrefabHash = "BlightedWorldHeart".GetStableHashCode();
        private static bool _subscribedToZDODestroyed;

        public static void OnZNetStart()
        {
            try
            {
                Reset();
                if (ZNet.instance == null || !ZNet.instance.IsServer()) return;
                if (!BlightedConfigManager.EnableBarrkBotExport.Value) return;

                _routine = BlightedHeartPlugin.Instance.StartCoroutine(ExportRoutine());

                // Defeats are recorded here, not from BlightedWorldHeartAI.OnDeath() - that method only runs
                // on whichever peer currently owns the boss's ZDO, which during an active fight is normally
                // a player's client, not this server (see PAUSED/TheRavensCall-OLD-1.2.1/KILL_TRACKING_FINDINGS.md).
                // m_onZDODestroyed is broadcast to every peer, including the server, once the destroy is
                // confirmed network-wide, regardless of who owned the object - the same event ZNetScene
                // itself subscribes to for its own bookkeeping. It also can't be confused with a zone unload
                // (that only removes the local GameObject via RemoveObjects and leaves the ZDO intact), so
                // this stays a reliable "really defeated" signal without needing a client-reported RPC.
                if (ZDOMan.instance != null)
                {
                    ZDOMan.instance.m_onZDODestroyed += OnZDODestroyed;
                    _subscribedToZDODestroyed = true;
                }
            }
            catch (Exception ex)
            {
                Jotunn.Logger.LogError($"BlightedHeart: could not start the BarrkBOT export (non-fatal). Reason: {ex}");
            }
        }

        // Coroutines live on the plugin object, which survives a world change; ZNet.Start does not.
        public static void Reset()
        {
            if (_routine != null && BlightedHeartPlugin.Instance != null) BlightedHeartPlugin.Instance.StopCoroutine(_routine);
            _routine = null;
            _previouslyActive = new HashSet<Heightmap.Biome>();

            if (_subscribedToZDODestroyed && ZDOMan.instance != null)
            {
                ZDOMan.instance.m_onZDODestroyed -= OnZDODestroyed;
            }
            _subscribedToZDODestroyed = false;
        }

        private static void OnZDODestroyed(ZDO zdo)
        {
            try
            {
                if (zdo == null || zdo.GetPrefab() != BlightedHeartPrefabHash) return;
                BlightedHeartStats.RecordDefeat(BiomeAt(zdo.GetPosition()));
            }
            catch (Exception ex)
            {
                Jotunn.Logger.LogWarning($"BlightedHeart: could not record a Heart defeat (non-fatal). Reason: {ex.Message}");
            }
        }

        // Heightmap.FindBiome answers from the loaded Heightmap under the point and returns Biome.None when
        // there is none. A dedicated server only builds real zones (with heightmaps) around (0,0) - everywhere
        // else is ZDO-only - so for any Heart away from spawn it would file the record under "None". The
        // world generator's biome is pure math over the seed and is valid at any position on every peer.
        private static Heightmap.Biome BiomeAt(Vector3 position)
        {
            Heightmap.Biome biome = Heightmap.FindBiome(position);
            if (biome == Heightmap.Biome.None && WorldGenerator.instance != null)
            {
                biome = WorldGenerator.instance.GetBiome(position);
            }
            return biome;
        }

        private static IEnumerator ExportRoutine()
        {
            yield return new WaitForSeconds(5f);

            while (true)
            {
                Write();
                yield return new WaitForSeconds(Mathf.Max(15f, BlightedConfigManager.BarrkBotExportIntervalSeconds.Value));
            }
            // ReSharper disable once IteratorNeverReturns
        }

        // Kept out of the coroutine so the risky work can sit in a try/catch - C# forbids "yield return"
        // inside a try block with a catch clause.
        private static void Write()
        {
            try
            {
                Dictionary<Heightmap.Biome, BlightedWorldHeartAI> liveHearts = new Dictionary<Heightmap.Biome, BlightedWorldHeartAI>();
                foreach (BlightedWorldHeartAI heart in UnityEngine.Object.FindObjectsOfType<BlightedWorldHeartAI>())
                {
                    if (heart == null) continue;
                    // Biome is read from world position rather than heart.CurrentBiome: CurrentBiome is set
                    // by Initialize(), which only runs on whichever peer's client spawned the boss. On a
                    // true dedicated server that's a different process than this one, so CurrentBiome would
                    // silently read the enum default there. Position is authoritative on every peer.
                    Heightmap.Biome biome = BiomeAt(heart.transform.position);
                    liveHearts[biome] = heart;
                }

                HashSet<Heightmap.Biome> currentlyActive = new HashSet<Heightmap.Biome>(liveHearts.Keys);
                foreach (Heightmap.Biome biome in currentlyActive)
                {
                    if (!_previouslyActive.Contains(biome))
                    {
                        BlightedHeartStats.RecordSummon(biome);
                    }
                }
                _previouslyActive = currentlyActive;

                Dictionary<string, object> biomesOut = new Dictionary<string, object>();

                // Union of "ever recorded" and "active right now" - a biome can be active on the very first
                // tick after a summon, in the same write as its RecordSummon() call above.
                HashSet<Heightmap.Biome> everRelevant = new HashSet<Heightmap.Biome>(currentlyActive);
                foreach (Heightmap.Biome biome in BlightedHeartStats.Records.Keys) everRelevant.Add(biome);

                foreach (Heightmap.Biome biome in everRelevant)
                {
                    bool active = liveHearts.TryGetValue(biome, out BlightedWorldHeartAI heart);
                    BlightedHeartStats.Records.TryGetValue(biome, out BlightedHeartStats.BiomeRecord stats);

                    biomesOut[biome.ToString()] = new Dictionary<string, object>
                    {
                        ["active"] = active,
                        ["current_hp_percent"] = active && heart.m_maxHealth > 0f
                            ? (object)Math.Round(heart.m_health / heart.m_maxHealth * 100.0, 1)
                            : null,
                        ["subboss_1_active"] = active && heart.SubBoss1Active,
                        ["subboss_2_active"] = active && heart.SubBoss2Active,
                        ["times_summoned"] = stats?.TimesSummoned ?? 0,
                        ["times_defeated"] = stats?.TimesDefeated ?? 0,
                        ["last_defeated"] = stats?.LastDefeatedUtc?.ToString("o", CultureInfo.InvariantCulture)
                    };
                }

                Dictionary<string, object> doc = new Dictionary<string, object>
                {
                    ["generated_at"] = DateTime.UtcNow.ToString("o", CultureInfo.InvariantCulture),
                    ["source"] = $"{BlightedHeartPlugin.PluginName} {BlightedHeartPlugin.PluginVersion}",
                    ["biomes"] = biomesOut
                };

                Save(JsonConvert.SerializeObject(doc, Formatting.Indented));
            }
            catch (Exception ex)
            {
                Jotunn.Logger.LogError($"BlightedHeart: the BarrkBOT export could not be built (non-fatal, the previous file stands). Reason: {ex}");
            }
        }

        private static void Save(string json)
        {
            Directory.CreateDirectory(ExportDir);

            string tmp = ExportPath + ".tmp";
            File.WriteAllText(tmp, json);

            // Written aside and swapped in, never written in place - anything pulling this file on its own
            // schedule (BarrkBOT, an admin's script) would otherwise eventually catch it half-written.
            if (File.Exists(ExportPath)) File.Replace(tmp, ExportPath, null);
            else File.Move(tmp, ExportPath);
        }
    }

    [HarmonyPatch]
    public static class BarrkBotExportPatches
    {
        [HarmonyPatch(typeof(ZNet), nameof(ZNet.Start))]
        [HarmonyPostfix]
        public static void ZNet_Start_Postfix()
        {
            BarrkBotExport.OnZNetStart();
        }

        [HarmonyPatch(typeof(ZNet), "Shutdown")]
        [HarmonyPostfix]
        public static void ZNet_Shutdown_Postfix()
        {
            BarrkBotExport.Reset();
        }
    }
}
