"""The rules: one fixed tick of the authoritative world.

Order inside a tick (fixed, so outcomes are deterministic):
1. aim, 2. dodge start, 3. player movement, 4. firing, 5. powers (Q then E), 6. hostiles
(tells, Relay blinks, bolts), 7. the Regulator (boot, protocol behavior), 8. hazard tiles,
9. projectile movement, 10. Arc Trail pulses, 11. hits (destroyed machines drop charges),
12. absorbing charges, 13. timers and cooldowns, 14. outcome (player down takes precedence
over clearing the room in the same tick, and a win absorbs every charge left), 15. tick
counter.
"""

from __future__ import annotations

import random

from overload.sim.arena import SUBSTATION, Arena
from overload.sim.damage import damage_rival
from overload.sim.geometry import (
    circle_hits_rect,
    circles_overlap,
    clamp_inside,
    length,
    normalize,
    outside_bounds,
    push_out_of_rect,
)
from overload.sim.inputs import InputFrame
from overload.sim.powers import (
    absorb_charges,
    drop_charge,
    tick_cooldowns,
    tick_trails,
    use_powers,
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


def spawn_relay(world: World, x: float, y: float, tuning: Tuning = DEFAULT) -> Hostile:
    hostile = Hostile(
        id=world.new_id(),
        kind="relay",
        x=x,
        y=y,
        radius=tuning.relay_radius,
        health=tuning.relay_health,
        max_health=tuning.relay_health,
        fire_timer=tuning.relay_idle + world.rng.randrange(tuning.relay_idle),
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
    use_powers(world, inp, tuning, arena)
    _hostiles(world, tuning, arena)
    _rival(world, tuning, arena)
    _hazards(world, tuning)
    _move_projectiles(world, arena)
    tick_trails(world, tuning)
    _hits(world, tuning)
    absorb_charges(world, tuning)
    _timers(world.player)
    tick_cooldowns(world)
    _outcome(world, tuning)
    world.tick += 1


def telegraphing(hostile: Hostile, tuning: Tuning = DEFAULT) -> bool:
    """True while a shot is being aimed (the dotted line and filling ring)."""
    if hostile.kind == "relay":
        return hostile.phase == "aim"
    return 0 < hostile.fire_timer <= tuning.arc_mite_tell


def tell_progress(hostile: Hostile, tuning: Tuning = DEFAULT) -> float:
    """0 when a tell starts, 1 at the moment of firing (or, for a Relay's landing marker,
    of arriving)."""
    if hostile.kind == "relay":
        total = {"aim": tuning.relay_aim_tell, "blink": tuning.relay_blink_tell}.get(hostile.phase)
        return 1.0 - hostile.fire_timer / total if total else 0.0
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
    player.x, player.y = move_body(player.x, player.y, vx, vy, tuning.player_radius, arena)


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


def _hostiles(world: World, tuning: Tuning, arena: Arena) -> None:
    player = world.player
    for hostile in world.hostiles:
        if hostile.kind == "relay":
            _relay(world, hostile, tuning, arena)
            continue
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
                    kind="bolt",
                )
            )
            hostile.fire_timer = tuning.arc_mite_fire_interval
            world.events.append(Event("bolt", hostile.x, hostile.y, hostile.id))


# Eight hop directions for the Relay (unit vectors, exact constants, no runtime trig).
_DIAG = 0.7071067811865476
_HOPS = (
    (1.0, 0.0),
    (_DIAG, _DIAG),
    (0.0, 1.0),
    (-_DIAG, _DIAG),
    (-1.0, 0.0),
    (-_DIAG, -_DIAG),
    (0.0, -1.0),
    (_DIAG, -_DIAG),
)


def _relay(world: World, relay: Hostile, tuning: Tuning, arena: Arena) -> None:
    """Idle, then mark a landing spot (0.5 s), blink there, aim (0.5 s) and fire one bolt."""
    player = world.player
    relay.fire_timer -= 1
    if relay.fire_timer > 0:
        return
    if relay.phase == "":
        start = world.rng.randrange(len(_HOPS))
        distance = tuning.relay_hop_min + world.rng.random() * (
            tuning.relay_hop_max - tuning.relay_hop_min
        )
        relay.dest_x, relay.dest_y = relay.x, relay.y
        for i in range(len(_HOPS)):
            hx, hy = _HOPS[(start + i) % len(_HOPS)]
            spot = (relay.x + hx * distance, relay.y + hy * distance)
            if not outside_bounds(spot, relay.radius, arena.bounds) and not any(
                circle_hits_rect(spot, relay.radius, rect) for rect in arena.obstacles
            ):
                relay.dest_x, relay.dest_y = spot
                break
        relay.phase, relay.fire_timer = "blink", tuning.relay_blink_tell
        world.events.append(Event("relay_mark", relay.dest_x, relay.dest_y, relay.id))
    elif relay.phase == "blink":
        world.events.append(Event("relay_from", relay.x, relay.y, relay.id))
        relay.x, relay.y = relay.dest_x, relay.dest_y
        dx, dy = normalize(player.x - relay.x, player.y - relay.y)
        relay.tell_dx, relay.tell_dy = (dx, dy) if (dx or dy) else (1.0, 0.0)
        relay.phase, relay.fire_timer = "aim", tuning.relay_aim_tell
        world.events.append(Event("relay_blink", relay.x, relay.y, relay.id))
        world.events.append(Event("tell", relay.x, relay.y, relay.id))
    else:
        offset = relay.radius + tuning.bolt_radius + 1.0
        world.projectiles.append(
            Projectile(
                id=world.new_id(),
                x=relay.x + relay.tell_dx * offset,
                y=relay.y + relay.tell_dy * offset,
                vx=relay.tell_dx * tuning.bolt_speed,
                vy=relay.tell_dy * tuning.bolt_speed,
                radius=tuning.bolt_radius,
                damage=tuning.bolt_damage,
                hostile=True,
                ttl=tuning.bolt_ttl,
                kind="bolt",
            )
        )
        relay.phase, relay.fire_timer = "", tuning.relay_idle
        world.events.append(Event("bolt", relay.x, relay.y, relay.id))


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
            world.events.append(Event("hostile_destroyed", hostile.x, hostile.y, hostile.id))
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
    elif rival_beaten or (world.rival is None and not world.hostiles):
        world.outcome = "clear"
        absorb_charges(world, tuning, everything=True)
        world.events.append(Event("clear"))


def hurt_player(world: World, damage: int, tuning: Tuning) -> None:
    """Apply damage unless the Surge is dodging or recently hit."""
    player = world.player
    if player.protected:
        return
    player.charge = max(0, player.charge - damage)
    player.invulnerable = tuning.hit_invulnerability
    world.events.append(Event("player_hit", player.x, player.y))


def move_body(x: float, y: float, vx: float, vy: float, radius: float, arena: Arena):
    """Move a circle and push it out of walls and props. Speeds stay below the thinnest
    obstacle, so nothing tunnels."""
    pos = (x + vx, y + vy)
    for _ in range(2):
        for rect in arena.obstacles:
            pos = push_out_of_rect(pos, radius, rect)
        pos = clamp_inside(pos, radius, arena.bounds)
    return pos


# The Regulator ----------------------------------------------------------------------------

PROTOCOLS = ("pressure", "spacing", "lateral")
# Volley fan for Oscillate: rotation by 15 degrees as exact constants (no runtime trig).
_COS15 = 0.9659258262890683
_SIN15 = 0.25881904510252074


def spawn_rival(world: World, x: float, y: float, protocol: str, tuning: Tuning = DEFAULT):
    if protocol not in PROTOCOLS:
        raise ValueError(f"unknown protocol {protocol!r}")
    world.rival = Rival(
        x=x,
        y=y,
        radius=tuning.rival_radius,
        health=tuning.rival_health,
        max_health=tuning.rival_health,
        protocol=protocol,
        boot=tuning.rival_boot,
        cooldown=tuning.clamp_rest,
        timer=tuning.oscillate_interval if protocol == "lateral" else tuning.insulate_orb_interval,
    )
    world.events.append(Event("protocol_boot", x, y))
    return world.rival


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
            kind="orb" if radius > tuning.bolt_radius else "bolt",
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
        )
    elif distance > tuning.insulate_max_distance:
        rival.x, rival.y = move_body(
            rival.x, rival.y, nx * tuning.rival_speed, ny * tuning.rival_speed, rival.radius, arena
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
    rival.x, rival.y = move_body(rival.x, rival.y, vx, vy, rival.radius, arena)
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
