using System.Collections.Generic;
using System.IO;
using System.Reflection;
using Newtonsoft.Json.Linq;
using UnityEngine;

namespace BlightedHeart
{
    // Integration stage 3 (materials), the Runic playbook (MagicRunicMod StationLook / ArmorModels): ONE table
    // (art/subbosses/runtime/materials.json, embedded), every part slot names a key ("looks" in the kit JSON), every material
    // is OUR copy of a vanilla material, built once per process and shared by every Sub-Boss of that kind. Colours are the
    // linear multipliers the approved renders used, written raw with SetVector (Runic DESIGN 9.25: SetColor would sRGB-decode
    // them). A key or a donor that is missing falls back to the part's own vanilla material with one warning.
    public static class BlightedSubBossMaterials
    {
        private const string TableResource = "BlightedHeart.SubBossKits.materials.json";
        private const string EyeMaskResource = "BlightedHeart.SubBossEyeMask.png";

        private static JObject _table;
        private static Texture2D _eyeMask;
        private static Color32[] _eyeMaskPx;
        private static readonly Dictionary<string, Material> Built = new Dictionary<string, Material>();
        private static readonly HashSet<string> Warned = new HashSet<string>();
        internal static readonly Dictionary<string, string> Report = new Dictionary<string, string>();   // key -> what was built (autotest reads it)

        internal static string KeyOf(string look) =>
            look != null && look.Length > 4 && look[look.Length - 4] == '.' && char.IsDigit(look[look.Length - 1]) ? look.Substring(0, look.Length - 4) : look;

        private static JObject Table()
        {
            if (_table != null) return _table;
            using (Stream s = Assembly.GetExecutingAssembly().GetManifestResourceStream(TableResource))
            {
                if (s == null) { Warn("table", "no embedded material table; the Sub-Boss parts keep their vanilla materials"); return _table = new JObject(); }
                using (var r = new StreamReader(s)) _table = JObject.Parse(r.ReadToEnd());
            }
            return _table;
        }

        private static void Warn(string key, string msg)
        {
            if (Warned.Add(key)) Jotunn.Logger.LogWarning("[BlightedHeart] Sub-Boss materials: " + msg);
        }

        // The material for one part slot: our shared copy, or the host (vanilla) material when the key is unknown.
        public static Material Get(string kitId, string look, Material host)
        {
            if (host == null || look == null) return host;
            string key = KeyOf(look);
            string cacheKey = kitId + "/" + key + "/" + host.name;
            if (Built.TryGetValue(cacheKey, out Material m) && m != null) return m;
            var def = Table()["kits"]?[kitId]?[key] as JObject;
            if (def == null) { Warn(kitId + "/" + key, $"no table entry for {kitId}/{key}; that slot keeps {host.name}"); return host; }
            try
            {
                m = Build(kitId, key, def, host);
            }
            catch (System.Exception e)
            {
                Warn(cacheKey, $"{kitId}/{key} failed ({e.Message}); that slot keeps {host.name}");
                m = host;
            }
            Built[cacheKey] = m;
            return m;
        }

        private static Vector4 V(JToken t, float a = 1f) => new Vector4((float)t[0], (float)t[1], (float)t[2], a);

        private static Material Build(string kitId, string key, JObject def, Material host)
        {
            bool creature = (string)def["shader"] == "creature";
            Material m;
            if (creature)
            {
                // Shader.Find cannot reach Custom/Creature (not an always-included shader): clone a loaded material that uses it,
                // as Runic does (ArmorModels: a copy of helmet_bronze_mat), then set every map we need ourselves.
                Material donor = CreatureDonor();
                if (donor == null) throw new System.InvalidOperationException("no loaded Custom/Creature material to copy");
                m = new Material(donor);
                if (m.HasProperty("_EmissionMap")) m.SetTexture("_EmissionMap", null);
                if (m.HasProperty("_MetalColor")) m.SetVector("_MetalColor", Vector4.one);
                if (m.HasProperty("_EmissionColor")) m.SetVector("_EmissionColor", new Vector4(0f, 0f, 0f, 1f));
            }
            else m = new Material(host);
            m.name = "BSB_" + kitId.Replace("BlightedSB_", "") + "_" + key;
            m.hideFlags = HideFlags.HideAndDontSave;
            Texture hostTex = host.HasProperty("_MainTex") ? host.GetTexture("_MainTex") : null;
            var notes = new List<string> { creature ? "Custom/Creature" : "copy of " + host.name };

            // ---- albedo
            JToken alb = def["albedo"];
            if (creature) { m.SetTexture("_MainTex", hostTex); if (m.HasProperty("_BumpMap")) m.SetTexture("_BumpMap", null); }
            if (alb != null && alb.Type == JTokenType.String && (string)alb == "white") { m.SetTexture("_MainTex", Texture2D.whiteTexture); notes.Add("white albedo"); }
            else if (alb != null && alb.Type == JTokenType.String && (string)alb == "eye_pupil" && hostTex != null)
            {
                m.SetTexture("_MainTex", EyeTexture(hostTex, key + "_pupil", EyeOp.Pupil)); notes.Add("pupil-darkened albedo");
            }
            else if (alb is JObject op && hostTex != null)
            {
                m.SetTexture("_MainTex", Weathered(hostTex, V(op["pre"] ?? new JArray(1, 1, 1)), (float?)op["saturation"] ?? 1f, m.name));
                notes.Add($"weathered albedo (saturation x{(float?)op["saturation"] ?? 1f})");
            }

            // ---- colour, gloss, moss
            if (def["color"] != null) { m.SetVector("_Color", V(def["color"])); notes.Add("_Color " + def["color"].ToString(Newtonsoft.Json.Formatting.None)); }
            if (def["gloss"] != null && m.HasProperty("_Glossiness")) m.SetFloat("_Glossiness", (float)def["gloss"]);
            if (def["moss"] != null && m.HasProperty("_MossAlpha")) m.SetFloat("_MossAlpha", (float)def["moss"]);

            // ---- emission
            JToken em = def["emission"];
            if (em != null && em.Type == JTokenType.String && (string)em == "off")
            {
                if (m.HasProperty("_EmissionColor")) m.SetVector("_EmissionColor", new Vector4(0f, 0f, 0f, 1f));
                notes.Add("emission off");
            }
            else if (em is JObject eo)
            {
                string map = eo["map"]?.Type == JTokenType.String ? (string)eo["map"] : null;
                Texture emTex = map == "main" ? hostTex
                              : map == "eye_core" && hostTex != null ? EyeTexture(hostTex, key + "_core", EyeOp.Core)
                              : map == "brood" && hostTex != null ? EyeTexture(hostTex, key + "_brood", EyeOp.Brood)
                              : null;
                if (emTex != null && m.HasProperty("_EmissionMap")) m.SetTexture("_EmissionMap", emTex);
                if (m.HasProperty("_EmissionColor")) m.SetVector("_EmissionColor", V(eo["color"]));
                m.EnableKeyword("_EMISSION");
                notes.Add($"emission {eo["color"].ToString(Newtonsoft.Json.Formatting.None)}" + (map != null ? " map " + map : ""));
            }
            Report[kitId + "/" + key] = string.Join(", ", notes) + $"; shader {m.shader?.name}";
            return m;
        }

        private static Material _creatureDonor;

        // A Custom/Creature material to copy: the Troll's ("troll", always loaded with its prefab) or any other that uses the shader.
        private static Material CreatureDonor()
        {
            if (_creatureDonor != null) return _creatureDonor;
            Material any = null;
            foreach (Material m in Resources.FindObjectsOfTypeAll<Material>())
            {
                if (m == null || m.shader == null || m.shader.name != "Custom/Creature") continue;
                if (m.name == "troll") return _creatureDonor = m;
                if (any == null) any = m;
            }
            return _creatureDonor = any;
        }

        // ------------------------------------------------------------------------------------------ textures (our copies)

        private enum EyeOp { Pupil, Core, Brood }

        private static Color32[] EyeMask(out int size)
        {
            if (_eyeMaskPx == null)
            {
                using (Stream s = Assembly.GetExecutingAssembly().GetManifestResourceStream(EyeMaskResource))
                {
                    if (s == null) throw new System.InvalidOperationException("no embedded eye mask");
                    var bytes = new byte[s.Length]; s.Read(bytes, 0, bytes.Length);
                    _eyeMask = new Texture2D(2, 2, TextureFormat.RGBA32, false, true) { hideFlags = HideFlags.HideAndDontSave };
                    _eyeMask.LoadImage(bytes, false);
                    _eyeMaskPx = _eyeMask.GetPixels32();
                }
            }
            size = _eyeMask.width;
            return _eyeMaskPx;
        }

        private static readonly Dictionary<string, Texture2D> Textures = new Dictionary<string, Texture2D>();

        // The eye mask is in eye_globe's own UVs, which are also the eye texture's (the approved renders sampled both with the same
        // UV map). Pupil: albedo x (1 - 0.92 G). Core: albedo x R (the emission map; _EmissionColor carries colour and strength).
        // Brood: (R + G)^0.45, no texture (a soft, wide glow). All in linear space, stored sRGB-encoded.
        private static Texture2D EyeTexture(Texture src, string name, EyeOp op)
        {
            if (Textures.TryGetValue(name, out Texture2D done) && done != null) return done;
            Color32[] mk = EyeMask(out int n);
            Color32[] px = ReadBack(src, n, n);
            for (int i = 0; i < px.Length; i++)
            {
                float r = mk[i].r / 255f, g = mk[i].g / 255f;
                Color c = ((Color)px[i]).linear;
                if (op == EyeOp.Pupil) c = c * (1f - 0.92f * g);
                else if (op == EyeOp.Core) c = c * r;
                else { float v = Mathf.Pow(Mathf.Clamp01(r + g), 0.45f); c = new Color(v, v, v); }
                Color s = c.gamma;
                px[i] = new Color32(B(s.r), B(s.g), B(s.b), 255);
            }
            return Textures[name] = Make(name, n, n, px);
        }

        // Blender: texture x pre (linear) -> Hue/Saturation node (S x sat) -> the material's _Color multiply.
        private static Texture2D Weathered(Texture src, Vector4 pre, float sat, string name)
        {
            if (Textures.TryGetValue(name, out Texture2D done) && done != null) return done;
            int w = Mathf.Min(src.width, 1024), h = Mathf.Min(src.height, 1024);
            Color32[] px = ReadBack(src, w, h);
            for (int i = 0; i < px.Length; i++)
            {
                Color c = ((Color)px[i]).linear;
                c = new Color(c.r * pre.x, c.g * pre.y, c.b * pre.z);
                Color.RGBToHSV(c, out float hh, out float ss, out float vv);
                c = Color.HSVToRGB(hh, Mathf.Clamp01(ss * sat), vv, true);
                Color s = c.gamma;
                px[i] = new Color32(B(s.r), B(s.g), B(s.b), px[i].a);
            }
            return Textures[name] = Make(name, w, h, px);
        }

        private static byte B(float v) => (byte)Mathf.Clamp(Mathf.RoundToInt(v * 255f), 0, 255);

        private static Texture2D Make(string name, int w, int h, Color32[] px)
        {
            var t = new Texture2D(w, h, TextureFormat.RGBA32, true, false) { name = "BSB_" + name, hideFlags = HideFlags.HideAndDontSave, wrapMode = TextureWrapMode.Repeat };
            t.SetPixels32(px);
            t.Apply(true, true);      // mipmaps, then no CPU copy
            return t;
        }

        // Runic's ArmorLook.ReadBack: Blit through an sRGB RenderTexture so the bytes are the authored sRGB values, then ReadPixels.
        internal static Color32[] ReadBack(Texture src, int w, int h)
        {
            RenderTexture rt = RenderTexture.GetTemporary(w, h, 0, RenderTextureFormat.ARGB32, RenderTextureReadWrite.sRGB);
            RenderTexture prev = RenderTexture.active;
            Texture2D tmp = null;
            try
            {
                Graphics.Blit(src, rt);
                RenderTexture.active = rt;
                tmp = new Texture2D(w, h, TextureFormat.RGBA32, false, false);
                tmp.ReadPixels(new Rect(0, 0, w, h), 0, 0, false);
                tmp.Apply(false, false);
                Color32[] px = tmp.GetPixels32();
                bool any = false;
                for (int i = 0; i < px.Length; i += 31)
                    if (px[i].r != 0 || px[i].g != 0 || px[i].b != 0 || px[i].a != 0) { any = true; break; }
                if (!any) throw new System.InvalidOperationException("read-back returned only zeros");
                return px;
            }
            finally
            {
                RenderTexture.active = prev;
                RenderTexture.ReleaseTemporary(rt);
                if (tmp != null) Object.Destroy(tmp);
            }
        }
    }
}
