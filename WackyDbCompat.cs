using System;
using System.Collections.Generic;
using System.IO;
using BepInEx;

namespace BlightedHeart
{
    /// <summary>
    /// Read-only view of which recipes Wacky's Database has a YAML for on this machine.
    ///
    /// WackyDB keeps one YAML per recipe under BepInEx/config/wackysDatabase/Recipes/ (subfolders allowed) and
    /// identifies the recipe by the file's top-level "name:" key, e.g. "name: Recipe_SwordBronze" - the file name
    /// is only a convention. Jotunn names every Blighted recipe "Recipe_&lt;prefab&gt;", so an admin-authored YAML for
    /// one reads "name: Recipe_BlightedSwamp_SwordIron_Blight". Any recipe found here belongs to the admin: we
    /// never inject upgrade materials on top of it.
    /// </summary>
    public static class WackyDbCompat
    {
        private const string RecipesFolder = "Recipes";

        private static HashSet<string> _recipeYamlNames;

        public static string RecipesDir => Path.Combine(Paths.ConfigPath, "wackysDatabase", RecipesFolder);

        /// <summary>True if a WackyDB recipe YAML on disk names this recipe (case-insensitive).</summary>
        public static bool HasRecipeYaml(string recipeName)
        {
            if (string.IsNullOrEmpty(recipeName)) return false;
            if (_recipeYamlNames == null) _recipeYamlNames = LoadRecipeYamlNames();
            return _recipeYamlNames.Contains(recipeName);
        }

        /// <summary>Number of recipe YAMLs found on disk (scans on first call, cached for the session).</summary>
        public static int RecipeYamlCount
        {
            get
            {
                if (_recipeYamlNames == null) _recipeYamlNames = LoadRecipeYamlNames();
                return _recipeYamlNames.Count;
            }
        }

        private static HashSet<string> LoadRecipeYamlNames()
        {
            var names = new HashSet<string>(StringComparer.OrdinalIgnoreCase);
            string dir = RecipesDir;

            try
            {
                if (!Directory.Exists(dir)) return names;

                foreach (string file in Directory.EnumerateFiles(dir, "*.y*ml", SearchOption.AllDirectories))
                {
                    string ext = Path.GetExtension(file);
                    if (!ext.Equals(".yml", StringComparison.OrdinalIgnoreCase) &&
                        !ext.Equals(".yaml", StringComparison.OrdinalIgnoreCase))
                        continue;

                    string name = ReadTopLevelName(file);
                    // No usable "name:" key - fall back to the file name, which is what WackyDB's own
                    // print commands use, so the two agree for every file an admin didn't hand-rename.
                    if (string.IsNullOrEmpty(name)) name = Path.GetFileNameWithoutExtension(file);
                    if (!string.IsNullOrEmpty(name)) names.Add(name);
                }
            }
            catch (Exception ex)
            {
                Jotunn.Logger.LogWarning($"Could not scan WackyDB recipe YAMLs in '{dir}': {ex.Message}");
            }

            return names;
        }

        // First top-level (column 0) "name:" key in the file. Nested keys, comments and blank lines are skipped;
        // a quoted value has its quotes stripped. Returns null if the file has no such key.
        private static string ReadTopLevelName(string file)
        {
            try
            {
                foreach (string raw in File.ReadLines(file))
                {
                    string line = raw.TrimStart('﻿');
                    if (line.Length == 0 || line[0] == ' ' || line[0] == '\t' || line[0] == '#' || line[0] == '-') continue;
                    if (!line.StartsWith("name", StringComparison.OrdinalIgnoreCase)) continue;

                    int colon = line.IndexOf(':');
                    if (colon < 0 || line.Substring(0, colon).Trim().Length != 4) continue;

                    string value = line.Substring(colon + 1);
                    int comment = value.IndexOf(" #", StringComparison.Ordinal);
                    if (comment >= 0) value = value.Substring(0, comment);
                    value = value.Trim().Trim('"', '\'').Trim();
                    return value.Length > 0 ? value : null;
                }
            }
            catch (Exception ex)
            {
                Jotunn.Logger.LogWarning($"Could not read WackyDB recipe YAML '{file}': {ex.Message}");
            }
            return null;
        }
    }
}
