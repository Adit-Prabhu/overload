"""Task 9: solid bodies, the encounter roster and the ending readout. Acceptance: a complete
win path, plus a loss and retry path."""

from __future__ import annotations

import math

from test_campaign import scripted_player

from overload.sim.campaign import ROSTER, Campaign, encounter_world
from overload.sim.inputs import IDLE, InputFrame
from overload.sim.tuning import DEFAULT
from overload.sim.world import step


def test_the_surge_cannot_walk_through_the_regulator() -> None:
    world = encounter_world(1, 1, "lateral")
    world.hostiles.clear()
    rival, player = world.rival, world.player
    rival.strafe_timer = 10_000
    player.x, player.y = rival.x - 40, rival.y
    for _ in range(80):
        step(world, InputFrame(move_x=1, aim_x=int(rival.x), aim_y=int(rival.y)))
        gap = math.dist((player.x, player.y), (rival.x, rival.y))
        assert gap >= rival.radius + DEFAULT.player_radius - 1e-9


def test_the_surge_cannot_stand_inside_a_machine() -> None:
    world = encounter_world(1, 1, "lateral")
    world.rival = None
    mite = world.hostiles[0]
    mite.fire_timer = 10_000
    world.player.x, world.player.y = mite.x + 1, mite.y
    step(world, IDLE)
    gap = math.dist((world.player.x, world.player.y), (mite.x, mite.y))
    assert gap >= mite.radius + DEFAULT.player_radius - 1e-9


def test_a_dodge_slips_through_bodies() -> None:
    world = encounter_world(1, 1, "lateral")
    world.rival = None
    mite = world.hostiles[0]
    mite.fire_timer = 10_000
    world.player.x, world.player.y = mite.x - 12, mite.y
    step(world, InputFrame(move_x=1, dodge=True))
    step(world, InputFrame(move_x=1))
    assert world.player.dodging
    assert math.dist((world.player.x, world.player.y), (mite.x, mite.y)) < 11


def test_every_encounter_brings_its_roster() -> None:
    for encounter, roster in ROSTER.items():
        world = encounter_world(1, encounter, "lateral")
        assert tuple(h.kind for h in world.hostiles) == roster


def test_a_complete_win_path() -> None:
    campaign = Campaign(5)
    for tick in range(12_000):
        if campaign.stage == "fuse_box":
            campaign.begin_next("pressure" if campaign.encounter == 1 else "spacing")
        if campaign.stage == "ending":
            break
        campaign.step(scripted_player(campaign.world, tick))
    assert campaign.stage == "ending" and campaign.encounter == 3
    assert campaign.stats["ticks"] > 0 and campaign.stats["shots"] > 0


def test_a_loss_and_retry_path_then_the_win() -> None:
    campaign = Campaign(5)
    for _ in range(2000):  # stand still and take every hit until the short circuit
        campaign.step(InputFrame(aim_x=0, aim_y=0))
        if campaign.world.outcome == "down":
            break
    assert campaign.world.outcome == "down", "the loss comes from real hits, not a forced value"
    ticks_when_down = campaign.stats["ticks"]
    for _ in range(30):
        campaign.step(IDLE)  # waiting on the retry: no fighting time counted
    assert campaign.stats["ticks"] == ticks_when_down
    campaign.step(InputFrame(restart=True))
    assert campaign.retries[1] == 1 and campaign.world.outcome == "playing"
    for tick in range(4000):
        campaign.step(scripted_player(campaign.world, tick))
        if campaign.stage != "encounter":
            break
    assert campaign.stage == "fuse_box", "the retried encounter can still be won"


def test_stats_count_shots_and_powers_across_retries() -> None:
    campaign = Campaign(5)
    campaign.world.unlocked = ["spark"]
    campaign.world.player.slots = ["spark", ""]
    campaign.step(InputFrame(aim_x=400, aim_y=150, fire=True, power_q=True))
    assert campaign.stats["shots"] == 1 and campaign.stats["powers"] == {"spark": 1}
    campaign.world.player.charge = 0
    campaign.step(IDLE)
    before = dict(campaign.stats, powers=dict(campaign.stats["powers"]))
    campaign.step(InputFrame(restart=True))
    assert campaign.stats == before, "a retry never erases what the player tried"
    campaign.step(IDLE)
    assert campaign.stats["ticks"] == before["ticks"] + 1
    assert campaign.stats["powers"] == {"spark": 1}
