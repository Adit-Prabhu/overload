"""Overhaul step 4: Burst, one evolution per power and the second fusion, Shock Cone (the G1
production ceiling)."""

from __future__ import annotations

import dataclasses

import pytest

from overload.sim.campaign import encounter_world
from overload.sim.inputs import IDLE, InputFrame
from overload.sim.powers import DROPS, Kit, evolved
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


def test_power_guards() -> None:
    with pytest.raises(ValueError):
        dataclasses.replace(DEFAULT, burst_knock=40.0)
    with pytest.raises(ValueError):
        dataclasses.replace(DEFAULT, boost_factor=4.0)


def test_a_robot_killed_by_burst_drops_its_charge_the_same_tick() -> None:
    world = armed("burst")
    p = world.player
    breaker = spawn_robot(world, "breaker", p.x + 24, p.y)
    breaker.health = 1
    step(world, aim_right(world, power_q=True))
    assert breaker not in world.hostiles
    assert [c.kind for c in world.charges] == ["burst"]


def test_a_robot_killed_by_a_chain_is_removed() -> None:
    world = armed("spark", fragments={"spark": 3}, slots=("spark", ""))
    p = world.player
    spawn_robot(world, "sentry", p.x + 40, p.y)
    second = spawn_robot(world, "drone", p.x + 40, p.y + 30)
    second.health = 1
    for _ in range(20):
        step(world, aim_right(world, power_q=True))
        if second not in world.hostiles:
            break
    assert second not in world.hostiles
    assert any(c.kind == "spark" for c in world.charges)


def test_burst_is_shielded_while_the_regulator_boots() -> None:
    world = armed("burst")
    p = world.player
    from overload.sim.spawns import spawn_rival

    rival = spawn_rival(world, p.x + 26, p.y, "lateral")
    step(world, aim_right(world, power_q=True))
    assert rival.health == rival.max_health
    assert "rival_shielded" in {e.kind for e in world.events}


def test_knockback_stops_at_a_locked_door() -> None:
    from floorbot import enter

    from overload.sim.campaign import Campaign

    campaign = Campaign(1)
    world = campaign.world
    Kit(["burst"], {"burst": 1}, ["burst", ""]).apply(world)
    enter(campaign, "s1_hall")
    floor = campaign.arena.floor
    x, y, w, h = next(d.rect for d in floor.doors if d.id == "s1_hall>s1_bay")
    door_x = x * 16
    p = world.player
    p.x, p.y = door_x - 40, (y + h / 2) * 16
    robot = spawn_robot(world, "sentry", door_x - 16, p.y)
    for _ in range(3):
        world.player.cooldowns.clear()
        campaign.step(InputFrame(aim_x=int(door_x) + 40, aim_y=int(p.y), power_q=True))
    assert robot.x + robot.radius <= door_x + 0.01, "the shutter holds the robot in the room"


def test_a_retry_keeps_the_entry_evolutions() -> None:
    from floorbot import skip_sector

    from overload.sim.campaign import Campaign

    campaign = Campaign(1)
    Kit(["spark"], {"spark": 3}, ["spark", ""]).apply(campaign.world)
    skip_sector(campaign)
    campaign.begin_next("pressure")
    campaign.world.fragments = {"spark": 9}
    campaign.world.player.charge = 0
    campaign.step(IDLE)
    campaign.step(InputFrame(restart=True))
    assert campaign.world.fragments == {"spark": 3}
    assert evolved(campaign.world.fragments, "spark", DEFAULT)


def test_shock_cone_can_be_fused_in_real_play_and_replays_exactly(tmp_path) -> None:
    """Burst drops in sector 2, so at the second Fuse Box a real run can fuse Shock Cone.
    The recorded run, Fuse Box actions included, replays to the same hash."""
    from floorbot import play_campaign

    from overload.session.replay import Recording, play
    from overload.sim.arena import FLOOR_ARENA, arena_id
    from overload.sim.campaign import Campaign

    campaign = Campaign(2)
    recording = Recording(
        seed=2,
        tuning_id=DEFAULT.tuning_id(),
        arena_id=arena_id(FLOOR_ARENA),
        mode="campaign",
        protocols=["lateral"],
    )
    results = []

    def fuse_box(campaign, recording) -> None:
        if campaign.encounter == 2:
            results.append(campaign.fuse("spark", "burst"))
            recording.fuse_box("fuse", "spark", "burst")

    play_campaign(campaign, recording=recording, on_fuse_box=fuse_box)
    assert results == ["fused"] and "shock_cone" in campaign.world.unlocked
    recording.final_hash = campaign.state_hash()
    path = tmp_path / "shock.json"
    recording.save(path)
    assert play(Recording.load(path)).state_hash() == recording.final_hash


def test_evolved_burst_also_reaches_farther() -> None:
    plain = armed("burst")
    wide = armed("burst", fragments={"burst": 3})
    for world in (plain, wide):
        p = world.player
        spawn_robot(world, "sweeper", p.x + 52, p.y)  # beyond 44 + 5, within 56 + 5
        step(world, aim_right(world, power_q=True))
    assert plain.hostiles[-1].health == DEFAULT.sweeper_health
    assert wide.hostiles[-1].health == DEFAULT.sweeper_health - DEFAULT.burst_damage
