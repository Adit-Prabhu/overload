# Overload · Powers and chance fusion (spec)
Version 0.3 · November 17, 2026 · Status: proposed, for Adit's sign-off. Production scope past the G1 ceiling, so it goes in the G3 scope-lock proposal (Nov 30) like the floor and the bosses. Version 0.2 took in the independent review of version 0.1. Version 0.3 follows Adit's play of the roll system (PR #31): every rarity becomes its own power, and the menu is rebuilt as a hub with a Fuse screen.

## 1. Why
Adit, Nov 17, after playing the sector 3 build: "right now the powers feel like an addition to the action part of the game, but I wanted it to be the focus". Stealing and fusing powers is the game's hook (the GDD's one-line pitch), so the crafting gets most of the remaining production time.

The change in one paragraph: two new base powers (Bulwark and Magnet) make five. Any two different base powers fuse, so there are ten pairs. Each fusion rolls a rarity, rare, epic or legendary, and each rarity of a pair is its own power with its own verb and icon, 30 in all. The first fusion of a pair is free. Fusing the same pair again costs one spare charge of each ingredient and rerolls it.

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

Starting tuning, all in `Tuning` with guards: `bulwark_ticks 45`, `bulwark_radius 14.0` (the Surge's radius plus 9, written out because a dataclass default cannot refer to another field), `bulwark_cooldown 150` (180 as built, see DECISIONS Nov 19), `magnet_range 72`, `magnet_radius 44`, `magnet_ticks 30`, `magnet_pull 1.5` px per tick (each step under the thinnest obstacle, walls win), `magnet_cooldown 120`, `magnet_crush_damage 2`.

**Fusions inherit evolutions.** Every power of a pair inherits the evolutions its rare inherits, as Shock Cone's sparks chain and Arc Trail gets Overdrive today:
- Spark + Blink and Blink + Burst take Overdrive.
- Spark + Burst takes CHAIN (strikes chain) and WIDE (blasts and the aura reach 25 percent further).

Inheriting both ingredients everywhere was measured and broke the power step guard (Bolt Lance at 1.50 times Arc Trail, Displacer below Impact Blink). No rarity step may be something an evolution already gives. The power step guard (section 5) runs evolved wherever an inherited evolution changes damage.

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

## 5. The ten pairs and their thirty powers
Adit, Nov 17, after trying the first epic and legendary results: "every combination needs to be unique... each one so rare, epic and legendary should be unique, with unique icons and unique powers". Version 0.2's higher rarities were the rare plus an attachment (a longer trail, a ring of sparks), which read as the same power. So every result is now its own power with its own verb, icon and effect, like Hades' legendary boons or the separate cards of a collectible card game:
- **Rare:** the plain combination of the two powers' verbs.
- **Epic:** a different verb that uses both elements.
- **Legendary:** a signature move that can carry a run.

No result is another result plus an extra part, and no two results anywhere share a verb. A result keeps its pair's cooldown family (section 6), so a Blink and any teleporting result still share one cooldown and two slots can never teleport twice in one tick. Each result has its own cooldown.

| Pair | Family | Rare | Epic | Legendary |
| --- | --- | --- | --- | --- |
| Spark + Blink | teleport | **Arc Trail**: Blink, leaving a line that pulses damage (as now) | **Bolt Lance**: the Surge becomes a bolt and dashes along the aim, untouchable, striking every robot it passes once | **Chain Jump**: hop to the robot nearest the cursor and strike it, then hop on to the next robot up to three more times |
| Spark + Burst | pulse | **Shock Cone**: Burst plus a fan of 3 sparks (as now) | **Shock Mine**: lob a charge to the cursor. After a 0.5 s fuse it bursts in a full ring that hurts and knocks back | **Storm Aura**: for 3 s a field around the Surge strikes the nearest robot every 15 ticks |
| Blink + Burst | teleport | **Impact Blink**: Blink, then a full ring blast on landing | **Displacer**: swap places with the robot nearest the cursor, and both spots blast | **Meteor**: leap toward the cursor, untouchable in the air for 0.5 s with a landing marker, and crash down in a big blast |
| Spark + Bulwark | shield | **Static Guard**: a shield, and each absorbed shot fires a spark at the nearest robot | **Tesla Coil**: plant a coil for 3 s that strikes the nearest robot every 20 ticks and soaks shots that hit it | **Capacitor Armor**: for 4 s the next 3 hits of any kind are absorbed, then released as a ring of sparks |
| Spark + Magnet | shot | **Lodestone**: a slow heavy spark that drags robots near its path toward it | **Ion Hook**: a hook spark. The first robot it hits is yanked to the Surge and stunned for 0.5 s | **Magrail**: a rail shot that pierces every robot in a line and drags them along. Robots slammed into a wall take extra damage |
| Blink + Bulwark | teleport | **Phase Guard**: Blink, arriving shielded | **Afterimage**: Blink, leaving a decoy at the take-off point that robots shoot at for 2 s | **Rewind**: snap back to where the Surge stood 2 s ago, with the charge it had then |
| Blink + Magnet | teleport | **Undertow**: Blink, and the take-off point drags nearby robots into it for 1 s | **Grapple**: zip to the prop or robot at the cursor, knocking a robot back on arrival | **Riptide**: Blink, and every robot within 90 px of the take-off point is yanked there and stunned for 1 s |
| Burst + Bulwark | shield | **Bastion**: a shield that ends in a full ring blast | **Reflector Wave**: a wall of force rolls forward, shoving robots and turning hostile shots into the Surge's sparks | **Fortress**: plant a dome for 2 s. Hostile shots cannot enter it, and robots touching it are blasted back every 20 ticks |
| Burst + Magnet | pulse | **Vortex Cone**: a cone that pulls robots in, then pops | **Implosion**: a field at the cursor that drags robots together and ends in a blast | **Gravity Well**: a 2 s well at the cursor that pulls everything in and ends in a blast three times a Burst's damage |
| Bulwark + Magnet | pull | **Lightning Rod**: a field at the aim point that pulls hostile shots in and eats them for 1 s | **Shield Toss**: throw the shield like a boomerang. It eats shots and knocks robots out and back | **Mirror Field**: for 3 s hostile shots near the Surge are caught in orbit, then fired back at the nearest robots |

All names and numbers are provisional (GDD). New simulation parts this needs, all deterministic and trig-free:
- a dash state (Bolt Lance, Meteor)
- a position and charge history 2 s long (Rewind)
- a stun timer on robots (Ion Hook, Riptide)
- a decoy that robot targeting checks before the Surge (Afterimage). The Regulator targets it too, identically in both conditions
- placed objects with a lifetime (Shock Mine, Tesla Coil, Fortress, wells)
- a friendly shockwave ring (Meteor), mirrored from the Breaker's

**Power step guard.** With unique powers, rarities are compared on value per second of cooldown, so a slow, strong power and a quick, light one compare fairly:
- **Damage results:** damage per second of cooldown in the 40 fixed scenes (built in PR #31).
- **Shield and pull results:** shots stopped per second of cooldown in fixed volleys.

An epic must beat its rare and stay at or under 1.35 times it. A legendary must beat its epic and stay at or under 1.75 times the rare. Utility results with no common measure (Afterimage, Rewind, Grapple) are judged in Adit's playtest and by the protocol check below, and the PR that adds one says so.

**Every protocol stays answerable.** The GDD requires every legal loadout to have a viable answer to every tactic, and none to make one trivial. The bot's Regulator fight time per protocol with any one fused power equipped must stay at least 70 percent of its time without. The bot runs over 8 seeds must keep sectors 1 and 2 at their current retry rate and sector 3 near one retry a run.

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

## 7. The menu and the Fuse screen
Adit, Nov 17, on the interim menu: "its too convoluted... all i do is press f and dont really know which one is fusing", "make it so when i click tab, i see many options and one of those is fuse and then in fuse i can go and do the rolls". The loadout and fusion stop sharing one panel. The structure follows the pause menus of action games like Hades and Dead Cells: a short list of sections, each a full screen with one job.

**Tab opens the menu hub** anywhere the Surge is up, and pauses the game. Arriving in a Fuse Box opens it too.
- **RESUME**, or **CONTINUE** in a Fuse Box. CONTINUE is greyed with ROUTING POWER until the 5 s hold ends (the hold that hides the condition).
- **LOADOUT**
- **FUSE**, with a dot when a free fusion is waiting
- **CONTROLS**

W and S (or the arrows) move, Space or Enter picks, Esc goes back one level, Tab closes the menu from anywhere. A one-line footer on every screen says which keys do what there.

**LOADOUT** lists every power the Surge owns: the base powers, then the fused ones, seven rows at a time, scrolling.
- Each row shows the power's icon, its name and its rarity marks.
- The right panel shows the selected power: a larger icon, a two-line description, its cooldown and whether its ingredients are evolved.
- Q or E equips it to that slot. The two slots are drawn at the top, so the result is visible at once.

**FUSE** is the crafting bench.
1. **Pick two powers.**
   - The five base powers are shown as a row of icons, with locked ones as padlocks. Each shows its spare charges.
   - Space puts the highlighted power in the first empty socket, and Space on a socketed power takes it out.
   - The bench reads `SPARK + BLINK`.
2. **See the three results.** With two powers socketed, three cards show the pair's rare, epic and legendary results.
   - Each card shows its rarity frame and marks and its odds (60%, 30%, 10%).
   - A result found before shows its icon, name and one-line description. One never found shows a dark silhouette and ???. A collection to complete, as in a game's item log.
   - The result the Surge owns now is tagged OWNED.
3. **Read the terms.** One line under the cards gives what the roll costs and how it works:
   - The cost: FREE FIRST ROLL, or REROLL: 1 SPARK + 1 BLINK.
   - A guarantee meter: two pips that fill with each rare in a row, and EPIC OR BETTER GUARANTEED when full. The rare card greys out then.
   - With a result owned, the line warns ROLLING REPLACES STORM STEP.
   - H opens a short HOW ROLLS WORK page with the odds, the guarantee, the cost, and that the same seed rolls the same luck.
4. **Roll.** Space rolls. The result is decided in the simulation at that moment, from the run's roll stream (section 4). The animation only reveals it, so replays never depend on it.
   - **The spin:** a highlight frame steps across the three cards, fast at first, slowing over about 1.6 s with a tick each step, and stops on the result. The step count is worked out backwards from the result, so it always lands right.
   - **The reveal:** the chosen card lifts to the center and turns face up, with the rarity's sting. A legendary gets three rays and an outline pulse.
   - **Then:** NEW or REPLACED, and Q, E or Space to equip to a slot or keep it in the loadout.
   - Space skips the spin to the reveal, and that press does nothing else.

**Photosensitivity.** The spin moves a small outline across the cards. It never flashes the screen, and nothing flashes more than 3 times a second. Flash reduction (UI-08) is not built yet, so the reveal uses outline pulses by default and never a white flash.

**Rarity marks (shape first, then color).**

| Rarity | Marks | Card frame | Color token |
| --- | --- | --- | --- |
| rare | 1 cross | plain | `px.rarity.rare`, steel |
| epic | 2 crosses | notched corners | `px.rarity.epic`, mint |
| legendary | 3 crosses | four rays | `px.rarity.legendary`, champagne |

The rarity colors appear only in menus and the HUD slots, never in the world. The HUD slots show the same marks under the key glyph. The interim menu from PR #31 (one panel, F fuses the next recipe) is replaced entirely.

## 8. Art and audio
Each item is checked on the contact sheet and in play, as before.
- **Icons:** one per power, 35 in all: five base powers and 30 fused results. Each is drawn for its own verb (a lance, a hop chain, a mine, a meteor), never a recolored sibling. The rarity shows through the card or slot frame and the marks, not the icon. Each result also has a dark silhouette version for undiscovered cards.
- **Effects:** every result has its own effect, drawn from its verb. A fused power still looks like its ingredients combined (art direction rule 5) through its ingredients' colors.
- **Base powers:**
  - Bulwark: bubble, absorb flick, reflect streak.
  - Magnet: field ring with inward dashes.
  - Charges: two new charge orbs, a shield shape for Bulwark and a horseshoe for Magnet.
- **Power colors:** Bulwark's and Magnet's are chosen with their style frame in step 3. They must differ from the hostile colors, the three existing power colors, the chassis shells and the rarity tokens.
- **Robots:** the Sentry and the Sweeper get a glowing charge core.
- **Sound:** each cue has a visual twin, as the audio rules require.
  - Each fused result: its own use cue.
  - Bulwark: `bulwark_up`, `bulwark_absorb` and `bulwark_reflect`.
  - Magnet: `magnet_field`.
  - The roll: `roll_tick`, plus `fuse_rare`, `fuse_epic` and `fuse_legendary` stings.
  - Menu: move and back.
- **License:** new art and audio are original and CC BY 4.0, as the rest.

## 9. Build order
Each step is its own branch and PR with an independent read-only review. Adit merges. Every step that changes rules, world state or tuning changes the pinned replay hashes and `tuning_id`. Each such PR re-pins them on purpose, checks them on Python 3.11 and 3.12, and says why in its body.

The work is split so the playtest on Nov 25 plays a complete system on the three base powers that exist today. Bulwark and Magnet follow.

| Step | PR | Target | Hours |
| --- | --- | --- | --- |
| 1 | This spec, decision rows | Nov 17 | 1 |
| 2 | The roll system: bank, cost, odds, guarantee, roll stream, retries, trace, seed in the trace (PR #31). Its attached epics and legendaries are placeholders, replaced in step 3 | Nov 17–18 | 3 |
| 3 | The six unique epics and legendaries of Spark + Blink and Spark + Burst, plus Blink + Burst's three, with icons, effects and cues | Nov 18–20 | 6 |
| 4 | The menu hub, LOADOUT, FUSE with the spin and reveal, CONTROLS, HUD marks | Nov 19–21 | 5 |
| 5 | Bulwark and Magnet: drops, charge cores, evolutions, effects, sounds, slotting banner (built Nov 19) | Nov 21–22 | 4 |
| 6 | Evidence version 4 and `config_hash` covering it. Adit redeploys and runs the smoke test | Nov 22 | 1.5 |
| 7 | The Bulwark and Magnet pairs, 21 powers in two PRs | Nov 22–24 | 8 |
| 8 | Balance with the bot and the protocol check, numbers in the PR | Nov 26–27 | 2 |

About 30 hours in all. That is on top of the 40 hours of D3, which the floor, robots and bosses have already used, so the G3 proposal states the overrun. The small live suite (task 13, Nov 26–27) runs only after the version 4 redeploy. Recording is Nov 28 and the combined G2/G3 review is Nov 30.

**Cut order** if time runs short, first cut first. Each tier is now its own power, so cuts remove whole pairs, never single tiers:
1. Bulwark + Magnet
2. Burst + Bulwark
3. Blink + Magnet
4. The rest of step 7

When a pair is cut it cannot be fused (the bench says NOT IN THIS BUILD), and the roll stream is unchanged. Steps 2 to 6 are not cut. If the instructor does not approve the scope at G3, the fallback is the G1 production ceiling: Spark, Blink and Burst, Arc Trail and Shock Cone, and no rarities.

**Risks.** The new risks are 30 unique powers and 35 icons in 10 days, against a playtest on Nov 25. The phasing and the cut order above are the mitigation. They go into the Update Risk Register with the G3 package (task 13).

## 10. Evaluation
- The existing fairness question stays. Add one post-play question: "Did fusion results feel fair?" (1 to 5). It changes the playtest protocol, so it is recorded with the other G3 protocol changes. No identities in the answers, as before.
- Every fusion's roll is in the trace, and the session's seed is in its first row, so analysis can line up rarity sequences by seed and account for luck. Because the nth roll of a seed is the same in both conditions, luck is controlled by design when a participant plays both conditions on one seed.
- Evidence labels as before: fixture, replay and live results are reported separately.

## 11. Open points for Adit
- **The seed rule (decided Nov 19, as recommended).** The game uses seed 1 unless given another. Recommendation: each participant plays both conditions on one seed, and different participants get different seeds. One seed per participant controls luck between that player's two conditions, at the cost of meeting the same rarity sequence twice (a possible learning effect). If that effect shows, the analysis can compare first sessions only.
- Names and the exact rarity effects are provisional and can change in their PRs.
- If rerolls feel too cheap or too stingy in play, `reroll_cost` and the odds are tuning values, not code changes.
