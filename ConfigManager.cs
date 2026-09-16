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

            EnableBarrkBotExport = plugin.Config.Bind("BarrkBOT Export", "Enable BarrkBOT Export", true, new ConfigDescription("Write a per-biome raid status file to BepInEx/config/BlightedHeart/barrkbot_blightedheart.json for external tools (e.g. BarrkBOT) to read. Server-side only; off means nothing is written.", null, new ConfigurationManagerAttributes { IsAdminOnly = true }));
            BarrkBotExportIntervalSeconds = plugin.Config.Bind("BarrkBOT Export", "Export Interval Seconds", 30f, new ConfigDescription("How often the BarrkBOT export file is rewritten.", new AcceptableValueRange<float>(15f, 600f), new ConfigurationManagerAttributes { IsAdminOnly = true }));


            // Setup per-biome configuration
            SetupBiomeConfig(plugin, Heightmap.Biome.Meadows, 3450f, 0.5f, 0.2f, 862.5f, 1437.5f, 1.5f, 6, 8f, "HardAntler", 1);
            SetupBiomeConfig(plugin, Heightmap.Biome.BlackForest, 6900f, 0.5f, 0.2f, 1725f, 2875f, 2.0f, 7, 8f, "CryptKey", 1);
            SetupBiomeConfig(plugin, Heightmap.Biome.Swamp, 10350f, 0.5f, 0.2f, 2587.5f, 4312.5f, 2.5f, 8, 8f, "Wishbone", 1);
            SetupBiomeConfig(plugin, Heightmap.Biome.Mountain, 13800f, 0.5f, 0.2f, 3450f, 5750f, 3.0f, 9, 8f, "DragonTear", 1);
            SetupBiomeConfig(plugin, Heightmap.Biome.Plains, 20700f, 0.5f, 0.2f, 5175f, 8625f, 3.5f, 10, 8f, "YagluthDrop", 1);
            SetupBiomeConfig(plugin, Heightmap.Biome.Mistlands, 27600f, 0.5f, 0.2f, 6900f, 11500f, 4.5f, 11, 8f, "QueenDrop", 1);
            SetupBiomeConfig(plugin, Heightmap.Biome.AshLands, 34500f, 0.5f, 0.2f, 8625f, 14375f, 5.5f, 12, 8f, "FaderDrop", 1);
            SetupBiomeConfig(plugin, Heightmap.Biome.DeepNorth, 43125f, 0.5f, 0.2f, 10350f, 17250f, 6.0f, 13, 8f, "FrozenKingDrop", 1); // Kall Fimbulbringer's drop (1.0 Deep North boss)
            
            // Allow Server Admins to change the config
            // Let Jotunn and BepInEx handle automatic saving
        }

        private static void SetupBiomeConfig(
            BlightedHeartPlugin plugin, 
            Heightmap.Biome biome, 
            float defaultHP, 
            float defaultThreshold1, 
            float defaultThreshold2, 
            float defaultSubBoss1HP,
            float defaultSubBoss2HP,
            float defaultLootScale, 
            int defaultMaxEnemies,
            float defaultWaveTimer,
            string defaultSummonItem,
            int defaultSummonAmount)
        {
            string section = biome.ToString();

            var config = new BiomeConfig
            {
                BossHP = plugin.Config.Bind(
                    section, 
                    "Boss HP", 
                    defaultHP, 
                    new ConfigDescription($"Base maximum Health of the Blighted World Heart when summoned in the {section}. This determines the overall duration and difficulty of the raid event.", new AcceptableValueRange<float>(100f, 100000f), new ConfigurationManagerAttributes { IsAdminOnly = true })),
                
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

            BiomeConfigs[biome] = config;
        }
    }
}
