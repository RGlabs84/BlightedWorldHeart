# The BarrkBOT contract — read before renaming or reshaping anything

**BarrkBOT reads this file off this server's local filesystem (`VALHEIM_SERVER_DIR`) via its
generic multi-mod scanner. It is an interface, not internal state.** Changing the filename or a
field name here breaks a program running in another repo (`WindowsDEV/Discord-BarrkBOT`, v6, at
the repo root) that has no way to find out.

| Path | Written by | BarrkBOT reads it as |
| :--- | :--- | :--- |
| `BepInEx/config/BlightedHeart/barrkbot_blightedheart.json` | `BarrkBotExport.cs` | per-biome raid state — is the Heart up right now, how healthy, and its lifetime summon/defeat history |

`BepInEx/config/BlightedHeart/stats.json` is this mod's own persistence (lifetime summon/defeat
counters, survives server restarts). BarrkBOT does **not** read it directly — the export above
carries the same numbers, and it's one less file for a generic scanner to have to know about.

## Why the shape is what it is

This export is **world/event-keyed, not player-keyed** — there's no per-player identity in a raid,
just "what is the Heart doing in each biome." Don't contort it into a fake `players` block to fit a
convention that doesn't apply here; BarrkBOT's reader already accounts for world-state exports.

**A biome that has never had a Heart summoned is OMITTED from `biomes` entirely** — never written
with zeroed fields. This is the rule TheRavensCall's contract exists to teach the hard way: a file
that exists and reads plausible beats a missing one, every time, at hiding a real absence. Once a
biome *does* have history, `0` is a genuine fact (e.g. "summoned twice, defeated zero times") and
gets written as `0` — the two cases must stay distinguishable on the read side, always.

Same principle for two fields specifically:
- `current_hp_percent` is `null` whenever `active` is `false` — never a fake `0`, which would read
  as "the Heart is dying" rather than "there is no Heart."
- `last_defeated` is `null` until a real defeat — **never epoch-0**, which renders as a date and is
  the worst kind of fabricated fact because it looks the most authoritative.

## Field names currently depended on

Top level: `generated_at`, `source`, `biomes`.

Per biome (only present if that biome has ever had a Heart): `active`, `current_hp_percent`,
`subboss_1_active`, `subboss_2_active`, `times_summoned`, `times_defeated`, `last_defeated`.

## Two things that are easy to get wrong here specifically, both already hit once this session

1. **The boss's own `CurrentBiome` field is not reliable off the server process.** It's set by
   `BlightedWorldHeartAI.Initialize()`, which only runs on whichever peer's client used the altar —
   fine in single-player or on a listen server, silently wrong (stuck at the enum default) on a real
   dedicated server, which is the one topology nobody tests first. The export reads biome from
   `Heightmap.FindBiome(transform.position)` instead, which is correct regardless of topology.
2. **`Character.OnDeath`-style hooks don't fire server-side for this boss either**, for the same
   underlying reason cataloged in `PAUSED/TheRavensCall-OLD-1.2.1/KILL_TRACKING_FINDINGS.md`: whichever peer
   currently owns the ZDO runs local simulation methods, and during an active fight that's normally
   the fighting player's client, not the dedicated server. `times_defeated` instead subscribes to
   `ZDOMan.instance.m_onZDODestroyed`, which is broadcast to every peer including the server once a
   destroy is confirmed network-wide, regardless of who owned the object — and it can't be confused
   with a zone unload (`RemoveObjects`), which removes the local GameObject but leaves the ZDO
   intact. `times_summoned` is the deliberately looser half: it's inferred from active-set
   transitions on the server's own periodic scan (the one thing in this file that's guaranteed to
   run on the server, being this mod's own coroutine), not from a spawn-event hook. **Consequence
   accepted, not a bug**: a Heart summoned and defeated entirely between two export ticks increments
   neither counter, and a server restart mid-fight can look like a new summon. `times_summoned` is
   therefore not exact in the way `times_defeated` is — don't present it as such.

## If you change any of this

1. **Say so in this file, in `HexiumDistrib/CHANGELOG.md`, and tell whoever is working on BarrkBOT.**
2. **Prefer adding a field over renaming one.** A new field costs BarrkBOT nothing; a renamed one
   silently zeroes a feature.
3. **If you must rename, write both names for one release, then delete the old one.** Don't leave a
   dead file sitting on disk after the overlap release ends — TheRavensCall's contract exists
   because BarrkBOT served 2.4-day-stale data from a file that had stopped being written but hadn't
   been deleted, with zero errors anywhere. A dead file that still parses is more dangerous than a
   missing one.
