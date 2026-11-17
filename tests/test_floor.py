"""The hand-built floor (overhaul): every room is reachable, doors sit in the walls where
corridors meet them, the hidden room is reachable only through its secret wall, and the
collision index answers exactly like a check against every wall and prop."""

from __future__ import annotations

import random
from collections import deque

import pytest

from overload.floor import FLOOR, TILE
from overload.sim.arena import FLOOR_ARENA, SUBSTATION
from overload.sim.campaign import encounter_world
from overload.sim.collision import blocked
from overload.sim.geometry import circle_hits_rect
from overload.sim.world import move_body

ROOM = FLOOR.room


def walkable_from(start: tuple[int, int], closed: set[tuple[int, int]]) -> set[tuple[int, int]]:
    seen = {start}
    queue = deque([start])
    while queue:
        x, y = queue.popleft()
        for nx, ny in ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)):
            if (nx, ny) in seen or (nx, ny) in closed or ROOM.is_wall(nx, ny):
                continue
            seen.add((nx, ny))
            queue.append((nx, ny))
    return seen


def door_tiles(secret: bool) -> set[tuple[int, int]]:
    tiles = set()
    for door in FLOOR.doors:
        if door.secret == secret:
            x, y, w, h = door.rect
            tiles |= {(tx, ty) for tx in range(x, x + w) for ty in range(y, y + h)}
    return tiles


def test_every_room_is_reachable_and_the_hidden_room_only_through_its_secret_wall() -> None:
    start = FLOOR.get("s1_entry").center
    open_floor = walkable_from(start, closed=door_tiles(secret=True))
    for room in FLOOR.rooms:
        assert (room.center in open_floor) == (room.kind != "hidden"), room.id
    everything = walkable_from(start, closed=set())
    assert FLOOR.get("hidden").center in everything


def test_doors_are_wall_gaps_on_their_own_room() -> None:
    for door in FLOOR.doors:
        room = FLOOR.get(door.room)
        rx, ry, rw, rh = room.rect
        x, y, w, h = door.rect
        assert rx <= x and x + w <= rx + rw and ry <= y and y + h <= ry + rh, door.id
        inside = room.interior
        assert not (
            inside[0] <= x < inside[0] + inside[2] and inside[1] <= y < inside[1] + inside[3]
        )
        for tx in range(x, x + w):
            for ty in range(y, y + h):
                assert not ROOM.is_wall(tx, ty), f"{door.id} is not carved"
                assert ROOM.decor[ty][tx] == ".", f"{door.id} has decor in its gap"


def test_every_link_has_a_door_on_both_rooms() -> None:
    pairs = {(d.room, d.other) for d in FLOOR.doors}
    assert all((b, a) in pairs for a, b in pairs)
    assert len(FLOOR.doors) == 2 * 14


def test_room_centers_are_clear_for_spawning() -> None:
    for room in FLOOR.rooms:
        cx, cy = room.center
        point = (cx * TILE + TILE / 2, cy * TILE + TILE / 2)
        assert not blocked(None, FLOOR_ARENA, point, 8.0), room.id


@pytest.mark.parametrize("arena", [FLOOR_ARENA, SUBSTATION], ids=["floor", "hall"])
def test_the_collision_index_matches_a_check_against_everything(arena) -> None:
    rng = random.Random(7)
    w, h = arena.size
    for _ in range(4000):
        point = (rng.uniform(0, w), rng.uniform(0, h))
        radius = rng.choice((1.0, 3.0, 5.0, 7.0, 14.0))
        brute = any(circle_hits_rect(point, radius, rect) for rect in arena.obstacles)
        assert blocked(None, arena, point, radius) == brute


def test_a_locked_door_is_solid() -> None:
    world = encounter_world(1, 1, "lateral")
    door_id, (x, y, w, h) = FLOOR_ARENA.doors[0]
    center = (x + w / 2, y + h / 2)
    assert not blocked(world, FLOOR_ARENA, center, 2.0)
    world.locked = [door_id]
    assert blocked(world, FLOOR_ARENA, center, 2.0)
    moved = move_body(center[0], center[1], 0.0, 0.0, 5.0, FLOOR_ARENA, world)
    assert moved != center, "a body inside a door that shuts is pushed out"
