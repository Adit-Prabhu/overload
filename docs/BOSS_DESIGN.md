# Overload · Boss design (the Regulator's three chassis)
Version 0.3 · November 18, 2026 · Presentation prototype implemented for Adit's sign-off. Production scope past the G1 ceiling, logged for the G3 scope-lock proposal like the floor and the chassis. The stacked combat and presentation PRs implement the design below.

## 1. Why
Adit, Nov 18, after the first redraw: "the bosses need more work, like they don't have interesting attacks or attack patterns, and they look weird ... they don't look intimidating ... if it's the same as mobs then it doesn't feel different, beating a boss should feel like an achievement and I don't get that right now."

Before this rework, a chassis was the protocol's attack plus one signature:

| Chassis | Health | What it does | Same as a mob? |
| --- | --- | --- | --- |
| Linesman | 36 | Clamp's lunge, Insulate's slow orbs and hazard tiles, or Oscillate's three-bolt fan, plus a ring of 8 bolts about every 6.8 s | The fan is the Relay Bot's, the ring is 8 Drone bolts at once |
| Transformer | 52 | The protocol attack, plus a wide shockwave about every 6.4 s | The quake is the Breaker's slam, bigger |
| Grid Core | 66 | The protocol attack, plus two Arc Drones about every 8.9 s (skipped while two robots are up). At half health, a two-arm spiral replaces the summons | The summons are mobs |

There was one phase (two on the Grid Core) and no punish window. The entrance was the 1.5 s protocol boot (a pose, a sting and an icon) and the death was a larger spark burst with its own sound. Nothing said "this is the fight of the sector".

## 2. What similar games do
I looked at how action roguelikes and boss-focused games build bosses. Each claim names its source (listed at the end):

1. **Bosses speak a different language from mobs.** Mobs fire single shots. Bosses fire patterns: rings, fans in sequence, spirals, sweeps, attacks on the arena itself. Enter the Gungeon's final boss, the Lich, cycles through rings, spirals, summons and sweeps across three phases [Gameranx boss guide]. For its spin-off, Dodge Roll made boss patterns "faster, more dense" [Game Developer, Exit the Gungeon]. Its patterns were prototyped by a gameplay programmer and refined with the team's feedback [Game Developer Q&A].
2. **Every attack has its own clean read.** Attacks need "clean reads", and two attacks must not share a wind-up or a sound. Big bodies get weight from slower, longer wind-ups. Longer helps up to about 2 s, with 1 to 1.5 s as the sweet spot [Game Developer, tips from a combat designer].
3. **Phases.** A boss that is the same from full health to zero is boring. Phases should expand or subvert earlier patterns, and the tempo should build [Choost Games]. Hades changes the arena during a fight: Tisiphone's chamber closes in as it goes on [Gorinstein thread, a secondary mirror of a developer's posts].
4. **Punish windows make the player feel strong.** After a big attack the boss is open, and the window must be generous. The goal is to "prove to the player how awesome they are", not how awesome the boss is [combat designer].
5. **Bosses are not subtle.** Larger than life, with exaggerated hits and reactions [combat designer]. Music and animation mark the beats [Choost Games].
6. **Fair deaths.** Every attack telegraphed with a window to respond. A good test: a player watching their death thinks "oh, I see what I should have done" [Choost Games].
7. **Reward.** A win pays off mechanically (drops, progress) and emotionally (music, a change in the world). If a player wins and feels nothing, the fight lacked challenge or payoff [Choost Games].

How a boss should look. These are my reading of the genre, not sourced claims:
- **Silhouette first:** each boss is a distinct shape that reads at a glance, and keeps it across phases while color and light escalate.
- **Proportions carry menace:** a heavy mass with a low head and a forward lean reads as threat. Round, chibi proportions read as cute, and the first redraw had exactly that.
- **Dark armor with glowing accents:** dark shells, bright slit eyes rather than round lenses, rim light. Jagged or clawed limbs read as dangerous.
- **Scale:** bosses tower. The Surge is 16 x 22 in a 256 x 144 view, so a boss should be about three times its height.

### Presentation research and application

- **Enter the Gungeon.** Dave Crooks describes Dodge Roll starting from a rough boss concept and letting the gameplay programmer experiment with patterns before the team iterates. He calls out the Beholster as the clearest expression of the game's fantasy and praises the High Priest's variety. For Overload, the kit already supplies the patterns. The character should embody a particular piece of substation machinery so that a wire sweep, coolant spray or reactor spiral makes sense as soon as the player sees it. [Dodge Roll developer interview](https://www.gamedeveloper.com/design/q-a-the-guns-and-dungeons-of-i-enter-the-gungeon-i-)
- **Cuphead.** Studio MDHR describes building the battles first, then iterating on animation against the established hitboxes and timing. Escalating transformations make progression an event in itself. For Overload, this means opening armor, changing posture and damaging hardware at the existing thresholds. Each chassis keeps its recognizable silhouette and recurring face shape through all three forms. [Studio MDHR developer interview](https://www.gamedeveloper.com/business/road-to-the-igf-studio-mdhr-s-i-cuphead-i-)
- **Hyper Light Drifter.** Alx Preston describes using visual design to carry narrative and character while keeping fast combat legible. Its approach gives the station equipment in Overload two jobs. The same ceramic insulators, panel stripes, steel pistons and status lights appear on the room props, the maintenance bots and the boss bodies. Scale, heavier joints, a deep visor and exposed high-energy machinery distinguish the bosses. [Heart Machine developer article](https://blog.playstation.com/2014/03/14/creating-the-world-of-hyper-light-drifter-on-ps4-and-ps-vita/)
- **Attack and punish cues.** Combat designer Mike Birkhead argues for recognizable anticipation and a clear visual state when a weak point can be punished. The large silhouette changes mark persistent phases. Individual attacks still have their existing patterns and floor tells, a lowered head or raised linkage illustrates the wind-up, and a small white-hot opening with pale steam marks a vent. Both side plates and thruster fins remain visible in all three phases. [Mike Birkhead on boss design](https://www.gamedeveloper.com/design/opinion-boss-design---tips-from-a-combat-designer)

### Three phases at game scale

| Chassis | Phase 1 | Phase 2 | Phase 3 |
| --- | --- | --- | --- |
| Linesman | Upright breaker gantry, a narrow welding visor and sprung climbing gaffs | Crossarm lifts, claws swing out and the mask drops into a scowl | Crossarm spreads wide, hot leads hang from the terminals, and a torn chest plate hangs beneath the cage |
| Transformer | Low oil-filled tank under a beveled shell, small cold stack and four piston legs | Head lowers behind the horns, radiator stack rises and the side hatch strains | Outer panel peels away, coils glow through the open side, and the bull drops its head farther into the charge |
| Grid Core | Sealed reactor cage, close plates, upright terminals and four armored feet | Plates part around a visible reactor, knees rise, and the terminals push out | Cage opens farther, the live reactor dominates the center, and fractured leads bridge the armor |

The [phase sheet](art/bosses.png) shows the three forms in their own chambers under game lighting, with the Surge for scale. The local [roster sheet](art/robot_style_frame.png) compares them to the five maintenance bots. Dark articulated legs and appendages extend beyond the damage circle. The colored armor stays near the aim point, with at least 80 percent covered in phase 1 and 65 percent in later phases. The game uses the same health breakpoints, attack rotations and attack timing values for the existing protocols.

On a Grid Core win, the wreck and chained explosions run for 1.5 s and the banner holds for another 1.5 s. The results screen follows while the simulation is already at the ending. Simultaneous player death suppresses the victory presentation. The separate boss times row has its own space below shots. The entrance keeps the health and loadout HUD visible. The DEV instant defeat lands a real killing hit after the next tick (Nov 19), so it plays the same sequence. Capture the death presentation with normal damage, as the render tool does.

The follow-up uses a distance-driven foot step along each chassis' actual heading, including strafes, retreats and vertical movement. A foot swings up to nine screen pixels clear of the floor. During the planted part of the cycle, its offset counters the body's movement. The boss HUD keeps its current phase visible, including a bordered `SHIFTING` badge during the shielded transition. The capture tool crosses the breakpoints with projectiles and lets the simulation change phase.

## 3. Rules this game must keep
The study needs these, and the rework stays inside them:
- **The protocol** (Clamp, Insulate, Oscillate) is still the only thing the rival model chooses. It moves the Regulator and fires its protocol attack. It stays frozen for the whole fight, through every phase, and a phase change makes no rival request (AGENTS.md).
- **Kit attacks may move the body.** The Bull Charge carries the Transformer across the room. While a kit attack, a vent or a phase change runs, the protocol waits, as it waited for the old signatures. After a charge, the protocol walks it back into its own range.
- **The protocol runs at least half of every boss fight**, in every sector and protocol, measured with the floor bot (the test totals time across retries per sector for three seeds, Clamp included). The kit is not allowed to crowd out the treatment. The 1.5 s boot does not count as fight time, since nothing acts during it. Counted with it, Insulate's share in sector 2 drops to about 0.46.
- **The chassis kit** is fixed per sector and identical in both comparison conditions. It never reads the model's observations.
- **Deterministic** and fully playable with the model off. No kit attack draws from the world RNG: volley marks, debris and lattice cells sit at fixed offsets from the Surge or the impact.
- **Telegraphs** fill up, use `hostile.danger` plus a pattern, and last at least 0.75 s for a kit attack (Tuning enforces it).
- **No legal loadout trivializes a protocol.** The fused-power protocol check (POWERS_AND_FUSION.md, section 9 step 8) runs on the new kits, including the vent windows. Vents happen wherever the protocol parked the body, so short-range powers gain more under Clamp than under Insulate. That check is where it shows.
- **Re-pinned hashes** on Python 3.11 and 3.12 for any sim or Tuning change.

## 4. The design (as built in the sim PR)

### 4.1 What every chassis gets
- **Three phases**, starting at two thirds and at one third of its health. The health bar shows two notches (presentation step).
- **Phase change** (1.2 s):
  - The chassis is shielded and nothing fires. Every hostile shot in the room is wiped. Hazard tiles, shockwaves already running, pending warps and summoned drones stay.
  - There is no knockback, so nothing can push the Surge onto a tile.
  - The rotation restarts for the new phase, and the protocol's rest shortens.
  - Wiping shots helps Insulate a little more than Clamp, since Insulate's orbs linger. The protocol check covers it.
- **A rotation of kit attacks**, patterns no robot uses, cycled in a fixed order. Some phase 1 attacks stay in later phases, as listed below.
- **A vent window:**
  - After its biggest attack each chassis vents for 1.5 s (the Grid Core's core spiral 1.75 s). It stands still and every hit lands half again as hard, rounded up. So a 1-damage gun shot does 2, a 2 does 3 and a 6 does 9.
  - The Transformer vents only when a Bull Charge hits a wall or a prop.
  - The Grid Core vents after the Lattice, the spiral and the core spiral, so it has a window in every phase.
- **Distinct reads.** Each kit attack has its own marking, unlike any robot's or protocol's:
  - Live Wire: lines of 2 px dots that fill outward from the crossarm, unlike the 1 px dotted aim line.
  - The volley: landing circles that close in.
  - The charge: a two-sided lane.
  - The spray: a fan.
  - The Lattice: 32 px cells with corner brackets and cross-hatching that grows from the middle, unlike Insulate's 16 px tiles that fill downward.
  - Debris: a growing shadow.
  - Tells last 0.75 to 1 s.
- **An entrance** (presentation step): the existing 1.5 s boot gets a name card and the boss music.
- **A death that lands** (presentation step):
  - View only: chained explosions, a flash, a banner and the lights coming back.
  - In the sim, the room clears on the tick health reaches zero, as it did before. Every hostile shot and tile goes at once, so the Surge cannot go down after winning.
- **A reward:**
  - One spare charge of every base power the Surge has stolen, for the Fuse Box's rerolls. A retry before the win does not keep it. It is part of the next sector's checkpoint.
  - The Grid Core's reward comes at the end of the run and only shows in the ending.
  - The fight time of the winning attempt is kept per sector for the ending readout.

### 4.2 Linesman (sector 1): "read the pattern, find the gap"
It stays at range and fills the air.
- **Look** (presentation step): a gaunt, hunched giant on a utility pole spine. Its crossarm forms the shoulders, with insulators as spikes. A hood has a slit of three red eyes, the arms end in hooks, and the legs carry climbing gaffs.

| Phase | Rotation | Gap between attacks |
| --- | --- | --- |
| 1 | Arc Ring (8 bolts, 0.8 s tell), Live Wire | 4.5 s |
| 2 | Double Ring (a second ring 0.25 s later, offset half a gap), Live Wire, Insulator Volley | 3.5 s |
| 3 | Double Ring, Live Wire twice, Insulator Volley | 3 s |

- **Live Wire:** three lines fan from the crossarm toward the Surge (0.9 s tell), then crackle for 0.4 s. They hurt within 3 px. **It vents after.** "Twice" means a second set lands in the first set's gaps after a 0.9 s tell of its own.
- **Insulator Volley:** three landing circles appear around the Surge (1 s tell), one where it stands. Each bursts into a ring of 6 bolts. The circle's own tell covers its ring, so standing on a circle is like standing on a marked mine.
- **Cover:** Live Wire's lines and the volley's circles ignore walls and props, as they are drawn. In the open chamber that rarely matters, and the answer is always to step away or dodge, never to hide.

### 4.3 Transformer (sector 2): "bait it, then punish it"
- **Look** (presentation step): a massive bull of a machine. It has a low, broad head with bushings as horns, a grille mouth, radiator fins that steam, and four heavy legs.

| Phase | Rotation | Gap |
| --- | --- | --- |
| 1 | Quake, Bull Charge | 3.7 s |
| 2 | Coolant Spray, Double Quake (0.5 s apart), Bull Charge | 3.2 s |
| 3 | Coolant Spray, Double Quake, Bull Charge twice | 2.7 s |

- **Bull Charge:** a lane is marked toward the Surge (1 s tell). It runs at 3.6 px a tick, below the tunneling limit, for at most 110 ticks. It stops dead on a wall or a prop, and that stuns it into its vent. Touching the Surge on the way hurts and it keeps going. Its read differs from Clamp's lunge: a wide two-sided lane instead of a dotted aim line, and a much longer run.
- **Charge twice:** after the first run it re-aims with a 0.75 s tell and charges again. Only the second impact stuns it, and it drops up to three debris tiles at fixed offsets (any that would land outside the chamber are left out, so usually one or two by a wall). A charge runs through the Surge: one hit, then it carries on, never shoving the Surge down the lane.
- **Coolant Spray:** a fan of 7 slow orbs (0.8 s tell), then 6 more into the gaps 0.4 s later.

### 4.4 Grid Core (sector 3): the finale
- **Look** (presentation step): a towering reactor heart in a cage of armored plates, with a ring of red eyes, on long spider legs. In phase 3 the plates open on the burning core.

| Phase | Rotation | Gap |
| --- | --- | --- |
| 1 | Summon (two Arc Drones, skipped while two robots are up), Lattice | 4.7 s |
| 2 (its Overload) | Spiral (two arms), Lattice twice, Summon | 4 s |
| 3 | Core Spiral (four arms), Lattice twice | 3.5 s |

- **Lattice:** a checkerboard of 32 px cells over 5 x 3 cells around the Surge (1 s tell), burning for 0.8 s. A cell is two tiles wide, so the Surge fits inside a dark one with room to spare, and one dodge (29 px) crosses a cell. Insulate's own tiles are swept away when a Lattice starts, so they never cover a dark cell. Only cells inside the chamber burn.
- **Lattice twice:** the other color arms as the first burns, and lights 0.6 s after the first goes out, so the player has to move once.

### 4.5 Balance (four floor bot seeds and sampled protocol orders)
- **Health:** 48, 64 and 80.
- **Hit circle:** 18 px for the Linesman and Grid Core, 22 for the wider Transformer. The legacy single-arena Regulator keeps 14. The Transformer's radius also sizes body contact and its Bull Charge lane, and moves its projectile and quake origins outward by 4 px. Attack rotations, tells and timing values are the same.
- **Transformer radius follow-up:** With seed 3 and lateral/pressure, the bot enters sector 3 on tick 5,702 at either radius. The larger chassis changes its position by about half a pixel at the Fuse Box, enough to change its route and fight. The 22 px run finishes on tick 72,473, with 27 bus-room deaths and 3 chamber deaths. The protocol still runs for 64, 56 and 70 percent of the three fights. The test retains this case with an 80,000-tick limit, and seeds 2 and 4 retain 40,000. These are scripted bot runs for protocol coverage. Human difficulty is assessed at the playtest.
- **Protocol share of fight time before widening the Transformer:** 50 to 66 percent across the sectors and orders measured.
- **Bot boss fights:** about 8 to 13 s. A human is slower and the vents reward patience.
- **Chamber deaths:** none in sectors 1 and 2. Up to 3 in sector 3, where most deaths stay in the combat rooms, as before.

## 5. Build order and time
Each step is its own PR with an independent review. Adit merges.

| Step | What | Estimate or PR |
| --- | --- | --- |
| 1 | This document | 1.5 |
| 2 | The sim (phases, rotations, vents, the eight new kit attacks, the reward, guards, tests, hashes, bot balance) | 5, done overnight |
| 3 | Presentation implemented: new phase silhouettes, vent poses, entrance, notched bar, victory animation and results | PR #41 |
| 3 follow-up | Sound implemented: distinct attack-family, damage, vent and victory cues | [PR #42](https://github.com/Adit-Prabhu/overload/pull/42) |
| 4 | Fused-power protocol check on the new kits during the planned roster balance pass, with numbers in its PR | 1.5 |

The kit attacks are Arc Ring (existing), Double Ring, Live Wire, Insulator Volley, Quake (existing), Double Quake, Bull Charge, Coolant Spray, Summon (existing), Lattice, Spiral (existing) and Core Spiral. The variants "twice" reuse their base attack.

This lands on top of the fusion schedule (POWERS_AND_FUSION.md section 9), which already fills Nov 21 to 24. If both cannot fit before the Nov 25 playtest, the first thing to move is the Bulwark and Magnet pairs (spec cut order item 1).

## 6. Open points for Adit
- **Scope (cut order accepted Nov 19).** This adds to the G3 overrun already logged.
  - Cut order: phase 3 of each chassis first, then the Insulator Volley and the Coolant Spray.
  - The vent windows stay in every phase, so cutting phase 3 never leaves a chassis without one.
- **The reward (decided Nov 19):** spare charges. A battery refill would add nothing, since the Fuse Box refills the battery after every chamber and the third chamber ends the run.
- **The playtest on Nov 25.** Freeze the boss Tuning by Nov 23. The live suite (Nov 26 to 27) and the recording (Nov 28) then run the same `tuning_id` as the playtest, or their evidence is labelled with the other build.
- **If the rework is not ready:** the playtest runs the pre-rework kit and art. The new look needs the new hit circle and phases, so it does not ship alone.

## Sources
- [Q&A: The guns and dungeons of Enter the Gungeon](https://gamedeveloper.com/design/q-a-the-guns-and-dungeons-of-i-enter-the-gungeon-i-) (Game Developer): patterns prototyped by the gameplay programmer with the team's feedback.
- [Building Exit the Gungeon](https://www.gamedeveloper.com/design/building-i-enter-the-gungeon-i-s-dungeon-climbing-spin-off-i-exit-the-gungeon-i-) (Game Developer): "faster, more dense" boss patterns.
- [Enter the Gungeon boss guide](https://gameranx.com/features/id/47856/article/enter-the-gungeon-boss-guide) (Gameranx): the Lich's three pattern phases.
- [Opinion: Boss design, tips from a combat designer](https://gamedeveloper.com/design/opinion-boss-design---tips-from-a-combat-designer) (Game Developer): clean reads, wind-up length, generous holds, larger than life, "prove to the player how awesome they are".
- [What makes a good boss fight](https://choostgames.com/blog/what-makes-a-good-boss-fight/) (Choost Games): telegraphs, phases, rhythm, fairness, reward.
- [Ed Gorinstein on Tisiphone's chamber](https://threadreaderapp.com/scrolly/1311777010239193088) (a mirror of a social media thread): the chamber closing in during the fight.
