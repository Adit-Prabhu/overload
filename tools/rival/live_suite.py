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


def estimated_cost(record: dict) -> float:
    tokens_in, tokens_out = record.get("input_tokens") or 0, record.get("output_tokens") or 0
    return (tokens_in * INPUT_USD_PER_M + tokens_out * OUTPUT_USD_PER_M) / 1e6


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
    valid = [r for r in records if r["source"] == "live" and r["reason"] is None]
    agree = [r for r in valid if r["tactic"] == r["intended"]]
    latencies = [r["latency_ms"] for r in valid if r["latency_ms"] is not None]
    tokens_in = sum(r["input_tokens"] or 0 for r in records)
    tokens_out = sum(r["output_tokens"] or 0 for r in records)
    cost = sum(estimated_cost(r) for r in records)
    per_case = Counter(r["case"] for r in records)
    counts = sorted(set(per_case.values()))
    per_case_text = (
        f"{counts[0]} per case" if len(counts) == 1 else f"{counts[0]} to {counts[-1]} per case"
    )
    lines = [
        f"# Rival live suite: {label}",
        "",
        "**Evidence type: live.** Real calls to the deployed rival service.",
        "",
        "| Measure | Value |",
        "| --- | --- |",
        f"| Attempts | {len(records)} ({per_case_text}) |",
        f"| Valid live decisions | {len(valid)} of {len(records)} |",
        f"| Agree with the designer's intent | {len(agree)} of {len(valid)} valid |",
        f"| Latency p50 / p95, nearest rank (valid) | {percentile(latencies, 0.5)} ms / "
        f"{percentile(latencies, 0.95)} ms |",
        f"| Tokens in / out | {tokens_in} / {tokens_out} |",
        f"| Estimated cost | USD {cost:.4f} at list prices of USD {INPUT_USD_PER_M} and "
        f"{OUTPUT_USD_PER_M} per million tokens |",
        "",
        "| Case | Intended | Chosen (per repeat) | Evidence cited |",
        "| --- | --- | --- | --- |",
    ]
    for case_id in dict.fromkeys(r["case"] for r in records):
        rows = [r for r in records if r["case"] == case_id]
        chosen = ", ".join(
            r["tactic"] if r["reason"] is None else f"fallback ({r['reason']})" for r in rows
        )
        cited = " / ".join(",".join(r["evidence_ids"]) or "none" for r in rows)
        lines.append(f"| {case_id} | {rows[0]['intended']} | {chosen} | {cited} |")
    fallbacks = [r for r in records if r["reason"] is not None]
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

    suite = json.loads(HISTORIES.read_text(encoding="utf-8"))
    stamp = datetime.now(UTC).strftime("%Y-%m-%d")
    out = ROOT / "evidence" / "rival" / f"{stamp}-{args.label}"
    out.mkdir(parents=True, exist_ok=True)
    budget = min(MAX_ATTEMPTS, args.repeats * len(suite["cases"]))
    (out / "config.json").write_text(
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
    results = out / "results.jsonl"
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
