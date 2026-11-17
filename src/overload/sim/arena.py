"""The substation floor: one arena reused for every encounter."""

from __future__ import annotations

from dataclasses import dataclass

from overload.sim.geometry import Point, Rect


@dataclass(frozen=True)
class Arena:
    size: tuple[int, int]
    bounds: Rect
    obstacles: tuple[Rect, ...]
    player_spawn: Point
    practice_spawns: tuple[Point, ...]


SUBSTATION = Arena(
    size=(1280, 720),
    bounds=(16.0, 16.0, 1248.0, 688.0),
    obstacles=(
        (250.0, 140.0, 36.0, 140.0),
        (994.0, 140.0, 36.0, 140.0),
        (250.0, 440.0, 36.0, 140.0),
        (994.0, 440.0, 36.0, 140.0),
        (560.0, 92.0, 160.0, 32.0),
    ),
    player_spawn=(400.0, 360.0),
    practice_spawns=((880.0, 250.0), (880.0, 470.0)),
)
