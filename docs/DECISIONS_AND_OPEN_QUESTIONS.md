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
| OQ7 | Which license covers the project's own code, art and audio? The repository has none yet, and `assets/audio/LICENSE.txt` reserves all rights until one is chosen | Before the public release (G4) |

## Decisions after G1
| Date | Decision | Source |
| --- | --- | --- |
| Nov 16, 2026 | G1 approved by the instructor. No conditions reported | Adit, from the CourseWorks gate comment |
| Nov 16, 2026 | D1 theme (Surge versus the Regulator), D2 Spark and Blink with Arc Trail, D3 40 hours through Nov 28 | Adit, recorded in [IMPLEMENTATION_PLAN.md](IMPLEMENTATION_PLAN.md) |
| Nov 16, 2026 | OQ1 resolved: the project lives in the public repository Adit-Prabhu/overload | Adit |
| Nov 16, 2026 | D8: art direction changes from neon vector to original pixel art in a 3/4 top-down view, in the spirit of Soul Knight. Substation setting kept, the Surge becomes a lineworker, the camera follows the player | Adit, after playing the vector build |
| Nov 16, 2026 | Asset source: original code-authored pixel art, with free CC0 packs as the fallback if it did not look good. CC0 packs were evaluated (0x72 Robot Tileset is side-view, Kenney roguelike packs are fantasy and village themed) and none fit a top-down industrial setting | Adit chose the rule, the assistant ran the comparison |
| Nov 16, 2026 | Pixel style frame round 2 approved ("much much better"). Make it playable | Adit |
| Nov 16, 2026 | D6: the rival service calls Gemini on Vertex AI with the course credits, through a service account key held as a Cloudflare Worker secret. Resolves OQ2 pending deployment | Adit |
| Nov 16, 2026 | D4 code-composed synth soundtrack. D5 protocol shown by pose, sound sting and icon at encounter start, no text. D7 fallback line "Grid link unstable. Regulator running default protocol." Banner labels "SHORT CIRCUIT" and "SECTOR CLEAR" kept | Adit |
| Nov 17, 2026 | After playing the first playable build: build a larger hand-built floor of rooms and corridors now (three sectors, combat rooms with locking doors, a Fuse Box room, a hidden branch), past the G1 ceiling of three combat rooms. Logged for the G3 scope-lock proposal. Dying restarts the current sector with its entry loadout and tactic. Enemies become chibi maintenance robots, each with its own attack and projectile shape. Plan in [IMPLEMENTATION_PLAN.md](IMPLEMENTATION_PLAN.md) section 2b | Adit |

## Differences from the Initial documents
| Initial document says | Implementation uses | Reason |
| --- | --- | --- |
| Rival service artifact `worker/src/rival.ts` | `worker/src/index.ts` (routes) and `session.ts` (RivalSession, a Cloudflare Agents SDK agent), with `schema.ts`, `prompt.ts`, `providers.ts`, `google.ts` and `budget.ts` | Workers need one entry module, the Agents SDK gives each session its own isolated state and scheduled expiry, and small files keep validation, prompt and provider separately testable |
| Evidence labels written by the client | Labels come from `config/evidence.json` on the server, and only the listed observation kinds are accepted | A modified client could otherwise put arbitrary text into the prompt |
| Context source `src/overload/observations.py:summary` | `src/overload/agent/observations.py:summary` | The knowledge boundary code is grouped under `agent/` |
| The Relay arrives with task 9 | The Relay arrives with task 8 | Blink needs a carrier, so the full collect, equip, fuse, use loop could not be tested without it |
| The GDD does not say whether Blink and Arc Trail can be chained | They share one teleport cooldown | Two slots could otherwise jump twice the Blink range in one tick and double the teleport rate |
| Fixed mode uses "the same minimum transition time as live mode" | The Fuse Box holds for 5 s, the request deadline, in every condition | A shorter hold let a slow live reply make the live gap visibly longer, which would reveal the condition |
| Bodies not specified | The Surge cannot stand inside the Regulator or a machine. A dodge slips through. Pinned between a body and a wall it may still overlap a little, because walls always win | Standard top-down convention, and dodge stays useful against Clamp |
| Retry restores the encounter's entry loadout, tactic and observation snapshot (GDD, Session) | Retry restores the sector's entry checkpoint: loadout, rooms, robots, Regulator, tactic and observation record | Adit, Nov 17: the larger floor makes a sector the unit of play. The rule is the same, applied to a bigger unit, and still makes no new model call |
| G2 test slice: one arena reused for three encounters, no full map (GDD scope table) | A hand-built floor of 15 rooms in three sectors, before G2 | Adit, Nov 17, after playing the slice. Needs the instructor's G3 approval to count, and the G1 cut order applies |
| Production ceiling: three short combat rooms, one hidden branch | Six combat rooms, three chambers, two Fuse Box rooms, three entries, one hidden room | As above. Rooms are data, so cuts are cheap |
| Enemies: Arc Mite (Spark), Relay (Blink), Coil (Burst) | Arc Drone (Spark), Relay Bot (Blink), Breaker (Burst), plus two power-less robots, Sweeper and Sentry | Adit, Nov 17: robots instead of bug-like machines, and each attacker needs its own attack and projectile |
| The Regulator observes its own encounter | The Regulator observes the whole sector with the same visible kinds | One fight is thin evidence, and the fiction is that it watches how you fight. Explained in IMPLEMENTATION_PLAN section 2b |
| The rival observes power uses by power (G1 plan, knowledge boundary) | Spark, Blink and Arc Trail counts arrive with #11. Burst and Shock Cone uses are not observed yet | Both need new evidence kinds in `config/evidence.json` and a Worker redeploy, which waits for Adit's go. Until then the rival sees less than the plan says, never more |
| Loadout and fusion happen in the safe-room menu (GDD) | Tab opens the loadout menu anywhere, pausing the game. Equip and fuse any time the Surge is up. The Fuse Box stays the safe room: recharge, the rival's one request, and Continue | Adit, Nov 17: "I should be able to fuse and switch these powers whenever I want". A retry still restores the sector's entry loadout, so a fusion made mid-sector is undone by dying, but its ingredients come back too |
| One Regulator, the same body in every encounter (GDD) | Three Regulator chassis, one per sector chamber: the Linesman (36 health, a ring of 8 bolts), the Transformer (52 health, quicker, a wide floor shockwave) and the Grid Core (66 health, summons two drones, then at half health overloads into a faster pace and a twin bolt spiral). Each signature has its own tell of at least 0.5 s and pauses the protocol while it runs. The protocol (pressure, spacing or lateral) is unchanged and still the only thing the rival model picks. The chassis is fixed per sector and identical in both conditions, so the comparison is unaffected. The legacy single-arena mode keeps the plain Regulator | Adit, Nov 17: "the boss feels pretty 1D... different bosses, different levels of difficulty and each one has different patterns". Needs the instructor's G3 approval to count |
| Balance not specified | Health 40 for every protocol. A scripted player beats Clamp and Insulate in about 10 s and Oscillate in about 40 s. Solid bodies made Insulate harder for a player who only walks, since a hazard can pin them against the Regulator, so the test player now dodges out of armed tiles | Left for the Nov 25 playtest to judge before any retune |

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
