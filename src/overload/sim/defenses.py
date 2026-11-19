"""The two base powers stolen from the robots that carried nothing before (powers spec
section 3): Bulwark from the Sentry and Magnet from the Sweeper.

- Bulwark raises a bubble around the Surge for `bulwark_ticks`. Hostile shots that touch
  it fizzle. It does not stop shockwaves, hazard tiles or bodies. Evolved (REFLECT), each
  absorbed shot flies back as a spark, reversed along the path it came in on.
- Magnet sets a field at the aim point, placed like a Blink lands: as far along the aim as
  it can, up to `magnet_range`, never inside a prop or past a wall. For `magnet_ticks` it
  drags robots and loose charges within `magnet_radius` toward its center. It does no
  damage of its own. Evolved (CRUSH), robots still in the field when it ends take
  `magnet_crush_damage`. Nothing moves the Regulator, but CRUSH dents it like any hit.

Deterministic and free of trig, like the rest of the simulation.
"""

from __future__ import annotations

from overload.sim.arena import Arena
from overload.sim.collision import move_body
from overload.sim.damage import damage_rival
from overload.sim.geometry import circles_overlap, length, normalize
from overload.sim.inputs import InputFrame
from overload.sim.state import Device, Event, Projectile, World
from overload.sim.tuning import Tuning


def bulwark(world: World, inp: InputFrame, tuning: Tuning, arena: Arena) -> bool:  # noqa: ARG001
    player = world.player
    player.shield = tuning.bulwark_ticks
    world.events.append(Event("bulwark_up", player.x, player.y))
    return True


def magnet(world: World, inp: InputFrame, tuning: Tuning, arena: Arena) -> bool:
    from overload.sim.powers import evolved, place_point

    spot = place_point(world, inp, tuning, arena, tuning.magnet_range, 1.0)
    player = world.player
    if spot is None:
        world.events.append(Event("magnet_rejected", player.x, player.y))
        return False
    crush = 1 if evolved(world.fragments, "magnet", tuning) else 0
    world.fields.append(
        Device(world.new_id(), "magnet", spot[0], spot[1], spot[0], spot[1], tuning.magnet_ticks)
    )
    world.events.append(Event("magnet_field", spot[0], spot[1], crush))
    return True


def shield_shots(world: World, tuning: Tuning) -> None:
    """While the bubble is up, hostile shots that touch it fizzle (REFLECT sends them back as
    sparks). Runs after shots move and before they hit, so a shot never lands through it."""
    from overload.sim.powers import evolved

    player = world.player
    if player.shield <= 0:
        return
    player.shield -= 1
    reflect = evolved(world.fragments, "bulwark", tuning)
    kept = []
    for shot in world.projectiles:
        if shot.hostile and circles_overlap(
            (shot.x, shot.y), shot.radius, (player.x, player.y), tuning.bulwark_radius
        ):
            world.events.append(Event("shield_absorb", shot.x, shot.y, shot.id))
            if reflect:
                ux, uy = normalize(-shot.vx, -shot.vy)
                kept.append(
                    Projectile(
                        id=world.new_id(),
                        x=shot.x,
                        y=shot.y,
                        vx=ux * tuning.spark_speed,
                        vy=uy * tuning.spark_speed,
                        radius=tuning.spark_radius,
                        damage=tuning.spark_damage,
                        hostile=False,
                        ttl=tuning.spark_ttl,
                        kind="spark",
                    )
                )
                world.events.append(Event("shield_reflect", shot.x, shot.y, shot.id))
            continue
        kept.append(shot)
    world.projectiles = kept


def tick_fields(world: World, tuning: Tuning, arena: Arena) -> None:
    """Each Magnet field drags robots and loose charges toward its center, then ends,
    crushing what is still inside when it evolved."""
    left = []
    for field in world.fields:
        reach = tuning.magnet_radius
        for robot in world.hostiles:
            if robot.health <= 0:
                continue
            dx, dy = field.x - robot.x, field.y - robot.y
            distance = length(dx, dy)
            if 0.0 < distance <= reach:
                step = min(tuning.magnet_pull, distance)
                ux, uy = dx / distance, dy / distance
                robot.x, robot.y = move_body(
                    robot.x, robot.y, ux * step, uy * step, robot.radius, arena, world
                )
        for charge in world.charges:
            dx, dy = field.x - charge.x, field.y - charge.y
            distance = length(dx, dy)
            if 0.0 < distance <= reach:
                step = min(tuning.magnet_pull, distance)
                charge.x += dx / distance * step
                charge.y += dy / distance * step
        field.timer -= 1
        if field.timer > 0:
            left.append(field)
            continue
        _crush(world, field, tuning)
    world.fields = left


def _crush(world: World, field: Device, tuning: Tuning) -> None:
    from overload.sim.powers import evolved

    crush = evolved(world.fragments, "magnet", tuning)
    world.events.append(Event("magnet_end", field.x, field.y, 1 if crush else 0))
    if not crush:
        return
    world.events.append(Event("magnet_crush", field.x, field.y))
    reach = tuning.magnet_radius
    for robot in world.hostiles:
        if robot.health > 0 and length(robot.x - field.x, robot.y - field.y) <= reach:
            robot.health -= tuning.magnet_crush_damage
            world.events.append(Event("hostile_hit", robot.x, robot.y, robot.id))
    rival = world.rival
    near = (
        rival is not None and length(rival.x - field.x, rival.y - field.y) <= reach + rival.radius
    )
    if near and rival.health > 0:
        damage_rival(world, tuning.magnet_crush_damage, rival.x, rival.y)
