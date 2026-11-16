# Initial Project Plan
Version 0.2 · November 15, 2026. All dates America/New_York. Dates follow the supplied syllabus. Effort is a proposed allowance, not confirmed availability.

## Gates and milestones
| Date | Commitment |
| --- | --- |
| Nov 15, 11:59 p.m. | G1 pitch recording and linked Initial documents |
| Nov 16 | G1 Concept review. Three assigned midterm silent-playtester notes before class |
| By Nov 17 | Instructor Approve/Hold comment on CourseWorks |
| Nov 19, 11:59 p.m. | Two G1 Braintrust replies, choosing posts with fewer than two replies |
| Nov 23 | Demonstrate deployed model call, isolated session state and forced-timeout fallback |
| Nov 28 | Combined G2/G3 first-playable recording |
| Nov 30 | G2 Prototype and G3 Production review. External playtest, scope lock, Update GDD/configuration and Risk Register. Three Braintrust responses before class |
| Dec 2 | Alpha: agreed features integrated, gaps recorded |
| Dec 4 | Beta: release content locked, verification and fixes |
| After Alpha, before Dec 5 recording | External release playtest and verification of fixes |
| Dec 5 | Gold candidate recording |
| Dec 7 | G4 Final / Pre-Launch review. Preserve approved Gold tag |
| Dec 12 | Draft AAR / showcase evidence |
| Dec 14 | G5 Closure, final game/AAR/log. Play three assigned Gold builds and respond to three classmates |
| Finals slot, Dec 17–23, TBD | Retrospective and 8–10-minute recording due at slot start. Live presentation |

G2 and G3 share a review but have separate decisions. G3 locks the production scope on Nov 30. The GDD/configuration become Final at G4. Post-G4 corrective releases need recorded patches, tests and instructor approval linked from Asana.

## First tasks through G2/G3
Student accountable owner for all tasks: Adit. Implementation begins after G1 approval. Move this plan into Asana after G1 with links to PRs, CI, risks and weekly Progress/Plans/Problems.

| Proposed work window | Task and delegated role | Hours | Dependency | Acceptance evidence |
| --- | --- | --- | --- | --- |
| Nov 16–17 | Scope/reuse audit and final-repo setup · Producer/Tech | 2 | G1 decision | Versioned Initial docs, role manifests and allowed reuse recorded |
| Nov 17–19 | Top-down arena, move/aim/shoot/dodge and restart · Tech/Design | 4 | Repo setup | Human can play, damage and restart deterministically |
| Nov 18–21 | Two powers, pickups, two slots and one fusion · Design/Tech/Art | 4 | Arena | Complete collect/equip/use loop with readable cues |
| Nov 18–22 | Three rival profiles and fixed schedule · Tech/QA | 3 | Arena | Same stats/moves across comparison conditions |
| Nov 17–22 | Cloudflare service, provider access, per-session context and validation · Tech | 5 | Repo/config | Real deployed call. No client secret. Cross-session isolation test |
| By Nov 23 | Hard timeout, neutral fallback and live checkpoint · Tech/QA | 3 | Service + rival | Forced timeout recorded. Late reply ignored. Attempt cap works |
| Nov 23–25 | Integrate history-based selector, reset and logs · Tech/BI | 3 | Checkpoint | End-to-end session, two-call cap, baseline toggle |
| Nov 25–27 | External playtest, bounded live suite and one fix · Design/QA/BI | 3 | Playable integration | Anonymous observations linked to change and verification |
| Nov 27–28 | Gate recording, Update docs and scope-lock proposal · Producer/Release | 1 | Evidence | Recording + linked build, logs, tests and explicit scope |
| Reserved throughout | Integration buffer | 2 | Problems as they arise | Resolve blockers or cut optional content |

Total proposed allowance: 30 hours through the first-playable recording, including two buffer hours. Confirm personal availability before committing. These windows overlap only for independently delegated tasks. The human integrator still reviews each handoff. Extra power/evolution work is excluded from this allowance.

## Scope protection and production
The G2 minimum is the production floor: one arena, three encounters, two powers, one fusion, one model role, deterministic fallback and a valid ending. The broader three-power/two-recipe concept is a ceiling, not a promise to add everything after Nov 30. Only include optional content already working and tested at scope lock, or demonstrably feasible without consuming release-test time. Cut second recipe first, then exploration and extra rooms. If deployment is blocked on Nov 21, dedicate buffer to the service and cut content. Do not silently replace the required model with a local policy.

Between G2/G3 and G4, test a revised encounter and link a finding to a change. Use at least two distinct external players across G2–G4. The post-Alpha release test can also evaluate the revised encounter if the log explicitly demonstrates both requirements. Six-player adaptive/baseline testing is an optional research target. Required external playtests take priority.

## Decision requested and Hold
Approve the bounded prototype and proposed 30-hour allowance through G2/G3 evidence. The instructor's approval is not presumed. Hold conditions: unclear causal agent hypothesis, an unsafe state/knowledge boundary, infeasible available hours, or no credible deployment/fallback plan. Corrective work: narrow content, fix the interface/baseline, demonstrate the service path and revise capacity before reconsideration.

## Braintrust reply method
Watch each real recording. Identify a timestamp, describe what you understood or experienced before proposing a cause, then offer a useful agent-hypothesis or scope note. Do not invent viewing evidence. G1 requires two replies by Nov 19. Subsequent gate responses follow the schedule above.
