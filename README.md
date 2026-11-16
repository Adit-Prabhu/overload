# Overload · G1 proposal
Version 0.2 · November 15, 2026 · Gate 1. Supersedes the local-policy-only draft.

Overload is a top-down shooter where you steal and fuse enemy powers to feel inventive and capable of surprising a rival that learns how you fight. COMS E6998 section 014 (AI in Practice: Game Design and Development), Columbia University, individual final project.

This repository currently holds the G1 concept package. It describes proposed work, not a completed game or observed playtest results. It follows the course syllabus and GDF reader v2.1 (November 10). No game code, deployed service, paid model call or playtest exists yet.

## G1 submission
- Recording (3–5 min): https://youtu.be/uBufxDVXPek
- Deck presented: [docs/g1/Overload_G1.pptx](docs/g1/Overload_G1.pptx)
- [Initial GDD](docs/INITIAL_GDD.md)
- [Initial Configuration Document](docs/INITIAL_CONFIGURATION.md) (open questions, planned agent role coverage, extension manifest)
- [Initial Project Plan](docs/INITIAL_PROJECT_PLAN.md)
- [Initial Risk Register](docs/INITIAL_RISK_REGISTER.md)
- [References and attribution](docs/REFERENCES.md)
- [Decisions and open questions](docs/DECISIONS_AND_OPEN_QUESTIONS.md)
- [Historical first-round pitch](docs/history/FIRST_ROUND_PITCH.md)

Files named "Initial" are the G1 gate proposal. They are preserved as submitted. Update (G2/G3) and Final (G4) versions will be added alongside them rather than overwriting them.

## Status
- G1 decision (Approve/Hold): pending, posted on CourseWorks by Nov 17.
- Next checkpoint: Nov 23, deployed model call, isolated session state and forced-timeout fallback.
- Videos are never committed. Recordings are linked above.

## Revision
The in-game rival now uses two bounded model requests between encounters, validated by game code, with deterministic fallback. The configuration plans all GDF production roles and an executable extension manifest. Dates are filled through G5.
