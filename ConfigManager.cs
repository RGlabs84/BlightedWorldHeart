using BepInEx.Configuration;
using Jotunn.Configs;
using Jotunn.Managers;
using System.Collections.Generic;

namespace BlightedHeart
{
    public static class BlightedConfigManager
    {
        public class BiomeConfig
        {
            public ConfigEntry<float> BossHP;
            public ConfigEntry<float> SubBossThreshold1;
            public ConfigEntry<float> SubBossThreshold2;
            public ConfigEntry<float> SubBoss1HP;
            public ConfigEntry<float> SubBoss2HP;
            public ConfigEntry<float> LootScaleFactor;
            public ConfigEntry<int> MaxEnemiesPerWave;
            public ConfigEntry<float> WaveTimerSeconds;
            public ConfigEntry<string> AltarSummonItem;
            public ConfigEntry<int> AltarSummonAmount;
        }

        public static Dictionary<Heightmap.Biome, BiomeConfig> BiomeConfigs = new Dictionary<Heightmap.Biome, BiomeConfig>();

        public static ConfigEntry<bool> DebugMode;
        public static ConfigEntry<bool> EnableWaveAnnouncement;
        public static ConfigEntry<MessageHud.MessageType> WaveAnnouncementLocation;
        public static ConfigEntry<float> MagicDamageMultiplier;
        public static ConfigEntry<bool> AllowRefinementForgeUpgrades;
        public static ConfigEntry<int> SubBossLevel;
        public static ConfigEntry<float> SubBossDamageMultiplier;
        public static ConfigEntry<float> SubBossGearDropChance;
        public static ConfigEntry<bool> UseBlightedFaction;
        public static ConfigEntry<bool> EnableBarrkBotExport;
        public static ConfigEntry<float> BarrkBotExportIntervalSeconds;

        public static void SetupConfig(BlightedHeartPlugin plugin)
        {
            // Sync configs using Jotunn's SynchronizationManager
            plugin.Config.SaveOnConfigSet = true;

            DebugMode = plugin.Config.Bind("General", "Debug Mode", false, new ConfigDescription("Enable verbose debug logging.", null, new ConfigurationManagerAttributes { IsAdminOnly = true }));
            EnableWaveAnnouncement = plugin.Config.Bind("General", "Enable Wave Announcement", true, new ConfigDescription("Toggle for wave spawn text.", null, new ConfigurationManagerAttributes { IsAdminOnly = true }));
            WaveAnnouncementLocation = plugin.Config.Bind("General", "Wave Announcement Location", MessageHud.MessageType.Center, new ConfigDescription("Where the wave text displays.", null, new ConfigurationManagerAttributes { IsAdminOnly = true }));
            MagicDamageMultiplier = plugin.Config.Bind("General", "Magic Damage Multiplier", 0.25f, new ConfigDescription("Damage multiplier for elemental/magic damage (Fire, Frost, Lightning, Poison, Spirit, Pure) against the Blighted Heart.", null, new ConfigurationManagerAttributes { IsAdminOnly = true }));
            AllowRefinementForgeUpgrades = plugin.Config.Bind("General", "Allow Refinement Forge Upgrades", false, new ConfigDescription("Valheim 1.0 only. Also let Blighted items be upgraded at the Refinement Forge (Upgrade Station) with the same Upgrader item as their base item - including past max quality, with vanilla's chance to FAIL or DESTROY the item. Off: Blighted items upgrade only at the normal station with trophies + materials, exactly as before 1.0.", null, new ConfigurationManagerAttributes { IsAdminOnly = true }));

            SubBossLevel = plugin.Config.Bind("General", "Sub-Boss Level", 2, new ConfigDescription("Star level of the Sub-Bosses the Heart summons (the stars shown over them). Since 1.2.1 stars no longer add damage: use Sub-Boss Damage Multiplier. Their HP is set separately per biome. This was fixed at 3 before 1.1.1.", new AcceptableValueRange<int>(1, 5), new ConfigurationManagerAttributes { IsAdminOnly = true }));

            SubBossDamageMultiplier = plugin.Config.Bind("General", "Sub-Boss Damage Multiplier", 1f, new ConfigDescription("Sub-Boss damage as a multiple of the vanilla creature it is cloned from (1 = exactly the vanilla creature's hit, no star bonus). Whatever the multiplier, a Sub-Boss never hits harder than the hardest-hitting vanilla creature of the biome it was summoned in (Meadows: Eikthyr's 20).", new AcceptableValueRange<float>(0.1f, 3f), new ConfigurationManagerAttributes { IsAdminOnly = true }));
            SubBossGearDropChance = plugin.Config.Bind("General", "Sub-Boss Gear Drop Chance", 0.25f, new ConfigDescription("Chance that a slain Sub-Boss drops one random Blighted weapon or armour piece of the biome it was summoned in. 0 = Sub-Bosses drop nothing. They never drop vanilla loot.", new AcceptableValueRange<float>(0f, 1f), new ConfigurationManagerAttributes { IsAdminOnly = true }));

            UseBlightedFaction = plugin.Config.Bind("General", "Blighted Faction", true, new ConfigDescription("Everything the Heart summons (waves and Sub-Bosses) joins the Heart's own faction: allied with each other, hostile to players, tames and every other creature. Off: summons keep their vanilla factions, so mixed waves (e.g. Greydwarfs and Skeletons) can fight each other, as before 1.2.0.", null, new ConfigurationManagerAttributes { IsAdminOnly = true }));

            EnableBarrkBotExport = plugin.Config.Bind("BarrkBOT Export", "Enable BarrkBOT Export", true, new ConfigDescription("Write a per-biome raid status file to BepInEx/config/BlightedHeart/barrkbot_blightedheart.json for external tools (e.g. BarrkBOT) to read. Server-side only; off means nothing is written.", null, new ConfigurationManagerAttributes { IsAdminOnly = true }));
            BarrkBotExportIntervalSeconds = plugin.Config.Bind("BarrkBOT Export", "Export Interval Seconds", 30f, new ConfigDescription("How often the BarrkBOT export file is rewritten.", new AcceptableValueRange<float>(15f, 600f), new ConfigurationManagerAttributes { IsAdminOnly = true }));


            // BepInEx writes every default into the cfg file, so a file created by an older version keeps the OLD
            // defaults forever. Revision 1 (1.1.1) rebalanced the Heart/Sub-Boss HP defaults; on the first start
            // with it, any of those entries still sitting on its old default is moved to the new one (a value an
            // admin changed is never touched), then the revision is recorded so this runs exactly once.
            var defaultsRevision = plugin.Config.Bind("General", "Defaults Revision", 0, new ConfigDescription("Internal bookkeeping for one-time default upgrades. Do not edit.", null, new ConfigurationManagerAttributes { Browsable = false }));
            _upgradeLegacyDefaults = defaultsRevision.Value < DefaultsRevision;

            // Setup per-biome configuration. The first number is the biome's tier multiplier: Heart and Sub-Boss
            // HP defaults are all (per-tier unit x tier), so the biomes stay proportional to each other and so
            // do the Heart and its Sub-Bosses - change a unit above and every biome moves in step.
            SetupBiomeConfig(plugin, Heightmap.Biome.Meadows, 1f, 0.5f, 0.2f, 1.5f, 6, 8f, "HardAntler", 1);
            SetupBiomeConfig(plugin, Heightmap.Biome.BlackForest, 2f, 0.5f, 0.2f, 2.0f, 7, 8f, "CryptKey", 1);
            SetupBiomeConfig(plugin, Heightmap.Biome.Swamp, 3f, 0.5f, 0.2f, 2.5f, 8, 8f, "Wishbone", 1);
            SetupBiomeConfig(plugin, Heightmap.Biome.Mountain, 4f, 0.5f, 0.2f, 3.0f, 9, 8f, "DragonTear", 1);
            SetupBiomeConfig(plugin, Heightmap.Biome.Plains, 6f, 0.5f, 0.2f, 3.5f, 10, 8f, "YagluthDrop", 1);
            SetupBiomeConfig(plugin, Heightmap.Biome.Mistlands, 8f, 0.5f, 0.2f, 4.5f, 11, 8f, "QueenDrop", 1);
            SetupBiomeConfig(plugin, Heightmap.Biome.AshLands, 10f, 0.5f, 0.2f, 5.5f, 12, 8f, "FaderDrop", 1);
            SetupBiomeConfig(plugin, Heightmap.Biome.DeepNorth, 12.5f, 0.5f, 0.2f, 6.0f, 13, 8f, "FrozenKingDrop", 1); // Kall Fimbulbringer's drop (1.0 Deep North boss)

            if (_upgradeLegacyDefaults) defaultsRevision.Value = DefaultsRevision;

            // Allow Server Admins to change the config
            // Let Jotunn and BepInEx handle automatic saving
        }

        // Per-tier units behind the Heart/Sub-Boss HP defaults (default = unit x the biome's tier multiplier).
        //  - Heart: a stationary raid target that takes full damage from every attacker (no armor, no dodging,
        //    no phases), so it needs to be far beefier than a mobile vanilla boss to last a few minutes. 1.0.x -
        //    1.1.0 used 3450 per tier and was reported far too easy at Elder tier.
        //  - Sub-Bosses: sized like a vanilla 1-star / 2-star elite of the biome (a Black Forest Troll is 600 base
        //    HP: 1200 at 1 star, 1800 at 2 stars). Through 1.1.0 they were a fixed 25% / 42% of the Heart, so
        //    raising the Heart would have raised them with it, and Black Forest's second one (2875 HP) already
        //    out-tanked the vanilla Elder (2500). Now 4.2% and 6.7% of the Heart at every tier.
        private const float HeartHpPerTier = 12000f;
        private const float SubBoss1HpPerTier = 500f;
        private const float SubBoss2HpPerTier = 800f;

        // Bump when the shipped default of an EXISTING entry changes, and add the old values to LegacyHpDefaults.
        private const int DefaultsRevision = 1;
        private static bool _upgradeLegacyDefaults;

        // Boss HP / Sub-Boss 1 HP / Sub-Boss 2 HP exactly as shipped through 1.1.0 (Deep North's Sub-Bosses were
        // 12x, not 12.5x, so these are explicit numbers rather than a unit x tier).
        private static readonly Dictionary<Heightmap.Biome, float[]> LegacyHpDefaults = new Dictionary<Heightmap.Biome, float[]>
        {
            { Heightmap.Biome.Meadows,     new[] { 3450f,  862.5f,  1437.5f } },
            { Heightmap.Biome.BlackForest, new[] { 6900f,  1725f,   2875f } },
            { Heightmap.Biome.Swamp,       new[] { 10350f, 2587.5f, 4312.5f } },
            { Heightmap.Biome.Mountain,    new[] { 13800f, 3450f,   5750f } },
            { Heightmap.Biome.Plains,      new[] { 20700f, 5175f,   8625f } },
            { Heightmap.Biome.Mistlands,   new[] { 27600f, 6900f,   11500f } },
            { Heightmap.Biome.AshLands,    new[] { 34500f, 8625f,   14375f } },
            { Heightmap.Biome.DeepNorth,   new[] { 43125f, 10350f,  17250f } },
        };

        // Moves one entry to its (new) default if, and only if, it is still exactly the old default.
        private static void UpgradeLegacyDefault(ConfigEntry<float> entry, float legacyDefault)
        {
            float current = entry.Value;
            float upgraded = (float)entry.DefaultValue;
            if (System.Math.Abs(current - legacyDefault) > 0.01f) return;   // an admin's own value: leave it
            if (System.Math.Abs(current - upgraded) <= 0.01f) return;       // already there

            Jotunn.Logger.LogInfo($"Config [{entry.Definition.Section}] {entry.Definition.Key}: {current} was the old default, updated to the new default {upgraded}.");
            entry.Value = upgraded;
        }

        private static void SetupBiomeConfig(
            BlightedHeartPlugin plugin, 
            Heightmap.Biome biome, 
            float tier, 
            float defaultThreshold1, 
            float defaultThreshold2, 
            float defaultLootScale, 
            int defaultMaxEnemies,
            float defaultWaveTimer,
            string defaultSummonItem,
            int defaultSummonAmount)
        {
            string section = biome.ToString();

            float defaultHP = HeartHpPerTier * tier;
            float defaultSubBoss1HP = SubBoss1HpPerTier * tier;
            float defaultSubBoss2HP = SubBoss2HpPerTier * tier;

            var config = new BiomeConfig
            {
                BossHP = plugin.Config.Bind(
                    section, 
                    "Boss HP", 
                    defaultHP, 
                    new ConfigDescription($"Base maximum Health of the Blighted World Heart when summoned in the {section}. This determines the overall duration and difficulty of the raid event.", new AcceptableValueRange<float>(100f, 1000000f), new ConfigurationManagerAttributes { IsAdminOnly = true })),
                
                SubBossThreshold1 = plugin.Config.Bind(
                    section, 
                    "Sub-Boss Threshold 1", 
                    defaultThreshold1, 
                    new ConfigDescription("The health percentage remaining (e.g., 0.5 = 50%) at which the Heart retaliates by summoning the first massive sub-boss.", new AcceptableValueRange<float>(0.01f, 0.99f), new ConfigurationManagerAttributes { IsAdminOnly = true })),
                
                SubBossThreshold2 = plugin.Config.Bind(
                    section, 
                    "Sub-Boss Threshold 2", 
                    defaultThreshold2, 
                    new ConfigDescription("The health percentage remaining (e.g., 0.2 = 20%) at which the Heart retaliates by summoning the second massive sub-boss in a final desperate stand.", new AcceptableValueRange<float>(0.01f, 0.99f), new ConfigurationManagerAttributes { IsAdminOnly = true })),
                
                SubBoss1HP = plugin.Config.Bind(
                    section, 
                    "Sub-Boss 1 HP", 
                    defaultSubBoss1HP, 
                    new ConfigDescription("Total maximum Health of the first sub-boss spawned at Threshold 1.", new AcceptableValueRange<float>(100f, 50000f), new ConfigurationManagerAttributes { IsAdminOnly = true })),
                
                SubBoss2HP = plugin.Config.Bind(
                    section, 
                    "Sub-Boss 2 HP", 
                    defaultSubBoss2HP, 
                    new ConfigDescription("Total maximum Health of the second sub-boss spawned at Threshold 2.", new AcceptableValueRange<float>(100f, 50000f), new ConfigurationManagerAttributes { IsAdminOnly = true })),
                
                LootScaleFactor = plugin.Config.Bind(
                    section, 
                    "Loot Scale Factor", 
                    defaultLootScale, 
                    new ConfigDescription("Determines the power, rarity, and drop quantity of Blighted Gear upon defeating the Heart.", new AcceptableValueRange<float>(0.1f, 10f), new ConfigurationManagerAttributes { IsAdminOnly = true })),
                
                MaxEnemiesPerWave = plugin.Config.Bind(
                    section, 
                    "Max Enemies Per Wave", 
                    defaultMaxEnemies, 
                    new ConfigDescription("The absolute maximum number of standard horde enemies that can be alive simultaneously during a wave.", new AcceptableValueRange<int>(1, 100), new ConfigurationManagerAttributes { IsAdminOnly = true })),
                    
                WaveTimerSeconds = plugin.Config.Bind(
                    section, 
                    "Wave Timer Seconds", 
                    defaultWaveTimer, 
                    new ConfigDescription("The exact time in seconds between each successive wave of enemies spawned by the Heart.", new AcceptableValueRange<float>(1f, 300f), new ConfigurationManagerAttributes { IsAdminOnly = true })),
                    
                AltarSummonItem = plugin.Config.Bind(
                    section,
                    "Altar Summon Item",
                    defaultSummonItem,
                    new ConfigDescription("The exact prefab name of the item required to be sacrificed to invoke the Heart.", null, new ConfigurationManagerAttributes { IsAdminOnly = true })),
                    
                AltarSummonAmount = plugin.Config.Bind(
                    section,
                    "Altar Summon Amount",
                    defaultSummonAmount,
                    new ConfigDescription("The required quantity of the summon item to successfully corrupt the altar.", new AcceptableValueRange<int>(1, 100), new ConfigurationManagerAttributes { IsAdminOnly = true }))
            };

            if (_upgradeLegacyDefaults && LegacyHpDefaults.TryGetValue(biome, out float[] legacy))
            {
                UpgradeLegacyDefault(config.BossHP, legacy[0]);
                UpgradeLegacyDefault(config.SubBoss1HP, legacy[1]);
                UpgradeLegacyDefault(config.SubBoss2HP, legacy[2]);
            }

            BiomeConfigs[biome] = config;
        }
    }
}
