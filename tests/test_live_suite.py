"""The live suite tool's pure parts: summaries match the service schema, and the report math."""

import importlib.util
import json
import math
import re

import pytest

from overload.paths import ROOT

spec = importlib.util.spec_from_file_location(
    "live_suite", ROOT / "tools" / "rival" / "live_suite.py"
)
live_suite = importlib.util.module_from_spec(spec)
spec.loader.exec_module(live_suite)


def test_authored_histories_use_only_allowed_kinds() -> None:
    suite = json.loads(live_suite.HISTORIES.read_text(encoding="utf-8"))
    evidence = json.loads((ROOT / "config" / "evidence.json").read_text(encoding="utf-8"))
    allowed_kinds = set(evidence["kinds"])
    tactics = {
        t["id"] for t in json.loads((ROOT / "config" / "tactics.json").read_text())["tactics"]
    }
    assert suite["version"] == 2
    assert len(suite["cases"]) == 6
    assert len({case["id"] for case in suite["cases"]}) == len(suite["cases"])
    assert {case["intended"] for case in suite["cases"]} == tactics
    for case in suite["cases"]:
        assert case["intended"] in tactics
        assert set(case["values"]) == allowed_kinds, case["id"]
        for kind, value in case["values"].items():
            assert not isinstance(value, bool) and isinstance(value, int | float), (
                case["id"],
                kind,
            )
            assert math.isfinite(value) and value >= 0, (case["id"], kind)
            if kind.endswith("_share"):
                assert 0.0 <= value <= 1.0, (case["id"], kind)
        shares = case["values"]["far_share"] + case["values"]["mid_share"]
        shares += case["values"]["near_share"]
        assert abs(shares - 1.0) < 1e-6, case["id"]
        summary = live_suite.summary_for(case["values"])
        assert len(summary["items"]) <= 12
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


def test_summary_distinguishes_fixture_mixed_empty_and_models(tmp_path) -> None:
    fixture_records = [
        {
            "case": "far_heavy",
            "intended": "pressure",
            "tactic": "pressure",
            "source": "fixture",
            "reason": None,
            "latency_ms": 5,
            "model": "fixture-rule-v1",
            "input_tokens": 500,
            "output_tokens": 30,
            "evidence_ids": ["e1.far_share"],
        },
    ]
    fixture_path = tmp_path / "fixture.md"
    live_suite.write_summary(fixture_path, "local", fixture_records)
    fixture_text = fixture_path.read_text(encoding="utf-8")
    assert "**Evidence type: fixture.**" in fixture_text
    assert "**Evidence type: live.**" not in fixture_text
    assert "| Model(s) observed | fixture-rule-v1 |" in fixture_text
    assert "| Valid live decisions | 0 of 1 |" in fixture_text
    assert "| Fixture decisions (excluded from live metrics) | 1 of 1 |" in fixture_text
    assert "| Tokens in / out | 0 / 0 |" in fixture_text
    assert "| Estimated cost | USD 0.0000" in fixture_text
    assert "pressure (fixture)" in fixture_text

    mixed_records = [
        {
            "case": "far_heavy",
            "intended": "pressure",
            "tactic": "pressure",
            "source": "live",
            "reason": None,
            "latency_ms": 900,
            "model": "gemini-3.5-flash-lite-001",
            "input_tokens": 400,
            "output_tokens": 40,
            "evidence_ids": ["e1.far_share"],
        },
        *fixture_records,
    ]
    mixed_path = tmp_path / "mixed.md"
    live_suite.write_summary(mixed_path, "mix", mixed_records)
    mixed_text = mixed_path.read_text(encoding="utf-8")
    assert "**Evidence type: mixed (live and fixture).**" in mixed_text
    assert "Warning:" in mixed_text
    assert "| Model(s) observed | fixture-rule-v1, gemini-3.5-flash-lite-001 |" in mixed_text
    assert "| Valid live decisions | 1 of 2 |" in mixed_text
    assert "| Tokens in / out | 400 / 40 |" in mixed_text
    assert "pressure, pressure (fixture)" in mixed_text

    empty_path = tmp_path / "empty.md"
    live_suite.write_summary(empty_path, "empty", [])
    empty_text = empty_path.read_text(encoding="utf-8")
    assert "**Evidence type: none.**" in empty_text
    assert "| Model(s) observed | none |" in empty_text
    assert "| Attempts | 0 (0 per case) |" in empty_text
    assert "| Latency p50 / p95, nearest rank (valid) | n/a |" in empty_text
    assert "No attempts recorded." in empty_text


def test_rerun_with_same_label_refuses_without_overwrite_and_replaces_with_it(
    tmp_path, monkeypatch, capsys
) -> None:
    def fake_case(client, case):
        return {
            "case": case["id"],
            "intended": case["intended"],
            "tactic": "pressure",
            "source": "live",
            "reason": None,
            "latency_ms": 100,
            "model": "gemini-3.5-flash-lite-001",
            "input_tokens": 100,
            "output_tokens": 10,
            "evidence_ids": ["e1.far_share"],
            "est_cost_usd": 0.000055,
        }

    monkeypatch.setattr(live_suite, "run_case", fake_case)
    monkeypatch.setattr(live_suite, "ROOT", tmp_path)
    monkeypatch.setattr(live_suite, "prompt_hash", lambda: "test")
    monkeypatch.setattr(live_suite, "git_commit", lambda: "test")

    base_argv = [
        "live_suite",
        "http://rival.test",
        "--label",
        "dup",
        "--worker-version",
        "v1",
        "--repeats",
        "1",
    ]
    monkeypatch.setattr("sys.argv", base_argv)
    assert live_suite.main() == 0
    run_dir = next(tmp_path.glob("evidence/rival/*-dup"))
    results_file = run_dir / "results.jsonl"
    config_file = run_dir / "config.json"
    assert len(results_file.read_text(encoding="utf-8").splitlines()) == 6
    assert json.loads(config_file.read_text(encoding="utf-8"))["worker_version"] == "v1"

    # Re-running the same label on the same UTC date without --overwrite refuses cleanly.
    monkeypatch.setattr(
        "sys.argv",
        [*base_argv[:4], "--worker-version", "v2", "--repeats", "1"],
    )
    with pytest.raises(SystemExit) as excinfo:
        live_suite.main()
    assert excinfo.value.code == 2
    assert "--overwrite" in capsys.readouterr().err
    assert len(results_file.read_text(encoding="utf-8").splitlines()) == 6
    assert json.loads(config_file.read_text(encoding="utf-8"))["worker_version"] == "v1"

    # With --overwrite, previous results are replaced cleanly instead of concatenated.
    monkeypatch.setattr(
        "sys.argv",
        [*base_argv[:4], "--worker-version", "v2", "--repeats", "1", "--overwrite"],
    )
    assert live_suite.main() == 0
    assert len(results_file.read_text(encoding="utf-8").splitlines()) == 6
    assert json.loads(config_file.read_text(encoding="utf-8"))["worker_version"] == "v2"
    summary_text = (run_dir / "summary.md").read_text(encoding="utf-8")
    assert "| Model(s) observed | gemini-3.5-flash-lite-001 |" in summary_text

    # An empty pre-existing directory works without --overwrite, and --resummarize allows empty.
    empty_dir = run_dir.parent / run_dir.name.replace("-dup", "-fresh")
    empty_dir.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(
        "sys.argv",
        [
            "live_suite",
            "http://rival.test",
            "--label",
            "fresh",
            "--worker-version",
            "v2",
            "--repeats",
            "1",
        ],
    )
    assert live_suite.main() == 0

    resum_dir = tmp_path / "2026-11-22-empty-resum"
    resum_dir.mkdir()
    (resum_dir / "results.jsonl").write_text("", encoding="utf-8")
    monkeypatch.setattr("sys.argv", ["live_suite", "--resummarize", str(resum_dir)])
    assert live_suite.main() == 0
    assert "**Evidence type: none.**" in (resum_dir / "summary.md").read_text(encoding="utf-8")
