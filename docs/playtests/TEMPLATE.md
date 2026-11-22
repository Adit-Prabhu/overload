# Overload Playtest Log Template

Copy this file to `docs/playtests/P<N>_YYYY-MM-DD.md` for each formal playtest run.

> **Anonymity and evidence rule:** Record zero personal data (no names, emails, handles, or recordings). Label `live`, `fallback`, `schedule`, and `neutral` evidence distinctly and never reclassify failed or fallback live decisions.

## Metadata

| Field | Value |
| --- | --- |
| Participant ID | `P1` |
| Date | `YYYY-MM-DD` |
| Build commit | `<short git sha>` |
| Worker version ID | `<wrangler deployment id>` |
| `tuning_id` | `624e3a96` (Medium) |
| `arena_id` | `cff616dc` |
| `config_hash` | `<from trace>` |
| Seed | `<integer seed>` |
| Condition order | `live -> fixed (schedule A)` or `fixed (schedule B) -> live` |
| Trace paths (local, git-ignored) | `logs/p1-live.jsonl`, `logs/p1-fixed.jsonl` |

## Blind Post-Run Answers (OQ5 and Fusion Fairness)

Record these answers **before** revealing which run was `live` and which was `fixed`.

1. **Did you notice the Regulator changing how it fought between sectors?**
   - Run 1:
   - Run 2:
2. **Did the changes feel fair and readable?**
   - Answer:
3. **Which power or fusion stood out?**
   - Answer:
4. **Where did you feel confused or frustrated?**
   - Answer:
5. **Did fusion results feel fair? (1 to 5)**
   - Score and note:
6. **Did Run 1 and Run 2 feel different in how the Regulator reacted to you? If so, how?**
   - Answer:

## Observations and Triage

Severity levels: `Blocker` (prevents completion or breaks comparison), `High` (hurts readability, fairness, or core loop), `Medium` (notable friction with workaround), `Low` (minor polish).

| # | Observation | Condition / Sector | Severity | Linked PR / Fix |
| --- | --- | --- | --- | --- |
| 1 | | | | |
| 2 | | | | |
| 3 | | | | |

## BI Trace-Comparison Summary

Generate with:
```sh
uv run python tools/rival/compare_traces.py logs/p1-live.jsonl logs/p1-fixed.jsonl
```

Paste the Markdown output (per-trace tables, Paired Comparison, and fallback confounds) below:

```markdown
<!-- Paste tools/rival/compare_traces.py output here -->
```

## Confound and Evidence Notes
- Any `live` decision that fell back to neutral (`source: "fallback"`): `None` or list encounter and exact reason.
- Any incomplete trace or difficulty mismatch: `None` or note honestly.
- Post-reveal remarks (optional, kept separate from blind answers above):
