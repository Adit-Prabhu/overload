# Overload · Handoff
Snapshot of November 21, 2026. For any agent or chat picking up the work. The standing rules are in [AGENTS.md](../AGENTS.md) (Workflow). Check `gh pr list` and `git log` before trusting this snapshot, and update it when a milestone lands.

## Where the project is
- G1 approved Nov 16. The combined G2/G3 review is Nov 30, the first-playable recording Nov 28, the live evaluation suite Nov 26 to 27, and the external playtest Nov 25 (Player 1) and Dec 2 to 4 (Player 2). Past-G1 scope is logged for the G3 scope-lock proposal.
- On `main` (`9bbc557`, PRs #64 through #69 merged):
  - deterministic simulation with Medium `tuning_id` `624e3a96` and `arena_id` `cff616dc` (freeze candidate)
  - three-sector hand-built substation floor (Switchyard, Cooling Plant, Grid Core) with locking combat rooms, Fuse Boxes, Sector 2's hidden Burst cache (`PR #64`), recessed Fuse Box charging bays, and Sector 2 and 3 arrival banners (`PR #66`)
  - five articulated maintenance robots (Arc Drone, Relay Bot, Breaker, Sweeper, Sentry) with sector color tiers, and three three-phase Regulator chassis (Linesman, Transformer, Grid Core) with attack kits, vent windows, crit and deflection VFX, protocol boot cards naming the active protocol (`CLAMP`, `INSULATE`, or `OSCILLATE PROTOCOL`), entrance and defeat sequences
  - five evolvable base powers and thirty distinct chance-fused powers across ten pairs and three rarities, plus the Tab pause/Fuse Box menu, Loadout with evolution pips and inherited evolution badges (`PR #65`), Fuse crafting bench, four difficulty presets, `SETTINGS` (`PR #67`), rebindable keys (`settings/keys.json`), first-run coach hints, 32 x 32 Surge app icon, and dev mode
  - all 90 audio cues (81 `sfx_` cues including all 30 fused power cues, 6 music stems and 3 protocol stings) approved by Adit in `assets/ASSET_MANIFEST.json`, plus regenerated art review renders in `docs/art/` (`PR #69`)
  - deployed and hardened Cloudflare Worker rival service (`bf48e333`, Vertex AI `gemini-3.5-flash-lite`) passing both Nov 23 checkpoint smoke tests on Evidence Version 4 ([LIVE_SMOKE_2026-11-19.md](evidence/LIVE_SMOKE_2026-11-19.md)), with `config/tactics.json` version 3 and 10-kind `eval/histories.json` version 2 merged in `PR #68` (awaiting Adit's redeploy)

## Final-readiness PRs (Nov 21, PRs #70 to #72)
Three independent PRs branched from `main` (`9bbc557`), each targeting a distinct subsystem with zero changes to `tuning_id` (`624e3a96`), `arena_id` (`cff616dc`), or simulation hash pins:
1. **PR #70 (impact hitstop, HUD, title, and ending music polish):** adds cosmetic impact hitstop, HUD readability polish, and title/ending music polish without touching simulation state.
2. **PR #71 (Worker OAuth cold-start warm-up):** warms the Google OAuth access token during session creation (`POST /sessions`) so the first between-encounter request does not race a cold token exchange against the 4.5 s Worker deadline.
3. **PR #72 (`feat/playtest-bi-and-release`):** adds the formal external playtest facilitator script ([docs/playtests/PROTOCOL.md](playtests/PROTOCOL.md)) and anonymized template ([docs/playtests/TEMPLATE.md](playtests/TEMPLATE.md)), the pure standard-library BI trace-comparison CLI (`tools/rival/compare_traces.py`) with paired `live` vs `fixed` analysis and explicit fallback confound flags (`tests/test_compare_traces.py`), the manual live-eval CI workflow (`.github/workflows/live-eval.yml`), the tagged `v*` release workflow (`.github/workflows/release.yml`), and the Gold release checklist ([docs/RELEASE_CHECKLIST.md](RELEASE_CHECKLIST.md)).

## Next steps for Adit
1. **Merge PRs #70, #71, and #72** after independent read-only QA reviews pass and CI is green.
2. **Single Worker redeploy (`docs/DEPLOY.md`)** from `main` after merging #71 so the live Cloudflare Worker serves `config/tactics.json` version 3, Evidence Version 4, and the OAuth cold-start warm-up in one deploy, followed by one smoke check (`tools/rival/smoke.py`).
3. **Nov 25 external playtest (Player 1):** follow [docs/playtests/PROTOCOL.md](playtests/PROTOCOL.md) on the frozen build (`tuning_id` `624e3a96`, Medium difficulty, same seed across `live` and `fixed`), analyze both JSONL traces with `tools/rival/compare_traces.py`, and record anonymized notes from [docs/playtests/TEMPLATE.md](playtests/TEMPLATE.md).
4. **Nov 26 to 27 live suite** (paid, Adit authorizes: `tools/rival/live_suite.py` or manual `.github/workflows/live-eval.yml`, 6 cases x 3 repeats = 18 calls on `eval/histories.json` v2) and **Nov 28 first-playable recording** on the same `tuning_id`.
5. **Nov 30 combined G2/G3 review:** write the `UPDATE_*` documents and G3 scope-lock proposal citing the frozen build, Player 1 playtest notes, live suite report, and cut orders.
6. **Dec 2 to 4 external release playtest (Player 2) and Dec 4 Beta lock:** run the second distinct participant on a fresh seed with counterbalanced order, verify fixes, and complete the clean-clone checks in [docs/RELEASE_CHECKLIST.md](RELEASE_CHECKLIST.md).
7. **Dec 5 to 7 Gold release (G4):** finalize `FINAL_*` docs, push the signed/annotated `v*` Gold tag (triggering `.github/workflows/release.yml`), record and link the Gold video, and preserve the G4 tag on Dec 7.

## How the fusion system fits together
- **Rules (`sim/powers.py`):** `RESULTS` maps each of the 10 pairs to rare, epic and legendary ability IDs. `fuse()` rolls from `(seed, fusions, guaranteed)` and replaces the pair's result. The bank holds spare charges, and cooldown families share cooldowns.
- **Powers (`sim/fusions.py`, `sim/pairs.py`):** one deterministic verb per power, inheriting evolutions from `INHERITS`. The Regulator is never displaced.
- **Menu (`game/menu.py`, `game/settings.py`, `game/keybinds.py`):** pure Python logic (`keybinds.py` lazily imports pygame only for key-code lookup), unit tested separately from `menu_view.py`.
- **Dev mode (`game/dev.py`):** gated by git-ignored `.overload-dev`, edits world state between ticks, disables rival calls and traces, refuses replays/practice, and stamps `DEV` on every frame.
- **Guards:** `tests/test_fusion.py` enforces rarity steps, `tests/test_balance.py` enforces protocol checks, `tests/test_palette.py` enforces palette tokens, and `tests/test_audio.py` enforces visual twins and cue completeness.
