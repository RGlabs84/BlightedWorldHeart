# BlightedHeart art: spec cards

Process: art-pipeline skill (model → owner approves shapes → texture/skin → owner approves final look). Nothing is
baked into a bundle or wired into the game before the final look is approved.

## Hive style sheet (shared by every sub-boss)

The Blighted World Heart is vanilla `TheHive` at 0.1 scale, tinted per biome at runtime (`ApplyBiomeVisuals`).
Reference renders and the exported vanilla textures: `art/subbosses/reference/` (`hive_sheet.png`; export and
render scripts in `reference/hive_tools/`, re-run against 1.0.21's `c4210710` bundle).

What the Hive is made of (measured from the prefab, 2026-11-21):
- **Body:** seven faceted, lumpy masses (`low`…`low (6)`, material `TheHive_Mat`): dark brown tree bark, tinted
  warm (`_Color` 1.0/0.83/0.46), moss on top (`_MossTex`). The lumps are fused, not smooth: big flat facets, deep
  creases between masses.
- **Timber:** twelve rough beams (`TheHive_Mat_legs`, pale grey-brown bark) forming a lashed ring around the body
  and splayed struts/legs reaching down.
- **Eyes:** small glowing spheres (`TheHive_Eye`, emission red-pink 1.43/0.0/0.10) set into the bark.
- **The growth:** six vanilla pines turned upside down with their trunks driven through the bark mass (bases at
  y 83–90, above the top of the body; tips at y 36–43, below it). No trunk or tree shape is seen: only the needles
  come out of the underside, as one dense, shaggy green clump hanging beneath the Hive. Plus drake heads
  (`Hatchling` meshes, green emission) buried in the body.

Rules for every sub-boss:
- Read as "a piece of the Hive that walks": lumpy faceted bark masses for the body, never smooth skin.
- At least one lashed timber element (ring, struts, ribs, pauldrons) echoing the Hive's legs.
- Glowing eye nodes in clusters, set INTO the bark (sockets, 2–6 mm proud rims), never floating.
- One growth, in the Hive's sense: dense shaggy needle clumps spilling out of creases and hanging beneath masses,
  with no trunks and no tree or sapling shapes (owner, 2026-11-21: "loose the trees, its more of a groth"). Drake heads
  also count.
- Blight glow: cracks/veins in their own slot, so the runtime biome tint can drive them like the Heart's.
- Material slots (same names on every model, assigned by NAME): `HiveBark`, `HiveTimber`, `HiveMoss`, `HiveEye`,
  `HiveFoliage`, `BlightGlow`. Placeholder colours for step-1 previews: HiveBark #5A4630, HiveTimber #9C8E78,
  HiveMoss #4F6B2E, HiveEye #FF2A40, HiveFoliage #2F5A2A, BlightGlow #7CFF3A.

Tone (owner, 2026-11-21: "make them 20% more evil look, 5% more sinister, 10% wtf is that coming after me"):
- evil: hunched, leading with the head, eyes glowing out of deep brows, big broken splinter teeth, hooked claws, jagged spikes;
- sinister: asymmetric eyes, a stray tiny eye in a crease, slit sockets;
- wtf: exactly ONE wrong feature per creature (Brute: chest-crack mouth; Gorgemaw: the howdah Hive is alive and watching;
  Rootstalker: split jaw or shoulder eye cluster; Seer: too-wide jaw hanging under the eye bulb; Husk: eye slit wraps
  all the way round plus a palm eye; Broodhusk: some brood cells hold eyes).

## METHOD (owner, 2026-11-21) - replaces the scratch-built models
Owner's words: "These models, honestly, they look like crap, and I would never sign off on them. If we're going to
repurpose the models, that's fine. We can control the color with tinting, but let's make sure that we're really
repurposing the model. Even if we have to go into the game, rip it out, and then come up with our own based on it."
and "not just recolored by Tinte. Added onto like the armor sets. And runic, yes."

So every sub-boss is built the way MagicRunicMod built its class armour (ASSET-001/002 there, final-approved 2026-11-18):
1. BASE = the real vanilla creature, cloned at runtime (mesh, rig, animations, attacks, AI). Not shipped by us.
2. REPAINT = the donor's own body texture repainted at runtime from OUR masks (bark/Hive palette, blight veins, emission
   mask), per biome tint on top. Not just a tint.
3. ADD-ONS = our own modelled Hive pieces (bark plates and lumps, eye clusters in sockets, the hanging growth, timber
   lashings, the one "wtf" feature), fitted against the REAL donor mesh in bind pose and attached to its bones (rigid
   per bone, or skinned with weights copied from the donor where a piece spans a joint). Shipped in our bundle.
4. Previews ALWAYS show the base in its real game texture (Runic lesson: clay lineups misled the owner), add-ons in
   placeholder slot colours at step 1, final textures at step 3. Fit is measured: add-on / base intersecting triangle
   pairs, and add-on clearance from the base surface.
REFINED 2026-11-21 after the first Husk pilot (hand-modelled add-ons read as cardboard glued on): the ADD-ONS are
VANILLA PARTS too, kitbashed the way TheHive itself is built (Hive bark lumps, Hive eyes, upside-down Pinetree_01 needles,
Hatchling heads, Root armour, Elder/Abomination roots, GuckSack...), each in its real game texture, placed on the donor's
bones. Shipped: only attach transforms (+ repaint masks); every mesh comes from the game at runtime. New geometry only for
tiny connective bits, named and justified. Survey: art/subbosses/kit_tools/vanilla_parts.tsv.
NO PINE, NO TREES IN ANY FORM (owner, 2026-11-21, said twice: "no pine, drop the trees, second time telling you"):
no Pinetree_01 or any tree mesh, not even upside-down needles as the Hive does it. The growth is vines, thorn roots,
Greydwarf roots, tentaroots and moss only.
PILOT RULINGS (owner, 2026-11-21: "yes, strip the shoulder pads, you're allowed to go into, sure as long as the end result
isn't jank"): Draugr Root-armour shoulder pads stripped; parts MAY sink into the base body; early skin repaint allowed for
the two pilots (my reading of "sure", stated to the owner). "Not jank" is checked by a 4-pose test with donor weights.
DIRECTION APPROVED (owner, 2026-11-21, on the Hive Brute v5 + Barkbound Husk v7 pilots): "yes, with branches".
Add bare gnarled woody branches sprouting from the crust (Elder-back style; no leaves, no needles, never a tree
silhouette). Fix each pilot's weak list, then roll the method out to 002 Wolf, 003 Lox, 004 Greydwarf_Shaman, 006 Seeker.
This approves the METHOD/direction, not the final shapes (gate 2 still per creature).
Runic's tools to reuse: ~/WubarrkCODING/MagicRunicMod/unity/blender/ (export_donor_textures.py, armor_attach.json,
make_armor.py, render_armor_previews.py, make_armor_repaint.py, apply_armor_repaint.py) and Features/Items/ArmorLook.cs,
ArmorRepaint (runtime repaint), lessons 25-32 in its DESIGN.md.
The scratch-built v1-v3 meshes in art/subbosses/ASSET-00N_*/ are SUPERSEDED (kept for reference only).
Pilots first: ASSET-001 (Troll) and ASSET-005 (Draugr); the other four wait for the owner's verdict on the pilots.

Rig rule: each sub-boss is our own mesh **skinned to a vanilla donor creature's skeleton** (bone names and bind pose
read from the game's data), so the donor's animations, attacks and AI work unchanged. Step-1 models are built around
the donor's bind-pose silhouette with edge loops at every joint. Sub-bosses spawn at 1.5× (`SpawnSubBoss`), so model at
the donor's native size.

---

## Sub-Boss integration (1.2.0, the Runic playbook; owner 2026-11-22)

Nothing of the game ships: our data is embedded in the DLL and the game's own meshes and textures are rebuilt at runtime, once per
Sub-Boss prefab, on clients only (a dedicated server builds the clones without visuals). A missing input falls back to the vanilla
look with one warning.
- **Clones** (`BlightedSubBosses.cs`): each Sub-Boss is a clone of its donor (moves, attacks, AI), never tameable or breeding.
- **Parts** (`BlightedSubBossKit.cs`, data `art/subbosses/runtime/<Id>.json` from `kit_tools/compile_runtime_kit.py`, which reads
  the APPROVED scenes): per part the vanilla source mesh (name + vertex count), its bone, and either a transform (meshes the game
  ships unreadable: eye_globe, ThornRoots) or L (3x4) + residuals + kept triangles; skinned parts get per-vertex weights (agent B:
  `transfer_weights.json`; agent A: the attach.json recipe, 4 nearest body vertices) and ride the donor's bones in a
  SkinnedMeshRenderer; the Gorgemaw's 4 smoothed lumps ship their subdivision (parent edge + offset per added vertex); the Husk's
  Root armour is the rebound ArmorRootChest/Legs (Player weights mapped to the Draugr, the skirt on the Draugr's thighs).
- **Materials** (`BlightedSubBossMaterials.cs`, table `runtime/materials.json`, checked by `kit_tools/check_material_table.py`:
  every part slot has an entry): our shared copies of the vanilla materials, linear values via SetVector (crust glow off, moss 0.5,
  weathered branches, eyes + brood cells on a Custom/Creature copy with our eye mask).
- **Body repaint** (`BlightedSubBossRepaint.cs` = `kit_tools/apply_subboss_repaint.py` line for line; maps from
  `kit_tools/make_repaint_maps.py` in `runtime/repaint/`): the reference rebuilds the six approved repaints from our maps to
  p99 <= 2.93/255 (2026-11-22); the in-game texture is within p99 4-16 / mean <= 2.3 of the reference (GPU resampling).
- **Biome tint** (`BlightedSubBossLook`): the Heart's biome colour MULTIPLIED onto each material's own colour (the approved
  "colour only" panel), no emission override.
- **Not done:** vertex colours (the Brute's fang root dirt, the Rootstalker's maw depth / canine gradient): the game's shaders do
  not read vertex colours; those parts ship their flat approved colour.
- **In-game check:** `tools/bh-autotest` (port of Runic's runic-autotest), see each card's IN GAME line.
- **In-game look approved** (owner 2026-11-22, on ~/valheim-testbed/autotest-blightedheart/review/run8_sheet.png + run8_walk.png,
  midday meadow, biome tint multiplied as approved: BF/Mistlands near-black, Meadows green): "they look fine". Tint stays as is.

## ASSET-001 Hive Brute (donor: Troll)                status: FINAL APPROVED (step 4, 2026-11-22, owner: "approved"); IN GAME: autotest PASS 97 of 97 on 2026-11-22 (run results-20261122-094136: 51 parts (1 skinned) on their bones, our materials, body repainted, biome tint, no broken shader, 0 error lines), screenshots ~/valheim-testbed/autotest-blightedheart/latest/img/S-*.png
- What it is / where it is seen: heavy melee sub-boss, seen at 5–25 m during a Heart fight.
- Reference: `art/subbosses/reference/hive_sheet.png`; donor `Troll` bind pose.
- Size: the Troll's bind-pose bounds (measure; recorded in the preview README).
- Budget: ≤ 12k tris (owner, 2026-11-21); six Hive slots; textures later (512–1024 px).
- Attach / origin: ground centre between the feet, +Y up, facing the donor's forward.
- Look: hunched giant. Torso is three fused bark lumps. Small head sunk between the shoulders with a triangle of three eye
  nodes. A shaggy needle growth spilling from the creases of the upper back and hanging down it, and a lashed timber ring round the waist like the Hive's
  leg ring. Forearms end in thick bark clubs with root fingers. Moss caps on the shoulders, and blight cracks across the chest.
- Measured 2026-11-21 (step 1, one mesh, six named slots, 1 UV channel): 8,700 / 10,000 tris; 11.11 × 6.73 × 4.16 m (T-pose; donor Troll 11.01 × 7.48 × 3.17 m, Body 4,652 + Hair 1,554 tris, 57 bones). Built in the Troll's REST frame: its bind pose faces −Z (rest = bind turned 180° about Y), so skinning must apply that turn. Previews: `art/subbosses/ASSET-001_*/previews/`.
- Measured 2026-11-21, after the 12k budget: v2 11,482 / 12,000 tris; 11.45 × 6.73 × 4.16 m (v1 8,700 kept in v1/).
- Measured 2026-11-21, v3 (trees → growth, tone add-on): 11,388 tris, 11.45 × 7.27 × 4.39 m; v2 kept in v2/.
- After review (2026-11-22): kitbash shape approved ("SHAPE only approved"). Geometry locked: kit/approved_shape_2026-11-22/. Step 3 = texture/material only.
- After review (2026-11-22): final look approved ("approved"). Biome tint: base colour only, like the Heart ("base color like the heart does"): _Color = biome tint, NO _EmissionColor override.
- Owner's words: "six different types of sub-bosses that the BlightedHearts can summon … take a look at the hive which
  the BlightedHeart is based on, just shrunk down. To incorporate that kind of style into the models." (2026-11-21)

## ASSET-002 Rootstalker (donor: Wolf)                status: FINAL APPROVED (step 4, 2026-11-22, owner: "approved"); IN GAME: autotest PASS 97 of 97 on 2026-11-22 (run results-20261122-094136: 51 parts (3 skinned) on their bones, our materials, body repainted, biome tint, no broken shader, 0 error lines), screenshots ~/valheim-testbed/autotest-blightedheart/latest/img/S-*.png
- What it is / where it is seen: fast quadruped hunter, seen at 3–20 m.
- Reference: hive sheet; donor `Wolf` bind pose.
- Size: Wolf bind-pose bounds.  Budget: ≤ 12k tris (owner, 2026-11-21).
- Attach / origin: ground centre, +Y up, donor forward.
- Look: lean body of twisted roots. Ribcage of arched timber struts over a hollow belly that shows a glowing blight core.
  Long bark head with eye nodes down each side of the snout (3–4 per side). Moss mane, and a tail of trailing roots.
- Measured 2026-11-21 (step 1, one mesh, six named slots, 1 UV channel): 5,938 / 6,000 tris; 0.56 × 1.36 × 2.90 m (donor Wolf 0.60 × 1.40 × 2.83 m, 1,962 tris, 34 bones). Added two haunch saplings (not on the card). Previews: `art/subbosses/ASSET-002_*/previews/`.
- Measured 2026-11-21, after the 12k budget: v2b 10,408 / 12,000 tris; 0.62 × 1.40 × 2.91 m (v1 5,938 in v1/, v2 8,178 in v2/).
- Measured 2026-11-21, v3 (trees → growth, tone add-on): 11,076 tris, 0.62 × 1.40 × 2.92 m; v2 kept in v2/.
- After review (2026-11-22), kitbash v1 on the real Wolf: throat mouth KEPT ("keep it but texture is better to better illistrate that its a mouth"): the repaint/texture must make the throat read clearly as a mouth.
- After review (2026-11-22): kitbash shape approved ("SHAPE only approved"). Geometry locked: kit/approved_shape_2026-11-22/. Step 3 = texture/material only.
- After review (2026-11-22): final look approved ("approved"). Biome tint: base colour only, like the Heart ("base color like the heart does"): _Color = biome tint, NO _EmissionColor override.
- Owner's words: as ASSET-001.

## ASSET-003 Gorgemaw (donor: Lox)                    status: FINAL APPROVED (step 4, 2026-11-22, owner: "approved"); IN GAME: autotest PASS 97 of 97 on 2026-11-22 (run results-20261122-094136: 49 parts (1 skinned, 4 smoothed lumps) on their bones, our materials, body repainted, biome tint, no broken shader, 0 error lines), screenshots ~/valheim-testbed/autotest-blightedheart/latest/img/S-*.png
- What it is / where it is seen: huge quadruped, seen at 8–30 m.
- Reference: hive sheet; donor `Lox` bind pose.
- Size: Lox bind-pose bounds.  Budget: ≤ 12k tris (owner, 2026-11-21).
- Attach / origin: ground centre, +Y up, donor forward.
- Look: its back carries a miniature Hive: a lumpy bark mass with timber struts and a shaggy needle growth hanging beneath it between the struts, like a howdah.
  Broad bark maw for a head. Two drake heads sprout from the shoulders, echoing the Hive's buried drakes, with green
  BlightGlow throats. Rows of eye nodes along the flanks.
- Measured 2026-11-21 (step 1, one mesh, six named slots, 1 UV channel): 9,100 / 12,000 tris; 4.14 × 4.35 × 6.46 m (donor Lox 3.99 × 4.29 × 7.24 m, Body 1,606 + Furr1 1,744 tris, 31 bones). Previews: `art/subbosses/ASSET-003_*/previews/`.
- Measured 2026-11-21, after the 12k budget: v2 11,172 / 12,000 tris; 4.14 × 4.35 × 6.46 m (v1 9,100 in v1/).
- Measured 2026-11-21, v3 (trees → growth, tone add-on): 11,720 tris, 4.06 × 4.35 × 6.60 m; v2 kept in v2/.
- After review (2026-11-22): kitbash v3 shape approved ("approved shape"). Geometry locked: kit/approved_shape_2026-11-22/. Step 3 = texture/material only.
- After review (2026-11-22): final look approved ("approved"). Biome tint: base colour only, like the Heart ("base color like the heart does"): _Color = biome tint, NO _EmissionColor override.
- Owner's words: as ASSET-001.

## ASSET-004 Eyeblight Seer (donor: Greydwarf_Shaman) status: FINAL APPROVED (step 4, 2026-11-22, owner: "approved"); IN GAME: autotest PASS 97 of 97 on 2026-11-22 (run results-20261122-094136: 53 parts (28 skinned) on their bones, our materials, body repainted, biome tint, no broken shader, 0 error lines), screenshots ~/valheim-testbed/autotest-blightedheart/latest/img/S-*.png
- What it is / where it is seen: small caster, seen at 5–20 m.
- Reference: hive sheet; donor `Greydwarf_Shaman` bind pose.
- Size: donor bind-pose bounds.  Budget: ≤ 12k tris (owner, 2026-11-21).
- Attach / origin: ground centre, +Y up, donor forward.
- Look: hunched. Its head is a lumpy bark bulb studded with 5–7 eye nodes of mixed sizes, with one large central eye.
  A timber strut grows out of one forearm like a staff, with a glowing blight knot at its tip. Mossy shawl over the
  shoulders, and foliage tassels hanging from the waist.
- Measured 2026-11-21 (step 1, one mesh, six named slots, 1 UV channel): 5,955 / 6,000 tris; 3.97 × 2.57 × 1.23 m (donor 3.76 × 2.87 × 1.18 m, 4 SMRs, 33 bones, no attach bones). Previews: `art/subbosses/ASSET-004_*/previews/`.
- Measured 2026-11-21, after the 12k budget: v2 8,148 / 12,000 tris; 3.85 × 2.57 × 1.31 m (v1 5,955 in v1/).
- Measured 2026-11-21, v3 (trees → growth, tone add-on): 10,725 tris, 3.92 × 2.57 × 1.44 m; v2 kept in v2/.
- After review (2026-11-22): kitbash shape approved ("SHAPE only approved"). Geometry locked: kit/approved_shape_2026-11-22/. Step 3 = texture/material only.
- After review (2026-11-22): final look approved ("approved"). Biome tint: base colour only, like the Heart ("base color like the heart does"): _Color = biome tint, NO _EmissionColor override.
- Owner's words: as ASSET-001.

## ASSET-005 Barkbound Husk (donor: Draugr)           status: FINAL APPROVED (step 4, 2026-11-22, owner: "approved"); IN GAME: autotest PASS 97 of 97 on 2026-11-22 (run results-20261122-094136: 61 parts (35 skinned; Root armour left off, owner) on their bones, our materials, body repainted, biome tint, no broken shader, 0 error lines), screenshots ~/valheim-testbed/autotest-blightedheart/latest/img/S-*.png
- What it is / where it is seen: armoured humanoid melee, seen at 3–15 m.
- Reference: hive sheet; donor `Draugr` bind pose.
- Size: donor bind-pose bounds.  Budget: ≤ 12k tris (owner, 2026-11-21).
- Attach / origin: ground centre, +Y up, donor forward. The right hand stays free for the donor's weapon attach.
- Look: humanoid encased in bark plates. Timber-plank pauldrons lashed with rope. The helm is a bark lump with a
  single horizontal slit of eye nodes. A needle growth spills from between the back plates, and blight veins glow at the plate seams.
- Measured 2026-11-21 (step 1, one mesh, six named slots, 1 UV channel): 6,216 / 8,000 tris; 1.70 × 2.31 × 1.04 m (donor 1.73 × 2.18 × 0.64 m, 1 SMR, 21 bones; VisEquipment Left/Right/HelmetAttach). Draugr bind pose faces −Z: check facing at skinning. Previews: `art/subbosses/ASSET-005_*/previews/`.
- Measured 2026-11-21, after the 12k budget: v2 11,243 / 12,000 tris; 1.71 × 2.85 × 1.38 m incl. 1.35 m sapling (v1 6,216 in v1/).
- Measured 2026-11-21, v3 (trees → growth, tone add-on): 11,900 tris, 1.71 × 2.25 × 0.88 m; v2 kept in v2/.
- After review (2026-11-22): kitbash shape approved ("SHAPE only approved"). Geometry locked: kit/approved_shape_2026-11-22/. Step 3 = texture/material only.
- After review (2026-11-22): final look approved ("approved"). Biome tint: base colour only, like the Heart ("base color like the heart does"): _Color = biome tint, NO _EmissionColor override.
- Owner's words: as ASSET-001.
- In game (2026-11-22): the game ships the Root armour meshes (RootArmorSkirt, RootArmorPants.005) UNREADABLE, so the cut +
  4 mm refit cannot be rebuilt at runtime. Owner decision 2026-11-22: "Leave it off" - 1.2.0 ships the Husk with its other 61
  approved parts and no Root armour (compile_runtime_kit.py leaves it out; BH_KIT_ROOT_ARMOUR=1 compiles it for a later route).

## ASSET-006 Broodhusk (donor: Seeker)                status: FINAL APPROVED (step 4, 2026-11-22, owner: "approved"); IN GAME: autotest PASS 97 of 97 on 2026-11-22 (run results-20261122-094136: 33 parts (7 skinned) on their bones, our materials, body repainted, biome tint, no broken shader, 0 error lines), screenshots ~/valheim-testbed/autotest-blightedheart/latest/img/S-*.png
- What it is / where it is seen: insectoid skirmisher, seen at 3–20 m.
- Reference: hive sheet; donor `Seeker` bind pose.
- Size: donor bind-pose bounds.  Budget: ≤ 12k tris (owner, 2026-11-21).
- Attach / origin: ground centre, +Y up, donor forward.
- Look: the carapace segments are Hive-mass lumps. Brood cells in the abdomen glow with blight. Mandibles are timber
  splinters. Eye clusters sit on the head, and foliage strands hang from the thorax.
- Measured 2026-11-21 (step 1, one mesh, six named slots, 1 UV channel): 7,033 / 8,000 tris; 4.50 × 2.16 × 4.24 m (donor 5.80 × 2.55 × 4.11 m, 1 SMR, 44 bones). Has wings (donor wings are skinned and animated; not on the card, owner to confirm). Previews: `art/subbosses/ASSET-006_*/previews/`.
- Measured 2026-11-21, after the 12k budget: v2 10,347 / 12,000 tris; 4.50 × 2.16 × 3.79 m, 63 brood cells (v1 7,033 in v1/).
- Measured 2026-11-21, v3 (trees → growth, tone add-on): 11,839 tris, 4.50 × 2.16 × 3.79 m; v2 kept in v2/.
- After review (2026-11-22): kitbash shape approved ("SHAPE only approved"). Geometry locked: kit/approved_shape_2026-11-22/. Step 3 = texture/material only.
- After review (2026-11-22): final look approved ("approved"). Biome tint: base colour only, like the Heart ("base color like the heart does"): _Color = biome tint, NO _EmissionColor override.
- Owner's words: as ASSET-001.
