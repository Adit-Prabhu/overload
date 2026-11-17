"""Replays: a seed, the tuning and arena IDs, every tick's input and, for a campaign, the
protocol each encounter started with and the tick it started on. Playing one back must
reproduce the recorded final state hash exactly.

Recordings hold inputs and accepted protocols only. They contain no player identity.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

from overload.sim.arena import SUBSTATION, Arena, arena_id
from overload.sim.campaign import Campaign
from overload.sim.inputs import InputFrame
from overload.sim.run import Run
from overload.sim.tuning import DEFAULT, Tuning

FORMAT = "overload-replay"
VERSION = 3


@dataclass
class Recording:
    seed: int
    tuning_id: str
    arena_id: str
    frames: list[InputFrame] = field(default_factory=list)
    final_hash: str | None = None
    mode: str = "practice"
    protocols: list[str] = field(default_factory=list)  # one per encounter, in order
    starts: list[int] = field(default_factory=list)  # frame index of each begin_next

    def begin_next(self, protocol: str) -> None:
        """Note that the next encounter starts here, before the next recorded frame."""
        self.protocols.append(protocol)
        self.starts.append(len(self.frames))

    def save(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "format": FORMAT,
            "version": VERSION,
            "seed": self.seed,
            "tuning_id": self.tuning_id,
            "arena_id": self.arena_id,
            "final_hash": self.final_hash,
            "mode": self.mode,
            "protocols": self.protocols,
            "starts": self.starts,
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
            mode=payload["mode"],
            protocols=list(payload["protocols"]),
            starts=list(payload["starts"]),
        )


def play(
    recording: Recording, tuning: Tuning = DEFAULT, arena: Arena = SUBSTATION
) -> Run | Campaign:
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
    if recording.mode == "practice":
        run = Run(recording.seed, tuning, arena)
        for frame in recording.frames:
            run.step(frame)
        return run
    if recording.mode != "campaign" or not recording.protocols:
        raise ValueError(f"cannot replay mode {recording.mode!r}")
    if len(recording.starts) != len(recording.protocols) - 1:
        raise ValueError("a campaign recording needs one start per encounter after the first")
    campaign = Campaign(recording.seed, recording.protocols[0], tuning, arena)
    starts = dict(zip(recording.starts, recording.protocols[1:], strict=True))
    for index, frame in enumerate(recording.frames):
        if index in starts:
            campaign.begin_next(starts[index])
        campaign.step(frame)
    if len(recording.frames) in starts:
        campaign.begin_next(starts[len(recording.frames)])
    return campaign
