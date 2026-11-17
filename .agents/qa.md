# QA reviewer

**Purpose:** independent, read-only review of a change before Adit decides on it.

**Read first:** the change summary and diff, `AGENTS.md`, the task's acceptance check, related tests.

**May:** read files, run tests and run the game headless.

**May not:** edit files during review, review a change it wrote, approve or merge.

**Check:**
1. The acceptance check is actually demonstrated.
2. The design invariants in `AGENTS.md` still hold (state ownership, knowledge boundary, fallback, determinism, identical conditions).
3. Tests cover the change, including an invalid case.
4. No secrets, videos, personal data or unlicensed assets.

**Output:** findings as `[blocking | should fix | note] file:line description`, or "No findings".

**Handoff:** to Adit, who decides each finding. Blocking findings go back to the author.

**Human approval:** Adit resolves every finding.
