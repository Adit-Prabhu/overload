"""The robot roster (overhaul, Nov 17). Every robot telegraphs before it attacks, and each
attacks in its own way with its own projectile, so no two look or play alike:

- Arc Drone (Spark): hovers at mid range, aims (0.45 s), fires a spiked spark ball.
- Relay Bot (Blink): marks a landing spot (0.5 s), blinks there, aims (0.5 s), fires a fan
  of three diamond shards.
- Breaker (Burst): walks in, raises its fists (0.6 s), slams. A shockwave ring runs along the
  floor and hurts once as it passes the Surge, unless the Surge is dodging.
- Sweeper: rolls closer, revs up with its direction locked (0.5 s), then rushes in a line.
- Sentry: never moves, aims for a long time (0.8 s), fires a slow heavy shell.

Deterministic, no trig at runtime.
"""

from __future__ import annotations

from overload.sim import floorplay
from overload.sim.collision import blocked, line_clear, move_body
from overload.sim.damage import hurt_player
from overload.sim.geometry import circles_overlap, length, normalize, outside_bounds
from overload.sim.state import Event, Hostile, Projectile, Shockwave, World
from overload.sim.tuning import Tuning

# Eight hop directions for the Relay Bot (unit vectors, exact constants).
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
# The shard fan: rotation by 15 degrees as exact constants.
_COS15 = 0.9659258262890683
_SIN15 = 0.25881904510252074


def pace(robot: Hostile, speed: float, tuning: Tuning) -> float:
    """Walking speed for the robot's tier (sim/spawns.py): Overcharged robots are faster."""
    return speed * tuning.overcharged_speed if robot.tier == 3 else speed


def rest(robot: Hostile, ticks: int, tuning: Tuning) -> int:
    """Rest between attacks for the robot's tier. Tuning guards these against the tells."""
    return max(1, round(ticks * tuning.overcharged_rest)) if robot.tier == 3 else ticks


def tick(world: World, tuning: Tuning, arena) -> None:
    for robot in world.hostiles:
        if robot.health <= 0:
            continue
        if robot.kind == "relay":
            _relay(world, robot, tuning, arena)
        elif robot.kind == "breaker":
            _breaker(world, robot, tuning, arena)
        elif robot.kind == "sweeper":
            _sweeper(world, robot, tuning, arena)
        elif robot.kind == "sentry":
            _sentry(world, robot, tuning)
        else:
            _drone(world, robot, tuning, arena)
    _shockwaves(world, tuning)


def telegraphing(robot: Hostile, tuning: Tuning) -> bool:
    """True while an aimed attack is being lined up (the dotted line and filling ring)."""
    if robot.kind in ("relay", "sweeper"):
        return robot.phase in ("aim", "rev")
    if robot.kind == "sentry":
        return 0 < robot.fire_timer <= tuning.sentry_tell
    if robot.kind == "breaker":
        return robot.phase == "raise"
    return 0 < robot.fire_timer <= tuning.drone_tell


def tell_progress(robot: Hostile, tuning: Tuning) -> float:
    """0 when a tell starts, 1 at the moment the attack (or a Relay Bot's landing) happens."""
    totals = {
        "relay": {"aim": tuning.relay_aim_tell, "blink": tuning.relay_blink_tell},
        "breaker": {"raise": tuning.breaker_tell},
        "sweeper": {"rev": tuning.sweeper_tell},
    }
    if robot.kind in totals:
        total = totals[robot.kind].get(robot.phase)
        return 1.0 - robot.fire_timer / total if total else 0.0
    total = tuning.sentry_tell if robot.kind == "sentry" else tuning.drone_tell
    if not 0 < robot.fire_timer <= total:
        return 0.0
    return 1.0 - robot.fire_timer / total


def _aim_at_player(world: World, robot: Hostile) -> None:
    player = world.player
    dx, dy = normalize(player.x - robot.x, player.y - robot.y)
    robot.tell_dx, robot.tell_dy = (dx, dy) if (dx or dy) else (1.0, 0.0)


def _shoot(
    world: World,
    robot: Hostile,
    dx: float,
    dy: float,
    speed: float,
    radius: float,
    ttl: int,
    kind: str,
    tuning: Tuning,
) -> None:
    offset = robot.radius + radius + 1.0
    world.projectiles.append(
        Projectile(
            id=world.new_id(),
            x=robot.x + dx * offset,
            y=robot.y + dy * offset,
            vx=dx * speed,
            vy=dy * speed,
            radius=radius,
            damage=tuning.bolt_damage,
            hostile=True,
            ttl=ttl,
            kind=kind,
        )
    )


def _drone(world: World, drone: Hostile, tuning: Tuning, arena) -> None:
    """Drift to mid range (never while aiming), then aim and fire a spark ball."""
    player = world.player
    dx, dy = player.x - drone.x, player.y - drone.y
    distance = length(dx, dy)
    if not telegraphing(drone, tuning) and distance > 0:
        ux, uy = dx / distance, dy / distance
        if distance > tuning.drone_far:
            vx, vy = ux, uy
        elif distance < tuning.drone_near:
            vx, vy = -ux, -uy
        else:
            vx, vy = -uy * 0.5, ux * 0.5  # a slow orbit
        drone.x, drone.y = move_body(
            drone.x,
            drone.y,
            vx * pace(drone, tuning.drone_speed, tuning),
            vy * pace(drone, tuning.drone_speed, tuning),
            drone.radius,
            arena,
            world,
        )
    drone.fire_timer -= 1
    if drone.fire_timer == tuning.drone_tell:
        _aim_at_player(world, drone)
        world.events.append(Event("tell", drone.x, drone.y, drone.id))
    if drone.fire_timer <= 0:
        _shoot(
            world,
            drone,
            drone.tell_dx,
            drone.tell_dy,
            tuning.bolt_speed,
            tuning.bolt_radius,
            tuning.bolt_ttl,
            "bolt",
            tuning,
        )
        drone.fire_timer = rest(drone, tuning.drone_fire_interval, tuning)
        world.events.append(Event("bolt", drone.x, drone.y, drone.id))


def _relay(world: World, relay: Hostile, tuning: Tuning, arena) -> None:
    """Idle, mark a landing spot in its own room, blink there, aim, fire three shards."""
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
            on_player = circles_overlap(
                spot,
                relay.radius + tuning.relay_landing_gap,
                (player.x, player.y),
                tuning.player_radius,
            )
            if (
                not on_player
                and not outside_bounds(spot, relay.radius, arena.bounds)
                and not blocked(world, arena, spot, relay.radius)
                and line_clear(world, arena, (relay.x, relay.y), spot)
                and floorplay.same_room(arena, (relay.x, relay.y), spot)
            ):
                relay.dest_x, relay.dest_y = spot
                break
        relay.phase, relay.fire_timer = "blink", tuning.relay_blink_tell
        world.events.append(Event("relay_mark", relay.dest_x, relay.dest_y, relay.id))
    elif relay.phase == "blink":
        world.events.append(Event("relay_from", relay.x, relay.y, relay.id))
        relay.x, relay.y = relay.dest_x, relay.dest_y
        _aim_at_player(world, relay)
        relay.phase, relay.fire_timer = "aim", tuning.relay_aim_tell
        world.events.append(Event("relay_blink", relay.x, relay.y, relay.id))
        world.events.append(Event("tell", relay.x, relay.y, relay.id))
    else:
        ax, ay = relay.tell_dx, relay.tell_dy
        fan = (
            (ax, ay),
            (ax * _COS15 - ay * _SIN15, ax * _SIN15 + ay * _COS15),
            (ax * _COS15 + ay * _SIN15, -ax * _SIN15 + ay * _COS15),
        )
        for dx, dy in fan:
            _shoot(
                world,
                relay,
                dx,
                dy,
                tuning.shard_speed,
                tuning.shard_radius,
                tuning.bolt_ttl,
                "shard",
                tuning,
            )
        relay.phase, relay.fire_timer = "", rest(relay, tuning.relay_idle, tuning)
        world.events.append(Event("shards", relay.x, relay.y, relay.id))


def _breaker(world: World, breaker: Hostile, tuning: Tuning, arena) -> None:
    """Walk in, raise the fists (the tell), slam a shockwave, then recover."""
    player = world.player
    if breaker.phase == "raise":
        breaker.fire_timer -= 1
        if breaker.fire_timer <= 0:
            world.shockwaves.append(
                Shockwave(world.new_id(), breaker.x, breaker.y, breaker.radius, False)
            )
            breaker.phase, breaker.fire_timer = "recover", tuning.breaker_recover
            world.events.append(Event("slam", breaker.x, breaker.y, breaker.id))
        return
    if breaker.phase == "recover":
        breaker.fire_timer -= 1
        if breaker.fire_timer <= 0:
            breaker.phase = ""
        return
    dx, dy = player.x - breaker.x, player.y - breaker.y
    distance = length(dx, dy)
    if distance <= tuning.breaker_reach:
        breaker.phase, breaker.fire_timer = "raise", tuning.breaker_tell
        world.events.append(Event("raise", breaker.x, breaker.y, breaker.id))
        return
    nx, ny = normalize(dx, dy)
    breaker.tell_dx, breaker.tell_dy = nx, ny
    breaker.x, breaker.y = move_body(
        breaker.x,
        breaker.y,
        nx * pace(breaker, tuning.breaker_speed, tuning),
        ny * pace(breaker, tuning.breaker_speed, tuning),
        breaker.radius,
        arena,
        world,
    )


def _shockwaves(world: World, tuning: Tuning) -> None:
    """Rings expand along the floor and hurt once as their edge passes the Surge."""
    player = world.player
    left = []
    for wave in world.shockwaves:
        wave.radius += tuning.wave_speed
        if not wave.hit:
            distance = length(player.x - wave.x, player.y - wave.y)
            if abs(distance - wave.radius) <= tuning.wave_width + tuning.player_radius:
                if not player.protected:
                    hurt_player(world, tuning.bolt_damage, tuning)
                wave.hit = True
        # The ring stops once its hit band reaches its reach, the radius its tell shows.
        reach = wave.reach or tuning.wave_reach
        if wave.radius + tuning.wave_width + tuning.player_radius < reach:
            left.append(wave)
    world.shockwaves = left


def _sweeper(world: World, sweeper: Hostile, tuning: Tuning, arena) -> None:
    """Roll closer, rev up with the direction locked, rush in a straight line, rest."""
    player = world.player
    if sweeper.phase == "rev":
        sweeper.fire_timer -= 1
        if sweeper.fire_timer <= 0:
            sweeper.phase, sweeper.fire_timer = "rush", tuning.sweeper_rush_ticks
            world.events.append(Event("rush", sweeper.x, sweeper.y, sweeper.id))
        return
    if sweeper.phase == "rush":
        sweeper.x, sweeper.y = move_body(
            sweeper.x,
            sweeper.y,
            sweeper.tell_dx * tuning.sweeper_rush_speed,
            sweeper.tell_dy * tuning.sweeper_rush_speed,
            sweeper.radius,
            arena,
            world,
        )
        if circles_overlap(
            (sweeper.x, sweeper.y), sweeper.radius, (player.x, player.y), tuning.player_radius
        ):
            hurt_player(world, tuning.rival_contact_damage, tuning)
        sweeper.fire_timer -= 1
        if sweeper.fire_timer <= 0:
            sweeper.phase, sweeper.fire_timer = "rest", tuning.sweeper_rest
        return
    if sweeper.phase == "rest":
        sweeper.fire_timer -= 1
        if sweeper.fire_timer <= 0:
            sweeper.phase = ""
        return
    dx, dy = player.x - sweeper.x, player.y - sweeper.y
    if length(dx, dy) <= tuning.sweeper_trigger:
        _aim_at_player(world, sweeper)
        sweeper.phase, sweeper.fire_timer = "rev", tuning.sweeper_tell
        world.events.append(Event("tell", sweeper.x, sweeper.y, sweeper.id))
        return
    nx, ny = normalize(dx, dy)
    sweeper.x, sweeper.y = move_body(
        sweeper.x,
        sweeper.y,
        nx * pace(sweeper, tuning.sweeper_speed, tuning),
        ny * pace(sweeper, tuning.sweeper_speed, tuning),
        sweeper.radius,
        arena,
        world,
    )


def _sentry(world: World, sentry: Hostile, tuning: Tuning) -> None:
    """Stand still, aim for a long time, fire a slow heavy shell."""
    sentry.fire_timer -= 1
    if sentry.fire_timer == tuning.sentry_tell:
        _aim_at_player(world, sentry)
        world.events.append(Event("tell", sentry.x, sentry.y, sentry.id))
    if sentry.fire_timer <= 0:
        _shoot(
            world,
            sentry,
            sentry.tell_dx,
            sentry.tell_dy,
            tuning.shell_speed,
            tuning.shell_radius,
            tuning.shell_ttl,
            "shell",
            tuning,
        )
        sentry.fire_timer = rest(sentry, tuning.sentry_interval, tuning)
        world.events.append(Event("shell", sentry.x, sentry.y, sentry.id))
