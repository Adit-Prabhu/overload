# Rival service: first deployed calls

**Evidence type: live.** These are real calls to Gemini on Vertex AI through the deployed Cloudflare Worker. They are a smoke test of the checkpoint requirements, not a model evaluation.

| Field | Value |
| --- | --- |
| Date (UTC) | 2026-11-17T03:35:36Z to 2026-11-17T03:36:08Z |
| Worker version | 01763d3a-6d8e-4493-9a97-845d6b261681 |
| Provider and model | Vertex AI, global, `gemini-3.5-flash-lite` (the model the replies report) |
| Settings | temperature 0, JSON constrained to the three tactics, max 512 output tokens, thinking budget 0 |
| Client | `tools/rival/smoke.py` at the commit that adds this folder |
| Service URL | Not recorded here. The Worker is public and spend-capped, so the URL lives in the `OVERLOAD_RIVAL_URL` environment variable, not the repository |

## What was checked (Nov 23 checkpoint)
| Requirement | Result | File |
| --- | --- | --- |
| Deployed model call | 3 live replies, all validated by the game, 1.15 to 1.46 s each | `normal.jsonl` |
| Isolated session state | Two sessions started separately and answered from their own summaries. Worker tests cover disjoint histories | `normal.jsonl` |
| Request cap | A third request in one session was refused (`request_cap`) and fell back to the neutral tactic | both files |
| Forced timeout and deterministic fallback | With the game's deadline set to 50 ms, every request fell back to `lateral` (Oscillate) at 50 to 51 ms with reason `timeout`. The late replies were ignored | `forced_deadline.jsonl` |
| No secret in the client | The only credential is a Worker secret. The game sends a generic user agent and a summary | code review |

## Cost
- **Live calls:** 6 in total (3 in each run). The forced-deadline calls still reached Vertex and are billed even though the game ignored them.
- **Reported usage:** 350 to 451 input tokens and 35 to 44 output tokens per call. At the dated planning rates ($0.30 and $2.50 per million) that is about $0.0002 per call and about $0.001 in all.
- **The `cost_usd` field** is the Worker's worst-case reservation ($0.00158 per call), not the actual cost.
- **Earlier attempts:** two runs failed before any tactic request (session creation was blocked) and made no paid calls.

## Findings
1. **Prompt gap.** The model chose `spacing` for a player who stayed far away and `pressure` for a player who stayed close, which reinforces the habit instead of countering it. The prompt never states that the Regulator's goal is to counter the observed habit. Fixing this is a prompt change, so it needs its own live check before it counts.
2. **Edge rule.** Cloudflare's edge rejects Python's default `Python-urllib` user agent (error 1010). The client now sends `overload-game/<version>`.
3. **Session timeout.** A short tactic deadline must not apply to session setup. The client now uses a separate session timeout.

## Limits of this evidence
Three live decisions show the path works and the boundary holds. They say nothing yet about whether the rival's choices are good or whether players notice them. That is the job of the live suite (six histories x three repeats) and the playtests.
