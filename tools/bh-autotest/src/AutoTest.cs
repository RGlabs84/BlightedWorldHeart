// BHAutoTest: drives the real Valheim CLIENT unattended through BlightedHeart's in-game checks, in a single-player world
// (the host IS the server, so the Heart's owner logic runs in this process). Inert unless BH_AUTOTEST_OUT is set.
// Ported from Runic's tools/runic-autotest (the Runic playbook, owner 2026-11-22), which ported BCAutoTest.
// Ported from Better Continents' BCAutoTest (tools/_precedent/bc-autotest/BCAutoTest/Plugin.cs: the wait for
// FejdStartup, the profile, the world load without menus, the mute, the console capture, Flat, the screenshots) and
// DwarvenDefender's DDPlaytest (no engine setting touched from Awake, reflection screenshots, kill as the last resort).
// Facts: libs-Tools/VALHEIM-CLIENT-TEST-DRIVER-FACTS.md.
//
// Phases (README.md): A boot, W world, S the six Sub-Bosses' art, F faction, H the Heart end to end.
// Every phase logs PASS / FAIL / WARN / SKIP / INFO lines to <out>/results.tsv + results.txt (and the BepInEx log),
// runs inside Flat (an exception fails that phase, never the run), and a hard overall timeout quits the game.
using System;
using System.Collections;
using System.Collections.Generic;
using System.Globalization;
using System.IO;
using System.Linq;
using System.Reflection;
using BepInEx;
using BepInEx.Logging;
using HarmonyLib;
using UnityEngine;

namespace BHAutoTest
{
    [BepInPlugin("wubarrk.bhautotest", "BH AutoTest", "0.1.0")]
    [BepInDependency("wubarrk.blightedworldheart")]
    public partial class AutoTest : BaseUnityPlugin
    {
        internal static string Out, Img;
        internal static ManualLogSource L;
        internal static AutoTest Self;
        internal static Harmony H;
        static readonly CultureInfo IC = CultureInfo.InvariantCulture;

        static readonly List<string> results = new List<string>();
        static int pass, fail, warn, skip;
        static string phase = "-";
        static bool finished;
        static float timeoutSeconds = 1800f;
        static DateTime startedUtc;
        static Coroutine mainRoutine;

        const string WorldName = "BHAutoTest";
        const string WorldSeed = "BlightTest01";
        const string CharacterFile = "runicautotest";

        void Awake()
        {
            Out = Environment.GetEnvironmentVariable("BH_AUTOTEST_OUT");
            L = Logger;
            if (string.IsNullOrEmpty(Out))
            {
                Logger.LogInfo("BHAutoTest is inert: BH_AUTOTEST_OUT is not set.");
                return;
            }
            Self = this;
            startedUtc = DateTime.UtcNow;
            Img = Path.Combine(Out, "img");
            Directory.CreateDirectory(Out);
            Directory.CreateDirectory(Img);
            if (float.TryParse(Environment.GetEnvironmentVariable("BH_AUTOTEST_TIMEOUT") ?? "", NumberStyles.Float, IC, out float t) && t > 60f)
                timeoutSeconds = t;

            ErrorWatch.Install();
            H = new Harmony("wubarrk.bhautotest");
            Patch(typeof(Terminal), nameof(Terminal.AddString), new[] { typeof(string) }, postfix: nameof(OnConsolePostfix));
            Patch(typeof(Player), nameof(Player.Message), new[] { typeof(MessageHud.MessageType), typeof(string), typeof(int), typeof(Sprite), typeof(bool) }, postfix: nameof(OnMessagePostfix));

            // Last resort if the main thread itself hangs: a plain thread kills the process (the launcher kills too).
            var backstop = new System.Threading.Thread(() =>
            {
                System.Threading.Thread.Sleep(TimeSpan.FromSeconds(timeoutSeconds + 120f));
                try { File.AppendAllText(Path.Combine(Out, "driver.log"), "backstop: the game did not quit in time; killing it\n"); } catch { }
                System.Diagnostics.Process.GetCurrentProcess().Kill();
            }) { IsBackground = true, Name = "BHAutoTest backstop" };
            backstop.Start();

            // Nothing that touches the engine runs here (DDPlaytest: setting engine state from Awake crashed the
            // graphics thread). Main waits for FejdStartup first.
            mainRoutine = StartCoroutine(Main());
            StartCoroutine(Watchdog());
        }

        // ------------------------------------------------------------------------------------------ logging and results

        static string T => Time.realtimeSinceStartup.ToString("0.0", IC).PadLeft(7);

        internal static void Log(string s)
        {
            L.LogInfo(s);
            try { File.AppendAllText(Path.Combine(Out, "driver.log"), $"[{T}] {s}\n"); } catch { }
        }

        internal static void Result(string verdict, string name, string detail)
        {
            switch (verdict)
            {
                case "PASS": pass++; break;
                case "FAIL": fail++; break;
                case "WARN": warn++; break;
                case "SKIP": skip++; break;
            }
            detail = (detail ?? "").Replace("\r", " ").Replace("\n", " | ").Replace("\t", " ");
            string line = $"{verdict}\t{phase}\t{name}\t{detail}";
            results.Add(line);
            Log("RESULT " + line);
            try
            {
                File.WriteAllText(Path.Combine(Out, "results.tsv"), "verdict\tphase\tcheck\tdetail\n" + string.Join("\n", results) + "\n");
                File.WriteAllText(Path.Combine(Out, "results.txt"), Summary() + "\n\n" + string.Join("\n", results.Select(Pretty)) + "\n");
            }
            catch { }
        }

        static string Pretty(string tsv)
        {
            var c = tsv.Split('\t');
            return c.Length < 4 ? tsv : $"{c[0],-4}  {c[1]}  {c[2]}: {c[3]}";
        }

        static string Summary() =>
            $"BHAutoTest: {pass} pass, {fail} fail, {warn} warn, {skip} skip (phase {phase}, {(DateTime.UtcNow - startedUtc).TotalSeconds:0} s)";

        internal static void Check(bool ok, string name, string detail) => Result(ok ? "PASS" : "FAIL", name, detail);

        static readonly List<string> consoleLines = new List<string>();
        static int ConsoleMark() { lock (consoleLines) return consoleLines.Count; }
        static List<string> ConsoleSince(int mark) { lock (consoleLines) return consoleLines.Skip(mark).ToList(); }

        static void OnConsolePostfix(string text)
        {
            if (Out == null || text == null) return;
            lock (consoleLines) consoleLines.Add(text);
            try { File.AppendAllText(Path.Combine(Out, "console.log"), $"[{T}] {text}\n"); } catch { }
        }

        static readonly List<string> messages = new List<string>();
        static void OnMessagePostfix(Player __instance, MessageHud.MessageType type, string msg)
        {
            if (Out == null || __instance != Player.m_localPlayer || string.IsNullOrEmpty(msg)) return;
            string shown = Localization.instance != null ? Localization.instance.Localize(msg) : msg;
            lock (messages) messages.Add(shown);
            try { File.AppendAllText(Path.Combine(Out, "messages.log"), $"[{T}] {type}: {shown}\n"); } catch { }
        }
        static int MessageMark() { lock (messages) return messages.Count; }
        static List<string> MessagesSince(int mark) { lock (messages) return messages.Skip(mark).ToList(); }

        static void Patch(Type type, string method, Type[] args, string prefix = null, string postfix = null, string finalizer = null)
        {
            try
            {
                MethodInfo target = args != null ? AccessTools.Method(type, method, args) : AccessTools.Method(type, method);
                if (target == null) { Log($"patch: {type.Name}.{method} not found"); return; }
                H.Patch(target,
                    prefix: prefix != null ? new HarmonyMethod(typeof(AutoTest), prefix) : null,
                    postfix: postfix != null ? new HarmonyMethod(typeof(AutoTest), postfix) : null,
                    finalizer: finalizer != null ? new HarmonyMethod(typeof(AutoTest), finalizer) : null);
            }
            catch (Exception e)
            {
                Log($"patch {type.Name}.{method} failed: {e}");
            }
        }

        static void Cmd(string text)
        {
            Log("> " + text);
            try { Console.instance.TryRunCommand(text, false, true); }
            catch (Exception e) { Log("command threw: " + e); }
        }

        // ------------------------------------------------------------------------------------------ coroutine helpers

        /// <summary>Set by <see cref="WaitFor"/>: did the condition come true before the timeout?</summary>
        static bool waitOk;

        static IEnumerator WaitFor(Func<bool> cond, float timeout)
        {
            float start = Time.realtimeSinceStartup;
            while (true)
            {
                bool ok = false;
                try { ok = cond(); } catch { }
                if (ok) { waitOk = true; yield break; }
                if (Time.realtimeSinceStartup - start > timeout) { waitOk = false; yield break; }
                yield return null;
            }
        }

        static IEnumerator Sec(float s) { yield return new WaitForSecondsRealtime(s); }

        /// <summary>BCAutoTest's Flat (PhaseQ.Helpers.cs): runs nested IEnumerators on one Unity coroutine, catching an
        /// exception at any depth, so a throwing check ends its phase with a FAIL line instead of killing the run.</summary>
        static IEnumerator Flat(IEnumerator inner, string what)
        {
            var stack = new Stack<IEnumerator>();
            stack.Push(inner);
            while (stack.Count > 0)
            {
                if (finished) yield break;   // the watchdog is quitting: stop issuing commands
                object current = null;
                bool more;
                try
                {
                    more = stack.Peek().MoveNext();
                    if (more) current = stack.Peek().Current;
                }
                catch (Exception e)
                {
                    Result("FAIL", what + " threw", e.ToString());
                    yield break;
                }
                if (!more) { stack.Pop(); continue; }
                if (current is IEnumerator nested) { stack.Push(nested); continue; }
                yield return current;
            }
        }

        /// <summary>One phase: its own name on every result line, run in Flat, then the error lines the game logged during it.</summary>
        IEnumerator RunPhase(string name, string title, Func<IEnumerator> body)
        {
            phase = name;
            Log($"==== phase {name}: {title}");
            int mark = ErrorWatch.Mark();
            float t0 = Time.realtimeSinceStartup;
            IEnumerator e = null;
            try { e = body(); }
            catch (Exception ex) { Result("FAIL", "phase setup", ex.ToString()); }
            if (e != null) yield return StartCoroutine(Flat(e, "phase " + name));
            ReportErrors(mark, "log during phase " + name);
            Log($"==== phase {name} done in {Time.realtimeSinceStartup - t0:0.0} s");
        }

        static void ReportErrors(int mark, string label)
        {
            List<string> lines = ErrorWatch.Since(mark);
            List<string> runic = lines.Where(ErrorWatch.MentionsMod).ToList();
            if (runic.Count > 0)
                Result("FAIL", label, $"{runic.Count} BlightedHeart error/exception line(s): " + string.Join(" || ", runic.Take(4).Select(Short)));
            else if (lines.Count > 0)
                Result("INFO", label, $"no BlightedHeart errors; {lines.Count} other error line(s): " + string.Join(" || ", lines.Take(3).Select(Short)));
            else
                Result("PASS", label, "no error or exception lines");
        }

        static string Short(string s) => s.Length > 400 ? s.Substring(0, 400) + "..." : s;

        // ------------------------------------------------------------------------------------------ main

        static bool inWorld;

        IEnumerator Main()
        {
            Log($"BHAutoTest: results in {Out}; overall timeout {timeoutSeconds:0} s");
            yield return WaitFor(() => FejdStartup.instance != null, 300f);
            if (!waitOk)
            {
                Result("FAIL", "main menu", "FejdStartup never appeared within 300 s");
                yield return Quit();
                yield break;
            }
            StartCoroutine(Mute());
            yield return new WaitForSecondsRealtime(4f);

            yield return RunPhase("A", "boot", PhaseA);
            yield return RunPhase("W", "into a single-player world", EnterWorld);

            var phases = new (string, string, Func<IEnumerator>)[]
            {
                ("S", "the six Hive Sub-Bosses: parts on their bones, materials, tint, screenshots", PhaseS),
                ("F", "the Blighted faction: IsEnemy matrix and a live mixed-faction watch", PhaseF),
                ("H", "the Heart end to end: wave, both Sub-Bosses through SpawnSubBoss, death and loot", PhaseH),
            };
            // BH_AUTOTEST_ONLY=GI (phase letters) runs only those phases after A and W.
            string only = Environment.GetEnvironmentVariable("BH_AUTOTEST_ONLY");
            foreach (var (name, title, body) in phases)
            {
                if (finished) yield break;
                if (!string.IsNullOrEmpty(only) && only.IndexOf(name, StringComparison.OrdinalIgnoreCase) < 0)
                {
                    phase = name;
                    Result("SKIP", title, $"not selected (BH_AUTOTEST_ONLY={only})");
                    continue;
                }
                if (!inWorld || Player.m_localPlayer == null)
                {
                    phase = name;
                    Result("SKIP", title, "not in a world (phase W failed)");
                    continue;
                }
                yield return RunPhase(name, title, body);
            }
            phase = "end";
            ReportErrors(0, "log over the whole run");
            yield return Quit();
        }

        static void WriteDone(string why)
        {
            try { File.WriteAllText(Path.Combine(Out, "done.txt"), Summary() + (why != null ? " - " + why : "") + "\n"); } catch { }
            Log("DONE " + Summary() + (why != null ? " - " + why : ""));
        }

        /// <summary>Results final, then leave cleanly: Logout (saves, back to the menu), Application.Quit, and Kill if the
        /// game is still up 30 s later.</summary>
        IEnumerator Quit(string why = null)
        {
            if (finished) yield break;
            finished = true;
            WriteDone(why);
            if (Game.instance != null && Player.m_localPlayer != null)
            {
                Log("logging out");
                try { Game.instance.Logout(true, true); } catch (Exception e) { Log("logout threw: " + e.Message); }
                float t0 = Time.realtimeSinceStartup;
                while (ZNet.instance != null && Time.realtimeSinceStartup - t0 < 60f) yield return new WaitForSecondsRealtime(0.5f);
                yield return new WaitForSecondsRealtime(2f);
            }
            Log("Application.Quit");
            Application.Quit();
            yield return new WaitForSecondsRealtime(30f);
            Log("still running 30 s after Quit: killing the process");
            System.Diagnostics.Process.GetCurrentProcess().Kill();
        }

        IEnumerator Watchdog()
        {
            while (!finished)
            {
                if ((DateTime.UtcNow - startedUtc).TotalSeconds > timeoutSeconds)
                {
                    Result("FAIL", "overall timeout", $"still running after {timeoutSeconds:0} s (in phase {phase}); quitting");
                    if (mainRoutine != null) StopCoroutine(mainRoutine);
                    yield return Quit("overall timeout");
                    yield break;
                }
                yield return new WaitForSecondsRealtime(1f);
            }
        }

        IEnumerator Mute()
        {
            while (true)
            {
                AudioListener.volume = 0f;
                yield return new WaitForSecondsRealtime(0.5f);
            }
        }

        // ------------------------------------------------------------------------------------------ screenshots

        static MethodInfo captureMethod;

        /// <summary>A 1280 x 720 PNG (the window size) in &lt;out&gt;/img, HUD hidden. ScreenCapture through reflection:
        /// UnityEngine.ScreenCaptureModule is not in libs-Tools (DDPlaytest).</summary>
        static IEnumerator Shot(string name, Vector3? lookAt = null, bool keepHud = false)
        {
            Player p = Player.m_localPlayer;
            if (p != null && lookAt.HasValue) AimAt(lookAt.Value);
            bool hid = false;
            if (!keepHud && Hud.instance != null && !Hud.instance.m_userHidden) { Hud.instance.m_userHidden = true; hid = true; }
            yield return new WaitForSecondsRealtime(0.4f);
            string path = Path.Combine(Img, name + ".png");
            try
            {
                if (captureMethod == null)
                {
                    Type sc = Type.GetType("UnityEngine.ScreenCapture, UnityEngine.ScreenCaptureModule");
                    captureMethod = sc?.GetMethod("CaptureScreenshot", new[] { typeof(string) });
                }
                if (captureMethod == null) Log("screenshot: ScreenCapture not found");
                else captureMethod.Invoke(null, new object[] { path });
            }
            catch (Exception e) { Log("screenshot failed: " + e.Message); }
            yield return new WaitForSecondsRealtime(0.8f);
            if (hid && Hud.instance != null) Hud.instance.m_userHidden = false;
            Log("screenshot " + path + (File.Exists(path) ? "" : " (not written yet)"));
        }
    }

    /// <summary>Every error, fatal, and exception line any BepInEx log source (Unity's included) writes while the driver
    /// runs. Lines written before the driver loaded (BlightedHeart's own Awake and prefab setup) are read back from LogOutput.log in phase A.</summary>
    internal sealed class ErrorWatch : ILogListener
    {
        static readonly List<string> lines = new List<string>();
        static bool installed;

        internal static void Install()
        {
            if (installed) return;
            installed = true;
            BepInEx.Logging.Logger.Listeners.Add(new ErrorWatch());
        }

        internal static int Mark() { lock (lines) return lines.Count; }
        internal static List<string> Since(int mark) { lock (lines) return lines.Skip(mark).ToList(); }

        internal static bool IsBad(LogLevel level, string text)
        {
            if ((level & (LogLevel.Error | LogLevel.Fatal)) != 0) return true;
            return text.IndexOf("Exception", StringComparison.Ordinal) >= 0 || text.IndexOf("Feature Lost", StringComparison.Ordinal) >= 0;
        }

        internal static bool MentionsMod(string line) =>
            (line.IndexOf("Blighted", StringComparison.OrdinalIgnoreCase) >= 0 || line.IndexOf("BSB_", StringComparison.Ordinal) >= 0)
            && line.IndexOf("BHAutoTest", StringComparison.Ordinal) < 0;

        public void LogEvent(object sender, LogEventArgs e)
        {
            try
            {
                string text = e.Data?.ToString() ?? "";
                if (!IsBad(e.Level, text)) return;
                string src = e.Source?.SourceName ?? "?";
                if (src == "BH AutoTest" && (e.Level & (LogLevel.Error | LogLevel.Fatal)) == 0) return;   // our own RESULT lines quote exceptions
                string line = $"[{e.Level}:{src}] {text}";
                lock (lines) lines.Add(line);
                if (AutoTest.Out != null)
                    File.AppendAllText(Path.Combine(AutoTest.Out, "errors.log"), line + "\n");
            }
            catch { }
        }

        public void Dispose() { }
    }
}
