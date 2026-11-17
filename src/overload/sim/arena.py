"""The arena: the substation hall from overload.rooms, as collision geometry.

Positions are in room pixels (16 per tile). A character's position is the center of its
body, so in the 3/4 view its head can overlap a wall face above it, as in classic top-down
games. Walls and prop footprints are solid. Props also block shots, so they work as cover.
"""

from __future__ import annotations

from dataclasses import dataclass

from overload.rooms import PROPS, SUBSTATION_HALL, TILE, Room
from overload.sim.geometry import Point, Rect, circle_hits_rect


@dataclass(frozen=True)
class Arena:
    room: Room
    size: tuple[int, int]
    bounds: Rect
    obstacles: tuple[Rect, ...]
    player_spawn: Point
    practice_spawns: tuple[Point, ...]


def wall_rects(room: Room) -> list[Rect]:
    """Wall tiles merged into horizontal runs, then runs merged down when they line up."""
    runs: list[list[int]] = []  # [x, y, width, height] in tiles
    for y, row in enumerate(room.terrain):
        x = 0
        while x < len(row):
            if row[x] != "#":
                x += 1
                continue
            start = x
            while x < len(row) and row[x] == "#":
                x += 1
            for run in runs:
                if run[0] == start and run[2] == x - start and run[1] + run[3] == y:
                    run[3] += 1
                    break
            else:
                runs.append([start, y, x - start, 1])
    return [
        (float(x * TILE), float(y * TILE), float(w * TILE), float(h * TILE)) for x, y, w, h in runs
    ]


def prop_rects(room: Room) -> list[Rect]:
    """Prop footprints, inset 1 px so characters can slip past neighbors."""
    rects = []
    for y, row in enumerate(room.decor):
        for x, char in enumerate(row):
            if char in PROPS:
                size = 2 if char == "T" else 1
                rects.append((x * TILE + 1.0, y * TILE + 1.0, size * TILE - 2.0, size * TILE - 2.0))
    return rects


def from_room(
    room: Room, player_tile: tuple[int, int], practice_tiles: tuple[tuple[int, int], ...]
) -> Arena:
    w, h = room.size
    obstacles = tuple(wall_rects(room) + prop_rects(room))

    def center(tile: tuple[int, int]) -> Point:
        point = (tile[0] * TILE + TILE / 2, tile[1] * TILE + TILE / 2)
        if any(circle_hits_rect(point, 6.0, rect) for rect in obstacles):
            raise ValueError(f"{room.name}: spawn tile {tile} is blocked")
        return point

    return Arena(
        room=room,
        size=(w, h),
        bounds=(0.0, 0.0, float(w), float(h)),
        obstacles=obstacles,
        player_spawn=center(player_tile),
        practice_spawns=tuple(center(tile) for tile in practice_tiles),
    )


SUBSTATION = from_room(SUBSTATION_HALL, player_tile=(8, 10), practice_tiles=((19, 4), (17, 11)))
