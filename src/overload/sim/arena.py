"""The arena: the substation hall from overload.rooms, as collision geometry.

Positions are in room pixels (16 per tile). A character's position is the center of its
body, so in the 3/4 view its head can overlap a wall face above it, as in classic top-down
games. Walls and prop footprints are solid. Props also block shots, so they work as cover.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field

from overload.floor import FLOOR, Floor, tile_rect_px
from overload.rooms import PROPS, SUBSTATION_HALL, TILE, Room, footprint_tiles
from overload.sim.collision import build_index
from overload.sim.geometry import Point, Rect, circle_hits_rect
from overload.sim.tuning import DEFAULT


@dataclass(frozen=True)
class Arena:
    room: Room
    size: tuple[int, int]
    bounds: Rect
    obstacles: tuple[Rect, ...]
    player_spawn: Point
    practice_spawns: tuple[Point, ...]
    rival_spawn: Point
    doors: tuple[tuple[str, Rect], ...] = ()  # door id and its rectangle, solid when locked
    index: dict = field(default_factory=dict, compare=False, hash=False, repr=False)

    def __post_init__(self) -> None:
        if not self.index:
            object.__setattr__(self, "index", build_index(self.obstacles))


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
                size = footprint_tiles(char)
                rects.append((x * TILE + 1.0, y * TILE + 1.0, size * TILE - 2.0, size * TILE - 2.0))
    return rects


def from_room(
    room: Room,
    player_tile: tuple[int, int],
    practice_tiles: tuple[tuple[int, int], ...],
    rival_tile: tuple[int, int],
) -> Arena:
    w, h = room.size
    obstacles = tuple(wall_rects(room) + prop_rects(room))
    clearance = max(DEFAULT.player_radius, DEFAULT.arc_mite_radius, DEFAULT.relay_radius)

    def center(tile: tuple[int, int]) -> Point:
        point = (tile[0] * TILE + TILE / 2, tile[1] * TILE + TILE / 2)
        if any(circle_hits_rect(point, clearance, rect) for rect in obstacles):
            raise ValueError(f"{room.name}: spawn tile {tile} is blocked")
        return point

    return Arena(
        room=room,
        size=(w, h),
        bounds=(0.0, 0.0, float(w), float(h)),
        obstacles=obstacles,
        player_spawn=center(player_tile),
        practice_spawns=tuple(center(tile) for tile in practice_tiles),
        rival_spawn=center(rival_tile),
    )


SUBSTATION = from_room(
    SUBSTATION_HALL, player_tile=(8, 10), practice_tiles=((19, 4), (17, 11)), rival_tile=(21, 9)
)


def from_floor(floor: Floor) -> Arena:
    """The whole substation floor as one arena. Doors are listed so they can lock. The
    player starts in sector 1's entry room. Robot and Regulator spawns belong to the rooms
    (overload.floor), so the practice and rival spawns here are only defaults."""
    room = floor.room
    w, h = room.size
    entry = floor.get("s1_entry")
    chamber = floor.get("s1_chamber")

    def center(tile: tuple[int, int]) -> Point:
        return (tile[0] * TILE + TILE / 2, tile[1] * TILE + TILE / 2)

    return Arena(
        room=room,
        size=(w, h),
        bounds=(0.0, 0.0, float(w), float(h)),
        obstacles=tuple(wall_rects(room) + prop_rects(room)),
        player_spawn=center(entry.center),
        practice_spawns=(),
        rival_spawn=center(chamber.center),
        doors=tuple((door.id, tile_rect_px(door.rect)) for door in floor.doors),
    )


FLOOR_ARENA = from_floor(FLOOR)


def arena_id(arena: Arena) -> str:
    """Short stable hash of the room and spawns. Replays record it, like the tuning ID, so a
    room edit is caught before playback instead of at the final hash."""
    blob = json.dumps(
        {
            "terrain": arena.room.terrain,
            "decor": arena.room.decor,
            "player": arena.player_spawn,
            "practice": arena.practice_spawns,
            "rival": arena.rival_spawn,
            "doors": arena.doors,
        },
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(blob.encode()).hexdigest()[:8]
