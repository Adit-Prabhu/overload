"""Overhaul step 4: Burst, one evolution per power and the second fusion, Shock Cone (the G1
production ceiling)."""

from __future__ import annotations

import dataclasses

import pytest

from overload.game.flow import next_recipe
from overload.sim.campaign import encounter_world
from overload.sim.inputs import IDLE, InputFrame
from overload.sim.powers import DROPS, Kit, evolved, fuse
from overload.sim.spawns import spawn_robot
from overload.sim.state import Charge, Projectile
from overload.sim.tuning import DEFAULT
from overload.sim.world import step


def armed(*abilities: str, fragments=None, slots=("burst", "")):
    world = encounter_world(1, 1, "lateral")
    world.rival = None
    world.hostiles.clear()
    idle = spawn_robot(world, "sentry", world.player.x + 230, world.player.y)
    idle.fire_timer = 1_000_000  # keeps the room from counting as clear
    Kit(list(abilities), dict(fragments or {a: 1 for a in abilities}), list(slots)).apply(world)
    return world


def aim_right(world, **fields) -> InputFrame:
    p = world.player
    return InputFrame(aim_x=int(p.x) + 60, aim_y=int(p.y), **fields)


def test_the_breaker_carries_burst() -> None:
    assert DROPS["breaker"] == "burst"


def test_burst_hits_and_knocks_back_robots_in_its_cone_only() -> None:
    world = armed("burst")
    p = world.player
    front = spawn_robot(world, "sweeper", p.x + 25, p.y)
    behind = spawn_robot(world, "sweeper", p.x - 25, p.y)
    before = front.x
    step(world, aim_right(world, power_q=True))
    assert front.health == DEFAULT.sweeper_health - DEFAULT.burst_damage
    assert front.x > before + 4, "knocked away from the Surge"
    assert behind.health == DEFAULT.sweeper_health


def test_burst_clears_hostile_shots_in_its_cone() -> None:
    world = armed("burst")
    p = world.player
    shot = Projectile(500, p.x + 20, p.y, -1.0, 0.0, 2.5, 1, True, 100, "bolt")
    away = Projectile(501, p.x - 20, p.y, 1.0, 0.0, 2.5, 1, True, 100, "bolt")
    world.projectiles = [shot, away]
    step(world, aim_right(world, power_q=True))
    assert [s.id for s in world.projectiles if s.hostile] == [501]


def test_burst_and_shock_cone_share_one_cooldown() -> None:
    world = armed("spark", "burst", "shock_cone", slots=("burst", "shock_cone"))
    step(world, aim_right(world, power_q=True, power_e=True))
    uses = [e.kind for e in world.events if e.kind.startswith("power_")]
    assert uses == ["power_burst"], "only one pulse per tick, whichever slot is first"


def test_shock_cone_pulses_and_fires_a_fan_of_three_sparks() -> None:
    world = armed("spark", "burst", "shock_cone", slots=("shock_cone", ""))
    step(world, aim_right(world, power_q=True))
    assert sum(1 for s in world.projectiles if s.kind == "spark") == 3
    assert "burst" in {e.kind for e in world.events}


def test_two_more_charges_evolve_a_power_and_more_say_fully_evolved() -> None:
    world = armed("spark", slots=("spark", ""))
    kinds = []
    for i in range(3):
        world.charges.append(Charge(900 + i, "spark", world.player.x, world.player.y))
        step(world, IDLE)
        kinds += [e.kind for e in world.events if e.kind in ("absorb", "evolve", "fully_evolved")]
    assert kinds == ["absorb", "evolve", "fully_evolved"]
    assert evolved(world.fragments, "spark", DEFAULT)


def test_evolved_spark_chains_to_the_next_robot() -> None:
    world = armed("spark", fragments={"spark": 3}, slots=("spark", ""))
    p = world.player
    first = spawn_robot(world, "sentry", p.x + 40, p.y)
    second = spawn_robot(world, "sentry", p.x + 40, p.y + 30)
    for _ in range(20):
        step(world, aim_right(world, power_q=True))
        if "chain" in {e.kind for e in world.events}:
            break
    assert second.health == DEFAULT.sentry_health - DEFAULT.spark_chain_damage
    assert first.health < DEFAULT.sentry_health


def test_evolved_blink_gives_a_burst_of_speed() -> None:
    world = armed("blink", fragments={"blink": 3}, slots=("blink", ""))
    p = world.player
    p.x, p.y = 200.0, 120.0  # open floor in the hall
    step(world, InputFrame(aim_x=int(p.x) + 40, aim_y=int(p.y), power_q=True))
    assert p.boost > 0
    x = p.x
    step(world, InputFrame(move_x=1, aim_x=int(p.x) + 50, aim_y=int(p.y)))
    assert p.x - x == pytest.approx(DEFAULT.player_speed * DEFAULT.boost_factor)


def test_evolved_burst_reaches_wider() -> None:
    plain = armed("burst")
    wide = armed("burst", fragments={"burst": 3})
    for world in (plain, wide):
        p = world.player
        spawn_robot(world, "sweeper", p.x + 30, p.y + 32)  # about 47 degrees off the aim
        step(world, aim_right(world, power_q=True))
    assert plain.hostiles[-1].health == DEFAULT.sweeper_health
    assert wide.hostiles[-1].health == DEFAULT.sweeper_health - DEFAULT.burst_damage


def test_the_fuse_key_picks_the_next_open_recipe() -> None:
    kit = Kit(["spark", "blink", "burst"], {}, ["", ""])
    assert next_recipe(kit) == ("spark", "blink")
    assert fuse(kit, *next_recipe(kit)) == "fused"
    assert next_recipe(kit) == ("spark", "burst")
    assert fuse(kit, *next_recipe(kit)) == "fused"
    assert fuse(kit, *next_recipe(kit)) == "already_fused"
    assert fuse(Kit(["spark"], {}, ["", ""]), "blink", "burst") == "unsupported"


def test_power_guards() -> None:
    with pytest.raises(ValueError):
        dataclasses.replace(DEFAULT, burst_knock=40.0)
    with pytest.raises(ValueError):
        dataclasses.replace(DEFAULT, boost_factor=4.0)
