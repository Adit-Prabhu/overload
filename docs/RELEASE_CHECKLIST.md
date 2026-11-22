# Overload Gold Release Checklist

Release verification runbook for the **December 4 Beta lock** and **December 5 to 7 Gold release (G4)**. Every deployment, paid evaluation run, git tag, release publication, and recording link is explicitly authorized and executed by Adit ([AGENTS.md](../AGENTS.md)).

## 1. Fresh-Clone Setup and Automated Tests (Dec 4 Beta Lock)
Run from a clean clone of `main` at the candidate commit (no local untracked files, no `.overload-dev`, no `settings/` overrides):

```sh
git clone https://github.com/Adit-Prabhu/overload.git overload-release-check
cd overload-release-check
git rev-parse --short HEAD

# Python 3.12 client verification
uv sync --frozen
uv run ruff check .
uv run ruff format --check .
uv run pytest -q -W error

# Python 3.11 client verification
uv run --isolated --python 3.11 pytest -q -W error

# Cloudflare Worker verification (local workerd, zero paid calls)
cd worker
npm ci
npm run typecheck
npm test
cd ..
```

- [ ] Clean clone installs cleanly with `uv sync --frozen` and `npm ci`.
- [ ] `ruff check`, `ruff format --check`, and `pytest -q -W error` pass on Python 3.12 and Python 3.11.
- [ ] Worker `npm run typecheck` and `npm test` pass with zero errors.

## 2. Determinism and Replay Check
Confirm pinned simulation hashes match identically across Python 3.12 and Python 3.11 and verify an interactive or headless replay round-trip:

```sh
uv run python tools/pin_hashes.py
uv run --isolated --python 3.11 python tools/pin_hashes.py
```

Verify a real recording replays to the exact same final state hash:

```sh
uv run overload --seed 7 --condition fixed --schedule A --record logs/release-check.json
uv run overload --replay logs/release-check.json
```

- [ ] `tools/pin_hashes.py` prints identical values on Python 3.12 and Python 3.11, matching `tuning_id` `624e3a96` (or the locked Beta `tuning_id`).
- [ ] Recording and replaying on the candidate build passes final state hash verification.
- [ ] Playing with `--condition off` and `--mute` works cleanly end to end.

## 3. Worker Version and Live Evaluation Evidence
Confirm the deployed Cloudflare Worker matches `main` (`config/tactics.json` v3, `config/evidence.json` v4, and `POST /sessions/:id/warmup` OAuth warm-up inside `RivalSession`):

```sh
cd worker
npx wrangler deployments list
cd ..
```

Run the live evaluation suite only with Adit's authorization (paid Vertex AI calls, capped at 18 attempts / $1.00 daily cap), either locally or via the manual GitHub Actions workflow `.github/workflows/live-eval.yml`:

```sh
uv run python tools/rival/live_suite.py "$OVERLOAD_RIVAL_URL" \
  --label beta-lock \
  --worker-version "<deployment-id>" \
  --repeats 3
```

- [ ] Deployed Worker version ID is recorded and matches `main`.
- [ ] Live smoke test (`tools/rival/smoke.py` normal and `--expect-timeout --deadline 0.05`) is recorded with date and Worker version ID.
- [ ] Full live suite report (`evidence/rival/<date>-<label>/summary.md`, `config.json`, `results.jsonl`) covers all 6 `eval/histories.json` v2 cases, logs the resolved `model` ID per attempt in `results.jsonl`, reports nearest-rank p50/p95 latency, tokens, and estimated cost in `summary.md`, and keeps every fallback or failure honestly labeled.
- [ ] External playtest logs (`P1` and `P2`, anonymized) include `tools/rival/compare_traces.py` output with all fallback confounds documented.

## 4. Asset Manifest and Attribution Check
Asset completeness, licenses, and SHA-256 hashes are checked by pytest and should also be spot-checked before tagging:

```sh
uv run pytest -q -W error tests/test_assets.py tests/test_audio_assets.py tests/test_audio.py tests/test_palette.py
```

- [ ] Every file under `assets/` is listed in `assets/ASSET_MANIFEST.json` with a matching SHA-256 hash and valid license file.
- [ ] Every audio cue (`"Approved by Adit in the Nov 19 listen-through"`) and font (`"Approved by Adit in the Nov 16 pixel style frame review"`) in `assets/ASSET_MANIFEST.json` carries an approved status (zero pending entries).
- [ ] `LICENSE`, `LICENSE-ASSETS.md`, `assets/fonts/silkscreen/OFL.txt`, and `docs/REFERENCES.md` are intact and accurate.

## 5. Repository Boundary, No-Videos, and No-Secrets Check
```sh
uv run pytest -q -W error tests/test_repo_boundary.py
git status --short
```

- [ ] `tests/test_repo_boundary.py` passes (zero video files tracked, zero secret files tracked, `agent-config.json` and `.agents/` valid).
- [ ] No playtester personal data, no service URL (`OVERLOAD_RIVAL_URL`), no `.env`, no `.dev.vars`, no `.overload-dev`, no `logs/`, and no `settings/` files are tracked in git.
- [ ] All G1 `docs/INITIAL_*` files remain unmodified. `UPDATE_*` (G2/G3) and `FINAL_*` (G4) docs are added alongside them.

## 6. Gold Candidate Tag and Release Workflow (Dec 5, Adit Only)
Once all checks above are green on `main` and `FINAL_*` documents plus release notes are merged:

1. Align the package version before tagging: update `version` in `pyproject.toml`, `__version__` in `src/overload/__init__.py`, and `uv.lock` (`uv lock`) to match the target release version (for example `1.0.0` for `v1.0.0`), verify tests pass, and merge that version bump to `main`.
2. Tag and push `main`:

```sh
git checkout main
git pull --ff-only origin main
git tag -a v1.0.0 -m "Overload Gold candidate (G4)"
git push origin v1.0.0
```

Pushing a `v*` tag triggers [`.github/workflows/release.yml`](../.github/workflows/release.yml), which re-runs Python 3.11 and 3.12 checks, Worker typecheck and tests, verifies that the tag matches the version in `pyproject.toml`, `src/overload/__init__.py`, and `uv.lock`, builds the wheel, sdist, and tagged source archive (`overload-<tag>-source.tar.gz`) with `SHA256SUMS.txt`, and publishes the GitHub Release. Note that only `overload-<tag>-source.tar.gz` is a complete standalone runnable release archive (including `assets/`, `config/`, docs, and Worker source), while both the `.whl` and the sdist omit `assets/` and `config/` and bundle only the Python `overload` package source.

- [ ] `pyproject.toml`, `src/overload/__init__.py`, and `uv.lock` match the tagged release version.
- [ ] `.github/workflows/release.yml` succeeded on the pushed tag.
- [ ] GitHub Release displays `overload-<tag>-source.tar.gz` (complete runnable archive), the wheel, sdist, `SHA256SUMS.txt`, and accurate release notes citing the Worker version ID, `tuning_id`, `arena_id`, and `config_hash`.
- [ ] Release assets verify locally against `SHA256SUMS.txt` (`sha256sum -c SHA256SUMS.txt`).

## 7. Gold Recording and G4 Freeze (Dec 5 to 7, Adit Only)
- [ ] Record a 3 to 5 minute Gold gameplay walkthrough showing the exact tag/commit, `tuning_id`, `arena_id`, `config_hash`, core loop (steal, evolve, chance fuse), a live Regulator protocol adaptation across sectors, and a fallback or settings/accessibility check.
- [ ] Upload the video externally and link the URL in `README.md` and `FINAL_*` docs (never commit the video file).
- [ ] Preserve the approved G4 Gold tag on December 7. Any post-G4 hotfix requires a recorded change, full passing tests, and instructor approval.
