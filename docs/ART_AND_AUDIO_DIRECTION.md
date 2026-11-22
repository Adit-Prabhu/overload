# Overload · Art and audio direction
Version 0.2 · November 16, 2026 · Pixel art direction approved by Adit (Creative Director)

This document is the single source of truth for how Overload looks and sounds. Every asset (player, enemies, rival, abilities, pickups, the station, UI, music, sound effects, text and showcase material) follows it. It supplements the Initial GDD, which only committed to "original geometric art", and will be folded into the Update GDD at G2/G3.

**History:**
- **Version 0.1 (November 16):** proposed a neon vector look. Adit approved the substation theme (decision D1).
- **Same day, after seeing it running:** Adit asked for a character-based pixel art look in the spirit of Soul Knight, with original art (decision D8). The theme, fiction and audio plan carried over unchanged.
- **Version 0.2:** records the pixel art direction. Adit approved it after the second style frame.

**Review images** (in `docs/art/`):
- `pixel_style_frame.png`: the gameplay view.
- `pixel_room.png`: the whole substation hall.
- `pixel_contact_sheet.png`: every asset.
- `pixel_contact_sheet_cvd.png`: the contact sheet in grayscale and three color-vision simulations.
- `title.png`, `title_controls.png`, `title_settings.png`, `hud_in_play.png`, `hud_loadout.png`: title, controls, settings, HUD and loadout review renders (`tools/art/ui_renders.py`).
- `boss_entrance.png`, `boss_in_play.png`, `bosses.png`, `boss_down.png`: three-phase Regulator review renders (`tools/art/boss_review.py`).

## 1. Theme

**Overload: a lineworker trapped in a city substation during a blackout.**

You play the Surge, a lineworker caught inside a sealed substation when the grid goes down. Your siphon glove can pull charge out of the machines that patrol the station. Destroy one and its charge breaks loose, so you can absorb it and use it as a power. In the Fuse Box between fights you wire two stolen charges together into something new. Overseeing everything is the Regulator, the substation's protection system. It watches how you fight and reroutes its protocol to shut you down.

Why this theme fits the design:
- **The title becomes literal.** Using stolen power until things overload is the fantasy.
- **The powers are already electrical.** Spark, Blink and Burst become an arc, a relay jump and a discharge pulse.
- **"Fuse" is a pun that works.** You fuse powers in the Fuse Box.
- **The rival has a reason to learn.** A regulator's whole job is to monitor load and adjust, so an adaptive opponent makes sense in the fiction without any dialogue.
- **The blackout gives the look its mood.** Emergency lamps cast warm pools in a dark hall, and anything charged glows.

### Three keywords
Every asset is checked against these. If an asset doesn't express at least one of them, it's off-theme.
1. **Charged.** Light means energy. Powers, cores, conduits and shots glow and stay bright in the dark. Drained things go dim.
2. **Industrial.** The station is a real place: steel floor tiles, diamond-plate walkways, cable trenches, transformers, switchgear, hazard paint and stenciled signage. Machines look built, with bolts, vents, ceramic insulators and treads.
3. **Unstable.** Lamps pulse, LEDs blink, sparks fly. The closer something is to overload, the more it flickers.

### Fiction glossary
Use these names everywhere: UI text, logs shown to players, recordings and docs. The internal config IDs stay as they are in the Initial documents.

| In-game name | What it is | Config ID |
| --- | --- | --- |
| Surge | The player, a lineworker | `player` |
| Regulator | The recurring rival | `rival` |
| Clamp protocol | Rival tactic that closes distance | `pressure` |
| Insulate protocol | Rival tactic that holds you at range | `spacing` |
| Oscillate protocol | Rival tactic that strafes. The neutral default | `lateral` |
| Arc Drone | Robot that carries Spark (was the Arc Mite before the Nov 17 overhaul) | `drone` |
| Relay Bot | Robot that carries Blink | `relay` |
| Breaker | Robot that carries Burst (was the Coil) | `breaker` |
| Sweeper | Robot that rushes and carries Magnet | `sweeper` |
| Sentry | Turret robot that carries Bulwark | `sentry` |
| Charge | A power fragment dropped by an enemy | `fragment` |
| Fuse Box | The safe room for loadout and fusion | `safe_room` |
| Substation hall | The arena | `arena` |
| Arc Trail | Spark + Blink fusion | `fusion_spark_blink` |
| Shock Cone | Spark + Burst fusion (ceiling content) | `fusion_spark_burst` |

## 2. Visual language

### Style
Original pixel art in a 3/4 top-down view, in the spirit of action roguelikes like Soul Knight: chunky characters, readable machines, a lit and detailed station. Nothing is copied from any other game.

- **Resolution:** 256 × 144 internal, scaled up by whole numbers (5× gives 1280 × 720), nearest-neighbor only.
- **Tiles:** 16 × 16. Characters are about 16 × 22, small enemies 16 to 20 px, and the Regulator about three times the Surge's height (up to 100 × 84 with its legs).
- **Outline:** every sprite gets the same 1 px dark outline automatically.
- **Light:** comes from the top left. Every material has a dark, mid and light tone.
- **Camera:** follows the Surge with a slight lead toward the aim, inside rooms larger than the screen.

### Palette
All colors come from `src/overload/art/palette.py`. No other file may contain a color literal, and a test enforces this (section 6).

The palette is organized as ramps, darkest first:

| Group | Tokens | Used for |
| --- | --- | --- |
| Station | `px.floor.*`, `px.tile.*`, `px.concrete.*`, `px.wall.*`, `px.ceramic.*`, `px.wood.*` | Floors, walls, props. Cool and dark, so characters and light read on top |
| Paint and light | `px.hazard.*`, `px.paint`, `px.conduit.*`, `px.lamp`, `px.lamp.light`, `px.led.amber`, `px.ambient` | Safety paint, stencils, conduits, emergency lighting |
| Surge | `px.helmet.*`, `px.skin.*`, `px.goggle.*`, `px.jacket.*`, `px.pack.*`, `px.pants.*`, `px.boots.*`, `player.core`, `player.halo` | The lineworker. White hard hat and teal jacket, so the player is never orange |
| Machines | `px.bot.*`, `px.hostile.*`, `px.dial.*` | Gunmetal bodies with hostile orange-red shells and accents |
| Powers | `power.spark`, `power.blink`, `power.burst`, `power.bulwark`, `power.magnet` and their `px.*.light` variants | Yellow, cyan, magenta, Bulwark's yellow green (kept off the rare rarity's mint) and Magnet's indigo (kept off Blink's cyan), used only for powers and power cores |
| Shared | `hostile.danger`, `ui.text`, `ui.dim`, `fx.flash`, `fx.none` | Telegraphs, text, hit flashes, light math |
| Rarity | `px.rarity.rare`, `px.rarity.epic`, `px.rarity.legendary` | Steel, mint and champagne for fusion rarities (docs/POWERS_AND_FUSION.md). Menus and HUD slots only, never in the world, and always with 1, 2 or 3 cross marks. Rare is deliberately plain, close to `ui.dim`. Champagne sits near Spark's yellow light, which is acceptable only because it never appears in play |

### Rules that keep it readable
1. **Shape before color.** Every power, enemy and hostile projectile can be told apart in grayscale by its shape or bright pattern. Color only reinforces it. The CVD contact sheet checks this.
2. **Friend versus foe:**
   - **The player:** white, teal and skin tones.
   - **Machines:** gunmetal with orange-red accents and visible power cores.
   - **Hostile projectiles:** spiked orange orbs. The player's shots are small white streaks.
3. **One symbol per power, everywhere.** A power's charge pickup, HUD socket icon, pack socket light, enemy core and effect all use the same symbol:
   - **Spark:** a bolt
   - **Blink:** a diamond
   - **Burst:** a ring
   - **Bulwark:** a shield
   - **Magnet:** a horseshoe
4. **You can see what you will steal.** Each maintenance robot shows its power core: the Arc Drone's bolt, the Relay Bot's diamond window, the Breaker's ring, the Sentry's shield and the Sweeper's horseshoe.
5. **A fusion looks like its ingredients combined.** Arc Trail is a yellow bolt line strung between two cyan Blink diamonds.
6. **Telegraphs fill up.** Every hostile attack shows something that fills over the tell time: a ring of dots around a shooter, hatching inside a hazard tile, a Relay's landing diamond. Telegraphs use `hostile.danger` plus a pattern, never color alone.
7. **Lit and emissive are separate.** Ordinary pixels are darkened by the blackout lighting. Glowing pixels (powers, cores, shots, conduits, LEDs, lamp lenses) are added after, so they always read.

### Lighting
Two passes per frame:
1. **Darkness and pools.** Multiply the view by a light map: a dim blue ambient plus additive pools from emergency lamps (pulsing slowly), overhead lights, the Surge's headlamp, and shots and bolts in flight.
2. **Warmth.** Add a faint tint of each light so pools read as warm, lit floor.

A glow pass then blooms the emissive layer.

### Motion language
| Faction | Motion personality | Implementation |
| --- | --- | --- |
| Surge | Responsive | 2-frame idle breathing, 4-frame walk with body bob, dodge ghosts |
| Machines | Mechanical and twitchy | Walkers step on jointed legs with an eight-step cycle driven by the distance walked, so a robot that stops stands still and a faster one steps faster (`art/pixel/rig.py`). The Breaker walks, swings its fists and kicks up dust at each footfall, the Sweeper scuttles on four spider legs and digs in to rev, the Arc Drone hovers with a spinning rotor and leans into its flight, the Sentry sweeps its eye and its barrel kicks back when it fires. The Relay Bot crouches before a blink and beams out and in on a column of Blink light |
| Regulator | Heavy and deliberate | Each chassis walks on its own legs (`art/pixel/regulators.py`): the Linesman on two long legs, the Transformer on a four-legged trot, the Grid Core on four arched legs stepping in pairs. When it backs away it steps backward. A gauge needle always points at the Surge, the pose changes per protocol, and the chassis lights up before its signature attack |

Timing standards apply to both comparison conditions identically:

| Action | Tell | Recovery |
| --- | --- | --- |
| Enemy attack | ≥ 0.40 s | ≥ 0.25 s |
| Regulator attack | ≥ 0.50 s | ≥ 0.60 s after lunges |
| Chassis signature (ring, quake, summon, spiral) | ≥ 0.50 s, the protocol waits while it runs | the signature's own rest (4 to 7 s) |
| Relay blink destination | 0.50 s marker before arrival | |
| Protocol boot at encounter start | 1.5 s pose, sound, protocol icon and label (revised D5) | |

**Feedback:** white hit flashes on enemies, spark bursts on hits and kills, muzzle flashes, invulnerability flicker on the Surge, screen shake at 2 px or less with a toggle, and short cosmetic impact hitstop (2 to 4 ticks on venting boss hits, phase changes, player hits, and boss defeats, suppressed on `down` or `player_down` transitions so lethal hits never stall retry).

**Determinism:** all cosmetic state (camera, animation, sparks, flashes, ghosts, lamp pulses) lives in the renderer with its own RNG. Rendering and audio never feed back into the game state.

## 3. Asset inventory

Priority key:
- **P0** is needed for the November 28 first-playable recording.
- **P1** is needed by Alpha (Dec 2) and locked at Beta (Dec 4).
- **P2** is ceiling content, built only if G3 approves it.

Status: **done** means drawn, in the game or style frame, and on the contact sheet.

### Characters
| ID | Asset | Look | Motion and tells | Pri | Status |
| --- | --- | --- | --- | --- | --- |
| CH-01 | Surge | Lineworker: white hard hat with a headlamp and reflective band, goggles, teal jacket with a reflective strip, utility belt, battery pack with two power sockets, siphon glove, spark caster | 2-frame idle, 4-frame walk, dodge ghosts, hit flicker, headlamp light follows the aim | P0 | Done |
| CH-02 | Regulator chassis | Linesman gantry and mask, oil-cooled Transformer, fractured reactor cage. Core armor anchors aim and the protocol modules attach on both sides | Three distinct silhouettes per chassis, articulated walks, notched health bar, vent steam, boss entrance with protocol label and icon, and a defeat sequence before the ending | P0 | Done (`art/pixel/regulators.py`, contact sheet and [BOSS_DESIGN.md](BOSS_DESIGN.md)) |
| CH-02a | Clamp protocol | Pincers forward | Lunge with a filling tell, then recovery | P0 | Done |
| CH-02b | Insulate protocol | Hatched shield plates on both sides | Backs off, lays hatched hazard tiles, slow orbs | P0 | Done |
| CH-02c | Oscillate protocol | Side thruster fins | Strafes, fins flash before a volley | P0 | Done (fins flash during the volley tell, steady under Reduce Flash) |
| CH-03 | Arc Drone | Hovering maintenance drone with a spinning rotor and bolt core (replaced Arc Mite) | Leans into flight, dotted aim line and filling ring for 0.45 s, spiked bolt | P0 | Done (`art/pixel/robots.py`) |
| CH-04 | Relay Bot | Boxy relay robot with a lever switch and diamond core window | Crouches before a blink, beams out and in on a column of Blink light | P0 | Done (`art/pixel/robots.py`) |
| CH-05 | Breaker, Sweeper, Sentry | Heavy slam walker (Burst), four-legged spider rusher (Magnet), swiveling shield turret (Bulwark) | Articulated walks, Breaker slam shockwave, Sweeper rev and rush, Sentry scanning eye and recoil | P2 | Done (`art/pixel/robots.py`, sector color tiers in `game/view.py`) |

### Abilities
| ID | Asset | Look | Pri | Status |
| --- | --- | --- | --- | --- |
| AB-01 | Gun shot | Small white streak with glow | P0 | Done |
| AB-02 | Dodge | Fading white ghosts of the Surge | P0 | Done |
| AB-03 | Spark | Bolt projectile | P0 | Done |
| AB-04 | Blink | Diamond at departure and arrival | P0 | Done |
| AB-05 | Arc Trail | Bolt line between two Blink diamonds | P0 | Done |
| AB-06 to 08 | Burst, Bulwark, Magnet and evolutions | Magenta ray cone (wider when evolved), shield dome with reflect flash, indigo pull field with crush arc, chain bolts between robots, Overdrive ghost trail | P2 | Done (`sim/fusions.py`, `art/pixel/effects.py`) |
| AB-09 | 30 chance-fused powers | 10 pairs x 3 rarities (rare, epic, legendary), each combining its ingredient colors and verbs (`docs/POWERS_AND_FUSION.md`), all 35 power icons on the contact sheet | P2 | Done (`sim/powers.py`, `sim/pairs.py`, `art/pixel/effects.py`) |

### Pickups, telegraphs and icons
| ID | Asset | Pri | Status |
| --- | --- | --- | --- |
| PK-01 | Charges (bolt, diamond, ring, shield, horseshoe) that float and glow | P0 | Done |
| PK-02, PK-03 | Unlock and fusion flashes | P0 | Done. The fusion rings and the Relay's arming lever are on the contact sheet. The unlock flash and the white fusion flash are full-screen effects, checked in play |
| TL-01 | Aim tell (dotted line, filling ring of dots) | P0 | Done |
| TL-02 | Relay landing diamond (hatched) | P0 | Done |
| TL-03 | Hazard tile (hatching fills over the tell) | P0 | Done |
| IC-01 | Protocol icons (chevron, hatched square, wave) | P0 | Done |

### The station
| ID | Asset | Pri | Status |
| --- | --- | --- | --- |
| EN-01 | Floor materials: steel tiles, cracked concrete, diamond-plate walkway with painted edges and arrows, cable trench grates, hazard keep-out zones, lit conduits | P0 | Done |
| EN-02 | Walls: autotiled rims, two-tile faces, corners, cast shadows | P0 | Done |
| EN-03 | Wall fixtures: breaker panels with LEDs, emergency lamps, danger signs, vents, meters, pipes | P0 | Done |
| EN-04 | Floor decals: oil stains, scorch marks, loose cables, drains, debris | P0 | Done |
| EN-05 | Props: transformer, switchgear cabinet, insulator stack, cable reel, crate, oil drum | P0 | Done |
| EN-06 | Stenciled signage on walls and floors | P0 | Done |
| EN-07 | Blackout lighting: lamp and overhead pools, headlamp, glow | P0 | Done |
| EN-08 | Fuse Box room | P0 | Done: dedicated safe rooms (`fuse_1`, `fuse_2`) with a cosmetic recessed charging and fusion bay wired to the north wall monitor, plus the Fuse Box menu hub |
| EN-09 | Lighting states per encounter (standby, rising, overload) | P1 | Partly done: one light per sector (below) |
| EN-10 | Sector identity (Nov 17) | P0 | Done, see below |
| EN-11 | Set dressing (Nov 18, `art/pixel/dressing.py`) | P1 | Done. Seeded by tile, cosmetic only. Contact shadows at wall bases, low-frequency grime, bolts and scuffs on every floor. Switchyard: painted walk lines, oil stains, cable trays on the upper walls. Cooling plant: wet patches (kept off the Cooled robots' teal) that catch drips, drains, rust streaks, pipes with valve wheels, steam from the vents. Grid core: scorch marks, cracks leaking conduit light, a lit conduit strip on the upper walls, damaged panels that spit sparks. Bare wall faces get junction boxes, numbered plates and fans. Some emergency lamps flicker, lens and light together. Dust drifts through lamp light |

#### Sector identity (Nov 17)
Each sector should read as a different part of the station within a second of walking in, without changing the rules.

| Sector | Place | Rooms | Floor | Light | Robots |
| --- | --- | --- | --- | --- | --- |
| 1 | Switchyard | Open halls with transformers and a conduit cross | Steel tiles, hazard keep-out paint | Untinted | Stock orange shells |
| 2 | Cooling plant | Pipe walls that split the room into lanes, a hall of square pillars, drums and crates | Cracked concrete | Cold (`px.tint.2`, multiplied) | Cooled: teal shells (`px.conduit`, `px.jacket`, kept off Blink cyan), stock stats |
| 3 | Grid core | Bus bars on lit conduit lines, four pillars around a conduit square, grates | Grates and lit conduits | Hot (`px.tint.3`, multiplied) | Overcharged: violet shells (`px.core`), a little tougher and quicker |

The light eases in as the Surge walks into a sector's room (half way in about 0.3 s, nearly all the way in about 1.2 s). Tells, shots and powers are also drawn on the glow layer after the tint, so their danger red and power colors never shift. Sprites themselves take the room's light. Robot recolors swap only the shell ramp: the danger red of eyes stays, and the bright rim around some eyes shares the shell highlight, so it takes the sector color.

### UI and HUD
#### HUD layout (Nov 17 redesign)
The view is only 256 x 144, so every HUD pixel competes with the fight. Rules, after how small-resolution roguelikes handle it (Soul Knight, Enter the Gungeon, Hades):

1. **Footprint under 10 percent, corners only, 4 px margins.** No big panels: elements sit on the scene with the shared 1 px outline and a drop shadow.
2. **Only what matters mid-fight.** Health, power readiness, where you are, the boss. Control hints live on the title screen's controls page and in the loadout menu footer, not on screen.
3. **Health, top left:** a battery glyph and one compact pip per point (about 50 x 10 px). Pips turn red at 2 or less and the battery glyph pulses. Dodge readiness is a 1 px line under them.
4. **Minimap, top right:** a schematic of the 5 x 3 room grid (about 50 x 22 px), not a scaled map. Rooms appear once seen or once a door to them is known. Current room white, cleared grey, the locked room red, a dot for chambers and Fuse Boxes.
5. **Powers, bottom right:** two 18 px slots with a small Q or E tab above each. A dark fill drains while a power cools. Fused powers carry their rarity border color and 1, 2 or 3 cross marks along the bottom edge, and slots show a 6-tick ready flash when coming off cooldown (steady border under Reduce Flash). Names appear in the loadout menu, not here.
6. **Boss, top center, only during the fight:** the name and a thin bar.

**Tab menu, Loadout and Fuse Bench:** one framed panel over a darkened scene. Pressing Tab or Esc opens the hub (`RESUME`, `LOADOUT`, `FUSE`, `SETTINGS`, `CONTROLS`, `QUIT`), while arriving in a Fuse Box opens with `CONTINUE` plus the link status line (the approved D7 line when the live link is down). `LOADOUT` lists stolen and fused powers on the left (base powers with 3 square evolution pips, fused powers with rarity crosses and slot letters) and shows the two equipped slots plus the selected power's rarity, wrapped description (including evolved perks), cooldown, recipe ingredients and `USES` / `ACTIVE` inherited evolution badges on the right. `FUSE` is a separate crafting bench where you pick two base powers to roll a rare, epic or legendary fusion with a reveal card (`docs/POWERS_AND_FUSION.md` section 7).

| ID | Asset | Pri | Status |
| --- | --- | --- | --- |
| UI-01 | Battery charge cells and dodge bar, top left | P0 | Done |
| UI-02 | Q and E power sockets with cooldown shade, bottom right | P0 | Done |
| UI-03 | Regulator bar with protocol icon, top center | P0 | Done |
| UI-04 | Pixel reticle | P0 | Done |
| UI-05 | Banners ("SHORT CIRCUIT", "SECTOR CLEAR") with the build stamp | P0 | Done, labels approved |
| UI-06 | Fuse Box link status message | P0 | Done (decision D7, live condition only) |
| UI-07 | Title screen and wordmark | P1 | Done (Start, Settings, Controls, Quit and difficulty selector over the Surge vs Grid Core standoff) |
| UI-08 | Settings (volume, screen shake, flash reduction, fullscreen) | P1 | Done (`game/settings.py`, Title and Pause/Fuse Box hubs, saved in `settings/prefs.json`) |
| UI-10 | Font: Silkscreen (SIL OFL 1.1), native 8 px | P0 | Done |

### Music
One original theme, "Overload", carries the whole game. Every cue is an arrangement of it, so the soundtrack is cohesive by construction.

- **Style:** darksynth/electro. Analog-style saw and square leads, pulsing bass, punchy drum machine.
- **Key and tempo:** B minor at 124 BPM. US mains hum is 60 Hz, which sits just under B1, so the substation hum doubles as the song's drone, slightly detuned for unease.
- **Progression:** Bm, G, D, A, with a four-note motif (B, D, F#, E) that becomes the pickup and fusion sounds.
- **Structure:** 8-bar loops (about 15.5 s each) split into synced stems. All stems start together and only their volumes change, so transitions are seamless and beat-aligned.

| ID | Cue | Contents | Pri |
| --- | --- | --- | --- |
| MU-01 | Theme stems | HUM (drone and bass), PULSE (drums), ARC (arpeggio), LEAD (motif) | P0: HUM and PULSE. P1: ARC and LEAD |
| MU-02 | Fuse Box | HUM with a low-pass filter, plus a slow pad on the same chords | P0 |
| MU-03 | Protocol stings | 1-bar sting per protocol, matching CH-02a to CH-02c | P0 |
| MU-04 | Victory and defeat | Consolidated into the 90 approved cues (no separate `.ogg` file): boss defeat plays `sfx_boss_down.ogg` (rolling explosions into the motif in B major), the victory ending drops `PULSE` to resolve over `HUM`, `ARC`, and `LEAD`, and player defeat plays `sfx_death.ogg` while dropping music to `HUM` alone | P1 |
| MU-05 | Title | Built Nov 19: the HUM's mains drone without its bass, a slow pad on the theme's chords, the motif and an answer on a soft bell with a dotted-eighth echo, a quiet heartbeat and a few line crackles. Same key and tempo, so it hands over to encounter 1 on a bar line | P1 |

How the music layers:

| Moment | Stems |
| --- | --- |
| Title screen | MU-05 |
| Fuse Box | MU-02 |
| Encounter 1 | HUM and PULSE |
| Encounter 2 | Adds ARC |
| Encounter 3 | Adds LEAD |
| Ending (victory) | HUM, ARC, and LEAD (PULSE drops out) |
| Down (defeat) | HUM alone |

Stems change on the next bar line. Music ducks by 6 dB during telegraph sounds so tells always cut through.

### Sound effects
All sound effects come from the same small synth as the music (saw, square, sine, noise, one resonant filter and a light bit-crush). Pitched sounds are tuned to B minor.

| Group | Sounds (81 approved `sfx_` cues in `assets/ASSET_MANIFEST.json`) | Pri |
| --- | --- | --- |
| Player | Shot, hit, dodge, death, low health | P0 |
| Base powers | Spark, Blink depart/arrive/deny, Bulwark up/absorb/reflect, Magnet field/crush, Burst and Arc Trail | P0 |
| Fused powers | 30 dedicated use cues (`sfx_fused_*`), one per fused power by pair, verb and rarity (`tools/audio/cues.py`) | P2 |
| Enemies | Arc Drone tell and zap, Relay Bot click and blink, Breaker raise and slam, Sweeper rev, Sentry fire, enemy death short-circuit | P0 |
| Regulator | Tread rumble, three protocol stings (MU-03), lunge thunk, hazard fill, orb fire, hit, defeated (`boss_down`) | P0 |
| Regulator chassis | Signature wind-up (`boss_charge`, ducks the music like other tells), ring burst, spiral, quake, summon, live wire, volley, charge and impact, spray, lattice, vent, phase change, overload alarm | P0 |
| Progression | Charge pickup, unlock, fusion, evolution, fusion roll and rarity stings (rare, epic, legendary) | P0 |
| UI | Hover, confirm, deny, link status blip | P1 |
| Ambient | Consolidated into the 90 approved cues: the 60 Hz substation hum bed and Fuse Box room tone live in `music_hum.ogg`, `music_title.ogg`, and `music_fuse_box.ogg` rather than separate ambient `.ogg` files | P1 |

Mix priority from highest to lowest:
1. Hostile tells
2. Player damage
3. Player actions
4. Pickups
5. Ambient

Peaks stay at or below -1 dBFS. Assets are exported as 44.1 kHz OGG.

**Accessibility:** every audio cue has a visual twin, and the game is fully playable muted.

### Showcase material
| ID | Asset | Notes | Pri |
| --- | --- | --- | --- |
| MK-01 | Key art and video thumbnail | Composed in-engine from real game assets with the wordmark | P1 |
| MK-02 | App icon | Done: 32 x 32 Surge hard hat with a Spark bolt (`art/pixel/actors.py:app_icon`, set via `pygame.display.set_icon`) | P1 |
| MK-03 | Short gameplay clip | For G5 and the finals showcase | P1 |

### Text
| ID | Asset | Notes | Pri |
| --- | --- | --- | --- |
| NA-01 | Labels | Power, enemy and protocol names from the glossary | P0 |
| NA-02 | Premise line | One sentence on the title screen. No dialogue. The model never generates player-facing text | P1 |

## 4. How assets get made

**Pixel art as code.** Sprites are authored as text grids (one character per pixel, mapped to palette tokens) in `src/overload/art/pixel/`. Larger machines and props are drawn pixel by pixel with palette helpers. `grid.render` adds the shared outline.

**Rooms as data.** Rooms are two text grids in `src/overload/rooms.py`:
- **Terrain:** walls, floor materials, trenches, hazard paint and conduits.
- **Decor:** wall fixtures, floor decals, props and lights.

Stenciled labels are listed separately. The tileset draws the room, and the simulation builds its collision from the same data, so what you see is what is solid.

**Audio** is synthesized by `tools/audio/` from one instrument file and one constants file (key, tempo, chords), then rendered to `assets/audio/` and committed alongside its source.

This approach has four advantages:
- Every asset is original.
- Every asset is reproducible from source.
- License provenance is trivial.
- A palette change updates everything at once.

**No AI image or music generators by default.** Their output terms and training provenance are hard to document for the course license manifest. If Adit wants one for a specific asset, record the tool, its terms and the prompt in the manifest before using it.

**External assets only with terms.** The only external asset is the Silkscreen font. Anything else needs a manifest entry with its source URL and license before it's added.

**References.** Soul Knight is the style and genre inspiration. 0x72's CC0 DungeonTileset II was studied to learn how tilesets are structured (wall rims, two-tile faces, set dressing). Nothing was copied from either. See `docs/REFERENCES.md`.

### Workflow for each batch of assets
1. **Style frame first.** `tools/art/pixel_style_frame.py` renders `pixel_style_frame.png` and `pixel_room.png`. Adit approves the look before more art is produced.
2. **Contact sheet per batch.** `tools/art/contact_sheet.py` renders every frame, pose, prop, tile sample, effect and icon. It also renders grayscale, deuteranopia, protanopia and tritanopia versions.
3. **Listen-through per audio batch.** `tools/audio/preview.py` renders all cues in sequence into one file for Adit to review.
4. **Review.**
   - QA checks readability and the rules in section 6.
   - A fresh read-only reviewer agent checks the code.
   - Adit approves the look and sound and merges.
5. **Manifest.** Each file under `assets/` gets an entry in `assets/ASSET_MANIFEST.json` with these required fields: `id`, `path`, `kind`, `creator`, `source`, `license`, `license_file`, `sha256`, `added`, and `approval`.

### Who does what
| Role | Owns | Approval |
| --- | --- | --- |
| Art Lead agent (`.agents/art.md`) | Palette, sprites, tileset, props, lighting, HUD, contact sheets, key art | Adit approves the style frame and each batch |
| Audio agent (`.agents/audio.md`) | Synth, music stems, SFX, mix | Adit approves each listen-through |
| Design Lead agent | Tell timings and readability rules in the sim, room layouts | Adit approves gameplay feel |
| Narrative agent | Glossary, labels, stenciled signage, premise line | Adit approves all text |
| QA agent | Grayscale, color-vision, mute and timing checks. Read-only | Adit resolves findings |

## 5. Accessibility settings
All implemented in `SETTINGS` (`game/settings.py`) and `CONTROLS` (`game/keybinds.py`):
- Volume sliders for music and SFX (0 to 100% in 10% steps)
- Screen shake toggle
- Flash reduction (replaces white unlock/hit/wreck flashes and rapid HUD/tell flicker with steady outline cues)
- Color-independent cues throughout (shape before color, CVD contact sheet verified)
- Key rebinding for move, dodge, both power slots, retry and menu (`settings/keys.json`)

## 6. Acceptance checks (automated where possible)
| Check | How |
| --- | --- |
| Palette discipline | Test fails if a color literal appears outside `art/palette.py` in a color position |
| Grid validity | Test fails on unknown grid characters. Animation frames share one size |
| Manifest completeness | Test fails if a file in `assets/` has no manifest entry with a license and matching hash |
| Shape readability | Bright-pattern comparison in `tests/shapes.py` for confusable pairs, plus the CVD contact sheet reviewed by QA |
| Room validity | Rows match in width, wall decor sits on walls, props and decals sit on the floor, spawns are clear |
| Tell timing | Sim tests assert every hostile attack's tell and recovery frames meet the timing standards in section 2 |
| Mute playability | Every audio event maps to a visual event (enforced by `tests/test_audio.py`, all 90 cues approved) |
| Audio technical | Peak level ≤ -1 dBFS, seamless loops, equal stem lengths |
| Performance | Light pools are built before the first frame. After that a full frame renders in well under 1 ms at 256 × 144 on the development laptop. Cosmetic effects advance per simulation tick, so they look the same at any display rate. Profile again before Alpha |
| Cohesion review | Adit compares each new batch with the approved style frame. Anything off-theme gets sent back |
