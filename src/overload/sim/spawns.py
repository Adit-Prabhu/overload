"""Putting robots and the Regulator into the world. Shared by the rules (overload.sim.world)
and the floor's rooms (overload.sim.floorplay)."""

from __future__ import annotations

from overload.sim.bosses import BOSSES, REGULATOR
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


# Sector variants (overhaul, Nov 17): the same robots, built for deeper in the station. Tier
# 1 is the stock robot. Tier 2 (Cooled, sector 2) has stock stats in the cooling plant's colors,
# so sector 2 stays as tuned. Tier 3 (Overcharged, sector 3) takes Tuning's overcharged_*
# values: more health (rounded up), a little faster walking, shorter rests. Tells and punish
# windows (a Breaker's recovery, a Sweeper's rest) never shrink. Health is the strong lever:
# 25 percent more made the test bot go down about 4 times a run in sector 3, so it stays
# small (numbers in the PR).


def tier_health(health: int, tier: int, tuning: Tuning = DEFAULT) -> int:
    """Integer math, rounded up, so no float edge case can add a point."""
    if tier != 3:
        return health
    return -(-health * tuning.overcharged_health_pct // 100)


def spawn_robot(
    world: World, kind: str, x: float, y: float, tuning: Tuning = DEFAULT, tier: int = 1
) -> Hostile:
    """Any robot of the roster by kind (overhaul), built for a sector's tier."""
    robot = _build_robot(world, kind, x, y, tuning)
    if tier != 1:
        robot.tier = tier
        robot.health = robot.max_health = tier_health(robot.max_health, tier, tuning)
    return robot


def _build_robot(world: World, kind: str, x: float, y: float, tuning: Tuning) -> Hostile:
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


def spawn_rival(
    world: World,
    x: float,
    y: float,
    protocol: str,
    tuning: Tuning = DEFAULT,
    sector: int | None = None,
):
    """The Regulator in its frozen protocol. On the floor, `sector` picks the chassis
    (sim/bosses.py). Without it, the legacy plain Regulator."""
    if protocol not in PROTOCOLS:
        raise ValueError(f"unknown protocol {protocol!r}")
    boss = BOSSES[sector] if sector is not None else REGULATOR
    health = boss.health or tuning.rival_health
    first = {"ring": tuning.ring_every, "quake": tuning.quake_every, "summon": tuning.summon_every}
    world.rival = Rival(
        x=x,
        y=y,
        radius=tuning.rival_radius,
        health=health,
        max_health=health,
        protocol=protocol,
        boot=tuning.rival_boot,
        cooldown=tuning.clamp_rest,
        timer=tuning.oscillate_interval if protocol == "lateral" else tuning.insulate_orb_interval,
        kind=boss.kind,
        sig_timer=first.get(boss.signature, 0) // 2,  # the first one comes sooner
    )
    world.events.append(Event("protocol_boot", x, y))
    return world.rival
