"""Putting robots and the Regulator into the world. Shared by the rules (overload.sim.world)
and the floor's rooms (overload.sim.floorplay)."""

from __future__ import annotations

from overload.sim.state import Event, Hostile, Rival, World
from overload.sim.tuning import DEFAULT, Tuning

PROTOCOLS = ("pressure", "spacing", "lateral")


def spawn_drone(world: World, x: float, y: float, tuning: Tuning = DEFAULT) -> Hostile:
    interval = tuning.drone_fire_interval
    hostile = Hostile(
        id=world.new_id(),
        kind="drone",
        x=x,
        y=y,
        radius=tuning.drone_radius,
        health=tuning.drone_health,
        max_health=tuning.drone_health,
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


def spawn_robot(world: World, kind: str, x: float, y: float, tuning: Tuning = DEFAULT) -> Hostile:
    """Any robot of the roster by kind (overhaul)."""
    if kind == "drone":
        return spawn_drone(world, x, y, tuning)
    if kind == "relay":
        return spawn_relay(world, x, y, tuning)
    radius, health, timer = {
        "breaker": (tuning.breaker_radius, tuning.breaker_health, 0),
        "sweeper": (tuning.sweeper_radius, tuning.sweeper_health, 0),
        "sentry": (
            tuning.sentry_radius,
            tuning.sentry_health,
            tuning.sentry_interval // 2 + world.rng.randrange(tuning.sentry_interval // 2),
        ),
    }[kind]
    robot = Hostile(
        id=world.new_id(),
        kind=kind,
        x=x,
        y=y,
        radius=radius,
        health=health,
        max_health=health,
        fire_timer=timer,
    )
    world.hostiles.append(robot)
    return robot


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
