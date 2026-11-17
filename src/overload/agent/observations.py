"""What the Regulator saw: the only game data that ever reaches the model.

ObservationLog never receives the World. The caller hands it visible facts only: where the
Surge and the Regulator stand, and the Surge's visible actions. Hidden state (charge,
cooldowns, inventory, RNG, other entities) cannot reach the summary by construction.
"""

from __future__ import annotations

import json
import math
from collections.abc import Iterable
from functools import cache

from overload.paths import ROOT

EVIDENCE_PATH = ROOT / "config" / "evidence.json"


@cache
def evidence_labels() -> dict[str, str]:
    """Observation kinds shared with the rival service (config/evidence.json)."""
    return json.loads(EVIDENCE_PATH.read_text(encoding="utf-8"))["kinds"]


NEAR = 40.0  # px, about 2.5 tiles
FAR = 104.0  # px, about 6.5 tiles
VISIBLE_ACTIONS = ("shot", "dodge")
TICKS_PER_MINUTE = 60 * 60


class ObservationLog:
    def __init__(self, encounter: int) -> None:
        if not 1 <= encounter <= 9:
            raise ValueError("encounter must be a single digit")
        self.encounter = encounter
        self.ticks = 0
        self.bands = {"near": 0, "mid": 0, "far": 0}
        self.actions = dict.fromkeys(VISIBLE_ACTIONS, 0)

    def observe(
        self, surge: tuple[float, float], rival: tuple[float, float], actions: Iterable[str]
    ) -> None:
        """Record one tick of what the rival could see."""
        self.ticks += 1
        distance = math.dist(surge, rival)
        band = "near" if distance < NEAR else "far" if distance > FAR else "mid"
        self.bands[band] += 1
        for action in actions:
            if action in self.actions:
                self.actions[action] += 1

    def summary(self, previous_tactic: str) -> dict:
        """The request summary: evidence items with stable IDs, at most a few hundred bytes."""
        e = f"e{self.encounter}"
        total = max(1, self.ticks)
        minutes = max(total / TICKS_PER_MINUTE, 1 / 60)
        values = {
            "far_share": round(self.bands["far"] / total, 2),
            "mid_share": round(self.bands["mid"] / total, 2),
            "near_share": round(self.bands["near"] / total, 2),
            "shots_per_minute": round(self.actions["shot"] / minutes, 1),
            "dodges": self.actions["dodge"],
        }
        labels = evidence_labels()
        items = [
            {"id": f"{e}.{kind}", "label": labels[kind], "value": value}
            for kind, value in values.items()
        ]
        return {"items": items, "previous_tactic": previous_tactic}


def observe_world(log: ObservationLog, world, rival: tuple[float, float]) -> None:
    """The one place the World is read for the rival: the Surge's position and the kinds of
    visible events this tick. Nothing else from the World is passed on."""
    log.observe((world.player.x, world.player.y), rival, (event.kind for event in world.events))
