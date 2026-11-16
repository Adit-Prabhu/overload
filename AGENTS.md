# Overload · instructions for development agents

Individual final project for COMS E6998 section 014. Adit is Executive Producer and Creative Director, accepting changes and authorizing live spending, publication, merges and tags. The instructor alone approves gates. CourseWorks syllabus, assignment posts and gate decisions override anything here. Record any difference in `docs/DECISIONS_AND_OPEN_QUESTIONS.md`.

## Before working
- Read `README.md`, the newest GDD/Configuration document and `docs/DECISIONS_AND_OPEN_QUESTIONS.md`.
- Check the current gate decision. Prototype implementation is authorized only after G1 approval. Production scope is limited to what G3 approves (Nov 30).
- Preserve user work. Make small, reviewable changes tied to one acceptance criterion. Verify before reporting a result.
- Never review or approve your own change. Hand off to a fresh read-only reviewer.

## Design invariants
- Game code owns all state. The rival model receives only the observation-filter summary (visible distance and power-use events, allowed tactic catalogue, prior accepted tactic) and returns one proposal: `pressure`, `spacing` or `lateral`, plus evidence IDs.
- Game code validates tactic enum, evidence IDs, session/request/encounter IDs, request cap and deadline. Anything invalid, late, unavailable, disabled or over budget becomes `lateral` (neutral), labelled as fallback in logs.
- Encounter 1 starts neutral. At most one request between encounters 1–2 and 2–3, zero retries, 5 s hard deadline, started in the safe room and never on the frame thread. The tactic freezes on encounter entry. Late replies are ignored. Retrying an encounter reuses its entry loadout, tactic and observation checkpoint with no new call.
- Combat is deterministic for the same inputs, seed and accepted tactic trace, and fully playable with the model disabled.
- The fixed-schedule baseline uses identical arena, moves, stats, unlocks and cues, and never reads observations.
- The model never sees raw world state, hidden inventory, RNG, secrets, other sessions, or tools beyond `select_tactic`. It cannot change stats, unlock items or invent moves.

## Docs
- "Initial" files are the G1 submission. Do not rewrite them. Add `UPDATE_*` (G2/G3) and `FINAL_*` (G4) versions.
- Label fixture, replay and live evidence distinctly. A mock, local-only call or replay is not live evidence.

## Safety and spending
- No paid model calls, deployments, credential creation, pushes, tags, releases or course submissions without Adit's explicit authorization for that action.
- Credentials stay server-side (Cloudflare Worker secrets / GitHub Actions secrets or OIDC). Never in the client, repo, prompts or logs.
- Never commit video files. Never put playtester identities or personal data in code, prompts, task text or logs.
- Original Abuse levels/assets are out of scope. Audit any code copied from `Adit-Prabhu/abuse_remake` and record provenance.

## Planned commands (not yet implemented)
- Client: `uv run pytest`, `uv run ruff check .`
- Worker: `npm test` in `worker/`
- CI: `.github/workflows/overload-checks.yml`, deterministic checks on every PR. Live evaluation is manual and separately authorized.
