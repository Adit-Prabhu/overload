# Live smoke test, November 17, 2026

**Evidence type: live.** Real calls to the deployed rival service, run by Adit from the merged `main`. This is not fixture, mock or replay evidence. It is the November 23 checkpoint evidence (deployed model call, isolated session state, forced-timeout fallback).

| Item | Value |
| --- | --- |
| Date | 2026-11-17 |
| Worker version ID | `937bd7e5-57e2-4ab6-8e3c-e86742093106` |
| Provider and model | Vertex AI, `gemini-3.5-flash-lite` (as reported in each reply) |
| Service URL | Kept out of the repository (`OVERLOAD_RIVAL_URL`) |
| Command | `uv run python tools/rival/smoke.py "$OVERLOAD_RIVAL_URL"`, then the same with `--expect-timeout --deadline 0.05` |

## Run 1: live replies, isolation and the request cap
```json
{"case": "far", "encounter": 2, "tactic": "pressure", "source": "live", "reason": null, "request_id": "1652df7e-6996-49fd-ad74-0e00859b4bc8", "evidence_ids": ["e1.far_share"], "latency_ms": 1641, "model": "gemini-3.5-flash-lite", "input_tokens": 521, "output_tokens": 35, "cost_usd": 0.00158}
{"case": "near", "encounter": 2, "tactic": "spacing", "source": "live", "reason": null, "request_id": "12ca5c9e-f44a-4f53-b25f-a156f46775ae", "evidence_ids": ["e1.near_share"], "latency_ms": 2252, "model": "gemini-3.5-flash-lite", "input_tokens": 521, "output_tokens": 35, "cost_usd": 0.00158}
{"case": "far_3", "encounter": 3, "tactic": "pressure", "source": "live", "reason": null, "request_id": "99e28992-2404-4f88-a9d9-1174ee18cf5f", "evidence_ids": ["e1.far_share"], "latency_ms": 1096, "model": "gemini-3.5-flash-lite", "input_tokens": 707, "output_tokens": 35, "cost_usd": 0.00158}
{"case": "far_4", "encounter": 4, "tactic": "lateral", "source": "fallback", "reason": "request_cap", "request_id": null, "evidence_ids": [], "latency_ms": null, "model": null, "input_tokens": null, "output_tokens": null, "cost_usd": null}
smoke passed
```
- Two sessions got their own answers: long range drew pressure, close range drew spacing, each citing the matching evidence ID.
- Every answer passed validation, and replies took 1.1 to 2.3 s, inside the 5 s deadline.
- The third request in a session was refused (`request_cap`) and became the neutral tactic, labelled as fallback.
- Ledger cost: 3 × $0.00158 = $0.00474.

## Run 2: forced timeout falls back to neutral
```json
{"case": "far", "encounter": 2, "tactic": "lateral", "source": "fallback", "reason": "timeout", "request_id": "716d790a-0eca-420f-adae-4801ee8a24d7", "evidence_ids": [], "latency_ms": 51, "model": null, "input_tokens": null, "output_tokens": null, "cost_usd": null}
{"case": "near", "encounter": 2, "tactic": "lateral", "source": "fallback", "reason": "timeout", "request_id": "6cc3c999-f15e-432b-af8a-a99ca8438cfa", "evidence_ids": [], "latency_ms": 50, "model": null, "input_tokens": null, "output_tokens": null, "cost_usd": null}
{"case": "far_3", "encounter": 3, "tactic": "lateral", "source": "fallback", "reason": "timeout", "request_id": "9b0817e7-cd60-4ade-90a8-5dd27d10358b", "evidence_ids": [], "latency_ms": 70, "model": null, "input_tokens": null, "output_tokens": null, "cost_usd": null}
{"case": "far_4", "encounter": 4, "tactic": "lateral", "source": "fallback", "reason": "request_cap", "request_id": null, "evidence_ids": [], "latency_ms": null, "model": null, "input_tokens": null, "output_tokens": null, "cost_usd": null}
smoke passed
```
- With the game's deadline cut to 0.05 s, every request became the neutral tactic (`lateral`), labelled as fallback with reason `timeout`. Late replies were ignored.
- The service most likely still completed these three model calls after the game stopped waiting, so expect about another $0.005 in the ledger. Both runs together stay far below the $1.00 daily cap.

## Not covered here
These summaries are synthetic (fixed distances and shot counts from `tools/rival/smoke.py`), not from play. Evidence from real play sessions, and the comparison against the fixed-schedule baseline, come later and will be recorded separately.
