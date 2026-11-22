"""Run the rival live suite against a deployed service and save the evidence.

Usage:
    uv run python tools/rival/live_suite.py URL --label NAME --worker-version ID [--repeats 3]
    uv run python tools/rival/live_suite.py --resummarize evidence/rival/<run>

Each case in eval/histories.json runs in a fresh session as an encounter 2 request, so every
attempt is one model call. A run never makes more than MAX_ATTEMPTS calls, whatever is
asked. Results go to evidence/rival/<UTC date>-<label>/:
- config.json: suite version, prices, limits, git commit, Worker version, prompt hash
- results.jsonl: every attempt as soon as it finishes, fallbacks and failures included
- summary.md: validity, agreement with the designer's intent, latency, tokens, cost

--resummarize rebuilds summary.md from a saved results.jsonl without any calls.
Agreement with intent is a reference for human review, not a correctness score.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import statistics
import subprocess
import time
from collections import Counter
from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path

from overload.agent.client import TacticClient
from overload.agent.observations import evidence_labels
from overload.agent.selector import LiveSelector
from overload.paths import ROOT

HISTORIES = ROOT / "eval" / "histories.json"
MAX_ATTEMPTS = 18  # the plan's ceiling per suite, enforced here
INPUT_USD_PER_M = 0.30  # Vertex Gemini 3.5 Flash-Lite, global, standard tier (list price)
OUTPUT_USD_PER_M = 2.50  # output includes thinking tokens
PROMPT_FILES = ("worker/src/prompt.ts", "config/tactics.json", "config/evidence.json")


def summary_for(values: dict) -> dict:
    labels = evidence_labels()
    items = [
        {"id": f"e1.{kind}", "label": labels[kind], "value": value}
        for kind, value in values.items()
    ]
    return {"items": items, "previous_tactic": "lateral"}


def prompt_hash() -> str:
    digest = hashlib.sha256()
    for name in PROMPT_FILES:
        digest.update((ROOT / name).read_bytes())
    return digest.hexdigest()[:16]


def git_commit() -> str:
    result = subprocess.run(
        ["git", "rev-parse", "--short", "HEAD"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    dirty = subprocess.run(
        ["git", "status", "--porcelain"], cwd=ROOT, capture_output=True, text=True, check=False
    ).stdout.strip()
    return result.stdout.strip() + ("-dirty" if dirty else "")


def _is_fixture_record(record: dict) -> bool:
    if record.get("source") == "fixture":
        return True
    model = record.get("model")
    return isinstance(model, str) and model.startswith("fixture")


def estimated_cost(record: dict) -> float:
    if _is_fixture_record(record):
        return 0.0
    tokens_in, tokens_out = record.get("input_tokens") or 0, record.get("output_tokens") or 0
    return (tokens_in * INPUT_USD_PER_M + tokens_out * OUTPUT_USD_PER_M) / 1e6


def _evidence_banner(records: list[dict]) -> str:
    if not records:
        return "**Evidence type: none.** No attempts recorded."
    has_live = any(r.get("source") == "live" for r in records)
    has_fixture = any(_is_fixture_record(r) for r in records)
    if has_live and has_fixture:
        return (
            "**Evidence type: mixed (live and fixture).** Warning: fixture replies are "
            "present and excluded from live totals, latency, and intent agreement."
        )
    if has_fixture:
        return (
            "**Evidence type: fixture.** Deterministic local fixture replies, "
            "not live model evidence."
        )
    if has_live:
        return "**Evidence type: live.** Real calls to the deployed rival service."
    return "**Evidence type: fallback only.** No valid live or fixture decisions were recorded."


def _format_choice(record: dict) -> str:
    if record.get("reason") is not None:
        return f"fallback ({record['reason']})"
    if record.get("source") == "fixture":
        return f"{record['tactic']} (fixture)"
    if record.get("source") != "live":
        return f"{record['tactic']} ({record.get('source', 'unknown')})"
    return str(record["tactic"])


def run_case(client: TacticClient, case: dict) -> dict:
    selector = LiveSelector(client, client.start_session())
    started = time.monotonic()
    selector.prepare(2, summary_for(case["values"]))
    while (decision := selector.poll(2)) is None:
        time.sleep(0.02)
    record = {
        "case": case["id"],
        "intended": case["intended"],
        **asdict(decision),
        "wall_ms": round((time.monotonic() - started) * 1000),
    }
    record["est_cost_usd"] = round(estimated_cost(record), 6)
    return record


def percentile(values: list[float], q: float) -> float | None:
    """Nearest-rank percentile: the smallest value with at least q of the data at or below."""
    if not values:
        return None
    ordered = sorted(values)
    rank = max(1, math.ceil(q * len(ordered)))
    return ordered[rank - 1]


def write_summary(path: Path, label: str, records: list[dict]) -> None:
    valid = [r for r in records if r.get("source") == "live" and r.get("reason") is None]
    fixture_rows = [r for r in records if r.get("source") == "fixture" and r.get("reason") is None]
    agree = [r for r in valid if r["tactic"] == r["intended"]]
    latencies = [r["latency_ms"] for r in valid if r.get("latency_ms") is not None]
    billable = [r for r in records if not _is_fixture_record(r)]
    tokens_in = sum(r.get("input_tokens") or 0 for r in billable)
    tokens_out = sum(r.get("output_tokens") or 0 for r in billable)
    cost = sum(estimated_cost(r) for r in billable)
    per_case = Counter(r["case"] for r in records)
    counts = sorted(set(per_case.values()))
    if not counts:
        per_case_text = "0 per case"
    elif len(counts) == 1:
        per_case_text = f"{counts[0]} per case"
    else:
        per_case_text = f"{counts[0]} to {counts[-1]} per case"
    models = sorted(
        {
            r["model"].strip()
            for r in records
            if isinstance(r.get("model"), str) and r["model"].strip()
        }
    )
    models_text = ", ".join(models) if models else "none"
    p50 = percentile(latencies, 0.5)
    p95 = percentile(latencies, 0.95)
    latency_text = f"{p50} ms / {p95} ms" if p50 is not None and p95 is not None else "n/a"
    lines = [
        f"# Rival live suite: {label}",
        "",
        _evidence_banner(records),
        "",
        "| Measure | Value |",
        "| --- | --- |",
        f"| Model(s) observed | {models_text} |",
        f"| Attempts | {len(records)} ({per_case_text}) |",
        f"| Valid live decisions | {len(valid)} of {len(records)} |",
    ]
    if fixture_rows:
        lines.append(
            f"| Fixture decisions (excluded from live metrics) | "
            f"{len(fixture_rows)} of {len(records)} |"
        )
    lines += [
        f"| Agree with the designer's intent | {len(agree)} of {len(valid)} valid |",
        f"| Latency p50 / p95, nearest rank (valid) | {latency_text} |",
        f"| Tokens in / out | {tokens_in} / {tokens_out} |",
        f"| Estimated cost | USD {cost:.4f} at list prices of USD {INPUT_USD_PER_M} and "
        f"{OUTPUT_USD_PER_M} per million tokens |",
        "",
    ]
    if records:
        lines += [
            "| Case | Intended | Chosen (per repeat) | Evidence cited |",
            "| --- | --- | --- | --- |",
        ]
        for case_id in dict.fromkeys(r["case"] for r in records):
            rows = [r for r in records if r["case"] == case_id]
            chosen = ", ".join(_format_choice(r) for r in rows)
            cited = " / ".join(",".join(r.get("evidence_ids") or ()) or "none" for r in rows)
            lines.append(f"| {case_id} | {rows[0]['intended']} | {chosen} | {cited} |")
    else:
        lines.append("No attempts recorded.")
    fallbacks = [r for r in records if r.get("reason") is not None]
    lines += ["", f"Fallbacks: {len(fallbacks)}."]
    if latencies:
        lines.append(f"Mean latency: {round(statistics.mean(latencies))} ms.")
    lines += [
        "",
        "Agreement with intent is a reference for human review. The model sees only the "
        "summary and the catalogue. Costs are estimates from list prices, not billing data.",
    ]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def load_records(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("url", nargs="?")
    parser.add_argument("--label")
    parser.add_argument("--worker-version")
    parser.add_argument("--repeats", type=int, default=3)
    parser.add_argument("--overwrite", action="store_true")
    parser.add_argument("--resummarize", type=Path)
    args = parser.parse_args()

    if args.resummarize:
        run_dir = args.resummarize
        label = run_dir.name.split("-", 3)[-1]
        write_summary(run_dir / "summary.md", label, load_records(run_dir / "results.jsonl"))
        print(f"rewrote {run_dir / 'summary.md'}")
        return 0
    if not (args.url and args.label and args.worker_version):
        parser.error("URL, --label and --worker-version are required to run the suite")
    if args.repeats < 1:
        parser.error("--repeats must be at least 1")

    suite = json.loads(HISTORIES.read_text(encoding="utf-8"))
    stamp = datetime.now(UTC).strftime("%Y-%m-%d")
    out = ROOT / "evidence" / "rival" / f"{stamp}-{args.label}"
    config = out / "config.json"
    results = out / "results.jsonl"
    summary = out / "summary.md"
    existing = [p for p in (config, results, summary) if p.exists() and p.stat().st_size > 0]
    if existing and not args.overwrite:
        parser.error(
            f"run directory {out} already has saved evidence "
            f"({', '.join(p.name for p in existing)}). "
            "Use a new --label or pass --overwrite to replace it."
        )
    out.mkdir(parents=True, exist_ok=True)
    if args.overwrite:
        for stale in (results, summary):
            stale.unlink(missing_ok=True)
    budget = min(MAX_ATTEMPTS, args.repeats * len(suite["cases"]))
    config.write_text(
        json.dumps(
            {
                "suite_version": suite["version"],
                "repeats_requested": args.repeats,
                "max_attempts": budget,
                "git_commit": git_commit(),
                "worker_version": args.worker_version,
                "prompt_hash": prompt_hash(),
                "prompt_files": list(PROMPT_FILES),
                "prices_usd_per_million": {"input": INPUT_USD_PER_M, "output": OUTPUT_USD_PER_M},
                "started_utc": datetime.now(UTC).isoformat(timespec="seconds"),
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )

    client = TacticClient(args.url)
    attempts = 0
    try:
        for _ in range(args.repeats):
            for case in suite["cases"]:
                if attempts >= budget:
                    break
                record = run_case(client, case)
                attempts += 1
                with results.open("a", encoding="utf-8") as handle:  # saved as it happens
                    handle.write(json.dumps(record) + "\n")
                print(json.dumps(record))
    finally:
        client.close()
        if results.exists():
            write_summary(out / "summary.md", args.label, load_records(results))
    print(f"wrote {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
