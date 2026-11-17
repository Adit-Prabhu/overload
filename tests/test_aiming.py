"""Shots go exactly where the cursor is, and leave the caster's tip."""

from __future__ import annotations

import random

import pytest

from overload.sim.aiming import hand, muzzle
from overload.sim.arena import SUBSTATION
from overload.sim.campaign import encounter_world
from overload.sim.inputs import InputFrame
from overload.sim.tuning import DEFAULT
from overload.sim.world import step


def fresh_world():
    """No Regulator, and one idle machine in a far corner so the room never counts as clear."""
    world = encounter_world(1, 1, "lateral")
    world.rival = None
    world.hostiles = world.hostiles[:1]
    world.hostiles[0].x, world.hostiles[0].y = 400.0, 240.0
    world.hostiles[0].fire_timer = 1_000_000
    return world


@pytest.mark.parametrize("seed", range(40))
def test_every_shot_passes_through_the_cursor(seed: int) -> None:
    rng = random.Random(seed)
    world = fresh_world()
    player = world.player
    player.x, player.y = rng.uniform(120, 300), rng.uniform(80, 180)
    cursor = (
        int(player.x + rng.choice((-1, 1)) * rng.uniform(25, 120)),
        int(player.y + rng.uniform(-90, 90)),
    )
    step(world, InputFrame(aim_x=cursor[0], aim_y=cursor[1], fire=True))
    shots = [p for p in world.projectiles if not p.hostile]
    if not shots:  # the caster tip was against a prop: the shot fizzled there
        assert "fizzle" in {e.kind for e in world.events}
        return
    shot = shots[0]
    # The line the shot travels on passes through the cursor point.
    cross = (cursor[0] - shot.x) * shot.vy - (cursor[1] - shot.y) * shot.vx
    assert abs(cross) / DEFAULT.shot_speed < 1e-6
    # It left from the caster's tip, which sits at the hand on the cursor's side.
    tip = muzzle(player)
    assert (shot.x - shot.vx, shot.y - shot.vy) == pytest.approx(tip)
    assert (hand(player)[0] - player.x) * (cursor[0] - player.x) > 0


def test_the_caster_switches_hands_with_the_cursor() -> None:
    world = fresh_world()
    player = world.player
    step(world, InputFrame(aim_x=int(player.x) - 60, aim_y=int(player.y)))
    assert player.facing == -1 and hand(player)[0] < player.x
    step(world, InputFrame(aim_x=int(player.x) + 60, aim_y=int(player.y)))
    assert player.facing == 1 and hand(player)[0] > player.x


def test_a_point_blank_shot_into_a_prop_fizzles_at_it() -> None:
    world = fresh_world()
    x, y, w, h = SUBSTATION.obstacles[-1]
    player = world.player
    player.x, player.y = x - DEFAULT.player_radius - 0.5, y + h / 2  # flush with its left side
    step(world, InputFrame(aim_x=int(x + w + 40), aim_y=int(y + h / 2), fire=True))
    assert not [p for p in world.projectiles if not p.hostile]
    assert "fizzle" in {e.kind for e in world.events}
