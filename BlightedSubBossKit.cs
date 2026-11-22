using System.Collections.Generic;
using System.IO;
using System.Reflection;
using Newtonsoft.Json;
using UnityEngine;

namespace BlightedHeart
{
    // Integration stage 2: the approved Hive art, rebuilt on the cloned Sub-Boss PREFAB from the game's own meshes.
    //
    // Data: art/subbosses/runtime/<Id>.json (embedded), compiled from the owner-approved Blender scenes by
    // art/subbosses/kit_tools/compile_runtime_kit.py. Per part: the vanilla source mesh (found by name + vertex count among the
    // loaded prefabs), the parent bone, and either
    //   - trs: the whole vanilla mesh placed by a local transform under the bone (used for meshes the game ships unreadable:
    //          eye_globe, ThornRoots), or
    //   - L (3x4) + residual + kept_tris: a new mesh whose vertices are L * v_vanilla + residual[i] in the bone's local space,
    //          made from the kept triangles only (islands cut from a bigger mesh). No game geometry ships with the mod.
    // Runs once per Sub-Boss prefab, on clients only (no GPU on a dedicated server: nothing visual is needed there). Instances
    // inherit it, so a spawn costs nothing extra.
    public static class BlightedSubBossKit
    {
        public class Trs { public float[] p; public float[] r; public float[] s; }
        public class MeshRef { public string name; public int verts; public string prefab; public string renderer; }
        public class Skin { public string[] bones; public int[][] bi; public float[][] bw; }
        public class Subdiv { public float[][] mids; public int[] tris; }   // per added vertex: [a, b, dx, dy, dz]; scene triangles
        public class Part
        {
            public Skin skin;
            public Subdiv subdiv;
            public string name; public string bone; public string mode;
            public MeshRef mesh; public int[] kept_tris; public float[][] L; public float[][] residual;
            public Trs trs; public string[] materials; public string[] looks;
        }
        public class Kit { public string id; public string donor; public string[] hide_renderers; public List<Part> parts; }

        private static Dictionary<string, List<(Mesh mesh, Material[] mats)>> _meshes;
        private static Dictionary<string, Material> _materials;

        public static Kit Load(string id)
        {
            string res = "BlightedHeart.SubBossKits." + id + ".json";
            using (Stream s = Assembly.GetExecutingAssembly().GetManifestResourceStream(res))
            {
                if (s == null) return null;
                using (var r = new StreamReader(s)) return JsonConvert.DeserializeObject<Kit>(r.ReadToEnd());
            }
        }

        private static string Key(string name, int verts) => name + "#" + verts;

        private static void BuildIndex()
        {
            if (_meshes != null) return;
            _meshes = new Dictionary<string, List<(Mesh, Material[])>>();
            void Add(Mesh m, Material[] mats)
            {
                if (m == null) return;
                string k = Key(m.name, m.vertexCount);
                if (!_meshes.TryGetValue(k, out var list)) _meshes[k] = list = new List<(Mesh, Material[])>();
                list.Add((m, mats));
            }
            foreach (MeshFilter mf in Resources.FindObjectsOfTypeAll<MeshFilter>())
                Add(mf.sharedMesh, mf.GetComponent<Renderer>() ? mf.GetComponent<Renderer>().sharedMaterials : new Material[0]);
            foreach (SkinnedMeshRenderer smr in Resources.FindObjectsOfTypeAll<SkinnedMeshRenderer>())
                Add(smr.sharedMesh, smr.sharedMaterials);
            _materials = new Dictionary<string, Material>();
            foreach (Material m in Resources.FindObjectsOfTypeAll<Material>())
                if (m != null && !_materials.ContainsKey(m.name)) _materials[m.name] = m;
            Jotunn.Logger.LogInfo($"[BlightedHeart] Sub-Boss kit index: {_meshes.Count} mesh keys, {_materials.Count} materials.");
        }

        // Applies the kit to a cloned Sub-Boss prefab. Returns the number of parts built.
        public static int Apply(GameObject prefab, string id)
        {
            if (SystemInfo.graphicsDeviceType == UnityEngine.Rendering.GraphicsDeviceType.Null) return 0;
            Kit kit = Load(id);
            if (kit == null) { Jotunn.Logger.LogWarning($"[BlightedHeart] no kit data for {id}"); return 0; }
            BuildIndex();

            var bones = new Dictionary<string, Transform>();
            foreach (Transform t in prefab.GetComponentsInChildren<Transform>(true))
                if (!bones.ContainsKey(t.name)) bones[t.name] = t;

            if (kit.hide_renderers != null)
                foreach (Renderer r in prefab.GetComponentsInChildren<Renderer>(true))
                    if (System.Array.IndexOf(kit.hide_renderers, r.gameObject.name) >= 0) r.enabled = false;

            int built = 0, failed = 0, skinned = 0;
            foreach (Part p in kit.parts)
            {
                if (!bones.TryGetValue(p.bone, out Transform bone)) { failed++; Jotunn.Logger.LogWarning($"[BlightedHeart] {id}/{p.name}: bone {p.bone} missing"); continue; }
                if (!_meshes.TryGetValue(Key(p.mesh.name, p.mesh.verts), out var cands)) { failed++; Jotunn.Logger.LogWarning($"[BlightedHeart] {id}/{p.name}: mesh {p.mesh.name} ({p.mesh.verts} verts) not loaded"); continue; }
                var (src, hostMats) = Pick(cands, p.materials);
                Material[] mats = ResolveMaterials(p.materials, hostMats);

                var go = new GameObject("BSB_" + p.name);
                go.layer = bone.gameObject.layer;
                go.transform.SetParent(bone, false);
                if (p.trs != null)
                {
                    go.transform.localPosition = new Vector3(p.trs.p[0], p.trs.p[1], p.trs.p[2]);
                    go.transform.localRotation = new Quaternion(p.trs.r[0], p.trs.r[1], p.trs.r[2], p.trs.r[3]);
                    go.transform.localScale = new Vector3(p.trs.s[0], p.trs.s[1], p.trs.s[2]);
                }
                Mesh baked = null;
                if (p.trs == null)
                {
                    if (!src.isReadable) { failed++; Object.DestroyImmediate(go); Jotunn.Logger.LogWarning($"[BlightedHeart] {id}/{p.name}: {src.name} is not readable"); continue; }
                    baked = Bake(src, p, ref mats);
                }
                // stage 3: each slot's approved look (our shared material copy, runtime/materials.json); unknown -> the vanilla one
                if (p.looks != null)
                    for (int i = 0; i < mats.Length && i < p.looks.Length; i++) mats[i] = BlightedSubBossMaterials.Get(id, p.looks[i], mats[i]);
                // stage 4: a skinned part follows the donor's own bones (weights compiled from the approved scene / its recipe);
                // a placed (unreadable) mesh or a part without weights rides its bone rigidly
                if (baked != null && p.skin != null && SkinPart(go, baked, p, bones, mats, id)) { skinned++; built++; continue; }
                go.AddComponent<MeshFilter>().sharedMesh = baked != null ? baked : src;
                go.AddComponent<MeshRenderer>().sharedMaterials = mats;
                built++;
            }
            Jotunn.Logger.LogInfo($"[BlightedHeart] Sub-Boss kit {id}: {built} parts built, {failed} failed, of {kit.parts.Count} ({skinned} skinned); " +
                                  $"{BlightedSubBossMaterials.Report.Count} shared Sub-Boss materials so far.");
            return built;
        }

        // The baked mesh (bone-local vertices) as a SkinnedMeshRenderer on the donor's bones. Bind poses are taken from the
        // prefab's own pose (bindpose_i = bone_i.worldToLocal x part.localToWorld), so the part sits exactly where the rigid
        // build put it and moves with its bones from there.
        private static bool SkinPart(GameObject go, Mesh mesh, Part p, Dictionary<string, Transform> bones, Material[] mats, string id)
        {
            var tb = new Transform[p.skin.bones.Length];
            for (int i = 0; i < tb.Length; i++)
                if (!bones.TryGetValue(p.skin.bones[i], out tb[i])) { Jotunn.Logger.LogWarning($"[BlightedHeart] {id}/{p.name}: skin bone {p.skin.bones[i]} missing; left rigid"); return false; }
            if (p.skin.bi.Length != mesh.vertexCount) { Jotunn.Logger.LogWarning($"[BlightedHeart] {id}/{p.name}: {p.skin.bi.Length} weights for {mesh.vertexCount} vertices; left rigid"); return false; }
            var bw = new BoneWeight[mesh.vertexCount];
            for (int v = 0; v < bw.Length; v++)
            {
                int[] i4 = p.skin.bi[v]; float[] w4 = p.skin.bw[v];
                bw[v] = new BoneWeight { boneIndex0 = i4[0], boneIndex1 = i4[1], boneIndex2 = i4[2], boneIndex3 = i4[3],
                                         weight0 = w4[0], weight1 = w4[1], weight2 = w4[2], weight3 = w4[3] };
            }
            var bp = new Matrix4x4[tb.Length];
            Matrix4x4 l2w = go.transform.localToWorldMatrix;
            for (int i = 0; i < tb.Length; i++) bp[i] = tb[i].worldToLocalMatrix * l2w;
            mesh.boneWeights = bw;
            mesh.bindposes = bp;
            var smr = go.AddComponent<SkinnedMeshRenderer>();
            smr.sharedMesh = mesh;
            smr.bones = tb;
            smr.rootBone = go.transform.parent;
            smr.sharedMaterials = mats;
            smr.updateWhenOffscreen = false;
            Bounds b = mesh.bounds;                                         // bounds in the root bone's space, padded for motion
            b.center = smr.rootBone.InverseTransformPoint(go.transform.TransformPoint(b.center));
            b.extents = b.extents * 1.5f + Vector3.one * 0.05f;
            smr.localBounds = b;
            return true;
        }

        private static (Mesh, Material[]) Pick(List<(Mesh mesh, Material[] mats)> cands, string[] want)
        {
            if (want != null)
                foreach (var c in cands)
                    foreach (Material m in c.mats)
                        if (m != null && System.Array.IndexOf(want, m.name) >= 0) return c;
            return cands[0];
        }

        private static Material[] ResolveMaterials(string[] names, Material[] host)
        {
            if (names == null || names.Length == 0) return host;
            var outMats = new Material[names.Length];
            for (int i = 0; i < names.Length; i++)
                outMats[i] = names[i] != null && _materials.TryGetValue(names[i], out Material m) ? m : (i < host.Length ? host[i] : host[0]);
            return outMats;
        }

        // v_bone = L * v + residual, kept triangles only, submeshes kept apart (one material each).
        private static Mesh Bake(Mesh src, Part p, ref Material[] mats)
        {
            Vector3[] V = src.vertices; Vector3[] N = src.normals; Vector2[] UV = src.uv;
            var subTris = new List<int[]>();
            for (int s = 0; s < src.subMeshCount; s++) subTris.Add(src.GetTriangles(s));

            // the kept triangles, as (submesh, a, b, c), indexed into the concatenated submeshes
            var tris = new List<(int sub, int a, int b, int c)>();
            if (p.kept_tris == null)
            {
                for (int s = 0; s < subTris.Count; s++)
                    for (int i = 0; i < subTris[s].Length; i += 3) tris.Add((s, subTris[s][i], subTris[s][i + 1], subTris[s][i + 2]));
            }
            else
            {
                var offs = new int[subTris.Count + 1];
                for (int s = 0; s < subTris.Count; s++) offs[s + 1] = offs[s] + subTris[s].Length / 3;
                foreach (int t in p.kept_tris)
                {
                    int s = 0; while (t >= offs[s + 1]) s++;
                    int i = (t - offs[s]) * 3;
                    tris.Add((s, subTris[s][i], subTris[s][i + 1], subTris[s][i + 2]));
                }
            }

            // vertex set: sorted unique (matches the compiler's island remap) or all
            var used = new SortedSet<int>();
            if (p.kept_tris == null) for (int i = 0; i < V.Length; i++) used.Add(i);
            else foreach (var t in tris) { used.Add(t.a); used.Add(t.b); used.Add(t.c); }
            var remap = new Dictionary<int, int>(); var vi = new List<int>(used);
            for (int n = 0; n < vi.Count; n++) remap[vi[n]] = n;

            float[][] L = p.L;
            var lin = new Matrix4x4();
            lin.SetRow(0, new Vector4(L[0][0], L[0][1], L[0][2], L[0][3]));
            lin.SetRow(1, new Vector4(L[1][0], L[1][1], L[1][2], L[1][3]));
            lin.SetRow(2, new Vector4(L[2][0], L[2][1], L[2][2], L[2][3]));
            lin.SetRow(3, new Vector4(0, 0, 0, 1));
            Matrix4x4 nrm = lin.inverse.transpose;

            var nv = new Vector3[vi.Count]; var nn = new Vector3[vi.Count]; var nuv = new Vector2[vi.Count];
            for (int n = 0; n < vi.Count; n++)
            {
                int o = vi[n];
                Vector3 v = lin.MultiplyPoint3x4(V[o]);
                if (p.residual != null) v += new Vector3(p.residual[n][0], p.residual[n][1], p.residual[n][2]);
                nv[n] = v;
                if (N != null && N.Length == V.Length) nn[n] = nrm.MultiplyVector(N[o]).normalized;
                if (UV != null && UV.Length == V.Length) nuv[n] = UV[o];
            }

            // stage 4: the approved smooth subdivision (Gorgemaw DENSE lumps): each added vertex = the midpoint of its parent edge
            // + our offset (bone-local), UVs interpolated; the scene's triangles replace the source ones (one material)
            if (p.subdiv != null)
            {
                int n0 = nv.Length, add = p.subdiv.mids.Length;
                System.Array.Resize(ref nv, n0 + add); System.Array.Resize(ref nn, n0 + add); System.Array.Resize(ref nuv, n0 + add);
                for (int j = 0; j < add; j++)
                {
                    float[] m = p.subdiv.mids[j]; int a = (int)m[0], b = (int)m[1];
                    nv[n0 + j] = (nv[a] + nv[b]) * 0.5f + new Vector3(m[2], m[3], m[4]);
                    nuv[n0 + j] = (nuv[a] + nuv[b]) * 0.5f;
                    nn[n0 + j] = (nn[a] + nn[b]).normalized;
                }
                int sub0 = tris.Count > 0 ? tris[0].sub : 0;
                var subMesh = new Mesh { name = "BSB_" + p.name };
                subMesh.vertices = nv; subMesh.normals = nn; subMesh.uv = nuv;
                subMesh.SetTriangles(p.subdiv.tris, 0);
                mats = new[] { sub0 < mats.Length ? mats[sub0] : mats[0] };
                subMesh.RecalculateNormals(); subMesh.RecalculateTangents(); subMesh.RecalculateBounds();
                return subMesh;
            }

            var mesh = new Mesh { name = "BSB_" + p.name };
            if (nv.Length > 65000) mesh.indexFormat = UnityEngine.Rendering.IndexFormat.UInt32;
            mesh.vertices = nv; mesh.normals = nn; mesh.uv = nuv;
            var subs = new SortedDictionary<int, List<int>>();
            foreach (var t in tris)
            {
                if (!subs.TryGetValue(t.sub, out var l)) subs[t.sub] = l = new List<int>();
                l.Add(remap[t.a]); l.Add(remap[t.b]); l.Add(remap[t.c]);
            }
            mesh.subMeshCount = subs.Count;
            var subMats = new List<Material>(); int k = 0;
            foreach (var kv in subs)
            {
                mesh.SetTriangles(kv.Value, k++);
                subMats.Add(kv.Key < mats.Length ? mats[kv.Key] : mats[mats.Length - 1]);
            }
            mats = subMats.ToArray();
            if (p.residual != null) mesh.RecalculateNormals();       // reshaped lumps: their normals follow the new surface
            mesh.RecalculateTangents();
            mesh.RecalculateBounds();
            return mesh;
        }
    }
}
