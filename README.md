# Overload

Overload is a top-down shooter where you steal and fuse enemy powers to feel inventive and capable of surprising a rival that learns how you fight. COMS E6998 section 014 (AI in Practice: Game Design and Development), Columbia University, individual final project.

G1 was approved. The repository holds a playable practice build in original pixel art: a lineworker (the Surge) in a blacked-out substation hall, with movement, aiming, shooting, dodging, retry and replay against two Arc Mites. It also holds a placeholder rival service with a health route, CI and the agent team configuration. There are no powers, Regulator fight, deployed service, paid model call or playtest yet.

## Run and test
Requirements: [uv](https://docs.astral.sh/uv/) and Python 3.11 or 3.12 for the game, Node.js 22 for the rival service.

```sh
uv sync --frozen
uv run overload                          # play the campaign (live rival if OVERLOAD_RIVAL_URL is set, else neutral)
uv run overload --condition fixed --schedule B   # the fixed-schedule baseline, order B
uv run overload --practice               # practice arena: two Arc Mites, no Regulator
uv run overload --mute                   # no sound (every sound has a visual twin)
uv run overload --record logs/run.json   # play and save a replay on exit
uv run overload --replay logs/run.json   # watch it back and verify the final state hash
uv run pytest                            # deterministic client tests
uv run --group tools python -m tools.audio.render    # re-render assets/audio/ from tools/audio/ (Python 3.12)
uv run --group tools python -m tools.audio.preview   # one listen-through file in logs/
uv run ruff check . && uv run ruff format --check .

cd worker
npm ci
npm test                                 # Worker tests run locally in workerd, no deployment
npm run typecheck
npx wrangler dev --port 8787             # run the rival service locally (fixture provider)
cd ..
uv run python tools/rival/smoke.py http://127.0.0.1:8787   # drive it from the game's client
```

The rival service (`worker/`) gives each player session its own Cloudflare Agent, accepts only a strict observation summary, allows two requests per session and validates every proposal. The game validates again and falls back to the neutral protocol on anything invalid, late or missing (`src/overload/agent/`). Locally the service uses a deterministic fixture rule that labels every answer as `fixture`. The deployed service calls Vertex AI (decision D6), see `docs/DEPLOY.md`.

Controls: WASD or arrow keys move, the mouse aims, hold left click to fire, Space dodges, Q and E use the powers in your two slots, Tab opens the loadout menu (the game pauses), R retries after going down, Esc quits. In the loadout menu and the Fuse Box, W and S pick a stolen power, Q or E equips it to that slot and F fuses the next recipe (Spark + Blink makes Arc Trail, Spark + Burst makes Shock Cone). In the Fuse Box, Enter continues. The campaign is a hand-built substation floor of three sectors. Combat rooms lock when you step in and open when every robot is down. Each sector ends in the Regulator's chamber, and the Fuse Box between sectors recharges you and is where the Regulator adapts. Dying restarts the current sector. Encounter 1 always runs the neutral protocol. Destroy Arc Mites to steal Spark and Relays to steal Blink. Somewhere in sector 2 a wall cracks if you shoot it. Each windowed session writes a trace to `logs/` (git-ignored) with no player identity. Headless runs write one only with `--trace PATH`. The window scales the 256 x 144 view by whole numbers.

Review renders of the art live in [`docs/art/`](docs/art/): the style frame, the whole room, and the contact sheet with color-vision simulations. Regenerate them with `uv run python tools/art/pixel_style_frame.py` and `uv run --group tools python tools/art/contact_sheet.py` (Python 3.12).

CI runs the same checks on every pull request ([`.github/workflows/overload-checks.yml`](.github/workflows/overload-checks.yml)). Development agent roles live in [`.agents/`](.agents/) and the common manifest is [`agent-config.json`](agent-config.json).

## G1 submission
- Recording (3–5 min): https://youtu.be/uBufxDVXPek
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
- [Art and audio direction](docs/ART_AND_AUDIO_DIRECTION.md): theme, visual and sound rules, full asset list

Files named "Initial" are the G1 gate proposal. They are preserved as submitted. Update (G2/G3) and Final (G4) versions will be added alongside them rather than overwriting them.

## Status
- G1 decision: Approved, as reported by Adit on Nov 16, 2026. See [decisions](docs/DECISIONS_AND_OPEN_QUESTIONS.md).
- Next checkpoint: Nov 23, deployed model call, isolated session state and forced-timeout fallback.
- Videos are never committed. Recordings are linked above.

## Revision
The in-game rival now uses two bounded model requests between encounters, validated by game code, with deterministic fallback. The configuration plans all GDF production roles and an executable extension manifest. Dates are filled through G5.
