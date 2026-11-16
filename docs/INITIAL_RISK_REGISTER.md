# Initial Risk Register
Version 0.2 · G1. Adit owns all risks. Delegated roles investigate. Ratings are initial judgments, not measured likelihoods.

| Risk / trigger | Impact and likelihood | Role | Mitigation | Contingency | Next check |
| --- | --- | --- | --- | --- | --- |
| No working deployed provider path by Nov 21 | High impact / Medium likelihood: local midterm auth does not prove Worker auth | Tech | Test minimum server-side call before gameplay integration | Spend buffer, cut optional content. Seek instructor permission for alternate hosting if needed | Nov 21, evidence by Nov 23 |
| Rival change feels arbitrary or unfair in first external test | High / Medium: no Overload player evidence | Design/QA | Fixed stats, explicit tells, small move set, fairness question | Reduce adaptation choices. Retain model role. Revise hypothesis and request review if contribution disappears | Nov 25–27 |
| Fusion/content work consumes integration time | High / High: interacting features and short release window | Producer | Minimum two powers/one recipe. No recursive fusion | Cut second recipe, exploration and extra rooms | Nov 23 and Nov 27 |
| Invalid or stale model output changes a live fight | High / Medium | Tech/QA | Validate enum, evidence and request/session/encounter IDs. Freeze tactics at encounter start | Neutral deterministic tactic. Log failure, never repair silently | Nov 23 forced-failure test |
| Memory crosses session boundary | High / Low-to-Medium: implementation untested | Tech/QA | Server-owned session keys, no global history, TTL and concurrency tests | Disable affected live path until regression fixed. Preserve honest unavailable status | Nov 23 |
| Model costs exceed reserved allowance or usage is missing | Medium / Medium | BI/Tech | Two attempts, bounded tokens, current pricing check, worst-case reservation | No more dispatch until reconciled. Fallback remains playable | Before each live run |
| Baseline comparison overstates LLM benefit | Medium / High: fixed baseline only tests history dependence | BI/Design | Identical stats/unlocks, balanced order, record waits and fallback | Narrow conclusion. Add simple adaptive baseline only if capacity remains | G2/G3 report |
| Agent output goes unreviewed or exceeds permissions | High / Medium | Producer/QA | Role manifests, small handoffs, independent read-only review | Reject change, reduce delegated task size | Each PR |
| Insufficient human playtest coverage | High / Medium: recruitment unconfirmed | Producer/Release | Recruit two distinct players early, reserve post-Alpha session | Reduce test duration/content, preserve required windows | Nov 23 and Dec 2 |

High Technology, Mechanics and Timeline ratings compound: a deployment delay reduces time to tune interactions and collect player evidence. The Nov 23 checkpoint and strict minimum slice protect both integration and release testing.
