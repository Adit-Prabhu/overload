"""Run the rival live suite against a deployed service and save the evidence.

Usage: uv run python tools/rival/live_suite.py URL --label NAME [--repeats 3] [--max-attempts 18]

Each case in eval/histories.json runs in a fresh session as an encounter 2 request, so every
attempt is one model call. The run stops at --max-attempts no matter what. Results go to
evidence/rival/<UTC date>-<label>/:
- config.json: suite version, prices, model and limits
- results.jsonl: every attempt, including fallbacks and unavailable runs
- summary.md: validity, agreement with the designer's intent, latency, tokens, cost

Agreement with intent is a reference for human review, not a correctness score.
"""

from __future__ import annotations

import argparse
import json
import statistics
import time
from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path

from overload.agent.client import TacticClient
from overload.agent.observations import evidence_labels
from overload.agent.selector import LiveSelector
from overload.paths import ROOT

HISTORIES = ROOT / "eval" / "histories.json"
INPUT_USD_PER_M = 0.30  # Vertex Gemini 3.5 Flash-Lite, global, standard tier
OUTPUT_USD_PER_M = 2.50  # output includes thinking tokens


def summary_for(values: dict) -> dict:
    labels = evidence_labels()
    items = [
        {"id": f"e1.{kind}", "label": labels[kind], "value": value}
        for kind, value in values.items()
    ]
    return {"items": items, "previous_tactic": "lateral"}


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
    tokens_in, tokens_out = decision.input_tokens or 0, decision.output_tokens or 0
    record["actual_cost_usd"] = round(
        (tokens_in * INPUT_USD_PER_M + tokens_out * OUTPUT_USD_PER_M) / 1e6, 6
    )
    return record


def percentile(values: list[float], q: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    return ordered[min(len(ordered) - 1, round(q * (len(ordered) - 1)))]


def write_summary(path: Path, label: str, records: list[dict], repeats: int) -> None:
    valid = [r for r in records if r["source"] == "live" and r["reason"] is None]
    agree = [r for r in valid if r["tactic"] == r["intended"]]
    latencies = [r["latency_ms"] for r in valid if r["latency_ms"] is not None]
    tokens_in = sum(r["input_tokens"] or 0 for r in records)
    tokens_out = sum(r["output_tokens"] or 0 for r in records)
    cost = sum(r["actual_cost_usd"] for r in records)
    lines = [
        f"# Rival live suite: {label}",
        "",
        "**Evidence type: live.** Real calls to the deployed rival service.",
        "",
        "| Measure | Value |",
        "| --- | --- |",
        f"| Attempts | {len(records)} ({repeats} per case) |",
        f"| Valid live decisions | {len(valid)} of {len(records)} |",
        f"| Agree with the designer's intent | {len(agree)} of {len(valid)} valid |",
        f"| Latency p50 / p95 (valid) | {percentile(latencies, 0.5)} ms / "
        f"{percentile(latencies, 0.95)} ms |",
        f"| Tokens in / out | {tokens_in} / {tokens_out} |",
        f"| Estimated cost | USD {cost:.4f} at USD {INPUT_USD_PER_M} and {OUTPUT_USD_PER_M} "
        "per million tokens |",
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
        "summary and the catalogue. Prices are third-party-reported list rates, not a quote.",
    ]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("url")
    parser.add_argument("--label", required=True)
    parser.add_argument("--repeats", type=int, default=3)
    parser.add_argument("--max-attempts", type=int, default=18)
    args = parser.parse_args()
    suite = json.loads(HISTORIES.read_text(encoding="utf-8"))
    stamp = datetime.now(UTC).strftime("%Y-%m-%d")
    out = ROOT / "evidence" / "rival" / f"{stamp}-{args.label}"
    out.mkdir(parents=True, exist_ok=True)
    (out / "config.json").write_text(
        json.dumps(
            {
                "suite_version": suite["version"],
                "repeats": args.repeats,
                "max_attempts": args.max_attempts,
                "prices_usd_per_million": {"input": INPUT_USD_PER_M, "output": OUTPUT_USD_PER_M},
                "started_utc": datetime.now(UTC).isoformat(timespec="seconds"),
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    client = TacticClient(args.url)
    records: list[dict] = []
    for _ in range(args.repeats):
        for case in suite["cases"]:
            if len(records) >= args.max_attempts:
                break
            records.append(run_case(client, case))
            print(json.dumps(records[-1]))
    client.close()
    with (out / "results.jsonl").open("w", encoding="utf-8") as handle:
        for record in records:
            handle.write(json.dumps(record) + "\n")
    write_summary(out / "summary.md", args.label, records, args.repeats)
    print(f"wrote {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
