# Overload · Boss design (the Regulator's three chassis)
Version 0.1 · November 18, 2026 · Status: proposed, for Adit's sign-off. Production scope past the G1 ceiling, logged for the G3 scope-lock proposal like the floor and the chassis.

## 1. Why
Adit, Nov 18, after the first redraw: "the bosses need more work, like they don't have interesting attacks or attack patterns, and they look weird ... they don't look intimidating ... if it's the same as mobs then it doesn't feel different, beating a boss should feel like an achievement and I don't get that right now."

He is right on every count. Today a chassis is the protocol's attack plus one signature:

| Chassis | Health | What it does | Same as a mob? |
| --- | --- | --- | --- |
| Linesman | 36 | The protocol attack (a lunge, a slow orb, or a three-bolt fan), and every 5 s a ring of 8 bolts | The fan is the Relay Bot's, the ring is 8 Drone bolts at once |
| Transformer | 52 | The protocol attack, and every 4.5 s a wide shockwave | The quake is the Breaker's slam, bigger |
| Grid Core | 66 | The protocol attack, and every 7 s two Arc Drones. At half health, a two-arm spiral replaces the summons | The summons are mobs |

There is one phase (the Grid Core has two), no window where the player gets to punish, no entrance, and the death is a spark burst like any robot's. Nothing about it says "this is the fight of the sector".

## 2. What similar games do
I looked at how action roguelikes and boss-focused games build their bosses, from developer interviews and design writing (sources at the end). The patterns agree:

1. **Bosses speak a different language from mobs.** Mobs fire single shots. Bosses fire patterns: rings, walls with gaps, spirals, fans in sequence, sweeping lines, attacks on the arena itself. Enter the Gungeon's bosses (the Bullet King, the Lich) are built from expanding rings, spirals and dense sweeps that no regular enemy uses, and its spin-off made boss patterns "faster, more dense" still. The pattern is the boss's identity.
2. **Every attack has its own clean read.** A combat designer's rule: attacks need "clean reads", and two attacks must never share a wind-up or a sound. Big bodies get weight from slower, longer wind-ups, with 1 to 1.5 s as the sweet spot and no gain past 2 s.
3. **Phases.** A boss that is the same from full health to zero is boring. Phases should expand or subvert earlier patterns, and the tempo should build like a crescendo. Supergiant's final Hades boss has three phases. Hades changes the arena mid-fight (Tisiphone's chamber constricts as the fight goes on).
4. **Punish windows make the player feel strong.** After a big attack the boss is open, and the window must be generous. "Prove to the player how awesome they are, not how awesome the boss is." Exaggerated hits and reactions sell it.
5. **Bosses are not subtle.** They are larger than life, with exaggerated hits and reactions. Spectacle and atmosphere (music that answers the phases, an entrance, a death) carry the emotional peaks.
6. **Fair deaths.** Every attack telegraphed, with a window to respond. A good test is a player watching their own death thinking "oh, I see what I should have done", or saying "I almost had it".
7. **Reward.** Beating a boss should pay off both mechanically (a drop, progress) and emotionally (music, a change in the world). If a player wins and feels nothing, the fight lacked challenge or payoff.

How a boss should look, from the same sources and from pixel art bosses in the genre:
- **Silhouette first:** each boss is a distinct shape that reads at a glance, and keeps it across phases while color and light escalate.
- **Proportions carry menace:** a heavy mass with a low head and a forward lean reads as threat. Round, chibi proportions read as cute, which is exactly what the first redraw had.
- **Dark armor with glowing accents:** dark shells, bright eyes (slits, not round lenses), rim light. Jagged or clawed limbs read as dangerous.
- **Scale:** bosses tower. In this game's 256 x 144 view the Surge is 16 x 22, so a boss should be roughly three times its height.

## 3. Rules this game must keep (unchanged)
The study needs these, so every proposal below stays inside them:
- The **protocol** (Clamp, Insulate, Oscillate) is still the only thing the rival model chooses. It still decides how the Regulator moves and its protocol attack.
- The **chassis kit** is fixed per sector and identical in both comparison conditions. The kit never reads the model's observations.
- Deterministic for the same inputs and seed, and fully playable with the model off. Any randomness comes from the world RNG.
- Telegraphs fill up, use `hostile.danger` plus a pattern, and last at least 0.5 s (chassis attacks at least 0.75 s, see section 4).
- No legal loadout trivializes a protocol. Dodge's invulnerability answers every attack.
- Any change to sim state or Tuning re-pins the replay hashes on Python 3.11 and 3.12.

## 4. The design

### 4.1 What every chassis gets
- **Three phases**, at two thirds and one third of its health. The health bar shows two notches.
- **Phase change** (about 1.2 s): the chassis is shielded and roars. A shockwave pushes the Surge back without hurting it. Every hostile shot in the room is wiped. The room's lamps flicker and come back harder. Then the next phase starts with one new attack and a quicker pace. Nothing hits the Surge during the change, so the player can breathe and see that the fight has turned.
- **A rotation of chassis attacks**, its own patterns that no mob uses. Each phase cycles through its list in a fixed order. They interleave with the protocol's attack the same way the signature does today: the protocol waits while one runs.
- **A punish window.** After its biggest attack each chassis **vents** for 1.5 s. It stands still, its core is exposed with steam and light, and it takes 1.5 times damage. This is when the player wins the fight.
- **Distinct reads.** Every chassis attack has its own wind-up pose, its own floor marking, and its own sound. Tells last 0.75 to 1.2 s.
- **An entrance.** It uses the existing 1.5 s boot: the camera settles on the chassis, a name card slides in (LINESMAN, then the sector), and the music drops into the boss stem.
- **A death that lands.** Chained explosions over the body for about 1.5 s, a white flash, the chassis collapses, the sector's lights come back on and a banner reads "LINESMAN DOWN". **Reward:** one spare charge of every power the Surge has stolen, which feeds the Fuse Box's rerolls. The time to beat it shows on the ending readout.

### 4.2 Linesman (sector 1): "read the pattern, find the gap"
The first boss teaches pattern reading. It stays at range and fills the air.
- **Look:** a gaunt, hunched giant built on a utility pole spine. Its crossarm forms the shoulders, with insulators standing up as spikes. A dark hood has a slit of three red eyes. Long arms end in lineman's hooks, and the legs have climbing gaffs.
- **Phase 1:**
  - **Arc Ring:** 8 bolts in a ring. This one exists today.
  - **Live Wire:** three dotted lines fan from its crossarm toward the Surge (0.9 s tell), then each becomes a crackling line for 0.4 s. Step between them or dodge through.
  - **Vents after Live Wire.**
- **Phase 2:**
  - **Double Ring:** a second ring 0.25 s after the first, offset by half a gap, so a moving player threads it.
  - **Insulator Volley:** three slow insulators lob to marked circles around the Surge, and each bursts into a ring of 6 on landing.
- **Phase 3:** Live Wire fires twice, the second set landing in the first set's gaps. The rotation quickens.

### 4.3 Transformer (sector 2): "bait it, then punish it"
The second boss teaches baiting. It is all weight.
- **Look:** a massive bull of a machine. It has a low, broad head with two bushings as horns, a glowing grille for a mouth, radiator fins that steam, and four heavy legs.
- **Phase 1:**
  - **Quake:** this one exists today.
  - **Bull Charge:** it paws the floor, and a lane is marked from it toward the Surge (1.0 s tell). It charges down the lane at dash speed until it hits a wall. A wall impact shakes the room and **stuns it for 1.5 s**, its punish window. Baiting it into a wall is the skill.
- **Phase 2:**
  - **Coolant Spray:** a fan of 7 slow orbs, then a second fan offset into the gaps.
  - **Double Quake:** two rings, 0.5 s apart.
- **Phase 3:** two Bull Charges back to back, the second one re-aimed. A wall impact drops three marked debris tiles near the impact.

### 4.4 Grid Core (sector 3): the finale
The final boss controls the arena itself.
- **Look:** a towering reactor heart in a cage of armored plates, with a ring of many red eyes, on long spider legs. In phase 3 the plates open and show the burning core.
- **Phase 1:**
  - **Summon:** two Arc Drones. This one exists today.
  - **Lattice:** a checkerboard of hazard tiles lights up around the Surge (1.0 s tell), then burns for 0.8 s. Stand on a dark tile.
- **Phase 2 (its Overload):**
  - **Spiral:** this one exists today.
  - **Lattice** now fires twice, the second time on the other color, so the player has to move again.
- **Phase 3:**
  - **Core Exposed:** the plates open and it fires a four-arm spiral.
  - **Vents after the spiral:** 2 s, double damage.
  - Summons stop, so it is just the player and the core.

## 5. Balance
- **Health:** about 48 (Linesman), 64 (Transformer) and 80 (Grid Core). Fights should last about 60 s, 75 s and 90 s for a player who uses the punish windows. They are longer than today's because the vents give the damage back.
- **Hit circle:** from 14 px to 18 px, to match bodies drawn about three times the Surge's height. The body center sits on the circle (as in #37).
- **Checks:** the floor bot must still clear the floor on 8 seeds in every protocol (spec section 9, step 8), and tells stay readable under the Tuning guards.

## 6. Build order
Each step is its own PR with an independent review. Adit merges.
1. This document.
2. **The sim:**
   - phases, the phase change and the vent window
   - the rotation and the nine new attacks, plus their tells
   - the reward
   - the Tuning guards
   - tests, re-pinned hashes, and balance with the floor bot
3. **The look:**
   - the three intimidating chassis at boss scale, with idle and walk animation
   - the vent and core-exposed poses, the attack wind-ups and floor markings
   - the name card, the phase-change effect, the death sequence, the notched health bar
   - new sound cues

## 7. Open points for Adit
- **Scope:** this adds to the G3 overrun already logged (the floor, the chassis, the fusion overhaul). The cut order if time runs short: Phase 3 of each boss first, then the Insulator Volley and the Coolant Spray. The phase change, the vent windows and the death sequence are the core of the "achievement" feeling and are not cut.
- **The reward:** one spare charge of every stolen power, or a full battery refill?
- **The playtest on Nov 25:** a boss rework this close needs a balance pass before it. If it is not settled by Nov 23, the playtest runs on the current kit, with the new look and presentation only.

## Sources
- [Q&A: The guns and dungeons of Enter the Gungeon](https://gamedeveloper.com/design/q-a-the-guns-and-dungeons-of-i-enter-the-gungeon-i-) and [Building Exit the Gungeon](https://www.gamedeveloper.com/design/building-i-enter-the-gungeon-i-s-dungeon-climbing-spin-off-i-exit-the-gungeon-i-) (Game Developer): how bullet patterns were prototyped, and denser, faster boss patterns.
- [Enter the Gungeon interview with Dave Crooks](https://gameranx.com/features/id/48447/article/enter-the-gungeon-interview-with-dodge-rolls-dave-crooks-the-past-present-and-future/) (Gameranx): who designed the enemy and boss patterns.
- [Enter the Gungeon boss guide](https://gameranx.com/features/id/47856/article/enter-the-gungeon-boss-guide) (Gameranx): the phases of the Lich and other bosses.
- [Opinion: Boss design, tips from a combat designer](https://gamedeveloper.com/design/opinion-boss-design---tips-from-a-combat-designer) (Game Developer): clean reads, wind-up length, generous holds, larger than life.
- [What makes a good boss fight](https://choostgames.com/blog/what-makes-a-good-boss-fight/) (Choost Games): telegraphs, phases, rhythm, fairness, reward.
- [Boss fights will never be the same](https://gamedeveloper.com/design/boss-fights-will-never-be-the-same) (Game Developer): how Hades keeps bosses fair and varied.
- [Ed Gorinstein on Tisiphone's chamber](https://threadreaderapp.com/scrolly/1311777010239193088): the arena changing during a Hades boss fight.
- [Greg Kasavin on Hades](https://inlander.com/culture/hades-writer-greg-kasavin-on-how-he-made-video-game-deaths-drive-a-feel-good-story-22725237) (Inlander): the final boss's three phases.
