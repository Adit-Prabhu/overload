"""The live suite tool's pure parts: summaries match the service schema, and the report math."""

import importlib.util
import json
import re

from overload.paths import ROOT

spec = importlib.util.spec_from_file_location(
    "live_suite", ROOT / "tools" / "rival" / "live_suite.py"
)
live_suite = importlib.util.module_from_spec(spec)
spec.loader.exec_module(live_suite)


def test_authored_histories_use_only_allowed_kinds() -> None:
    suite = json.loads(live_suite.HISTORIES.read_text(encoding="utf-8"))
    tactics = {
        t["id"] for t in json.loads((ROOT / "config" / "tactics.json").read_text())["tactics"]
    }
    assert len(suite["cases"]) == 6
    for case in suite["cases"]:
        assert case["intended"] in tactics
        summary = live_suite.summary_for(case["values"])
        for item in summary["items"]:
            assert re.fullmatch(r"e1\.[a-z_]+", item["id"])
            assert 1 <= len(item["label"]) <= 80


def test_percentile_is_nearest_rank() -> None:
    assert live_suite.percentile([], 0.95) is None
    assert live_suite.percentile([3, 1, 2], 0.5) == 2
    assert live_suite.percentile(list(range(1, 21)), 0.95) == 19
    eighteen = list(range(1, 19))
    assert live_suite.percentile(eighteen, 0.95) == 18, "ceil(0.95 x 18) = 18th value"
    assert live_suite.percentile(eighteen, 0.5) == 9


def test_summary_counts_fallbacks_agreement_and_old_cost_field(tmp_path) -> None:
    base = {
        "source": "live",
        "reason": None,
        "latency_ms": 1000,
        "input_tokens": 400,
        "output_tokens": 40,
        "evidence_ids": ["e1.far_share"],
    }
    records = [
        {**base, "case": "far_heavy", "intended": "pressure", "tactic": "pressure"},
        {**base, "case": "far_heavy", "intended": "pressure", "tactic": "spacing"},
        {
            **base,
            "case": "near_heavy",
            "intended": "spacing",
            "tactic": "lateral",
            "source": "fallback",
            "reason": "timeout",
            "evidence_ids": [],
            "input_tokens": None,
            "output_tokens": None,
        },
    ]
    path = tmp_path / "summary.md"
    live_suite.write_summary(path, "test", records)
    text = path.read_text()
    assert "| Attempts | 3 (1 to 2 per case) |" in text
    assert "| Valid live decisions | 2 of 3 |" in text
    assert "| Agree with the designer's intent | 1 of 2 valid |" in text
    assert "fallback (timeout)" in text
    assert "USD 0.0004" in text


def test_a_run_never_exceeds_the_attempt_ceiling(tmp_path, monkeypatch) -> None:
    calls = []

    def fake_case(client, case):
        calls.append(case["id"])
        return {
            "case": case["id"],
            "intended": case["intended"],
            "tactic": "lateral",
            "source": "live",
            "reason": None,
            "latency_ms": 10,
            "input_tokens": 1,
            "output_tokens": 1,
            "evidence_ids": [],
            "est_cost_usd": 0.0,
        }

    monkeypatch.setattr(live_suite, "run_case", fake_case)
    monkeypatch.setattr(live_suite, "ROOT", tmp_path)
    monkeypatch.setattr(live_suite, "prompt_hash", lambda: "test")
    monkeypatch.setattr(live_suite, "git_commit", lambda: "test")
    monkeypatch.setattr(
        "sys.argv",
        [
            "live_suite",
            "http://rival.test",
            "--label",
            "cap",
            "--worker-version",
            "test",
            "--repeats",
            "10",
        ],
    )
    live_suite.main()
    assert len(calls) == live_suite.MAX_ATTEMPTS
    results = next(tmp_path.glob("evidence/rival/*-cap/results.jsonl"))
    assert len(results.read_text().splitlines()) == live_suite.MAX_ATTEMPTS
