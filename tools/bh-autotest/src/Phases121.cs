// 1.2.1 phases (owner playtest 2026-11-23): D = Sub-Boss damage and what summons drop, R = the Heart resumes after its
// zone unloads and reloads (everyone died and respawned away, a relog, a zone reload).
using System;
using System.Collections;
using System.Collections.Generic;
using System.Linq;
using BlightedHeart;
using UnityEngine;

namespace BHAutoTest
{
    public partial class AutoTest
    {
        // The hardest vanilla hit per biome, from the game's item data (libs-Tools WubarrksEye Values_Dump), written out here
        // on its own so the check does not just read the mod's table back.
        static readonly Dictionary<Heightmap.Biome, float> TestCap = new Dictionary<Heightmap.Biome, float>
        {
            { Heightmap.Biome.Meadows, 20f }, { Heightmap.Biome.BlackForest, 70f }, { Heightmap.Biome.Swamp, 80f },
            { Heightmap.Biome.Mountain, 110f }, { Heightmap.Biome.Plains, 130f }, { Heightmap.Biome.Mistlands, 230f },
        };

        static float LevelFactor(Humanoid h, ItemDrop.ItemData item)
        {
            Attack a = item.m_shared.m_attack.Clone();
            a.m_character = h;
            a.m_weapon = item;
            return a.GetLevelDamageFactor();
        }

        static void Hold(GameObject go)
        {
            if (go == null) return;
            BaseAI ai = go.GetComponent<BaseAI>();
            if (ai != null) ai.enabled = false;
        }

        static void Kill(GameObject go, Player by)
        {
            Character c = go != null ? go.GetComponent<Character>() : null;
            if (c == null) return;
            var hit = new HitData();
            hit.m_damage.m_blunt = 1e6f; hit.m_damage.m_slash = 1e6f; hit.m_damage.m_pierce = 1e6f;
            hit.m_point = c.GetCenterPoint();
            hit.SetAttacker(by);
            c.Damage(hit);
        }

        static List<ItemDrop> DropsNear(Vector3 at, float r, HashSet<ItemDrop> before) =>
            UnityEngine.Object.FindObjectsOfType<ItemDrop>().Where(x => !before.Contains(x) && Vector3.Distance(x.transform.position, at) < r).ToList();

        static HashSet<string> GearPool(Heightmap.Biome b)
        {
            var s = new HashSet<string>();
            if (BlightedItemsManager.BiomeWeaponDrops.TryGetValue(b, out var w)) s.UnionWith(w);
            if (BlightedItemsManager.BiomeArmorDrops.TryGetValue(b, out var a)) s.UnionWith(a);
            return s;
        }

        // ------------------------------------------------------------------------------------------ D: damage and drops

        IEnumerator PhaseD()
        {
            ResetPlayer();
            Player p = Player.m_localPlayer;
            int level = BlightedConfigManager.SubBossLevel.Value;
            float mult = BlightedConfigManager.SubBossDamageMultiplier.Value;
            float vanillaStar = 1f + Mathf.Max(0, level - 1) * 0.5f;
            int combos = 0, combosOk = 0;

            foreach (BlightedSubBosses.Def d in BlightedSubBosses.All)
            {
                GameObject sb = Spawn(d.Id, OnGround(Origin + Fwd * 12f - Right * 5f), Quaternion.LookRotation(-Fwd));
                GameObject dn = Spawn(d.Donor, OnGround(Origin + Fwd * 12f + Right * 5f), Quaternion.LookRotation(-Fwd));
                yield return Sec(1.5f);
                Hold(sb); Hold(dn);
                Humanoid h = sb != null ? sb.GetComponent<Humanoid>() : null, hv = dn != null ? dn.GetComponent<Humanoid>() : null;
                if (h == null || hv == null) { Result("FAIL", $"damage: {d.DisplayName} spawn", $"Sub-Boss {(h != null)}, donor {d.Donor} {(hv != null)}"); Remove(sb); Remove(dn); continue; }
                h.SetLevel(level); hv.SetLevel(level);

                var attacks = h.GetInventory().GetAllItems().Where(i => i.m_shared.m_attack != null && BlightedSubBossBalance.BaseHit(i) > 0f).ToList();
                var dAttacks = hv.GetInventory().GetAllItems().Where(i => i.m_shared.m_attack != null && BlightedSubBossBalance.BaseHit(i) > 0f).ToList();
                if (attacks.Count == 0) { Result("FAIL", $"damage: {d.DisplayName} attacks", "no damaging items in its inventory"); Remove(sb); Remove(dn); continue; }

                // control: the vanilla donor at the same level keeps vanilla's star bonus (the patch touches Sub-Bosses only)
                var ctrl = dAttacks.Select(i => LevelFactor(hv, i)).ToList();
                Check(ctrl.Count > 0 && ctrl.All(f => Mathf.Abs(f - vanillaStar) < 1e-4f), $"damage: vanilla {d.Donor} unchanged",
                    $"level {level}: factor {string.Join("/", ctrl.Select(f => f.ToString("0.###")).Distinct())} (vanilla {vanillaStar:0.###})");

                ZDO zdo = sb.GetComponent<ZNetView>().GetZDO();
                foreach (var kv in BlightedSubBosses.ByBiome.Where(kv => kv.Value.Contains(d)))
                {
                    Heightmap.Biome biome = kv.Key;
                    zdo.Set(BlightedSubBosses.ZdoBiome, (int)biome);
                    bool capped = TestCap.TryGetValue(biome, out float cap);
                    var rows = new List<string>();
                    bool ok = true;
                    foreach (var it in attacks)
                    {
                        float b = BlightedSubBossBalance.BaseHit(it);
                        float f = LevelFactor(h, it);
                        // the cap is applied to the donor's hit, then the admin multiplier (BlightedSubBossBalance.Factor)
                        float want = mult * (capped && b > cap ? cap / b : 1f);
                        float got = b * f;
                        bool rowOk = Mathf.Abs(f - want) < 1e-4f && (!capped || mult > 1f || got <= cap + 0.01f);
                        ok &= rowOk;
                        rows.Add($"{it.m_dropPrefab?.name ?? it.m_shared.m_name} {b:0}->{got:0.#}{(rowOk ? "" : " WRONG")}");
                    }
                    combos++; if (ok) combosOk++;
                    Check(ok, $"damage: {d.DisplayName} in {biome}",
                        $"level {level}, multiplier {mult:0.##}, cap {(capped ? cap.ToString("0") : "none")}: {string.Join(", ", rows)} (vanilla {d.Donor} at this level: x{vanillaStar:0.##})");
                }
                Remove(sb); Remove(dn);
                yield return Sec(0.5f);
            }
            Result("INFO", "damage: summary", $"{combosOk} of {combos} Sub-Boss/biome pairs hit at their donor's vanilla damage, capped to the biome");

            // drops 1: our six prefabs carry no CharacterDrop at all
            var withDrop = BlightedSubBosses.All.Where(d => ZNetScene.instance.GetPrefab(d.Id)?.GetComponentInChildren<CharacterDrop>(true) != null).Select(d => d.DisplayName).ToList();
            Check(withDrop.Count == 0, "drops: no vanilla drop table on the six prefabs", withDrop.Count == 0 ? "0 of 6 carry a CharacterDrop" : "still on: " + string.Join(", ", withDrop));

            // drops 2: a marked vanilla summon (a wave Troll) drops nothing on death, ragdoll path included; an unmarked one does
            ResetPlayer();
            Vector3 mPos = OnGround(Origin + Fwd * 16f - Right * 12f), cPos = OnGround(Origin + Fwd * 16f + Right * 12f);
            GameObject tm = Spawn("Troll", mPos, Quaternion.identity), tc = Spawn("Troll", cPos, Quaternion.identity);
            yield return Sec(1.5f);
            Hold(tm); Hold(tc);
            if (tm == null || tc == null) { Result("FAIL", "drops: summoned Troll", "a Troll did not spawn"); }
            else
            {
                tm.GetComponent<ZNetView>().GetZDO().Set(BlightedWorldHeartAI.ZDO_Summoned, 1);
                int gm = 0, gc = 0;
                for (int i = 0; i < 5; i++) { gm += tm.GetComponent<CharacterDrop>().GenerateDropList().Count; gc += tc.GetComponent<CharacterDrop>().GenerateDropList().Count; }
                Check(gm == 0 && gc > 0, "drops: GenerateDropList refuses a summon", $"5 rolls: summoned Troll {gm} stacks, wild Troll {gc} stacks");

                var before = new HashSet<ItemDrop>(UnityEngine.Object.FindObjectsOfType<ItemDrop>());
                Kill(tm, p); Kill(tc, p);
                yield return Sec(14f);   // the ragdolls drop their loot when they fade
                var dm = DropsNear(mPos, 8f, before); var dc = DropsNear(cPos, 8f, before);
                Check(dm.Count == 0 && dc.Count > 0, "drops: a summoned Troll drops nothing when killed",
                    $"summoned {dm.Count} [{string.Join(", ", dm.Select(x => Utils.GetPrefabName(x.gameObject)))}], wild control {dc.Count} [{string.Join(", ", dc.Select(x => Utils.GetPrefabName(x.gameObject)).Distinct())}]");
                foreach (var x in dm.Concat(dc)) if (x != null) Remove(x.gameObject);
            }

            // drops 3: the Sub-Boss gear roll - at chance 1 exactly one Blighted piece of its biome, at chance 0 nothing
            var chanceEntry = BlightedConfigManager.SubBossGearDropChance;
            float savedChance = chanceEntry.Value;
            foreach (var (def, biome, chance) in new[] { (BlightedSubBosses.Gorgemaw, Heightmap.Biome.Plains, 1f), (BlightedSubBosses.Rootstalker, Heightmap.Biome.Meadows, 1f),
                                                          (BlightedSubBosses.HiveBrute, Heightmap.Biome.BlackForest, 0f) })
            {
                ResetPlayer();
                chanceEntry.Value = chance;
                Vector3 at = OnGround(Origin + Fwd * 14f);
                GameObject g = Spawn(def.Id, at, Quaternion.identity);
                yield return Sec(1.5f);
                Hold(g);
                if (g == null) { Result("FAIL", $"drops: {def.DisplayName} gear roll", "did not spawn"); continue; }
                ZDO z = g.GetComponent<ZNetView>().GetZDO();
                z.Set(BlightedSubBosses.ZdoBiome, (int)biome);
                z.Set(BlightedWorldHeartAI.ZDO_Summoned, 1);
                at = g.transform.position;
                var before = new HashSet<ItemDrop>(UnityEngine.Object.FindObjectsOfType<ItemDrop>());
                Kill(g, p);
                yield return Sec(12f);
                var got = DropsNear(at, 8f, before);
                var names = got.Select(x => Utils.GetPrefabName(x.gameObject)).ToList();
                var pool = GearPool(biome);
                bool ok = chance >= 1f ? got.Count == 1 && pool.Contains(names[0]) : got.Count == 0;
                Check(ok, $"drops: {def.DisplayName} in {biome} at chance {chance:0}",
                    $"{got.Count} drops [{string.Join(", ", names)}]; want {(chance >= 1f ? "exactly 1 from the " + pool.Count + "-piece " + biome + " pool" : "none")}");
                foreach (var x in got) if (x != null) Remove(x.gameObject);
            }
            chanceEntry.Value = savedChance;
            ResetPlayer();
        }

        // ------------------------------------------------------------------------------------------ R: the Heart resumes

        IEnumerator PhaseR()
        {
            ResetPlayer();
            Player p = Player.m_localPlayer;
            const Heightmap.Biome biome = Heightmap.Biome.BlackForest;
            int keyBiome = "blighted_biome".GetStableHashCode();
            GameObject heartPrefab = ZNetScene.instance.GetPrefab("BlightedWorldHeart");
            if (heartPrefab == null) { Result("FAIL", "resume: prefab", "BlightedWorldHeart not in ZNetScene"); yield break; }
            Vector3 at = OnGround(Origin + Fwd * 14f);
            GameObject heart = UnityEngine.Object.Instantiate(heartPrefab, at, Quaternion.identity);
            var ai = heart.GetComponent<BlightedWorldHeartAI>();
            ai.Initialize(biome);
            ZDOID hid = heart.GetComponent<ZNetView>().GetZDO().m_uid;
            Check(heart.GetComponent<ZNetView>().GetZDO().GetInt(keyBiome) == (int)biome, "resume: the biome is saved with the Heart",
                $"ZDO blighted_biome = {heart.GetComponent<ZNetView>().GetZDO().GetInt(keyBiome)} ({biome} = {(int)biome})");

            yield return WaitFor(() => ai.m_spawnedEnemies.Count > 0, 10f);
            var hit = new HitData();
            hit.m_damage.m_blunt = ai.m_health - ai.m_maxHealth * 0.45f;
            hit.m_point = at + Vector3.up; hit.SetAttacker(p);
            ai.Damage(hit);
            yield return WaitFor(() => ai.m_subBoss1 != null, 8f);
            if (ai.m_subBoss1 == null) { Result("FAIL", "resume: Sub-Boss 1 before leaving", "none spawned"); Remove(heart); yield break; }
            ZDOID sb1 = ai.m_subBoss1.GetZDOID();
            float hpBefore = ai.m_health;
            Result("INFO", "resume: before leaving", $"Heart {hpBefore:0}/{ai.m_maxHealth:0}, Sub-Boss 1 {Utils.GetPrefabName(ai.m_subBoss1.gameObject)}, wave {ai.m_spawnedEnemies.Count}");

            // leave: far enough that the zone unloads, as when everyone dies and respawns at a far spawn point
            Vector3 away = Origin;
            for (float r = 1500f; r <= 3000f && away == Origin; r += 250f)
                for (int j = 0; j < 16; j++)
                {
                    Vector3 c = Origin + Quaternion.Euler(0f, j * 22.5f, 0f) * Vector3.forward * r;
                    if (WorldGenerator.instance.GetHeight(c.x, c.z) > ZoneSystem.instance.m_waterLevel + 2f) { away = c; break; }
                }
            away.y = WorldGenerator.instance.GetHeight(away.x, away.z) + 0.5f;
            p.TeleportTo(away, Quaternion.LookRotation(Fwd), true);
            yield return null;
            yield return WaitFor(() => !p.IsTeleporting() && ZoneSystem.instance.IsActiveAreaLoaded(), 120f);
            yield return WaitFor(() => ZNetScene.instance.FindInstance(hid) == null, 60f);
            bool unloaded = ZNetScene.instance.FindInstance(hid) == null;
            Check(unloaded, "resume: the Heart unloads when nobody is near", $"{Vector3.Distance(p.transform.position, at):0} m away: instance {(unloaded ? "gone, its ZDO kept" : "STILL LOADED")}");
            if (!unloaded) { Result("NOT ASSESSED", "resume: the Heart after a reload", "it never unloaded"); yield break; }

            // come back
            p.TeleportTo(Origin + Vector3.up * 0.3f, Quaternion.LookRotation(Fwd), true);
            yield return null;
            yield return WaitFor(() => !p.IsTeleporting() && ZoneSystem.instance.IsActiveAreaLoaded(), 120f);
            ResetPlayer();
            GameObject h2 = null;
            yield return WaitFor(() => (h2 = ZNetScene.instance.FindInstance(hid)) != null, 30f);
            var ai2 = h2 != null ? h2.GetComponent<BlightedWorldHeartAI>() : null;
            if (ai2 == null) { Result("FAIL", "resume: the Heart reloads", "no instance within 30 s of coming back"); yield break; }
            Check(ai2.m_nview.IsOwner() && ai2.CurrentBiome == biome && Mathf.Abs(ai2.m_health - hpBefore) < 1f, "resume: the rebuilt Heart knows its biome and health",
                $"new instance {(ai2 != ai ? "yes" : "NO")}, owner {ai2.m_nview.IsOwner()}, biome {ai2.CurrentBiome} (want {biome}; 1.2.0 came back as None), HP {ai2.m_health:0} (was {hpBefore:0})");
            Check(ai2._subBoss1Spawned && !ai2._subBoss2Spawned, "resume: it remembers which Sub-Bosses it called",
                $"Sub-Boss 1 called {ai2._subBoss1Spawned}, Sub-Boss 2 called {ai2._subBoss2Spawned}");

            int waveBefore = ai2.m_spawnedEnemies.Count;
            yield return WaitFor(() => ai2.m_spawnedEnemies.Count > 0, 15f);
            Check(ai2.m_spawnedEnemies.Count > 0, "resume: waves start again", $"{ai2.m_spawnedEnemies.Count} wave creatures summoned by the rebuilt Heart within 15 s");
            yield return Sec(3f);
            var subsNear = UnityEngine.Object.FindObjectsOfType<Character>().Where(c => c != null && BlightedSubBosses.IsOurs(Utils.GetPrefabName(c.gameObject)) && Vector3.Distance(c.transform.position, at) < 60f).ToList();
            Check(subsNear.Count == 1 && ai2.m_subBoss1 != null && ai2.m_subBoss1.GetZDOID() == sb1, "resume: no second Sub-Boss 1",
                $"{subsNear.Count} Sub-Boss(es) within 60 m; the Heart's Sub-Boss 1 {(ai2.m_subBoss1 != null ? "is the original" + (ai2.m_subBoss1.GetZDOID() == sb1 ? "" : " NOT") : "not found")}");

            var hit2 = new HitData();
            hit2.m_damage.m_blunt = ai2.m_health - ai2.m_maxHealth * 0.15f;
            hit2.m_point = h2.transform.position + Vector3.up; hit2.SetAttacker(p);
            ai2.Damage(hit2);
            yield return WaitFor(() => ai2.m_subBoss2 != null, 8f);
            Check(ai2.m_subBoss2 != null, "resume: Sub-Boss 2 comes at its threshold", ai2.m_subBoss2 != null ? Utils.GetPrefabName(ai2.m_subBoss2.gameObject) : "none within 8 s at 15%");

            var before = new HashSet<ItemDrop>(UnityEngine.Object.FindObjectsOfType<ItemDrop>());
            var kill = new HitData();
            kill.m_damage.m_blunt = ai2.m_health + 10f;
            kill.m_point = h2.transform.position + Vector3.up; kill.SetAttacker(p);
            Vector3 hpos = h2.transform.position;
            ai2.Damage(kill);
            yield return Sec(2f);
            var drops = DropsNear(hpos, 6f, before);
            var names = drops.Select(x => Utils.GetPrefabName(x.gameObject)).ToList();
            Check(h2 == null && drops.Count == 3 && names.All(x => x.StartsWith("Blighted", StringComparison.OrdinalIgnoreCase)),
                "resume: the rebuilt Heart dies with its loot", $"heart {(h2 == null ? "destroyed" : "STILL THERE")}; {drops.Count} drops [{string.Join(", ", names)}]");
            foreach (var x in drops) if (x != null) Remove(x.gameObject);

            // clean up the fight: everything summoned near the Heart
            foreach (var c in UnityEngine.Object.FindObjectsOfType<Character>().Where(c => c != null && !c.IsPlayer() && Vector3.Distance(c.transform.position, at) < 60f
                         && c.m_nview != null && c.m_nview.GetZDO() != null && c.m_nview.GetZDO().GetInt(BlightedWorldHeartAI.ZDO_Summoned) == 1).ToList())
                Remove(c.gameObject);

            // a Heart saved by 1.2.0 (no biome in its save) reads the ground under it
            Vector3 old = OnGround(Origin + Fwd * 10f + Right * 10f);
            int hash = "BlightedWorldHeart".GetStableHashCode();
            ZDO oz = ZDOMan.instance.CreateNewZDO(old, hash);
            oz.SetPrefab(hash);
            oz.Persistent = true;
            ZNetView ov = null;
            yield return WaitFor(() => (ov = ZNetScene.instance.FindInstance(oz)) != null, 10f);
            var oai = ov != null ? ov.GetComponent<BlightedWorldHeartAI>() : null;
            Heightmap.Biome ground = WorldGenerator.instance.GetBiome(old);
            Check(oai != null && oai.CurrentBiome == ground && oz.GetInt(keyBiome) == (int)ground, "resume: a 1.2.0 Heart (no saved biome) reads the ground",
                oai != null ? $"biome {oai.CurrentBiome} (ground {ground}), now saved {oz.GetInt(keyBiome)}" : "ZNetScene did not build it within 10 s");
            if (ov != null) Remove(ov.gameObject);
            yield return Sec(1f);
            foreach (var c in UnityEngine.Object.FindObjectsOfType<Character>().Where(c => c != null && !c.IsPlayer() && c.m_nview != null && c.m_nview.GetZDO() != null
                         && c.m_nview.GetZDO().GetInt(BlightedWorldHeartAI.ZDO_Summoned) == 1).ToList())
                Remove(c.gameObject);
            ResetPlayer();
        }
    }
}
