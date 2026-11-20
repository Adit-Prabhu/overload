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
  - the rival service: Cloudflare Worker, deployed, with both smoke tests passing on evidence version 4 (docs/evidence/LIVE_SMOKE_2026-11-19.md, which replaces LIVE_SMOKE_2026-11-17.md)
  - evidence version 4 (power uses by family), live on the Worker since Adit's Nov 19 redeploy, and the MIT and CC BY 4.0 licenses
  - the chance-fusion spec, nine distinct fusion outcomes, the pause and Fuse menus, and dev mode from PRs #30 to #35
  - the polish pass and the boss rework from PRs #36 to #43:
    - robots walk on moving legs
    - the floor is dressed per sector, with live ambience
    - three Regulator chassis with three phases each, their own attack rotations, vent windows, an entrance, a death sequence and their own sounds
- Review images: the [nine phase images](art/bosses.png), the [Grid Core victory](art/boss_down.png), the [robot walk cycles](art/robot_walk_cycles.png) and the [roster](art/robot_style_frame.png). The design and its research are in [BOSS_DESIGN.md](BOSS_DESIGN.md). These are headless renders, not playtest evidence.
- Practice mode (the single arena) still has the legacy Regulator with no kit. Check boss work in the campaign or with `tools/art/boss_review.py`.

## Powers and evidence integration

- Bulwark and Magnet landed in #45.
- Evidence version 4 is live: Adit redeployed the Worker on Nov 19 and the smoke test passed ([LIVE_SMOKE_2026-11-19.md](evidence/LIVE_SMOKE_2026-11-19.md)). A cold first request and one transient 500 were seen, both falling back safely. Hardening is proposed there.
- #47 has the first twelve new fusion results. The final nine are on its stacked `feat/fusion-pairs-b` branch. Together they give all ten pairs and thirty results.
- The dedicated cue pass is done (Nov 19): every fused power has its own use cue, built from its pair's voices, its verb and its rarity in `tools/audio/cues.py` (`FUSED_RECIPES`).

## Pilot playtest fixes (Nov 19)
Adit's informal pilot with a friend ([notes](evidence/PILOT_PLAYTEST_2026-11-19.md), pilot only, not study data) led to four PRs. Merge order: #52, then #54, then #55 (stacked). #53 is independent.
- #52: a chassis phase change keeps its shots and lets an attack already striking finish. Re-pinned the campaign and full loop hashes.
- #53: the camera keeps the Surge on screen in boss fights.
- #54: rebindable keys (`game/keybinds.py`, saved to the git-ignored `settings/keys.json`).
- #55: first-run hints (`game/coach.py`), the Fuse Box arrow and an obvious CONTINUE, charges flying into the Surge, the boss reward shown, and the empty LOADOUT overlap.

## Next step (spec section 9)

The balance pass is done (`tools/balance.py`, numbers in DECISIONS, Nov 19). Medium's `tuning_id` is 624e3a96, the freeze candidate. Once Adit merges it, that is the build for the playtest, the live suite and the recording. Any later Tuning change makes a new build, labelled by its `tuning_id`.

## Decided Nov 19
- The playtest seed rule: one seed per participant for both conditions, different seeds across participants.
- The roll spin is quicker (1.1 to 1.5 s). Its fast first steps are accepted.
- The boss reward stays spare charges, and the boss cut order for the G3 proposal is phase 3 first.

## After the fusion work
Development ends with the steps above. Then, one timeline (DECISIONS, Nov 19):
1. The playtest on Nov 25 (Adit), on the frozen build.
2. The live suite on Nov 26 to 27 (paid, Adit authorizes) and the recording on Nov 28, on the same `tuning_id`. A Tuning change from the playtest notes makes a new build, and each build's evidence is labelled with its `tuning_id`.
3. The UPDATE documents and the G3 scope-lock proposal for Nov 30, stating the overrun (floor, bosses, fusion) and the cut orders.

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
  - The Bulwark + Magnet volley guard and the Blink utility cases are in `tests/test_blink_and_guard_fusions.py`. Tuning guards are in `sim/tuning.py`.
