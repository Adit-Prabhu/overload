"""Task 6: the Regulator's protocols and the three-encounter campaign.

Acceptance: each protocol is beatable with every legal loadout (here, the starting loadout:
the gun and dodge, since powers arrive with task 8), stats are identical across protocols,
tells meet the readability minimums, and retries restore the entry state exactly.
"""

from __future__ import annotations

import dataclasses
import math

import pytest
from floorbot import enter, play_campaign, skip_sector

from overload.session.replay import Recording, play
from overload.sim.arena import FLOOR_ARENA, arena_id
from overload.sim.campaign import ENCOUNTERS, Campaign, encounter_world
from overload.sim.inputs import IDLE, InputFrame
from overload.sim.state import state_hash
from overload.sim.tuning import DEFAULT, TICK_RATE
from overload.sim.world import PROTOCOLS, step

ATTACKS = {"rival_lunge", "rival_orb", "rival_volley"}


def scripted_player(world, tick: int, near: float = 90, far: float = 135) -> InputFrame:
    """A plain but competent player: aim at the Regulator, hold a distance band while
    strafing, dodge as a tell finishes, step out of hazard tiles and dodge out of armed ones."""
    player, rival = world.player, world.rival
    if rival is None or rival.health <= 0:
        return IDLE
    dx, dy = rival.x - player.x, rival.y - player.y
    distance = math.sqrt(dx * dx + dy * dy) or 1.0
    ux, uy = dx / distance, dy / distance
    side = 1 if (tick // 150) % 2 == 0 else -1
    if distance < near:
        mx, my = -ux, -uy
    elif distance > far:
        mx, my = ux, uy
    else:
        mx, my = -uy * side, ux * side
    trapped = False
    for hazard in world.hazards:
        cx, cy = hazard.x + hazard.size / 2, hazard.y + hazard.size / 2
        if abs(player.x - cx) < 16 and abs(player.y - cy) < 16:
            mx, my = player.x - cx, player.y - cy
            trapped = trapped or hazard.arming == 0
    sx = 0 if abs(mx) < 0.3 else (1 if mx > 0 else -1)
    sy = 0 if abs(my) < 0.3 else (1 if my > 0 else -1)
    dodge = trapped or (rival.action == "tell" and rival.timer <= 4)
    return InputFrame(sx, sy, int(rival.x), int(rival.y), fire=True, dodge=dodge)


def fight(protocol: str, band: tuple[float, float], limit: int = 3600):
    """One encounter against `protocol`. Returns the world and how many attacks it made."""
    world = encounter_world(1, 2, protocol)
    attacks = 0
    for tick in range(limit):
        step(world, scripted_player(world, tick, *band))
        attacks += sum(1 for event in world.events if event.kind in ATTACKS)
        if world.outcome != "playing":
            break
    return world, attacks


# Protocols -----------------------------------------------------------------------------------


@pytest.mark.parametrize("protocol", PROTOCOLS)
@pytest.mark.parametrize("band", [(90, 135), (60, 100)], ids=["mid", "close"])
def test_every_protocol_is_beatable_with_the_starting_loadout(
    protocol: str, band: tuple[float, float]
) -> None:
    world, attacks = fight(protocol, band)
    assert world.outcome == "clear", (protocol, band, world.player.charge)
    assert attacks >= 2, "the Regulator must actually fight back for this to mean anything"


def test_a_clamp_lunge_reaches_a_player_who_stands_still() -> None:
    world = encounter_world(1, 2, "pressure")
    world.hostiles.clear()
    for _ in range(600):
        step(world, IDLE)
        if world.player.charge < DEFAULT.player_max_charge:
            return
    pytest.fail("Clamp never landed a lunge on a still target")


@pytest.mark.parametrize("protocol", PROTOCOLS)
def test_every_regulator_attack_follows_a_full_tell(protocol: str) -> None:
    world = encounter_world(5, 1, protocol)
    world.hostiles.clear()
    tell_started = None
    attacks = 0
    for _ in range(1500):
        world.player.invulnerable = 1_000  # keep the fight going to watch the pattern
        step(world, IDLE)
        kinds = {event.kind for event in world.events}
        if "rival_tell" in kinds:
            tell_started = world.tick
        if kinds & ATTACKS:
            assert tell_started is not None
            assert world.tick - tell_started >= 0.50 * TICK_RATE
            tell_started = None
            attacks += 1
    assert attacks >= 2


def test_clamp_recovers_for_at_least_0_6_s_after_a_lunge() -> None:
    world = encounter_world(5, 1, "pressure")
    world.hostiles.clear()
    lunge_end = None
    for _ in range(1500):
        world.player.invulnerable = 1_000
        step(world, IDLE)
        rival = world.rival
        if rival.action == "recover" and lunge_end is None:
            lunge_end = world.tick
        if "rival_tell" in {e.kind for e in world.events} and lunge_end is not None:
            assert world.tick - lunge_end >= 0.60 * TICK_RATE
            return
    pytest.fail("no second lunge observed")


def test_protocol_boot_shields_the_regulator() -> None:
    world = encounter_world(1, 1, "lateral")
    rival = world.rival
    assert rival.boot == DEFAULT.rival_boot
    for _ in range(40):
        step(world, InputFrame(aim_x=int(rival.x), aim_y=int(rival.y), fire=True))
    assert rival.health == rival.max_health


def test_clamp_dash_hurts_on_contact() -> None:
    world = encounter_world(1, 1, "pressure")
    world.hostiles.clear()
    rival, player = world.rival, world.player
    rival.boot = 0
    rival.x, rival.y = player.x + 40, player.y
    rival.action, rival.timer, rival.aim_x, rival.aim_y = "dash", 12, -1.0, 0.0
    for _ in range(12):
        step(world, IDLE)
    assert player.charge == DEFAULT.player_max_charge - DEFAULT.rival_contact_damage


def test_hazard_arms_before_it_hurts() -> None:
    world = encounter_world(1, 1, "spacing")
    world.hostiles.clear()
    rival, player = world.rival, world.player
    rival.boot = 0
    rival.cooldown = 1
    rival.timer = 10_000  # no orbs in this test
    step(world, IDLE)
    assert len(world.hazards) == 1
    for _ in range(DEFAULT.insulate_hazard_tell - 1):
        step(world, IDLE)
        assert player.charge == DEFAULT.player_max_charge, "an arming hazard never hurts"
    for _ in range(3):
        step(world, IDLE)
    assert player.charge == DEFAULT.player_max_charge - 1


def test_oscillate_fires_a_three_bolt_fan() -> None:
    world = encounter_world(1, 1, "lateral")
    world.hostiles.clear()
    rival = world.rival
    rival.boot = 0
    rival.action, rival.timer = "tell", 1
    step(world, IDLE)
    assert "rival_volley" in {e.kind for e in world.events}
    assert sum(1 for p in world.projectiles if p.hostile) == 3


def test_stats_are_identical_across_protocols() -> None:
    rivals = [encounter_world(1, 1, protocol).rival for protocol in PROTOCOLS]
    assert len({(r.health, r.radius, r.boot) for r in rivals}) == 1


def test_clamp_never_starts_a_lunge_it_cannot_finish() -> None:
    with pytest.raises(ValueError):
        dataclasses.replace(DEFAULT, clamp_range=200.0)


def test_encounter_one_is_always_neutral() -> None:
    campaign = Campaign(1)
    assert campaign.protocols == {1: "lateral"} and campaign.world.protocol == "lateral"
    enter(campaign, "s1_chamber")
    assert campaign.world.rival.protocol == "lateral"


# Campaign on the floor -----------------------------------------------------------------------


def test_three_sectors_then_the_ending() -> None:
    campaign = Campaign(4)
    assert (campaign.stage, campaign.encounter) == ("encounter", 1)
    skip_sector(campaign)
    assert campaign.stage == "fuse_box"
    campaign.begin_next("pressure")
    assert campaign.encounter == 2 and campaign.world.protocol == "pressure"
    enter(campaign, "s2_chamber")
    assert campaign.world.rival.protocol == "pressure", "the frozen protocol boots there"
    skip_sector(campaign)
    campaign.begin_next("spacing")
    skip_sector(campaign)
    assert campaign.stage == "ending" and campaign.encounter == ENCOUNTERS
    assert campaign.protocols == {1: "lateral", 2: "pressure", 3: "spacing"}


def test_the_fuse_box_heals_and_its_exit_opens_only_on_begin_next() -> None:
    campaign = Campaign(4)
    campaign.world.player.charge = 2
    skip_sector(campaign)
    assert campaign.world.player.charge == DEFAULT.player_max_charge
    exits = {"fuse_1>s2_entry", "s2_entry>fuse_1"}
    assert exits <= set(campaign.world.locked)
    campaign.begin_next("pressure")
    assert not exits & set(campaign.world.locked)
    assert {"fuse_2>s3_entry", "s3_entry>fuse_2"} <= set(campaign.world.locked)


def test_combat_rooms_lock_send_waves_and_open_when_clear() -> None:
    campaign = Campaign(4)
    enter(campaign, "s1_hall")
    world = campaign.world
    doors = {"s1_hall>s1_entry", "s1_hall>s1_bay"}
    assert world.active_room == "s1_hall" and doors <= set(world.locked)
    assert len(world.warps) == 2 and not world.hostiles, "robots show a marker before they arrive"
    for _ in range(DEFAULT.warp_tell):
        campaign.step(IDLE)
    assert len(world.hostiles) == 2 and not world.warps
    for _wave in (0, 1):
        for _ in range(DEFAULT.warp_tell + 1):
            for hostile in world.hostiles:
                hostile.health = 0
            campaign.step(IDLE)
    assert "s1_hall" in world.cleared and not doors & set(world.locked)
    assert world.active_room == ""


def test_begin_next_only_from_the_fuse_box() -> None:
    campaign = Campaign(4)
    with pytest.raises(RuntimeError):
        campaign.begin_next("pressure")
    skip_sector(campaign)
    with pytest.raises(ValueError):
        campaign.begin_next("berserk")


def test_retry_restores_the_sector_entry_and_keeps_the_protocol() -> None:
    campaign = Campaign(4)
    skip_sector(campaign)
    campaign.begin_next("spacing")
    entry = state_hash(campaign.world)
    enter(campaign, "s2_yard")
    for _ in range(50):
        campaign.step(IDLE)
    campaign.world.player.charge = 0
    campaign.step(IDLE)
    assert campaign.world.outcome == "down"
    campaign.step(InputFrame(restart=True))
    assert state_hash(campaign.world) == entry
    assert campaign.world.protocol == "spacing" and campaign.world.cleared[-1] == "s1_chamber"
    assert campaign.retries == {1: 0, 2: 1}
    assert campaign.protocols[2] == "spacing", "a retry never asks for a new protocol"


def test_the_secret_wall_cracks_after_a_few_shots() -> None:
    campaign = Campaign(4)
    skip_sector(campaign)
    campaign.begin_next("pressure")
    world = campaign.world
    floor = campaign.arena.floor
    x, y, w, _ = next(d.rect for d in floor.doors if d.id == "s2_entry>hidden")
    target = ((x + w / 2) * 16, (y + 1) * 16)
    world.player.x, world.player.y = target[0], target[1] - 40
    assert "s2_entry>hidden" in world.locked
    for _ in range(200):
        campaign.step(InputFrame(aim_x=int(target[0]), aim_y=int(target[1]) + 20, fire=True))
        if "s2_entry>hidden" not in world.locked:
            break
    assert "s2_entry>hidden" not in world.locked and "hidden>s2_entry" not in world.locked


def test_campaign_replay_reproduces_the_run(tmp_path) -> None:
    campaign = Campaign(9)
    recording = Recording(
        seed=9,
        tuning_id=DEFAULT.tuning_id(),
        arena_id=arena_id(FLOOR_ARENA),
        mode="campaign",
        protocols=["lateral"],
    )
    play_campaign(campaign, recording=recording)
    recording.final_hash = campaign.state_hash()
    path = tmp_path / "campaign.json"
    recording.save(path)
    replayed = play(Recording.load(path))
    assert replayed.state_hash() == recording.final_hash
    assert replayed.protocols == campaign.protocols


def campaign_recording(protocols: list[str], starts: list[int], frames: int) -> Recording:
    return Recording(
        seed=9,
        tuning_id=DEFAULT.tuning_id(),
        arena_id=arena_id(FLOOR_ARENA),
        mode="campaign",
        protocols=protocols,
        starts=starts,
        frames=[IDLE] * frames,
    )


@pytest.mark.parametrize(
    ("protocols", "starts", "frames"),
    [
        (["pressure"], [], 10),  # encounter 1 must be neutral
        (["lateral", "pressure"], [999], 10),  # start beyond the frames
        (["lateral", "pressure", "spacing"], [5, 5], 10),  # not strictly increasing
        (["lateral", "pressure"], [0], 10),  # before anything was cleared
        (["lateral", "pressure"], [5], 10),  # sector 1 not cleared at tick 5
        (["lateral", "pressure"], [], 10),  # protocol without a start
    ],
)
def test_malformed_campaign_replays_are_rejected(protocols, starts, frames) -> None:
    with pytest.raises(ValueError):
        play(campaign_recording(protocols, starts, frames))


def test_pinned_campaign_hash_matches_across_python_versions() -> None:
    """A full scripted campaign on the floor (three sectors, two protocol changes) has a
    known result on every CI Python version. Update deliberately if rules change."""
    campaign = Campaign(9)
    play_campaign(campaign)
    assert (campaign.stage, campaign.encounter) == ("ending", 3)
    assert campaign.state_hash() == "PIN"


def test_no_path_along_the_walls_skips_a_room() -> None:
    """Every interior tile of every combat room and chamber locks it, including the ring of
    tiles along the walls, so no route can slip past a fight."""
    from overload.sim import floorplay

    floor = FLOOR_ARENA.floor
    for room in floor.rooms:
        if room.kind not in ("combat", "chamber"):
            continue
        x, y, w, h = room.interior
        ring = [(tx, y) for tx in range(x, x + w)] + [(tx, y + h - 1) for tx in range(x, x + w)]
        ring += [(x, ty) for ty in range(y, y + h)] + [(x + w - 1, ty) for ty in range(y, y + h)]
        for tile in ring:
            if floor.room.decor[tile[1]][tile[0]] in "TCRIKB":
                continue
            campaign = Campaign(1)
            campaign.world.player.x, campaign.world.player.y = floorplay.tile_center(tile)
            campaign.step(IDLE)
            assert campaign.world.active_room == room.id, (room.id, tile)


def test_going_down_as_the_last_regulator_falls_is_still_down() -> None:
    campaign = Campaign(4)
    skip_sector(campaign)
    campaign.begin_next("pressure")
    skip_sector(campaign)
    campaign.begin_next("spacing")
    enter(campaign, "s3_chamber")
    campaign.world.rival.health = 0
    campaign.world.player.charge = 0
    campaign.step(IDLE)
    assert campaign.world.outcome == "down" and campaign.stage == "encounter"
