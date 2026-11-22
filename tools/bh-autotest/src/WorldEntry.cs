// Into a single-player world without the menus, the test spot, and the player/world helpers every phase uses.
// Ported from BCAutoTest Plugin.cs (EnsureCharacter, StartWorld, InWorld, Teleport) and FACTS section 2.
using System;
using System.Collections;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using Splatform;
using UnityEngine;

namespace BHAutoTest
{
    public partial class AutoTest
    {
        /// <summary>Where the tests stand (flat, dry, open ground near the spawn) and which way they face.</summary>
        static Vector3 Origin, Fwd, Right;

        static PlayerProfile EnsureCharacter()
        {
            var profile = new PlayerProfile(CharacterFile, FileHelpers.FileSource.Local);
            if (!profile.Load())
            {
                profile = new PlayerProfile(CharacterFile, FileHelpers.FileSource.Local);
                profile.SetName("Hearttester");
            }
            profile.m_firstSpawn = false;   // no Valkyrie intro (Game.cs: m_firstSpawn queues it)
            profile.Save();
            return profile;
        }

        IEnumerator EnterWorld()
        {
            inWorld = false;
            var profile = EnsureCharacter();
            Game.SetProfile(profile.GetFilename(), profile.m_fileSource);
            SaveSystem.ClearWorldListCache(true);

            global::World world;
            if (SaveSystem.TryGetSaveByName(WorldName, SaveDataType.World, out var save) && !save.IsDeleted)
            {
                world = global::World.LoadWorld(save);
                if (world.m_dataError != global::World.SaveDataError.None)
                {
                    Result("FAIL", "load world", $"{WorldName}: data error {world.m_dataError}");
                    yield break;
                }
                Log($"world {WorldName} exists (seed {world.m_seedName})");
            }
            else
            {
                // World.GetCreateWorld with a fixed seed (World.cs:173-192): same spawn area every run.
                world = new global::World(WorldName, WorldSeed) { m_fileSource = FileHelpers.FileSource.Local };
                SaveSystem.SetSaveNumber(0u);
                world.SaveWorldFWLData(DateTime.Now);
                Log($"world {WorldName} created (seed {WorldSeed}); its locations generate on the first load");
            }

            FejdStartup.instance.m_world = world;
            ZNet.m_onlineBackend = OnlineBackendType.Steamworks;
            ZNet.SetServer(true, false, false, world.m_name, "", world);
            ZNet.ResetServerHost();
            Log($"loading {world.m_name} with character {profile.GetName()}");
            FejdStartup.instance.LoadMainScene();

            float t0 = Time.realtimeSinceStartup;
            yield return WaitFor(() => Player.m_localPlayer != null && ZoneSystem.instance != null && ZoneSystem.instance.IsActiveAreaLoaded()
                                       && !Player.m_localPlayer.IsTeleporting(), 900f);
            if (!waitOk)
            {
                Result("FAIL", "spawn", "no player in a loaded world within 900 s");
                yield break;
            }
            Result("PASS", "spawn", $"player in the world after {Time.realtimeSinceStartup - t0:0} s; ZNet server {ZNet.instance.IsServer()}");
            yield return Sec(8f);

            Player p = Player.m_localPlayer;
            p.SetGodMode(true);     // the test character never dies...
            p.SetGhostMode(true);   // ...and the test creatures leave it alone
            Check(ZNet.instance.IsServer(), "host is the server", "single player: the Heart's owner logic runs in this process");

            yield return FindSpot();
            inWorld = Player.m_localPlayer != null;
        }

        /// <summary>Flat, dry, open ground near the spawn: nothing solid within 7 m, the ground within 1.2 m over a 6 m
        /// circle, at least 1 m above the sea. Then the player stands there facing <see cref="Fwd"/>.</summary>
        IEnumerator FindSpot()
        {
            Player p = Player.m_localPlayer;
            Vector3 start = p.transform.position;
            float water = ZoneSystem.instance.m_waterLevel;
            int solid = LayerMask.GetMask("Default", "static_solid", "Default_small", "piece", "vehicle");
            Vector3 best = Vector3.zero;
            bool found = false;
            foreach (float r in new[] { 20f, 30f, 45f, 15f, 60f })
            {
                for (int k = 0; k < 16 && !found; k++)
                {
                    float a = k * Mathf.PI / 8f;
                    var c = start + new Vector3(Mathf.Cos(a), 0f, Mathf.Sin(a)) * r;
                    float h0 = Ground(c);
                    if (h0 < water + 1f) continue;
                    float lo = h0, hi = h0;
                    bool dry = true;
                    for (int j = 0; j < 8; j++)
                    {
                        float b = j * Mathf.PI / 4f;
                        float h = Ground(c + new Vector3(Mathf.Cos(b), 0f, Mathf.Sin(b)) * 6f);
                        if (h < water + 1f) { dry = false; break; }
                        lo = Mathf.Min(lo, h); hi = Mathf.Max(hi, h);
                    }
                    if (!dry || hi - lo > 1.2f) continue;
                    c.y = h0;
                    if (Physics.OverlapSphere(c + Vector3.up * 2f, 7f, solid, QueryTriggerInteraction.Ignore).Length > 0) continue;
                    best = c;
                    found = true;
                }
                if (found) break;
            }
            if (!found)
            {
                best = start;
                Result("WARN", "test spot", $"no flat open spot within 60 m of the spawn {V(start)}; testing at the spawn");
            }

            Fwd = best - start;
            Fwd.y = 0f;
            Fwd = Fwd.sqrMagnitude > 0.01f ? Fwd.normalized : Vector3.forward;
            Right = Vector3.Cross(Vector3.up, Fwd).normalized;
            if (found)
            {
                if (!p.TeleportTo(best + Vector3.up * 0.3f, Quaternion.LookRotation(Fwd), false))
                {
                    yield return Sec(2.5f);
                    p.TeleportTo(best + Vector3.up * 0.3f, Quaternion.LookRotation(Fwd), false);
                }
                yield return null;
                yield return WaitFor(() => !p.IsTeleporting() && ZoneSystem.instance.IsActiveAreaLoaded(), 120f);
                yield return Sec(3f);
            }
            Origin = p.transform.position;
            Face(Fwd);
            Result(found ? "PASS" : "WARN", "test spot", $"at {V(Origin)}, {Vector3.Distance(start, Origin):0} m from the spawn, facing {V(Fwd)}");
        }

        /// <summary>For the creature shots: open, flat ground with nothing solid (tree, rock, building) within 22 m. Candidates
        /// up to 300 m away are probed only once their zone is LOADED (run 2: an unloaded spot has no colliders, so it looked
        /// open and was a forest). The tests then run there (Origin moves). Keeps the old spot if none is found.</summary>
        IEnumerator OpenGround()
        {
            Player p = Player.m_localPlayer;
            Vector3 start = Origin;
            float water = ZoneSystem.instance.m_waterLevel;
            int skip = LayerMask.GetMask("terrain", "character", "character_net", "character_ghost", "character_noenv", "item", "Water", "hitbox", "ragdoll", "smoke", "viewblock");
            bool found = false; Vector3 best = start; int probed = 0, blocked = 0, leastSolid = int.MaxValue; Vector3 least = start;
            // candidates ranked by their forest factor (the lowest of 9 samples over 15 m: vegetation with m_inForest grows only
            // inside its band, so a high factor is a clearing); dry ground only. Probed in that order once loaded.
            var cands = new List<(Vector3 c, float ff)>();
            // a 100 m grid out to 2 km from the world generator alone (nothing has to be loaded): dry ground in the Meadows or
            // the Plains (open biomes, no swamp gloom or mist), ranked by forest factor (run 6: within 560 m of this spawn every
            // candidate was forest)
            for (float gx = -2000f; gx <= 2000f; gx += 100f)
                for (float gz = -2000f; gz <= 2000f; gz += 100f)
                {
                    var c = start + new Vector3(gx, 0f, gz);
                    Heightmap.Biome bio = WorldGenerator.instance.GetBiome(c);
                    if (bio != Heightmap.Biome.Meadows && bio != Heightmap.Biome.Plains) continue;
                    if (WorldGenerator.instance.GetHeight(c.x, c.z) < water + 2f) continue;
                    float ff = WorldGenerator.GetForestFactor(c);
                    for (int j = 0; j < 8; j++) ff = Mathf.Min(ff, WorldGenerator.GetForestFactor(c + Quaternion.Euler(0f, j * 45f, 0f) * Vector3.forward * 15f));
                    cands.Add((c, ff));
                }
            cands.Sort((x, y) => y.ff.CompareTo(x.ff));
            foreach (var (c0, ff) in cands.Take(16))
            {
                Vector3 c = c0;
                if (Vector3.Distance(p.transform.position, c) > 40f)
                {
                    p.TeleportTo(new Vector3(c.x, Ground(c) + 0.3f, c.z), Quaternion.LookRotation(Fwd), false);
                    yield return null;
                    yield return WaitFor(() => !p.IsTeleporting() && ZoneSystem.instance.IsActiveAreaLoaded(), 60f);
                    yield return Sec(4f);      // let ZNetScene instantiate the zone's objects before probing
                }
                probed++;
                float h0 = Ground(c);
                float lo = h0, hi = h0; bool dry = true;
                for (int j = 0; j < 12; j++)
                {
                    float b2 = j * Mathf.PI / 6f;
                    float h = Ground(c + new Vector3(Mathf.Cos(b2), 0f, Mathf.Sin(b2)) * 12f);
                    if (h < water + 1f) { dry = false; break; }
                    lo = Mathf.Min(lo, h); hi = Mathf.Max(hi, h);
                }
                if (!dry || hi - lo > 4f) continue;
                c.y = h0;
                var hits = Physics.OverlapSphere(c + Vector3.up * 3f, 16f, ~skip, QueryTriggerInteraction.Ignore)
                    .Where(col => col.attachedRigidbody == null || col.attachedRigidbody.isKinematic).ToList();
                int solid = hits.Count;
                Log($"open ground candidate {V(c)} forest {ff:0.00}: {solid} solids [{string.Join(", ", hits.Take(4).Select(h => h.name + "@" + LayerMask.LayerToName(h.gameObject.layer)))}]");
                if (solid < leastSolid) { leastSolid = solid; least = c; }
                if (solid > 0) { blocked++; continue; }
                best = c; found = true;
                Log($"open ground: forest factor {ff:0.00} at {V(c)}");
                break;
            }
            if (!found)
            {
                best = leastSolid < int.MaxValue ? least : start;
                Result("WARN", "open ground for the shots", $"none of {probed} loaded candidates (2 km grid, Meadows/Plains) is fully open ({blocked} had solids within 16 m); " +
                                                            $"shooting at the least blocked ({(leastSolid < int.MaxValue ? leastSolid.ToString() : "none")} solids) {V(best)}");
            }
            p.TeleportTo(best + Vector3.up * 0.3f, Quaternion.LookRotation(Fwd), false);
            yield return null;
            yield return WaitFor(() => !p.IsTeleporting() && ZoneSystem.instance.IsActiveAreaLoaded(), 120f);
            yield return Sec(3f);
            Origin = p.transform.position;
            Face(Fwd);
            if (found) Result("INFO", "open ground for the shots", $"at {V(Origin)}, {Vector3.Distance(start, Origin):0} m from the test spot; {probed} loaded candidates probed, nothing solid within 16 m");
        }

        // ------------------------------------------------------------------------------------------ helpers

        internal static string V(Vector3 v) => $"({v.x.ToString("0.0", IC)}, {v.y.ToString("0.0", IC)}, {v.z.ToString("0.0", IC)})";

        static float Ground(Vector3 p) => ZoneSystem.instance.GetGroundHeight(p);

        static Vector3 OnGround(Vector3 p) => new Vector3(p.x, Ground(p), p.z);

        /// <summary>Turns the player's look (yaw + pitch: the eye and the camera follow them, Player.UpdateEyeRotation and
        /// GameCamera read m_eye) and body toward <paramref name="dir"/>.</summary>
        static void Face(Vector3 dir)
        {
            Player p = Player.m_localPlayer;
            if (p == null || dir.sqrMagnitude < 1e-6f) return;
            dir.Normalize();
            var flat = new Vector3(dir.x, 0f, dir.z);
            if (flat.sqrMagnitude < 1e-6f) flat = p.transform.forward;
            p.m_lookYaw = Quaternion.LookRotation(flat.normalized);
            p.m_lookPitch = Mathf.Clamp(-Mathf.Asin(Mathf.Clamp(dir.y, -1f, 1f)) * Mathf.Rad2Deg, -89f, 89f);
            p.SetLookDir(dir);
            p.transform.rotation = Quaternion.LookRotation(flat.normalized);
        }

        /// <summary>Aims the crosshair ray (CastPipeline.Aim: from the camera along its forward) at a point: the direction
        /// from the CAMERA, which itself moves with the look, so call it again a frame later.</summary>
        static void AimAt(Vector3 point)
        {
            Player p = Player.m_localPlayer;
            if (p == null) return;
            Vector3 from = GameCamera.instance != null ? GameCamera.instance.transform.position : p.m_eye.position;
            Face(point - from);
        }

        static IEnumerator AimSettled(Func<Vector3> point)
        {
            for (int i = 0; i < 4; i++)
            {
                AimAt(point());
                yield return null;
                yield return null;
            }
        }

        /// <summary>Back to the test origin (spells such as Uruz and Ehwaz move the caster), facing forward.</summary>
        static void ResetPlayer()
        {
            Player p = Player.m_localPlayer;
            if (p == null) return;
            if (Vector3.Distance(p.transform.position, Origin) > 0.75f)
            {
                p.transform.position = Origin;
                if (p.m_body != null)
                {
                    p.m_body.position = Origin;
                    p.m_body.velocity = Vector3.zero;
                }
            }
            Face(Fwd);
        }

        static GameObject Spawn(string prefabName, Vector3 pos, Quaternion rot)
        {
            GameObject prefab = ZNetScene.instance != null ? ZNetScene.instance.GetPrefab(prefabName) : null;
            if (prefab == null) return null;
            return UnityEngine.Object.Instantiate(prefab, pos, rot);
        }

        static void Remove(GameObject go)
        {
            if (go == null) return;
            var nv = go.GetComponent<ZNetView>();
            if (nv != null && nv.IsValid())
            {
                if (!nv.IsOwner()) nv.ClaimOwnership();
                ZNetScene.instance.Destroy(go);
            }
            else UnityEngine.Object.Destroy(go);
        }

        /// <summary>A piece placed as Player.PlacePiece leaves it: instantiated, creator set (FACTS section 4).</summary>
        static GameObject PlacePiece(string prefabName, Vector3 pos, Quaternion rot)
        {
            GameObject go = Spawn(prefabName, OnGround(pos), rot);
            if (go == null) return null;
            Piece piece = go.GetComponent<Piece>();
            Player p = Player.m_localPlayer;
            try
            {
                if (piece != null && p != null)
                    piece.SetCreator(p.GetPlayerID(), PlatformManager.DistributionPlatform.LocalUser.PlatformUserID);
            }
            catch (Exception e) { Log("SetCreator: " + e.Message); }
            return go;
        }

        static ItemDrop.ItemData Give(string prefab, int amount)
        {
            Player p = Player.m_localPlayer;
            return p.GetInventory().AddItem(prefab, amount, 1, 0, p.GetPlayerID(), p.GetPlayerName(), false);
        }

        static ZDO PlayerZdo => Player.m_localPlayer != null && Player.m_localPlayer.m_nview != null && Player.m_localPlayer.m_nview.IsValid()
            ? Player.m_localPlayer.m_nview.GetZDO() : null;
    }
}
