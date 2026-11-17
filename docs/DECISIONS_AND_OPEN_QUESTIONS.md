# Decisions and open questions
Version 0.2 · November 15, 2026

## Human decisions from the design conversation
Fast shooting, active powers, exploration between fights, a growing collection with two equipped options, same-type evolution plus limited cross-type fusion, and a rival that adapts to habits. The designer rejected trap-heavy concepts as too strategic and expressed no camera preference.

## Assistant recommendations for human review
Top-down 2D, a Python/Pygame client with a Cloudflare-hosted model selector, reuse of midterm harness patterns, two between-encounter calls, and exact recipes, thresholds, latency allocations, optional six-player comparison and 30-hour estimate. These are proposals, not completed work or approved commitments.

## Requirements now resolved
GDF v2.1 Sections 5.1/5.2 and Gate 1 read. Required live deployed model behavior and extension manifest included. Combined G2/G3 review: Nov 30, recording Nov 28. All GDF production roles covered in plan. Cloudflare is the course deployment path. Alternative hosting needs instructor permission. The final is individual, with Adit as Executive Producer/Creative Director and instructor as Gate Approver.

## Open questions
| ID | Question | Needed by |
| --- | --- | --- |
| OQ1 | Which final-game repository and course submission directory should hold the project? | Before upload/PR. Do not assume the midterm directory |
| OQ2 | Can the approved Cloudflare service authenticate to the course Vertex project? | Deployment spike, Nov 21. Demonstrate Nov 23 |
| OQ3 | Are the proposed model ID/settings supported, and what are current prices? | Before first paid call |
| OQ4 | Is 30 hours available through Nov 28, and which dependency versions will be pinned? | G1 review/setup |
| OQ5 | Do players recognize adaptation and regard it as fair? | Initial external playtest |
| OQ6 | Does the LLM improve anything over a simple adaptive rule? | Optional third condition. Otherwise leave claim untested |

## Decisions after G1
| Date | Decision | Source |
| --- | --- | --- |
| Nov 16, 2026 | G1 approved by the instructor. No conditions reported | Adit, from the CourseWorks gate comment |
| Nov 16, 2026 | D1 theme (Surge versus the Regulator), D2 Spark and Blink with Arc Trail, D3 40 hours through Nov 28 | Adit, recorded in [IMPLEMENTATION_PLAN.md](IMPLEMENTATION_PLAN.md) |
| Nov 16, 2026 | OQ1 resolved: the project lives in the public repository Adit-Prabhu/overload | Adit |

## Differences from the Initial documents
| Initial document says | Implementation uses | Reason |
| --- | --- | --- |
| Rival service artifact `worker/src/rival.ts` | Entry point `worker/src/index.ts`, with rival logic planned in `worker/src/rival.ts` | Workers need one entry module. The rival logic file keeps its planned name |
| Context source `src/overload/observations.py:summary` | `src/overload/agent/observations.py:summary` | The knowledge boundary code is grouped under `agent/` |

## Pinned dependencies (OQ4, partly resolved)
Pinned in task 1 (November 16, 2026). Versions published before November 2, 2026 were chosen on purpose, so nothing is days old.

| Package | Version | Note |
| --- | --- | --- |
| pygame-ce | 2.5.8 | LGPL 2.1 |
| pytest | 9.2.0 | |
| ruff | 0.17.5 | |
| wrangler | 4.156.1 | The plan listed 4.163.0, which was published the day of setup |
| @cloudflare/vitest-plugin | 1.4.12 | Replaces @cloudflare/vitest-pool-workers, which is deprecated |
| vitest | 4.1.12 | The plugin needs vitest 4 or 5 |
| @cloudflare/workers-types | 5.20261101.1 | |
| typescript | 5.9.3 | |
| agents (Cloudflare Agents SDK) | Not yet pinned | Added in task 4, when the session agent needs it |
