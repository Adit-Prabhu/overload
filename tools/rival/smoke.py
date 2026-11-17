"""Smoke-test a running rival service from the game's real client and selector.

Usage: uv run python tools/rival/smoke.py http://127.0.0.1:8787 [--expect-timeout]

Starts two sessions, sends one long-range and one close-range summary, checks that each
session gets its own answer, that a third request is refused, and prints every decision as
JSON lines. With --expect-timeout (run against a service started with a provider delay
above 5 s) it checks that the game falls back to the neutral tactic at the deadline.
Results are only as live as the service: against the fixture provider they are fixture
evidence, never model evidence.
"""

from __future__ import annotations

import json
import sys
import time
from dataclasses import asdict

from overload.agent.client import TacticClient
from overload.agent.observations import ObservationLog
from overload.agent.selector import LiveSelector


def summary(distance: float) -> dict:
    log = ObservationLog(1)
    for tick in range(600):
        log.observe((0.0, 0.0), (distance, 0.0), ["shot"] if tick % 10 == 0 else [])
    return log.summary("lateral")


def wait(selector: LiveSelector, encounter: int):
    while (decision := selector.poll(encounter)) is None:
        time.sleep(0.02)
    return decision


def main(argv: list[str]) -> int:
    base = argv[1]
    expect_timeout = "--expect-timeout" in argv
    client = TacticClient(base)
    far_player = LiveSelector(client, client.start_session())
    near_player = LiveSelector(client, client.start_session())
    assert far_player.session_id and near_player.session_id, "could not start sessions"
    assert far_player.session_id != near_player.session_id
    far_player.prepare(2, summary(200.0))
    near_player.prepare(2, summary(10.0))
    results = {"far": wait(far_player, 2), "near": wait(near_player, 2)}
    far_player.prepare(3, summary(200.0))
    results["far_3"] = wait(far_player, 3)
    far_player.prepare(4, summary(200.0))
    results["far_4"] = wait(far_player, 4)
    for name, decision in results.items():
        print(json.dumps({"case": name, **asdict(decision)}))
    if expect_timeout:
        # The service gives up at 4.5 s and reports a timeout, or the game's own 5 s deadline
        # fires first. Either way the fight starts on the neutral tactic.
        assert results["far"].reason in ("timeout", "service_timeout"), results["far"]
        assert results["far"].tactic == "lateral"
    else:
        assert results["far"].tactic == "pressure", results["far"]
        assert results["near"].tactic == "spacing", results["near"]
    assert results["far_4"].reason == "request_cap", results["far_4"]
    client.close()
    print("smoke passed")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
