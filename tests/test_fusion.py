"""Chance fusion, step 2 of docs/POWERS_AND_FUSION.md: the charge bank, the reroll cost, the
odds and the guarantee, the seeded roll stream, retries, the trace, and the epic and
legendary results of Arc Trail and Shock Cone."""

from __future__ import annotations

import copy
import dataclasses
import json
import math
import random
from collections import Counter

import pytest
from floorbot import clear_encounter, fuse_box_with

from overload.agent.selector import NeutralSelector
from overload.game.flow import FUSE_NOTICES, FuseBoxMenu, Session
from overload.session.trace import TraceWriter
from overload.sim.arena import SUBSTATION, Arena
from overload.sim.campaign import Campaign, encounter_world
from overload.sim.inputs import IDLE, InputFrame
from overload.sim.powers import (
    FUSION_NAMES,
    RARITIES,
    RECIPES,
    Kit,
    absorb_charges,
    evolved,
    fuse,
    fused_name,
    roll_rarity,
)
from overload.sim.spawns import spawn_robot
from overload.sim.state import Charge, Projectile
from overload.sim.tuning import DEFAULT
from overload.sim.world import step

# An open room with no props, so every spark and trail has room to work.
OPEN = Arena(
    room=SUBSTATION.room,
    size=(320, 240),
    bounds=(0.0, 0.0, 320.0, 240.0),
    obstacles=(),
    player_spawn=(110.0, 120.0),
    practice_spawns=((10.0, 10.0), (310.0, 10.0)),
    rival_spawn=(300.0, 220.0),
)
BASES = ("spark", "blink", "burst")
AIM = {"aim_x": 166, "aim_y": 120}  # straight right, a full Blink away


def armed(power: str, rarity: str, fragments=None):
    kit = Kit(
        unlocked=["spark", "blink", "burst", power],
        fragments=dict(fragments or {}),
        slots=[power, ""],
        rarity={power: rarity},
    )
    world = encounter_world(1, 1, "lateral", arena=OPEN, kit=kit)
    world.hostiles.clear()
    world.rival = None
    world.player.x, world.player.y = OPEN.player_spawn
    return world


def armed_and_fired(power: str, rarity: str):
    world = armed(power, rarity)
    step(world, InputFrame(power_q=True, **AIM), arena=OPEN)
    return world


def dummy(world, x: float, y: float):
    """A Sentry that never fires, with health to spare: it only counts damage."""
    robot = spawn_robot(world, "sentry", x, y)
    robot.fire_timer = 10**6
    robot.health = robot.max_health = 999
    return robot


def sparks(world) -> list[Projectile]:
    return [p for p in world.projectiles if p.kind == "spark" and not p.hostile]


# Rolls ---------------------------------------------------------------------------------------


def test_the_roll_depends_only_on_the_seed_and_the_fusion_count() -> None:
    assert all(roll_rarity(7, n, False) == roll_rarity(7, n, False) for n in range(50))
    rolls = {(seed, n): roll_rarity(seed, n, False) for seed in range(20) for n in range(20)}
    assert set(rolls.values()) == set(RARITIES)


def test_the_odds_are_sixty_thirty_ten() -> None:
    counts = Counter(roll_rarity(seed, 0, False) for seed in range(6000))
    assert 0.57 < counts["rare"] / 6000 < 0.63
    assert 0.27 < counts["epic"] / 6000 < 0.33
    assert 0.08 < counts["legendary"] / 6000 < 0.12


def test_a_guaranteed_roll_is_never_rare_and_keeps_the_epic_to_legendary_ratio() -> None:
    counts = Counter(roll_rarity(seed, 3, True) for seed in range(4000))
    assert counts["rare"] == 0
    assert 0.22 < counts["legendary"] / 4000 < 0.28


def test_two_rares_in_a_row_guarantee_epic_or_better() -> None:
    guaranteed = 0
    for seed in range(60):
        kit = Kit(["spark", "blink"], {}, ["", ""], bank={"spark": 99, "blink": 99})
        history = []
        trailing = 0  # rares in a row, counted here independently of the kit
        for n in range(25):
            due = trailing >= DEFAULT.fuse_guarantee_after
            guaranteed += due
            assert fuse(kit, "spark", "blink", seed) == "fused"
            history.append(kit.rarity["arc_trail"])
            assert history[n] == roll_rarity(seed, n, due), (seed, n)
            trailing = trailing + 1 if history[n] == "rare" else 0
            assert kit.streak == trailing, "the streak resets on epic or legendary"
        for i in range(2, len(history)):
            if history[i - 2] == history[i - 1] == "rare":
                assert history[i] != "rare", (seed, history)
    assert guaranteed > 20, "the guarantee actually comes up"


def test_the_nth_fusion_rolls_the_same_whatever_pair_is_picked() -> None:
    """The same seed gives the same rarity sequence in both conditions, whatever the
    player fuses, so luck cannot differ between them."""

    def sequence(order):
        kit = Kit(["spark", "blink", "burst"], {}, ["", ""], bank=dict.fromkeys(BASES, 9))
        out = []
        for a, b in order:
            assert fuse(kit, a, b, 11) == "fused"
            out.append(kit.rarity["arc_trail" if b == "blink" else "shock_cone"])
        return out

    one = sequence([("spark", "blink"), ("spark", "burst"), ("spark", "blink")])
    two = sequence([("spark", "burst"), ("spark", "burst"), ("spark", "blink")])
    assert one == two


def test_fusing_never_touches_the_combat_rng() -> None:
    campaign = Campaign(4)
    campaign.world.unlocked = ["spark", "blink"]
    before = campaign.world.rng.getstate()
    assert campaign.fuse("spark", "blink") == "fused"
    assert campaign.world.rng.getstate() == before


# Charges and cost ----------------------------------------------------------------------------


def test_spare_charges_go_to_the_bank_and_still_evolve() -> None:
    world = armed("arc_trail", "rare")
    world.unlocked = []
    for i in range(3):
        world.charges.append(Charge(900 + i, "spark", world.player.x, world.player.y))
        absorb_charges(world, DEFAULT)
    assert world.unlocked == ["spark"], "the first charge unlocks"
    assert world.bank == {"spark": 2} and world.fragments == {"spark": 3}
    assert evolved(world.fragments, "spark", DEFAULT)


def test_the_first_fusion_is_free_and_a_reroll_costs_one_charge_of_each() -> None:
    kit = Kit(["spark", "blink"], {"spark": 3, "blink": 2}, ["", ""], bank={"spark": 2, "blink": 1})
    assert fuse(kit, "spark", "blink", 5) == "fused"
    assert kit.bank == {"spark": 2, "blink": 1} and kit.fusions == 1
    assert fuse(kit, "blink", "spark", 5) == "fused"
    assert kit.bank == {"spark": 1, "blink": 0} and kit.fusions == 2
    assert kit.rarity["arc_trail"] == roll_rarity(5, 1, False), "the new roll replaces"
    assert fuse(kit, "spark", "blink", 5) == "no_charges"
    assert kit.bank == {"spark": 1, "blink": 0} and kit.fusions == 2, "a refused reroll is free"
    assert kit.fragments == {"spark": 3, "blink": 2}, "spending never undoes an evolution"
    assert kit.unlocked == ["spark", "blink", "arc_trail"], "one fused power per pair"


def test_a_retry_brings_back_the_same_roll() -> None:
    """Going down restores the sector's kit, fusion count included, so dying never rerolls."""
    campaign = Campaign(8)
    world = campaign.world
    world.unlocked = ["spark", "blink"]
    world.bank = {"spark": 1, "blink": 1}
    campaign.checkpoint = copy.deepcopy(world)
    campaign.fuse("spark", "blink")
    campaign.fuse("spark", "blink")
    first = (campaign.world.rarity["arc_trail"], campaign.world.fusions)
    campaign.world.player.charge = 0
    campaign.step(IDLE)
    assert campaign.world.outcome == "down"
    campaign.step(InputFrame(restart=True))
    assert campaign.world.fusions == 0 and campaign.world.bank == {"spark": 1, "blink": 1}
    campaign.fuse("spark", "blink")
    campaign.fuse("spark", "blink")
    assert (campaign.world.rarity["arc_trail"], campaign.world.fusions) == first


def test_fusions_are_traced_with_their_roll(tmp_path) -> None:
    trace = TraceWriter(tmp_path / "t.jsonl", condition="off", tuning_id="t", arena_id="a")
    session = Session(Campaign(1), NeutralSelector(), trace, "anon")
    clear_encounter(session)
    world = session.campaign.world
    world.unlocked = ["spark", "blink"]
    world.bank = {"spark": 1, "blink": 1}
    session.fuse("spark", "blink")
    session.fuse("spark", "blink")
    rows = [json.loads(line) for line in (tmp_path / "t.jsonl").read_text().splitlines()]
    fuses = [r for r in rows if r["event"] == "fuse"]
    assert [(r["n"], r["cost"]) for r in fuses] == [(0, 0), (1, DEFAULT.reroll_cost)]
    assert fuses[-1]["rarity"] == world.rarity["arc_trail"] and fuses[-1]["power"] == "arc_trail"
    assert all(r["guaranteed"] is False for r in fuses)


# The menu ------------------------------------------------------------------------------------


def test_the_menu_rerolls_the_picked_fusion_and_says_when_it_cannot() -> None:
    session = fuse_box_with("spark", "blink")
    menu = FuseBoxMenu()
    world = session.campaign.world
    assert menu.press(session, "fuse") == ["fuse", "spark", "blink"]
    # Burst is not stolen: with a base power picked, F reports what Shock Cone still needs.
    assert menu.press(session, "fuse") == ["fuse", "spark", "burst"]
    assert menu.notice == FUSE_NOTICES["missing"] and world.fusions == 1
    world.rarity["arc_trail"] = "rare"  # a rare rerolls at once (an epic asks first)
    menu.press(session, "up")  # wraps to the last row, Arc Trail: F now rerolls it
    assert menu.press(session, "fuse") == ["fuse", "spark", "blink"]
    assert menu.notice == FUSE_NOTICES["no_charges"] and world.fusions == 1
    world.bank = {"spark": 1, "blink": 1}
    assert menu.press(session, "fuse") == ["fuse", "spark", "blink"]
    rarity = world.rarity["arc_trail"]
    assert world.fusions == 2 and world.bank == {"spark": 0, "blink": 0}
    assert menu.notice == f"{fused_name('arc_trail', rarity)} {rarity.upper()}"


def test_with_every_recipe_fused_f_spends_nothing_until_a_fusion_is_picked() -> None:
    session = fuse_box_with("spark", "blink", "burst")
    world = session.campaign.world
    world.bank = {"spark": 5, "blink": 5, "burst": 5}
    menu = FuseBoxMenu()
    menu.press(session, "fuse")
    menu.press(session, "fuse")
    assert world.unlocked[-2:] == ["arc_trail", "shock_cone"]
    assert menu.press(session, "fuse") is None and menu.notice == FUSE_NOTICES["pick"]
    assert world.bank == {"spark": 5, "blink": 5, "burst": 5} and world.fusions == 2


@pytest.mark.parametrize("rarity", ["epic", "legendary"])
def test_rerolling_an_epic_or_legendary_takes_a_second_press(rarity) -> None:
    session = fuse_box_with("spark", "blink")
    world = session.campaign.world
    menu = FuseBoxMenu()
    menu.press(session, "fuse")
    world.rarity["arc_trail"], world.bank = rarity, {"spark": 2, "blink": 2}
    menu.press(session, "up")  # Arc Trail
    assert menu.press(session, "fuse") is None and world.fusions == 1, "nothing spent yet"
    assert menu.notice == f"F AGAIN TO REROLL {rarity.upper()}"
    menu.press(session, "down")  # any other key cancels
    menu.press(session, "up")
    assert menu.press(session, "fuse") is None and world.fusions == 1
    assert menu.press(session, "fuse") == ["fuse", "spark", "blink"]
    assert world.fusions == 2 and world.bank == {"spark": 1, "blink": 1}


def test_the_session_trace_starts_with_the_run_seed(tmp_path) -> None:
    trace = TraceWriter(tmp_path / "t.jsonl", condition="off", tuning_id="t", arena_id="a")
    Session(Campaign(37), NeutralSelector(), trace, "anon")
    rows = [json.loads(line) for line in (tmp_path / "t.jsonl").read_text().splitlines()]
    start = next(r for r in rows if r["event"] == "encounter_start")
    assert start["seed"] == 37 and start["encounter"] == 1


def test_every_recipe_has_its_three_rarity_names() -> None:
    assert set(FUSION_NAMES) == set(RECIPES.values())
    assert all(len(names) == len(RARITIES) for names in FUSION_NAMES.values())


# Rarity effects ------------------------------------------------------------------------------


def test_storm_step_leaves_a_longer_wider_trail_and_thunderhead_adds_a_ring() -> None:
    trails = {}
    for rarity in RARITIES:
        world = armed("arc_trail", rarity)
        step(world, InputFrame(power_q=True, **AIM), arena=OPEN)
        (trail,) = world.trails
        trails[rarity] = (trail.ttl, trail.width, len(sparks(world)))
    assert trails["rare"][:2] == (DEFAULT.trail_ttl - 1, DEFAULT.trail_width)
    assert trails["epic"][:2] == (DEFAULT.storm_trail_ttl - 1, DEFAULT.storm_trail_width)
    assert trails["legendary"] == (DEFAULT.storm_trail_ttl - 1, DEFAULT.storm_trail_width, 8)
    assert trails["rare"][2] == trails["epic"][2] == 0
    ring = sparks(armed_and_fired("arc_trail", "legendary"))
    assert {(s.arc, s.damage) for s in ring} == {("none", DEFAULT.thunder_spark_damage)}


def test_shock_fan_fires_five_sparks_and_overcurrent_chains_them() -> None:
    fans = {}
    for rarity in RARITIES:
        world = armed("shock_cone", rarity)
        step(world, InputFrame(power_q=True, **AIM), arena=OPEN)
        fans[rarity] = sparks(world)
    assert len(fans["rare"]) == 3 and len(fans["epic"]) == len(fans["legendary"]) == 5
    assert (
        sorted(s.damage for s in fans["epic"])
        == [DEFAULT.fan_spark_damage] * 2 + [DEFAULT.spark_damage] * 3
    )
    assert not any(s.arc for s in fans["rare"] + fans["epic"])
    assert sorted(s.arc for s in fans["legendary"]) == [""] * 2 + ["overcurrent"] * 3


@pytest.mark.parametrize("spark_evolved", [False, True])
def test_an_overcurrent_spark_chains_twice_evolved_or_not(spark_evolved) -> None:
    """One robot further than an evolved Spark reaches, so the legendary step never
    disappears once Spark evolves (sector 1 for most players)."""
    world = armed("shock_cone", "legendary", {"spark": 3} if spark_evolved else None)
    hit, second, third = dummy(world, 200, 120), dummy(world, 200, 150), dummy(world, 200, 180)
    world.projectiles.append(
        Projectile(800, 190, 120, 3.0, 0.0, 3.0, DEFAULT.spark_damage, False, 30, "spark")
    )
    world.projectiles[-1].arc = "overcurrent"
    for _ in range(5):
        step(world, IDLE, arena=OPEN)
    first_arc = DEFAULT.spark_chain_damage if spark_evolved else DEFAULT.overcurrent_chain_damage
    assert hit.health == 999 - DEFAULT.spark_damage
    assert second.health == 999 - first_arc
    assert third.health == 999 - DEFAULT.overcurrent_chain_damage


def test_thunderhead_ring_sparks_never_chain() -> None:
    world = armed("arc_trail", "legendary", {"spark": 3})
    hit, other = dummy(world, 200, 120), dummy(world, 200, 150)
    world.projectiles.append(Projectile(800, 190, 120, 3.0, 0.0, 3.0, 1, False, 30, "spark"))
    world.projectiles[-1].arc = "none"
    for _ in range(5):
        step(world, IDLE, arena=OPEN)
    assert hit.health == 998 and other.health == 999


# Power step guard ----------------------------------------------------------------------------


def _scene(k: int) -> list[tuple[float, float]]:
    """Four robots in front of the Surge, 20 to 90 px away, apart from each other."""
    rng = random.Random(k)
    spots: list[tuple[float, float]] = []
    while len(spots) < 4:
        d, a = rng.uniform(20, 90), rng.uniform(-math.pi / 2, math.pi / 2)
        p = (110 + d * math.cos(a), 120 + d * math.sin(a))
        if all(math.dist(p, q) > 18 for q in spots) and math.dist(p, (110, 120)) > 18:
            spots.append(p)
    return spots


def _damage_per_use(power: str, rarity: str, k: int, fragments) -> int:
    world = armed(power, rarity, fragments)
    robots = [dummy(world, x, y) for x, y in _scene(k)]
    step(world, InputFrame(power_q=True, **AIM), arena=OPEN)
    for _ in range(240):
        step(world, InputFrame(**AIM), arena=OPEN)
    return sum(999 - r.health for r in robots)


@pytest.mark.parametrize("evolutions", [False, True], ids=["stock", "evolved"])
@pytest.mark.parametrize("power", ["arc_trail", "shock_cone"])
def test_higher_rarities_are_stronger_but_only_modestly(power, evolutions) -> None:
    """Spec section 5: averaged over 40 fixed scenes, an epic deals more than its rare and at
    most 1.35 times as much, a legendary more than its epic and at most 1.75 times the rare.
    Checked with the ingredients stock and evolved, since fusions inherit evolutions."""
    fragments = dict.fromkeys(BASES, 3) if evolutions else None
    total = {r: sum(_damage_per_use(power, r, k, fragments) for k in range(40)) for r in RARITIES}
    assert total["rare"] < total["epic"] <= 1.35 * total["rare"]
    assert total["epic"] < total["legendary"] <= 1.75 * total["rare"]


# Guards --------------------------------------------------------------------------------------


@pytest.mark.parametrize(
    "change",
    [
        {"fuse_odds": (100, 0, 0)},
        {"fuse_odds": (60, -1, 41)},
        {"reroll_cost": 0},
        {"fuse_odds": (60.0, 30, 10)},
        {"fan_spark_damage": 0},
        {"thunder_spark_damage": 0},
        {"overcurrent_chain_damage": 0},
        {"storm_trail_width": DEFAULT.trail_width - 1},
        {"fuse_guarantee_after": 0},
        {"storm_trail_ttl": DEFAULT.trail_ttl - 1},
    ],
)
def test_fusion_guards(change) -> None:
    with pytest.raises(ValueError):
        dataclasses.replace(DEFAULT, **change)
