# Overload · Implementation plan
Version 0.5 · November 16, 2026 · G1 approved. D1 to D8 approved by Adit

This plan turns the Initial Project Plan into buildable work through the finals. The Initial Project Plan stays unchanged as the G1 submission. After G1, these tasks move into Asana with owners, dependencies and acceptance checks. Asset direction lives in [ART_AND_AUDIO_DIRECTION.md](ART_AND_AUDIO_DIRECTION.md).

## 1. Preconditions
- **G1 decision.** Approved, as Adit reported on November 16. Feature work has started.
- **Human authorization.** Adit authorizes each of these individually: paid model calls, deployments, credential creation, pushes to `main`, tags, releases and course submissions.
- **Gates.** The instructor approves gates. Agents never approve or merge their own work.

## 2. Decisions
All decisions D1 to D8 were approved by Adit on November 16, 2026.

| ID | Decision | Recommendation or outcome | Needed by |
| --- | --- | --- | --- |
| D1 | Theme and fiction | **Approved.** "Surge versus the Regulator in a blacked-out substation", as described in the art direction doc | Done |
| D2 | G2 powers and recipe | **Approved.** Spark and Blink, fused into Arc Trail. This is the showcase recipe from the pitch, and both powers are simple to validate. Burst and Shock Cone wait for G3 | Done |
| D3 | Hours through Nov 28 | **Approved: option A, 40 h** (section 6), up from the 30 h in the Initial plan | Done |
| D4 | Music approach | **Approved.** Code-composed synth soundtrack built by the Audio agent and approved by Adit | Done |
| D5 | How visible rival adaptation is | **Approved.** Protocol boot pose, sound sting and icon at encounter start, with no text label. The icon and pose are identical in both conditions | Done |
| D6 | Provider and credential path for the Worker | **Approved.** Gemini on Vertex AI with the course credits. The Worker signs its own access token from a service account key stored as a Worker secret (`roles/aiplatform.user` only). If the course project blocks key creation, ask the instructor. Steps in [DEPLOY.md](DEPLOY.md) | Done |
| D8 | Art direction | **Approved.** Original pixel art in a 3/4 top-down view, in the spirit of Soul Knight, with a follow camera. Replaces the neon vector look from version 0.1 of the art doc. Tasks 2 and 3 were redone in this style on November 16 | Done |
| D7 | Fallback wording | **Approved.** The Fuse Box line reads "Grid link unstable. Regulator running default protocol." It's shown only in live mode and logged as a confound | Done |

## 2b. Overhaul after the first play (Nov 17)
Adit played the first playable build (#7 to #16) and found it too small and too samey. The findings, checked independently:
- The whole game is one hall of 26 x 16 tiles, about 1.6 x 1.8 screens. Nothing to explore, and the player can roam the whole place at once.
- Each fight is two machines plus the Regulator, three times in the same hall.
- Every hostile fires the same bolt sprite.
- The Arc Mite reads as a beetle and the Relay and Regulator as boxes, not robots.
- Two base powers and one fusion are too few for a Soul Knight style game.
- Shots did not leave the caster or land exactly on the cursor (fixed in #16).

Kept: the tile and lighting style, the deterministic simulation and replays, the rival boundary, readable tells, the HUD, the Fuse Box, the audio and the steal, fuse, use loop.

Decisions (Adit, Nov 17):
- **Bigger map now, logged for G3.** The G1 production ceiling allowed three short combat rooms and one hidden branch. Adit chose a larger hand-built floor now. It goes in the G3 scope-lock proposal, and rooms are data, so the instructor can cut them cheaply. Procedural maps stay out of scope (G1 GDD).
- **Dying restarts the sector.** The Surge respawns at the sector's start with the loadout it entered with. Rooms, robots, the Regulator and the observation record all roll back to that checkpoint, and the accepted tactic stays, so the experiment's retry rule (entry loadout, tactic and observation checkpoint, no new model call) holds.
- **Chibi maintenance robots.** Round, chunky bodies with a big glowing visor, readable at 16 px. A style frame comes first for Adit's approval.

### The new structure
| Part | Contents |
| --- | --- |
| Floor | A hand-built substation floor of rooms joined by corridors, identical in both conditions. Three sectors with their own look: Control Hall, Transformer Yard, Core |
| Sector | Entry, then two or three combat rooms, then the Regulator's chamber. Combat room doors lock on entry, robots warp in over a visible 0.6 s tell in two waves, and the doors open when the room is clear |
| Fuse Box | A safe room between sectors: loadout, fusion and evolutions. The rival's one request starts here, as before |
| Regulator | Fought once per sector, three times in all. Encounter 1 stays neutral. The tactic for the next sector is accepted in the Fuse Box and frozen when the player leaves it, before the sector's first room |
| Observation window | The rival now observes the whole sector, robot rooms and the Regulator fight, because the Regulator "watches how you fight" and one fight is little evidence. It uses the same visible kinds only: distance to the nearest active hostile, shots and dodges. Power-use counts for Spark, Blink, Arc Trail, Burst and Shock Cone arrived with #11 (evidence version 3). The deployed Worker accepts them only after a redeploy from main, so until then live requests carrying them fall back to the neutral tactic. Robots in rooms ignore the tactic, so only the Regulator adapts. The fixed baseline records the same window in its trace but never reads it |
| Hidden branch | One secret room behind a cracked wall in sector 2, holding an evolution charge |

### Robots
Each robot carries one power or none, and each attacks in its own way, so no two look or shoot alike. Hostile shots keep the hostile colors and differ by shape (accessibility rule: shape, not color alone).

| Robot | Carries | Attack and tell |
| --- | --- | --- |
| Arc Drone | Spark | Hovers and fires a spiked spark ball after an aim tell |
| Relay Bot | Blink | Marks a landing spot, blinks, then fires three diamond shards in a fan |
| Breaker | Burst | Heavy brute. Raises its fists (tell), slams, and a shockwave ring expands along the floor |
| Sweeper | Nothing | Small roller. Revs up (sparks under the wheels), then rushes in a straight line |
| Sentry | Nothing | Stationary. A long tell, then a slow heavy shell |
| Regulator | Nothing | A big armored control mech with the three protocols: Clamp lunges, Insulate orbs and hazard tiles, Oscillate needle volleys |

### Powers (the G1 production ceiling)
- **Base powers:** Spark, Blink and Burst (a short knockback cone).
- **Evolutions:** two more charges of the same power unlock one:
  - Spark chains to one nearby robot
  - Blink gives a speed boost on arrival
  - Burst widens
- **Fusions:** Arc Trail (Spark + Blink) and Shock Cone (Spark + Burst). Blink + Burst stays unsupported.

### Order of work
This scope needs the instructor's G3 approval (Nov 30) before it counts. If cuts are needed, the G1 cut order applies: the second recipe first, then the hidden branch, then extra rooms. Rooms are data, so cutting one is cheap.

Each item is its own reviewed PR:
1. The robot style frame, for Adit's approval.
2. The floor engine: rooms, corridors, doors, waves and the camera.
3. The robot roster with distinct attacks.
4. Sectors, the Fuse Box room, sector retry, and the rival's timing and observation window.
5. Burst, evolutions and Shock Cone.
6. The Regulator redesign.
7. Sound for the new robots and rooms.

The Worker needs a redeploy from main to accept the five power-use evidence kinds (Adit runs it, docs/DEPLOY.md).

## 3. Architecture

### Repository layout
```
overload/
  pyproject.toml, uv.lock          pygame-ce 2.5.8, pytest, ruff (pinned at setup)
  agent-config.json                common manifest, all course-required fields
  .agents/                         role configs: producer, design, tech, art, narrative, audio, qa, bi, release
  .github/workflows/
    overload-checks.yml            every PR: ruff, pytest (headless), worker tests, boundary checks
    live-eval.yml                  manual dispatch only, budget-capped
    release.yml                    tagged release packaging
  config/
    tactics.json                   pressure, spacing, lateral catalogue
    schedules.json                 fixed-schedule baseline orders (counterbalanced)
    build.toml                     tunables pinned per build
  src/overload/
    sim/                           deterministic game rules, no pygame imports
      world.py state.py rules.py rng.py inputs.py
      powers.py fusion.py enemies.py rival.py encounter.py
    agent/                         the knowledge boundary
      observations.py              world state to filtered summary with evidence IDs
      tactics.py                   proposal validation
      selector.py                  live, fixed-schedule, neutral and fixture selectors
      client.py                    background-thread HTTP client with a hard deadline
    session/
      trace.py replay.py           JSONL traces and deterministic replay
    rooms.py                       room layouts shared by art and sim (terrain, decor, labels)
    game/                          pygame presentation
      app.py                       fixed-step loop and input
      view.py                      pixel renderer, follow camera, cosmetic effects
      (fuse_box.py, title.py, ending.py added with their tasks)
    art/                           palette.py
      pixel/                       grid, actors, tiles, effects, lighting, light (glow), hud
    audio/                         mixer.py (stem control), sfx.py
  assets/
    audio/                         rendered OGG files
    fonts/                         font plus its OFL license
    ASSET_MANIFEST.json
  tools/
    art/ pixel_style_frame.py contact_sheet.py (with color-vision simulation)
    audio/ synth.py song.py sfx.py render.py preview.py
  worker/                          TypeScript Cloudflare Worker (wrangler 4.156.1, Agents SDK added in task 4)
    src/ index.ts session.ts rival.ts validate.ts provider.ts budget.ts
    test/                          vitest with @cloudflare/vitest-plugin
  eval/                            live suite: authored histories, configs, results
  tests/
  docs/
```

### Runtime flow
1. **Title.** Assign the condition (`live` or `fixed`) and the schedule from launch flags. The player never sees them. Live mode creates a server session and gets an opaque session ID.
2. **Encounter 1.** Starts with Oscillate (`lateral`). The rival records visible events only.
3. **End of the encounter.** Freeze the observation summary. Live mode sends exactly one request on a background thread, and the player enters the Fuse Box.
4. **Fuse Box.** The player sets the loadout and fuses powers.
   - **Live mode:** on Continue, wait only until the original 5 s deadline, then validate the reply. If it's invalid, late or missing, fall back to `lateral` and log the reason.
   - **Fixed mode:** reads the next tactic from the schedule, with the same minimum transition time as live mode.
5. **Encounters 2 and 3.** The tactic freezes on entry. Late replies are discarded by request ID.
6. **Death.** Restore the encounter's entry checkpoint: loadout, tactic and observation snapshot. No new request.
7. **Ending.** Winning encounter 3 shows the readout screen. The trace is closed.

### Knowledge boundary
- `observations.py` is the only code that reads world state for the model. It emits a summary of at most 300 tokens. The summary contains:
  - the share of visible time in each distance band (near, mid, far)
  - power uses by power
  - dodge count
  - the previous accepted tactic
  - an evidence ID for each item, such as `e1.far_share`
- The model gets the summary and the tactic catalogue. Nothing else crosses: no positions, health, inventory, RNG, other sessions or tools beyond `select_tactic`.
- Validation happens twice:
  - **In the Worker:** schema, enum, evidence IDs and caps.
  - **In the client:** the same checks plus session, request and encounter IDs and the deadline.
- A test changes hidden state while keeping the observations identical and asserts the prompt bytes don't change.

### Determinism
- The simulation steps at a fixed 60 Hz with its own seeded RNG and doesn't import pygame.
- Cosmetic randomness uses a separate RNG.
- A replay of seed, input frames and accepted tactic trace reproduces the same state hash. CI checks this.

### The Worker
- **Session agent.** One Agents SDK `Agent` per server-issued session ID. Its state holds the last two summaries, the attempt count, request IDs and an expiry. An alarm deletes the state after 30 minutes of inactivity.
- **Routes.** `POST /sessions` creates a session. `POST /sessions/:id/tactic` takes the summary and returns a tactic, evidence IDs, the request ID, requested and resolved model, token usage and latency.
- **Limits.**
  - Two attempts per session, with failures counting.
  - Zero retries.
  - At most 1,000 input and 512 output tokens per attempt.
  - Worst-case cost reserved before dispatch.
- **Global spend cap.** A separate counter refuses all calls once the daily cap is reached. This is the real protection, since a game client can't hold secrets.
- **Secrets.** Stored only with `wrangler secret`. They never reach the client, logs or repo.

### Reuse from the midterm (audited before copying)
These parts of `Adit-Prabhu/abuse_remake` at `ac1e2ba` are worth porting:

| Source | Use in Overload |
| --- | --- |
| `agent/evaluate.py`, `agent/stats.py` and `eval/configs/*.toml` | Live suite runner and report format |
| `agent/protocol.py` | Validation patterns |
| `.github/workflows/live-eval.yml` and `release.yml` | Manual live gating and packaging |
| `.claude/agents/rules-reviewer.md` | Independent reviewer pattern |
| `docs/playtests/protocol.md` and `template.md` | Playtest log format |

The Python provider adapters don't port directly, because the provider call moves into the TypeScript Worker. Their response normalization logic informs `worker/src/provider.ts`. Every copied file gets a provenance note.

## 4. Schedule

### Phase 1 · Critical path (Nov 17–23)
Goal: deployed model call, isolated sessions and forced-timeout fallback by the Nov 23 checkpoint, with a playable deterministic core underneath.

| # | When | Task | Role | Hours | Acceptance |
| --- | --- | --- | --- | --- | --- |
| 1 | Nov 17 | Scaffold: pinned `pyproject.toml` and `uv.lock`, worker package, CI workflow, `agent-config.json`, `.agents/` role files | Tech, Producer | 2 | A PR shows green `uv run pytest`, `ruff` and `npm test` |
| 2 | Nov 17–18 | Style frame: palette, primitives, one composed target screenshot, contact sheet v0 | Art, Design | 2 | Adit approves the style frame |
| 3 | Nov 17–19 | Sim core: fixed step, move, aim, shoot, dodge, arena collision, health, death, retry checkpoint, replay recorder | Tech | 4 | Replay gives an identical state hash. A human can play and restart |
| 4 | Nov 18–21 | Worker: session agent, both routes, validation, provider call, caps, spend counter, TTL alarm. Deploy after Adit authorizes it | Tech | 5 | A deployed call returns a validated tactic. Two sessions keep disjoint histories. No secret in the client |
| 5 | Nov 19–21 | Client selector: background thread, deadline, validation, fallback, stale reply rejection, fixed schedule, JSONL trace | Tech, QA | 3 | Forced timeout and late reply tests pass. The frame loop never blocks |
| 6 | Nov 19–22 | Regulator: three protocols with tells and recovery, protocol boot cue, encounter state machine | Tech, Design | 3 | Scripted test shows each protocol is beatable with every legal loadout. Stats are identical across conditions |
| 7 | Nov 22 | Checkpoint evidence: short recording of a deployed call, two isolated sessions, forced timeout to fallback, and the trace | QA, Release | 1 | Recording plus trace files, labeled live, mock or replay |

**Nov 21 decision point:** if the deployed provider path isn't working, spend the buffer on it, cut content, and raise the blocker with the instructor. Never quietly swap in a local policy.

### Phase 2 · First playable (Nov 23–28)
Thanksgiving is Thursday, Nov 26. The external playtest is scheduled for Wednesday, Nov 25, to avoid it.

| # | When | Task | Role | Hours | Acceptance |
| --- | --- | --- | --- | --- | --- |
| 8 | Nov 23–25 | Powers: Spark, Blink, Arc Trail, charges, two slots, Fuse Box menu, invalid fusion and teleport handling | Design, Tech | 4 | Full loop: collect, equip, fuse, use |
| 9 | Nov 23–25 | Enemies (Arc Mite, Relay), three encounters, ending readout | Tech, Design | 2 | A complete win path, plus a loss and retry path |
| 10 | Nov 21–26 | Art P0 pass: every P0 visual, VFX and HUD element in final style | Art | 3 | Contact sheet passes the grayscale and color-vision check. Adit approves |
| 11 | Nov 21–26 | Audio P0: synth tool, core SFX, HUM and PULSE stems, Fuse Box loop, protocol stings | Audio | 3 | Adit approves the listen-through. The game is fully playable muted |
| 12 | Nov 25 | External playtest with one player, triage, one fix verified | Design, QA, BI | 3 | Anonymous Initial Playtest Log entry linked to a change |
| 13 | Nov 26–27 | Small live suite (at most 18 attempts and $1), plus Update GDD, Update Configuration, Update Risk Register and scope-lock proposal | BI, Producer | 2 | Results record the model ID, latency, cost and failed or unavailable runs |
| 14 | Nov 28 | First-playable recording, 3–5 minutes, with build and config IDs visible | Producer, Release | 1 | Recording linked, never committed |
| | Throughout | Buffer | | 2 | |

### Phase 3 · Production (Nov 30–Dec 5)
| # | When | Task | Role | Hours | Acceptance |
| --- | --- | --- | --- | --- | --- |
| 15 | Nov 30 | Log the G2 and G3 decisions in Asana and lock scope | Producer | 0.5 | Decision task links the reviewed build and config |
| 16 | Nov 30–Dec 2 | Art P1: three lighting states, title and wordmark, animated Fuse Box, styled readout, settings, key art, app icon | Art | 4 | Contact sheet review. Adit approves |
| 17 | Nov 30–Dec 2 | Audio P1: ARC and LEAD stems, full SFX set, victory and defeat stingers, title cue, mix pass | Audio | 4 | Listen-through approved. Audio tool tests pass |
| 18 | Nov 30–Dec 2 | Ceiling content, only what G3 approves | Design, Tech | 0–4 | Same tests and readability checks as P0 |
| 19 | Dec 2 | Alpha: everything agreed is integrated, with the known gaps recorded | Tech, QA | 1 | Gap list in Asana |
| 20 | Dec 2–4 | External release playtest with a second distinct player, triage, verify fixes | Design, QA | 3 | Update Playtest Log links findings to verified changes |
| 21 | Dec 3–4 | Polish within locked content: hitstop, shake, particles, accessibility toggles | Art, Tech | 2 | 60 FPS profile. Toggles work |
| 22 | Dec 4 | Beta: content lock, full live suite, fresh-machine run from the README | QA, Release, BI | 2 | Clean-clone run recorded. Live results saved |
| 23 | Dec 4–5 | Final GDD and Configuration, Update Risk Register, release notes, Gold candidate tag after Adit approves it | Producer, Release | 2 | Docs link the exact tag |
| 24 | Dec 5 | Gold recording | Producer | 1 | 3–5 min recording with the Gold build ID |

### Phase 4 · Release and closure (Dec 7–23)
| Date | Milestone | What's needed |
| --- | --- | --- |
| Dec 7 | G4 | Preserve the approved Gold tag. Any patch after G4 needs a recorded change, tests and instructor approval linked from Asana |
| Dec 12 | Draft AAR and showcase evidence | Shared for peer feedback |
| Dec 14 | G5 | Play three assigned Gold builds, complete the Final Playtest Log, archive the release |
| Finals slot | Retrospective | 8–10 minute walkthrough. Appendix built from `git shortlog` and `gh pr list --author`, plus the Asana export |

## 5. Testing and evaluation
Every PR runs these checks, and they must pass before merging:

| Requirement | Test |
| --- | --- |
| Rule and state invariants | Health bounds, cooldowns, slot limits, fusion inputs kept |
| Valid terminal path | Scripted inputs win all three encounters. A second script loses and retries |
| Invalid actions rejected | Illegal fusion, a blink into a wall, out-of-cooldown use. State stays unchanged |
| Observed regression | Added as soon as the first real bug is found |
| Schema and evidence validation | Unknown tactic, unknown evidence ID, wrong session, request or encounter ID |
| Two-session isolation | Worker test with interleaved requests and disjoint histories |
| Hidden-state invariance | Prompt bytes don't change when only hidden state changes |
| Deadline and stale replies | Fake clock and a delayed fixture |
| Request and budget bounds | A third attempt is refused. Spend cap refusal |
| Playable fallback | Full scripted session with the selector disabled |
| Determinism | Replay produces an identical state hash |
| Asset checks | Palette discipline, manifest completeness, tell timings, mute map, audio levels |

Mocks and fixtures test plumbing only. A live suite runs six authored histories with three repeats each, capped at 18 attempts and $1:
- **When:** it runs before gates and after any model, prompt, tool, memory or permission change.
- **What it records:** model and config versions, outcomes, latency, tokens, cost and failed runs.

Fixture, replay and live data are always labeled separately. Player experience comes from human playtests only.

## 6. Hours
| Phase | Hours |
| --- | --- |
| Phase 1 (tasks 1–7) | 20 |
| Phase 2 (tasks 8–14 and buffer) | 20 |
| Through Nov 28 | 40 |
| Phase 3 (tasks 15–24) | 19.5–23.5 |

The Initial plan allowed 30 h through Nov 28. The extra 10 h breaks down like this:

| Change | Hours |
| --- | --- |
| Style frame plus the art and audio P0 passes | +8 |
| Enemy task, checkpoint recording, live suite and docs | +5 |
| Merging the timeout and integration tasks into the selector task | −3 |

Options for D3:

| Option | Hours | Trade-off |
| --- | --- | --- |
| A | 40 | Full plan. The first playable already looks and sounds like the final game |
| B | 36 | Keep the style frame. Cut P0 audio to six SFX and one loop. Move VFX polish to Phase 3. The recording looks cohesive but plain |
| C | 32 | Style frame only, with simple shapes in the approved palette. All other art and audio move to Phase 3, which is risky with only Dec 2–4 left before the content lock |

Adit chose option A on November 16, 2026.

## 7. Cut order
1. **Gameplay** (unchanged from the Initial plan): second recipe, then the hidden branch, then extra rooms.
2. **Assets:** P2 assets, then P1 animation polish (animated Fuse Box, lighting states, title cue), then showcase material.

Never cut these:
- Telegraphs
- Shape readability
- Palette discipline
- The fallback
- The ending
- Logs
- The adaptive versus fixed comparison

## 8. Risks this plan adds
| Risk | Mitigation |
| --- | --- |
| Asset polish eats integration time | Asset tasks are timeboxed and come after the Nov 23 checkpoint, apart from the 2 h style frame |
| Code-synth music sounds thin | Listen-through review on Nov 26. Fall back to D4's alternatives, with license terms recorded |
| Thanksgiving week cuts playtest access | Playtest moved to Nov 25. Recruit the player by Nov 20 |
| The Worker can't authenticate to Vertex | D6 resolved by Nov 19, with the instructor's input where needed |
| The protocol icon makes adaptation too obvious, or not obvious enough | Ask the playtest question exactly as written. Adjust D5 only with evidence |
