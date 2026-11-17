"""Rooms on the floor (overhaul): a combat room locks its doors when the Surge steps in,
robots warp in wave by wave after a visible marker, and the doors open for good once the
last robot is down. A chamber locks and boots the Regulator in the sector's protocol. A
secret wall cracks open after a few shots. Deterministic, no pygame.
"""

from __future__ import annotations

from overload.floor import TILE, WAVES, Floor, FloorRoom
from overload.sim.geometry import circle_hits_rect
from overload.sim.powers import absorb_charges
from overload.sim.spawns import spawn_rival, spawn_robot
from overload.sim.state import Event, Warp, World
from overload.sim.tuning import Tuning


def tile_center(tile: tuple[int, int]) -> tuple[float, float]:
    return (tile[0] * TILE + TILE / 2, tile[1] * TILE + TILE / 2)


def room_of(floor: Floor, x: float, y: float, margin: int = 0) -> FloorRoom | None:
    """The room whose interior holds this point, at least `margin` tiles in from its walls."""
    tx, ty = int(x // TILE), int(y // TILE)
    for room in floor.rooms:
        rx, ry, rw, rh = room.interior
        if rx + margin <= tx < rx + rw - margin and ry + margin <= ty < ry + rh - margin:
            return room
    return None


def same_room(arena, a: tuple[float, float], b: tuple[float, float]) -> bool:
    """On the floor, both points are inside the same room (a corridor counts as no room).
    Always true in a single-room arena."""
    floor = arena.floor
    if floor is None:
        return True
    room = room_of(floor, *a)
    return room is not None and room == room_of(floor, *b)


def lock(world: World, door_ids) -> None:
    world.locked = sorted(set(world.locked) | set(door_ids))


def unlock(world: World, door_ids) -> None:
    world.locked = sorted(set(world.locked) - set(door_ids))


def tick(world: World, tuning: Tuning, arena) -> None:
    floor = arena.floor
    if floor is None or world.mode != "floor":
        return
    _warps(world, tuning)
    if world.active_room:
        _hold(world, tuning, floor)
        return
    player = world.player
    # Any interior tile counts (door gaps are wall tiles, never interior), so no path along
    # the walls can slip past a room. A body still overlapping the gap is pushed into the
    # room when the doors shut.
    room = room_of(floor, player.x, player.y)
    if room is not None and room.kind in ("combat", "chamber") and room.id not in world.cleared:
        _activate(world, tuning, floor, room)


def _activate(world: World, tuning: Tuning, floor: Floor, room: FloorRoom) -> None:
    lock(world, [door.id for door in floor.doors_of(room.id)])
    world.active_room = room.id
    world.wave = 0
    world.events.append(Event("room_lock", *tile_center(room.center)))
    if room.kind == "combat":
        _queue_wave(world, tuning, room)
    else:
        x, y = tile_center(room.center)
        spawn_rival(world, x, y, world.protocol, tuning)


def _queue_wave(world: World, tuning: Tuning, room: FloorRoom) -> None:
    for kind, spawn in WAVES[room.id][world.wave]:
        x, y = tile_center(room.spawns[spawn])
        world.warps.append(Warp(world.new_id(), kind, x, y, tuning.warp_tell))
        world.events.append(Event("warp", x, y))


def _warps(world: World, tuning: Tuning) -> None:
    waiting = []
    for warp in world.warps:
        warp.timer -= 1
        if warp.timer > 0:
            waiting.append(warp)
            continue
        spawn_robot(world, warp.kind, warp.x, warp.y, tuning)
        world.events.append(Event("warp_in", warp.x, warp.y))
    world.warps = waiting


def _hold(world: World, tuning: Tuning, floor: Floor) -> None:
    room = floor.get(world.active_room)
    if room.kind == "combat":
        if world.warps or any(h.health > 0 for h in world.hostiles):
            return
        if world.wave + 1 < len(WAVES[room.id]):
            world.wave += 1
            _queue_wave(world, tuning, room)
            return
    elif world.rival is not None and world.rival.health > 0:
        return
    else:
        world.rival = None
    absorb_charges(world, tuning, everything=True)  # nothing stolen is ever left behind
    # The fight is over: hostile shots and hazard tiles still in the air go with it.
    world.projectiles = [shot for shot in world.projectiles if not shot.hostile]
    world.hazards = []
    world.cleared = [*world.cleared, room.id]
    world.active_room = ""
    unlock(world, [door.id for door in floor.doors_of(room.id)])
    world.events.append(Event("room_clear", *tile_center(room.center)))


def shot_hits_wall(world: World, tuning: Tuning, arena, center, radius: float) -> None:
    """A friendly shot stopped by a wall: if it was a locked secret wall, crack it."""
    floor = arena.floor
    if floor is None:
        return
    for door_id, rect in arena.doors:
        door = next(d for d in floor.doors if d.id == door_id)
        if not door.secret or door_id not in world.locked:
            continue
        if circle_hits_rect(center, radius + 1.0, rect):
            hits = world.secret_hits.get(door_id, 0) + 1
            world.secret_hits = {**world.secret_hits, door_id: hits}
            world.events.append(Event("secret_hit", center[0], center[1]))
            if hits >= tuning.secret_wall_hits:
                pair = [
                    d.id
                    for d in floor.doors
                    if d.secret and {d.room, d.other} == {door.room, door.other}
                ]
                unlock(world, pair)
                world.events.append(Event("secret_open", center[0], center[1]))
            return
