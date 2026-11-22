# Overload

Overload is a top-down shooter where you steal and fuse enemy powers to feel inventive and capable of surprising a rival that learns how you fight. COMS E6998 section 014 (AI in Practice: Game Design and Development), Columbia University, individual final project.

The build holds a full three-sector substation campaign in original pixel art (256 x 144 scaled cleanly to the window): five maintenance robots (Arc Drone, Relay Bot, Breaker, Sweeper, Sentry), three three-phase Regulator chassis (Linesman, Transformer, Grid Core) with protocol boot cards, vent windows and defeat sequences, five evolvable base powers and thirty chance-fused powers across ten pairs and three rarities, four difficulty presets, rebindable controls, audio and accessibility settings, an original approved darksynth soundtrack and 81 approved sound effects, and a deployed Cloudflare Worker rival service backed by Vertex AI.

## Run and test
Requirements: [uv](https://docs.astral.sh/uv/) and Python 3.11 or 3.12 for the game, Node.js 22 for the rival service.

```sh
uv sync --frozen
uv run overload                                  # play the campaign (live rival if OVERLOAD_RIVAL_URL is set, else neutral)
uv run overload --condition fixed --schedule B   # the fixed-schedule baseline, order B
uv run overload --difficulty hard                # select a starting difficulty
uv run overload --practice                       # legacy single-arena practice mode
uv run overload --mute                           # no sound (every sound has a visual twin)
uv run overload --skip-title                     # straight into play, no title screen
uv run overload --record logs/run.json           # play and save a replay on exit
uv run overload --replay logs/run.json           # watch it back and verify the final state hash
uv run pytest                                    # deterministic client tests
uv run --group tools python -m tools.audio.render    # re-render assets/audio/ from tools/audio/ (Python 3.12)
uv run --group tools python -m tools.audio.preview   # one listen-through file in logs/
uv run ruff check . && uv run ruff format --check .

cd worker
npm ci
npm test                                         # Worker tests run locally in workerd, no deployment
npm run typecheck
npx wrangler dev --port 8787                     # run the rival service locally (fixture provider)
cd ..
uv run python tools/rival/smoke.py http://127.0.0.1:8787   # drive it from the game's client
uv run python tools/rival/compare_traces.py logs/p1-live.jsonl logs/p1-fixed.jsonl  # compare playtest traces
```

The rival service (`worker/`) gives each player session its own Cloudflare Agent, accepts only a strict Evidence Version 4 observation summary (distance shares, shots, dodges and five power-family counts, never power names or rarities), allows two requests per session and validates every proposal. The game validates again and falls back to the neutral protocol (`Oscillate`) on anything invalid, late or missing (`src/overload/agent/`). Locally the service uses a deterministic fixture rule labeled `fixture`. The deployed service calls Gemini on Vertex AI (decision D6), see [docs/DEPLOY.md](docs/DEPLOY.md) and the Nov 19 live smoke evidence in [docs/evidence/LIVE_SMOKE_2026-11-19.md](docs/evidence/LIVE_SMOKE_2026-11-19.md).

Controls: WASD or arrow keys move, the mouse aims, hold left click to fire, Space dodges, Q and E use the powers in your two slots, R retries after going down. Every key except Esc can be rebound in CONTROLS (on the title screen or in the menu), saved to `settings/keys.json` (git-ignored). SETTINGS (also on the title screen and in the menu) adjusts Music Volume, SFX Volume, Screen Shake, Reduce Flash and Fullscreen, saved to `settings/prefs.json` (git-ignored, ignored by replays and headless runs). Tab or Esc opens and closes the menu freely (mid-sector it pauses play, and in a Fuse Box it stays optional while the charging bay runs): RESUME, LOADOUT (with evolution pips, evolved descriptions and inherited perks), FUSE, SETTINGS, CONTROLS and QUIT. Arriving in a Fuse Box plays a 5 s in-world recharge from the yellow-and-blue charging bay while refilling your battery and running the rival's single adaptation request, then automatically unlocks the exit once ready. In FUSE, pick two stolen base powers and roll: each pair can become a rare, an epic or a legendary power (60, 30 and 10 percent, epic or better after two rares in a row). A pair's first roll is free, and a reroll costs a spare charge of each power.

The campaign is a hand-built substation floor of three sectors (Switchyard, Cooling Plant, Grid Core). Combat rooms lock when you step in and open when every robot is down. Destroy Arc Drones for Spark, Relay Bots for Blink, Breakers for Burst, Sentries for Bulwark and Sweepers for Magnet. Somewhere in Sector 2 a cracked wall hides a bonus cache. Each sector ends in the Regulator's chamber, and the Fuse Box between sectors recharges you and runs the rival's single adaptation request. Dying restarts the current sector with its entry loadout and protocol. Encounter 1 always starts neutral. Pressing Space or Enter on the ending readout returns cleanly to the title screen. Each windowed session writes a trace to `logs/` (git-ignored) with no player identity. Headless runs write one only with `--trace PATH`.

On the title screen, use A/D or Left/Right to choose Easy, Medium, Hard, or Nightmare before Start. Medium (`tuning_id` `624e3a96`) is the formal playtest balance. Other presets adjust battery capacity, enemy health, and bolt speed. The choice stays fixed for the run and its retries. Recordings replay at their recorded difficulty.

Review renders of the art live in [`docs/art/`](docs/art/): the contact sheet with color-vision simulations, boss phases, robot roster and UI screens. Regenerate them with `uv run --group tools python tools/art/contact_sheet.py` (Python 3.12), `uv run python tools/art/robot_style_frame.py`, `uv run python tools/art/boss_review.py` and `uv run python tools/art/ui_renders.py`.

CI runs deterministic checks on every pull request ([`.github/workflows/overload-checks.yml`](.github/workflows/overload-checks.yml)). Manual live evaluation ([`.github/workflows/live-eval.yml`](.github/workflows/live-eval.yml)) and tagged `v*` release packaging ([`.github/workflows/release.yml`](.github/workflows/release.yml)) run only when explicitly triggered by Adit. Development agent roles live in [`.agents/`](.agents/) and the common manifest is [`agent-config.json`](agent-config.json).

## G1 submission
- Recording (3-5 min): https://youtu.be/uBufxDVXPek
- Deck presented: [Google Slides](https://docs.google.com/presentation/d/1_75mht-kKFm1omTLg8itxf0CBhAFPch-feteD2jY0VI/edit?usp=sharing) · copy in repo: [docs/g1/Overload_G1.pptx](docs/g1/Overload_G1.pptx)
- [Initial GDD](docs/INITIAL_GDD.md)
- [Initial Configuration Document](docs/INITIAL_CONFIGURATION.md) (open questions, planned agent role coverage, extension manifest)
- [Initial Project Plan](docs/INITIAL_PROJECT_PLAN.md)
- [Initial Risk Register](docs/INITIAL_RISK_REGISTER.md)
- [References and attribution](docs/REFERENCES.md)
- [Decisions and open questions](docs/DECISIONS_AND_OPEN_QUESTIONS.md)
- [Historical first-round pitch](docs/history/FIRST_ROUND_PITCH.md)

## Planning after G1
- [Implementation plan](docs/IMPLEMENTATION_PLAN.md): architecture, schedule through the finals, tests and decisions
- [Powers and fusion](docs/POWERS_AND_FUSION.md): base powers, evolutions, chance fusion and 30 fused outcomes
- [Boss design](docs/BOSS_DESIGN.md): three-phase chassis kits, vent windows and protocol balance
- [Art and audio direction](docs/ART_AND_AUDIO_DIRECTION.md): theme, visual and sound rules, full asset list
- [External playtest protocol](docs/playtests/PROTOCOL.md) and [log template](docs/playtests/TEMPLATE.md): blind `live` vs `fixed` facilitator script, OQ5 questions, and trace comparison workflow (`tools/rival/compare_traces.py`)
- [Gold release checklist](docs/RELEASE_CHECKLIST.md): Dec 4 Beta lock, fresh-clone checks, live evidence, and Dec 5 to 7 Gold tag steps
- [Handoff](docs/HANDOFF.md): current milestone snapshot and next steps

Files named "Initial" are the G1 gate proposal. They are preserved as submitted. Update (G2/G3) and Final (G4) versions are added alongside them rather than overwriting them.

## Status
- G1 decision: Approved (Nov 16, 2026). See [decisions](docs/DECISIONS_AND_OPEN_QUESTIONS.md).
- Nov 23 checkpoint: Met early on Nov 19 with the deployed and hardened Cloudflare Worker (`bf48e333`), live Vertex AI replies, two-session isolation and forced-timeout fallback ([LIVE_SMOKE_2026-11-19.md](docs/evidence/LIVE_SMOKE_2026-11-19.md)).
- Freeze candidate: Medium `tuning_id` `624e3a96`, `arena_id` `cff616dc`, all 90 audio cues approved.
- Upcoming: Worker redeploy for `config/tactics.json` v3 and OAuth cold-start warm-up (`POST /sessions/:id/warmup`), Nov 25 external playtest, Nov 26 to 27 live suite, Nov 28 recording, Nov 30 combined G2/G3 review.
- Videos are never committed. Recordings are linked above.

## License
- **Code:** MIT, see [`LICENSE`](LICENSE).
- **Original art and audio:** CC BY 4.0, see [`LICENSE-ASSETS.md`](LICENSE-ASSETS.md). Credit line: "Overload by Adit Prabhu, CC BY 4.0".
- **The Silkscreen font:** keeps its SIL Open Font License 1.1, in `assets/fonts/silkscreen/OFL.txt`.
- **Dependencies:** keep their own licenses. pygame-ce is LGPL 2.1.

## Revision
The in-game rival uses two bounded model requests between encounters on Evidence Version 4 and Tactics Version 3, validated by game code, with deterministic fallback. The full three-sector campaign, 35 powers, three-phase Regulator chassis, Settings and approved audio are implemented and verified.
