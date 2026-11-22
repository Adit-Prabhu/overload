"""Replays: a seed, the tuning and arena IDs, every tick's input and, for a campaign, the
protocol each encounter started with and the tick it started on. Playing one back must
reproduce the recorded final state hash exactly.

Recordings hold inputs and accepted protocols only. They contain no player identity.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

from overload.sim.arena import FLOOR_ARENA, SUBSTATION, Arena, arena_id
from overload.sim.campaign import ENCOUNTERS, NEUTRAL, Campaign
from overload.sim.difficulty import PRESETS
from overload.sim.inputs import InputFrame
from overload.sim.run import Run
from overload.sim.tuning import DEFAULT, Tuning
from overload.sim.world import PROTOCOLS

FORMAT = "overload-replay"
VERSION = 4
MENU_OPS = ("equip", "fuse")


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
    menu: list[list] = field(default_factory=list)  # [frame index, op, arg, arg] Fuse Box actions

    def begin_next(self, protocol: str) -> None:
        """Note that the next encounter starts here, before the next recorded frame."""
        self.protocols.append(protocol)
        self.starts.append(len(self.frames))

    def fuse_box(self, op: str, a: int | str, b: str) -> None:
        """Note a Fuse Box action (equip slot ability, or fuse power power) made here. Menu
        actions at a frame index happen before an encounter start at the same index."""
        self.menu.append([len(self.frames), op, a, b])

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
            "menu": self.menu,
            "frames": [frame.to_list() for frame in self.frames],
        }
        path.write_text(json.dumps(payload, separators=(",", ":")), encoding="utf-8")

    @classmethod
    def load(cls, path: Path) -> Recording:
        payload = json.loads(path.read_text(encoding="utf-8"))
        if (
            not isinstance(payload, dict)
            or payload.get("format") != FORMAT
            or payload.get("version") != VERSION
        ):
            raise ValueError(f"{path} is not an {FORMAT} v{VERSION} file")
        try:
            seed = payload["seed"]
            tuning_id = payload["tuning_id"]
            arena = payload["arena_id"]
            raw_frames = payload["frames"]
            mode = payload["mode"]
            raw_protocols = payload["protocols"]
            raw_starts = payload["starts"]
            raw_menu = payload["menu"]
        except KeyError as error:
            raise ValueError(f"{path} is missing field {error.args[0]!r}") from error
        if not _is_int(seed) or not isinstance(tuning_id, str) or not isinstance(arena, str):
            raise ValueError(f"{path} has malformed header fields")
        if not isinstance(mode, str):
            raise ValueError(f"{path} has malformed mode")
        if not all(
            isinstance(seq, list) for seq in (raw_frames, raw_protocols, raw_starts, raw_menu)
        ):
            raise ValueError(f"{path} has malformed replay lists")
        final_hash = payload.get("final_hash")
        if final_hash is not None and not isinstance(final_hash, str):
            raise ValueError(f"{path} has malformed final_hash")
        try:
            frames = [InputFrame.from_list(values) for values in raw_frames]
        except (TypeError, ValueError, IndexError) as error:
            raise ValueError(f"{path} has malformed input frame: {error}") from error
        return cls(
            seed=seed,
            tuning_id=tuning_id,
            arena_id=arena,
            frames=frames,
            final_hash=final_hash,
            mode=mode,
            protocols=list(raw_protocols),
            starts=list(raw_starts),
            menu=list(raw_menu),
        )


def check_campaign(recording: Recording) -> None:
    """Reject campaign recordings that could not have come from a real session."""
    if recording.mode != "campaign":
        raise ValueError(f"cannot replay mode {recording.mode!r}")
    if not recording.protocols or recording.protocols[0] != NEUTRAL:
        raise ValueError("a campaign recording starts with the neutral protocol")
    if len(recording.protocols) > ENCOUNTERS:
        raise ValueError(f"a campaign recording has at most {ENCOUNTERS} encounters")
    for protocol in recording.protocols[1:]:
        if not isinstance(protocol, str) or protocol not in PROTOCOLS:
            raise ValueError(f"unknown protocol {protocol!r}")
    if len(recording.starts) != len(recording.protocols) - 1:
        raise ValueError("a campaign recording needs one start per encounter after the first")
    if any(not _is_int(start) for start in recording.starts):
        raise ValueError("encounter starts must be integers")
    bounds = [0, *recording.starts]
    if any(b <= a for a, b in zip(bounds, bounds[1:], strict=False)):
        raise ValueError("encounter starts must be positive and strictly increasing")
    if recording.starts and recording.starts[-1] > len(recording.frames):
        raise ValueError("an encounter start lies beyond the recorded frames")
    previous = 0
    for entry in recording.menu:
        if not _well_formed(entry):
            raise ValueError(f"malformed Fuse Box action {entry!r}")
        if not previous <= entry[0] <= len(recording.frames):
            raise ValueError("Fuse Box actions must be in order and within the recorded frames")
        previous = entry[0]


def _is_int(value: object) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def _well_formed(entry: object) -> bool:
    """[frame, "equip", slot, ability] or [frame, "fuse", power, power], exact types only."""
    if not isinstance(entry, list) or len(entry) != 4 or not _is_int(entry[0]):
        return False
    _, op, a, b = entry
    if op == "equip":
        return _is_int(a) and isinstance(b, str)
    return op == "fuse" and isinstance(a, str) and isinstance(b, str)


def menu_by_frame(recording: Recording) -> dict[int, list[list]]:
    grouped: dict[int, list[list]] = {}
    for entry in recording.menu:
        grouped.setdefault(entry[0], []).append(entry)
    return grouped


def apply_menu(campaign: Campaign, entry: list) -> None:
    """Replay one loadout action (Fuse Box or the paused menu). Invalid choices replay as the
    same harmless no-op they were when recorded. An action while the Surge is down or after
    the ending means the recording is corrupt."""
    if not _well_formed(entry):
        raise ValueError(f"malformed Fuse Box action {entry!r}")
    index, op, a, b = entry
    try:
        if op == "equip":
            campaign.equip(a, b)
        else:
            campaign.fuse(a, b)
    except RuntimeError as error:
        raise ValueError(
            f"loadout action at tick {index} while the loadout cannot change"
        ) from error


def recorded_tuning(tuning_id: str) -> Tuning:
    """Resolve a shipped preset by hash for both old and new recordings."""
    for preset in PRESETS.values():
        if preset.tuning_id() == tuning_id:
            return preset
    raise ValueError(f"recording uses tuning {tuning_id}, this build is {DEFAULT.tuning_id()}")


def play(
    recording: Recording, tuning: Tuning | None = None, arena: Arena | None = None
) -> Run | Campaign:
    """Re-run a recording from scratch. Practice runs use the hall, campaigns the floor.
    Refuses a recording made with a different tuning or a different arena."""
    if arena is None:
        arena = SUBSTATION if recording.mode == "practice" else FLOOR_ARENA
    if tuning is None:
        tuning = recorded_tuning(recording.tuning_id)
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
    check_campaign(recording)
    campaign = Campaign(recording.seed, tuning, arena)
    starts = dict(zip(recording.starts, recording.protocols[1:], strict=True))
    menu = menu_by_frame(recording)
    for index in range(len(recording.frames) + 1):
        for action in menu.get(index, []):
            apply_menu(campaign, action)
        if index in starts:
            try:
                campaign.begin_next(starts[index])
            except RuntimeError as error:
                raise ValueError(
                    f"encounter start at tick {index} is not in the Fuse Box"
                ) from error
        if index < len(recording.frames):
            campaign.step(recording.frames[index])
    return campaign
