"""The fused powers of the pairs Bulwark and Magnet join, first half (sim/pairs.py): what
each one does, what it never does, and its guards."""

from __future__ import annotations

import dataclasses

import pytest
from test_fusion import AIM, OPEN, armed, dummy, fire

from overload.sim.inputs import IDLE, InputFrame
from overload.sim.state import Projectile
from overload.sim.tuning import DEFAULT
from overload.sim.world import step


def bolt_at(world, x: float, y: float, vx: float, vy: float) -> Projectile:
    shot = Projectile(world.new_id(), x, y, vx, vy, DEFAULT.bolt_radius, 1, True, 200, "bolt")
    world.projectiles.append(shot)
    return shot


def idle(world, ticks: int) -> list[str]:
    seen = []
    for _ in range(ticks):
        step(world, InputFrame(**AIM), arena=OPEN)
        seen += [e.kind for e in world.events]
    return seen


# Spark + Bulwark -----------------------------------------------------------------------------


def test_static_guard_eats_a_shot_and_sparks_at_the_nearest_robot() -> None:
    world = armed("static_guard")
    robot = dummy(world, 170, 120)
    fire(world)
    player = world.player
    assert player.shield > 0 and player.shield_kind == "static_guard"
    bolt_at(world, player.x + 20, player.y, -2.0, 0.0)
    idle(world, 30)
    assert player.charge == DEFAULT.player_max_charge
    assert robot.health < 999, "the eaten shot came back as a spark"


def test_tesla_coil_strikes_robots_and_soaks_the_shots_that_hit_it() -> None:
    world = armed("tesla_coil")
    robot = dummy(world, 190, 120)
    fire(world)
    coil = next(f for f in world.fields if f.kind == "coil")
    shot = bolt_at(world, coil.x, coil.y - 20, 0.0, 2.0)  # falls onto the coil
    idle(world, 60)
    assert robot.health < 999 and shot not in world.projectiles
    idle(world, DEFAULT.coil_ticks)
    assert not [f for f in world.fields if f.kind == "coil"], "it runs out"


def test_capacitor_armor_eats_three_hits_then_bursts_into_sparks() -> None:
    world = armed("capacitor_armor")
    dummy(world, 170, 120)
    fire(world)
    player = world.player
    from overload.sim.damage import hurt_player

    for _ in range(DEFAULT.capacitor_hits):
        player.invulnerable = 0
        hurt_player(world, 1, DEFAULT)
    assert player.charge == DEFAULT.player_max_charge
    kinds = idle(world, 1)
    assert "armor_release" in kinds and player.armor == 0
    player.invulnerable = 0
    hurt_player(world, 1, DEFAULT)
    assert player.charge == DEFAULT.player_max_charge - 1, "a fourth hit lands"


# Spark + Magnet ------------------------------------------------------------------------------


def test_lodestone_drags_robots_near_its_path() -> None:
    world = armed("lodestone")
    robot = dummy(world, 170, 140)  # beside the path, not on it
    fire(world)
    idle(world, 40)
    assert robot.y < 140, "dragged toward the slow spark as it passed"


def test_ion_hook_yanks_the_robot_it_hits_and_stuns_it() -> None:
    world = armed("ion_hook")
    robot = dummy(world, 190, 120)
    fire(world)
    kinds = idle(world, 30)
    assert "hooked" in kinds
    player = world.player
    assert abs(robot.x - player.x) < robot.radius + 12 and robot.health < 999
    assert robot.stun > 0


def test_a_stunned_robot_does_nothing() -> None:
    world = armed("spark")
    robot = dummy(world, 190, 120)
    robot.fire_timer, robot.stun = 1, 30
    seen = idle(world, 20)
    assert "shell" not in seen


def test_magrail_pierces_a_line_and_drags_and_never_moves_the_regulator() -> None:
    world = armed("magrail")
    near, far = dummy(world, 140, 120), dummy(world, 200, 120)
    off = dummy(world, 160, 170)
    fire(world)
    assert near.health < 999 and far.health < 999 and off.health == 999
    assert near.x > 140, "dragged along the rail"


def test_magrail_slams_a_robot_into_a_wall_for_more() -> None:
    world = armed("magrail")
    world.player.x = 200.0  # the room's east edge (x 320) inside the rail's reach
    against = dummy(world, 312, 120)  # right at the edge
    fire(world, aim_x=300, aim_y=120)
    assert 999 - against.health == DEFAULT.magrail_damage + DEFAULT.magrail_slam


# Burst + Bulwark -----------------------------------------------------------------------------


def test_bastion_ends_its_bubble_in_a_blast() -> None:
    world = armed("bastion")
    robot = dummy(world, 130, 120)
    fire(world)
    kinds = idle(world, DEFAULT.bulwark_ticks + 2)
    assert "blast" in kinds and robot.health == 999 - DEFAULT.bastion_damage


def test_reflector_wave_shoves_once_and_turns_shots() -> None:
    world = armed("reflector_wave")
    robot = dummy(world, 140, 120)
    bolt_at(world, 150, 140, -1.0, 0.0)  # off the robot's line, so its spark flies past
    fire(world)
    idle(world, DEFAULT.reflector_ticks)
    assert robot.health == 999 - DEFAULT.reflector_damage, "struck once, however long it rode"
    assert robot.x > 140, "shoved ahead of the wall"
    assert not [p for p in world.projectiles if p.hostile]
    assert [p for p in world.projectiles if p.kind == "reflect"]


def test_fortress_keeps_shots_out_and_blasts_robots_that_touch_it() -> None:
    world = armed("fortress")
    robot = dummy(world, 140, 120)
    fire(world)
    player = world.player
    bolt_at(world, player.x, player.y - 60, 0.0, 2.0)
    idle(world, 60)
    assert player.charge == DEFAULT.player_max_charge and robot.health < 999


# Burst + Magnet ------------------------------------------------------------------------------


def test_vortex_cone_pulls_the_robots_in_its_cone_and_hurts_them() -> None:
    world = armed("vortex_cone")
    robot = dummy(world, 150, 120)
    behind = dummy(world, 70, 120)
    fire(world)
    assert robot.x < 150 and robot.health == 999 - DEFAULT.vortex_damage
    assert behind.health == 999


def test_implosion_draws_robots_together_then_blasts() -> None:
    world = armed("implosion")
    a, b = dummy(world, 150, 100), dummy(world, 150, 140)
    fire(world, aim_x=150, aim_y=120)
    gap = abs(a.y - b.y)
    kinds = idle(world, DEFAULT.implosion_ticks + 1)
    assert abs(a.y - b.y) < gap and "blast" in kinds and a.health < 999


def test_gravity_well_eats_shots_and_ends_in_a_heavy_blast() -> None:
    world = armed("gravity_well")
    robot = dummy(world, 160, 140)
    fire(world, aim_x=160, aim_y=120)
    well = next(f for f in world.fields if f.kind == "well")
    bolt_at(world, well.x + 30, well.y, 0.0, 0.0)  # a shot lingering inside its reach
    idle(world, DEFAULT.well_ticks + 1)
    assert not [p for p in world.projectiles if p.hostile]
    assert 999 - robot.health >= DEFAULT.well_damage


# Rules every new power keeps -----------------------------------------------------------------


@pytest.mark.parametrize("power", ["magrail", "vortex_cone", "implosion", "gravity_well"])
def test_nothing_moves_the_regulator(power) -> None:
    from overload.sim.spawns import spawn_rival

    world = armed(power)
    rival = spawn_rival(world, 160, 120, "lateral")
    rival.boot = 10**6  # it stands still on its own, so only the power could move it
    where = (rival.x, rival.y)
    fire(world, aim_x=160, aim_y=120)
    for _ in range(DEFAULT.well_ticks + 2):
        step(world, IDLE, arena=OPEN)
    assert (round(rival.x), round(rival.y)) == (round(where[0]), round(where[1]))


@pytest.mark.parametrize(
    "change",
    [
        {"lodestone_pull": 20.0},
        {"reflector_speed": 20.0},
        {"vortex_pull": 40.0},
        {"magrail_drag": 80.0},
        {"coil_interval": 0},
        {"capacitor_hits": 0},
    ],
)
def test_the_new_tuning_is_guarded(change) -> None:
    with pytest.raises(ValueError):
        dataclasses.replace(DEFAULT, **change)
