"""Smoke-test a running rival service from the game's real client and selector.

Usage: uv run python tools/rival/smoke.py URL [--expect-timeout] [--deadline SECONDS]

Starts two sessions, sends one long-range and one close-range summary, checks that each
session gets its own answer, that a third request is refused, and prints every decision as
JSON lines. With --expect-timeout (run against a service started with a provider delay
above 5 s, or with a --deadline shorter than the service's reply time) it checks that the
game falls back to the neutral tactic at the deadline.
Results are only as live as the service: against the fixture provider they are fixture
evidence, never model evidence.
"""

from __future__ import annotations

import json
import sys
import time
from dataclasses import asdict

from overload.agent.client import TacticClient, Transport, urllib_transport
from overload.agent.observations import ObservationLog
from overload.agent.selector import LiveSelector
from overload.agent.tactics import Decision


def summary(distance: float, encounter: int = 1, previous_tactic: str = "lateral") -> dict:
    log = ObservationLog(encounter)
    for tick in range(600):
        log.observe((0.0, 0.0), (distance, 0.0), ["shot"] if tick % 10 == 0 else [])
    return log.summary(previous_tactic)


def wait(selector: LiveSelector, encounter: int) -> Decision:
    while (decision := selector.poll(encounter)) is None:
        time.sleep(0.02)
    return decision


def run_smoke(
    base: str,
    *,
    expect_timeout: bool = False,
    deadline: float = 5.0,
    transport: Transport = urllib_transport,
) -> dict[str, Decision]:
    client = TacticClient(base, transport=transport, deadline=deadline)
    try:
        far_player = LiveSelector(client, client.start_session())
        near_player = LiveSelector(client, client.start_session())
        assert far_player.session_id and near_player.session_id, "could not start sessions"
        assert far_player.session_id != near_player.session_id
        if expect_timeout:
            far_player.warm()
        else:
            warm_status, warm_body = client.transport(
                "POST",
                f"{client.base_url}/sessions/{far_player.session_id}/warmup",
                None,
                min(3.0, deadline),
            )
            assert (
                warm_status == 200 and isinstance(warm_body, dict) and warm_body.get("ok") is True
            ), (warm_status, warm_body)
        near_player.warm()
        far_player.prepare(2, summary(200.0, encounter=1))
        near_player.prepare(2, summary(10.0, encounter=1))
        results = {"far": wait(far_player, 2), "near": wait(near_player, 2)}
        far_player.prepare(3, summary(200.0, encounter=2, previous_tactic=results["far"].tactic))
        results["far_3"] = wait(far_player, 3)
        far_player.prepare(4, summary(200.0, encounter=3, previous_tactic=results["far_3"].tactic))
        results["far_4"] = wait(far_player, 4)
        for name, decision in results.items():
            print(json.dumps({"case": name, **asdict(decision)}))
        if expect_timeout:
            # The service gives up at 4.5 s and reports a timeout, or the game's own 5 s deadline
            # fires first. Either way every fight starts on the neutral tactic.
            for name in ("far", "near", "far_3"):
                assert results[name].source == "fallback", results[name]
                assert results[name].reason in ("timeout", "late", "service_timeout"), results[name]
                assert results[name].tactic == "lateral", results[name]
        else:
            for name in ("far", "near", "far_3"):
                assert results[name].reason is None, results[name]
                assert bool(results[name].evidence_ids), results[name]
            if results["far"].source == "fixture":
                # The fixture is a fixed rule, so its answers are known exactly.
                for name in ("far", "near", "far_3"):
                    assert results[name].source == "fixture", results[name]
                assert results["far"].tactic == "pressure", results["far"]
                assert results["near"].tactic == "spacing", results["near"]
                assert results["far_3"].tactic == "pressure", results["far_3"]
            else:
                # A live model may choose differently. It must give valid, cited answers.
                for name in ("far", "near", "far_3"):
                    assert results[name].source == "live", results[name]
                    assert bool(results[name].evidence_ids), results[name]
        assert results["far_4"].source == "fallback", results["far_4"]
        assert results["far_4"].reason == "request_cap", results["far_4"]
        assert results["far_4"].tactic == "lateral", results["far_4"]
        return results
    finally:
        client.close()


def main(argv: list[str]) -> int:
    base = argv[1]
    expect_timeout = "--expect-timeout" in argv
    deadline = float(argv[argv.index("--deadline") + 1]) if "--deadline" in argv else 5.0
    run_smoke(base, expect_timeout=expect_timeout, deadline=deadline)
    print("smoke passed")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
