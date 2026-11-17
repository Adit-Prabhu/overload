"""The rules: one fixed tick of the authoritative world.

Order inside a tick (fixed, so outcomes are deterministic):
1. aim, 2. dodge start, 3. player movement, 4. firing, 5. powers (Q then E), 6. hostiles
(tells, Relay blinks, bolts), 7. the Regulator (boot, protocol behavior), 8. hazard tiles,
9. body collision (the Surge is pushed out of the Regulator and machines unless dodging),
10. projectile movement (a shot stopped by a secret wall cracks it), 11. Arc Trail pulses,
12. hits (destroyed machines drop charges), 13. absorbing charges, 14. floor rooms (warps,
locking, waves, clearing), 15. timers and cooldowns, 16. outcome (player down takes
precedence over clearing the room in the same tick, and a win absorbs every charge left),
17. tick counter.
"""

from __future__ import annotations

import random

from overload.sim import floorplay, robots
from overload.sim.aiming import aim, launch_point
from overload.sim.arena import SUBSTATION, Arena
from overload.sim.collision import blocked, move_body  # noqa: F401 (move_body re-exported)
from overload.sim.damage import damage_rival, hurt_player
from overload.sim.geometry import (
    circle_hits_rect,
    circles_overlap,
    length,
    normalize,
    outside_bounds,
)
from overload.sim.inputs import InputFrame
from overload.sim.powers import (
    DROPS,
    absorb_charges,
    drop_charge,
    tick_cooldowns,
    tick_trails,
    use_powers,
)
from overload.sim.spawns import (  # noqa: F401 (re-exported for callers of the rules)
    PROTOCOLS,
    spawn_drone,
    spawn_relay,
    spawn_rival,
)
from overload.sim.state import Event, Hazard, Hostile, Player, Projectile, Rival, World
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
        spawn_drone(world, x, y, tuning)
    return world


def step(world: World, inp: InputFrame, tuning: Tuning = DEFAULT, arena: Arena = SUBSTATION):
    """Advance one tick. A finished world (down or clear) does not change."""
    world.events.clear()
    if world.outcome != "playing":
        return
    aim(world.player, inp, tuning)
    _dodge(world, inp, tuning)
    _move_player(world, inp, tuning, arena)
    _fire(world, inp, tuning, arena)
    use_powers(world, inp, tuning, arena)
    robots.tick(world, tuning, arena)
    _rival(world, tuning, arena)
    _hazards(world, tuning)
    _separate(world, tuning, arena)
    _move_projectiles(world, tuning, arena)
    tick_trails(world, tuning)
    _hits(world, tuning)
    absorb_charges(world, tuning)
    floorplay.tick(world, tuning, arena)
    _timers(world.player)
    tick_cooldowns(world)
    _outcome(world, tuning)
    world.tick += 1


def telegraphing(hostile: Hostile, tuning: Tuning = DEFAULT) -> bool:
    """True while a robot lines up an attack (see overload.sim.robots)."""
    return robots.telegraphing(hostile, tuning)


def tell_progress(hostile: Hostile, tuning: Tuning = DEFAULT) -> float:
    """0 when a tell starts, 1 when the attack (or a Relay Bot's landing) happens."""
    return robots.tell_progress(hostile, tuning)


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


def _move_player(world: World, inp: InputFrame, tuning: Tuning, arena: Arena) -> None:
    player = world.player
    if player.dodging:
        vx, vy = player.dodge_dx * tuning.dodge_speed, player.dodge_dy * tuning.dodge_speed
    else:
        nx, ny = normalize(inp.move_x, inp.move_y)
        vx, vy = nx * tuning.player_speed, ny * tuning.player_speed
    player.x, player.y = move_body(player.x, player.y, vx, vy, tuning.player_radius, arena, world)


def _fire(world: World, inp: InputFrame, tuning: Tuning, arena: Arena) -> None:
    player = world.player
    if not inp.fire or player.gun_cooldown > 0 or player.dodging:
        return
    player.gun_cooldown = tuning.gun_cooldown
    world.events.append(Event("shot", player.x, player.y))  # a visible shot, even a fizzle
    start = launch_point(world, tuning, arena)
    if start is None:
        return
    world.projectiles.append(
        Projectile(
            id=world.new_id(),
            x=start[0],
            y=start[1],
            vx=player.aim_x * tuning.shot_speed,
            vy=player.aim_y * tuning.shot_speed,
            radius=tuning.shot_radius,
            damage=tuning.shot_damage,
            hostile=False,
            ttl=tuning.shot_ttl,
        )
    )


def _move_projectiles(world: World, tuning: Tuning, arena: Arena) -> None:
    survivors = []
    for shot in world.projectiles:
        shot.x += shot.vx
        shot.y += shot.vy
        shot.ttl -= 1
        center = (shot.x, shot.y)
        hit_wall = outside_bounds(center, shot.radius, arena.bounds) or blocked(
            world, arena, center, shot.radius
        )
        if shot.ttl <= 0 or hit_wall:
            if hit_wall and not shot.hostile:
                floorplay.shot_hits_wall(world, tuning, arena, center, shot.radius)
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
                hurt_player(world, shot.damage, tuning)
                continue
        else:
            rival = world.rival
            if (
                rival is not None
                and rival.health > 0
                and circles_overlap(center, shot.radius, (rival.x, rival.y), rival.radius)
            ):
                damage_rival(world, shot.damage, shot.x, shot.y)
                continue
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
            world.events.append(
                Event(
                    "hostile_destroyed",
                    hostile.x,
                    hostile.y,
                    hostile.id,
                    DROPS.get(hostile.kind, ""),
                )
            )
            drop_charge(world, hostile.kind, hostile.x, hostile.y)
    world.hostiles = [h for h in world.hostiles if h.health > 0]


def _timers(player: Player) -> None:
    player.gun_cooldown = max(0, player.gun_cooldown - 1)
    player.dodge_ticks = max(0, player.dodge_ticks - 1)
    player.dodge_cooldown = max(0, player.dodge_cooldown - 1)
    player.invulnerable = max(0, player.invulnerable - 1)


def _outcome(world: World, tuning: Tuning) -> None:
    """Going down takes precedence. With a Regulator present, beating it clears the encounter.
    Without one (practice), clearing every hostile does. A win absorbs every charge left."""
    rival_beaten = world.rival is not None and world.rival.health <= 0
    if world.player.charge <= 0:
        world.outcome = "down"
        world.events.append(Event("player_down", world.player.x, world.player.y))
    elif world.mode == "floor":
        return  # on the floor, rooms clear one by one and the campaign tracks progress
    elif rival_beaten or (world.rival is None and not world.hostiles):
        world.outcome = "clear"
        absorb_charges(world, tuning, everything=True)
        world.events.append(Event("clear"))


def _separate(world: World, tuning: Tuning, arena: Arena) -> None:
    """Bodies are solid: the Surge cannot stand inside the Regulator or a machine. It is the
    one pushed (it is the lightest body), then kept out of walls. A dodge slips through."""
    player = world.player
    if player.dodging:
        return
    bodies = [(h.x, h.y, h.radius) for h in world.hostiles if h.health > 0]
    rival = world.rival
    if rival is not None and rival.health > 0:
        bodies.append((rival.x, rival.y, rival.radius))
    # A few passes settle a Surge squeezed between two bodies. Pinned between a body and a
    # wall it may still overlap a little: walls always win, so it never ends up inside one.
    for _ in range(3):
        moved = False
        for bx, by, radius in bodies:
            dx, dy = player.x - bx, player.y - by
            reach = radius + tuning.player_radius
            if dx * dx + dy * dy >= reach * reach:
                continue
            nx, ny = normalize(dx, dy)
            if not (nx or ny):
                nx, ny = -player.aim_x, -player.aim_y
            player.x, player.y = bx + nx * reach, by + ny * reach
            moved = True
        player.x, player.y = move_body(
            player.x, player.y, 0.0, 0.0, tuning.player_radius, arena, world
        )
        if not moved:
            break


# The Regulator ----------------------------------------------------------------------------

# Volley fan for Oscillate: rotation by 15 degrees as exact constants (no runtime trig).
_COS15 = 0.9659258262890683
_SIN15 = 0.25881904510252074


def rival_telegraphing(rival: Rival) -> bool:
    return rival.action == "tell"


def rival_tell_progress(rival: Rival, tuning: Tuning = DEFAULT) -> float:
    """0 when a Regulator tell starts, 1 when the attack lands."""
    if rival.action != "tell":
        return 0.0
    total = {
        "pressure": tuning.clamp_tell,
        "spacing": tuning.insulate_orb_tell,
        "lateral": tuning.oscillate_tell,
    }[rival.protocol]
    return 1.0 - rival.timer / total


def _lock_aim(rival: Rival, player: Player) -> None:
    dx, dy = normalize(player.x - rival.x, player.y - rival.y)
    rival.aim_x, rival.aim_y = (dx, dy) if (dx or dy) else (1.0, 0.0)


def _rival_shoot(
    world: World,
    rival: Rival,
    dx: float,
    dy: float,
    speed: float,
    radius: float,
    ttl: int,
    tuning: Tuning,
) -> None:
    offset = rival.radius + radius + 1.0
    world.projectiles.append(
        Projectile(
            id=world.new_id(),
            x=rival.x + dx * offset,
            y=rival.y + dy * offset,
            vx=dx * speed,
            vy=dy * speed,
            radius=radius,
            damage=tuning.bolt_damage,
            hostile=True,
            ttl=ttl,
            kind="orb" if radius > tuning.bolt_radius else "needle",
        )
    )


def _rival(world: World, tuning: Tuning, arena: Arena) -> None:
    rival = world.rival
    if rival is None or rival.health <= 0:
        return
    if rival.boot > 0:
        rival.boot -= 1
        return
    player = world.player
    if rival.protocol == "pressure":
        _clamp(world, rival, player, tuning, arena)
    elif rival.protocol == "spacing":
        _insulate(world, rival, player, tuning, arena)
    else:
        _oscillate(world, rival, player, tuning, arena)


def _clamp(world: World, rival: Rival, player: Player, tuning: Tuning, arena: Arena) -> None:
    """Close the distance, telegraph a lunge, dash, then recover in the open."""
    if rival.action == "move":
        dx, dy = player.x - rival.x, player.y - rival.y
        nx, ny = normalize(dx, dy)
        distance = length(dx, dy)
        if distance > tuning.clamp_range:
            rival.x, rival.y = move_body(
                rival.x,
                rival.y,
                nx * tuning.clamp_speed,
                ny * tuning.clamp_speed,
                rival.radius,
                arena,
                world,
            )
        if rival.cooldown > 0:
            rival.cooldown -= 1
        elif distance <= tuning.clamp_range:
            _lock_aim(rival, player)
            rival.action, rival.timer = "tell", tuning.clamp_tell
            world.events.append(Event("rival_tell", rival.x, rival.y))
    elif rival.action == "tell":
        rival.timer -= 1
        if rival.timer <= 0:
            rival.action, rival.timer = "dash", tuning.clamp_dash_ticks
            world.events.append(Event("rival_lunge", rival.x, rival.y))
    elif rival.action == "dash":
        rival.x, rival.y = move_body(
            rival.x,
            rival.y,
            rival.aim_x * tuning.clamp_dash_speed,
            rival.aim_y * tuning.clamp_dash_speed,
            rival.radius,
            arena,
            world,
        )
        if circles_overlap(
            (rival.x, rival.y), rival.radius, (player.x, player.y), tuning.player_radius
        ):
            hurt_player(world, tuning.rival_contact_damage, tuning)
        rival.timer -= 1
        if rival.timer <= 0:
            rival.action, rival.timer = "recover", tuning.clamp_recovery
    elif rival.action == "recover":
        rival.timer -= 1
        if rival.timer <= 0:
            rival.action, rival.cooldown = "move", tuning.clamp_rest


def _insulate(world: World, rival: Rival, player: Player, tuning: Tuning, arena: Arena) -> None:
    """Hold the Surge at range, lay hazard tiles under them and lob slow orbs."""
    dx, dy = player.x - rival.x, player.y - rival.y
    nx, ny = normalize(dx, dy)
    distance = length(dx, dy)
    if distance < tuning.insulate_min_distance:
        rival.x, rival.y = move_body(
            rival.x,
            rival.y,
            -nx * tuning.rival_speed,
            -ny * tuning.rival_speed,
            rival.radius,
            arena,
            world,
        )
    elif distance > tuning.insulate_max_distance:
        rival.x, rival.y = move_body(
            rival.x,
            rival.y,
            nx * tuning.rival_speed,
            ny * tuning.rival_speed,
            rival.radius,
            arena,
            world,
        )
    rival.cooldown -= 1
    if rival.cooldown <= 0:
        size = 16.0
        hx = (player.x // size) * size
        hy = (player.y // size) * size
        world.hazards.append(
            Hazard(
                world.new_id(),
                hx,
                hy,
                size,
                tuning.insulate_hazard_tell,
                tuning.insulate_hazard_active,
            )
        )
        rival.cooldown = tuning.insulate_hazard_interval
        world.events.append(Event("hazard_armed", hx, hy))
    if rival.action == "move":
        rival.timer -= 1
        if rival.timer <= 0:
            _lock_aim(rival, player)
            rival.action, rival.timer = "tell", tuning.insulate_orb_tell
            world.events.append(Event("rival_tell", rival.x, rival.y))
    elif rival.action == "tell":
        rival.timer -= 1
        if rival.timer <= 0:
            _rival_shoot(
                world,
                rival,
                rival.aim_x,
                rival.aim_y,
                tuning.orb_speed,
                tuning.orb_radius,
                tuning.orb_ttl,
                tuning,
            )
            rival.action, rival.timer = "move", tuning.insulate_orb_interval
            world.events.append(Event("rival_orb", rival.x, rival.y))


def _oscillate(world: World, rival: Rival, player: Player, tuning: Tuning, arena: Arena) -> None:
    """Strafe across the Surge's line of fire and answer with a three-bolt fan."""
    nx, ny = normalize(player.x - rival.x, player.y - rival.y)
    vx, vy = -ny * rival.strafe * tuning.oscillate_speed, nx * rival.strafe * tuning.oscillate_speed
    before = (rival.x, rival.y)
    rival.x, rival.y = move_body(rival.x, rival.y, vx, vy, rival.radius, arena, world)
    rival.strafe_timer -= 1
    moved = abs(rival.x - before[0]) + abs(rival.y - before[1])
    if rival.strafe_timer <= 0 or ((vx or vy) and moved < 0.25):
        rival.strafe, rival.strafe_timer = -rival.strafe, tuning.oscillate_turn
    if rival.action == "move":
        rival.timer -= 1
        if rival.timer <= 0:
            _lock_aim(rival, player)
            rival.action, rival.timer = "tell", tuning.oscillate_tell
            world.events.append(Event("rival_tell", rival.x, rival.y))
    elif rival.action == "tell":
        rival.timer -= 1
        if rival.timer <= 0:
            ax, ay = rival.aim_x, rival.aim_y
            for dx, dy in (
                (ax, ay),
                (ax * _COS15 - ay * _SIN15, ax * _SIN15 + ay * _COS15),
                (ax * _COS15 + ay * _SIN15, -ax * _SIN15 + ay * _COS15),
            ):
                _rival_shoot(
                    world,
                    rival,
                    dx,
                    dy,
                    tuning.bolt_speed,
                    tuning.bolt_radius,
                    tuning.bolt_ttl,
                    tuning,
                )
            rival.action, rival.timer = "move", tuning.oscillate_interval
            world.events.append(Event("rival_volley", rival.x, rival.y))


def _hazards(world: World, tuning: Tuning) -> None:
    player = world.player
    survivors = []
    for hazard in world.hazards:
        if hazard.arming > 0:
            hazard.arming -= 1
        else:
            rect = (hazard.x, hazard.y, hazard.size, hazard.size)
            if circle_hits_rect((player.x, player.y), tuning.player_radius, rect):
                hurt_player(world, tuning.hazard_damage, tuning)
            hazard.active -= 1
        if hazard.arming > 0 or hazard.active > 0:
            survivors.append(hazard)
    world.hazards = survivors
