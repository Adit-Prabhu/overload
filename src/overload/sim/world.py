"""The rules: one fixed tick of the authoritative world.

Order inside a tick (fixed, so outcomes are deterministic):
1. aim, 2. dodge start, 3. player movement, 4. firing, 5. hostiles (tells and bolts),
6. projectile movement, 7. hits, 8. timers, 9. outcome (player down takes precedence over
clearing the room in the same tick), 10. tick counter.
"""

from __future__ import annotations

import random

from overload.sim.arena import SUBSTATION, Arena
from overload.sim.geometry import (
    circle_hits_rect,
    circles_overlap,
    clamp_inside,
    normalize,
    outside_bounds,
    push_out_of_rect,
)
from overload.sim.inputs import InputFrame
from overload.sim.state import Event, Hostile, Player, Projectile, World
from overload.sim.tuning import DEFAULT, Tuning


def new_world(seed: int, tuning: Tuning = DEFAULT, arena: Arena = SUBSTATION) -> World:
    """Fresh practice world: the Surge at its spawn and Arc Mites at the practice spawns."""
    sx, sy = arena.player_spawn
    world = World(
        seed=seed,
        rng=random.Random(seed),
        player=Player(x=sx, y=sy, charge=tuning.player_max_charge),
    )
    for x, y in arena.practice_spawns:
        spawn_arc_mite(world, x, y, tuning)
    return world


def spawn_arc_mite(world: World, x: float, y: float, tuning: Tuning = DEFAULT) -> Hostile:
    interval = tuning.arc_mite_fire_interval
    hostile = Hostile(
        id=world.new_id(),
        kind="arc_mite",
        x=x,
        y=y,
        radius=tuning.arc_mite_radius,
        health=tuning.arc_mite_health,
        max_health=tuning.arc_mite_health,
        fire_timer=interval // 2 + world.rng.randrange(interval // 2),
    )
    world.hostiles.append(hostile)
    return hostile


def step(world: World, inp: InputFrame, tuning: Tuning = DEFAULT, arena: Arena = SUBSTATION):
    """Advance one tick. A finished world (down or clear) does not change."""
    world.events.clear()
    if world.outcome != "playing":
        return
    _aim(world.player, inp)
    _dodge(world, inp, tuning)
    _move_player(world.player, inp, tuning, arena)
    _fire(world, inp, tuning)
    _hostiles(world, tuning)
    _move_projectiles(world, arena)
    _hits(world, tuning)
    _timers(world.player)
    _outcome(world)
    world.tick += 1


def telegraphing(hostile: Hostile, tuning: Tuning = DEFAULT) -> bool:
    return 0 < hostile.fire_timer <= tuning.arc_mite_tell


def tell_progress(hostile: Hostile, tuning: Tuning = DEFAULT) -> float:
    """0 when a tell starts, 1 at the moment of firing."""
    if not telegraphing(hostile, tuning):
        return 0.0
    return 1.0 - hostile.fire_timer / tuning.arc_mite_tell


def _aim(player: Player, inp: InputFrame) -> None:
    ax, ay = normalize(inp.aim_x - player.x, inp.aim_y - player.y)
    if ax or ay:
        player.aim_x, player.aim_y = ax, ay


def _dodge(world: World, inp: InputFrame, tuning: Tuning) -> None:
    player = world.player
    if not inp.dodge or player.dodging or player.dodge_cooldown > 0:
        return
    dx, dy = normalize(inp.move_x, inp.move_y)
    if not (dx or dy):
        dx, dy = player.aim_x, player.aim_y
    player.dodge_dx, player.dodge_dy = dx, dy
    player.dodge_ticks = tuning.dodge_ticks
    player.dodge_cooldown = tuning.dodge_ticks + tuning.dodge_cooldown
    world.events.append(Event("dodge", player.x, player.y))


def _move_player(player: Player, inp: InputFrame, tuning: Tuning, arena: Arena) -> None:
    if player.dodging:
        vx, vy = player.dodge_dx * tuning.dodge_speed, player.dodge_dy * tuning.dodge_speed
    else:
        nx, ny = normalize(inp.move_x, inp.move_y)
        vx, vy = nx * tuning.player_speed, ny * tuning.player_speed
    pos = (player.x + vx, player.y + vy)
    for _ in range(2):
        for rect in arena.obstacles:
            pos = push_out_of_rect(pos, tuning.player_radius, rect)
        pos = clamp_inside(pos, tuning.player_radius, arena.bounds)
    player.x, player.y = pos


def _fire(world: World, inp: InputFrame, tuning: Tuning) -> None:
    player = world.player
    if not inp.fire or player.gun_cooldown > 0 or player.dodging:
        return
    offset = tuning.player_radius + tuning.shot_radius + 2.0
    world.projectiles.append(
        Projectile(
            id=world.new_id(),
            x=player.x + player.aim_x * offset,
            y=player.y + player.aim_y * offset,
            vx=player.aim_x * tuning.shot_speed,
            vy=player.aim_y * tuning.shot_speed,
            radius=tuning.shot_radius,
            damage=tuning.shot_damage,
            hostile=False,
            ttl=tuning.shot_ttl,
        )
    )
    player.gun_cooldown = tuning.gun_cooldown
    world.events.append(Event("shot", player.x, player.y))


def _hostiles(world: World, tuning: Tuning) -> None:
    player = world.player
    for hostile in world.hostiles:
        hostile.fire_timer -= 1
        if hostile.fire_timer == tuning.arc_mite_tell:
            dx, dy = normalize(player.x - hostile.x, player.y - hostile.y)
            hostile.tell_dx, hostile.tell_dy = (dx, dy) if (dx or dy) else (1.0, 0.0)
            world.events.append(Event("tell", hostile.x, hostile.y, hostile.id))
        if hostile.fire_timer <= 0:
            offset = hostile.radius + tuning.bolt_radius + 1.0
            world.projectiles.append(
                Projectile(
                    id=world.new_id(),
                    x=hostile.x + hostile.tell_dx * offset,
                    y=hostile.y + hostile.tell_dy * offset,
                    vx=hostile.tell_dx * tuning.bolt_speed,
                    vy=hostile.tell_dy * tuning.bolt_speed,
                    radius=tuning.bolt_radius,
                    damage=tuning.bolt_damage,
                    hostile=True,
                    ttl=tuning.bolt_ttl,
                )
            )
            hostile.fire_timer = tuning.arc_mite_fire_interval
            world.events.append(Event("bolt", hostile.x, hostile.y, hostile.id))


def _move_projectiles(world: World, arena: Arena) -> None:
    survivors = []
    for shot in world.projectiles:
        shot.x += shot.vx
        shot.y += shot.vy
        shot.ttl -= 1
        center = (shot.x, shot.y)
        blocked = outside_bounds(center, shot.radius, arena.bounds) or any(
            circle_hits_rect(center, shot.radius, rect) for rect in arena.obstacles
        )
        if shot.ttl <= 0 or blocked:
            world.events.append(Event("fizzle", shot.x, shot.y, shot.id))
            continue
        survivors.append(shot)
    world.projectiles = survivors


def _hits(world: World, tuning: Tuning) -> None:
    player = world.player
    survivors = []
    for shot in world.projectiles:
        center = (shot.x, shot.y)
        if shot.hostile:
            if not player.protected and circles_overlap(
                center, shot.radius, (player.x, player.y), tuning.player_radius
            ):
                player.charge = max(0, player.charge - shot.damage)
                player.invulnerable = tuning.hit_invulnerability
                world.events.append(Event("player_hit", player.x, player.y))
                continue
        else:
            target = next(
                (
                    h
                    for h in world.hostiles
                    if h.health > 0 and circles_overlap(center, shot.radius, (h.x, h.y), h.radius)
                ),
                None,
            )
            if target is not None:
                target.health -= shot.damage
                world.events.append(Event("hostile_hit", target.x, target.y, target.id))
                continue
        survivors.append(shot)
    world.projectiles = survivors
    for hostile in world.hostiles:
        if hostile.health <= 0:
            world.events.append(Event("hostile_destroyed", hostile.x, hostile.y, hostile.id))
    world.hostiles = [h for h in world.hostiles if h.health > 0]


def _timers(player: Player) -> None:
    player.gun_cooldown = max(0, player.gun_cooldown - 1)
    player.dodge_ticks = max(0, player.dodge_ticks - 1)
    player.dodge_cooldown = max(0, player.dodge_cooldown - 1)
    player.invulnerable = max(0, player.invulnerable - 1)


def _outcome(world: World) -> None:
    if world.player.charge <= 0:
        world.outcome = "down"
        world.events.append(Event("player_down", world.player.x, world.player.y))
    elif not world.hostiles:
        world.outcome = "clear"
        world.events.append(Event("clear"))
