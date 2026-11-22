#!/bin/bash
# Headless dedicated-server smoke test for BlightedHeart (ported from MagicRunicMod tools/server-smoke.sh, the Runic playbook).
# Boots the Steam 1.0 dedicated server in place with BepInEx 5.4.2360 from ~/valheim-testbed/profile-blightedheart (fresh every
# run: the BepInEx core from libs-Tools' pack, Jotunn, the built DLL), a THROWAWAY HOME on the launch line
# (~/valheim-testbed/run-runic-server.sh, generic), waits for the world, stops it with SIGTERM (never -9: that skips the save),
# and proves the player's own prefs were not touched (hash before/after).
#
# ALWAYS run through the machine's heavy-job gate:
#   ~/valheim-testbed/heavy.sh 6G bh-server tools/server-smoke.sh [seconds]
set -u
TB="$HOME/valheim-testbed"
LT="${LIBS_TOOLS:-$HOME/WubarrkCODING/libs-Tools}"
MOD="$(cd "$(dirname "$0")/.." && pwd)"
DLL="$MOD/bin/Release/net48/BlightedHeart.dll"
JOTUNN_DIR="${BH_JOTUNN_DIR:-$TB/compat/plugins/ValheimModding-Jotunn}"
export PROFILE="$TB/profile-blightedheart" SAVES="$TB/saves-blightedheart" DOORSTOP="$TB/doorstop_libs-5.4.2360"
export LOG="$TB/blightedheart-server-console.log" NAME="BlightedHeartSmoke" PORT=2534 WORLD="BlightedDedi" PASSWORD="blighted123"
WAIT="${1:-240}"
BEPLOG="$PROFILE/BepInEx/LogOutput.log"
PACKDIR="$TB/autotest-blightedheart/pack/BepInExPack_Valheim"

ss -ltnu 2>/dev/null | grep -q ":$PORT " && { echo "smoke: port $PORT is in use: not starting"; exit 3; }
[ -f "$PACKDIR/BepInEx/core/BepInEx.Preloader.dll" ] || { mkdir -p "$TB/autotest-blightedheart/pack"; (cd "$TB/autotest-blightedheart/pack" && unzip -q -o "$LT/denikson-BepInExPack_Valheim-5.4.2360.zip"); }
for f in "$DLL" "$JOTUNN_DIR/Jotunn.dll" "$PACKDIR/BepInEx/core/BepInEx.Preloader.dll" "$TB/run-runic-server.sh"; do [ -e "$f" ] || { echo "smoke: missing $f"; exit 2; }; done
rm -rf "${PROFILE:?}"
mkdir -p "$PROFILE/BepInEx/plugins/Wubarrk-BlightedWorldHeart" "$PROFILE/BepInEx/config" "$PROFILE/BepInEx/patchers" "$SAVES"
cp -r "$PACKDIR/BepInEx/core" "$PROFILE/BepInEx/"
cp "$DLL" "$PROFILE/BepInEx/plugins/Wubarrk-BlightedWorldHeart/"
cp -r "$JOTUNN_DIR" "$PROFILE/BepInEx/plugins/ValheimModding-Jotunn"
PREFS="$HOME/.config/unity3d/IronGate/Valheim"
before=$(find "$PREFS" -maxdepth 1 -type f -exec md5sum {} + 2>/dev/null | sort | md5sum)
: > "$LOG"; rm -f "$BEPLOG"

"$TB/run-runic-server.sh" &
PID=$!
echo "smoke: server pid $PID, port $PORT, waiting up to ${WAIT}s"
ready=0
for ((i = 0; i < WAIT; i += 5)); do
  sleep 5
  kill -0 "$PID" 2>/dev/null || { echo "smoke: server exited early"; break; }
  if grep -q -E "Game server connected|Done generating locations|Opened Steam server" "$LOG" 2>/dev/null; then
    ready=1; echo "smoke: server up after ~${i}s; letting zones settle 30 s"; sleep 30; break
  fi
done
if kill -0 "$PID" 2>/dev/null; then
  SRV=$(pgrep -f "valheim_server.x86_64.*-port $PORT" | head -1)
  [ -n "$SRV" ] && kill -TERM "$SRV"
  for ((i = 0; i < 60; i++)); do kill -0 "$PID" 2>/dev/null || break; sleep 1; done
  kill -0 "$PID" 2>/dev/null && { echo "smoke: still running after 60 s, SIGTERM again"; kill -TERM "$SRV" 2>/dev/null; sleep 10; }
fi
after=$(find "$PREFS" -maxdepth 1 -type f -exec md5sum {} + 2>/dev/null | sort | md5sum)

echo "==== ready=$ready"
echo "==== BlightedHeart lines (BepInEx log)"
grep -a -E "Blighted" "$BEPLOG" 2>/dev/null | head -40
echo "==== errors / exceptions (BepInEx log)"
grep -a -n -E "\[Error|\[Fatal|Exception|NullReference" "$BEPLOG" 2>/dev/null | head -40
echo "==== server console: key lines"
grep -a -E "Game server connected|World saved|Done generating|Opened Steam|exception|Exception" "$LOG" 2>/dev/null | head -20

NMOD=$(grep -a -c -E "BlightedWorldHeart v[0-9.]+ loaded" "$BEPLOG" 2>/dev/null); NERR=$(grep -a -c -E "\[Error|\[Fatal|Exception|NullReference" "$BEPLOG" 2>/dev/null)
NSB=$(grep -a -c "Sub-Boss prefab BlightedSB_.* registered" "$BEPLOG" 2>/dev/null)
WHY=""
[ -f "$BEPLOG" ] || WHY="no BepInEx log: BepInEx never started"
[ -z "$WHY" ] && [ "$ready" = 0 ] && WHY="the world never came up within ${WAIT}s"
[ -z "$WHY" ] && [ "${NMOD:-0}" -eq 0 ] && WHY="no 'BlightedWorldHeart v... loaded' line: the plugin never loaded"
grep -a -q "World saved" "$LOG" 2>/dev/null || SAVENOTE="     note: no 'World saved' line, so the shutdown save was not seen"
PREFSBAD=""; [ "$before" != "$after" ] && PREFSBAD=1
NEWER=$(find "$MOD" -maxdepth 1 -name '*.cs' -newer "$DLL" 2>/dev/null | head -3 | tr '\n' ' ')
if [ "${NERR:-0}" -gt 0 ] || [ -n "$PREFSBAD" ]; then V=FAIL; elif [ -n "$WHY" ]; then V="NOT ASSESSED"; else V=PASS; fi
echo "==== VERDICT: $V  (loaded ${NMOD:-0}, ${NSB:-0} of 6 Sub-Boss prefabs registered, ${NERR:-0} error lines in the BepInEx log; ready=$ready; player prefs $([ -n "$PREFSBAD" ] && echo CHANGED || echo untouched))"
[ -n "$WHY" ] && echo "     not assessed because: $WHY"
[ -n "${SAVENOTE:-}" ] && echo "$SAVENOTE"
[ -n "$NEWER" ] && echo "     WARNING: source is newer than the tested DLL (e.g. $NEWER)"
case "$V" in PASS) exit 0 ;; FAIL) exit 1 ;; *) exit 4 ;; esac
