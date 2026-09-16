using UnityEngine;
using System.Reflection;
using System.Collections.Generic;
using Jotunn.Managers;
using System;

namespace BlightedHeart
{
    public class BlightedWorldHeartAI : MonoBehaviour, IDestructible
    {
        // ============================================================
        // Custom health system — we own the entire damage pipeline.
        // No Destructible component, no RPC collisions.
        // ============================================================
        private static readonly int RPC_BlightedDamage = "RPC_BlightedHeartDamage".GetStableHashCode();

        public float m_health;
        public float m_maxHealth = 2000f;
        private bool m_isDead = false;

        public Heightmap.Biome CurrentBiome;
        private float _lastWaveTime;
        private float _waveInterval = 30f;

        private bool _subBoss1Spawned = false;
        private bool _subBoss2Spawned = false;
        public bool SubBoss1Active => m_subBoss1 != null && !m_subBoss1.IsDead();
        public bool SubBoss2Active => m_subBoss2 != null && !m_subBoss2.IsDead();
        public Character m_subBoss1;
        public Character m_subBoss2;
        
        public ZNetView m_nview;
        private float _lastLogTime = 0f;

        // ZDO keys — uniquely named to avoid collision with any vanilla or mod keys
        private static readonly int ZDO_Health = "blighted_health".GetStableHashCode();
        private static readonly int ZDO_MaxHealth = "blighted_max_health".GetStableHashCode();
        private static readonly string ZDO_SubBoss1 = "blighted_subboss1";
        private static readonly string ZDO_SubBoss2 = "blighted_subboss2";

        public void Awake()
        {
            m_nview = GetComponent<ZNetView>();
            
            // ============================================================
            // RUNTIME CLEANUP: Strip ALL vanilla components from the live
            // instance. We keep ONLY ZNetView and our own components.
            //
            // Destroy order matters — dependents before dependencies.
            // ============================================================
            
            // Phase 1: Destroy components that depend on Character/Humanoid
            foreach (var cae in GetComponentsInChildren<CharacterAnimEvent>(true))
                DestroyImmediate(cae);
            foreach (var cd in GetComponentsInChildren<CharacterDrop>(true))
                DestroyImmediate(cd);
            foreach (var ai in GetComponentsInChildren<BaseAI>(true))
                DestroyImmediate(ai);
            foreach (var fh in GetComponentsInChildren<FootStep>(true))
                DestroyImmediate(fh);
            foreach (var vis in GetComponentsInChildren<VisEquipment>(true))
                DestroyImmediate(vis);
            
            // Phase 2: Destroy Character/Humanoid itself
            foreach (var ch in GetComponentsInChildren<Character>(true))
            {
                Jotunn.Logger.LogInfo($"[BlightedHeart] Stripping Character: {ch.gameObject.name}");
                DestroyImmediate(ch);
            }
            
            // Phase 3: Animation, physics, and remaining vanilla components
            foreach (var zsa in GetComponentsInChildren<ZSyncAnimation>(true))
                DestroyImmediate(zsa);
            foreach (var anim in GetComponentsInChildren<Animator>(true))
                DestroyImmediate(anim);
            foreach (var rb in GetComponentsInChildren<Rigidbody>(true))
                DestroyImmediate(rb);
            foreach (var aoe in GetComponentsInChildren<Aoe>(true))
            {
                Jotunn.Logger.LogInfo($"[BlightedHeart] Stripping Aoe: {aoe.gameObject.name}");
                DestroyImmediate(aoe);
            }
            foreach (var mr in GetComponentsInChildren<MineRock5>(true))
                DestroyImmediate(mr);
            foreach (var ha in GetComponentsInChildren<HitArea>(true))
                DestroyImmediate(ha);
            foreach (var d in GetComponentsInChildren<Destructible>(true))
                DestroyImmediate(d);
            
            // Phase 4: Destroy trigger colliders (contact damage zones)
            foreach (var col in GetComponentsInChildren<Collider>(true))
            {
                if (col != null && col.isTrigger)
                    DestroyImmediate(col);
            }
            
            // Phase 5: Nuke any remaining unknown MonoBehaviours
            foreach (var mb in GetComponentsInChildren<MonoBehaviour>(true))
            {
                if (mb == null) continue;
                if (mb is ZNetView) continue;
                if (mb is BlightedWorldHeartAI) continue;
                if (mb is BlightedDamageForwarder) continue;
                DestroyImmediate(mb);
            }
            
            // ============================================================
            // Register our custom RPC with a unique name — no collisions
            // ============================================================
            if (m_nview != null)
            {
                m_nview.Register<HitData>("RPC_BlightedHeartDamage", RPC_HandleDamage);
            }
            
            // Initialize health from ZDO or default
            m_health = m_maxHealth;
            if (m_nview != null && m_nview.GetZDO() != null)
            {
                float savedHealth = m_nview.GetZDO().GetFloat(ZDO_Health, 0f);
                if (savedHealth > 0f)
                {
                    m_health = savedHealth;
                }
                float savedMax = m_nview.GetZDO().GetFloat(ZDO_MaxHealth, 0f);
                if (savedMax > 0f)
                {
                    m_maxHealth = savedMax;
                }
            }
            
            // Route ALL remaining child colliders to us via BlightedDamageForwarder
            foreach (var col in GetComponentsInChildren<Collider>(true))
            {
                if (col != null && col.gameObject != gameObject)
                {
                    var forwarder = col.gameObject.GetComponent<BlightedDamageForwarder>();
                    if (forwarder == null) forwarder = col.gameObject.AddComponent<BlightedDamageForwarder>();
                    forwarder.m_heart = this;
                }
            }
            
            // Add a collider on the root if there isn't one
            var rootCollider = gameObject.GetComponent<Collider>();
            if (rootCollider == null)
            {
                var box = gameObject.AddComponent<BoxCollider>();
                box.size = new Vector3(10f, 10f, 10f);
                box.center = Vector3.zero;
            }
            
            if (BlightedUIManager.Instance != null)
            {
                BlightedUIManager.Instance.RegisterHeart(this);
            }
            
            Jotunn.Logger.LogInfo("[BlightedHeart] Runtime cleanup complete. Custom IDestructible active.");
        }

        // ============================================================
        // IDestructible Implementation — this is what Valheim's attack
        // system calls when a player hits us with a weapon.
        // ============================================================
        
        public DestructibleType GetDestructibleType()
        {
            return DestructibleType.Default;
        }
        
        public void Damage(HitData hit)
        {
            if (m_isDead) return;
            if (m_nview == null || !m_nview.IsValid()) return;
            
            // Protect the Blighted World Heart from non-player damage (e.g., Abominations, Trolls, other enemies)
            // But ALLOW players and their tamed/summoned creatures
            if (hit != null)
            {
                var attacker = hit.GetAttacker();
                if (attacker == null || (!attacker.IsPlayer() && !attacker.IsTamed()))
                {
                    return;
                }
            }

            // If we're not the owner, forward via RPC to the owner
            if (!m_nview.IsOwner())
            {
                m_nview.InvokeRPC("RPC_BlightedHeartDamage", hit);
                return;
            }
            
            // Separate physical and magic/elemental damage
            float physicalDamage = hit.m_damage.m_blunt + hit.m_damage.m_slash + hit.m_damage.m_pierce + hit.m_damage.m_chop + hit.m_damage.m_pickaxe;
            float magicDamage = hit.m_damage.m_fire + hit.m_damage.m_frost + hit.m_damage.m_lightning + hit.m_damage.m_poison + hit.m_damage.m_spirit + hit.m_damage.m_damage;
            
            float magicMultiplier = BlightedConfigManager.MagicDamageMultiplier != null ? BlightedConfigManager.MagicDamageMultiplier.Value : 0.25f;
            float totalDamage = physicalDamage + (magicDamage * magicMultiplier);
            
            if (totalDamage <= 0f) return;
            
            m_health -= totalDamage;
            
            // Sync to ZDO
            m_nview.GetZDO().Set(ZDO_Health, m_health);
            
            // Show floating damage number
            if (DamageText.instance != null)
            {
                DamageText.instance.ShowText(DamageText.TextType.Normal, hit.m_point, totalDamage);
            }
            
            // Hit effect (flash or particle)
            // We could add visual feedback here later
            
            if (BlightedConfigManager.DebugMode != null && BlightedConfigManager.DebugMode.Value)
            {
                Jotunn.Logger.LogInfo($"[BlightedHeart] Took {totalDamage:F1} damage. Health: {m_health:F0}/{m_maxHealth:F0}");
            }
            
            // Check for death
            if (m_health <= 0f)
            {
                m_health = 0f;
                m_isDead = true;
                OnDeath();
            }
        }
        
        private void RPC_HandleDamage(long sender, HitData hit)
        {
            // This runs on the owner when a non-owner sends damage
            Damage(hit);
        }
        
        private void OnDeath()
        {
            Jotunn.Logger.LogInfo("[BlightedHeart] The Blighted World Heart has been destroyed!");

            // NOT the place to record a defeat for BarrkBotExport: OnDeath only runs on whichever peer
            // currently owns this ZDO, which during an active fight is typically a *player's* client, not
            // the dedicated server (ownership follows whoever is standing in the zone) - see the "Fires
            // server-side?" table in PAUSED/TheRavensCall/KILL_TRACKING_FINDINGS.md. BarrkBotExport instead
            // watches ZDOMan.m_onZDODestroyed, which is broadcast to every peer including the server
            // regardless of who owned the object.

            // Drop loot
            DropLoot();
            
            // Announce death
            if (Player.m_localPlayer != null)
            {
                Player.MessageAllInRange(transform.position, 200f, MessageHud.MessageType.Center, "The Blighted World Heart has been purified!");
            }
            
            // Destroy the object
            if (m_nview != null && m_nview.IsOwner())
            {
                m_nview.Destroy();
            }
        }
        
        private void DropLoot()
        {
            if (!BlightedConfigManager.BiomeConfigs.TryGetValue(CurrentBiome, out var config)) return;
            
            int playerCount = 1;
            List<Player> players = new List<Player>();
            Player.GetPlayersInRange(transform.position, 100f, players);
            if (players.Count > 0)
            {
                playerCount = players.Count;
            }

            int dropCount = 3 + (playerCount - 1);
            if (dropCount < 3) dropCount = 3;

            bool hasWeapons = BlightedItemsManager.BiomeWeaponDrops.TryGetValue(CurrentBiome, out var weapons) && weapons.Count > 0;
            bool hasArmors = BlightedItemsManager.BiomeArmorDrops.TryGetValue(CurrentBiome, out var armors) && armors.Count > 0;

            if (!hasWeapons && !hasArmors) return;

            for (int i = 0; i < dropCount; i++)
            {
                bool dropWeapon = UnityEngine.Random.value > 0.5f;
                if ((dropWeapon && hasWeapons) || !hasArmors)
                {
                    string randomWeapon = weapons[UnityEngine.Random.Range(0, weapons.Count)];
                    SpawnDrop(randomWeapon);
                }
                else if (hasArmors)
                {
                    string randomArmor = armors[UnityEngine.Random.Range(0, armors.Count)];
                    SpawnDrop(randomArmor);
                }
            }
        }
        
        private void SpawnDrop(string prefabName)
        {
            var prefab = ZNetScene.instance?.GetPrefab(prefabName);
            if (prefab != null)
            {
                Vector3 dropPos = transform.position + Vector3.up * 1f + UnityEngine.Random.insideUnitSphere * 0.5f;
                UnityEngine.Object.Instantiate(prefab, dropPos, Quaternion.identity);
            }
        }

        private void OnDestroy()
        {
            if (BlightedUIManager.Instance != null)
            {
                BlightedUIManager.Instance.UnregisterHeart(this);
            }
        }

        public void Initialize(Heightmap.Biome biome)
        {
            CurrentBiome = biome;
            // Force first wave to spawn exactly 1 second after initialization
            if (BlightedConfigManager.BiomeConfigs.TryGetValue(biome, out var c))
            {
                float waveInterval = c.WaveTimerSeconds != null ? c.WaveTimerSeconds.Value : _waveInterval;
                _lastWaveTime = Time.time - waveInterval + 1f;
            }
            else
            {
                _lastWaveTime = Time.time - _waveInterval + 1f;
            }
            
            // Update stats based on biome config
            if (BlightedConfigManager.BiomeConfigs.TryGetValue(biome, out var config))
            {
                m_maxHealth = config.BossHP.Value;
                m_health = m_maxHealth;
                
                if (m_nview != null && m_nview.GetZDO() != null)
                {
                    m_nview.GetZDO().Set(ZDO_Health, m_health);
                    m_nview.GetZDO().Set(ZDO_MaxHealth, m_maxHealth);
                }
            }

            ApplyBiomeVisuals(biome);
        }

        private void ApplyBiomeVisuals(Heightmap.Biome biome)
        {
            Renderer[] renderers = GetComponentsInChildren<Renderer>();
            Color tintColor = GetBiomeColor(biome);

            foreach (Renderer r in renderers)
            {
                if (r.material != null)
                {
                    r.material.SetColor("_Color", tintColor);
                    if (r.material.HasProperty("_EmissionColor"))
                    {
                        r.material.SetColor("_EmissionColor", tintColor * 2.0f);
                        r.material.EnableKeyword("_EMISSION");
                    }
                }
            }
        }

        private Color GetBiomeColor(Heightmap.Biome biome)
        {
            switch (biome)
            {
                case Heightmap.Biome.Meadows: return new Color(0.2f, 0.8f, 0.2f);
                case Heightmap.Biome.BlackForest: return new Color(0.5f, 0.1f, 0.8f);
                case Heightmap.Biome.Swamp: return new Color(0.4f, 0.3f, 0.1f);
                case Heightmap.Biome.Mountain: return new Color(0.8f, 0.9f, 1.0f);
                case Heightmap.Biome.Plains: return new Color(0.9f, 0.7f, 0.2f);
                case Heightmap.Biome.Mistlands: return new Color(0.3f, 0.1f, 0.5f);
                case Heightmap.Biome.AshLands: return new Color(1.0f, 0.2f, 0.0f);
                case Heightmap.Biome.DeepNorth: return new Color(0.9f, 0.9f, 1.0f);
                default: return Color.white;
            }
        }

        private void Update()
        {
            if (m_nview == null || m_isDead)
                return;

            if (!m_nview.IsOwner())
            {
                if (m_nview.GetZDO() != null)
                {
                    m_health = m_nview.GetZDO().GetFloat(ZDO_Health, m_health);
                    m_maxHealth = m_nview.GetZDO().GetFloat(ZDO_MaxHealth, m_maxHealth);

                    if (m_subBoss1 == null)
                    {
                        ZDOID sb1_id = m_nview.GetZDO().GetZDOID(ZDO_SubBoss1);
                        if (sb1_id != ZDOID.None)
                        {
                            GameObject go = ZNetScene.instance.FindInstance(sb1_id);
                            if (go) m_subBoss1 = go.GetComponent<Character>();
                        }
                    }
                    if (m_subBoss2 == null)
                    {
                        ZDOID sb2_id = m_nview.GetZDO().GetZDOID(ZDO_SubBoss2);
                        if (sb2_id != ZDOID.None)
                        {
                            GameObject go = ZNetScene.instance.FindInstance(sb2_id);
                            if (go) m_subBoss2 = go.GetComponent<Character>();
                        }
                    }
                }
                return;
            }
                
            CheckSubBossThresholds();
            HandleWaveSpawning();
        }

        private void HandleWaveSpawning()
        {
            if (!BlightedConfigManager.BiomeConfigs.TryGetValue(CurrentBiome, out var config)) return;
            
            float waveInterval = config.WaveTimerSeconds != null ? config.WaveTimerSeconds.Value : _waveInterval;
            if (Time.time - _lastWaveTime > waveInterval)
            {
                _lastWaveTime = Time.time;
                SpawnWave();
            }
        }

        private List<GameObject> m_spawnedEnemies = new List<GameObject>();

        private void SpawnWave()
        {
            if (!BlightedConfigManager.BiomeConfigs.TryGetValue(CurrentBiome, out var config)) return;
            
            int maxEnemies = config.MaxEnemiesPerWave.Value;
            
            // Clean up dead or destroyed enemies
            m_spawnedEnemies.RemoveAll(e => e == null || e.GetComponent<Character>() == null || e.GetComponent<Character>().IsDead());
            
            int toSpawn = maxEnemies - m_spawnedEnemies.Count;
            if (toSpawn <= 0) return;

            string[] enemyPrefabs = GetWaveEnemiesForBiome(CurrentBiome);
            if (enemyPrefabs.Length == 0) return;

            if (BlightedConfigManager.DebugMode.Value)
                Jotunn.Logger.LogInfo($"Attempting to spawn {toSpawn} wave enemies (Current: {m_spawnedEnemies.Count}/{maxEnemies}) of type {string.Join(",", enemyPrefabs)} in {CurrentBiome}.");

            int spawned = 0;
            for (int i = 0; i < toSpawn; i++)
            {
                string prefabName = enemyPrefabs[UnityEngine.Random.Range(0, enemyPrefabs.Length)];
                GameObject prefab = ZNetScene.instance.GetPrefab(prefabName);
                if (prefab != null)
                {
                    Vector3 spawnPos = GetGroundedSpawnPosition(10f);
                    GameObject spawnedEnemy = UnityEngine.Object.Instantiate(prefab, spawnPos, Quaternion.identity);
                    m_spawnedEnemies.Add(spawnedEnemy);
                    spawned++;
                    
                    // Remove standard vanilla loot from summoned wave enemies
                    var charDrops = spawnedEnemy.GetComponentsInChildren<CharacterDrop>(true);
                    foreach(var cd in charDrops) UnityEngine.Object.Destroy(cd);
                    
                    // Make the spawned enemy immediately aggressive towards any nearby player
                    BaseAI enemyAI = spawnedEnemy.GetComponent<BaseAI>();
                    if (enemyAI != null)
                    {
                        enemyAI.Alert();
                        Player closestPlayer = Player.GetClosestPlayer(spawnPos, 50f);
                        if (closestPlayer != null)
                        {
                            MonsterAI monsterAI = spawnedEnemy.GetComponent<MonsterAI>();
                            if (monsterAI != null)
                            {
                                monsterAI.SetTarget(closestPlayer.GetComponent<Character>());
                            }
                        }
                    }
                }
                else if (BlightedConfigManager.DebugMode.Value)
                {
                    Jotunn.Logger.LogWarning($"Wave enemy prefab {prefabName} not found in ZNetScene.");
                }
            }

            if (BlightedConfigManager.DebugMode.Value)
                Jotunn.Logger.LogInfo($"Successfully spawned {spawned} wave enemies.");
                
            if (spawned > 0 && BlightedConfigManager.EnableWaveAnnouncement.Value)
            {
                Player.MessageAllInRange(transform.position, 100f, BlightedConfigManager.WaveAnnouncementLocation.Value, "The Blighted World Heart cries out for the fallen...");
            }
        }

        private void CheckSubBossThresholds()
        {
            if (!BlightedConfigManager.BiomeConfigs.TryGetValue(CurrentBiome, out var config)) return;

            float healthPct = m_health / m_maxHealth;

            if (BlightedConfigManager.DebugMode.Value && Time.time - _lastLogTime > 5f)
            {
                _lastLogTime = Time.time;
                Jotunn.Logger.LogInfo($"Checking SubBoss thresholds. Current Health: {healthPct:P0}. T1: {config.SubBossThreshold1.Value:P0}, T2: {config.SubBossThreshold2.Value:P0}. Spawned: {_subBoss1Spawned}, {_subBoss2Spawned}");
            }

            if (!_subBoss1Spawned && healthPct <= config.SubBossThreshold1.Value)
            {
                _subBoss1Spawned = true;
                SpawnSubBoss(1, config.SubBoss1HP.Value);
            }
            if (!_subBoss2Spawned && healthPct <= config.SubBossThreshold2.Value)
            {
                _subBoss2Spawned = true;
                SpawnSubBoss(2, config.SubBoss2HP.Value);
            }
        }

        // Solid-height margin vanilla gives the 1.0 Deep North altar (offeraltar_FrozenKing_bossroom), whose
        // boss room is enclosed. A ray started that far above the Heart finds the room's floor; the default
        // 1000 m ray starts above the roof and finds the roof instead.
        private const int IndoorSolidHeightMargin = 4;

        // A random point within `radius` of the Heart (horizontal only), snapped to the ground. The short ray is
        // tried first so that inside the Deep North boss room spawns land on the floor rather than the roof; in
        // open terrain it can start below ground on an uphill slope and miss, so the full 1000 m ray is the
        // fallback there, and the Heart's own height is the last resort exactly as before.
        private Vector3 GetGroundedSpawnPosition(float radius)
        {
            Vector2 offset = UnityEngine.Random.insideUnitCircle * radius;
            Vector3 spawnPos = transform.position + new Vector3(offset.x, 0f, offset.y);
            float height;
            if (ZoneSystem.instance.GetSolidHeight(spawnPos, out height, IndoorSolidHeightMargin) ||
                ZoneSystem.instance.GetSolidHeight(spawnPos, out height))
            {
                spawnPos.y = height;
            }
            return spawnPos;
        }

        private void SpawnSubBoss(int index, float maxHealth)
        {
            string subBossPrefabName = GetSubBossForBiome(CurrentBiome);
            
            if (BlightedConfigManager.DebugMode.Value)
                Jotunn.Logger.LogInfo($"Attempting to spawn subboss: {subBossPrefabName} for biome {CurrentBiome}");

            GameObject prefab = ZNetScene.instance.GetPrefab(subBossPrefabName);
            
            if (prefab != null)
            {
                Vector3 spawnPos = GetGroundedSpawnPosition(5f);
                
                GameObject subBoss = UnityEngine.Object.Instantiate(prefab, spawnPos, Quaternion.identity);
                
                if (BlightedConfigManager.DebugMode.Value)
                    Jotunn.Logger.LogInfo($"Successfully spawned subboss {subBossPrefabName}");

                // Scale it up and make it a subboss
                subBoss.transform.localScale *= 1.5f;
                
                // Strip vanilla drops
                var charDrops = subBoss.GetComponentsInChildren<CharacterDrop>(true);
                foreach(var cd in charDrops) UnityEngine.Object.Destroy(cd);

                foreach (var comp in subBoss.GetComponentsInChildren<Component>(true))
                {
                    string typeName = comp.GetType().Name;
                    if (typeName == "DropOnDestroy" || typeName == "SpawnOnDestroy")
                    {
                        UnityEngine.Object.Destroy(comp);
                    }
                }
                
                Character character = subBoss.GetComponent<Character>();
                if (character != null)
                {
                    character.SetLevel(3);
                    character.SetMaxHealth(maxHealth);
                    character.SetHealth(maxHealth);
                }
                
                // Attach our subboss component to fix UI overlap
                subBoss.AddComponent<BlightedSubBoss>();

                // Shadows of Midgard interop: stamp SoM's networked stealth-exemption flag so SoM
                // leaves sub-bosses entirely alone (no stealth senses, no flee/retreat orders) on
                // EVERY peer. The BlightedSubBoss component above is AddComponent'd locally and is
                // not networked, so it cannot protect the sub-boss after ZDO ownership migrates to
                // another client - the ZDO flag can. The key string is SoM's frozen public API
                // (ShadowsOfMidgard.StealthExemption.ZDOKey, "present and 1" means exempt); writing
                // it with SoM absent is one harmless ZDO int.
                ZNetView subBossView = subBoss.GetComponent<ZNetView>();
                if (subBossView != null && subBossView.GetZDO() != null)
                {
                    subBossView.GetZDO().Set("SoMStealthExempt", 1);
                }
            
                if (index == 1) 
                {
                    m_subBoss1 = character;
                    if (m_nview != null && m_nview.GetZDO() != null && character != null)
                    {
                        ZNetView sbView = character.GetComponent<ZNetView>();
                        if (sbView != null && sbView.GetZDO() != null)
                        {
                            m_nview.GetZDO().Set(ZDO_SubBoss1, sbView.GetZDO().m_uid);
                        }
                    }
                }
                else if (index == 2) 
                {
                    m_subBoss2 = character;
                    if (m_nview != null && m_nview.GetZDO() != null && character != null)
                    {
                        ZNetView sbView = character.GetComponent<ZNetView>();
                        if (sbView != null && sbView.GetZDO() != null)
                        {
                            m_nview.GetZDO().Set(ZDO_SubBoss2, sbView.GetZDO().m_uid);
                        }
                    }
                }
            }
        }

        private string[] GetWaveEnemiesForBiome(Heightmap.Biome biome)
        {
            switch (biome)
            {
                case Heightmap.Biome.Meadows: return new[] { "Boar", "Neck", "Greyling" };
                case Heightmap.Biome.BlackForest: return new[] { "Greydwarf", "Greydwarf_Elite", "Skeleton" };
                case Heightmap.Biome.Swamp: return new[] { "Draugr", "Blob", "Leech" };
                case Heightmap.Biome.Mountain: return new[] { "Wolf", "Hatchling" };
                case Heightmap.Biome.Plains: return new[] { "Goblin", "Deathsquito" };
                case Heightmap.Biome.Mistlands: return new[] { "Seeker", "SeekerBrood" };
                case Heightmap.Biome.AshLands: return new[] { "Charred_Melee", "Charred_Archer" };
                case Heightmap.Biome.DeepNorth: return new[] { "Greydwarf_Frozen", "Skeleton_DeepNorth", "Elaking" }; // all DeepNorth faction, so the wave does not fight itself
                default: return new[] { "Boar" };
            }
        }

        private string GetSubBossForBiome(Heightmap.Biome biome)
        {
            string[] options;
            switch (biome)
            {
                case Heightmap.Biome.Meadows: 
                    options = new[] { "Boar", "Neck" }; 
                    break;
                case Heightmap.Biome.BlackForest: 
                    options = new[] { "Greydwarf_Elite", "Troll", "Skeleton_Poison" }; 
                    break;
                case Heightmap.Biome.Swamp: 
                    options = new[] { "Draugr_Elite", "Wraith", "Abomination" }; 
                    break;
                case Heightmap.Biome.Mountain: 
                    options = new[] { "Fenring", "StoneGolem" }; 
                    break;
                case Heightmap.Biome.Plains: 
                    options = new[] { "GoblinBrute", "GoblinShaman", "Lox" }; 
                    break;
                case Heightmap.Biome.Mistlands: 
                    options = new[] { "SeekerBrute", "Seeker" }; 
                    break;
                case Heightmap.Biome.AshLands:
                    options = new[] { "Morgen", "Charred_Melee" };
                    break;
                case Heightmap.Biome.DeepNorth:
                    options = new[] { "JotunWarrior", "JotunWitch", "Barka", "TrollFrost" };
                    break;
                default:
                    options = new[] { "Boar" };
                    break;
            }
            return options[UnityEngine.Random.Range(0, options.Length)];
        }
    }
}
