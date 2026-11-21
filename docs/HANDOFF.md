# Overload · Handoff
Snapshot of November 21, 2026. For any agent or chat picking up the work. The standing rules are in [AGENTS.md](../AGENTS.md) (Workflow). Check `gh pr list` and `git log` before trusting this snapshot, and update it when a milestone lands.

## Where the project is
- G1 approved Nov 16. The combined G2/G3 review is Nov 30, the recording Nov 28, the live evaluation suite Nov 26 to 27, and the external playtest Nov 25. Past-G1 scope is logged for the G3 scope-lock proposal.
- On `main` (`b561af8`):
  - deterministic simulation with Medium `tuning_id` `624e3a96` and `arena_id` `cff616dc` (freeze candidate)
  - three-sector hand-built substation floor (Switchyard, Cooling Plant, Grid Core) with locking combat rooms, Fuse Boxes and Sector 2's hidden room
  - five articulated maintenance robots (Arc Drone, Relay Bot, Breaker, Sweeper, Sentry) with sector color tiers, and three three-phase Regulator chassis (Linesman, Transformer, Grid Core) with attack kits, vent windows, entrance and defeat sequences
  - five evolvable base powers and thirty distinct chance-fused powers across ten pairs and three rarities, plus the Tab pause/Fuse Box menu, Loadout, Fuse crafting bench, four difficulty presets, rebindable keys (`settings/keys.json`), first-run coach hints and dev mode
  - all 90 audio cues (81 `sfx_` cues including all 30 fused power cues, 6 music stems and 3 protocol stings) approved by Adit in `assets/ASSET_MANIFEST.json`
  - deployed and hardened Cloudflare Worker rival service (`bf48e333`, Vertex AI `gemini-3.5-flash-lite`) passing both Nov 23 checkpoint smoke tests on Evidence Version 4 ([LIVE_SMOKE_2026-11-19.md](evidence/LIVE_SMOKE_2026-11-19.md))

## Polish stack (Nov 21, PRs #64 to #69)
Six stacked PRs, each independently reviewed by a fresh read-only QA reviewer and verified on Python 3.12 and 3.11 without changing `tuning_id` (`624e3a96`), `arena_id` (`cff616dc`), simulation hash pins or approved `.ogg` audio files:
1. **PR #64 (`feat/secret-room-cache`):** shooting open Sector 2's secret wall spawns a Burst charge in `hidden`, room-clear auto-pickup stays scoped to the cleared combat room so the player walks in to claim the cache, and contact pickups never spawn duplicate flyers.
2. **PR #65 (`polish/ui-clarity`):** ending screen wraps up to 22 powers across two rows (with rarity marks and a `+N` cap beyond 22) and lets interactive runs press Space/Enter to return cleanly to the title screen on the same window and Audio instance. LOADOUT shows square evolution pips, `EVOLVED_INFO`, and inline inherited evolution badges (`USES` / `ACTIVE`). Fuse bench clears `+N` spares above card frames and shows the rolled power's description inside the reveal card. In-play HUD slots show rarity borders, rarity crosses and a 6-tick ready flash. Entry and Fuse Box floor stencils shift clear of the top-left battery HUD.
3. **PR #66 (`polish/combat-juice-and-world`):** revises D5 for OQ5 by showing the active protocol icon and label (`CLAMP`, `INSULATE`, or `OSCILLATE PROTOCOL`) on the 1.5 s Regulator boot card identically in all conditions. Adds Vent-window gold crit rings, bursts and layered spark audio, shield deflection rings, a 2 px jolt on player hits and a thin danger-red edge vignette on player hits and single-cell low battery, a cosmetic recessed charging bay in `fuse_1` and `fuse_2`, and non-blocking 1.5 s arrival banners for Sector 2 and Sector 3.
4. **PR #67 (`feat/settings-and-stingers`):** adds `SETTINGS` (`UI-08`, `game/settings.py`, saved in git-ignored `settings/prefs.json`, ignored by replays and headless runs) on Title and Pause/Fuse Box hubs for Music Volume, SFX Volume, Screen Shake, Reduce Flash (steady outline cues across every flash and flicker source) and Fullscreen, plus the 32 x 32 Surge app icon (`MK-02`).
5. **PR #68 (`feat/rival-v4-guidance`):** updates `config/tactics.json` (version 3) with power-family counter guidance for Evidence Version 4 and upgrades `eval/histories.json` (version 2) to six 10-kind Evidence Version 4 histories, verified with Worker typecheck and 38 Worker tests.
6. **PR #69 (`docs/polish-and-renders`):** updates `README.md`, `agent-config.json`, `docs/ART_AND_AUDIO_DIRECTION.md`, `docs/HANDOFF.md`, `tools/art/contact_sheet.py`, `tools/art/ui_renders.py`, and regenerates the review renders in `docs/art/`.

## Next steps for Adit
1. **Merge PRs #64 to #69 in order** (merge #64 into `main`, then retarget each stacked PR to `main` and merge).
2. **One Worker redeploy (`docs/DEPLOY.md`)** from `main` after merging #68 so the live Cloudflare Worker serves `config/tactics.json` version 3 alongside Evidence Version 4, followed by one quick smoke check (`tools/rival/smoke.py`).
3. **Nov 25 external playtest** on the frozen build (`tuning_id` `624e3a96`, Medium difficulty): each participant plays both `live` and `fixed` conditions on one seed, with different seeds across participants.
4. **Nov 26 to 27 live suite** (paid, Adit authorizes: `tools/rival/live_suite.py`, 6 cases x 3 repeats = 18 calls on `eval/histories.json` v2) and **Nov 28 recording** on the same `tuning_id`.
5. **Nov 30 combined G2/G3 review:** write the `UPDATE_*` documents and G3 scope-lock proposal citing the frozen build, playtest notes, live suite report and cut orders.

## How the fusion system fits together
- **Rules (`sim/powers.py`):** `RESULTS` maps each of the 10 pairs to rare, epic and legendary ability IDs. `fuse()` rolls from `(seed, fusions, guaranteed)` and replaces the pair's result. The bank holds spare charges, and cooldown families share cooldowns.
- **Powers (`sim/fusions.py`, `sim/pairs.py`):** one deterministic verb per power, inheriting evolutions from `INHERITS`. The Regulator is never displaced.
- **Menu (`game/menu.py`, `game/settings.py`, `game/keybinds.py`):** pure Python logic (`keybinds.py` lazily imports pygame only for key-code lookup), unit tested separately from `menu_view.py`.
- **Dev mode (`game/dev.py`):** gated by git-ignored `.overload-dev`, edits world state between ticks, disables rival calls and traces, refuses replays/practice, and stamps `DEV` on every frame.
- **Guards:** `tests/test_fusion.py` enforces rarity steps, `tests/test_balance.py` enforces protocol checks, `tests/test_palette.py` enforces palette tokens, and `tests/test_audio.py` enforces visual twins and cue completeness.
