using BepInEx;
using Newtonsoft.Json;
using System;
using System.Collections.Generic;
using System.Globalization;
using System.IO;

namespace BlightedHeart
{
    // Lifetime per-biome raid counters (times summoned, times defeated, when last defeated).
    // This is our own persistence, not the BarrkBOT-facing file — mirrors TortalPortal's
    // playernames.json vs barrkbot_portals.json split. Every live BlightedWorldHeartAI instance
    // is destroyed on death, so without this, "times defeated" would reset to zero on every
    // server restart and BarrkBotExport would have nothing truthful to report.
    public static class BlightedHeartStats
    {
        public class BiomeRecord
        {
            public int TimesSummoned;
            public int TimesDefeated;
            public DateTime? LastDefeatedUtc;
        }

        private static string StatsPath => Path.Combine(Paths.ConfigPath, "BlightedHeart", "stats.json");

        private static Dictionary<Heightmap.Biome, BiomeRecord> _records;

        public static IReadOnlyDictionary<Heightmap.Biome, BiomeRecord> Records
        {
            get
            {
                EnsureLoaded();
                return _records;
            }
        }

        public static void RecordSummon(Heightmap.Biome biome)
        {
            EnsureLoaded();
            GetOrAdd(biome).TimesSummoned++;
            Save();
        }

        public static void RecordDefeat(Heightmap.Biome biome)
        {
            EnsureLoaded();
            BiomeRecord record = GetOrAdd(biome);
            record.TimesDefeated++;
            record.LastDefeatedUtc = DateTime.UtcNow;
            Save();
        }

        private static BiomeRecord GetOrAdd(Heightmap.Biome biome)
        {
            if (!_records.TryGetValue(biome, out BiomeRecord record))
            {
                record = new BiomeRecord();
                _records[biome] = record;
            }
            return record;
        }

        private static void EnsureLoaded()
        {
            if (_records != null) return;
            _records = new Dictionary<Heightmap.Biome, BiomeRecord>();

            try
            {
                if (!File.Exists(StatsPath)) return;

                string json = File.ReadAllText(StatsPath);
                Dictionary<string, RawRecord> raw = JsonConvert.DeserializeObject<Dictionary<string, RawRecord>>(json);
                if (raw == null) return;

                foreach (KeyValuePair<string, RawRecord> pair in raw)
                {
                    if (!Enum.TryParse(pair.Key, out Heightmap.Biome biome)) continue;

                    _records[biome] = new BiomeRecord
                    {
                        TimesSummoned = pair.Value.times_summoned,
                        TimesDefeated = pair.Value.times_defeated,
                        LastDefeatedUtc = string.IsNullOrEmpty(pair.Value.last_defeated)
                            ? (DateTime?)null
                            : DateTime.Parse(pair.Value.last_defeated, CultureInfo.InvariantCulture, DateTimeStyles.AdjustToUniversal | DateTimeStyles.AssumeUniversal)
                    };
                }
            }
            catch (Exception ex)
            {
                // Corrupt or unreadable stats file: start empty rather than crash. The next summon/defeat
                // starts a fresh count for that biome - better than latching every read into a permanent no-op.
                Jotunn.Logger.LogWarning($"BlightedHeart: could not read stats.json (non-fatal, starting fresh). Reason: {ex.Message}");
                _records = new Dictionary<Heightmap.Biome, BiomeRecord>();
            }
        }

        private static void Save()
        {
            try
            {
                Dictionary<string, RawRecord> raw = new Dictionary<string, RawRecord>();
                foreach (KeyValuePair<Heightmap.Biome, BiomeRecord> pair in _records)
                {
                    raw[pair.Key.ToString()] = new RawRecord
                    {
                        times_summoned = pair.Value.TimesSummoned,
                        times_defeated = pair.Value.TimesDefeated,
                        last_defeated = pair.Value.LastDefeatedUtc?.ToString("o", CultureInfo.InvariantCulture)
                    };
                }

                string dir = Path.Combine(Paths.ConfigPath, "BlightedHeart");
                Directory.CreateDirectory(dir);

                string tmp = StatsPath + ".tmp";
                File.WriteAllText(tmp, JsonConvert.SerializeObject(raw, Formatting.Indented));

                if (File.Exists(StatsPath)) File.Replace(tmp, StatsPath, null);
                else File.Move(tmp, StatsPath);
            }
            catch (Exception ex)
            {
                Jotunn.Logger.LogWarning($"BlightedHeart: could not save stats.json (non-fatal, previous file stands). Reason: {ex.Message}");
            }
        }

        private class RawRecord
        {
            public int times_summoned;
            public int times_defeated;
            public string last_defeated;
        }
    }
}
