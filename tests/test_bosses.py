"""The Regulator's three chassis: one per sector chamber, each with a signature attack that
has its own tell, layered on the protocol (which stays the only adaptive choice)."""

from __future__ import annotations

import dataclasses

import pytest
from floorbot import enter

from overload.sim.arena import FLOOR_ARENA
from overload.sim.bosses import BOSSES, RING
from overload.sim.campaign import Campaign
from overload.sim.collision import blocked
from overload.sim.inputs import IDLE
from overload.sim.tuning import DEFAULT, Tuning
from overload.sim.world import summon_points


def chamber(sector: int, seed: int = 1) -> Campaign:
    campaign = Campaign(seed)
    enter(campaign, f"s{sector}_chamber")
    campaign.world.player.invulnerable = 10**9
    return campaign


def run_until(campaign: Campaign, kind: str, limit: int = 2000) -> list[str]:
    """Step until an event of this kind. Returns every event kind seen on the way."""
    seen = []
    for _ in range(limit):
        campaign.world.player.invulnerable = 10**9
        campaign.step(IDLE)
        kinds = [e.kind for e in campaign.world.events]
        seen += kinds
        if kind in kinds:
            return seen
    raise AssertionError(f"no {kind} event within {limit} ticks")


@pytest.mark.parametrize("sector", [1, 2, 3])
def test_each_chamber_has_its_own_chassis(sector) -> None:
    rival = chamber(sector).world.rival
    boss = BOSSES[sector]
    assert rival is not None and rival.kind == boss.kind
    assert rival.health == rival.max_health == boss.health
    assert BOSSES[1].health < BOSSES[2].health < BOSSES[3].health


def test_the_legacy_regulator_has_no_signature() -> None:
    from overload.sim.campaign import encounter_world
    from overload.sim.world import step

    world = encounter_world(1, 2, "lateral")
    assert world.rival.kind == "regulator"
    seen = []
    for _ in range(900):
        world.player.invulnerable = 10**9
        step(world, IDLE)
        seen += [e.kind for e in world.events]
    assert "boss_tell" not in seen and "rival_volley" in seen


def test_the_linesman_tells_then_throws_a_ring_of_eight() -> None:
    campaign = chamber(1)
    seen = run_until(campaign, "boss_ring")
    assert "boss_tell" in seen
    tell_at = len(seen) - seen[::-1].index("boss_tell")
    assert tell_at < len(seen)
    bolts = [p for p in campaign.world.projectiles if p.hostile]
    assert len(bolts) >= len(RING) == 8


def test_the_signature_tell_lasts_and_pauses_the_protocol() -> None:
    campaign = chamber(1)
    run_until(campaign, "boss_tell")
    rival = campaign.world.rival
    assert rival.sig_action == "tell" and rival.sig_timer == DEFAULT.ring_tell
    before = (rival.action, rival.timer, rival.cooldown)
    for _ in range(DEFAULT.ring_tell - 1):
        campaign.step(IDLE)
        assert (rival.action, rival.timer, rival.cooldown) == before, "protocol waits"


def test_the_transformer_stomps_a_wide_shockwave() -> None:
    campaign = chamber(2)
    run_until(campaign, "quake")
    waves = campaign.world.shockwaves
    assert waves and waves[-1].reach == DEFAULT.quake_reach > DEFAULT.wave_reach


def test_the_grid_core_summons_drones_on_clear_tiles_up_to_a_cap() -> None:
    campaign = chamber(3)
    run_until(campaign, "summon")
    points = summon_points(FLOOR_ARENA)
    assert len(points) == 2
    for point in points:
        assert not blocked(campaign.world, FLOOR_ARENA, point, 8.0)
    assert len(campaign.world.warps) == 2
    for _ in range(DEFAULT.summon_every * 2):
        campaign.world.player.invulnerable = 10**9
        campaign.step(IDLE)
        alive = [h for h in campaign.world.hostiles if h.health > 0]
        assert len(alive) + len(campaign.world.warps) <= DEFAULT.summon_cap + 1


def test_the_grid_core_overloads_at_half_health() -> None:
    campaign = chamber(3)
    rival = campaign.world.rival
    rival.boot = 0
    rival.health = rival.max_health // 2
    campaign.step(IDLE)
    assert rival.phase == 2 and rival.boot > 0
    assert "overload" in [e.kind for e in campaign.world.events]
    seen = run_until(campaign, "boss_spiral")
    assert "summon" not in seen, "phase 2 trades the summons for the spiral"
    shots = 0
    for _ in range(DEFAULT.spiral_ticks):
        campaign.world.player.invulnerable = 10**9
        before = len([p for p in campaign.world.projectiles if p.hostile])
        campaign.step(IDLE)
        shots += max(0, len([p for p in campaign.world.projectiles if p.hostile]) - before)
    assert shots >= 2 * (DEFAULT.spiral_ticks // DEFAULT.spiral_gap) - 2


def test_summoned_drones_short_out_with_the_core() -> None:
    campaign = chamber(3)
    run_until(campaign, "warp_in")
    assert any(h.health > 0 for h in campaign.world.hostiles)
    campaign.world.rival.health = 0
    campaign.step(IDLE)
    assert not campaign.world.hostiles and not campaign.world.warps
    assert "s3_chamber" in campaign.world.cleared


def test_chassis_tells_respect_the_readability_minimum() -> None:
    for name in ("ring_tell", "quake_tell", "summon_tell", "spiral_tell"):
        with pytest.raises(ValueError):
            Tuning(**{name: 20})
    assert dataclasses.replace(DEFAULT).ring_tell >= 30


def test_the_protocol_stays_quiet_while_a_quake_is_still_running() -> None:
    campaign = chamber(2)
    run_until(campaign, "quake")
    rival = campaign.world.rival
    for _ in range(DEFAULT.signature_quiet - 1):
        campaign.world.player.invulnerable = 10**9
        campaign.step(IDLE)
        kinds = {e.kind for e in campaign.world.events}
        assert not kinds & {"rival_tell", "rival_lunge", "rival_orb", "rival_volley"}
    reach = DEFAULT.quake_reach - DEFAULT.wave_width - DEFAULT.player_radius
    assert DEFAULT.signature_quiet * DEFAULT.wave_speed >= reach - rival.radius
