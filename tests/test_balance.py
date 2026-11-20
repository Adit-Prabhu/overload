"""The balance pass (docs/POWERS_AND_FUSION.md section 5, section 9 step 8). tools/balance.py
prints the full numbers. These tests hold the fixes it led to (Nov 19)."""

from __future__ import annotations

import sys
from dataclasses import replace
from pathlib import Path

import pytest
from floorbot import enter

from overload.sim.campaign import Campaign
from overload.sim.fusions import _strike
from overload.sim.tuning import DEFAULT

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from overload.sim.powers import FUSED  # noqa: E402
from tools.balance import FLOOR, fight  # noqa: E402


def chamber(sector: int = 3) -> Campaign:
    campaign = Campaign(1)
    enter(campaign, f"s{sector}_chamber")
    campaign.world.rival.change = campaign.world.rival.boot = 0
    return campaign


@pytest.mark.parametrize("kind", ["field", "fortress"])
def test_field_powers_strike_a_chassis_for_the_chassis_damage(kind) -> None:
    campaign = chamber()
    world = campaign.world
    rival = world.rival
    before = rival.health
    if kind == "field":
        _strike(world, rival, 5, tuning=DEFAULT, field=True)
    else:
        _strike(world, rival, 5, "fortress", DEFAULT)
    assert before - rival.health == DEFAULT.chassis_field_damage


@pytest.mark.parametrize("kind", ["coil", "fortress", "toss"])
def test_a_real_coil_fortress_or_toss_strikes_a_chassis_for_one(kind) -> None:
    """Through the real field ticks (pairs.py), not a direct call: removing the cap from
    any of the three call sites fails here."""
    from overload.sim.inputs import IDLE
    from overload.sim.state import Device

    campaign = chamber()
    world = campaign.world
    rival = world.rival
    timer = {
        "coil": DEFAULT.coil_interval + 1,
        "fortress": DEFAULT.fortress_interval + 1,
        "toss": DEFAULT.toss_out + DEFAULT.toss_back,
    }[kind]
    world.fields.append(Device(world.new_id(), kind, rival.x, rival.y, 1.0, 0.0, timer))
    hits = []
    for _ in range(3):
        world.player.invulnerable = 10**9
        rival.vent = 0
        campaign.step(IDLE)
        hits += [e.ref for e in world.events if e.kind == "rival_hit"]
    assert hits and set(hits) == {DEFAULT.chassis_field_damage}


def test_other_strikes_on_a_chassis_take_full_damage() -> None:
    campaign = chamber()
    world = campaign.world
    rival = world.rival
    before = rival.health
    _strike(world, rival, 5)  # a bolt, a blast that is not a field
    assert before - rival.health == 5


def test_chassis_field_damage_must_be_positive() -> None:
    with pytest.raises(ValueError):
        replace(DEFAULT, chassis_field_damage=0)


@pytest.mark.parametrize(
    "power, protocol",
    [
        ("shield_toss", "pressure"),
        ("fortress", "pressure"),
        ("ion_hook", "lateral"),
        ("tesla_coil", "lateral"),
    ],
)
def test_no_fused_power_makes_the_grid_core_trivial(power, protocol) -> None:
    """The four cases the Nov 19 balance pass found under the floor (0.61 to 0.66 of the
    fight time with the pair's two base powers). Now 0.85 or more."""
    (a, b), _ = FUSED[power]
    without = fight(1, 3, protocol, (a, b), DEFAULT)
    with_power = fight(1, 3, protocol, (power, a), DEFAULT)
    assert with_power / without >= FLOOR
