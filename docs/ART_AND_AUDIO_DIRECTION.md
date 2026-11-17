# Overload · Art and audio direction
Version 0.1 · November 16, 2026 · Theme approved by Adit (Creative Director)

This document is the single source of truth for how Overload looks and sounds. Every asset (player, enemies, rival, abilities, pickups, arena, UI, music, sound effects, text and showcase material) follows it. It supplements the Initial GDD, which only committed to "original geometric art". It will be folded into the Update GDD at G2/G3.

Adit approved the theme (decision D1) on November 16, 2026. Individual assets still need approval, starting with the style frame (section 4). Palette values stay provisional until they pass the contrast and color-vision check.

## 1. Theme

**Overload: a stray surge loose in a city substation during a blackout.**

You are the Surge, a spark of live current trapped inside a sealed substation. The machines that patrol it each hold a charge. Destroy one and its charge breaks loose, so you can absorb it and use it as a power. In the Fuse Box between fights you wire two stolen charges together into something new. Overseeing everything is the Regulator, the substation's protection system. It watches how you fight and reroutes its protocol to shut you down.

Why this theme fits the design:
- **The title becomes literal.** Using stolen power until things overload is the fantasy.
- **The powers already are electrical.** Spark, Blink and Burst become an arc, a relay jump and a discharge pulse.
- **"Fuse" is a pun that works.** You fuse powers in the Fuse Box.
- **The rival has a reason to learn.** A regulator's whole job is to monitor load and adjust, so an adaptive opponent makes sense in the fiction without any dialogue.
- **It suits a solo build.** Glowing vector lines on a dark background are cheap to draw in code, read well at speed, and stay consistent because one palette and one shape grammar produce everything.

### Three keywords
Every asset is checked against these. If an asset doesn't express at least one of them, it's off-theme.
1. **Charged.** Light means energy. Brightness shows power and health. Things that are powered glow, and things that are drained go dim.
2. **Schematic.** Shapes come from circuit diagram symbols such as junction dots, diode triangles, resistor zigzags, relay switches, inductor coils and ground bars. Lines are clean, with consistent stroke widths.
3. **Unstable.** Energy flickers, jitters and arcs. The closer something is to overload, the more it shakes.

### Fiction glossary
Use these names everywhere: UI text, logs shown to players, recordings and docs. The internal config IDs stay as they are in the Initial documents.

| In-game name | What it is | Config ID |
| --- | --- | --- |
| Surge | The player | `player` |
| Regulator | The recurring rival | `rival` |
| Clamp protocol | Rival tactic that closes distance | `pressure` |
| Insulate protocol | Rival tactic that holds you at range | `spacing` |
| Oscillate protocol | Rival tactic that strafes. The neutral default | `lateral` |
| Arc Mite | Enemy that carries Spark | `enemy_spark` |
| Relay | Enemy that carries Blink | `enemy_blink` |
| Coil | Enemy that carries Burst (ceiling content) | `enemy_burst` |
| Charge | A power fragment dropped by an enemy | `fragment` |
| Fuse Box | The safe room for loadout and fusion | `safe_room` |
| Substation floor | The arena | `arena` |
| Arc Trail | Spark + Blink fusion | `fusion_spark_blink` |
| Shock Cone | Spark + Burst fusion (ceiling content) | `fusion_spark_burst` |

## 2. Visual language

### Style
Neon schematic vector: thin glowing lines and simple filled cores on a near-black background with faint circuit traces. Everything is drawn in code from shared primitives, with no hand-painted raster art. A glow pass is pre-baked once at load time with `pygame.transform.gaussian_blur`, so the game holds 60 FPS.

Logical resolution is 1280 × 720, scaled to the window. Stroke widths are 2 px for detail, 3 px for outlines and 5 px for walls.

### Palette tokens
All colors come from `src/overload/art/palette.py`. No other file may contain a color literal, and a test enforces this (section 6). The values below are provisional until they pass the contrast and color-vision check.

| Token | Hex | Used for |
| --- | --- | --- |
| `bg.void` | `#0A0E17` | Background |
| `bg.trace` | `#16233A` | Circuit traces on the floor |
| `bg.trace_lit` | `#24406B` | Powered traces, encounter lighting |
| `wall.busbar` | `#5B7BA8` | Walls and insulator blocks |
| `player.core` | `#F5F8FF` | Surge core, player bullets |
| `player.halo` | `#CFE3FF` | Surge glow |
| `power.spark` | `#FFD23F` | Spark, Arc Mite core, Spark charge |
| `power.blink` | `#3DE0FF` | Blink, Relay core, Blink charge |
| `power.burst` | `#FF4FB4` | Burst, Coil core, Burst charge |
| `hostile.line` | `#FF6B35` | Outline of every hostile thing |
| `hostile.danger` | `#FF3B3B` | Telegraph fills and hazard hatching |
| `rival.body` | `#1C1F2B` | Regulator housing |
| `ui.text` | `#E6ECF5` | Text and icons |
| `ui.dim` | `#7D8AA3` | Secondary text, empty slots |
| `fx.flash` | `#FFFFFF` | Hit flashes, 2 frames maximum |

### Rules that keep it readable
1. **Shape before color.** Every faction and power can be identified from its silhouette alone, in grayscale. Color only reinforces it, because the GDD forbids relying on color alone.
2. **Friend versus foe:**
   - **Friendly:** anything friendly is filled and smooth, with rounded shapes.
   - **Hostile:** anything hostile is angular and has a `hostile.line` outline.
   - **Hostile projectiles:** these are hollow, so you never mistake one for your own bullet.
3. **One icon per power, everywhere.** The shape of a power's charge pickup, its HUD socket icon, its Fuse Box icon, the enemy core that carries it and its visual effect all use the same symbol:
   - **Spark:** a zigzag bolt
   - **Blink:** a hollow diamond
   - **Burst:** a ring
4. **A fusion looks like its ingredients combined.** Arc Trail is a yellow zigzag line strung between two cyan diamonds. That teaches the recipe without any text.
5. **Telegraphs fill up like a charging capacitor.** Every hostile attack shows a shape that fills over the tell time, so the player can read timing, not just direction. Fills always use `hostile.danger` plus diagonal hatching.
6. **Brightness shows state.** Low health dims the Surge and adds flicker. A drained enemy goes gray before it pops.

### Motion language
Each faction moves differently, so it reads at a glance even before you see its shape.

| Faction | Motion personality | Implementation |
| --- | --- | --- |
| Surge (player) | Fluid and responsive | Ease-out curves, a short motion trail at speed |
| Components (enemies) | Jittery and unstable | Small noise offset on position and rotation, quick hops |
| Regulator (rival) | Mechanical and deliberate | Stepped moves with clear holds, plates that lock into place |

Timing standards apply to both comparison conditions identically:

| Action | Tell | Recovery |
| --- | --- | --- |
| Enemy attack | ≥ 0.40 s | ≥ 0.25 s |
| Regulator attack | ≥ 0.50 s | ≥ 0.60 s after lunges |
| Relay blink destination | 0.50 s marker before arrival | |
| Protocol boot at encounter start | 1.5 s pose, sound and icon | |

**Feedback ("juice"):** 50 ms hitstop on hits to the Regulator, a 2-frame white flash on any hit, and spark-line particles drawn only as short lines and never as blobs. Screen shake stays at 4 px or less, and every intense effect has a toggle (section 5).

**Determinism:** all cosmetic randomness (particles, jitter, audio variation) uses its own RNG, separate from the simulation RNG. Rendering and audio never feed back into the game state.

## 3. Asset inventory

Priority key:
- **P0** is needed for the November 28 first-playable recording.
- **P1** is needed by Alpha (Dec 2) and locked at Beta (Dec 4).
- **P2** is ceiling content, built only if G3 approves it.

### Characters
| ID | Asset | Look | Motion and tells | Sound | Pri |
| --- | --- | --- | --- | --- | --- |
| CH-01 | Surge (player) | White junction dot (radius 12 px) with a soft halo. Two small socket dots orbit it, tinted and shaped by the equipped powers. A short "lead" line points at the cursor | Fluid movement with a trail at speed. Dodge is a 0.15 s streak with a hollow outline while invulnerable. At low health it dims and flickers | Dodge whoosh, hit crackle, low-health heartbeat hum | P0 |
| CH-02 | Regulator (rival) | Octagonal housing (radius about 34 px), `rival.body` fill and `hostile.line` outline. A central gauge needle always points at the Surge, which shows its attention | Stepped mechanical movement. Each protocol has its own pose | Relay clunk on each step | P0 |
| CH-02a | Clamp protocol | Front plates fold into a forward chevron, and the needle swings to the red zone | Lunge with a 0.5 s chevron fill tell, then a dash, then a 0.6 s recovery while the plates vent | Rising saw charge, heavy thunk | P0 |
| CH-02b | Insulate protocol | A ring of hatched insulator plates surrounds the body | Backs off to range and lays hatched hazard tiles that take 0.6 s to fill. Fires slow hollow orbs | Low drone swell, ceramic clinks | P0 |
| CH-02c | Oscillate protocol | Side fins extend, leaving a sine-wave trail | Strafes on a sine path. Fins flash for 0.4 s before a perpendicular volley | Wobbling tone panned left and right | P0 |
| CH-03 | Arc Mite | Diode triangle with a resistor-zigzag tail. A yellow zigzag core shows inside | Jittery hops. The tail crackles for 0.45 s, then it fires a zigzag bolt | Crackle, zap | P0 |
| CH-04 | Relay | Relay-switch body (two contacts and a hinged line) with a cyan hollow-diamond core | A destination diamond outline appears 0.5 s before it blinks there | Double click | P0 |
| CH-05 | Coil | Inductor loops with a magenta ring core | The loops tighten for 0.5 s, then it emits a ring shockwave | Coil whine and thump | P2 |

### Abilities
| ID | Asset | Look | Notes | Sound | Pri |
| --- | --- | --- | --- | --- | --- |
| AB-01 | Gun | Short white current dashes | Friendly and filled | Soft tick zap | P0 |
| AB-02 | Dodge | White streak with a hollow outline | Shows invulnerability frames | Whoosh | P0 |
| AB-03 | Spark | Yellow zigzag bolt | Evolution (P2) adds a thin arc that chains to one nearby enemy | Sharp crack | P0 |
| AB-04 | Blink | Cyan diamond at departure and arrival, with a fading afterimage | An invalid target shows a red X flash, plays a deny blip and keeps the cost | Two-tone blip, deny buzz | P0 |
| AB-05 | Arc Trail (Spark + Blink) | Yellow zigzag line between two cyan diamonds. Lasts 1.5 s and damages anything crossing it | The showcase recipe | Sustained buzz that fades | P0 |
| AB-06 | Burst | Magenta arc wedge pushing outward | Knockback | Discharge thump | P2 |
| AB-07 | Shock Cone (Spark + Burst) | Magenta cone with yellow zigzag edges | | Crack layered on a thump | P2 |
| AB-08 | Evolved variants | Same symbol with a gold double outline and one added element | Must stay recognizable as the base power | Base sound up a fifth | P2 |

### Pickups and progression feedback
| ID | Asset | Look | Sound | Pri |
| --- | --- | --- | --- | --- |
| PK-01 | Charge (fragment) | The enemy's core symbol, floating and bobbing, with a gentle magnet pull | A pickup note in the song's key (B, D or F#, rising with each pickup in a chain) | P0 |
| PK-02 | Power unlocked | Ring burst around the Surge, and the HUD socket flashes | Three-note theme motif | P0 |
| PK-03 | Fusion created | Both cores slide into one fuse in the Fuse Box, a flash, then the new icon | Full theme motif, then a power-up sweep | P0 |
| PK-04 | Evolution reached | Gold outline ring | Motif up a fifth | P2 |
| PK-05 | "Fully evolved" duplicate | Dim pop and text | Muted blip | P2 |

### Environment
| ID | Asset | Look | Pri |
| --- | --- | --- | --- |
| EN-01 | Substation floor | `bg.void` with faint circuit traces, pre-rendered once to a surface. Lighting changes by encounter:<br>• E1 standby: dim traces<br>• E2 load rising: traces pulse slowly<br>• E3 overload: traces bright and flickering<br>The lighting is the same in both conditions | P0 (one state), P1 (three states) |
| EN-02 | Walls and cover | Busbar walls (5 px lines) and ribbed insulator blocks that serve as cover and test Blink validation | P0 |
| EN-03 | Fuse Box (safe room) | A fuse panel screen with two equipped sockets, a collection rack and a fusing slot. Shows link status messages | P0 static, P1 animated |
| EN-04 | Hidden branch | Dark side room whose traces light up when found | P2 |

### UI and HUD
| ID | Asset | Look | Pri |
| --- | --- | --- | --- |
| UI-01 | Health | Battery-style charge cells, bottom left | P0 |
| UI-02 | Power sockets | Q and E sockets showing the power symbol, with a gauge-style radial cooldown. Dodge appears as a pip | P0 |
| UI-03 | Rival bar | Top center, labeled REGULATOR, with the current protocol shown as an icon (shape, not text) | P0 |
| UI-04 | Crosshair | Junction reticle: a small plus sign with a center gap | P0 |
| UI-05 | Ending readout | Deaths, powers tried and completion time, printed like a meter readout. No ranking | P0 basic, P1 styled |
| UI-06 | Link status | One-line Fuse Box message when the live call falls back. Wording is neutral, so players aren't told about the model | P0 |
| UI-07 | Build stamp | Build and config ID in a corner. Needed for gate recordings | P0 |
| UI-08 | Title screen and wordmark | "OVERLOAD" wordmark where the O is a junction dot and a zigzag cuts through the letters | P1 |
| UI-09 | Settings | Music and SFX volume, screen shake, flash reduction | P1 |
| UI-10 | Font | One open-licensed family, for example Chakra Petch for headings and Share Tech Mono for numbers. Bundle its OFL license file and verify it when adding | P0 |

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
| Regulator | Step clunk, three protocol stings (MU-03), lunge thunk, hazard fill, orb fire, hit, defeated | P0 |
| Progression | Charge pickup, unlock, fusion | P0 |
| UI | Hover, confirm, deny, link status blip | P1 |
| Ambient | Substation hum bed, Fuse Box room tone | P1 |
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
| MK-01 | Key art and video thumbnail | Composed in-engine from real game assets with the wordmark, so it matches the game | P1 |
| MK-02 | App icon | Junction dot with a spark | P1 |
| MK-03 | Short gameplay clip | For G5 and the finals showcase | P1 |

### Text
| ID | Asset | Notes | Pri |
| --- | --- | --- | --- |
| NA-01 | Labels | Power, enemy and protocol names from the glossary | P0 |
| NA-02 | Premise line | One sentence on the title screen. No dialogue. The model never generates player-facing text | P1 |

## 4. How assets get made

**Assets as code.** Visuals are drawing functions in `src/overload/art/`, built from shared primitives (`stroke`, `glow`, `hatch`, `zigzag`, `diamond`, `ring`, `chevron`). Audio is synthesized by `tools/audio/` from one instrument file and one constants file (key, tempo, chords), then rendered to `assets/audio/` and committed alongside its source.

This approach has four advantages:
- Every asset is original.
- Every asset is reproducible from source.
- License provenance is trivial.
- A palette or shape change updates everything at once.

**No AI image or music generators by default.** Their output terms and training provenance are hard to document for the course license manifest. Raster output also wouldn't match the vector style. If Adit wants one for a specific asset, record the tool, its terms and the prompt in the manifest before using it.

**External assets only with terms.** The only planned external asset is the font. Anything else (for example a CC0 sound) needs a manifest entry with its source URL and license before it's added.

### Workflow for each batch of assets
1. **Style frame first.** The Art agent builds one composed target screenshot showing the Surge, the Regulator in one protocol, an Arc Mite, a Relay, an Arc Trail, charges and the HUD on the substation floor. Adit approves it before any other art is produced. This one image is the reference for everything after it.
2. **Contact sheet per batch.** `tools/art/contact_sheet.py` renders every sprite, icon and effect frame on the real background at 1× and 2×. It also renders grayscale, deuteranopia, protanopia and tritanopia versions. The output goes to `docs/art/`.
3. **Listen-through per audio batch.** `tools/audio/preview.py` renders all cues in sequence into one file for Adit to review.
4. **Review.**
   - QA checks readability and the rules in section 6.
   - A fresh read-only reviewer agent checks the code.
   - Adit approves the look and sound and merges.
5. **Manifest.** Each asset gets an entry in `assets/ASSET_MANIFEST.json` with these fields: id, source file, creator (Adit or the agent role), tool, license, approver, date and build.

### Who does what
| Role | Owns | Approval |
| --- | --- | --- |
| Art Lead agent (`.agents/art.md`) | Palette, shapes, sprites, VFX, HUD, contact sheets, key art | Adit approves the style frame and each batch |
| Audio agent (`.agents/audio.md`) | Synth, music stems, SFX, mix | Adit approves each listen-through |
| Design Lead agent | Tell timings and readability rules in the sim | Adit approves gameplay feel |
| Narrative agent | Glossary, labels, premise line | Adit approves all text |
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
| Palette discipline | Test fails if a color literal appears outside `art/palette.py` |
| Manifest completeness | Test fails if a file in `assets/` has no manifest entry with a license |
| Shape readability | Contact sheet in grayscale and three color-vision simulations. QA confirms every power, enemy and hostile projectile is distinguishable |
| Tell timing | Sim tests assert every hostile attack's tell and recovery frames meet the timing standards in section 2 |
| Mute playability | Every audio event maps to a visual event in the event table (test) |
| Audio technical | Tool tests check peak level ≤ -1 dBFS, loop seams (first and last samples match within tolerance) and equal stem lengths |
| Performance | 60 FPS with the maximum particle count on the target laptop (profile before Alpha) |
| Cohesion review | Adit compares each new batch with the approved style frame. Anything off-theme gets sent back |
