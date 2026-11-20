# Live smoke test, November 19, 2026 (evidence version 4)

**Evidence type: live.** Real calls to the deployed rival service, run by Adit after redeploying the Worker from the merged `main` with evidence version 4 (power uses by family). This is not fixture, mock or replay evidence. Runs 3 and 4 replace the November 17 runs as the November 23 checkpoint evidence (run 4 for live replies, isolation and the cap, run 3 for the forced timeout), since the Worker now runs the evidence version the game sends.

| Item | Value |
| --- | --- |
| Date | 2026-11-19 |
| Worker version ID | Not recorded (the deploy output was not saved). `npx wrangler deployments list` in `worker/` shows it |
| Provider and model | Vertex AI, `gemini-3.5-flash-lite` (as reported in each reply) |
| Service URL | Kept out of the repository (`OVERLOAD_RIVAL_URL`) |
| Command | `uv run python tools/rival/smoke.py "$OVERLOAD_RIVAL_URL"`, and with `--expect-timeout --deadline 0.05` |

All runs are listed in order, including the two that failed, since the failures are evidence too.

## Run 1, straight after the deploy: cold start, failed
```json
{"case": "far", "encounter": 2, "tactic": "lateral", "source": "fallback", "reason": "timeout", "request_id": "10eee769-999f-44ed-ae8f-6f27ba978ad7", "evidence_ids": [], "latency_ms": 5002, "model": null, "input_tokens": null, "output_tokens": null, "cost_usd": null}
{"case": "near", "encounter": 2, "tactic": "lateral", "source": "fallback", "reason": "timeout", "request_id": "1d8399bf-3439-4ccb-8cd2-0eb9b3f09ed4", "evidence_ids": [], "latency_ms": 5003, "model": null, "input_tokens": null, "output_tokens": null, "cost_usd": null}
{"case": "far_3", "encounter": 3, "tactic": "pressure", "source": "live", "reason": null, "request_id": "ff20e32e-3ff7-4fa6-b7df-059bfab3872c", "evidence_ids": ["e1.far_share"], "latency_ms": 1249, "model": "gemini-3.5-flash-lite", "input_tokens": 695, "output_tokens": 35, "cost_usd": 0.00158}
{"case": "far_4", "encounter": 4, "tactic": "lateral", "source": "fallback", "reason": "request_cap", "request_id": null, "evidence_ids": [], "latency_ms": null, "model": null, "input_tokens": null, "output_tokens": null, "cost_usd": null}
```
- The first request of each new session hit the game's 5 s deadline and became the neutral tactic, labelled as fallback with reason `timeout`. The Worker's own 4.5 s timeout starts only after the session object is started, its state is written and its expiry rescheduled, and budget is reserved (`worker/src/session.ts`). On a cold Worker that setup, plus the network time, must have taken more than about 0.5 s, or the Worker's own `timeout` reply would have reached the game before its 5 s deadline. The access token exchange and the model call then share the Worker's 4.5 s window, and the token is fetched fresh after a deploy. The third request, on the now warm session, answered live in 1.2 s.
- The fallback behaved as designed. It does mean a cold first request in real play can lose a live data point (see Follow-up).

## Run 2: one server error, failed
```json
{"case": "far", "encounter": 2, "tactic": "pressure", "source": "live", "reason": null, "request_id": "727d5ea5-d805-4691-b6a2-495602966389", "evidence_ids": ["e1.far_share"], "latency_ms": 2146, "model": "gemini-3.5-flash-lite", "input_tokens": 515, "output_tokens": 35, "cost_usd": 0.00158}
{"case": "near", "encounter": 2, "tactic": "lateral", "source": "fallback", "reason": "http_500", "request_id": "804f3c7c-378f-4b45-8434-ebe8d49aefaf", "evidence_ids": [], "latency_ms": 732, "model": null, "input_tokens": null, "output_tokens": null, "cost_usd": null}
{"case": "far_3", "encounter": 3, "tactic": "pressure", "source": "live", "reason": null, "request_id": "0209f214-92e3-41c0-b538-901bfff932db", "evidence_ids": ["e1.far_share"], "latency_ms": 1206, "model": "gemini-3.5-flash-lite", "input_tokens": 695, "output_tokens": 35, "cost_usd": 0.00158}
{"case": "far_4", "encounter": 4, "tactic": "lateral", "source": "fallback", "reason": "request_cap", "request_id": null, "evidence_ids": [], "latency_ms": null, "model": null, "input_tokens": null, "output_tokens": null, "cost_usd": null}
```
- One request got an HTTP 500 from the Worker and became the neutral tactic, labelled `http_500`. The game handled it as designed.
- Cause not confirmed: no log was captured for this run. Every model and provider error inside the session's handler becomes a labelled status (`provider_error`, `timeout`), never a 500, so the 500 probably came from a step outside it: starting or looking up the session object (`getAgentByName`, `isStarted` in `worker/src/index.ts`), writing its state or rescheduling its expiry, a provider setup error other than a missing configuration, or the cross-object call that reserves budget. The same smoke test passed three times against a local `npx wrangler dev` with the fixture provider on November 19 (fixture evidence, not recorded elsewhere), which rules out the prompt and validation code for these summaries.

## Run 3: forced timeout falls back to neutral, passed
```json
{"case": "far", "encounter": 2, "tactic": "lateral", "source": "fallback", "reason": "timeout", "request_id": "d7f40891-ccab-42bb-85e3-b11a3613692d", "evidence_ids": [], "latency_ms": 52, "model": null, "input_tokens": null, "output_tokens": null, "cost_usd": null}
{"case": "near", "encounter": 2, "tactic": "lateral", "source": "fallback", "reason": "timeout", "request_id": "8a08bdf3-3564-49c2-8026-66696e8abc80", "evidence_ids": [], "latency_ms": 51, "model": null, "input_tokens": null, "output_tokens": null, "cost_usd": null}
{"case": "far_3", "encounter": 3, "tactic": "lateral", "source": "fallback", "reason": "timeout", "request_id": "fd3cbb9b-20f8-48a2-996c-199e26b1f446", "evidence_ids": [], "latency_ms": 69, "model": null, "input_tokens": null, "output_tokens": null, "cost_usd": null}
{"case": "far_4", "encounter": 4, "tactic": "lateral", "source": "fallback", "reason": "request_cap", "request_id": null, "evidence_ids": [], "latency_ms": null, "model": null, "input_tokens": null, "output_tokens": null, "cost_usd": null}
smoke passed
```
- With the game's deadline cut to 0.05 s, every request became the neutral tactic, labelled as fallback with reason `timeout`. The game stops waiting at its deadline (`src/overload/agent/selector.py`), so a reply arriving later cannot change the tactic. The output above shows the fallbacks, not the late replies themselves.

## Run 4: live replies, isolation and the request cap, passed (with the Worker log tailed)
```json
{"case": "far", "encounter": 2, "tactic": "pressure", "source": "live", "reason": null, "request_id": "8c296295-51ba-4915-862d-0e632edc96bb", "evidence_ids": ["e1.far_share"], "latency_ms": 1468, "model": "gemini-3.5-flash-lite", "input_tokens": 515, "output_tokens": 35, "cost_usd": 0.00158}
{"case": "near", "encounter": 2, "tactic": "spacing", "source": "live", "reason": null, "request_id": "6fd28fef-a9f2-48d1-b7d0-458295e0426b", "evidence_ids": ["e1.near_share"], "latency_ms": 1516, "model": "gemini-3.5-flash-lite", "input_tokens": 515, "output_tokens": 35, "cost_usd": 0.00158}
{"case": "far_3", "encounter": 3, "tactic": "pressure", "source": "live", "reason": null, "request_id": "c2f917c1-c1ce-4fbc-be2a-aec31a68ee42", "evidence_ids": ["e1.far_share"], "latency_ms": 933, "model": "gemini-3.5-flash-lite", "input_tokens": 695, "output_tokens": 35, "cost_usd": 0.00158}
{"case": "far_4", "encounter": 4, "tactic": "lateral", "source": "fallback", "reason": "request_cap", "request_id": null, "evidence_ids": [], "latency_ms": null, "model": null, "input_tokens": null, "output_tokens": null, "cost_usd": null}
smoke passed
```
- Two sessions got their own answers: long range drew pressure, close range drew spacing, each citing the matching evidence ID, the same choices as on November 17.
- Every answer passed validation, and replies took 0.9 to 1.5 s, inside the 5 s deadline.
- The third request in a session was refused (`request_cap`) and became the neutral tactic, labelled as fallback.
- The `wrangler tail` log showed every session start, budget reservation and proposal returning Ok, with no exception.
- Input is 515 tokens per first request (521 under version 3), as the version 4 summary is slightly shorter.

## Cost
At most 12 model calls across the four runs (three per run, counting calls the service likely finished after the game stopped waiting, and the run 2 request that failed, which may not have reached the model), at $0.00158 reserved each: under $0.02 in the ledger, far below the $1.00 daily cap.

## Follow-up
- A cold first request can miss the 5 s deadline, and one transient server error was seen. Both fall back safely but lose a live data point. Proposed: retry the budget reservation once and label any other error instead of returning a raw 500, and optionally warm the session before the Fuse Box. Awaiting Adit's decision, since it changes the deployed service.

## Not covered here
These summaries are synthetic (fixed distances and shot counts from `tools/rival/smoke.py`), not from play. Evidence from real play sessions, and the comparison against the fixed-schedule baseline, come later and will be recorded separately.
