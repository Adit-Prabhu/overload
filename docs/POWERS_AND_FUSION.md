# Overload · Powers and chance fusion (spec)
Version 0.1 · November 17, 2026 · Status: proposed, for Adit's sign-off. Production scope past the G1 ceiling, so it goes in the G3 scope-lock proposal (Nov 30) like the floor and the bosses.

## 1. Why
Adit, Nov 17, after playing the sector 3 build: "right now the powers feel like an addition to the action part of the game, but I wanted it to be the focus". Stealing and fusing powers is the game's hook (GDD line 1), so the crafting gets most of the remaining production time.

The change in one paragraph: two new base powers (Bulwark and Magnet) make five. Any two different base powers fuse, so there are ten pairs. Each fusion rolls a rarity, rare, epic or legendary, and each rarity of a pair is its own named power. The first fusion of a pair is free. Fusing the same pair again costs one spare charge of each ingredient and rerolls it.

## 2. Rules that do not change
These come from AGENTS.md and the GDD and every part of this spec keeps them.
- **Deterministic.** The roll comes from the simulation, from a stream fed only by the run seed and the number of fusions so far. Replays and retries reproduce every roll.
- **Same in both conditions.** The fixed baseline must have "identical arena, moves, stats, unlocks and cues". The nth fusion of a run rolls the same rarity in both conditions for the same seed, whatever pair the player picks.
- **The rival sees no more than before.** It gets power-use counts, never rarities, the bank or the roll stream (hidden inventory and RNG stay hidden).
- **Base powers only, no recursion.** Fusions take two different base powers. A fused power is never an ingredient. The list is fixed, so this is still the GDD's limited fusion, not unrestricted fusion.
- **Ingredients are kept.** Fusing never removes a base power.
- **Two slots.** Q and E, as now.
- **Tells and readability.** Every new effect is readable by shape, not colour alone, and nothing new hurts the Surge.

## 3. Base powers
| Power | Carried by | Use (Q or E) | Evolution (two more charges) | Cooldown family |
| --- | --- | --- | --- | --- |
| Spark | Arc Drone | A fast spark along the aim (as now) | CHAIN: a hit arcs to one nearby robot | shot |
| Blink | Relay Bot | Teleport toward the cursor (as now) | OVERDRIVE: speed boost on arrival | teleport |
| Burst | Breaker | Knockback cone along the aim (as now) | WIDE: a wider, longer cone | pulse |
| **Bulwark** (new) | Sentry | A shield bubble around the Surge for 0.75 s. Hostile shots that touch it fizzle. It does not stop shockwaves, hazard tiles or bodies | REFLECT: absorbed shots fly back as sparks, reversed along the path they came in on | shield |
| **Magnet** (new) | Sweeper | A field at the aim point, up to 72 px away (it stops short of walls like a Blink). For 0.5 s it drags robots and loose charges within 44 px toward its centre. The Regulator is too heavy to move, as with Burst. No damage of its own | CRUSH: robots still in the field when it ends take 2 damage | pull |

Starting tuning, all in `Tuning` with guards: `bulwark_ticks 45`, `bulwark_radius player_radius + 8`, `bulwark_cooldown 150`, `magnet_range 72`, `magnet_radius 44`, `magnet_ticks 30`, `magnet_pull 1.5` px per tick (each step under the thinnest obstacle, walls win), `magnet_cooldown 120`, `magnet_crush_damage 2`.

**Why these robots.** The Sentry and the Sweeper carry nothing today, so the new powers need no new enemies. They get a glowing charge core in their power's colour so players can see they carry something.

**When they unlock.** Counted from `WAVES` in `src/overload/floor.py`:

| Power | Robots per run | First available | Spare charges by the end of sector 2 |
| --- | --- | --- | --- |
| Spark | 12 drones | sector 1 | about 7 |
| Magnet | 7 sweepers (4 in sector 1) | sector 1 | about 3 |
| Blink | 8 relays | sector 2 | about 4 |
| Bulwark | 5 sentries (3 in sector 2) | sector 2 | about 2 |
| Burst | 5 breakers (1 in sector 2) | sector 2 | 0 |

So the first pair (Spark + Magnet) can be fused in the first Fuse Box, and all ten pairs before sector 3, where the build matters most. Summoned drones and the hidden room's charge add a little on top.

## 4. Charges, cost and the roll
**Charges.** The first charge of a power unlocks it, as now. Every later charge goes into that power's bank and also counts toward its evolution, which still triggers at three absorbed in all. Spending banked charges never undoes an evolution.

**Cost.** The first fusion of a pair is free once both ingredients are unlocked. Fusing a pair again (a reroll) costs one banked charge of each ingredient (`refuse_cost 1`). The new result replaces the pair's old one, so rerolling a rare risks nothing, and rerolling an epic or a legendary is a real gamble.

**Odds.** Rare 60, epic 30, legendary 10 (`fuse_odds (60, 30, 10)`), shown in the menu.

**Guarantee.** After two rares in a row, the next roll is epic or better, at the same 30 to 10 ratio (75 and 25). The streak counts fusions of any pair.

**The roll stream.** Fusion n of a run (counting from 0) draws from its own `random.Random` seeded from the run seed and n only. It never touches `world.rng`, so fusing cannot shift any combat roll. Because the guarantee depends only on earlier rolls, the whole rarity sequence of a run is a function of its seed.

**Retries.** A sector retry restores the kit it entered with, including the bank, every pair's result and the fusion count. The same rolls come back after a retry, so dying cannot be used to reroll for free.

**Logs.** Every fusion is logged in the trace with the pair, n, the rarity, the cost and whether the guarantee applied, so analysis can account for luck. Replays record the fuse action, not its result, and recompute it.

**Fusing during play.** Tab opens the menu anywhere and pauses the game (Nov 17 decision). That stays. The cost is what stops endless mid-fight rerolls.

## 5. The ten pairs
Each pair has one mechanic, and each rarity adds a visible step on top of the one below it. A fused power keeps the cooldown family listed, which is also its evidence family (section 6). Within a pair, all three rarities have the same cooldown, so a higher rarity is stronger per use and never faster. Arc Trail and Shock Cone keep their current behaviour as the rare results of their pairs.

| Pair | Family | Rare | Epic | Legendary |
| --- | --- | --- | --- | --- |
| Spark + Blink | teleport | **Arc Trail**: Blink that leaves a trail pulsing damage (as now) | **Storm Step**: the trail lasts half again as long and pulses twice as often | **Thunderhead**: Storm Step, and the arrival fires a ring of 8 sparks |
| Spark + Burst | pulse | **Shock Cone**: Burst plus a fan of 3 sparks (as now) | **Shock Fan**: a fan of 5 sparks | **Overcurrent**: a fan of 5 sparks that chain like an evolved Spark |
| Spark + Bulwark | shield | **Static Guard**: Bulwark, and each absorbed shot fires a spark at the nearest robot | **Capacitor**: Static Guard, and when the shield drops it fires one spark along the aim per absorbed shot (at most 5) | **Tesla Dome**: Capacitor that lasts half again as long, and robots touching the dome take 1 damage every 10 ticks |
| Spark + Magnet | shot | **Lodestone**: a slow heavy spark that drags robots near its path toward it | **Lodestone Split**: it bursts into 4 sparks when it hits or expires | **Maelstrom**: it stops at the cursor and becomes a Magnet field for 1 s that zaps everything inside every 10 ticks |
| Blink + Burst | teleport | **Impact Blink**: Blink, then a full circle Burst on landing | **Shockfall**: the landing Burst reaches further and knocks harder | **Meteor**: Shockfall, and the take-off point bursts too |
| Blink + Bulwark | shield | **Phase Guard**: Blink with a Bulwark shield on arrival | **Aegis Step**: the arrival shield lasts half again as long and reflects | **Ghost Line**: Aegis Step, and the path leaves a barrier that eats hostile shots for 2 s |
| Blink + Magnet | teleport | **Undertow**: Blink, and a Magnet field stays at the take-off point for 1 s, dragging robots to where the Surge was | **Riptide**: the field ends with a full circle Burst | **Event Horizon**: the field lasts 2 s and zaps everything inside every 10 ticks before the Burst |
| Burst + Bulwark | shield | **Bastion**: a Bulwark shield that ends in a full circle Burst | **Rampart**: the shield reflects | **Citadel**: Rampart that lasts half again as long and pulses a full circle Burst every 20 ticks while up |
| Burst + Magnet | pulse | **Implosion**: a Magnet field that ends in a Burst at its centre | **Crusher**: twice the pull, and the end Burst clears hostile shots in the field | **Gravity Well**: the field lasts 2 s and the end Burst deals triple damage |
| Bulwark + Magnet | pull | **Lightning Rod**: a field at the aim point that pulls hostile shots in and eats them for 1 s | **Grounding Rod**: it pulls robots too | **Mirror Well**: Grounding Rod, and each eaten shot comes back out as a spark at the nearest robot |

Blink + Burst was unsupported in the G1 prototype to keep the scope small. Supporting it is part of this change.

**Building blocks.** Every effect above is assembled from parts the simulation already has (spark projectiles, trails, cone and full circle pulses, knockback, the boss ring's 8 exact vectors) plus the two new ones (shield bubble, Magnet field). No runtime trig, as now.

**Power step guard.** A test scene with fixed robots and a scripted aim measures damage per use. A legendary deals at most 1.75 times its rare, and an epic at most 1.35 times. The test fails if a tuning change breaks that. The rival-free bot runs over 8 seeds must keep sectors 1 and 2 at their current retry rate and sector 3 near one retry a run, with the bot fusing whatever it can.

## 6. What the rival sees
`config/evidence.json` version 4 replaces the five per-power counts with five per-family counts, so the kinds stay at 10, under the Worker's cap of 12:

| Kind | Label (written by the Worker, never the client) | Counts |
| --- | --- | --- |
| `shot_power_uses` | Spark-type shots used | Spark and the Spark + Magnet results |
| `teleport_uses` | Teleports used | Blink and the Spark + Blink, Blink + Burst and Blink + Magnet results |
| `pulse_uses` | Pulse blasts used | Burst and the Spark + Burst and Burst + Magnet results |
| `shield_uses` | Shields raised | Bulwark and the Spark + Bulwark, Blink + Bulwark and Burst + Bulwark results |
| `pull_uses` | Pull fields used | Magnet and the Bulwark + Magnet results |

Distance shares, shots per minute and dodges stay. Uses count only when the power actually fires on screen (version 3 rule). Rarity is never sent. The tactic catalogue (pressure, spacing, lateral) does not change.

This needs a Worker redeploy from main and one live smoke run, both by Adit (docs/DEPLOY.md). Until the redeploy, live requests carrying version 4 kinds fall back to the neutral tactic, labelled as fallback, as with version 3.

## 7. The Fuse Box screen
Tab opens it anywhere, the game pauses, and the left side keeps the loadout as now (up and down pick, Q and E equip).

The right side is the fusion bench:
- A row of the five base power icons. Locked ones show a padlock and no name.
- Two sockets. Left and right (or A and D) move along the row, Space or Enter puts the power in the next empty socket, pressing it again takes it out, Backspace empties both.
- With two powers socketed, the bench shows the pair's three results with their names, odds and rarity marks, the pair's current result highlighted, and the cost: FREE, or the two charges with the bank count of each.
- F fuses. A greyed F with a reason (STEAL BOTH POWERS FIRST, NOT ENOUGH CHARGES) when it cannot.

**The reveal.** The fusion takes effect in the simulation the moment F is pressed. The reveal is presentation only, so replays do not depend on it:
1. The sockets slide together (0.3 s).
2. The three rarity frames flicker in turn (0.5 s).
3. The result lands with its name, rarity frame and sting (0.4 s).

Any key skips to the end. With flash reduction on (UI-08), the legendary's white flash becomes an outline pulse, and no reveal flashes more than 3 times a second.

**Rarity marks (shape first, then colour).**

| Rarity | Pips | Frame | Colour token |
| --- | --- | --- | --- |
| rare | 1 | plain square | `px.rarity.rare`, cyan |
| epic | 2 | square with notched corners | `px.rarity.epic`, violet |
| legendary | 3 | square with four rays | `px.rarity.legendary`, gold |

The HUD slots show the same pips under the key glyph. A reroll of an equipped pair updates the slot in place.

## 8. Art and audio
Each item is checked on the contact sheet and in play, as before.
- **Icons:** Bulwark, Magnet and ten pair icons. The rarity shows through the frame and pips, so there are 12 icons, not 30.
- **Effects:**
  - Bulwark: bubble, absorb flick, reflect streak.
  - Magnet: field ring with inward dashes.
  - Fused results: each rarity of a pair reuses the pair's effects with its rarity tint and one added part (the extra ring, the barrier, the zaps).
  - Charges: two new charge orbs, a shield shape for Bulwark and a horseshoe for Magnet.
- **Robots:** the Sentry and the Sweeper get a glowing charge core.
- **Sound:** each cue has a visual twin, as the audio rules require.
  - Bulwark: `bulwark_up`, `bulwark_absorb` and `bulwark_reflect`.
  - Magnet: `magnet_field`.
  - Fusion stings: `fuse_rare`, `fuse_epic` and `fuse_legendary`.
- **Licence:** new art and audio are original and CC BY 4.0, as the rest.

## 9. Build order
Each step is its own branch and PR with an independent read-only review. Adit merges.

| Step | PR | Target |
| --- | --- | --- |
| 1 | This spec, decision rows | Nov 17 |
| 2 | The roll system: kit bank, cost, odds, guarantee, roll stream, retries, trace. Arc Trail and Shock Cone become the rare results of their pairs, with their epics and legendaries | Nov 18–19 |
| 3 | Bulwark and Magnet: drops, charge cores, evolutions, effects, sounds. Pinned replay hashes change here once, on purpose, because the Sentry and Sweeper start dropping charges | Nov 19–20 |
| 4 | Pairs with Spark (Bulwark and Magnet pairs) | Nov 20–21 |
| 5 | Pairs with Blink (Burst, Bulwark, Magnet) | Nov 21–22 |
| 6 | Burst + Bulwark, Burst + Magnet, Bulwark + Magnet | Nov 22–24 |
| 7 | The Fuse Box screen, reveal and HUD pips | Nov 23–25 |
| 8 | Evidence version 4 and the Worker. Then Adit redeploys and runs the smoke test | Nov 25 |
| 9 | Balance with the bot, Adit's playtest, record numbers in the PR | Nov 26–27 |

Recording is Nov 28 and the combined G2/G3 review is Nov 30.

**Cut order** if time runs short, first cut first:
1. Legendaries of the pairs fused least in Adit's playtest. Those pairs top out at epic, and the legendary's share moves to epic (60 and 40).
2. Epics of the same pairs.
3. Bulwark + Magnet, then Spark + Magnet.

The roll system, the two new base powers, Arc Trail, Shock Cone and the Fuse Box screen are not cut.

## 10. Evaluation
- The existing fairness question stays. Add one post-play question: "Did fusion results feel fair?" (1 to 5). No identities in the answers, as before.
- Each condition's analysis reports the rarity sequence per seed. Because the sequence is the same per seed in both conditions, it is controlled by design. Log it anyway.
- Evidence labels as before: fixture, replay and live results are reported separately.

## 11. Open points for Adit
- Names and the exact rarity effects are provisional and can change in their PRs.
- If rerolls feel too cheap or too stingy in play, `refuse_cost` and the odds are tuning values, not code changes.
