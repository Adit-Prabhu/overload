"""Bulwark (from the Sentry) and Magnet (from the Sweeper), powers spec section 3: what they
do, what they never do, their evolutions, their drops and their tuning guards."""

from __future__ import annotations

import pytest
from test_powers import ROOM, bare_world, kit_with, press

from overload.sim.inputs import IDLE
from overload.sim.powers import COOLDOWN_KEYS, DROPS, EVOLUTIONS
from overload.sim.spawns import spawn_robot
from overload.sim.state import Charge, Projectile, Shockwave
from overload.sim.tuning import DEFAULT, Tuning
from overload.sim.world import step


def hostile_shot(world, x: float, y: float, vx: float, vy: float) -> Projectile:
    shot = Projectile(world.new_id(), x, y, vx, vy, DEFAULT.bolt_radius, 1, True, 200, "bolt")
    world.projectiles.append(shot)
    return shot


def evolve(kit, power: str):
    kit.fragments[power] = DEFAULT.evolve_at
    return kit


# Drops and families ---------------------------------------------------------------------------


def test_sentries_and_sweepers_drop_their_powers() -> None:
    assert DROPS["sentry"] == "bulwark" and DROPS["sweeper"] == "magnet"
    world = bare_world()
    for kind in ("sentry", "sweeper"):
        spawn_robot(world, kind, 60, 90, DEFAULT).health = 0
    step(world, IDLE, arena=ROOM)
    assert sorted(c.kind for c in world.charges) == ["bulwark", "magnet"]
    assert EVOLUTIONS["bulwark"] == "REFLECT" and EVOLUTIONS["magnet"] == "CRUSH"
    assert COOLDOWN_KEYS["bulwark"] == "shield" and COOLDOWN_KEYS["magnet"] == "pull"


# Bulwark --------------------------------------------------------------------------------------


def test_the_bubble_eats_hostile_shots_and_only_for_its_time() -> None:
    world = bare_world(kit_with("bulwark", slots=("bulwark", "")))
    player = world.player
    press(world, power_q=True)
    assert player.shield == DEFAULT.bulwark_ticks - 1
    assert "power_bulwark" in [e.kind for e in world.events]
    hostile_shot(world, player.x + 30, player.y, -2.0, 0.0)
    for _ in range(20):
        step(world, IDLE, arena=ROOM)
    assert player.charge == DEFAULT.player_max_charge, "the shot fizzled on the bubble"
    assert not [p for p in world.projectiles if p.hostile]
    for _ in range(DEFAULT.bulwark_ticks):
        step(world, IDLE, arena=ROOM)
    assert player.shield == 0
    hostile_shot(world, player.x + 30, player.y, -2.0, 0.0)
    for _ in range(20):
        step(world, IDLE, arena=ROOM)
    assert player.charge < DEFAULT.player_max_charge, "after the bubble, shots land again"
    assert player.cooldowns.get("shield", 0) > 0


def test_the_bubble_never_stops_shockwaves_or_the_surges_own_shots() -> None:
    world = bare_world(kit_with("bulwark", slots=("bulwark", "")))
    player = world.player
    press(world, power_q=True)
    friendly = Projectile(world.new_id(), player.x + 6, player.y, 2.0, 0.0, 1.5, 1, False, 50)
    world.projectiles.append(friendly)
    world.shockwaves.append(Shockwave(world.new_id(), player.x - 20, player.y, 5.0, False))
    for _ in range(12):
        step(world, IDLE, arena=ROOM)
    assert player.charge < DEFAULT.player_max_charge, "a shockwave still hurts"
    assert any(e.kind == "shield_absorb" for e in world.events) is False


def test_reflect_sends_an_eaten_shot_back_as_a_spark() -> None:
    world = bare_world(evolve(kit_with("bulwark", slots=("bulwark", "")), "bulwark"))
    player = world.player
    press(world, power_q=True)
    hostile_shot(world, player.x + 30, player.y, -2.0, 0.0)
    reflected, sparks = [], []
    for _ in range(20):
        step(world, IDLE, arena=ROOM)
        now = [e for e in world.events if e.kind == "shield_reflect"]
        if now:  # the moment it reflects (it soon meets the room's middle wall)
            sparks = [p for p in world.projectiles if p.kind == "reflect" and not p.hostile]
        reflected += now
    assert len(reflected) == 1
    assert sparks and sparks[0].vx > 0, "it flies back the way the shot came"


# Magnet ---------------------------------------------------------------------------------------


def test_a_field_drags_robots_and_charges_to_its_center_without_damage() -> None:
    world = bare_world(kit_with("magnet", slots=("magnet", "")))
    player = world.player
    robot = spawn_robot(world, "sweeper", player.x + 60, player.y + 30, DEFAULT)
    robot.fire_timer = 10**6
    health = robot.health
    charge = Charge(world.new_id(), "spark", player.x + 30, player.y + 30)
    world.charges.append(charge)
    press(world, power_q=True, aim_x=int(player.x + 45), aim_y=int(player.y + 30))
    field = world.fields[0]
    assert abs(field.x - (player.x + 45)) < 4 and abs(field.y - (player.y + 30)) < 4
    before = abs(robot.x - field.x) + abs(robot.y - field.y)
    ends = []
    for _ in range(DEFAULT.magnet_ticks):
        step(world, IDLE, arena=ROOM)
        ends += [e for e in world.events if e.kind == "magnet_end"]
    assert abs(robot.x - field.x) + abs(robot.y - field.y) < before
    assert abs(charge.x - field.x) < 15 and robot.health == health
    assert not world.fields
    assert len(ends) == 1 and ends[0].ref == 0, "no CRUSH unless it evolved"


def test_crush_hurts_what_is_left_in_the_field() -> None:
    world = bare_world(evolve(kit_with("magnet", slots=("magnet", "")), "magnet"))
    player = world.player
    robot = spawn_robot(world, "sweeper", player.x + 40, player.y, DEFAULT)
    robot.fire_timer = 10**6
    health = robot.health
    press(world, power_q=True, aim_x=int(player.x + 40), aim_y=int(player.y))
    for _ in range(DEFAULT.magnet_ticks + 1):
        step(world, IDLE, arena=ROOM)
    assert robot.health == health - DEFAULT.magnet_crush_damage


def test_a_field_lands_short_of_walls_and_never_past_them() -> None:
    from overload.sim.inputs import InputFrame
    from overload.sim.powers import place_point

    world = bare_world()
    world.player.x, world.player.y = 91.0, 40.0  # flush against the room's middle wall
    aim = InputFrame(aim_x=200, aim_y=40)
    spot = place_point(world, aim, DEFAULT, ROOM, DEFAULT.magnet_range, 1.0)
    assert spot is not None and spot[0] < 96, "it stops at the wall's face"
    assert place_point(world, aim, DEFAULT, ROOM, DEFAULT.magnet_range, 6.0) is None


def test_a_field_with_nowhere_to_go_is_rejected_and_costs_nothing(monkeypatch) -> None:
    from overload.sim import powers

    world = bare_world(kit_with("magnet", slots=("magnet", "")))
    monkeypatch.setattr(powers, "place_point", lambda *args: None)  # nowhere is valid
    press(world, power_q=True)
    kinds = [e.kind for e in world.events]
    assert not world.fields
    assert "magnet_rejected" in kinds and "power_magnet" not in kinds
    assert world.player.cooldowns.get("pull", 0) == 0, "a rejected use keeps its cooldown free"


def test_a_field_never_moves_the_regulator() -> None:
    from floorbot import enter

    from overload.sim.campaign import Campaign
    from overload.sim.powers import Kit

    campaign = Campaign(1)
    enter(campaign, "s1_chamber")
    world = campaign.world
    Kit(unlocked=["magnet"], fragments={"magnet": 1}, slots=["magnet", ""]).apply(world)
    rival = world.rival
    rival.boot = 10**6  # stands still
    where = (rival.x, rival.y)
    from overload.sim.inputs import InputFrame

    campaign.step(InputFrame(aim_x=int(rival.x), aim_y=int(rival.y), power_q=True))
    for _ in range(DEFAULT.magnet_ticks):
        world.player.invulnerable = 10**6
        campaign.step(IDLE)
    assert (rival.x, rival.y) == where


def test_the_new_tuning_is_guarded() -> None:
    for bad in (
        {"bulwark_radius": 4.0},
        {"bulwark_ticks": 0},
        {"magnet_pull": 20.0},
        {"magnet_pull": 0.0},
        {"magnet_ticks": 0},
    ):
        with pytest.raises(ValueError):
            Tuning(**bad)


def _hits_standing(sector: int, protocol: str, power: str | None, offset: int) -> int:
    """A Surge that stands and shoots at the chassis, pressing E whenever it is ready from
    tick `offset` on, kept alive and the chassis kept in phase 1. The hits it takes."""
    from floorbot import enter

    from overload.sim.campaign import Campaign
    from overload.sim.inputs import InputFrame
    from overload.sim.powers import Kit

    campaign = Campaign(1)
    campaign.encounter = campaign.world.encounter = sector
    campaign.protocols[sector] = campaign.world.protocol = protocol
    unlocked = ["spark"] + ([power] if power else [])
    slots = ["spark", power or ""]
    Kit(unlocked=unlocked, fragments={p: 1 for p in unlocked}, slots=slots).apply(campaign.world)
    enter(campaign, f"s{sector}_chamber")
    world = campaign.world
    world.player.y += 50
    hits = 0
    for tick in range(1800):
        rival = world.rival
        rival.health = rival.max_health
        world.player.charge = DEFAULT.player_max_charge
        aim = {"aim_x": int(rival.x), "aim_y": int(rival.y)}
        campaign.step(InputFrame(**aim, fire=True, power_e=tick >= offset))
        hits += sum(e.kind == "player_hit" for e in world.events)
    return hits


@pytest.mark.parametrize("sector", [1, 3])
def test_a_shield_never_trivializes_a_projectile_protocol(sector) -> None:
    """GDD: no loadout may make a tactic trivial. Against Oscillate, the most projectile-heavy
    protocol, a Surge standing in the open with Bulwark on every cooldown still takes at
    least 70 percent of the hits it takes without it. Averaged over four timings of the
    first press, since one timing can line the bubble up with the volleys by luck (measured
    over eight timings and a minute: 0.81 to 1.00 under every chassis and protocol)."""
    offsets = (0, 20, 40, 60)
    without = sum(_hits_standing(sector, "lateral", None, o) for o in offsets)
    shielded = sum(_hits_standing(sector, "lateral", "bulwark", o) for o in offsets)
    assert without > 0 and shielded >= 0.7 * without


def test_a_field_never_drags_a_charge_through_a_wall() -> None:
    from overload.sim.state import Device

    world = bare_world()
    # The room's middle wall runs x 96 to 112, y 0 to 80. A charge east of it, a field west.
    charge = Charge(world.new_id(), "spark", 120.0, 40.0)
    world.charges.append(charge)
    world.fields.append(Device(world.new_id(), "magnet", 86.0, 40.0, 86.0, 40.0, 30))
    for _ in range(30):
        step(world, IDLE, arena=ROOM)
    assert charge.x >= 112.0, "walls win: it stays on its own side"


def test_reflected_sparks_never_chain_through_sparks_evolution() -> None:
    """REFLECT is Bulwark's evolution. Its sparks do not also pick up CHAIN from an evolved
    Spark, so the two evolutions stay separate."""
    kit = evolve(evolve(kit_with("bulwark", "spark", slots=("bulwark", "")), "bulwark"), "spark")
    world = bare_world(kit)
    player = world.player
    press(world, power_q=True)
    hostile_shot(world, player.x + 30, player.y, -2.0, 0.0)
    kinds = set()
    for _ in range(20):
        step(world, IDLE, arena=ROOM)
        kinds |= {p.kind for p in world.projectiles if not p.hostile}
    assert "reflect" in kinds and "spark" not in kinds
