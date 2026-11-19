# Overload · Handoff
Snapshot of November 19, 2026. For any agent or chat picking up the work. The standing rules are in [AGENTS.md](../AGENTS.md) (Workflow). This file says where things stand, so check `gh pr list` and `git log` before trusting it, and update it when a milestone lands.

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
  - the chance-fusion spec, nine distinct fusion outcomes, the pause and Fuse menus, and dev mode from PRs #30 to #35
  - the polish pass and the boss rework from PRs #36 to #43:
    - robots walk on moving legs
    - the floor is dressed per sector, with live ambience
    - three Regulator chassis with three phases each, their own attack rotations, vent windows, an entrance, a death sequence and their own sounds
- Review images: the [nine phase images](art/bosses.png), the [Grid Core victory](art/boss_down.png), the [robot walk cycles](art/robot_walk_cycles.png) and the [roster](art/robot_style_frame.png). The design and its research are in [BOSS_DESIGN.md](BOSS_DESIGN.md). These are headless renders, not playtest evidence.
- Practice mode (the single arena) still has the legacy Regulator with no kit. Check boss work in the campaign or with `tools/art/boss_review.py`.

## Next steps (spec section 9)
1. Bulwark (from the Sentry) and Magnet (from the Sweeper) base powers: drops, charge cores, evolutions (REFLECT, CRUSH), effects, sounds, and the slotting banner. Then a bot protocol check that shields do not trivialize projectile protocols.
2. `config/evidence.json` version 4, which counts power uses by cooldown family (shot, teleport, pulse, shield, pull). Make `config_hash` cover it. Adit then redeploys the Worker and runs the smoke test (docs/DEPLOY.md).
3. The 21 powers of the Bulwark and Magnet pairs (spec section 5), each its own verb and icon, held to the power step guard. The cut order is whole pairs (section 9).
4. Balance the planned power roster against the new boss kits with the floor bot over 8 seeds and Adit's playtest notes, Nov 26 to 27 (spec section 9, step 8). The three-seed boss protocol guard includes the slower seed 3 bot run. Details in [BOSS_DESIGN.md](BOSS_DESIGN.md).

## Decided Nov 19
- The playtest seed rule: one seed per participant for both conditions, different seeds across participants.
- The roll spin is quicker (1.1 to 1.5 s). Its fast first steps are accepted.
- The boss reward stays spare charges, and the boss cut order for the G3 proposal is phase 3 first.

## After the fusion work
Development ends with spec section 9, steps 5 to 7. Then:
1. Balance against the new bosses with the floor bot, including the fused-power protocol check.
2. Freeze the Tuning by Nov 23, so the playtest, the live suite and the recording share one `tuning_id`.
3. The playtest on Nov 25 (Adit), the live suite on Nov 26 to 27 (paid, Adit authorizes), the recording on Nov 28.
4. The UPDATE documents and the G3 scope-lock proposal for Nov 30, stating the overrun (floor, bosses, fusion) and the cut orders.

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
