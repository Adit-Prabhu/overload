"""The robot roster (overhaul): each robot telegraphs before it attacks, for at least the
readability minimum, and attacks in its own way with its own projectile."""

from __future__ import annotations

import pytest

from overload.floor import WAVES
from overload.sim.campaign import encounter_world
from overload.sim.inputs import IDLE, InputFrame
from overload.sim.spawns import spawn_robot
from overload.sim.state import Shockwave
from overload.sim.tuning import DEFAULT, TICK_RATE
from overload.sim.world import step

# robot kind: (tell event, attack event, minimum tell in seconds)
ATTACKS = {
    "drone": ("tell", "bolt", 0.40),
    "relay": ("tell", "shards", 0.50),
    "sentry": ("tell", "shell", 0.50),
    "breaker": ("raise", "slam", 0.50),
    "sweeper": ("tell", "rush", 0.50),
}
SHOTS = {"drone": ("bolt", 1), "relay": ("shard", 3), "sentry": ("shell", 1)}


def lone_robot(kind: str, distance: float = 40.0):
    world = encounter_world(1, 1, "lateral")
    world.rival = None
    world.hostiles.clear()
    player = world.player
    robot = spawn_robot(world, kind, player.x + distance, player.y)
    return world, robot


@pytest.mark.parametrize("kind", sorted(ATTACKS))
def test_every_robot_attack_follows_a_full_tell(kind: str) -> None:
    tell_event, attack_event, minimum = ATTACKS[kind]
    world, robot = lone_robot(kind)
    started, attacks = None, 0
    for _ in range(900):
        world.player.invulnerable = 1_000
        step(world, IDLE)
        kinds = {e.kind for e in world.events if e.ref == robot.id}
        if tell_event in kinds:
            started = world.tick
        if attack_event in kinds:
            assert started is not None, f"{kind} attacked without a tell"
            assert world.tick - started >= minimum * TICK_RATE
            started = None
            attacks += 1
    assert attacks >= 2, kind


@pytest.mark.parametrize("kind", sorted(SHOTS))
def test_each_shooter_fires_its_own_projectile(kind: str) -> None:
    shape, count = SHOTS[kind]
    world, robot = lone_robot(kind, distance=60.0)
    for _ in range(600):
        world.player.invulnerable = 1_000
        step(world, IDLE)
        if any(e.kind in ("bolt", "shards", "shell") and e.ref == robot.id for e in world.events):
            fired = [p for p in world.projectiles if p.hostile]
            assert {p.kind for p in fired} == {shape} and len(fired) == count
            return
    pytest.fail(f"{kind} never fired")


def ring_world():
    """A world with one idle robot far away (so it never counts as cleared) and a fresh
    shockwave just behind the Surge."""
    world, idle = lone_robot("sentry", distance=230.0)
    idle.fire_timer = 1_000_000
    player = world.player
    world.shockwaves.append(Shockwave(99, player.x - 30, player.y, 9.0, False))
    return world, player


def test_a_shockwave_hurts_once_as_it_passes_and_a_dodge_slips_it() -> None:
    world, player = ring_world()
    for _ in range(40):
        step(world, IDLE)
    assert player.charge == DEFAULT.player_max_charge - 1, "hurts exactly once"
    world, player = ring_world()
    for tick in range(40):
        step(world, InputFrame(dodge=tick == 4))  # the ring reaches the Surge around tick 8
        if world.shockwaves and world.shockwaves[0].hit:
            break
    assert player.charge == DEFAULT.player_max_charge, "a dodge through the ring is free"


def test_a_sweeper_rush_hurts_on_contact() -> None:
    world, sweeper = lone_robot("sweeper", distance=50.0)
    for _ in range(200):
        step(world, IDLE)
        if world.player.charge < DEFAULT.player_max_charge:
            return
    pytest.fail("a Sweeper rush never landed on a player standing still")


def test_drones_keep_to_mid_range() -> None:
    world, drone = lone_robot("drone", distance=200.0)
    world.player.invulnerable = 10_000
    for _ in range(400):
        step(world, IDLE)
    distance = abs(drone.x - world.player.x)
    assert DEFAULT.drone_near - 8 <= distance <= DEFAULT.drone_far + 8


def test_every_wave_uses_the_roster() -> None:
    kinds = {kind for waves in WAVES.values() for wave in waves for kind, _ in wave}
    assert kinds == {"drone", "relay", "breaker", "sweeper", "sentry"}
    with pytest.raises(KeyError):
        spawn_robot(encounter_world(1, 1, "lateral"), "toaster", 0, 0)


def test_the_slam_reaches_exactly_as_far_as_its_tell_ring() -> None:
    """The ring hits within `wave_reach` and no farther, the radius the tell ring shows."""
    from overload.sim.robots import _shockwaves

    for distance, hurt in ((DEFAULT.wave_reach - 2, True), (DEFAULT.wave_reach + 3, False)):
        world, idle = lone_robot("sentry", distance=230.0)
        idle.fire_timer = 1_000_000
        player = world.player
        for dy in (0.0, distance):  # straight right and straight below: a true circle
            world.player.charge = DEFAULT.player_max_charge
            world.player.invulnerable = 0
            dx = distance if dy == 0.0 else 0.0
            world.shockwaves = [Shockwave(1, player.x - dx, player.y - dy, 9.0, False)]
            for _ in range(80):
                _shockwaves(world, DEFAULT)
            assert (player.charge < DEFAULT.player_max_charge) == hurt, (distance, dy)


def test_a_sentry_never_starts_inside_its_tell() -> None:
    import dataclasses

    with pytest.raises(ValueError):
        dataclasses.replace(DEFAULT, sentry_interval=90, sentry_tell=48)


def test_robots_are_built_for_their_sector() -> None:
    """Sector 3 fields Overcharged variants: more health, faster walking and shorter rests.
    Sector 2's Cooled variants keep stock stats (only their colors change). Tells and punish
    windows never change."""
    import math

    from overload.sim.spawns import TIER_HEALTH, TIER_REST

    world = encounter_world(1, 1, "lateral")
    for kind in ATTACKS:
        stock = spawn_robot(world, kind, 100, 100)
        for tier in (2, 3):
            tough = spawn_robot(world, kind, 100, 100, tier=tier)
            assert tough.tier == tier
            assert tough.max_health == math.ceil(stock.max_health * TIER_HEALTH[tier])
            assert tough.max_health >= stock.max_health
    assert TIER_REST[3] < TIER_REST[2] == TIER_REST[1] == 1.0
    assert TIER_HEALTH[3] > TIER_HEALTH[2] == 1.0


def test_warped_robots_take_the_tier_of_their_room() -> None:
    from floorbot import enter

    from overload.sim.campaign import Campaign

    for room, tier in (("s1_hall", 1), ("s2_yard", 2), ("s3_core", 3)):
        campaign = Campaign(1)
        enter(campaign, room)
        for _ in range(DEFAULT.warp_tell + 2):
            campaign.world.player.invulnerable = 10**9
            campaign.step(IDLE)
        assert campaign.world.hostiles
        assert {h.tier for h in campaign.world.hostiles} == {tier}, room


def test_a_tougher_robot_keeps_its_tell_length() -> None:
    world = encounter_world(1, 1, "lateral")
    world.hostiles.clear()
    drone = spawn_robot(world, "drone", world.player.x + 60, world.player.y, tier=3)
    drone.fire_timer = 3
    for _ in range(4):
        step(world, IDLE)
    assert drone.fire_timer > DEFAULT.drone_tell, "a shorter rest, but never a shorter tell"
