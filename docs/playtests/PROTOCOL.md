# Overload External Playtest Protocol

Step-by-step facilitator script for the formal external playtests:
- **Player 1 (`P1`):** November 25, 2026 (first-playable evaluation before the Nov 30 G2/G3 review)
- **Player 2 (`P2`):** December 2 to 4, 2026 (release playtest before the Dec 4 Beta lock)

This protocol produces anonymized human-play evidence for OQ5 ("Do players recognize adaptation and regard it as fair?") and fusion fairness ([POWERS_AND_FUSION.md](../POWERS_AND_FUSION.md), sections 10 and 11).

## 1. Anonymity and Evidence Rules
- **Strict anonymity:** refer to participants only as `P1`, `P2`, and so on. Never record names, emails, handles, voices, photos, or any personal data in playtest logs, traces, issues, PRs, or commits.
- **No video commits:** never commit recordings or raw trace files. Keep raw JSONL traces in local `logs/` (git-ignored).
- **Honest labeling:** keep `live`, `fallback`, `schedule`, and `neutral` evidence strictly separated. Never reclassify a failed, timed-out, or unavailable `live` call as valid live adaptation or silently drop it from analysis.
- **No dev mode:** never pass `--dev` during a playtest. Dev mode disables rival calls and writes no trace.

## 2. Frozen Build and Seed Rule
Every participant plays the same frozen balance build:
- **Difficulty:** `medium` (`tuning_id` `624e3a96`, `arena_id` `cff616dc`). Do not switch difficulty on the title screen.
- **Seed rule ([POWERS_AND_FUSION.md](../POWERS_AND_FUSION.md), section 11):** each participant plays **both** conditions (`live` and `fixed`) on the **same seed**, so the nth fusion roll produces the same rarity in both runs and luck is controlled within-subject. Assign **distinct seeds** across different participants so results do not depend on a single roll sequence.
- **Counterbalancing:** alternate which condition runs first and which fixed schedule (`A` or `B`) is used across participants.

| Participant | Target date | Seed | Run 1 | Run 2 | Fixed schedule |
| --- | --- | --- | --- | --- | --- |
| `P1` | Nov 25, 2026 | `101` | `live` | `fixed` | `A` (`lateral`, `pressure`, `spacing`) |
| `P2` | Dec 2 to 4, 2026 | `202` | `fixed` | `live` | `B` (`lateral`, `spacing`, `pressure`) |

If additional participants join (`P3`, `P4`, ...), continue alternating starting condition (`live` first vs `fixed` first), alternating schedule `A` and `B`, and assigning a fresh unused integer seed per participant.

## 3. Pre-Session Facilitator Checklist
1. Confirm the clean build commit (`git rev-parse --short HEAD`) and verify deterministic checks passed (`uv run pytest -q -W error`).
2. Confirm the deployed Cloudflare Worker version ID (`npx wrangler deployments list` in `worker/`) matches `config/tactics.json` v3 and `config/evidence.json` v4.
3. Export the deployed Worker URL in the facilitator terminal without revealing or committing it:
   ```sh
   export OVERLOAD_RIVAL_URL="https://overload-rival.<your-subdomain>.workers.dev"
   ```
   Verify `OVERLOAD_RIVAL_URL` is non-empty before launching a `--condition live` run. If it is unset, the client falls back to `off` (`neutral`).
4. Check `settings/keys.json` and `settings/prefs.json` before a new participant sits down. Reset to defaults if left over from an earlier player, or invite the participant to open `CONTROLS` and `SETTINGS` on the title screen before clicking Start. Keybinds and audio/accessibility settings never change simulation determinism or rival evidence.
5. Prepare a fresh anonymized log copied from [TEMPLATE.md](TEMPLATE.md) (for example, `docs/playtests/P1_2026-11-25.md`).

## 4. Blind Launch Commands
Keep the terminal out of the participant's sight and refer to the two sessions only as **Run 1** and **Run 2**. Never tell the participant which run is `live` and which is `fixed` until all post-run questions are answered. Both conditions hold the Fuse Box for the same 5 s window (`MIN_FUSE_TICKS`) and use identical arenas, moves, stats, unlocks, and protocol boot cards.

### Participant P1 (seed `101`, `live` first, then `fixed` schedule `A`)
```sh
# Run 1 (blind to participant)
uv run overload --seed 101 --difficulty medium --condition live --trace logs/p1-live.jsonl

# Run 2 (blind to participant)
uv run overload --seed 101 --difficulty medium --condition fixed --schedule A --trace logs/p1-fixed.jsonl
```

### Participant P2 (seed `202`, `fixed` schedule `B` first, then `live`)
```sh
# Run 1 (blind to participant)
uv run overload --seed 202 --difficulty medium --condition fixed --schedule B --trace logs/p2-fixed.jsonl

# Run 2 (blind to participant)
uv run overload --seed 202 --difficulty medium --condition live --trace logs/p2-live.jsonl
```

## 5. Facilitator Script
### Before Run 1 (2 minutes)
Read aloud:
> "You are going to play two full runs of Overload, called Run 1 and Run 2. Each run has three sectors ending in a boss fight against the Regulator. Between sectors you enter a Fuse Box where you can check your loadout and fuse stolen powers before continuing. Please leave the difficulty set to Medium. Feel free to think aloud while you play. I will take notes and avoid giving hints unless you are completely stuck."

During play:
- Do not coach tactics or reveal which protocol is coming next.
- Log confusion, friction, bugs, or strong reactions in the observation table with the condition and sector.
- If the participant quits early or crashes, keep the trace file as recorded and note the incomplete stop honestly.

### Short Break Between Run 1 and Run 2 (2 minutes)
Ask briefly before launching Run 2 (do not reveal the condition):
1. "How did Run 1 feel overall?"
2. "Did you notice the Regulator changing how it fought between sectors?"
3. "Was anything confusing in combat or in the menus?"

### Post-Run Debrief After Run 2 (5 minutes)
Ask these exact questions in order and record verbatim or close-paraphrase answers in the anonymized log before revealing which run was `live` and which was `fixed`:

1. **OQ5 recognition:** "Did you notice the Regulator changing how it fought between sectors?"
2. **OQ5 fairness and readability:** "Did the changes feel fair and readable?"
3. **Powers and fusion highlight:** "Which power or fusion stood out?"
4. **Friction and clarity:** "Where did you feel confused or frustrated?"
5. **Fusion fairness (spec section 10):** "Did fusion results feel fair? (1 to 5, where 1 is very unfair and 5 is very fair)"
6. **Blind run comparison:** "Did Run 1 and Run 2 feel different in how the Regulator reacted to you? If so, how?"

After all six answers are recorded, you may debrief the participant on which run used the live rival and which used the fixed schedule. Label any post-reveal comments separately from blind answers.

## 6. Post-Session BI Trace Comparison
Immediately after the session, run the trace-comparison tool on both JSONL logs:
```sh
uv run python tools/rival/compare_traces.py logs/p1-live.jsonl logs/p1-fixed.jsonl
```

To also save machine-readable JSON locally in `logs/` (git-ignored):
```sh
uv run python tools/rival/compare_traces.py logs/p1-live.jsonl logs/p1-fixed.jsonl --json --out logs/p1-compare.json
```

Review the **Paired Comparison** section carefully:
1. Check `tuning_id`, `arena_id`, and `config_hash` match across both runs.
2. Check whether any `live` encounter 2 or encounter 3 decision fell back to neutral (`source: "fallback"`). If a fallback occurred, keep it flagged as a confound in the participant log and never reclassify it as valid live adaptation.
3. Copy the anonymized summary table and confound flags into the participant's log from [TEMPLATE.md](TEMPLATE.md).
4. Triage every High or Blocker observation into a linked issue or PR and record the fix in the observation table once verified.
