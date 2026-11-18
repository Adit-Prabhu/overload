# Overload · Handoff
Snapshot of November 18, 2026. For any agent or chat picking up the work. The standing rules are in [AGENTS.md](../AGENTS.md) (Workflow). This file says where things stand, so check `gh pr list` and `git log` before trusting it, and update it when a milestone lands.

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
- **Boss rework implementation is complete on the stack below.** All three Regulators have distinct bodies in each of their three phases. The original rework's attack rotations, tells and vent windows carry through. The Grid Core's defeat gets its own on-screen sequence before the results, and all boss attack families have their own sound. The stronger Transformer hitbox affects body contact and attack origins, as documented.
- Review the [nine phase images](art/bosses.png), the [Grid Core victory](art/boss_down.png), and the [design and original developer research](BOSS_DESIGN.md). These are headless fixture renders. Adit owns sign-off, merge, and the human playtest. Production scope remains subject to G3.

## Open boss stack

| PR | What |
| --- | --- |
| [#36](https://github.com/Adit-Prabhu/overload/pull/36) | Walking robots and more detailed mob sprites |
| [#37](https://github.com/Adit-Prabhu/overload/pull/37) | First redraw of the Regulator walk cycles |
| [#38](https://github.com/Adit-Prabhu/overload/pull/38) | Dressed floor, contact shadows and sector ambience |
| [#39](https://github.com/Adit-Prabhu/overload/pull/39) | Boss design and scope proposal |
| [#40](https://github.com/Adit-Prabhu/overload/pull/40) | Three-phase combat kit, damage and reward rules, Transformer radius and replay pins |
| [#41](https://github.com/Adit-Prabhu/overload/pull/41) | Phase-specific chassis art, camera, victory, retry and replay presentation |
| [#42](https://github.com/Adit-Prabhu/overload/pull/42) | Ten new original cues, event bindings and the completion record on `feat/boss-sounds` |

Adit merges in this order.

```sh
gh pr merge 36 --merge && gh pr merge 37 --merge && gh pr merge 38 --merge
gh pr merge 39 --merge && gh pr merge 40 --merge && gh pr merge 41 --merge
gh pr merge 42 --merge
git switch main && git pull --ff-only
```

## Next steps (spec section 9)
1. Bulwark (from the Sentry) and Magnet (from the Sweeper) base powers: drops, charge cores, evolutions (REFLECT, CRUSH), effects, sounds, and the slotting banner. Then a bot protocol check that shields do not trivialize projectile protocols.
2. `config/evidence.json` version 4, which counts power uses by cooldown family (shot, teleport, pulse, shield, pull). Make `config_hash` cover it. Adit then redeploys the Worker and runs the smoke test (docs/DEPLOY.md).
3. The 21 powers of the Bulwark and Magnet pairs (spec section 5), each its own verb and icon, held to the power step guard. The cut order is whole pairs (section 9).
4. Balance the planned power roster against the new boss kits with the floor bot over 8 seeds and Adit's playtest notes, Nov 26 to 27 (spec section 9, step 8). The three-seed boss protocol guard includes the slower seed 3 bot run. Details in [BOSS_DESIGN.md](BOSS_DESIGN.md).

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
