# Overload · Powers and chance fusion (spec)
Version 0.2 · November 17, 2026 · Status: proposed, for Adit's sign-off. Production scope past the G1 ceiling, so it goes in the G3 scope-lock proposal (Nov 30) like the floor and the bosses. Version 0.2 takes in the independent review of version 0.1 (PR #30) and the measured values of the roll system (PR #31).

## 1. Why
Adit, Nov 17, after playing the sector 3 build: "right now the powers feel like an addition to the action part of the game, but I wanted it to be the focus". Stealing and fusing powers is the game's hook (the GDD's one-line pitch), so the crafting gets most of the remaining production time.

The change in one paragraph: two new base powers (Bulwark and Magnet) make five. Any two different base powers fuse, so there are ten pairs. Each fusion rolls a rarity, rare, epic or legendary, and each rarity of a pair is its own named power. The first fusion of a pair is free. Fusing the same pair again costs one spare charge of each ingredient and rerolls it.

## 2. Rules that do not change
These come from AGENTS.md and the GDD and every part of this spec keeps them.
- **Deterministic.** The roll comes from the simulation, from a stream fed only by the run seed and the number of fusions so far. Replays and retries reproduce every roll.
- **Same in both conditions.** The fixed baseline must have "identical arena, moves, stats, unlocks and cues". The nth fusion of a run rolls the same rarity in both conditions for the same seed, whatever pair the player picks.
- **The rival sees no more than before.** It gets power-use counts, never rarities, the bank or the roll stream (hidden inventory and RNG stay hidden).
- **Base powers only, no recursion.** Fusions take two different base powers. A fused power is never an ingredient. The list is fixed, so this is still the GDD's limited fusion, not unrestricted fusion.
- **Ingredients are kept.** Fusing never removes a base power.
- **Two slots.** Q and E, as now.
- **Tells and readability.** Every new effect is readable by shape, not color alone, and nothing new hurts the Surge.
- **The Regulator.** Anything that damages a robot also damages the Regulator (through its boot shield, as now). Nothing moves it: it is too heavy for knockback or pull, as with Burst.

## 3. Base powers
| Power | Carried by | Use (Q or E) | Evolution (two more charges) | Cooldown family |
| --- | --- | --- | --- | --- |
| Spark | Arc Drone | A fast spark along the aim (as now) | CHAIN: a hit arcs to one nearby robot | shot |
| Blink | Relay Bot | Teleport toward the cursor (as now) | OVERDRIVE: speed boost on arrival | teleport |
| Burst | Breaker | Knockback cone along the aim (as now) | WIDE: a wider, longer cone | pulse |
| **Bulwark** (new) | Sentry | A shield bubble around the Surge for 45 ticks (0.75 s). Hostile shots that touch it fizzle. It does not stop shockwaves, hazard tiles or bodies | REFLECT: absorbed shots fly back as sparks, reversed along the path they came in on | shield |
| **Magnet** (new) | Sweeper | A field at the aim point, up to 72 px away. It is placed like a Blink lands: as far along the aim as it can, never inside a prop or behind a wall. With nowhere valid, the use is rejected, keeps its cooldown free and is not counted, as a Blink is. For 30 ticks (0.5 s) it drags robots and loose charges within 44 px toward its center. No damage of its own | CRUSH: robots still in the field when it ends take 2 damage | pull |

Starting tuning, all in `Tuning` with guards: `bulwark_ticks 45`, `bulwark_radius 14.0` (the Surge's radius plus 8, written out because a dataclass default cannot refer to another field), `bulwark_cooldown 150`, `magnet_range 72`, `magnet_radius 44`, `magnet_ticks 30`, `magnet_pull 1.5` px per tick (each step under the thinnest obstacle, walls win), `magnet_cooldown 120`, `magnet_crush_damage 2`.

**Fusions inherit evolutions.** A fused power uses its ingredients' evolutions, as Shock Cone's sparks chain and Arc Trail gets Overdrive today. So no rarity step may be something an evolution already gives (a legendary that "chains" when Spark chains anyway would add nothing). The power step guard (section 5) runs with the ingredients both stock and evolved.

**Why these robots.** The Sentry and the Sweeper carry nothing today, so the new powers need no new enemies. They get a glowing charge core in their power's color so players can see they carry something.

**When they unlock.** Counted from `WAVES` in `src/overload/floor.py`:

| Power | Robots per run | First available | Spare charges by the end of sector 2 |
| --- | --- | --- | --- |
| Spark | 13 drones | sector 1 | 8 |
| Magnet | 8 sweepers (5 in sector 1) | sector 1 | 4 |
| Blink | 8 relays | sector 2 | 4 |
| Bulwark | 5 sentries (3 in sector 2) | sector 2 | 2 |
| Burst | 5 breakers (1 in sector 2) | sector 2 | 0 |

So the first pair (Spark + Magnet) can be fused in the first Fuse Box, and all ten pairs before sector 3, where the build matters most. The Grid Core's summoned drones add a few Spark charges in sector 3's chamber. The hidden room's evolution charge is planned (IMPLEMENTATION_PLAN section 2b) but not built, so the table leaves it out.

**Slots.** A newly unlocked base power fills an empty slot, as now, and never replaces an equipped one. A fusion result is never equipped automatically. With Magnet in sector 1, the Surge usually enters sector 2 with Spark and Magnet equipped, so Blink no longer equips itself there. The unlock banner adds TAB TO EQUIP when both slots are full. This changes sector 2 for a player who never opens the menu. Step 3 measures it with the bot, which equips the newest base power to E in each Fuse Box.

## 4. Charges, cost and the roll
**Charges.** The first charge of a power unlocks it, as now. Every later charge goes into that power's bank and also counts toward its evolution, which still triggers at three absorbed in all. Spending banked charges never undoes an evolution. A charge picked up after full evolution still says FULLY EVOLVED (GDD) and adds one to the bank.

**Cost.** The first fusion of a pair is free once both ingredients are unlocked. Fusing a pair again (a reroll) costs one banked charge of each ingredient (`reroll_cost 1`). The new result replaces the pair's old one, so rerolling a rare risks nothing, and rerolling an epic or a legendary is a real gamble. A reroll the bank cannot pay for changes nothing.

**Odds.** Rare 60, epic 30, legendary 10 (`fuse_odds (60, 30, 10)`), shown in the menu.

**Guarantee.** After two rares in a row (`fuse_guarantee_after 2`), the next roll is epic or better, at the same 30 to 10 ratio (75 and 25). The streak counts fusions of any pair.

**The roll stream.** Fusion n of a run (counting from 0) makes one draw from `random.Random(f"overload-fusion:{seed}:{n}")`, an integer below the sum of the weights, compared against the cumulative weights. It never touches `world.rng`, so fusing cannot shift any combat roll. Because the guarantee depends only on earlier rolls, the whole rarity sequence of a run is a function of its seed.

**Retries.** A sector retry restores the kit it entered with, including the bank, every pair's result, the fusion count and the streak. The same rolls come back after a retry, so dying never rerolls for free.

**A known gap, accepted.** First fusions are free, so a player could fuse a pair they do not care about mid-sector, see roll n, go down on purpose, retry, and spend that known roll on the pair they want. It needs deliberate deaths, only moves luck between pairs and does not create any. Fusions undone by a retry appear in the trace twice with the same n, so analysis can spot it. A stream per pair would close it but would break the guarantee across pairs, so the design keeps one stream.

**Logs.** Every fusion is logged in the trace with the pair, n, the rarity, the cost and whether the guarantee applied, and the session's first row logs the run seed (both built in PR #31). Replays record the fuse action, not its result, and recompute it.

**Fusing during play.** Tab opens the menu anywhere and pauses the game (Nov 17 decision). That stays. The cost is what stops endless mid-fight rerolls.

## 5. The ten pairs
Each pair has one mechanic, and each rarity adds a visible step on top of the one below it. A fused power keeps the cooldown family listed, which is also its evidence family (section 6). Within a pair, all three rarities have the same cooldown, so a higher rarity is stronger per use and never faster. Arc Trail and Shock Cone keep their current behavior as the rare results of their pairs.

Every result that teleports is in the teleport family, so a Blink and any teleporting fusion share one cooldown and two slots can never teleport twice in one tick (the Nov 17 decision on Blink and Arc Trail). "Epic, and" below means everything the epic does, plus the step.

| Pair | Family | Guard metric | Rare | Epic | Legendary |
| --- | --- | --- | --- | --- | --- |
| Spark + Blink | teleport | damage | **Arc Trail**: Blink that leaves a trail pulsing damage (as now) | **Storm Step**: the trail lasts 138 ticks instead of 120 and reaches 5 px past a body instead of 4 | **Thunderhead**: epic, and the landing fires a ring of 8 one-damage sparks that never chain |
| Spark + Burst | pulse | damage | **Shock Cone**: Burst plus a fan of 3 sparks (as now) | **Shock Fan**: a fan of 5, the outer pair at 1 damage | **Overcurrent**: epic, and the inner three sparks chain twice, one robot further than an evolved Spark |
| Spark + Bulwark | shield | shots stopped | **Static Guard**: Bulwark, and each absorbed shot fires a spark at the nearest robot | **Capacitor**: rare, and when the shield drops it fires one spark along the aim per absorbed shot (at most 3) | **Tesla Dome**: epic, the shield lasts 60 ticks, and robots touching it take 1 damage every 15 ticks |
| Spark + Magnet | shot | damage | **Lodestone**: a slow heavy spark that drags robots near its path toward it | **Lodestone Split**: it bursts into 4 light sparks when it hits or expires | **Maelstrom**: epic, and it stops at the cursor and holds a Magnet field for 45 ticks that zaps everything inside every 15 ticks |
| Blink + Burst | teleport | damage | **Impact Blink**: Blink, then a full circle Burst on landing | **Shockfall**: the landing Burst reaches 25 percent further and knocks harder | **Meteor**: epic, and the take-off point bursts too, for 1 damage |
| Blink + Bulwark | teleport | shots stopped | **Phase Guard**: Blink with a Bulwark shield on arrival | **Aegis Step**: the arrival shield lasts 60 ticks | **Ghost Line**: epic, and the path leaves a barrier that eats hostile shots for 90 ticks |
| Blink + Magnet | teleport | pull distance | **Undertow**: Blink, and a Magnet field stays at the take-off point for 60 ticks, dragging robots to where the Surge was | **Riptide**: the field ends with a full circle Burst | **Event Horizon**: epic, the field lasts 90 ticks and zaps everything inside every 15 ticks |
| Burst + Bulwark | shield | shots stopped | **Bastion**: a Bulwark shield that ends in a full circle Burst | **Rampart**: the end Burst reaches 50 percent further | **Citadel**: epic, the shield lasts 60 ticks and also bursts when raised |
| Burst + Magnet | pulse | damage | **Implosion**: a Magnet field that ends in a Burst at its center | **Crusher**: twice the pull, and the end Burst clears hostile shots in the field | **Gravity Well**: epic, the field lasts 60 ticks and the end Burst deals 3 instead of 2 |
| Bulwark + Magnet | pull | shots eaten | **Lightning Rod**: a field at the aim point that pulls hostile shots in and eats them for 60 ticks | **Grounding Rod**: the field lasts 75 ticks and pulls robots too | **Mirror Well**: epic, and each eaten shot comes back out as a spark at the nearest robot |

The first two rows are built and measured (PR #31). The rest are starting points, provisional like every name and number in the GDD, and the guard below decides their final values.

Blink + Burst was unsupported in the G1 prototype to keep the scope small. Supporting it is part of this change.

**Building blocks.** Every effect above is assembled from parts the simulation already has (spark projectiles, trails, cone and full circle pulses, knockback, the boss ring's 8 exact vectors) plus the two new ones (shield bubble, Magnet field). No runtime trig, as now.

**Power step guard.** Each pair is checked on its guard metric, averaged over fixed scripted scenes, with the ingredients both stock and evolved:
- **damage:** total damage dealt in 40 fixed scenes of four still robots in front of the Surge (built in PR #31)
- **shots stopped** and **shots eaten:** hostile shots that never reach the Surge, in fixed scripted volleys of Sentry shells and needle fans
- **pull distance:** the total distance robots are dragged toward the field

An epic must beat its rare and stay at or under 1.35 times it. A legendary must beat its epic and stay at or under 1.75 times the rare. Where a rarity adds damage to a pair whose metric is not damage, that added damage per use stays at or under Shock Cone's rare damage per use in the damage scenes. The measured first two pairs:

| Pair | Epic, stock | Legendary, stock | Epic, evolved | Legendary, evolved |
| --- | --- | --- | --- | --- |
| Spark + Blink | 1.20 | 1.61 | 1.20 | 1.61 |
| Spark + Burst | 1.16 | 1.53 | 1.27 | 1.36 |

Version 0.1's first numbers (a trail twice as dense and half again as long, five full sparks, sparks that only chain) measured 1.4 to 3 times the rare, which is why the table above was lowered.

**Every protocol stays answerable.** Bulwark, the shield results and Lightning Rod answer projectile attacks (Insulate orbs, Oscillate needles, the ring and the spiral). The GDD requires every legal loadout to have a viable answer to every tactic, and none to make one trivial. With Bulwark at 45 ticks of shield every 150, about 30 percent uptime, the bot's Regulator fight time per protocol with a shield power equipped must stay at least 70 percent of its time without. Steps 3 and 6 check it.

The bot runs over 8 seeds must keep sectors 1 and 2 at their current retry rate and sector 3 near one retry a run, with the bot fusing whatever it can.

## 6. What the rival sees
`config/evidence.json` version 4 replaces the five per-power counts with five per-family counts. That keeps 10 kinds, under the Worker's cap of 12 summary items (`MAX_SUMMARY_ITEMS` in `worker/src/schema.ts`):

| Kind | Label (written by the Worker, never the client) | Counts |
| --- | --- | --- |
| `shot_power_uses` | Spark-type shots used | Spark and the Spark + Magnet results |
| `teleport_uses` | Teleports used | Blink and the Spark + Blink, Blink + Burst, Blink + Bulwark and Blink + Magnet results |
| `pulse_uses` | Pulse blasts used | Burst and the Spark + Burst and Burst + Magnet results |
| `shield_uses` | Shields raised | Bulwark and the Spark + Bulwark and Burst + Bulwark results |
| `pull_uses` | Pull fields used | Magnet and the Bulwark + Magnet results |

Distance shares, shots per minute and dodges stay. Uses count only when the power actually fires on screen (version 3 rule). Rarity is never sent. The tactic catalogue (pressure, spacing, lateral) does not change.

This needs a Worker redeploy from main and one live smoke run, both by Adit (docs/DEPLOY.md). Until the redeploy, live requests carrying version 4 kinds fall back to the neutral tactic, labelled as fallback, as with version 3. The trace's `config_hash` does not cover `config/evidence.json` today. Step 8 adds it, so traces from the two versions can be told apart.

## 7. The Fuse Box screen
Tab opens it anywhere, the game pauses, and the left side keeps the loadout as now (up and down pick, Q and E equip).

**The left list.** Five base powers and up to ten fused results do not fit in the panel's eight rows. The list shows the base powers first, then the fused results, seven rows at a time, and scrolls with W and S. Arrows above and below show when more rows are hidden.

The right side is the fusion bench:
- A row of the five base power icons. Locked ones show a padlock and no name.
- Two sockets. Left and right (or A and D) move along the row. Space puts the power in the next empty socket, and pressing it again takes it out. Backspace empties both. Enter stays Continue in the Fuse Box, so it never sockets.
- With two powers socketed, the bench shows the pair's three results with their names, odds and rarity marks, the pair's current result highlighted, and the cost: FREE, or the two charges with the bank count of each.
- F fuses. A greyed F with a reason (STEAL BOTH POWERS FIRST, NO SPARE CHARGES) when it cannot.

**The reveal.** The fusion takes effect in the simulation the moment F is pressed. The reveal is presentation only, so replays do not depend on it:
1. The sockets slide together (0.3 s).
2. The three rarity frames light one after another, a steady outline held 0.35 s each, with no flashing.
3. The result lands with its name, rarity frame and sting (0.4 s).

Any key skips to the end, and the key that skips does nothing else, so a skip can never fuse again or spend charges. Nothing in the reveal flashes more than 3 times a second. Flash reduction (UI-08) is not built yet, so the safe behavior is the default: the legendary's landing is an outline pulse, never a white flash.

**Rarity marks (shape first, then color).** Built in PR #31 for the interim menu.

| Rarity | Marks | Frame | Color token |
| --- | --- | --- | --- |
| rare | 1 cross | plain square | `px.rarity.rare`, steel |
| epic | 2 crosses | square with notched corners | `px.rarity.epic`, mint |
| legendary | 3 crosses | square with four rays | `px.rarity.legendary`, champagne |

Crosses, so they never read as the square evolution pips. The colors are hues no power, robot, hazard or chassis uses, and they appear only in menus and the HUD slots, never in the world. The HUD slots show the same marks under the key glyph. A reroll of an equipped pair updates the slot in place.

## 8. Art and audio
Each item is checked on the contact sheet and in play, as before.
- **Icons:** Bulwark, Magnet and ten pair icons. The rarity shows through the frame and marks, so there are 12 icons, not 30.
- **Effects:**
  - Bulwark: bubble, absorb flick, reflect streak.
  - Magnet: field ring with inward dashes.
  - Fused results look like their ingredients combined (art direction rule 5). A rarity shows by its added part (the ring of sparks, the barrier, the zaps), never by a tint.
  - Charges: two new charge orbs, a shield shape for Bulwark and a horseshoe for Magnet.
- **Power colors:** Bulwark's and Magnet's colors are chosen with their style frame in step 3. They must differ from the hostile colors, the three existing power colors, the chassis shells and the rarity tokens.
- **Robots:** the Sentry and the Sweeper get a glowing charge core.
- **Sound:** each cue has a visual twin, as the audio rules require.
  - Bulwark: `bulwark_up`, `bulwark_absorb` and `bulwark_reflect`.
  - Magnet: `magnet_field`.
  - Fusion stings: `fuse_rare`, `fuse_epic` and `fuse_legendary`.
- **License:** new art and audio are original and CC BY 4.0, as the rest.

## 9. Build order
Each step is its own branch and PR with an independent read-only review. Adit merges. Every step that changes rules, world state or tuning changes the pinned replay hashes and `tuning_id`. Each such PR re-pins them on purpose, checks them on Python 3.11 and 3.12, and says why in its body. Old replays stop verifying at each change, as with every earlier tuning change.

| Step | PR | Target | Hours |
| --- | --- | --- | --- |
| 1 | This spec, decision rows | Nov 17 | 1 |
| 2 | The roll system: bank, cost, odds, guarantee, roll stream, retries, trace, seed in the trace. Arc Trail and Shock Cone with their epics and legendaries (PR #31) | Nov 17–18 | 3 |
| 3 | Bulwark and Magnet: drops, charge cores, evolutions, effects, sounds, slotting banner, protocol check | Nov 18–20 | 4 |
| 4 | Spark + Bulwark, Spark + Magnet | Nov 20 | 2 |
| 5 | Blink + Burst, Blink + Bulwark, Blink + Magnet | Nov 21 | 3 |
| 6 | Burst + Bulwark, Burst + Magnet, Bulwark + Magnet | Nov 22 | 3 |
| 7 | The Fuse Box screen, reveal and HUD marks | Nov 22–24 | 4 |
| 8 | Evidence version 4, `config_hash` covering it, the Worker. Then Adit redeploys and runs the smoke test | Nov 24 | 1.5 |
| 9 | Balance with the bot, record numbers in the PR | Nov 26–27 | 2 |

About 23 hours in all. That is on top of the 40 hours of D3, which the floor, robots and bosses have already used, so the G3 proposal states the overrun. The external playtest on Nov 25 (task 12) plays the full system, so steps 7 and 8 land the day before. The small live suite (task 13, Nov 26–27) runs only after the version 4 redeploy, so its results never mix the two evidence versions. Recording is Nov 28 and the combined G2/G3 review is Nov 30.

**Cut order** if time runs short, first cut first:
1. Legendaries of the pairs fused least in the playtest. Those pairs top out at epic.
2. Epics of the same pairs. A pair left with only a rare cannot be rerolled (F says so), since a reroll could only give the same result.
3. Bulwark + Magnet, then Burst + Bulwark.

When a pair is capped, the roll and the guarantee still run on the full odds, so the rarity sequence stays the same whatever pair is fused. The capped pair takes the best rarity it has at or below the roll, and the trace logs both the roll and the result. Spark + Magnet is never cut, because it is the only pair in the first Fuse Box.

This replaces the G1 cut order for powers ("second cross-type recipe" first). Shock Cone, the roll system, Bulwark, Magnet, Arc Trail and the Fuse Box screen are not cut by this order. If the instructor does not approve the scope at G3, the fallback is the G1 production ceiling: Spark, Blink and Burst, Arc Trail and Shock Cone, and no rarities.

**Risks.** The mechanics count and the timeline are the new risks: 27 new effects in 9 days, against a playtest on Nov 25. The cut order above is the mitigation. They go into the Update Risk Register with the G3 package (task 13).

## 10. Evaluation
- The existing fairness question stays. Add one post-play question: "Did fusion results feel fair?" (1 to 5). It changes the playtest protocol, so it is recorded with the other G3 protocol changes. No identities in the answers, as before.
- Every fusion's roll is in the trace, and the session's seed is in its first row, so analysis can line up rarity sequences by seed and account for luck. Because the nth roll of a seed is the same in both conditions, luck is controlled by design when a participant plays both conditions on one seed.
- Evidence labels as before: fixture, replay and live results are reported separately.

## 11. Open points for Adit
- **The seed rule.** The game uses seed 1 unless given another. Recommendation: each participant plays both conditions on one seed, and different participants get different seeds. One seed per participant controls luck between that player's two conditions, at the cost of meeting the same rarity sequence twice (a possible learning effect). If that effect shows, the analysis can compare first sessions only.
- Names and the exact rarity effects are provisional and can change in their PRs.
- If rerolls feel too cheap or too stingy in play, `reroll_cost` and the odds are tuning values, not code changes.
