// Phases A (boot), S (the six Sub-Bosses' art), F (faction), H (the Heart end to end).
// The Runic playbook (owner, 2026-11-22): every check calls the mod's own code (publicized), every result is PASS / FAIL /
// WARN / INFO with the numbers behind it, and the art gets screenshots through the real game camera.
using System;
using System.Collections;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using System.Text.RegularExpressions;
using BepInEx;
using BlightedHeart;
using UnityEngine;

namespace BHAutoTest
{
    public partial class AutoTest
    {
        // ------------------------------------------------------------------------------------------ A: boot

        IEnumerator PhaseA()
        {
            string logPath = Path.Combine(Paths.BepInExRootPath, "LogOutput.log");
            List<string> lines = ReadShared(logPath);
            string loaded = lines.FirstOrDefault(l => l.Contains("BlightedWorldHeart v") && l.Contains(" loaded."));
            Check(loaded != null && loaded.Contains("v" + BlightedHeartPlugin.PluginVersion), "BlightedHeart load line", loaded ?? $"no 'BlightedWorldHeart v... loaded.' line in {logPath} ({lines.Count} lines)");

            string index = lines.FirstOrDefault(l => l.Contains("Sub-Boss kit index:"));
            Result(index != null ? "INFO" : "FAIL", "kit mesh index", index != null ? Short(index) : "no 'Sub-Boss kit index' line: BlightedSubBossKit never ran (headless?)");

            var rx = new Regex(@"Sub-Boss kit (\S+): (\d+) parts built, (\d+) failed, of (\d+)\b");
            foreach (BlightedSubBosses.Def d in BlightedSubBosses.All)
            {
                bool reg = BlightedSubBosses.Registered.Contains(d.Id);
                // at the main menu there is no ZNetScene yet: Jotunn's registry is what ZNetScene gets in the world (phase S spawns from ZNetScene)
                GameObject prefab = Jotunn.Managers.PrefabManager.Instance.GetPrefab(d.Id);
                Match m = lines.Select(l => rx.Match(l)).FirstOrDefault(x => x.Success && x.Groups[1].Value == d.Id);
                int built = m != null ? int.Parse(m.Groups[2].Value) : -1, failed = m != null ? int.Parse(m.Groups[3].Value) : -1, of = m != null ? int.Parse(m.Groups[4].Value) : -1;
                var warnings = lines.Where(l => l.Contains("[BlightedHeart] " + d.Id + "/")).ToList();
                Check(reg && prefab != null && m != null && failed == 0 && built == of && of > 0, $"{d.DisplayName} registered, kit built",
                    $"registered {reg}, in Jotunn's prefab registry {prefab != null}, kit {(m != null ? $"{built} built, {failed} failed, of {of}" : "NO kit line")}" +
                    (warnings.Count > 0 ? "; " + string.Join(" || ", warnings.Take(4).Select(Short)) : ""));
            }

            var lost = lines.Where(l => l.Contains("Feature Lost")).ToList();
            var bad = lines.Where(l => l.Contains("[Error") || l.Contains("[Fatal") || l.Contains("Exception")).ToList();
            var badMod = bad.Where(ErrorWatch.MentionsMod).ToList();
            if (badMod.Count > 0) Result("FAIL", "boot log: BlightedHeart errors", $"{badMod.Count}: " + string.Join(" || ", badMod.Take(4).Select(Short)));
            else Result(bad.Count == 0 ? "PASS" : "INFO", "boot log: errors so far", bad.Count == 0 ? "none" : $"{bad.Count} other: " + string.Join(" || ", bad.Take(3).Select(Short)));
            yield break;
        }

        static List<string> ReadShared(string path)
        {
            try
            {
                using (var fs = new FileStream(path, FileMode.Open, FileAccess.Read, FileShare.ReadWrite | FileShare.Delete))
                using (var r = new StreamReader(fs))
                    return r.ReadToEnd().Split('\n').Select(l => l.TrimEnd('\r')).ToList();
            }
            catch (Exception e)
            {
                Log($"could not read {path}: {e.Message}");
                return new List<string>();
            }
        }

        // ------------------------------------------------------------------------------------------ shared art checks

        static Heightmap.Biome FirstBiome(BlightedSubBosses.Def d) =>
            BlightedSubBosses.ByBiome.Where(kv => kv.Value.Contains(d)).Select(kv => kv.Key).DefaultIfEmpty(Heightmap.Biome.Meadows).First();

        static Transform FindDeep(Transform root, string name)
        {
            if (root == null) return null;
            foreach (Transform t in root.GetComponentsInChildren<Transform>(true))
                if (t.name == name) return t;
            return null;
        }

        static bool IsPart(Renderer r) => r.name.StartsWith("BSB_", StringComparison.Ordinal);

        /// <summary>The donor's own body: the combined bounds of its enabled skinned renderers (ours excluded).</summary>
        static Bounds BodyBounds(GameObject go)
        {
            Bounds b = new Bounds(go.transform.position + Vector3.up, Vector3.zero);
            bool any = false;
            foreach (SkinnedMeshRenderer r in go.GetComponentsInChildren<SkinnedMeshRenderer>(false))
            {
                if (!r.enabled || IsPart(r)) continue;
                if (!any) { b = r.bounds; any = true; } else b.Encapsulate(r.bounds);
            }
            return b;
        }

        /// <summary>Every art check on one live Sub-Boss instance. Returns the number of parts found on their bones.</summary>
        static int CheckArt(GameObject go, BlightedSubBosses.Def d, string tag, float expectScale)
        {
            BlightedSubBossKit.Kit kit = BlightedSubBossKit.Load(d.Id);
            if (kit == null) { Result("FAIL", $"{tag}: kit data", "no embedded kit JSON"); return 0; }

            // --- the clone itself: name, not a boss, never a pet or a breeder, our look component
            Character ch = go.GetComponent<Character>();
            var tame = go.GetComponentsInChildren<Tameable>(true).Length + go.GetComponentsInChildren<Procreation>(true).Length + go.GetComponentsInChildren<Growup>(true).Length;
            Check(ch != null && ch.m_name == d.DisplayName && !ch.m_boss && tame == 0 && go.GetComponent<BlightedSubBossLook>() != null,
                $"{tag}: the clone", $"name '{ch?.m_name}', boss {ch?.m_boss}, taming/breeding components {tame}, look {(go.GetComponent<BlightedSubBossLook>() != null)}, " +
                $"scale {go.transform.localScale.x:0.00} (expected {expectScale:0.00})");

            // --- every part on its bone, with a mesh, enabled, at the compiled transform (TRS parts)
            var bad = new List<string>();
            int ok = 0, trs = 0, baked = 0, skinnedOk = 0;
            var all = go.GetComponentsInChildren<Transform>(true).Where(t => t.name.StartsWith("BSB_", StringComparison.Ordinal)).ToList();
            foreach (BlightedSubBossKit.Part p in kit.parts)
            {
                Transform t = all.FirstOrDefault(x => x.name == "BSB_" + p.name);
                if (t == null) { bad.Add(p.name + " missing"); continue; }
                if (t.parent == null || t.parent.name != p.bone) { bad.Add($"{p.name} on '{t.parent?.name}' not {p.bone}"); continue; }
                MeshFilter mf = t.GetComponent<MeshFilter>();
                SkinnedMeshRenderer smr = t.GetComponent<SkinnedMeshRenderer>();
                Renderer mr = smr != null ? (Renderer)smr : t.GetComponent<MeshRenderer>();
                Mesh mesh = smr != null ? smr.sharedMesh : mf != null ? mf.sharedMesh : null;
                if (mesh == null || mesh.vertexCount == 0) { bad.Add(p.name + " no mesh"); continue; }
                if (mr == null || !mr.enabled || !t.gameObject.activeInHierarchy) { bad.Add(p.name + " not drawn"); continue; }
                if (mr.sharedMaterials.Length != mesh.subMeshCount) { bad.Add($"{p.name}: {mr.sharedMaterials.Length} materials for {mesh.subMeshCount} submeshes"); continue; }
                bool wantSkin = p.skin != null && p.trs == null;
                if (wantSkin != (smr != null)) { bad.Add($"{p.name}: skinned {smr != null}, expected {wantSkin}"); continue; }
                if (smr != null)
                {
                    skinnedOk++;
                    if (smr.bones.Length != p.skin.bones.Length || smr.bones.Any(x => x == null) || mesh.boneWeights.Length != mesh.vertexCount)
                    { bad.Add($"{p.name}: {smr.bones.Length} bones (want {p.skin.bones.Length}), {mesh.boneWeights.Length} weights for {mesh.vertexCount} verts"); continue; }
                }
                if (p.trs != null)
                {
                    trs++;
                    var lp = new Vector3(p.trs.p[0], p.trs.p[1], p.trs.p[2]);
                    var lr = new Quaternion(p.trs.r[0], p.trs.r[1], p.trs.r[2], p.trs.r[3]);
                    var ls = new Vector3(p.trs.s[0], p.trs.s[1], p.trs.s[2]);
                    float dp = (t.localPosition - lp).magnitude, dr = Quaternion.Angle(t.localRotation, lr), ds = (t.localScale - ls).magnitude / Mathf.Max(ls.magnitude, 1e-6f);
                    if (dp > 1e-4f * Mathf.Max(1f, lp.magnitude) || dr > 0.05f || ds > 1e-3f) { bad.Add($"{p.name}: offset {dp:0.00000}, angle {dr:0.00}, scale {ds:0.0000}"); continue; }
                }
                else baked++;
                ok++;
            }
            int extra = all.Count - kit.parts.Count;
            Check(bad.Count == 0 && ok == kit.parts.Count && extra == 0, $"{tag}: parts on their bones",
                $"{ok} of {kit.parts.Count} ({trs} placed, {baked} baked, {skinnedOk} skinned on the donor's bones), {all.Count} BSB objects on the instance" + (bad.Count > 0 ? "; " + string.Join("; ", bad.Take(8)) : ""));

            // --- the donor renderers the kit hides stay hidden
            var shown = new List<string>();
            if (kit.hide_renderers != null)
                foreach (Renderer r in go.GetComponentsInChildren<Renderer>(true))
                    if (Array.IndexOf(kit.hide_renderers, r.gameObject.name) >= 0 && r.enabled) shown.Add(r.name);
            Check(shown.Count == 0, $"{tag}: donor parts hidden", $"{kit.hide_renderers?.Length ?? 0} to hide [{string.Join(", ", kit.hide_renderers ?? new string[0])}]" + (shown.Count > 0 ? "; STILL SHOWN " + string.Join(", ", shown) : ""));

            // --- no broken shader anywhere (hot pink = null material / InternalErrorShader / unsupported)
            var broken = new List<string>();
            int mats = 0;
            foreach (Renderer r in go.GetComponentsInChildren<Renderer>(false))
            {
                if (!r.enabled || r is ParticleSystemRenderer) continue;
                foreach (Material m in r.sharedMaterials)
                {
                    mats++;
                    Shader sh = m != null ? m.shader : null;
                    if (m == null || sh == null || sh.name == "Hidden/InternalErrorShader" || !sh.isSupported)
                        broken.Add($"{r.name}: {(m != null ? m.name : "null material")} / {(sh != null ? sh.name : "null shader")}");
                }
            }
            Check(broken.Count == 0 && mats > 0, $"{tag}: no broken shader", $"{mats} material slots on enabled renderers" + (broken.Count > 0 ? "; " + string.Join("; ", broken.Take(8)) : ""));

            // --- the parts sit on the body: each part's centre inside the body's bounds grown by half their size
            Bounds body = BodyBounds(go);
            Bounds grown = body; grown.Expand(body.size * 0.5f);
            var outside = new List<string>();
            int parts = 0;
            foreach (Renderer r in go.GetComponentsInChildren<Renderer>(false))
            {
                if (!IsPart(r) || r is ParticleSystemRenderer) continue;
                parts++;
                // a part is ON the body when its bounds touch the body box grown by 50% (a tall branch rises far above the
                // body but is rooted in it; a part on the wrong bone frame floats metres away)
                if (!grown.Intersects(r.bounds)) outside.Add($"{r.name.Substring(4)} {Vector3.Distance(r.bounds.center, body.center):0.00} m off");
            }
            Check(outside.Count == 0 && parts > 0, $"{tag}: parts on the body",
                $"{parts - outside.Count} of {parts} parts touch the body box ({V(body.size)} m) + 50%" + (outside.Count > 0 ? "; OUTSIDE " + string.Join(", ", outside.Take(8)) : ""));
            return ok;
        }

        /// <summary>The biome tint, as the approved "colour only" panel: every _Color on the instance = the PREFAB's own _Color
        /// (the shared Sub-Boss or vanilla material) x the Heart's biome colour in linear space.</summary>
        static void CheckTint(GameObject go, Heightmap.Biome biome, string tag)
        {
            Color tint = BlightedWorldHeartAI.GetBiomeColor(biome);
            GameObject prefab = ZNetScene.instance.GetPrefab(Utils.GetPrefabName(go));
            var own = new Dictionary<string, Vector4>();
            foreach (Renderer r in prefab.GetComponentsInChildren<Renderer>(true))
            {
                Material[] ms = r.sharedMaterials;
                for (int i = 0; i < ms.Length; i++)
                    if (ms[i] != null && ms[i].HasProperty("_Color")) own[Rel(prefab.transform, r.transform) + "#" + i] = ms[i].GetVector("_Color");
            }
            int withColor = 0, tinted = 0;
            var off = new List<string>();
            foreach (Renderer r in go.GetComponentsInChildren<Renderer>(true))
            {
                if (r is ParticleSystemRenderer) continue;
                Material[] ms = r.sharedMaterials;
                for (int i = 0; i < ms.Length; i++)
                {
                    Material m = ms[i];
                    if (m == null || !m.HasProperty("_Color")) continue;
                    if (!own.TryGetValue(Rel(go.transform, r.transform) + "#" + i, out Vector4 o)) continue;
                    withColor++;
                    Vector4 want = BlightedSubBossLook.Tinted(o, tint), got = m.GetVector("_Color");
                    if ((want - got).magnitude < 0.003f) tinted++;
                    else if (off.Count < 6) off.Add($"{r.name}/{m.name} {got} want {want}");
                }
            }
            var look = go.GetComponent<BlightedSubBossLook>();
            Check(look != null && look._applied && tinted == withColor && withColor > 0, $"{tag}: {biome} tint",
                $"{tinted} of {withColor} _Color slots = own colour x {tint} (linear) (look applied {look?._applied})" + (off.Count > 0 ? "; OFF " + string.Join("; ", off) : ""));
        }

        static string Rel(Transform root, Transform t)
        {
            var parts = new List<string>();
            for (Transform x = t; x != null && x != root; x = x.parent) parts.Add(x.name);
            parts.Reverse();
            return string.Join("/", parts);
        }

        /// <summary>Stage 3b: the donor body on the instance draws OUR repainted albedo + emission (not the vanilla texture).</summary>
        static void CheckRepaint(GameObject go, BlightedSubBosses.Def d, string tag)
        {
            BlightedSubBossRepaint.Albedo.TryGetValue(d.Id, out Texture2D alb);
            BlightedSubBossRepaint.Emission.TryGetValue(d.Id, out Texture2D em);
            int users = 0;
            foreach (Renderer r in go.GetComponentsInChildren<Renderer>(true))
                foreach (Material m in r.sharedMaterials)
                    if (m != null && alb != null && m.HasProperty("_MainTex") && m.GetTexture("_MainTex") == alb
                        && (!m.HasProperty("_EmissionMap") || m.GetTexture("_EmissionMap") == em)) users++;
            BlightedSubBossRepaint.Report.TryGetValue(d.Id, out string rep);
            Check(alb != null && users > 0, $"{tag}: body repainted", $"{users} body material slot(s) draw our albedo {(alb != null ? alb.name + " " + alb.width + "px" : "NONE")}; {rep}");
            if (alb != null) DumpTex(alb, d.Id + "_albedo");
            if (em != null) DumpTex(em, d.Id + "_emission");
        }

        static void DumpTex(Texture t, string name)
        {
            try
            {
                System.Type ic = System.Type.GetType("UnityEngine.ImageConversion, UnityEngine.ImageConversionModule");
                var enc = ic?.GetMethod("EncodeToPNG", new[] { typeof(Texture2D) });
                if (enc == null) return;
                string dir = Path.Combine(Img, "tex"); Directory.CreateDirectory(dir);
                Color32[] px = BlightedSubBossMaterials.ReadBack(t, t.width, t.height);
                var tmp = new Texture2D(t.width, t.height, TextureFormat.RGBA32, false);
                tmp.SetPixels32(px); tmp.Apply();
                File.WriteAllBytes(Path.Combine(dir, name + ".png"), (byte[])enc.Invoke(null, new object[] { tmp }));
                UnityEngine.Object.Destroy(tmp);
            }
            catch (System.Exception e) { Log("tex dump " + name + ": " + e.Message); }
        }

        /// <summary>Stage 3: every part slot carries OUR shared material for its look key (not the vanilla one), and the crust's
        /// vanilla glow is off. Call before the tint (the tint instances the materials).</summary>
        static void CheckMaterials(GameObject go, BlightedSubBosses.Def d, string tag)
        {
            BlightedSubBossKit.Kit kit = BlightedSubBossKit.Load(d.Id);
            int slots = 0, ours = 0, glowing = 0;
            var bad = new List<string>();
            var shaders = new HashSet<string>();
            foreach (BlightedSubBossKit.Part p in kit.parts)
            {
                Transform t = FindDeep(go.transform, "BSB_" + p.name);
                Renderer mr = t != null ? (t.GetComponent<SkinnedMeshRenderer>() != null ? (Renderer)t.GetComponent<SkinnedMeshRenderer>() : t.GetComponent<MeshRenderer>()) : null;
                if (mr == null) continue;
                Material[] ms = mr.sharedMaterials;
                for (int i = 0; i < ms.Length; i++)
                {
                    slots++;
                    string want = p.looks != null && i < p.looks.Length ? BlightedSubBossMaterials.KeyOf(p.looks[i]) : null;
                    if (ms[i] != null && ms[i].name.StartsWith("BSB_") && want != null && ms[i].name.EndsWith("_" + want)) ours++;
                    else if (bad.Count < 6) bad.Add($"{p.name}[{i}] {(ms[i] != null ? ms[i].name : "null")} (look {want})");
                    if (ms[i] != null) shaders.Add(ms[i].shader.name);
                    if (ms[i] != null && want != null && want.Contains("TheHive_Mat") && ms[i].HasProperty("_EmissionColor") && ((Vector4)ms[i].GetVector("_EmissionColor")).magnitude > 1.001f) glowing++;
                }
            }
            Check(ours == slots && slots > 0 && glowing == 0, $"{tag}: our shared materials on every part slot",
                $"{ours} of {slots} slots; crust slots still glowing {glowing}; shaders [{string.Join(", ", shaders)}]" + (bad.Count > 0 ? "; NOT OURS " + string.Join("; ", bad) : ""));
        }

        /// <summary>Front, three-quarter, side and back of a creature through the game's own camera (GameCamera paused),
        /// framed on its body bounds; the tester's body hidden.</summary>
        IEnumerator CreatureShots(GameObject go, string name)
        {
            GameCamera gc = GameCamera.instance;
            Camera cam = gc != null ? gc.m_camera : null;
            if (cam == null || go == null) { Log("creature shots: no game camera or creature"); yield break; }
            Player p = Player.m_localPlayer;
            bool vis = p != null && p.m_visual != null && p.m_visual.activeSelf;
            if (vis) p.m_visual.SetActive(false);
            var hidden = new List<GameObject>();
            foreach (Raven rv in UnityEngine.Object.FindObjectsOfType<Raven>()) if (rv.gameObject.activeSelf) { rv.gameObject.SetActive(false); hidden.Add(rv.gameObject); }
            // only the grass root: ClutterSystem's own GameObject carries other game systems (run 2 froze the camera)
            GameObject grass = ClutterSystem.instance != null ? ClutterSystem.instance.m_grassRoot : null;
            if (grass != null && grass.activeSelf) { grass.SetActive(false); hidden.Add(grass); }
            float fov = cam.fieldOfView;
            // the camera always on the sun's side (Runic's ArmorShots): the creature turns, not the light
            Vector3 sunDir = RenderSettings.sun != null ? RenderSettings.sun.transform.forward : Vector3.down;
            var toSun = new Vector3(-sunDir.x, 0f, -sunDir.z);
            if (toSun.sqrMagnitude < 1e-4f) toSun = -Fwd;
            toSun.Normalize();
            foreach (var (view, yaw) in new[] { ("front", 0f), ("threequarter", 40f), ("side", 90f), ("back", 180f) })
            {
                if (go == null) break;
                Vector3 face = Quaternion.Euler(0f, -yaw, 0f) * toSun;
                Character fc = go.GetComponent<Character>();
                if (fc != null) { fc.SetLookDir(face); fc.m_moveDir = Vector3.zero; }   // Character.UpdateRotation turns the body to its look dir
                go.transform.rotation = Quaternion.LookRotation(face);
                yield return Sec(0.6f);
                if (fc != null) fc.SetLookDir(face);
                go.transform.rotation = Quaternion.LookRotation(face);
                Bounds b = BodyBounds(go);
                float dist = Mathf.Max(b.extents.magnitude * 2.4f, 2.5f);
                Vector3 dir = toSun;
                gc.enabled = false;
                try
                {
                    Vector3 at = b.center;
                    Vector3 from = at + dir * dist + Vector3.up * (b.extents.y * 0.35f);
                    cam.transform.position = from;
                    cam.transform.rotation = Quaternion.LookRotation(at - from);
                    cam.fieldOfView = 50f;
                }
                catch (Exception e) { Log("creature shots: " + e.Message); }
                yield return Shot($"{name}-{view}", null);
                cam.fieldOfView = fov;
                gc.enabled = true;
            }
            // in motion: a few steps toward the camera's side (the skinned parts must follow the walk cycle), shot mid-stride
            if (go != null && go.GetComponent<Character>() is Character wc)
            {
                Vector3 side = Vector3.Cross(Vector3.up, toSun).normalized;
                wc.SetLookDir(side); go.transform.rotation = Quaternion.LookRotation(side);
                gc.enabled = false;
                for (int f = 0; f < 45; f++)
                {
                    wc.SetMoveDir(side); wc.SetWalk(true);
                    Bounds b = BodyBounds(go);
                    Vector3 from = b.center + toSun * Mathf.Max(b.extents.magnitude * 2.4f, 2.5f) + Vector3.up * (b.extents.y * 0.35f);
                    cam.transform.position = from; cam.transform.rotation = Quaternion.LookRotation(b.center - from); cam.fieldOfView = 50f;
                    yield return null;
                }
                yield return Shot($"{name}-walk", null);
                wc.SetMoveDir(Vector3.zero);
                cam.fieldOfView = fov;
                gc.enabled = true;
            }
            if (vis && p != null) p.m_visual.SetActive(true);
            foreach (GameObject h in hidden) if (h != null) h.SetActive(true);
        }

        static void MorningLight(bool on)
        {
            EnvMan env = EnvMan.instance;
            if (env == null) return;
            env.m_debugTimeOfDay = on;
            env.m_debugTime = 0.37f;    // Runic's shot light: morning sun, not blown out
            env.m_debugEnv = on ? "Clear" : "";
        }

        // ------------------------------------------------------------------------------------------ S: the six Sub-Bosses

        IEnumerator PhaseS()
        {
            yield return OpenGround();
            ResetPlayer();
            MorningLight(true);
            yield return Sec(3f);
            foreach (BlightedSubBosses.Def d in BlightedSubBosses.All)
            {
                string tag = d.DisplayName;
                GameObject prefab = ZNetScene.instance.GetPrefab(d.Id);
                if (prefab == null) { Result("FAIL", $"{tag}: spawn", "no prefab in ZNetScene"); continue; }
                Vector3 at = OnGround(Origin + Fwd * 9f);
                GameObject go = UnityEngine.Object.Instantiate(prefab, at, Quaternion.LookRotation(-Fwd));
                yield return Sec(1.5f);
                if (go == null) { Result("FAIL", $"{tag}: spawn", "the instance is gone after 1.5 s"); continue; }
                BaseAI ai = go.GetComponent<BaseAI>();
                if (ai != null) ai.enabled = false;   // hold the pose for the shots (the Animator keeps idling)
                go.transform.rotation = Quaternion.LookRotation(-Fwd);

                CheckArt(go, d, tag, prefab.transform.localScale.x);
                CheckMaterials(go, d, tag);
                CheckRepaint(go, d, tag);

                Heightmap.Biome biome = FirstBiome(d);
                ZNetView nv = go.GetComponent<ZNetView>();
                nv.GetZDO().Set(BlightedSubBosses.ZdoBiome, (int)biome);
                var look = go.GetComponent<BlightedSubBossLook>();
                yield return WaitFor(() => look != null && look._applied, 5f);
                CheckTint(go, biome, tag);

                yield return CreatureShots(go, "S-" + d.Id.Replace("BlightedSB_", ""));
                Remove(go);
                yield return Sec(0.5f);
            }
            MorningLight(false);
            foreach (var kv in BlightedSubBossMaterials.Report.OrderBy(k => k.Key)) Result("INFO", "material " + kv.Key, kv.Value);
            foreach (var kv in BlightedSubBossRepaint.Report.OrderBy(k => k.Key)) Result("INFO", "repaint " + kv.Key, kv.Value);
            ResetPlayer();
        }

        // ------------------------------------------------------------------------------------------ F: the faction

        static bool Enemy(Character a, Character b) => BaseAI.IsEnemy(a, b);

        IEnumerator PhaseF()
        {
            ResetPlayer();
            Player p = Player.m_localPlayer;
            var made = new List<GameObject>();
            GameObject Mk(string prefab, Vector3 off, bool join)
            {
                GameObject g = Spawn(prefab, OnGround(Origin + off), Quaternion.LookRotation(-Fwd));
                if (g != null) { made.Add(g); if (join) BlightedFaction.Join(g); }
                return g;
            }
            GameObject bg = Mk("Greydwarf", Fwd * 10f - Right * 2f, true);
            GameObject bs = Mk("Skeleton", Fwd * 10f + Right * 2f, true);
            GameObject sb = Mk(BlightedSubBosses.Rootstalker.Id, Fwd * 14f, true);
            GameObject vg = Mk("Greydwarf", Fwd * 30f - Right * 12f, false);
            GameObject vb = Mk("Boar", Fwd * 30f + Right * 12f, false);
            yield return Sec(1.5f);
            Character G = bg?.GetComponent<Character>(), S = bs?.GetComponent<Character>(), R = sb?.GetComponent<Character>(),
                      VG = vg?.GetComponent<Character>(), VB = vb?.GetComponent<Character>();
            if (new[] { G, S, R, VG, VB }.Any(c => c == null)) { Result("FAIL", "faction: spawn", "a test creature did not spawn"); foreach (var g in made) Remove(g); yield break; }

            Check(G.m_faction == BlightedFaction.Value && S.m_faction == BlightedFaction.Value && R.m_faction == BlightedFaction.Value,
                "faction: Join sets the faction", $"Greydwarf {G.m_faction}, Skeleton {S.m_faction}, Rootstalker {R.m_faction} (Blighted = {(int)BlightedFaction.Value})");
            int key = "blighted_faction".GetStableHashCode();
            Check(bg.GetComponent<ZNetView>().GetZDO().GetInt(key) == 1, "faction: stored on the ZDO", "blighted_faction = 1");

            // allies: every pair of summons, both ways
            var allies = new[] { (G, S, "Greydwarf/Skeleton"), (G, R, "Greydwarf/Rootstalker"), (S, R, "Skeleton/Rootstalker") };
            foreach (var (a, b, n) in allies)
                Check(!Enemy(a, b) && !Enemy(b, a), $"faction: {n} are allies", $"IsEnemy {Enemy(a, b)} / {Enemy(b, a)}");
            // enemies of everything else, both ways
            var foes = new[] { (G, VG, "Blighted Greydwarf vs wild Greydwarf"), (S, VB, "Blighted Skeleton vs Boar"), (R, VB, "Rootstalker vs Boar"),
                               (G, (Character)p, "Blighted Greydwarf vs the player"), (R, (Character)p, "Rootstalker vs the player") };
            foreach (var (a, b, n) in foes)
                Check(Enemy(a, b) && Enemy(b, a), $"faction: {n} are enemies", $"IsEnemy {Enemy(a, b)} / {Enemy(b, a)}");
            Result("INFO", "faction: vanilla Greydwarf vs Skeleton (no Join)", "vanilla factions ForestMonsters / Undead: the infighting the fix removes");
            Check(G.IsMonsterFaction(Time.time) && R.IsMonsterFaction(Time.time), "faction: counts as a monster", $"IsMonsterFaction {G.IsMonsterFaction(Time.time)} / {R.IsMonsterFaction(Time.time)}");

            // the reload path: a ZDO with the key, instantiated by ZNetScene itself (zone load / ownership change)
            int hash = "Draugr".GetStableHashCode();
            Vector3 zpos = OnGround(Origin + Fwd * 16f - Right * 6f);
            ZDO z = ZDOMan.instance.CreateNewZDO(zpos, hash);
            z.SetPrefab(hash);
            z.Persistent = true;
            z.Set(key, 1);
            ZNetView zv = null;
            yield return WaitFor(() => (zv = ZNetScene.instance.FindInstance(z)) != null, 10f);
            Character zc = zv != null ? zv.GetComponent<Character>() : null;
            if (zv != null) made.Add(zv.gameObject);
            Check(zc != null && zc.m_faction == BlightedFaction.Value, "faction: re-applied when ZNetScene loads the creature",
                zc != null ? $"Draugr from a stored ZDO: faction {zc.m_faction}" : "ZNetScene did not instantiate the ZDO within 10 s");

            // live: the two summons of different vanilla factions side by side with their AI on, a Boar walked in
            float gh = G.GetHealth(), sh = S.GetHealth();
            if (vb != null) { vb.transform.position = OnGround(Origin + Fwd * 13f); }
            float t0 = Time.time;
            bool sawBoarTarget = false;
            Character gTarget = null, sTarget = null;
            while (Time.time - t0 < 20f)
            {
                var gm = bg.GetComponent<MonsterAI>(); var sm = bs.GetComponent<MonsterAI>();
                gTarget = gm != null ? gm.m_targetCreature : null; sTarget = sm != null ? sm.m_targetCreature : null;
                if (gTarget == S || sTarget == G) break;
                if (gTarget == VB || sTarget == VB || (VB != null && VB.GetHealth() < VB.GetMaxHealth())) sawBoarTarget = true;
                yield return Sec(0.5f);
            }
            Check(G != null && S != null && gTarget != S && sTarget != G && G.GetHealth() >= gh && S.GetHealth() >= sh,
                "faction: live, Blighted Greydwarf and Skeleton do not fight",
                $"{Time.time - t0:0} s side by side: Greydwarf targets {gTarget?.m_name ?? "none"}, HP {G?.GetHealth():0}/{gh:0}; Skeleton targets {sTarget?.m_name ?? "none"}, HP {S?.GetHealth():0}/{sh:0}");
            Result(sawBoarTarget ? "PASS" : "WARN", "faction: live, the summons go for a Boar",
                sawBoarTarget ? "a summon targeted or hurt the Boar" : $"no summon targeted the Boar in 20 s (Boar HP {VB?.GetHealth():0}/{VB?.GetMaxHealth():0}; the Boar may have fled out of sight)");

            foreach (var g in made) Remove(g);
            ResetPlayer();
        }

        // ------------------------------------------------------------------------------------------ H: the Heart end to end

        IEnumerator PhaseH()
        {
            ResetPlayer();
            Player p = Player.m_localPlayer;
            const Heightmap.Biome biome = Heightmap.Biome.BlackForest;   // the mixed-faction altar, two Sub-Boss options
            GameObject heartPrefab = ZNetScene.instance.GetPrefab("BlightedWorldHeart");
            if (heartPrefab == null) { Result("FAIL", "heart: prefab", "BlightedWorldHeart not in ZNetScene"); yield break; }
            Vector3 at = OnGround(Origin + Fwd * 14f);
            GameObject heart = UnityEngine.Object.Instantiate(heartPrefab, at, Quaternion.identity);
            var ai = heart.GetComponent<BlightedWorldHeartAI>();
            ai.Initialize(biome);   // what BlightedHeartSpawning does after the altar's build-up
            Result("INFO", "heart: spawned", $"{biome}, HP {ai.m_health:0}/{ai.m_maxHealth:0} at {V(at)}");

            // the first wave comes 1 s after Initialize
            yield return WaitFor(() => ai.m_spawnedEnemies.Count > 0, 10f);
            yield return Sec(1f);
            var wave = ai.m_spawnedEnemies.Where(e => e != null).ToList();
            var waveF = wave.Select(e => e.GetComponent<Character>()).Where(c => c != null).ToList();
            Check(wave.Count > 0 && waveF.All(c => c.m_faction == BlightedFaction.Value), "heart: the wave joins the Blighted faction",
                $"{wave.Count} wave creatures [{string.Join(", ", wave.Select(e => Utils.GetPrefabName(e)).GroupBy(x => x).Select(g => g.Count() + "x " + g.Key))}], " +
                $"{waveF.Count(c => c.m_faction == BlightedFaction.Value)} Blighted");

            string[] pool = BlightedSubBosses.ByBiome[biome].Select(x => x.Id).ToArray();
            var subs = new List<GameObject>();
            foreach (var (n, frac) in new[] { (1, 0.45f), (2, 0.15f) })
            {
                var hit = new HitData();
                hit.m_damage.m_blunt = ai.m_health - ai.m_maxHealth * frac;
                hit.m_point = at + Vector3.up;
                hit.SetAttacker(p);
                ai.Damage(hit);
                Character sbc = null;
                yield return WaitFor(() => (sbc = n == 1 ? ai.m_subBoss1 : ai.m_subBoss2) != null, 8f);
                if (sbc == null) { Result("FAIL", $"heart: Sub-Boss {n}", $"none spawned within 8 s at {ai.m_health / ai.m_maxHealth:P0} health"); continue; }
                GameObject sg = sbc.gameObject;
                subs.Add(sg);
                yield return Sec(1.5f);
                string id = Utils.GetPrefabName(sg);
                BlightedSubBosses.Def d = BlightedSubBosses.All.FirstOrDefault(x => x.Id == id);
                ZDO zdo = sg.GetComponent<ZNetView>().GetZDO();
                var cfg = BlightedConfigManager.BiomeConfigs[biome];
                float wantHp = n == 1 ? cfg.SubBoss1HP.Value : cfg.SubBoss2HP.Value;
                Check(d != null && pool.Contains(id) && sbc.m_faction == BlightedFaction.Value && zdo.GetInt(BlightedSubBosses.ZdoBiome) == (int)biome
                      && Mathf.Abs(sbc.GetMaxHealth() - wantHp) < 1f && sbc.GetLevel() == BlightedConfigManager.SubBossLevel.Value && sg.GetComponent<BlightedSubBoss>() != null,
                    $"heart: Sub-Boss {n} from the biome's pool",
                    $"{id} (pool {string.Join("/", pool)}), faction {sbc.m_faction}, ZDO biome {zdo.GetInt(BlightedSubBosses.ZdoBiome)}, HP {sbc.GetMaxHealth():0} (config {wantHp:0}), " +
                    $"level {sbc.GetLevel()} (config {BlightedConfigManager.SubBossLevel.Value}), health-bar component {sg.GetComponent<BlightedSubBoss>() != null}");
                if (d != null)
                {
                    BaseAI sai = sg.GetComponent<BaseAI>();
                    if (sai != null) sai.enabled = false;
                    var look = sg.GetComponent<BlightedSubBossLook>();
                    yield return WaitFor(() => look != null && look._applied, 5f);
                    CheckArt(sg, d, $"heart: Sub-Boss {n} {d.DisplayName}", heartPrefabScale(d) * 1.5f);
                    CheckTint(sg, biome, $"heart: Sub-Boss {n} {d.DisplayName}");
                    var gm = sg.GetComponent<MonsterAI>();
                    Check(waveF.All(w => w == null || !BaseAI.IsEnemy(sbc, w)), $"heart: Sub-Boss {n} allied with the wave", $"{waveF.Count} wave creatures checked");
                    MorningLight(true);
                    yield return Sec(1f);
                    yield return CreatureShots(sg, $"H-subboss{n}-{id.Replace("BlightedSub", "").Replace("BlightedSB_", "")}");
                    MorningLight(false);
                    if (sai != null) sai.enabled = true;
                }
            }

            // the wide shot: Heart, wave and Sub-Bosses together
            MorningLight(true);
            yield return Sec(1f);
            ResetPlayer();
            yield return AimSettled(() => at + Vector3.up * 1.5f);
            yield return Shot("H-heart-fight", at + Vector3.up * 1.5f);

            // death and loot: 3 Blighted items for one player
            var before = new HashSet<ItemDrop>(UnityEngine.Object.FindObjectsOfType<ItemDrop>());
            var kill = new HitData();
            kill.m_damage.m_blunt = ai.m_health + 10f;
            kill.m_point = at + Vector3.up;
            kill.SetAttacker(p);
            ai.Damage(kill);
            yield return Sec(2f);
            var drops = UnityEngine.Object.FindObjectsOfType<ItemDrop>().Where(x => !before.Contains(x) && Vector3.Distance(x.transform.position, at) < 6f).ToList();
            var names = drops.Select(x => Utils.GetPrefabName(x.gameObject)).ToList();
            Check(heart == null && drops.Count == 3 && names.All(x => x.StartsWith("Blighted", StringComparison.OrdinalIgnoreCase)),
                "heart: death drops 3 Blighted items", $"heart {(heart == null ? "destroyed" : "STILL THERE")}; {drops.Count} drops [{string.Join(", ", names)}]");
            MorningLight(false);

            foreach (var g in drops) if (g != null) Remove(g.gameObject);
            foreach (var g in subs) Remove(g);
            foreach (var g in wave) Remove(g);
            ResetPlayer();
        }

        static float heartPrefabScale(BlightedSubBosses.Def d)
        {
            GameObject pf = ZNetScene.instance.GetPrefab(d.Id);
            return pf != null ? pf.transform.localScale.x : 1f;
        }
    }
}
