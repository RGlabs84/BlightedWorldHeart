using System.Collections.Generic;
using System.IO;
using System.Reflection;
using Newtonsoft.Json.Linq;
using UnityEngine;

namespace BlightedHeart
{
    // Integration stage 3b: the body repaint, the Runic playbook (MagicRunicMod ArmorRepaint.cs = apply_armor_repaint.py).
    // This is art/subbosses/kit_tools/apply_subboss_repaint.py LINE FOR LINE (same names, same order); that script rebuilds the
    // six approved repaints from the same maps to p99 <= 2.93/255 (2026-11-22). Inputs: our maps and the recipe table
    // (art/subbosses/runtime/repaint/, embedded) + the donor's own _MainTex and TheHive's bark, read back from the GPU. No vanilla
    // pixel ships. Runs once per Sub-Boss prefab on clients; a missing input keeps the vanilla body with one warning.
    public static class BlightedSubBossRepaint
    {
        private const string Prefix = "BlightedHeart.SubBossRepaint.";
        private static JObject _table;
        internal static readonly Dictionary<string, string> Report = new Dictionary<string, string>();   // the autotest reads it
        internal static readonly Dictionary<string, Texture2D> Albedo = new Dictionary<string, Texture2D>();
        internal static readonly Dictionary<string, Texture2D> Emission = new Dictionary<string, Texture2D>();

        private static readonly Vector3 LumW = new Vector3(0.3f, 0.59f, 0.11f);

        private static JObject Table()
        {
            if (_table != null) return _table;
            using (Stream s = Res("repaint.json"))
            {
                if (s == null) return _table = new JObject();
                using (var r = new StreamReader(s)) _table = JObject.Parse(r.ReadToEnd());
            }
            return _table;
        }

        private static Stream Res(string name) => Assembly.GetExecutingAssembly().GetManifestResourceStream(Prefix + name);

        private static Color32[] Png(string name, out int size)
        {
            using (Stream s = Res(name))
            {
                size = 0;
                if (s == null) return null;
                var bytes = new byte[s.Length]; s.Read(bytes, 0, bytes.Length);
                var t = new Texture2D(2, 2, TextureFormat.RGBA32, false, true);
                t.LoadImage(bytes, false);
                size = t.width;
                Color32[] px = t.GetPixels32();      // bottom-up, as the reference
                Object.Destroy(t);
                return px;
            }
        }

        private static Vector3 V3(JToken t) => new Vector3((float)t[0], (float)t[1], (float)t[2]);
        private static Vector3 Mul(Vector3 a, Vector3 b) => new Vector3(a.x * b.x, a.y * b.y, a.z * b.z);
        private static float Clip(float x, float lo, float hi) => x < lo ? lo : (x > hi ? hi : x);

        // Repaints the donor body on one cloned Sub-Boss prefab. Returns true when the repainted material is on.
        public static bool Apply(GameObject prefab, string kitId)
        {
            if (SystemInfo.graphicsDeviceType == UnityEngine.Rendering.GraphicsDeviceType.Null) return false;   // headless server
            var k = Table()["kits"]?[kitId] as JObject;
            if (k == null) return false;
            string matName = (string)k["material"];
            Material body = null;
            var users = new List<Renderer>();
            foreach (Renderer r in prefab.GetComponentsInChildren<Renderer>(true))
                foreach (Material m in r.sharedMaterials)
                    if (m != null && m.name == matName) { body = m; users.Add(r); break; }
            if (body == null) { Warn(kitId, $"no renderer uses '{matName}'"); return false; }
            Texture bark = BarkTexture();
            if (bark == null) { Warn(kitId, "TheHive_Mat's bark texture not found"); return false; }
            Texture main = body.HasProperty("_MainTex") ? body.GetTexture("_MainTex") : null;
            if (main == null) { Warn(kitId, $"{matName} has no _MainTex"); return false; }
            try
            {
                var t0 = System.Diagnostics.Stopwatch.StartNew();
                Repaint(kitId, k, body, main, bark, out Texture2D alb, out Texture2D em, out string note);
                var m = new Material(body) { name = body.name + "_BSB_" + kitId.Replace("BlightedSB_", ""), hideFlags = HideFlags.HideAndDontSave };
                m.SetTexture("_MainTex", alb);
                if (m.HasProperty("_EmissionMap")) m.SetTexture("_EmissionMap", em);
                float st = (float)k["strength"];
                if (m.HasProperty("_EmissionColor")) m.SetVector("_EmissionColor", new Vector4(st, st, st, 1f));
                m.EnableKeyword("_EMISSION");
                foreach (Renderer r in users)
                {
                    Material[] ms = r.sharedMaterials;
                    for (int i = 0; i < ms.Length; i++) if (ms[i] == body) ms[i] = m;
                    r.sharedMaterials = ms;
                }
                Albedo[kitId] = alb; Emission[kitId] = em;
                Report[kitId] = $"{note}; {users.Count} renderer(s) on {m.name}, emission x{st}; {t0.ElapsedMilliseconds} ms";
                return true;
            }
            catch (System.Exception e)
            {
                Warn(kitId, "repaint failed: " + e.Message);
                return false;
            }
        }

        private static readonly HashSet<string> Warned = new HashSet<string>();
        private static void Warn(string kitId, string msg)
        {
            Report[kitId] = "NOT repainted: " + msg;
            if (Warned.Add(kitId)) Jotunn.Logger.LogWarning($"[BlightedHeart] Sub-Boss repaint {kitId}: {msg}; it keeps the vanilla body.");
        }

        private static Texture _bark;
        private static Texture BarkTexture()
        {
            if (_bark != null) return _bark;
            foreach (Material m in Resources.FindObjectsOfTypeAll<Material>())
                if (m != null && m.name == "TheHive_Mat" && m.HasProperty("_MainTex") && m.GetTexture("_MainTex") != null)
                    return _bark = m.GetTexture("_MainTex");
            return null;
        }

        // ------------------------------------------------------------------------------------------ apply_subboss_repaint.repaint

        private static void Repaint(string kid, JObject k, Material body, Texture mainTex, Texture barkTex,
                                    out Texture2D albedoTex, out Texture2D emTex, out string note)
        {
            Color32[] hive = Png(kid + "_hive.png", out int S);
            Color32[] reg = Png(kid + "_regions.png", out int _);
            Color32[] bk = Png(kid + "_bark.png", out int BS);
            if (hive == null || reg == null || bk == null) throw new System.InvalidOperationException("a map is missing");
            int N = S * S;
            int barkPx = (int)Table()["bark_px"];
            string formula = (string)k["formula"];

            // the vanilla albedo at the map size, and TheHive's bark at 512 (the composites' sizes), stored texel values 0..1
            Color32[] alb32 = BlightedSubBossMaterials.ReadBack(mainTex, S, S);
            Color32[] bark32 = BlightedSubBossMaterials.ReadBack(barkTex, 512, 512);
            var bark = new Vector3[512 * 512];
            for (int i = 0; i < bark.Length; i++) bark[i] = new Vector3(bark32[i].r / 255f, bark32[i].g / 255f, bark32[i].b / 255f);

            var cov = new bool[N]; var code = new int[N];
            for (int i = 0; i < N; i++) { cov[i] = reg[i].r > 127; code[i] = reg[i].b; }

            // the bark: the composites' 4-tap sample at each stored coordinate, px = int(u * 510), averaged over the f x f
            // sub-samples inside the layout
            int f = BS / S;
            var BKs = new Vector3[N];
            var nsub = new int[N];
            for (int y = 0; y < BS; y++)
                for (int x = 0; x < BS; x++)
                {
                    Color32 c = bk[y * BS + x];
                    if (c.r + c.g + c.b + c.a == 0) continue;
                    float u = (c.r * 256 + c.g) / 65536f, v = (c.b * 256 + c.a) / 65536f;
                    int px = (int)(u * barkPx), py = (int)(v * barkPx);
                    Vector3 b4 = (bark[py * 512 + px] + bark[(py + 1) * 512 + px] + bark[py * 512 + px + 1] + bark[(py + 1) * 512 + px + 1]) * 0.25f;
                    int o = (y / f) * S + (x / f);
                    BKs[o] += b4; nsub[o]++;
                }
            for (int i = 0; i < N; i++) if (nsub[i] > 0) BKs[i] /= nsub[i];

            var O = new Vector3[N];
            var lum = new float[N];
            double sumL = 0, sumO = 0, sumBK = 0; int nc = 0;
            for (int i = 0; i < N; i++)
            {
                O[i] = new Vector3(alb32[i].r / 255f, alb32[i].g / 255f, alb32[i].b / 255f);
                lum[i] = Vector3.Dot(O[i], LumW);
                if (cov[i]) { sumL += lum[i]; sumO += (O[i].x + O[i].y + O[i].z) / 3f; sumBK += (BKs[i].x + BKs[i].y + BKs[i].z) / 3f; nc++; }
            }
            float mlum = (float)(sumL / System.Math.Max(nc, 1));
            float mO = (float)(sumO / System.Math.Max(nc, 1));
            float mbk = (float)(sumBK / System.Math.Max(nc, 1));

            Color32[] moss = formula == "A" ? Png(kid + "_moss.png", out int _) : null;
            Color32[] mouth = k["fold_darken"] != null ? Png(kid + "_mouth.png", out int _) : null;
            Vector3 barkTint = V3(k["bark_tint"]), sickSkin = V3(k["sick_skin"]), rootC = V3(k["root_colour"]), veinC = V3(k["vein_albedo"]);
            float extD = (float)k["extremity_darken"], imd = (float)k["infection_margin_darken"];
            bool headCap = k["head_cap"] != null && (bool)k["head_cap"];

            var outRGB = new Vector3[N];
            for (int i = 0; i < N; i++)
            {
                if (!cov[i]) { outRGB[i] = O[i]; continue; }
                float b = hive[i].r / 255f, ext = hive[i].g / 255f, rm = hive[i].a / 255f, vm = reg[i].a / 255f;
                float ln = lum[i] / System.Math.Max(1e-6f, mlum);
                Vector3 col;
                if (formula == "A")
                {
                    float seam = reg[i].g / 255f;
                    ln = ln * (1 - seam) + 0.92f * seam;                                   // the mirrored halves' shading blended across x = 0
                    if (headCap && code[i] == 1) ln = Mathf.Min(ln, 1f);                   // the Lox's pale head plate capped
                    Vector3 barkcol = Mul(BKs[i], barkTint) * (0.45f + 0.55f * Clip(ln, 0, 2));
                    Vector3 sick = sickSkin * Clip(ln, 0, 2.5f);
                    col = sick * (1 - b) + barkcol * b;
                    float ms = moss[i].r / 255f;
                    col = col * (1 - ms) + V3(k["moss_colour"]) * Clip(ln, 0.4f, 1.4f) * ms;
                    col = col * (1 - extD * ext);
                    col = col * (1 - imd * 4 * b * (1 - b));
                    col = col * (1 - rm) + rootC * rm;
                    col = col * (1 - vm) + veinC * vm;
                    if (mouth != null)
                    {
                        float ov = mouth[i].r / 255f, gv = mouth[i].g / 255f, fv = mouth[i].b / 255f;
                        col = col * (1 - (float)k["fold_darken"] * fv);
                        col = col * (1 - gv) + V3(k["gum_colour"]) * Clip(ln, 0.5f, 1.6f) * gv;
                        col = col * (1 - ov) + V3(k["mouth_opening_colour"]) * ov;
                    }
                }
                else
                {
                    float lnc = Clip(ln, 0, 2.5f);
                    Vector3 barkcol = Mul(BKs[i], barkTint) * (0.45f + 0.55f * Clip(lnc, 0, 2));
                    float mix = (float)k["sick_mix"];
                    Vector3 sick = formula == "brood"
                        ? O[i] * (1 - mix) + sickSkin * (lnc * mlum / 0.4f * mix)
                        : O[i] * (1 - mix) + sickSkin * (lnc * mix);
                    if (k["antler_weather"] != null && code[i] == 2)
                        sick = O[i] * 0.45f + V3(k["antler_weather"]) * (lnc * 0.55f * mO);
                    col = sick * (1 - b) + barkcol * b;
                    col = col * (1 - extD * ext);
                    col = col * (1 - imd * 4 * b * (1 - b));
                    if (formula == "brood")
                    {
                        if (code[i] == 3 || code[i] == 4)
                            col = V3(k["wing_colour"]) * (lnc * mlum / 0.4f * (0.6f + 0.4f * ((BKs[i].x + BKs[i].y + BKs[i].z) / 3f) / System.Math.Max(1e-6f, mbk)));
                        if (code[i] == 5)
                            col = V3(k["mandible_colour"]) * Clip(lnc, 0, 1.3f);
                    }
                    col = col * (1 - rm) + rootC * rm;
                    col = col * (1 - vm) + veinC * vm;
                }
                outRGB[i] = col;
            }
            outRGB = DilateFill(outRGB, cov, S, 8);

            var px32 = new Color32[N];
            for (int i = 0; i < N; i++)
            {
                byte a = formula == "brood" && code[i] == 4 ? (byte)0 : alb32[i].a;          // the torn wings' ragged holes
                px32[i] = new Color32(B(outRGB[i].x), B(outRGB[i].y), B(outRGB[i].z), a);
            }
            albedoTex = Make(kid + "_albedo", S, px32, false);

            // emission, linear: blight veins x colour [x strength in map] (+ brood halo) + the donor's own glow x own_emission
            Vector3 blight = V3(k["blight_colour"]);
            float sim = (float)k["strength_in_map"], own = (float)k["own_emission"];
            Vector3[] ownE = null;
            if (own > 0 && body.HasProperty("_EmissionMap") && body.GetTexture("_EmissionMap") != null)
            {
                Color32[] e32 = BlightedSubBossMaterials.ReadBack(body.GetTexture("_EmissionMap"), S, S);
                Vector4 ec = body.GetVector("_EmissionColor");
                ownE = new Vector3[N];
                for (int i = 0; i < N; i++)
                {
                    Color lin = ((Color)e32[i]).linear;
                    ownE[i] = new Vector3(lin.r * ec.x, lin.g * ec.y, lin.b * ec.z);
                }
            }
            var em32 = new Color32[N];
            Vector3 halo = formula == "brood" ? V3(k["halo_colour"]) : Vector3.zero;
            for (int i = 0; i < N; i++)
            {
                Vector3 e = blight * (Clip(hive[i].b / 255f, 0, 1) * sim);
                if (formula == "brood")
                {
                    Vector3 h = halo * (reg[i].g / 255f * 0.5f);
                    e = new Vector3(Mathf.Max(e.x, h.x), Mathf.Max(e.y, h.y), Mathf.Max(e.z, h.z));
                }
                if (ownE != null) e += ownE[i] * own;
                em32[i] = new Color32(B(e.x), B(e.y), B(e.z), 255);
            }
            emTex = Make(kid + "_emission", S, em32, true);
            note = $"{S}px, formula {formula}, bark {BS}px ({f}x{f} sub-samples), {nc} covered texels, mean luminance {mlum:0.000}" +
                   (ownE != null ? $", own glow x{own}" : "");
        }

        // troll_repaint.dilate_fill: 4-neighbour mean into the gutter, wrapping at the edges, simultaneous per pass
        private static Vector3[] DilateFill(Vector3[] img, bool[] valid, int S, int n)
        {
            var outp = (Vector3[])img.Clone(); var v = (bool[])valid.Clone();
            for (int it = 0; it < n; it++)
            {
                var next = (Vector3[])outp.Clone(); var nv = (bool[])v.Clone();
                for (int y = 0; y < S; y++)
                    for (int x = 0; x < S; x++)
                    {
                        int i = y * S + x;
                        if (v[i]) continue;
                        Vector3 acc = Vector3.zero; int cnt = 0;
                        int yu = (y + S - 1) % S, yd = (y + 1) % S, xl = (x + S - 1) % S, xr = (x + 1) % S;
                        int a0 = yu * S + x, a1 = yd * S + x, a2 = y * S + xl, a3 = y * S + xr;
                        if (v[a0]) { acc += outp[a0]; cnt++; }
                        if (v[a1]) { acc += outp[a1]; cnt++; }
                        if (v[a2]) { acc += outp[a2]; cnt++; }
                        if (v[a3]) { acc += outp[a3]; cnt++; }
                        if (cnt > 0) { next[i] = acc / cnt; nv[i] = true; }
                    }
                outp = next; v = nv;
            }
            return outp;
        }

        private static byte B(float v) => (byte)Mathf.Clamp(Mathf.RoundToInt(v * 255f), 0, 255);

        private static Texture2D Make(string name, int S, Color32[] px, bool linear)
        {
            var t = new Texture2D(S, S, TextureFormat.RGBA32, true, linear) { name = "BSB_" + name, hideFlags = HideFlags.HideAndDontSave, wrapMode = TextureWrapMode.Repeat };
            t.SetPixels32(px);
            t.Apply(true, true);
            return t;
        }
    }
}
