"""The nine results in the final three fusion pairs, through their real power slots."""

from __future__ import annotations

import dataclasses

import pytest
from test_fusion import AIM, OPEN, armed, dummy, fire, fire_walled, walled
from test_pairs import bolt_at, idle

from overload.sim.inputs import InputFrame
from overload.sim.powers import cooldown_of
from overload.sim.spawns import spawn_rival, spawn_robot
from overload.sim.state import Decoy
from overload.sim.tuning import DEFAULT
from overload.sim.world import step


def test_phase_guard_teleports_and_raises_a_shield() -> None:
    world = armed("phase_guard")
    player = world.player
    bolt_at(world, AIM["aim_x"], AIM["aim_y"] - 10, 0, 2)
    fire(world)
    assert (player.x, player.y) == (AIM["aim_x"], AIM["aim_y"])
    assert player.shield_kind == "phase_guard" and not world.projectiles
    assert player.cooldowns["teleport"] == DEFAULT.phase_guard_cooldown - 1


@pytest.mark.parametrize(
    "slots", [("phase_guard", "bastion"), ("bastion", "phase_guard")], ids=["phase-q", "phase-e"]
)
def test_phase_guard_leaves_bastions_blast_intact_in_either_slot(slots) -> None:
    world = armed("phase_guard")
    world.unlocked.append("bastion")
    world.player.slots = list(slots)
    dummy(world, 290, 220)
    step(world, InputFrame(power_q=True, power_e=True, **AIM), arena=OPEN)
    assert world.player.x == AIM["aim_x"]
    assert world.player.shield_kind == "bastion"
    assert "blast" in idle(world, DEFAULT.bulwark_ticks - 1)


def test_afterimage_redirects_robot_and_regulator_tells_then_expires() -> None:
    world = armed("afterimage")
    bot = spawn_robot(world, "sentry", 130, 120)
    bot.fire_timer = DEFAULT.sentry_tell + 1
    rival = spawn_rival(world, 134, 104, "pressure")
    rival.boot = rival.cooldown = 0
    fire(world)
    assert world.decoy is not None and (world.decoy.x, world.decoy.y) == OPEN.player_spawn
    assert bot.tell_dx < 0 and rival.aim_x < 0
    idle(world, DEFAULT.decoy_ticks - 1)
    assert world.decoy is None


def test_afterimage_does_not_redirect_where_a_lunge_can_hurt() -> None:
    world = armed("afterimage")
    rival = spawn_rival(world, 160, 120, "pressure")
    rival.boot = 0
    fire(world)
    world.player.x, world.player.y = 167, 120
    world.decoy = Decoy(110, 120, 60)
    rival.action, rival.timer = "dash", 5
    rival.aim_x, rival.aim_y = 1, 0
    step(world, InputFrame(**AIM), arena=OPEN)
    assert world.player.charge == DEFAULT.player_max_charge - 1


def test_rewind_restores_the_position_and_charge_from_120_ticks_ago() -> None:
    world = armed("rewind")
    dummy(world, 290, 220)
    player = world.player
    player.charge = 4
    idle(world, 1)
    player.charge, player.x = 2, 180
    idle(world, DEFAULT.rewind_ticks - 1)
    assert len(player.history) == DEFAULT.rewind_ticks
    fire(world)
    assert (player.x, player.y, player.charge) == (*OPEN.player_spawn, 4)


def test_rewind_with_no_history_costs_nothing() -> None:
    world = armed("rewind")
    fire(world)
    assert "teleport" not in world.player.cooldowns
    assert [e.power for e in world.events if e.kind == "blink_rejected"] == ["rewind"]


def test_undertow_drags_a_robot_toward_the_takeoff_point() -> None:
    world = armed("undertow")
    target = dummy(world, 110, 152)
    fire(world, ticks=12)
    assert world.player.x == AIM["aim_x"] and target.y < 152
    field = next(field for field in world.fields if field.kind == "undertow")
    assert (field.x, field.y) == OPEN.player_spawn


def test_grapple_hits_a_robot_and_stops_in_front_of_it() -> None:
    world = armed("grapple")
    target = dummy(world, 170, 120)
    fire(world, aim_x=170, aim_y=120)
    assert 110 < world.player.x < 170 < target.x
    assert target.health == 999 - DEFAULT.grapple_damage


def test_grapple_to_a_wall_does_not_hit_a_robot_behind_it() -> None:
    world = walled("grapple")
    target = dummy(world, 177, 120)
    fire_walled(world, aim_x=177, aim_y=120)
    assert 110 < world.player.x < 145
    assert target.health == 999


def test_grapple_with_nothing_in_reach_costs_nothing() -> None:
    world = armed("grapple")
    fire(world)
    assert "teleport" not in world.player.cooldowns
    assert world.player.x == 110


def test_riptide_drags_and_stuns_but_never_moves_the_regulator() -> None:
    world = armed("riptide")
    near, far = dummy(world, 100, 158), dummy(world, 110, 220)
    rival = spawn_rival(world, 85, 105, "spacing")
    rival.boot = 100
    fire(world)
    assert near.y < 122 and near.stun >= DEFAULT.riptide_stun - 1
    assert far.y == 220 and far.stun == 0
    assert (rival.x, rival.y) == (85, 105)


def test_lightning_rod_draws_in_a_hostile_shot_only() -> None:
    world = armed("lightning_rod")
    dummy(world, 290, 220)
    fire(world)
    rod = world.fields[0]
    hostile = bolt_at(world, rod.x, rod.y + 25, 0, 0)
    friendly = bolt_at(world, rod.x, rod.y - 25, 0, 0)
    friendly.hostile = False
    idle(world, 15)
    assert hostile not in world.projectiles
    assert friendly in world.projectiles and friendly.y == rod.y - 25


def test_shield_toss_hits_a_robot_and_returns_to_the_surge() -> None:
    world = armed("shield_toss")
    robot = dummy(world, 144, 120)
    bolt_at(world, 152, 107, 0, 0)
    fire(world, ticks=DEFAULT.toss_out - 1)
    assert not world.projectiles
    assert robot.health < 999 and robot.x > 144
    assert world.fields[0].x > world.player.x
    idle(world, DEFAULT.toss_back)
    assert not world.fields


def test_mirror_field_catches_up_to_its_cap_and_returns_the_shots() -> None:
    world = armed("mirror_field", {"spark": DEFAULT.evolve_at})
    robot = dummy(world, 165, 120)
    for i in range(DEFAULT.mirror_cap + 1):
        bolt_at(world, 130, 120 + i, 0, 0)
    fire(world)
    assert world.player.caught == DEFAULT.mirror_cap
    assert len(world.projectiles) == 1 and world.projectiles[0].hostile
    kinds = idle(world, DEFAULT.mirror_ticks - 1)
    assert "mirror_release" in kinds and world.player.caught == 0
    assert len([p for p in world.projectiles if p.kind == "reflect"]) == DEFAULT.mirror_cap
    idle(world, 20)
    assert robot.health < 999


def test_mirror_field_cannot_catch_a_shot_behind_a_wall() -> None:
    world = walled("mirror_field")
    world.player.x, world.player.y = 145, 120
    shot = bolt_at(world, 169, 120, 0, 1)
    fire_walled(world)
    assert shot in world.projectiles and world.player.caught == 0


def stopped_shots(power: str, offset: int) -> int:
    world = armed(power)
    dummy(world, 290, 220)
    absorbed = 0
    for tick in range(200):
        if (tick + offset) % 12 == 0:
            y = 120 + ((tick // 12) % 5 - 2) * 7
            bolt_at(world, 177, y, -DEFAULT.bolt_speed, 0)
        step(world, InputFrame(power_q=tick == 0, aim_x=143, aim_y=120), arena=OPEN)
        absorbed += sum(event.kind == "shield_absorb" for event in world.events)
    return absorbed


def test_higher_bulwark_magnet_rarities_stop_more_shots_per_cooldown() -> None:
    rare, epic, legendary = [
        sum(stopped_shots(power, offset) for offset in (0, 3, 6, 9))
        / (cooldown_of(power, DEFAULT) / 60)
        for power in ("lightning_rod", "shield_toss", "mirror_field")
    ]
    assert rare < epic <= 1.35 * rare
    assert epic < legendary <= 1.75 * rare


@pytest.mark.parametrize(
    "change",
    [{"rewind_ticks": 0}, {"mirror_cap": 0}, {"toss_speed": 14}, {"rod_pull": -1}],
)
def test_invalid_fusion_tuning_is_rejected(change) -> None:
    with pytest.raises(ValueError):
        dataclasses.replace(DEFAULT, **change)
