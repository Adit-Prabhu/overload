# Initial Game Design Document
Version 0.2 · November 15, 2026 · Gate 1 proposal

## The X
Overload is a top-down shooter where you steal and fuse enemy powers to feel inventive and capable of surprising a rival that learns how you fight.

## Player and motivation
For players who enjoy aiming while moving, combining active abilities, and exploring between intense fights. The proposed motivation is mastery through discovery. In a playtest, players should voluntarily try a newly unlocked combination and change their approach after recognizing a rival's adjustment. This is a hypothesis, not validated audience demand.

## Pillars
1. **Keep moving.** Shooting and powers remain usable during movement. Short, readable attacks reward execution.
2. **Discover useful combinations.** Every new power changes an action, and hidden areas reward exploration with a new option.
3. **A rival that remembers.** The rival responds to observed habits across encounters. Telegraphs let the player understand and answer that response.

## Concepts explored
| Concept | Appeal | Why it did not win |
| --- | --- | --- |
| Hunt the Hunter | Creature pursuit and environmental traps | Too much preparation and trap strategy for the intended action experience |
| Blink | Shooting with short-range teleportation | Strong movement hook, but less room for the growing power collection the designer chose |
| Zero-G | Shooting, grappling and gravity | Appealing movement, but physics interactions increase implementation and tuning work |
| Overload | Shooting, stolen powers and limited fusion | Best match to the designer's stated preferences for active combat and discovering abilities |

These were explored in design discussion. No comparative prototypes or class votes were conducted.

## Core loop
- **Act:** enter a room, move, shoot and use equipped powers.
- **Respond:** enemies telegraph attacks, take damage and drop power fragments. The rival records only behavior it can see.
- **Interpret:** notice which combinations work and which habits the rival starts countering.
- **Next action:** explore a branch or enter a safe room to evolve powers, choose a loadout and face the next encounter.

## Player controls and progression
Proposed desktop controls: WASD movement, mouse aim, left click shooting, Space basic dodge, Q/E equipped powers. A safe-room menu handles loadout and fusion. Key rebinding is an open accessibility question.

Collection persists through a session. First pickup unlocks a base power. Two additional same-type fragments unlock one predefined evolution. These thresholds are initial tuning choices. Fusion unlocks a recipe without destroying its ingredients. Each resulting ability uses one of two loadout slots. Recipes use base powers only at first. No recursive fusion.

| Power | Base action | One planned evolution |
| --- | --- | --- |
| Spark | Short electric projectile | Chains to one nearby enemy |
| Burst | Short directional knockback | Wider cone |
| Blink | Short teleport, validated against walls | Brief movement-speed boost after arrival |

Two planned cross-type recipes: Spark + Blink leaves an electric trail. Spark + Burst creates an electric knockback cone. Blink + Burst is intentionally unsupported in this prototype. All names, effects and costs are provisional.

## Session, win and failure
Target: approximately 10 minutes, with a safe room between encounters. Win by completing the final rival encounter. On defeat, restart the current encounter with the same entry loadout. Restore its entry rival-memory snapshot so retries do not secretly strengthen the opponent. Exact enemy count and session pacing require testing.

## In-game agent hypothesis
An LLM-controlled rival that changes its next encounter's tactic using observed combat habits will encourage players to experiment with loadouts and feel that their choices matter more than a rival with a fixed tactic schedule.

The proposed implementation is an LLM tactic selector called between encounters through a deployed Cloudflare service. The rival measures visible time spent far away and visible uses of equipped powers. It selects one of three authored tactic profiles between encounters: pressure, spacing or lateral movement. Game code validates its structured proposal. A five-second deadline, invalid output or service failure triggers a deterministic neutral profile. Low-level movement and attack execution remain authored in both conditions. Do not describe this as unrestricted learning or new move generation.

Example: after observing sustained long-range attacks, the rival selects pressure, using a clearly signaled approach with recovery frames. It does not gain damage, health, speed or perfect counters. A different tactic must remain beatable with every legal loadout.

### Scripted baseline
Use the same arena, moves, stats, telegraphs, powers and progression. Replace observation-based tactic selection with a predetermined schedule across the three encounters. Record observations for analysis in both versions, but prevent the baseline selector from reading them. Counterbalance session order. Fixed schedules should be balanced across participants so one unusually hard profile does not define the comparison.

### Player loss
The baseline can still offer challenge and variety. What it cannot offer is a tactic change caused by this player's observed history. The player loses the experience of recognizing and deliberately breaking a habit that their rival has learned.

### Small playtest
Recruit six players if feasible as an optional comparison beyond the required course playtests. Each plays a 10-minute adaptive session and a 10-minute baseline session, with fresh state and identical unlock opportunities. Three play adaptive first. Three play baseline first. Treat this as formative evidence, not statistical proof.

Question: “What did you think the rival changed, and did that make you change how you played? Describe a specific moment.” Then rate “The rival responded to how I played” and “The fight felt fair” from 1 to 5. Log power use, distance, loadout changes, tactic selection, deaths and encounter duration. Do not count a loadout change alone as proof of adaptation, since progression also encourages changes.

Proposed continuation criterion: if six players are recruited, at least four of six players identify a behavior-linked adjustment and give an example of their response, median perceived responsiveness is at least one point higher than baseline, and median fairness is at least 3/5. Failure means revise signals or selection policy before adding content.

## Scope
| Milestone | Included | Explicitly excluded |
| --- | --- | --- |
| G2 test slice | One arena reused for three rival encounters, gun/dodge, two base powers, two equip slots, one fusion, adaptive/baseline toggle, logs | Full map, full collection, visual polish |
| Production ceiling, conditional on G2/G3 scope lock | Three base powers, one evolution each, two fusion recipes, three short combat rooms, one hidden branch and one safe-room menu | Multiplayer, procedural maps, 3D, dialogue, neural training, open-ended move generation, accounts, multiplayer backend, unrestricted fusion |

Cut order: second cross-type recipe, hidden branch, extra rooms. Keep the adaptive/baseline comparison and minimum two powers. Same-type evolution may remain a menu-only proof at G2. No cut should silently remove the agent hypothesis.

## Risk profile
| Dimension | Rating | Evidence / uncertainty | Mitigation |
| --- | --- | --- | --- |
| IP / Concept | Low | Original setting and placeholder art planned. References inform mechanics. Working title unreviewed | Keep source/license manifest and use original assets. Check title before public release |
| Business / Audience | Medium | Designer preferences are known. No external audience validation | Recruit action-game players and observe voluntary experimentation |
| Technology | High | Midterm has a Vertex adapter and harness, but Cloudflare deployment, authentication and session isolation are untested | Prove deployed call, session isolation and forced fallback by Nov 23. Keep combat independent of calls |
| Team | Medium | One human integrator. Python/Pygame midterm exists, but available hours remain unconfirmed | Separate bounded agent tasks, human review, small integration batches |
| Genre / Mechanics | High | Fusion and adaptive opposition can become confusing or feel unfair | Start with two powers/one recipe, fixed stats, readable tells, fairness question and cut thresholds |
| Timeline | High | Several interacting systems remain unbuilt. First playable is due Nov 28 and scope locks Nov 30 | Use the 30-hour proposed allowance, finish a minimal playable before Nov 28, cut content before agent evaluation |

Mechanics and Timeline share a cause: too many interactions to tune. Technology adds a deployment dependency that could consume the same buffer. The Nov 23 service checkpoint and smallest comparison slice address these compounding risks.

## Open questions
See the decision log. Largest uncertainties are whether players notice the rival's response, whether it feels fair, actual implementation time, and whether the deployed selector is reliable within its budget.

## Dynamics, aesthetics and feedback
Intended dynamics: a strong loadout encourages a repeatable habit, the rival's next tactic makes the player reconsider it, and a new combination opens a different approach. Intended aesthetics are discovery, tension and mastery. Each rival tactic has a distinct opening pose/movement cue. Attack tells use shape and motion as well as color. Optional sound reinforces them. Do not rely on color alone. No free-form generated dialogue is needed.

## Scoring, edge cases and balance
No competitive score or leaderboard in the prototype. Success means winning the third encounter. Optional end-screen statistics show deaths, powers tried and completion time, without ranking participants.
- Invalid fusion: show supported recipes, consume no fragments and preserve inventory.
- Duplicate pickup after maximum evolution: display “fully evolved”. No recursive upgrades.
- Invalid teleport: reject the move and preserve its resource cost. Test wall and arena edges.
- Both damage events in one tick: resolve deterministic order, then outcome. Proposed tie rule: player death takes precedence over victory. Expose this in rules.
- Late model result: discard by session and encounter/request ID. Never alter a fight already started.
- Retry: restore entry loadout and accepted tactic. No extra model request and no extra adaptation.
- Timeout: display a brief connection-status message in the safe room, then start with the neutral tactic. Label fallback in logs so it is not mistaken for successful live adaptation.
Power cooldowns and damage are tunable proposals, pinned per build. All legal loadouts must have a viable answer to every rival profile. Compare versions with identical movement, stats, unlock timing and telegraphs.

## Platform and implementation proposal
Python 3.11/3.12 with pygame-ce for the top-down desktop client, plus a Cloudflare-hosted agent endpoint. This uses familiar midterm tooling while implementing an original top-down simulation. The Abuse side-scrolling engine and original assets are not drop-in components. Start with the course's Cloudflare foundation for the deployed service and verify the Vertex access path by November 23. Alternative hosting requires instructor permission.

## Limits of the AI claim
A fixed-schedule baseline tests history-dependent behavior, not whether an LLM is necessary. A simple adaptive rule could also react to history. If time permits, add that rule-based adaptive control. Otherwise explicitly limit conclusions to the fixed-schedule comparison. If the LLM adds no useful behavior, record that result and propose a smaller role for instructor review rather than claiming superiority.
