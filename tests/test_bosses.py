"""The Regulator's three chassis (boss rework, docs/BOSS_DESIGN.md): one per sector chamber,
each with three phases and a rotation of attacks no robot uses, layered on the protocol
(which stays the only adaptive choice)."""

from __future__ import annotations

import dataclasses
import math

import pytest
from floorbot import enter

from overload.sim.arena import FLOOR_ARENA
from overload.sim.bosses import BOSSES, RING, phase_for
from overload.sim.campaign import Campaign
from overload.sim.collision import blocked
from overload.sim.inputs import IDLE
from overload.sim.tuning import DEFAULT, Tuning
from overload.sim.world import summon_points

HOSTILE_ATTACKS = {"rival_tell", "rival_lunge", "rival_orb", "rival_volley"}


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


def hostile_shots(campaign: Campaign) -> int:
    return len([p for p in campaign.world.projectiles if p.hostile])


def start(campaign: Campaign, name: str):
    """Skip the boot and the wait, and start this kit attack now."""
    rival = campaign.world.rival
    rival.boot, rival.action = 0, "move"
    phase = BOSSES[{"linesman": 1, "transformer": 2, "grid_core": 3}[rival.kind]]
    rotation = phase.phases[rival.phase - 1].rotation
    rival.sig_index = rotation.index(name)
    rival.sig_action, rival.sig_timer = "idle", 1
    campaign.world.player.invulnerable = 10**9
    campaign.step(IDLE)
    assert rival.sig_name == name and rival.sig_action == "tell"
    return rival


def set_phase(campaign: Campaign, phase: int) -> None:
    rival = campaign.world.rival
    rival.boot = 0
    rival.health = rival.max_health * (3 - (phase - 1)) // 3 - (1 if phase > 1 else 0)
    for _ in range(phase):  # one change per phase crossed
        campaign.world.player.invulnerable = 10**9
        campaign.step(IDLE)
        rival.change = 0
    assert rival.phase == phase


def test_phases_change_at_two_thirds_and_one_third() -> None:
    boss = BOSSES[1]
    assert phase_for(boss, 48, 48) == 1
    assert phase_for(boss, 33, 48) == 1 and phase_for(boss, 32, 48) == 2
    assert phase_for(boss, 17, 48) == 2 and phase_for(boss, 16, 48) == 3
    assert phase_for(boss, 1, 48) == 3
    for sector in (1, 2, 3):
        assert len(BOSSES[sector].phases) == 3


def test_a_phase_change_shields_keeps_shots_and_restarts_the_rotation() -> None:
    campaign = chamber(1)
    rival = campaign.world.rival
    run_until(campaign, "boss_ring")
    shots = {p.id for p in campaign.world.projectiles if p.hostile}
    assert shots
    rival.health = 30
    campaign.step(IDLE)
    assert rival.phase == 2 and rival.change > 0
    still = {p.id for p in campaign.world.projectiles if p.hostile}
    assert still and still <= shots, "shots fired in phase 1 keep flying (Adit, Nov 19)"
    assert "phase_change" in [e.kind for e in campaign.world.events]
    health = rival.health
    from overload.sim.damage import damage_rival

    damage_rival(campaign.world, 5, rival.x, rival.y)
    assert rival.health == health, "shielded while it changes"
    seen = []
    for _ in range(DEFAULT.phase_change - 1):
        campaign.world.player.invulnerable = 10**9
        campaign.step(IDLE)
        seen += [e.kind for e in campaign.world.events]
    assert not set(seen) & (HOSTILE_ATTACKS | {"boss_tell"}), "nothing fires during it"


def test_an_attack_already_striking_finishes_before_the_phase_changes() -> None:
    campaign = chamber(1)
    rival = start(campaign, "live_wire")
    for _ in range(DEFAULT.wire_tell + 1):
        campaign.world.player.invulnerable = 10**9
        campaign.step(IDLE)
    assert rival.sig_action == "active" and rival.wires
    rival.health = 30
    campaign.world.player.invulnerable = 10**9
    campaign.step(IDLE)
    assert rival.phase == 1 and rival.wires, "the live lines stay until they end"
    run_until(campaign, "phase_change", DEFAULT.wire_active + 5)
    assert rival.phase == 2 and not rival.wires and rival.vent == 0


def test_a_pair_finishes_its_second_half_before_the_phase_changes() -> None:
    campaign = chamber(1)
    set_phase(campaign, 3)
    rival = start(campaign, "live_wire_twice")
    for _ in range(400):
        campaign.world.player.invulnerable = 10**9
        campaign.step(IDLE)
        if rival.sig_action == "tell" and rival.sig_step == 1:
            break
    assert rival.sig_step == 1 and rival.wires, "the second set is waiting to strike"
    second = list(rival.wires)
    rival.phase = 2  # pretend the third phase is still ahead, so a change is due
    campaign.world.player.invulnerable = 10**9
    campaign.step(IDLE)
    assert rival.phase == 2 and rival.wires == second, "the second half is not called off"
    seen = run_until(campaign, "phase_change", 400)
    assert seen.count("live_wire") >= 1 and rival.phase == 3


def test_phases_change_one_at_a_time() -> None:
    campaign = chamber(1)
    rival = campaign.world.rival
    rival.boot, rival.health = 0, 1  # past both thresholds at once
    campaign.world.player.invulnerable = 10**9
    campaign.step(IDLE)
    assert rival.phase == 2
    run_until(campaign, "phase_change", DEFAULT.phase_change + 5)
    assert rival.phase == 3


def test_the_linesman_rings_then_doubles_them() -> None:
    campaign = chamber(1)
    seen = run_until(campaign, "boss_ring")
    assert "boss_tell" in seen and hostile_shots(campaign) >= len(RING) == 8
    set_phase(campaign, 2)
    start(campaign, "double_ring")
    rings = 0
    for _ in range(DEFAULT.ring_tell + DEFAULT.ring_gap + 2):
        campaign.world.player.invulnerable = 10**9
        campaign.step(IDLE)
        rings += sum(e.kind == "boss_ring" for e in campaign.world.events)
    assert rings == 2 and hostile_shots(campaign) >= 16


def test_live_wire_hurts_on_its_lines_only_after_its_tell_then_vents() -> None:
    campaign = chamber(1)
    rival = start(campaign, "live_wire")
    player = campaign.world.player
    assert len(rival.wires) == 3
    dx, dy = rival.wires[1]
    player.x, player.y = rival.x + dx * 60, rival.y + dy * 60  # on the middle line
    for _ in range(DEFAULT.wire_tell - 2):
        player.invulnerable = 0
        charge = player.charge
        campaign.step(IDLE)
        player.x, player.y = rival.x + dx * 60, rival.y + dy * 60
        assert player.charge == charge, "the tell never hurts"
    for _ in range(4):
        player.invulnerable = 0
        campaign.step(IDLE)
        player.x, player.y = rival.x + dx * 60, rival.y + dy * 60
    assert player.charge < DEFAULT.player_max_charge, "the live line hurts"
    for _ in range(DEFAULT.wire_active + 2):
        player.invulnerable = 10**9
        campaign.step(IDLE)
    assert rival.vent > 0 and not rival.wires, "the Linesman vents after Live Wire"


def test_venting_takes_half_again_as_much_damage() -> None:
    from overload.sim.damage import damage_rival

    campaign = chamber(1)
    rival = campaign.world.rival
    rival.boot = 0
    health = rival.health
    damage_rival(campaign.world, 2, rival.x, rival.y)
    assert rival.health == health - 2
    rival.vent = 30
    damage_rival(campaign.world, 2, rival.x, rival.y)
    assert rival.health == health - 2 - 3
    hits = [e for e in campaign.world.events if e.kind == "rival_hit"]
    assert hits[-1].power == "vent" and hits[-1].ref == 3


def test_the_protocol_waits_while_it_vents() -> None:
    campaign = chamber(1)
    rival = campaign.world.rival
    rival.boot, rival.vent = 0, DEFAULT.vent_ticks
    seen = []
    for _ in range(DEFAULT.vent_ticks - 1):
        campaign.world.player.invulnerable = 10**9
        campaign.step(IDLE)
        seen += [e.kind for e in campaign.world.events]
    assert not set(seen) & (HOSTILE_ATTACKS | {"boss_tell"})


def test_the_insulator_volley_bursts_where_it_lands() -> None:
    campaign = chamber(1)
    set_phase(campaign, 2)
    rival = start(campaign, "volley")
    marks = list(rival.marks)
    assert len(marks) == 3
    run_until(campaign, "volley")
    bolts = [p for p in campaign.world.projectiles if p.hostile]
    for mx, my in marks:
        assert sum(abs(b.x - mx) < 3 and abs(b.y - my) < 3 for b in bolts) == 6


def test_the_transformer_stomps_a_wide_shockwave() -> None:
    campaign = chamber(2)
    run_until(campaign, "quake")
    waves = campaign.world.shockwaves
    assert waves and waves[-1].reach == DEFAULT.quake_reach > DEFAULT.wave_reach


def test_a_bull_charge_into_a_wall_stuns_the_transformer() -> None:
    campaign = chamber(2)
    rival = start(campaign, "charge")
    player = campaign.world.player
    player.x, player.y = rival.x + 120, rival.y  # bait it toward the east wall
    from overload.sim.bosskit import lock_aim

    lock_aim(rival, campaign.world)
    player.x = rival.x - 40  # then step aside
    seen = run_until(campaign, "charge_impact", limit=DEFAULT.charge_tell + DEFAULT.charge_ticks)
    assert "charge" in seen
    campaign.step(IDLE)
    assert rival.vent > 0, "a wall impact is its punish window"


def test_coolant_spray_fires_two_fans_of_orbs_into_each_others_gaps() -> None:
    campaign = chamber(2)
    set_phase(campaign, 2)
    start(campaign, "spray")
    run_until(campaign, "spray")
    first = hostile_shots(campaign)
    assert first == 7
    for _ in range(DEFAULT.spray_gap + 1):
        campaign.world.player.invulnerable = 10**9
        campaign.step(IDLE)
    assert hostile_shots(campaign) == 13


def test_the_grid_core_summons_drones_on_clear_tiles_up_to_a_cap() -> None:
    campaign = chamber(3)
    run_until(campaign, "summon")
    points = summon_points(FLOOR_ARENA)
    assert len(points) == 2
    for point in points:
        assert not blocked(campaign.world, FLOOR_ARENA, point, 8.0)
    assert len(campaign.world.warps) == 2
    for _ in range(900):
        campaign.world.player.invulnerable = 10**9
        campaign.step(IDLE)
        alive = [h for h in campaign.world.hostiles if h.health > 0]
        assert len(alive) + len(campaign.world.warps) <= DEFAULT.summon_cap + 1


def test_the_lattice_burns_one_color_then_the_other() -> None:
    campaign = chamber(3)
    world = campaign.world
    from overload.sim.state import Hazard

    world.hazards.append(Hazard(999, 0.0, 0.0, 16.0, 10, 100))  # an Insulate tile
    rival = start(campaign, "lattice")
    cell = DEFAULT.lattice_cell
    hazards = world.hazards
    assert hazards and all(h.kind == "lattice" and h.size == cell for h in hazards)
    assert all(h.arming >= DEFAULT.lattice_tell - 1 for h in hazards)
    assert {(int(h.x // cell) + int(h.y // cell)) % 2 for h in hazards} == {0}
    from overload.sim import floorplay

    for h in hazards:  # only inside the chamber
        assert floorplay.same_room(FLOOR_ARENA, (h.x + 16, h.y + 16), (rival.x, rival.y))
    set_phase(campaign, 2)
    world.hazards.clear()
    start(campaign, "lattice_twice")
    run_until(campaign, "lattice")
    colors = {(int(h.x // cell) + int(h.y // cell)) % 2 for h in world.hazards}
    assert colors == {0, 1}, "the second Lattice takes the other color"


def test_a_body_fits_in_a_dark_lattice_cell() -> None:
    """Standing in the middle of a dark cell, nothing burns the Surge."""
    campaign = chamber(3)
    player = campaign.world.player
    cell = DEFAULT.lattice_cell
    gx, gy = int(player.x // cell), int(player.y // cell)
    if (gx + gy) % 2 == 0:  # stand in a dark cell next door
        gx += 1
    start(campaign, "lattice")
    player.x, player.y = gx * cell + cell / 2, gy * cell + cell / 2
    for _ in range(DEFAULT.lattice_tell + DEFAULT.lattice_active):
        player.invulnerable = 0
        campaign.world.rival.vent = 0
        campaign.step(IDLE)
        player.x, player.y = gx * cell + cell / 2, gy * cell + cell / 2
        assert player.charge == DEFAULT.player_max_charge


def test_the_grid_core_overloads_and_spirals_in_phase_two() -> None:
    campaign = chamber(3)
    rival = campaign.world.rival
    rival.boot = 0
    rival.health = 53
    campaign.step(IDLE)
    assert rival.phase == 2 and rival.change > 0
    assert "overload" in [e.kind for e in campaign.world.events]
    rival.change = 0
    start(campaign, "spiral")
    run_until(campaign, "boss_spiral")
    shots = 0
    for _ in range(DEFAULT.spiral_ticks):
        campaign.world.player.invulnerable = 10**9
        before = hostile_shots(campaign)
        campaign.step(IDLE)
        shots += max(0, hostile_shots(campaign) - before)
    assert shots >= 2 * (DEFAULT.spiral_ticks // DEFAULT.spiral_gap) - 2
    campaign.step(IDLE)
    assert rival.vent > 0


def test_the_core_spiral_has_four_arms_and_a_long_vent() -> None:
    campaign = chamber(3)
    set_phase(campaign, 3)
    rival = start(campaign, "core_spiral")
    run_until(campaign, "boss_spiral")
    before = hostile_shots(campaign)
    for _ in range(DEFAULT.spiral_gap):
        campaign.world.player.invulnerable = 10**9
        campaign.step(IDLE)
    assert hostile_shots(campaign) - before == 4
    for _ in range(DEFAULT.core_spiral_ticks):
        campaign.world.player.invulnerable = 10**9
        campaign.step(IDLE)
        if rival.vent:
            break
    assert rival.vent > DEFAULT.vent_ticks - 2


def test_summoned_drones_short_out_with_the_core() -> None:
    campaign = chamber(3)
    run_until(campaign, "warp_in")
    assert any(h.health > 0 for h in campaign.world.hostiles)
    campaign.world.rival.health = 0
    campaign.step(IDLE)
    assert not campaign.world.hostiles and not campaign.world.warps
    assert "s3_chamber" in campaign.world.cleared


def test_beating_a_chassis_pays_a_spare_charge_of_every_stolen_power() -> None:
    campaign = chamber(1)
    world = campaign.world
    world.unlocked = ["spark", "blink"]
    world.bank = {"spark": 2}
    world.rival.health = 0
    campaign.step(IDLE)
    assert world.bank == {"spark": 3, "blink": 1}
    assert "boss_reward" in [e.kind for e in world.events]


def test_the_fight_time_is_kept_for_the_ending() -> None:
    from overload.sim.damage import damage_rival

    campaign = chamber(1)
    for _ in range(120):
        campaign.world.player.invulnerable = 10**9
        campaign.step(IDLE)
    rival = campaign.world.rival
    rival.boot, rival.change, rival.health = 0, 0, 1
    shot_at = campaign.world.tick
    damage_rival(campaign.world, 1, rival.x, rival.y)
    events = list(campaign.world.events)
    campaign.world.events = events
    campaign._count(events)
    assert campaign.stats["bosses"]["1"] == shot_at - campaign.boss_from
    assert 100 <= campaign.stats["bosses"]["1"] <= 125


def test_a_bull_charge_runs_through_the_surge_with_one_hit() -> None:
    """It never bulldozes the Surge down the lane: one hit, then it runs on through."""
    campaign = chamber(2)
    rival = start(campaign, "charge")
    player = campaign.world.player
    player.x, player.y = rival.x + 60, rival.y  # standing in the lane
    from overload.sim.bosskit import lock_aim

    lock_aim(rival, campaign.world)
    player.invulnerable = 0
    stood = (player.x, player.y)
    hits = 0
    for _ in range(DEFAULT.charge_tell + DEFAULT.charge_ticks):
        before = player.charge
        campaign.step(IDLE)
        hits += before > player.charge
        if rival.sig_action != "tell" and rival.sig_action != "active":
            break
    assert hits == 1
    moved = abs(player.x - stood[0]) + abs(player.y - stood[1])
    assert moved < 1.0, "an idle Surge stays where it stood, never shoved down the lane"
    assert rival.x > stood[0], "the chassis ran on past it"


def test_the_second_lattice_leaves_time_to_cross_a_cell() -> None:
    with pytest.raises(ValueError):
        Tuning(lattice_again=0)
    with pytest.raises(ValueError):
        Tuning(lattice_again=20)
    assert DEFAULT.lattice_again >= 30


def test_kit_tells_respect_the_readability_minimum() -> None:
    names = ("ring_tell", "quake_tell", "summon_tell", "spiral_tell", "wire_tell")
    for name in (*names, "volley_tell", "charge_tell", "spray_tell", "lattice_tell"):
        with pytest.raises(ValueError):
            Tuning(**{name: 40})
    assert dataclasses.replace(DEFAULT).ring_tell >= 45
    with pytest.raises(ValueError):
        Tuning(vent_ticks=30)


def test_the_protocol_stays_quiet_while_a_quake_is_still_running() -> None:
    campaign = chamber(2)
    run_until(campaign, "quake")
    rival = campaign.world.rival
    for _ in range(DEFAULT.signature_quiet - 1):
        campaign.world.player.invulnerable = 10**9
        campaign.step(IDLE)
        kinds = {e.kind for e in campaign.world.events}
        assert not kinds & HOSTILE_ATTACKS
    reach = DEFAULT.quake_reach - DEFAULT.wave_width - DEFAULT.player_radius
    assert DEFAULT.signature_quiet * DEFAULT.wave_speed >= reach - rival.radius


@pytest.mark.parametrize("sector", [1, 2, 3])
def test_every_attack_in_every_phase_runs_to_the_end(sector) -> None:
    """Each rotation entry starts, strikes and hands back to the protocol, on every phase."""
    for phase in (1, 2, 3):
        campaign = chamber(sector)
        if phase > 1:
            set_phase(campaign, phase)
        rival = campaign.world.rival
        for name in BOSSES[sector].phases[phase - 1].rotation:
            if name == "summon":
                continue
            start(campaign, name)
            for _ in range(800):
                campaign.world.player.invulnerable = 10**9
                campaign.step(IDLE)
                if rival.sig_action in ("quiet", "idle") and not rival.vent:
                    break
            assert rival.sig_action in ("quiet", "idle"), (sector, phase, name)
            rival.sig_action, rival.vent = "idle", 0
            campaign.world.projectiles.clear()
            campaign.world.hazards.clear()


@pytest.mark.parametrize(
    "seed, order, limit",
    [
        (2, ("spacing", "lateral"), 40_000),
        (3, ("lateral", "pressure"), 80_000),
        (4, ("spacing", "pressure"), 40_000),
    ],
)
def test_the_protocol_runs_at_least_half_of_every_boss_fight(seed, order, limit) -> None:
    """The protocol is the study's treatment, so the kit (its tells, attacks, vents and
    phase changes) may take at most half of the fight time per sector across the bot's
    attempts. The sampled orders include every protocol. The 1.5 s boot does not count."""
    from collections import Counter

    from floorbot import FloorBot

    from overload.sim.inputs import InputFrame

    campaign = Campaign(seed)
    bot = FloorBot(campaign)
    order = iter(order)
    share = Counter()
    # Seed 3's floor bot repeatedly loses in the bus room. Give it time to reach the
    # final boss so this test measures its protocol, rather than the bot's route time.
    for tick in range(limit):
        if campaign.stage == "fuse_box":
            campaign.begin_next(next(order))
        if campaign.stage == "ending":
            break
        frame = bot.frame(tick)
        if campaign.world.outcome == "down":
            frame = InputFrame(restart=True)
        campaign.step(frame)
        rival = campaign.world.rival
        if rival is not None and rival.health > 0 and rival.boot == 0:
            busy = rival.change or rival.vent or rival.sig_action != "idle"
            share[(campaign.encounter, not busy)] += 1
    assert campaign.stage == "ending"
    for sector in (1, 2, 3):
        total = share[(sector, True)] + share[(sector, False)]
        assert total and share[(sector, True)] / total >= 0.5, sector


@pytest.mark.parametrize("sector", [1, 2, 3])
def test_the_protocol_keeps_its_share_in_a_long_fight(sector) -> None:
    """A human takes far longer than the bot, and a long fight lets the kit run its whole
    rotation through every phase. Over a fight of about 35 to 50 s (one hit every 40 ticks)
    the protocol still runs at least 0.55 of the time, phase changes counted, under every
    protocol (Nov 19: measured 0.57 to 0.66, and 0.55 to 0.64 at twice the length)."""
    from overload.sim.damage import damage_rival
    from overload.sim.inputs import InputFrame

    for protocol in ("pressure", "spacing", "lateral"):
        campaign = Campaign(1)
        campaign.encounter = campaign.world.encounter = sector
        campaign.protocols[sector] = campaign.world.protocol = protocol
        enter(campaign, f"s{sector}_chamber")
        world = campaign.world
        acting = busy = 0
        for tick in range(1, 6000):
            rival = world.rival
            if rival is None or rival.health <= 0:
                break
            world.player.charge = DEFAULT.player_max_charge
            world.player.invulnerable = 10**6
            campaign.step(InputFrame(aim_x=int(rival.x), aim_y=int(rival.y)))
            if tick % 40 == 0 and world.rival is not None:
                damage_rival(world, 1, world.rival.x, world.rival.y)
            rival = world.rival
            if rival is not None and rival.health > 0 and rival.boot == 0:
                if rival.change or rival.vent or rival.sig_action != "idle":
                    busy += 1
                else:
                    acting += 1
        assert world.rival is None or world.rival.health <= 0, (sector, protocol)
        assert acting / (acting + busy) >= 0.55, (sector, protocol, acting / (acting + busy))


@pytest.mark.parametrize("degrees", [0, 30, 35, 45, 60])
def test_a_diagonal_bull_charge_impacts_a_chamber_wall_without_sliding(degrees: int) -> None:
    """Hitting a wall at any angle triggers charge_impact and vent right on contact."""
    campaign = chamber(2)
    world = campaign.world
    room = FLOOR_ARENA.floor.get("s2_chamber")
    ix, iy, _, _ = room.interior
    wall_y = iy * 16.0
    rival = start(campaign, "charge")
    # Place the Transformer with clear horizontal runway so every angle hits the north wall first.
    rival.x, rival.y = (ix + 5) * 16.0, wall_y + rival.radius + 45.0
    world.player.x, world.player.y = (ix + 18) * 16.0, (iy + 12) * 16.0
    rad = math.radians(degrees)
    rival.aim_x, rival.aim_y = math.sin(rad), -math.cos(rad)
    for _ in range(DEFAULT.charge_tell):
        world.player.invulnerable = 10**9
        campaign.step(IDLE)
    assert rival.sig_action == "active"

    expected_ticks = math.ceil(45.0 / (DEFAULT.charge_speed * math.cos(rad)))
    ticks = 0
    impacted = False
    while rival.sig_action == "active":
        ticks += 1
        before_y = rival.y
        world.player.invulnerable = 10**9
        campaign.step(IDLE)
        if any(e.kind == "charge_impact" for e in world.events):
            impacted = True
            break
        assert before_y > wall_y + rival.radius + 1e-6, "never slides along the wall before impact"
    assert impacted, f"charge at {degrees} deg never triggered charge_impact"
    assert expected_ticks <= ticks <= expected_ticks + 1
    assert rival.y == pytest.approx(wall_y + rival.radius)
    assert rival.vent == DEFAULT.vent_ticks


def test_a_diagonal_bull_charge_impacts_a_cover_obstacle_and_vents() -> None:
    """Glancing or diagonal contact with a chamber prop triggers charge_impact and vent."""
    campaign = chamber(2)
    world = campaign.world
    room = FLOOR_ARENA.floor.get("s2_chamber")
    rx, ry, _, _ = room.rect
    # The chamber template places an insulator prop ("I") at local tile (2, 14).
    prop_x = (rx + 2) * 16.0 + 8.0
    prop_y = (ry + 14) * 16.0 + 8.0
    rival = start(campaign, "charge")
    rival.x, rival.y = prop_x + 48.0, prop_y - 48.0
    world.player.x, world.player.y = prop_x + 120.0, prop_y - 100.0
    diag = math.sqrt(0.5)
    rival.aim_x, rival.aim_y = -diag, diag
    for _ in range(DEFAULT.charge_tell):
        world.player.invulnerable = 10**9
        campaign.step(IDLE)
    assert rival.sig_action == "active"

    seen = run_until(campaign, "charge_impact", limit=30)
    assert "charge_impact" in seen
    assert rival.vent == DEFAULT.vent_ticks


@pytest.mark.parametrize("degrees", [35, 45])
def test_a_diagonal_bull_charge_across_open_floor_never_falsely_impacts(degrees: int) -> None:
    """Unobstructed diagonal travel keeps running at full speed without false wall hits."""
    campaign = chamber(2)
    world = campaign.world
    room = FLOOR_ARENA.floor.get("s2_chamber")
    ix, iy, _, ih = room.interior
    rival = start(campaign, "charge")
    rival.x, rival.y = (ix + 5) * 16.0, (iy + ih - 4) * 16.0
    world.player.x, world.player.y = (ix + 18) * 16.0, (iy + ih - 3) * 16.0
    rad = math.radians(degrees)
    rival.aim_x, rival.aim_y = math.sin(rad), -math.cos(rad)
    for _ in range(DEFAULT.charge_tell):
        world.player.invulnerable = 10**9
        campaign.step(IDLE)
    assert rival.sig_action == "active"

    vx = rival.aim_x * DEFAULT.charge_speed
    vy = rival.aim_y * DEFAULT.charge_speed
    for _ in range(25):
        before = (rival.x, rival.y)
        world.player.invulnerable = 10**9
        campaign.step(IDLE)
        assert rival.sig_action == "active"
        assert rival.vent == 0
        assert "charge_impact" not in [e.kind for e in world.events]
        assert rival.x == pytest.approx(before[0] + vx)
        assert rival.y == pytest.approx(before[1] + vy)


@pytest.mark.parametrize(
    ("phase", "name", "next_health", "tell_elapsed"),
    [
        (1, "lattice", 53, DEFAULT.lattice_tell // 2),
        (1, "lattice", 53, DEFAULT.lattice_tell - 1),
        (2, "lattice_twice", 26, DEFAULT.lattice_tell // 2),
        (2, "lattice_twice", 26, DEFAULT.lattice_tell - 1),
    ],
)
def test_grid_core_phase_change_cancels_arming_lattice_tell_cleanly(
    phase: int, name: str, next_health: int, tell_elapsed: int
) -> None:
    """Cancelling an unstruck Lattice tell clears its arming tiles without wiping shots or
    already-active hazards, so the Surge takes zero damage during the phase change."""
    from overload.sim.state import Hazard, Projectile

    campaign = chamber(3)
    if phase > 1:
        set_phase(campaign, phase)
    world = campaign.world
    rival = start(campaign, name)
    arming_ids = {h.id for h in world.hazards if h.kind == "lattice"}
    assert arming_ids

    # Place the Surge inside one of the arming Lattice cells so any leaked tile would burn it.
    cell = next(h for h in world.hazards if h.kind == "lattice")
    world.player.x, world.player.y = cell.x + cell.size / 2, cell.y + cell.size / 2

    # Advance through the tell (including the final tick before _strike runs).
    for _ in range(tell_elapsed):
        world.player.invulnerable = 10**9
        campaign.step(IDLE)
    assert rival.sig_action == "tell" and rival.sig_step == 0

    # Add a hostile bolt and already-active hazards away from the Surge to verify preservation.
    bolt = Projectile(
        id=world.new_id(),
        x=rival.x,
        y=rival.y - 30.0,
        vx=0.0,
        vy=-0.1,
        radius=DEFAULT.bolt_radius,
        damage=DEFAULT.bolt_damage,
        hostile=True,
        ttl=120,
    )
    active_insulate = Hazard(
        id=world.new_id(),
        x=0.0,
        y=0.0,
        size=16.0,
        arming=0,
        active=100,
        kind="insulate",
    )
    active_lattice = Hazard(
        id=world.new_id(),
        x=0.0,
        y=0.0,
        size=DEFAULT.lattice_cell,
        arming=0,
        active=DEFAULT.lattice_active - 10,
        kind="lattice",
    )
    world.projectiles.append(bolt)
    world.hazards.extend([active_insulate, active_lattice])

    # Cross the phase threshold with the Surge vulnerable inside the cancelled Lattice cell.
    rival.health = next_health
    world.player.invulnerable = 0
    world.player.charge = DEFAULT.player_max_charge
    campaign.step(IDLE)
    assert rival.phase == phase + 1 and rival.change > 0
    assert "phase_change" in [e.kind for e in world.events]
    assert "lattice" not in [e.kind for e in world.events]

    remaining_ids = {h.id for h in world.hazards}
    assert not (arming_ids & remaining_ids), "arming tiles from the cancelled tell are removed"
    assert active_insulate.id in remaining_ids, "already-active insulate hazard stays intact"
    assert active_lattice.id in remaining_ids, "already-burning lattice hazard stays intact"
    assert bolt.id in {p.id for p in world.projectiles}, "hostile shots stay intact"

    for _ in range(DEFAULT.phase_change):
        world.player.invulnerable = 0
        world.player.x, world.player.y = cell.x + cell.size / 2, cell.y + cell.size / 2
        campaign.step(IDLE)
        assert "lattice" not in [e.kind for e in world.events]
        assert world.player.charge == DEFAULT.player_max_charge


def test_grid_core_phase_change_waits_for_an_already_striking_lattice() -> None:
    """Once Lattice has struck (sig_action == active), the phase change waits until it ends."""
    campaign = chamber(3)
    world = campaign.world
    rival = start(campaign, "lattice")
    run_until(campaign, "lattice", limit=DEFAULT.lattice_tell + 2)
    assert rival.sig_action == "active"
    active_ids = {h.id for h in world.hazards if h.kind == "lattice"}
    assert active_ids

    rival.health = 53
    world.player.invulnerable = 10**9
    campaign.step(IDLE)
    assert rival.phase == 1 and rival.sig_action == "active"
    assert active_ids <= {h.id for h in world.hazards}

    run_until(campaign, "phase_change", limit=DEFAULT.lattice_active + 5)
    assert rival.phase == 2
