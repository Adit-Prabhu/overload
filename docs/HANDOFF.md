# Overload · Handoff
Snapshot of November 17, 2026. For any agent or chat picking up the work. The standing rules are in [AGENTS.md](../AGENTS.md) (Workflow). This file says where things stand, so check `gh pr list` and `git log` before trusting it, and update it when a milestone lands.

## Where the project is
- G1 approved Nov 16. The combined G2/G3 review is Nov 30, the recording Nov 28, the external playtest Nov 25. Past-G1 scope is logged for the G3 scope-lock proposal.
- On `main`:
  - the deterministic sim
  - the floor of three sectors with locking combat rooms, Fuse Boxes and a hidden room
  - five robot types, and the three Regulator chassis (Linesman, Transformer, Grid Core)
  - sector identity and difficulty, with sector 3 hard on purpose
  - the HUD, the title screen, audio and pixel art
  - the rival service: Cloudflare Worker, deployed, with both smoke tests passing (docs/evidence/LIVE_SMOKE_2026-11-17.md)
  - evidence version 3, and the MIT and CC BY 4.0 licenses
- The current focus is making powers and fusion the heart of the game. The spec is [POWERS_AND_FUSION.md](POWERS_AND_FUSION.md) (version 0.3), and its section 9 has the build order.

## Open PRs (stacked, reviewed, waiting for Adit to merge in this order)
| PR | What | Key files |
| --- | --- | --- |
| #30 | Spec 0.3 and decision rows, including every as-built deviation | docs/POWERS_AND_FUSION.md, docs/DECISIONS_AND_OPEN_QUESTIONS.md |
| #31 | Roll system: spare-charge bank, reroll cost, odds 60/30/10, guarantee after two rares, roll stream seeded by run seed and fusion count | src/overload/sim/powers.py |
| #32 | Nine unique fused powers. Spark + Blink: Arc Trail, Bolt Lance, Chain Jump. Spark + Burst: Shock Cone, Shock Mine, Storm Aura. Blink + Burst: Impact Blink, Displacer, Meteor | src/overload/sim/fusions.py, tests/test_fusion.py |
| #33 | Tab menu hub (Resume or Continue, Loadout, Fuse, Controls, Quit) and the Fuse screen: sockets, outcome cards, odds, luck meter, roll spin and reveal | src/overload/game/menu.py, menu_view.py, app.py, tests/test_menu.py |
| #34 | Dev mode: `--dev` plus a git-ignored `.overload-dev` file. God mode, unlimited charges, forced roll rarity, grant power, room and sector skips | src/overload/game/dev.py, tests/test_dev.py |

This PR (handoff docs and `tools/pin_hashes.py`) is independent of the stack. Merge commands:
```sh
gh pr merge 30 --merge && gh pr merge 31 --merge && gh pr merge 32 --merge
gh pr merge 33 --merge && gh pr merge 34 --merge
git switch main && git pull --ff-only
```

## Next steps (spec section 9)
1. Bulwark (from the Sentry) and Magnet (from the Sweeper) base powers: drops, charge cores, evolutions (REFLECT, CRUSH), effects, sounds, and the slotting banner. Then a bot protocol check that shields do not trivialize projectile protocols.
2. `config/evidence.json` version 4, which counts power uses by cooldown family (shot, teleport, pulse, shield, pull). Make `config_hash` cover it. Adit then redeploys the Worker and runs the smoke test (docs/DEPLOY.md).
3. The 21 powers of the Bulwark and Magnet pairs (spec section 5), each its own verb and icon, held to the power step guard. The cut order is whole pairs (section 9).
4. Balance with the floor bot over 8 seeds, before the Nov 25 playtest.

## Open decisions for Adit
- The playtest seed rule (spec section 11). Recommendation: one seed per participant for both conditions, and different seeds across participants.
- The roll spin's first steps move the highlight faster than 3 times a second. It is a small moving outline, not a flash, and is recorded in DECISIONS for his OK.

## How the fusion system fits together
- **Rules** (`sim/powers.py`):
  - `RESULTS` maps each pair to its rare, epic and legendary ability ids.
  - `fuse()` rolls with `roll_rarity(seed, n, guaranteed)` and replaces the pair's result in the list and in its slot.
  - The bank holds spare charges.
  - Every teleport shares one cooldown, every pulse another.
- **Powers** (`sim/fusions.py`): one function per verb, plus `tick()` for lances, leaps, the aura and mines.
  - Each power inherits the evolutions its pair's rare inherits (`INHERITS`).
  - The Regulator is never moved.
- **Menu** (`game/menu.py`):
  - The logic has no pygame and is unit tested.
  - `roll_terms()` computes what the bench shows.
  - The spin is presentation only: the sim decides the result first and the replay records `["fuse", a, b]`.
- **Dev mode** (`game/dev.py`): it edits the world between ticks and never touches the sim. A dev run makes no rival call and writes no trace or recording, and DEV is always on screen.
- **Guards**:
  - `tests/test_fusion.py` holds the power step guard: epic at most 1.35 times its rare, legendary at most 1.75, measured as damage per second of cooldown.
  - The Tuning guards are in `sim/tuning.py`.
