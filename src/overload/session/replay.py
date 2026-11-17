"""Replays: a seed, the tuning ID and every tick's input. Playing one back must reproduce
the recorded final state hash exactly.

Recordings hold inputs only. They contain no player identity.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

from overload.sim.arena import SUBSTATION, Arena, arena_id
from overload.sim.inputs import InputFrame
from overload.sim.run import Run
from overload.sim.tuning import DEFAULT, Tuning

FORMAT = "overload-replay"
VERSION = 2


@dataclass
class Recording:
    seed: int
    tuning_id: str
    arena_id: str
    frames: list[InputFrame] = field(default_factory=list)
    final_hash: str | None = None

    def save(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "format": FORMAT,
            "version": VERSION,
            "seed": self.seed,
            "tuning_id": self.tuning_id,
            "arena_id": self.arena_id,
            "final_hash": self.final_hash,
            "frames": [frame.to_list() for frame in self.frames],
        }
        path.write_text(json.dumps(payload, separators=(",", ":")), encoding="utf-8")

    @classmethod
    def load(cls, path: Path) -> Recording:
        payload = json.loads(path.read_text(encoding="utf-8"))
        if payload.get("format") != FORMAT or payload.get("version") != VERSION:
            raise ValueError(f"{path} is not an {FORMAT} v{VERSION} file")
        return cls(
            seed=payload["seed"],
            tuning_id=payload["tuning_id"],
            arena_id=payload["arena_id"],
            frames=[InputFrame.from_list(values) for values in payload["frames"]],
            final_hash=payload.get("final_hash"),
        )


def play(recording: Recording, tuning: Tuning = DEFAULT, arena: Arena = SUBSTATION) -> Run:
    """Re-run a recording from scratch. Refuses a recording made with a different tuning or
    a different arena."""
    if recording.tuning_id != tuning.tuning_id():
        raise ValueError(
            f"recording uses tuning {recording.tuning_id}, this build is {tuning.tuning_id()}"
        )
    if recording.arena_id != arena_id(arena):
        raise ValueError(
            f"recording uses arena {recording.arena_id}, this build is {arena_id(arena)}"
        )
    run = Run(recording.seed, tuning, arena)
    for frame in recording.frames:
        run.step(frame)
    return run
