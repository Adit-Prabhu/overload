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
| Arc Mite | Enemy that carries Spark | `enemy_spark` |
| Relay | Enemy that carries Blink | `enemy_blink` |
| Coil | Enemy that carries Burst (ceiling content) | `enemy_burst` |
| Charge | A power fragment dropped by an enemy | `fragment` |
| Fuse Box | The safe room for loadout and fusion | `safe_room` |
| Substation hall | The arena | `arena` |
| Arc Trail | Spark + Blink fusion | `fusion_spark_blink` |
| Shock Cone | Spark + Burst fusion (ceiling content) | `fusion_spark_burst` |

## 2. Visual language

### Style
Original pixel art in a 3/4 top-down view, in the spirit of action roguelikes like Soul Knight: chunky characters, readable machines, a lit and detailed station. Nothing is copied from any other game.

- **Resolution:** 256 × 144 internal, scaled up by whole numbers (5× gives 1280 × 720), nearest-neighbor only.
- **Tiles:** 16 × 16. Characters are about 16 × 22, small enemies 16 to 20 px, and the Regulator about 46 × 42.
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
| Powers | `power.spark`, `power.blink`, `power.burst` and their `px.*.light` variants | Yellow, cyan and magenta, used only for powers and power cores |
| Shared | `hostile.danger`, `ui.text`, `ui.dim`, `fx.flash`, `fx.none` | Telegraphs, text, hit flashes, light math |

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
4. **You can see what you will steal.** Each enemy shows its power core: the Arc Mite's bolt, the Relay's diamond window.
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
| Machines | Mechanical and twitchy | Leg cycles (Arc Mite), a lever that flips (Relay), legs speed up while charging a shot |
| Regulator | Heavy and deliberate | Treads, a gauge needle that always points at the Surge, pose changes per protocol |

Timing standards apply to both comparison conditions identically:

| Action | Tell | Recovery |
| --- | --- | --- |
| Enemy attack | ≥ 0.40 s | ≥ 0.25 s |
| Regulator attack | ≥ 0.50 s | ≥ 0.60 s after lunges |
| Relay blink destination | 0.50 s marker before arrival | |
| Protocol boot at encounter start | 1.5 s pose, sound and icon | |

**Feedback:** white hit flashes on enemies, spark bursts on hits and kills, muzzle flashes, invulnerability flicker on the Surge, and screen shake at 2 px or less with a toggle.

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
| CH-02 | Regulator | Orange machine with a big gauge face, ceramic insulator shoulders, vents, status lights, hazard-striped hip, treads. The needle tracks the Surge | Pose per protocol, protocol boot cue | P0 | Done (poses), boot cue pending |
| CH-02a | Clamp protocol | Pincers forward | Lunge with a filling tell, then recovery | P0 | Pose done |
| CH-02b | Insulate protocol | Hatched shield plates on both sides | Backs off, lays hatched hazard tiles, slow orbs | P0 | Pose done |
| CH-02c | Oscillate protocol | Side thruster fins | Strafes, fins flash before a volley | P0 | Pose done |
| CH-03 | Arc Mite | Beetle machine with a shiny shell, a glowing bolt core, a sparking antenna, one eye, jointed legs | Legs cycle, faster while charging. Dotted aim line and filling ring for 0.45 s, then a spiked bolt | P0 | Done |
| CH-04 | Relay | Boxy machine with a lever switch, visor eyes, a diamond core window, a status light, treads | Lever flips. A hatched landing diamond shows 0.5 s before it blinks | P0 | Drawn, behavior in task 9 |
| CH-05 | Coil | Coil-spring machine with a ring core | Coils tighten, then a shockwave | P2 | Not started |

### Abilities
| ID | Asset | Look | Pri | Status |
| --- | --- | --- | --- | --- |
| AB-01 | Gun shot | Small white streak with glow | P0 | Done |
| AB-02 | Dodge | Fading white ghosts of the Surge | P0 | Done |
| AB-03 | Spark | Bolt projectile | P0 | Symbol done, effect in task 8 |
| AB-04 | Blink | Diamond at departure and arrival | P0 | Diamond done |
| AB-05 | Arc Trail | Bolt line between two Blink diamonds | P0 | Done |
| AB-06 to 08 | Burst, Shock Cone, evolutions | Ring-based effects | P2 | Not started |

### Pickups, telegraphs and icons
| ID | Asset | Pri | Status |
| --- | --- | --- | --- |
| PK-01 | Charges (bolt, diamond, ring) that float and glow | P0 | Done |
| PK-02, PK-03 | Unlock and fusion flashes | P0 | Task 8 |
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
| EN-08 | Fuse Box room | P0 | Task 8 |
| EN-09 | Lighting states per encounter (standby, rising, overload) | P1 | Not started |

### UI and HUD
| ID | Asset | Pri | Status |
| --- | --- | --- | --- |
| UI-01 | Battery charge cells and dodge bar, top left | P0 | Done |
| UI-02 | Q and E power sockets with cooldown shade, bottom right | P0 | Done |
| UI-03 | Regulator bar with protocol icon, top center | P0 | Done |
| UI-04 | Pixel reticle | P0 | Done |
| UI-05 | Banners ("SHORT CIRCUIT", "SECTOR CLEAR") with the build stamp | P0 | Done, labels approved |
| UI-06 | Fuse Box link status message | P0 | Task 5 |
| UI-07 | Title screen and wordmark | P1 | Not started |
| UI-08 | Settings (volume, screen shake, flash reduction) | P1 | Not started |
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
| MU-04 | Victory and defeat | Victory: the motif resolved to B major with a rising sweep. Defeat: a tape-stop "power cut", silence, then the hum returns | P1 |
| MU-05 | Title | HUM with a sparse LEAD | P1 |

How the music layers:

| Moment | Stems |
| --- | --- |
| Fuse Box | MU-02 |
| Encounter 1 | HUM and PULSE |
| Encounter 2 | Adds ARC |
| Encounter 3 | Adds LEAD |

Stems change on the next bar line. Music ducks by 6 dB during telegraph sounds so tells always cut through.

### Sound effects
All sound effects come from the same small synth as the music (saw, square, sine, noise, one resonant filter and a light bit-crush). Pitched sounds are tuned to B minor.

| Group | Sounds | Pri |
| --- | --- | --- |
| Player | Shot, hit, dodge, death, low health | P0 |
| Powers | Spark, Blink depart and arrive, Blink deny, Arc Trail buzz | P0 |
| Enemies | Arc Mite tell and zap, Relay click and blink, enemy death short-circuit | P0 |
| Regulator | Tread rumble, three protocol stings (MU-03), lunge thunk, hazard fill, orb fire, hit, defeated | P0 |
| Progression | Charge pickup, unlock, fusion | P0 |
| UI | Hover, confirm, deny, link status blip | P1 |
| Ambient | Substation hum bed, emergency lamp buzz, Fuse Box room tone | P1 |
| Ceiling | Burst, Shock Cone, Coil, evolution | P2 |

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
| MK-02 | App icon | The Surge's hard hat with a spark | P1 |
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
5. **Manifest.** Each file under `assets/` gets an entry in `assets/ASSET_MANIFEST.json` with these fields: id, source file, creator, tool, license, approver, date and hash.

### Who does what
| Role | Owns | Approval |
| --- | --- | --- |
| Art Lead agent (`.agents/art.md`) | Palette, sprites, tileset, props, lighting, HUD, contact sheets, key art | Adit approves the style frame and each batch |
| Audio agent (`.agents/audio.md`) | Synth, music stems, SFX, mix | Adit approves each listen-through |
| Design Lead agent | Tell timings and readability rules in the sim, room layouts | Adit approves gameplay feel |
| Narrative agent | Glossary, labels, stenciled signage, premise line | Adit approves all text |
| QA agent | Grayscale, color-vision, mute and timing checks. Read-only | Adit resolves findings |

## 5. Accessibility settings
- Volume sliders for music and SFX
- Screen shake toggle
- Flash reduction (replaces white flashes with outline pulses)
- Color-independent cues throughout
- Key rebinding stays an open question from the GDD

## 6. Acceptance checks (automated where possible)
| Check | How |
| --- | --- |
| Palette discipline | Test fails if a color literal appears outside `art/palette.py` in a color position |
| Grid validity | Test fails on unknown grid characters. Animation frames share one size |
| Manifest completeness | Test fails if a file in `assets/` has no manifest entry with a license and matching hash |
| Shape readability | Bright-pattern comparison in `tests/shapes.py` for confusable pairs, plus the CVD contact sheet reviewed by QA |
| Room validity | Rows match in width, wall decor sits on walls, props and decals sit on the floor, spawns are clear |
| Tell timing | Sim tests assert every hostile attack's tell and recovery frames meet the timing standards in section 2 |
| Mute playability | Every audio event maps to a visual event (test, once audio lands) |
| Audio technical | Peak level ≤ -1 dBFS, seamless loops, equal stem lengths |
| Performance | Light pools are built before the first frame. After that a full frame renders in well under 1 ms at 256 × 144 on the development laptop. Cosmetic effects advance per simulation tick, so they look the same at any display rate. Profile again before Alpha |
| Cohesion review | Adit compares each new batch with the approved style frame. Anything off-theme gets sent back |
