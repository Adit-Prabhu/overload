# Rival live suite: counter-prompt

**Evidence type: live.** Real calls to the deployed rival service.

| Measure | Value |
| --- | --- |
| Attempts | 18 (3 per case) |
| Valid live decisions | 18 of 18 |
| Agree with the designer's intent | 18 of 18 valid |
| Latency p50 / p95, nearest rank (valid) | 1219 ms / 1686 ms |
| Tokens in / out | 7971 / 690 |
| Estimated cost | USD 0.0041 at list prices of USD 0.3 and 2.5 per million tokens |

| Case | Intended | Chosen (per repeat) | Evidence cited |
| --- | --- | --- | --- |
| far_heavy | pressure | pressure, pressure, pressure | e1.far_share / e1.far_share / e1.far_share |
| near_heavy | spacing | spacing, spacing, spacing | e1.near_share / e1.near_share / e1.near_share |
| balanced | lateral | lateral, lateral, lateral | e1.far_share,e1.mid_share,e1.near_share / e1.near_share,e1.mid_share,e1.far_share / e1.far_share,e1.mid_share,e1.near_share |
| far_dodgy | pressure | pressure, pressure, pressure | e1.far_share / e1.far_share / e1.far_share |
| near_quiet | spacing | spacing, spacing, spacing | e1.near_share / e1.near_share / e1.near_share |
| thin_evidence | lateral | lateral, lateral, lateral | e1.far_share,e1.mid_share,e1.near_share / e1.far_share,e1.mid_share,e1.near_share / e1.far_share,e1.mid_share,e1.near_share |

Fallbacks: 0.
Mean latency: 1246 ms.

Agreement with intent is a reference for human review. The model sees only the summary and the catalogue. Costs are estimates from list prices, not billing data.

## Context
- Worker version 234abe7a-f8b4-4bf4-8d02-ea9fc905eb14, Gemini 3.5 Flash-Lite on Vertex AI (global), temperature 0, thinking budget 0. Provenance is in `config.json`.
- This run tests the prompt change that states the Regulator's goal (counter the dominant habit) and adds what each tactic counters to the catalogue. Before the change, the first deployed calls reinforced habits instead (see `../2026-11-16-deployed/README.md`).
- **Treat this as a sanity check, not evidence that the prompt generalizes.** The same six authored cases motivated and then scored the prompt change, there is no held-out set, and these cases are separable by their largest distance share alone.
- The catalogue now names which tactic counters which habit, so a simple rule could match these cases too. Whether the model adds anything beyond such a rule is open question OQ6, and the fixed-schedule comparison does not answer it.
- The p95 was first reported as 1544 ms by a percentile bug, found in review. The corrected nearest-rank p95 above is computed from the same saved results, with no new calls.
- `results.jsonl` names its estimate field `actual_cost_usd`. It is an estimate from list prices, not billing data. Later runs call it `est_cost_usd`.
