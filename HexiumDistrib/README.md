<div align="center">

# 🫀 The Blighted World Heart

**A dynamic, massive raid event that violently transforms your serene surroundings into a blood-soaked warzone. Only the strongest Vikings will survive.**

</div>

---

## 🌑 The Corrupted Core
Forged from the twisted remains of "The Hive," the **Blighted World Heart** beats with a sinister, pulsating malice. This towering abomination anchors the nightmare, serving as the nucleus of the raid and the prime target your clan must annihilate to stem the tide of darkness.

## 🩸 Universal Desecration
No sanctuary is safe. This cataclysm can be invoked at **any existing vanilla boss altar**. 

By sacrificing the required biome-specific trophies, you corrupt the ancient stones, tearing open a rift for the Blighted World Heart to erupt into existence. **Transform any boss spawn in your world into a legendary battleground!**

---

## 🌪️ Biome-Dynamic Onslaught
The Blighted World Heart is a living, adapting nightmare. It bends the very environment to its will depending on where it is unleashed:

* **Twisted Visuals & Mechanics** 🎭 - The Heart warps its horrific appearance and deadly characteristics to mirror the biome it infests.
* **Relentless Hordes** 🧟 - The endless, surging waves of enemies are ripped directly from the local environment. A Heart in the Black Forest will unleash suffocating swarms of Greydwarves led by towering Trolls, while a desecrated altar in the Plains will crush you beneath a stampede of bloodthirsty Fulings and enraged Loxes.
* **Monstrous Sub-Bosses** 👹 - When you strike the Heart and shatter its health thresholds, it retaliates by summoning colossal, biome-dependent Sub-Bosses. These behemoths offer unique, devastating mechanics tailored to break your spirit.

---

## ✨ Epic Features
* **The Blighted World Heart**: A corrupted monstrosity summoned via dark sacrifices. Once awakened, it unleashes an unrelenting, endless tide of foes. Survive, or be consumed!
* **Nightmarish Sub-Bosses**: As the Heart bleeds, it calls forth scaled-up champions of the horde (e.g., furious 2-Star Loxes, titanic Trolls, and terrifying Seekers) that must be slaughtered to proceed.
* **Legendary Custom Loot System**: Triumph over the Heart to claim the ultimate prize: Blighted Gear. Discover over **360+** incredibly rare, unique Blighted variations of Vanilla weapons and armors, forged in the heat of battle — including the full Valheim 1.0 Deep North set of Frost-Fire gold weapons and Deep North armor!
* **Dynamic Multiplayer Scaling**: The spoils of war grow with your warband. The Heart guarantees 3 legendary loot drops upon its destruction, plus 1 additional artifact for every Viking brother or sister who stood by your side.
* **Fully Server Authoritative & Synced**: Forged for dedicated realms. Every brutal config value is locked in server-side and automatically synchronized via Jotunn.
* **Sleek Custom UI**: Keep your eyes on the prize with a beautifully dynamic Boss Health Bar that relentlessly tracks the Heart and its summoned Sub-Bosses.
* **Wacky's Database Compatibility**: Safely customize the stats, recipes, and requirements of any Blighted Item using Wacky's Database! WackyDB is auto-detected on startup, handing full authoritative control of Blighted Items over to your YAML configurations. A Blighted recipe with a WackyDB YAML (`name: Recipe_Blighted...`) is left entirely to that YAML; every other Blighted recipe keeps its normal upgrade cost. Blighted items stay drop-only (hidden from the Craft tab) until you give one a real level-1 cost in its recipe YAML — then it becomes craftable.

---

## ☠️ Blighted Affixes
The spoils of your victory are imbued with devastating, game-changing enchantments:

### ⚔️ Weapons of Annihilation
| Affix | Effect |
| :--- | :--- |
| **of the Serpent** 🐍 | Infuses your strikes with a lethal, festering Poison that rots your enemies from the inside. |
| **of the Wraith** 👻 | Channels the wrath of the dead, adding massive, soul-crushing Spirit damage. |
| **of the Blight** ☢️ | An ultra-rare, god-tier enchantment combining both Poison and Spirit elements, while massively amplifying your weapon's base destruction. |

### 🛡️ Armor of the Titans
| Affix | Effect |
| :--- | :--- |
| **of the Bastion** 🏰 | Forges your armor into an impenetrable wall, granting a colossal boost to Armor Rating and unyielding Durability. |
| **of the Serpent** 🐍 | Wards your flesh with absolute resistance against Venom and Poison. |
| **of the Wraith** 👻 | Shields your soul, granting powerful resistance against necrotic Spirit attacks. |
| **of the Blight** ☢️ | The ultimate ward. A phenomenally rare aegis that bestows both elemental resistances and a monstrous multiplier to your base armor rating. |

---

## ⚙️ Server Forging & Configuration
Bend the nightmare to your will via BepInEx config or Jotunn's Configuration Manager:
* **Boss Health & Sub-Boss Thresholds**: Scale the Heart's vitality to create an insurmountable challenge in every biome.
* **Wave Timers & Spawns**: Dictate the pacing of the slaughter—adjust wave intervals and the maximum horde size allowed to swarm the battlefield.
* **Summoning Sacrifices**: Demand greater tributes! Customize the specific items and quantities required to invoke the Heart in any territory.
* **Loot Scaling**: Master the economy of war by adjusting the power curve of Blighted gear dropped across different biomes.

### 📡 BarrkBOT Metrics Export
Server admins can optionally enable a read-only status file (`BepInEx/config/BlightedHeart/barrkbot_blightedheart.json`) reporting per-biome raid state — active/inactive, current Heart health %, active Sub-Bosses, and lifetime summon/defeat counts — for external tools like BarrkBOT to read. World/event data only; no player data is written. Toggle it in the `BarrkBOT Export` config section. On a dedicated server the lifetime summon/defeat counts and biomes are reliable everywhere; the live `active` / health % / Sub-Boss fields are only populated while the Heart is instantiated on the server itself, which a dedicated server only does near the world origin.

### 🕯️ Default Sacrifice Requirements
By default, corrupting an altar requires **1x of the local Boss's unique drop**.

| Biome | Required Sacrifice |
| :--- | :--- |
| 🌳 **Meadows** | 1x Hard Antler |
| 🌲 **Black Forest** | 1x Swamp Key |
| 🐸 **Swamp** | 1x Wishbone |
| 🏔️ **Mountain** | 1x Dragon Tear |
| 🌾 **Plains** | 1x Yagluth Thing |
| 🌫️ **Mistlands** | 1x Queen Drop |
| 🔥 **Ashlands** | 1x Fader Drop |
| ❄️ **Deep North** | 1x Sacrificial Blood (Kall Fimbulbringer's drop) |

> _Note: These items and quantities can be completely customized in the configuration file!_

---

## 🛠️ Installation
1. Install **BepInEx** for Valheim.
2. Install **Jotunn**.
3. Extract the `BlightedHeart.dll` file into your `BepInEx/plugins` folder.
4. Prepare for battle!

<br>
<small>

**License:** MIT — use, modify, and redistribute freely, including commercially; just keep the copyright notice. See `LICENSE.md` for the full text.

</small>
