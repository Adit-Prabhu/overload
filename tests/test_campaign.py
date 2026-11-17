"""Task 6: the Regulator's protocols and the three-encounter campaign.

Acceptance: each protocol is beatable with every legal loadout (here, the starting loadout:
the gun and dodge, since powers arrive with task 8), stats are identical across protocols,
tells meet the readability minimums, and retries restore the entry state exactly.
"""

from __future__ import annotations

import pytest

from overload.session.replay import Recording, play
from overload.sim.arena import SUBSTATION, arena_id
from overload.sim.campaign import ENCOUNTERS, Campaign, encounter_world
from overload.sim.inputs import IDLE, InputFrame
from overload.sim.state import state_hash
from overload.sim.tuning import DEFAULT, TICK_RATE
from overload.sim.world import PROTOCOLS, step

ATTACKS = {"rival_lunge", "rival_orb", "rival_volley"}


def scripted_player(world, tick: int) -> InputFrame:
    """A plain but competent player: aim at the Regulator, hold the middle distance while
    strafing, dodge as a tell finishes, step out of armed hazard tiles."""
    player, rival = world.player, world.rival
    if rival is None or rival.health <= 0:
        return IDLE
    dx, dy = rival.x - player.x, rival.y - player.y
    distance = (dx * dx + dy * dy) ** 0.5 or 1.0
    ux, uy = dx / distance, dy / distance
    side = 1 if (tick // 150) % 2 == 0 else -1
    if distance < 90:
        mx, my = -ux, -uy
    elif distance > 135:
        mx, my = ux, uy
    else:
        mx, my = -uy * side, ux * side
    for hazard in world.hazards:
        cx, cy = hazard.x + hazard.size / 2, hazard.y + hazard.size / 2
        if abs(player.x - cx) < 16 and abs(player.y - cy) < 16:
            mx, my = player.x - cx, player.y - cy
    sx = 0 if abs(mx) < 0.3 else (1 if mx > 0 else -1)
    sy = 0 if abs(my) < 0.3 else (1 if my > 0 else -1)
    dodge = rival.action == "tell" and rival.timer <= 4
    return InputFrame(sx, sy, int(rival.x), int(rival.y), fire=True, dodge=dodge)


def fight(protocol: str, seed: int, limit: int = 3600) -> Campaign:
    campaign = Campaign(seed, protocol)
    for tick in range(limit):
        campaign.step(scripted_player(campaign.world, tick))
        if campaign.world.outcome != "playing":
            break
    return campaign


def beat_encounter(campaign: Campaign) -> None:
    campaign.world.rival.health = 0
    campaign.step(IDLE)


# Protocols -----------------------------------------------------------------------------------


@pytest.mark.parametrize("protocol", PROTOCOLS)
@pytest.mark.parametrize("seed", [1, 2, 3])
def test_every_protocol_is_beatable_with_the_starting_loadout(protocol: str, seed: int) -> None:
    campaign = fight(protocol, seed)
    assert campaign.world.outcome == "clear", (protocol, seed, campaign.world.player.charge)
    assert campaign.stage == "fuse_box"


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


def test_unknown_protocol_is_rejected() -> None:
    with pytest.raises(ValueError):
        Campaign(1, "berserk")


# Campaign ------------------------------------------------------------------------------------


def test_three_encounters_then_the_ending() -> None:
    campaign = Campaign(4)
    assert (campaign.stage, campaign.encounter, campaign.protocols) == (
        "encounter",
        1,
        {1: "lateral"},
    )
    beat_encounter(campaign)
    assert campaign.stage == "fuse_box"
    campaign.begin_next("pressure")
    assert campaign.world.rival.protocol == "pressure" and campaign.encounter == 2
    beat_encounter(campaign)
    campaign.begin_next("spacing")
    beat_encounter(campaign)
    assert campaign.stage == "ending" and campaign.encounter == ENCOUNTERS
    assert campaign.protocols == {1: "lateral", 2: "pressure", 3: "spacing"}


def test_nothing_moves_in_the_fuse_box() -> None:
    campaign = Campaign(4)
    beat_encounter(campaign)
    before = campaign.state_hash()
    campaign.step(InputFrame(move_x=1, fire=True))
    assert campaign.state_hash() == before


def test_begin_next_only_from_the_fuse_box() -> None:
    campaign = Campaign(4)
    with pytest.raises(RuntimeError):
        campaign.begin_next("pressure")
    beat_encounter(campaign)
    with pytest.raises(ValueError):
        campaign.begin_next("berserk")


def test_retry_restores_the_entry_state_and_keeps_the_protocol() -> None:
    campaign = Campaign(4)
    beat_encounter(campaign)
    campaign.begin_next("spacing")
    entry = state_hash(campaign.world)
    for _ in range(50):
        campaign.step(IDLE)
    campaign.world.player.charge = 0
    campaign.step(IDLE)
    assert campaign.world.outcome == "down"
    campaign.step(InputFrame(restart=True))
    assert state_hash(campaign.world) == entry
    assert campaign.world.rival.protocol == "spacing"
    assert campaign.retries == {1: 0, 2: 1}
    assert campaign.protocols[2] == "spacing", "a retry never asks for a new protocol"


def test_campaign_replay_reproduces_the_run(tmp_path) -> None:
    campaign = Campaign(9, "lateral")
    recording = Recording(
        seed=9,
        tuning_id=DEFAULT.tuning_id(),
        arena_id=arena_id(SUBSTATION),
        mode="campaign",
        protocols=["lateral"],
    )
    for tick in range(5000):
        if campaign.stage == "fuse_box":
            protocol = "pressure" if campaign.encounter == 1 else "spacing"
            campaign.begin_next(protocol)
            recording.begin_next(protocol)
        if campaign.stage == "ending":
            break
        frame = scripted_player(campaign.world, tick)
        campaign.step(frame)
        recording.frames.append(frame)
    recording.final_hash = campaign.state_hash()
    path = tmp_path / "campaign.json"
    recording.save(path)
    replayed = play(Recording.load(path))
    assert replayed.state_hash() == recording.final_hash
    assert replayed.protocols == campaign.protocols


def test_campaign_replay_with_other_protocols_differs() -> None:
    recording = Recording(
        seed=9,
        tuning_id=DEFAULT.tuning_id(),
        arena_id=arena_id(SUBSTATION),
        mode="campaign",
        protocols=["lateral"],
        frames=[IDLE] * 200,
    )
    other = Recording(
        seed=9,
        tuning_id=DEFAULT.tuning_id(),
        arena_id=arena_id(SUBSTATION),
        mode="campaign",
        protocols=["pressure"],
        frames=[IDLE] * 200,
    )
    assert play(recording).state_hash() != play(other).state_hash()


def test_pinned_campaign_hash_matches_across_python_versions() -> None:
    """A full scripted campaign (three encounters, two protocol changes) has a known result on
    every CI Python version. Update deliberately, with a note in the PR, if rules change."""
    campaign = Campaign(9, "lateral")
    for tick in range(4000):
        if campaign.stage == "fuse_box":
            campaign.begin_next("pressure" if campaign.encounter == 1 else "spacing")
        if campaign.stage == "ending":
            break
        campaign.step(scripted_player(campaign.world, tick))
    assert (campaign.stage, campaign.encounter) == ("ending", 3)
    assert campaign.state_hash() == "b48b1a7c03bb5239"
