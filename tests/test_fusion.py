"""Chance fusion (docs/POWERS_AND_FUSION.md): the charge bank, the reroll cost, the odds and
the guarantee, the seeded roll stream, retries, the trace, and the nine fused powers of the
three pairs that exist today, each its own verb."""

from __future__ import annotations

import copy
import dataclasses
import json
import math
import random
from collections import Counter

import pytest
from floorbot import clear_encounter

from overload.agent.selector import NeutralSelector
from overload.game.flow import Session
from overload.session.trace import TraceWriter
from overload.sim.arena import SUBSTATION, Arena
from overload.sim.campaign import Campaign, encounter_world
from overload.sim.geometry import normalize
from overload.sim.inputs import IDLE, InputFrame
from overload.sim.powers import (
    ABILITIES,
    COOLDOWN_KEYS,
    FUSED,
    NAMES,
    RARITIES,
    RECIPE_ORDER,
    RESULTS,
    Kit,
    absorb_charges,
    cooldown_of,
    evolved,
    fuse,
    owned_result,
    rarity_of,
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


def armed(power: str, fragments=None):
    kit = Kit(
        unlocked=["spark", "blink", "burst", power],
        fragments=dict(fragments or {}),
        slots=[power, ""],
    )
    world = encounter_world(1, 1, "lateral", arena=OPEN, kit=kit)
    world.hostiles.clear()
    world.rival = None
    world.player.x, world.player.y = OPEN.player_spawn
    return world


def fire(world, ticks: int = 0, **aim) -> None:
    """Press Q once with the cursor at `aim` (default straight right), then run idle."""
    cursor = aim or AIM
    step(world, InputFrame(power_q=True, **cursor), arena=OPEN)
    for _ in range(ticks):
        step(world, InputFrame(**cursor), arena=OPEN)


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
            history.append(rarity_of(owned_result(kit.unlocked, "spark", "blink")))
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
            out.append(rarity_of(owned_result(kit.unlocked, a, b)))
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
    world = armed("arc_trail")
    world.unlocked = []
    for i in range(3):
        world.charges.append(Charge(900 + i, "spark", world.player.x, world.player.y))
        absorb_charges(world, DEFAULT)
    assert world.unlocked == ["spark"], "the first charge unlocks"
    assert world.bank == {"spark": 2} and world.fragments == {"spark": 3}
    assert evolved(world.fragments, "spark", DEFAULT)


def test_the_first_fusion_is_free_and_a_reroll_costs_one_charge_of_each() -> None:
    kit = Kit(["spark", "blink"], {"spark": 3, "blink": 2}, ["", ""], bank={"spark": 2, "blink": 1})
    results = RESULTS[frozenset(("spark", "blink"))]
    assert fuse(kit, "spark", "blink", 5) == "fused"
    assert kit.bank == {"spark": 2, "blink": 1} and kit.fusions == 1
    first = kit.unlocked[-1]
    assert first == results[RARITIES.index(roll_rarity(5, 0, False))]
    kit.slots = ["", first]
    assert fuse(kit, "blink", "spark", 5) == "fused"
    assert kit.bank == {"spark": 1, "blink": 0} and kit.fusions == 2
    second = results[RARITIES.index(roll_rarity(5, 1, False))]
    assert kit.unlocked == ["spark", "blink", second], "the new power replaces the old one"
    assert kit.slots == ["", second], "in its slot too"
    assert fuse(kit, "spark", "blink", 5) == "no_charges"
    assert kit.bank == {"spark": 1, "blink": 0} and kit.fusions == 2, "a refused reroll is free"
    assert kit.fragments == {"spark": 3, "blink": 2}, "spending never undoes an evolution"


def test_a_retry_brings_back_the_same_roll() -> None:
    """Going down restores the sector's kit, fusion count included, so dying never rerolls."""
    campaign = Campaign(8)
    world = campaign.world
    world.unlocked = ["spark", "blink"]
    world.bank = {"spark": 1, "blink": 1}
    campaign.checkpoint = copy.deepcopy(world)
    campaign.fuse("spark", "blink")
    campaign.fuse("spark", "blink")
    first = (list(campaign.world.unlocked), campaign.world.fusions)
    campaign.world.player.charge = 0
    campaign.step(IDLE)
    assert campaign.world.outcome == "down"
    campaign.step(InputFrame(restart=True))
    assert campaign.world.fusions == 0 and campaign.world.bank == {"spark": 1, "blink": 1}
    campaign.fuse("spark", "blink")
    campaign.fuse("spark", "blink")
    assert (campaign.world.unlocked, campaign.world.fusions) == first


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
    power = owned_result(world.unlocked, "spark", "blink")
    assert fuses[-1]["power"] == power and fuses[-1]["rarity"] == rarity_of(power)
    assert fuses[-1]["replaced"] == fuses[0]["power"] and fuses[0]["replaced"] == ""
    assert all(r["guaranteed"] is False for r in fuses)


def test_the_session_trace_starts_with_the_run_seed(tmp_path) -> None:
    trace = TraceWriter(tmp_path / "t.jsonl", condition="off", tuning_id="t", arena_id="a")
    Session(Campaign(37), NeutralSelector(), trace, "anon")
    rows = [json.loads(line) for line in (tmp_path / "t.jsonl").read_text().splitlines()]
    start = next(r for r in rows if r["event"] == "encounter_start")
    assert start["seed"] == 37 and start["encounter"] == 1


def test_every_pair_fuses_into_three_distinct_powers() -> None:
    """Spec section 5: each rarity is its own power, with its own name, icon, description,
    cooldown and family. No two results share an id or an icon."""
    from overload.art.pixel.effects import _CHARGE
    from overload.game.view import DESCRIPTIONS, SOCKET_TOKENS

    results = [r for pair in RECIPE_ORDER for r in RESULTS[frozenset(pair)]]
    assert len(RECIPE_ORDER) == 10
    assert len(results) == len(set(results)) == 30
    assert [rarity_of(r) for r in results] == list(RARITIES) * len(RECIPE_ORDER)
    for power in ABILITIES:
        assert power in NAMES and power in DESCRIPTIONS and power in SOCKET_TOKENS
        assert cooldown_of(power, DEFAULT) > 0 and COOLDOWN_KEYS[power]
    icons = [tuple(_CHARGE[p]) for p in ABILITIES]
    assert len(icons) == len(set(icons)), "every power has its own icon"
    teleports = {
        "arc_trail",
        "bolt_lance",
        "chain_jump",
        "impact_blink",
        "displacer",
        "meteor",
        "phase_guard",
        "afterimage",
        "rewind",
        "undertow",
        "grapple",
        "riptide",
    }
    assert {p for p in FUSED if COOLDOWN_KEYS[p] == "teleport"} == teleports


# The fused powers ----------------------------------------------------------------------------


def test_bolt_lance_dashes_through_robots_and_strikes_each_once() -> None:
    world = armed("bolt_lance")
    first, second = dummy(world, 140, 120), dummy(world, 165, 121)
    fire(world, DEFAULT.lance_ticks + 5)
    travelled = world.player.x - OPEN.player_spawn[0]
    assert travelled >= DEFAULT.lance_speed * (DEFAULT.lance_ticks - 1) - 0.01
    assert first.health == second.health == 999 - DEFAULT.lance_damage
    assert world.player.cooldowns["teleport"] > 0 and not world.player.lance


def test_bolt_lance_is_untouchable_and_cannot_shoot() -> None:
    world = armed("bolt_lance")
    fire(world)
    assert world.player.protected and world.player.busy
    step(world, InputFrame(fire=True, **AIM), arena=OPEN)
    assert not [p for p in world.projectiles if p.kind == "shot"]


def test_chain_jump_hops_robot_to_robot_and_lands_beside_the_last() -> None:
    world = armed("chain_jump")
    robots = [dummy(world, 160, 120), dummy(world, 200, 140), dummy(world, 240, 120)]
    fire(world)
    assert [r.health for r in robots] == [999 - DEFAULT.chain_jump_damage] * 3
    last = robots[-1]
    gap = math.dist((world.player.x, world.player.y), (last.x, last.y))
    assert gap == pytest.approx(last.radius + DEFAULT.player_radius + 2.0)


def test_chain_jump_with_nothing_in_reach_costs_nothing() -> None:
    world = armed("chain_jump")
    dummy(world, 300, 230)
    fire(world)
    assert "teleport" not in world.player.cooldowns
    assert (world.player.x, world.player.y) == OPEN.player_spawn


def test_a_shock_mine_flies_to_the_cursor_then_bursts_after_its_fuse() -> None:
    world = armed("shock_mine")
    near, far = dummy(world, 166, 140), dummy(world, 166, 200)
    fire(world, 25)
    (mine,) = world.devices
    assert (mine.x, mine.y) == (166, 120) and mine.timer > 0
    assert near.health == 999, "nothing until the fuse burns down"
    fire(world, DEFAULT.shock_mine_fuse)
    assert world.devices == []
    assert near.health == 999 - DEFAULT.shock_mine_damage and far.health == 999


def test_storm_aura_strikes_the_nearest_robot_for_its_whole_duration() -> None:
    world = armed("storm_aura")
    near, far = dummy(world, 140, 120), dummy(world, 200, 120)
    fire(world, DEFAULT.storm_aura_ticks + 30)
    strikes = DEFAULT.storm_aura_ticks // DEFAULT.storm_aura_interval
    assert near.health == 999 - strikes * DEFAULT.storm_aura_damage
    assert far.health == 999 and world.player.aura == 0


def test_impact_blink_lands_and_blasts_robots_away() -> None:
    world = armed("impact_blink")
    robot = dummy(world, 180, 120)
    fire(world)
    assert world.player.x == pytest.approx(166)
    assert robot.health == 999 - DEFAULT.impact_damage and robot.x > 180


def test_displacer_swaps_places_with_the_robot_nearest_the_cursor() -> None:
    world = armed("displacer")
    target, other = dummy(world, 170, 120), dummy(world, 110, 60)
    fire(world)
    assert (world.player.x, world.player.y) == (170, 120)
    assert target.health == 999 - DEFAULT.displacer_damage, "the blast where it lands"
    assert other.health == 999


def test_displacer_with_no_robot_in_reach_costs_nothing() -> None:
    world = armed("displacer")
    fire(world)
    assert "teleport" not in world.player.cooldowns


def test_meteor_leaps_untouchable_and_crashes_down_in_a_blast() -> None:
    world = armed("meteor")
    robot = dummy(world, 175, 120)
    fire(world, DEFAULT.meteor_ticks // 2)
    assert world.player.protected and robot.health == 999, "in the air, nothing lands yet"
    fire(world, DEFAULT.meteor_ticks)
    assert world.player.x == pytest.approx(166) and world.player.leap == 0
    assert robot.health == 999 - DEFAULT.meteor_damage


def test_blasts_hurt_the_regulator_but_never_move_it() -> None:
    world = armed("impact_blink")
    world.rival = encounter_world(1, 1, "lateral", arena=OPEN).rival
    rival = world.rival
    rival.x, rival.y, rival.boot = 185.0, 120.0, 0
    before = rival.health
    fire(world)
    assert rival.health == before - DEFAULT.impact_damage
    # Only its own step moves it this tick, never the blast's knockback (12 px outward).
    assert math.dist((rival.x, rival.y), (185.0, 120.0)) < 2.0


# Edges and evolutions -------------------------------------------------------------------------

WALL = (150.0, 100.0, 16.0, 40.0)  # a pillar right of the Surge, x 150 to 166, y 100 to 140
WALLED = Arena(
    room=SUBSTATION.room,
    size=(320, 240),
    bounds=(0.0, 0.0, 320.0, 240.0),
    obstacles=(WALL,),
    player_spawn=(110.0, 120.0),
    practice_spawns=((10.0, 10.0), (310.0, 10.0)),
    rival_spawn=(300.0, 220.0),
)


def walled(power: str, fragments=None):
    world = armed(power, fragments)
    dummy(world, 300, 230)  # far away, so the room is never cleared mid-test
    return world


def fire_walled(world, ticks: int = 0, **aim) -> None:
    cursor = aim or AIM
    step(world, InputFrame(power_q=True, **cursor), arena=WALLED)
    for _ in range(ticks):
        step(world, InputFrame(**cursor), arena=WALLED)


def test_a_meteor_in_the_air_never_locks_a_room_behind_it() -> None:
    """Review of PR #32: a Meteor launched inside a room's doorway, back toward the corridor,
    used to lock the room mid-air and land outside its shut doors, a soft lock."""
    from overload.floor import FLOOR
    from overload.sim import floorplay

    campaign = Campaign(1)
    world = campaign.world
    world.unlocked, world.player.slots = ["spark", "blink", "burst", "meteor"], ["meteor", ""]
    door = next(d for d in FLOOR.doors_of("s1_hall") if d.other == "s1_entry")
    x, y, w, h = door.rect
    world.player.x, world.player.y = floorplay.tile_center((x + w, y + h // 2))
    assert floorplay.room_of(FLOOR, world.player.x, world.player.y).id == "s1_hall"
    back = {"aim_x": int(world.player.x) - 40, "aim_y": int(world.player.y)}
    campaign.step(InputFrame(power_q=True, **back))
    assert world.player.leap > 0 and world.active_room == "", "nothing locks mid-air"
    for _ in range(DEFAULT.meteor_ticks + 5):
        campaign.step(InputFrame(**back))
    assert world.active_room == "" and door.id not in world.locked, "landed outside, doors open"


def test_bolt_lance_stops_at_a_wall() -> None:
    world = walled("bolt_lance")
    fire_walled(world, DEFAULT.lance_ticks + 2)
    assert world.player.x <= WALL[0] - DEFAULT.player_radius + 0.01


def test_a_shock_mine_arms_where_a_wall_stops_it() -> None:
    world = walled("shock_mine")
    fire_walled(world, 16, aim_x=200, aim_y=120)
    (mine,) = world.devices
    assert mine.x < WALL[0] and mine.timer > 0


def test_a_meteor_with_nowhere_to_land_costs_nothing() -> None:
    world = walled("meteor")
    world.player.x = WALL[0] - 10  # every landing spot within reach is inside the pillar
    fire_walled(world, aim_x=200, aim_y=120)
    assert world.player.leap == 0 and "teleport" not in world.player.cooldowns


def test_displacer_never_swaps_the_regulator() -> None:
    world = armed("displacer")
    world.rival = encounter_world(1, 1, "lateral", arena=OPEN).rival
    world.rival.x, world.rival.y = 170.0, 120.0
    fire(world)
    assert "teleport" not in world.player.cooldowns, "no robot to swap with"


def test_displacer_hits_the_swapped_robot_once_and_pushes_it_away() -> None:
    world = armed("displacer")
    robot = dummy(world, 130, 120)  # close: both blasts would reach it
    fire(world, aim_x=130, aim_y=120)
    assert robot.health == 999 - DEFAULT.displacer_damage
    assert robot.x < 110, "pushed away from the Surge, never into it"


def test_chain_jump_stops_at_its_hop_cap() -> None:
    world = armed("chain_jump")
    robots = [dummy(world, 140 + 30 * i, 120) for i in range(DEFAULT.chain_jump_hops + 2)]
    fire(world, aim_x=140, aim_y=120)
    struck = [r for r in robots if r.health < 999]
    assert len(struck) == DEFAULT.chain_jump_hops


def test_chain_jump_tries_the_next_robot_when_the_nearest_has_no_room() -> None:
    world = walled("chain_jump")
    behind = dummy(world, 185, 120)  # behind the pillar: no clear line to it
    open_one = dummy(world, 120, 165)
    fire_walled(world, aim_x=185, aim_y=120)
    assert behind.health == 999 and open_one.health < 999


def test_storm_aura_inherits_chain_and_wide_from_its_ingredients() -> None:
    reach = DEFAULT.storm_aura_range * DEFAULT.fused_wide
    world = armed("storm_aura", dict.fromkeys(BASES, 3))
    near = dummy(world, 110 + DEFAULT.storm_aura_range + 10, 120)  # only the wide aura reaches
    beside = dummy(world, near.x + 20, 120)
    assert DEFAULT.storm_aura_range + 10 < reach + near.radius
    fire(world, DEFAULT.storm_aura_interval + 1)
    assert near.health == 999 - DEFAULT.storm_aura_damage
    assert beside.health == 999 - DEFAULT.spark_chain_damage, "the strike chained"


def test_impact_blink_does_not_inherit_wide() -> None:
    world = armed("impact_blink", dict.fromkeys(BASES, 3))
    fire(world)
    (event,) = [e for e in world.events if e.kind == "blast"]
    assert event.ref == round(DEFAULT.impact_radius)


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


def _damage_per_second(power: str, k: int, fragments) -> float:
    world = armed(power, fragments)
    robots = [dummy(world, x, y) for x, y in _scene(k)]
    fire(world, 240)
    return sum(999 - r.health for r in robots) / (cooldown_of(power, DEFAULT) / 60)


# The first three pairs deal damage, so they compare on damage alone. The pairs Bulwark and
# Magnet join mix damage with stopping shots, so they compare on value: damage dealt plus
# hits prevented, per second of cooldown, against robots that fire at the Surge (spec
# section 5 asks for shots stopped for shield and pull results, recorded in DECISIONS).
DAMAGE_PAIRS = (("spark", "blink"), ("spark", "burst"), ("blink", "burst"))
VALUE_PAIRS = (("spark", "bulwark"), ("spark", "magnet"), ("burst", "bulwark"), ("burst", "magnet"))
# Evolved runs only where an inherited evolution changes damage: Spark + Burst takes CHAIN
# and WIDE. The other pairs inherit only Overdrive (speed) or nothing, so their evolved runs
# would just repeat the stock ones.
GUARD_CASES = [(pair, False) for pair in DAMAGE_PAIRS] + [(("spark", "burst"), True)]


def _volleys_and_damage(power: str | None, k: int) -> tuple[int, int]:
    """Scene k with every robot firing a bolt at the Surge every 40 ticks (staggered), the
    power used once. Returns the damage dealt and the hits the Surge took."""
    world = armed(power or "spark")
    if power is None:
        world.player.slots = ["", ""]
    robots = [dummy(world, x, y) for x, y in _scene(k)]
    player = world.player
    hits = 0
    for tick in range(241):
        for i, robot in enumerate(robots):
            if robot.health > 0 and (tick + i * 10) % 40 == 0:
                dx, dy = normalize(player.x - robot.x, player.y - robot.y)
                speed = DEFAULT.bolt_speed
                world.projectiles.append(
                    Projectile(
                        world.new_id(),
                        robot.x + dx * 10,
                        robot.y + dy * 10,
                        dx * speed,
                        dy * speed,
                        DEFAULT.bolt_radius,
                        1,
                        True,
                        200,
                        "bolt",
                    )
                )
        player.invulnerable, player.charge = 0, DEFAULT.player_max_charge  # count every hit
        step(world, InputFrame(power_q=tick == 0, **AIM), arena=OPEN)
        hits += sum(e.kind == "player_hit" for e in world.events)
    return sum(999 - r.health for r in robots), hits


@pytest.mark.parametrize("pair", VALUE_PAIRS, ids=lambda v: "+".join(v))
def test_higher_rarities_are_worth_more_but_only_modestly(pair) -> None:
    """The power step guard for the pairs Bulwark and Magnet join, on value per second of
    cooldown over 40 fixed scenes (tuned Nov 19 to about 1.20 and 1.50 times the rare)."""
    base = [_volleys_and_damage(None, k)[1] for k in range(40)]
    values = []
    for power in RESULTS[frozenset(pair)]:
        total = 0
        for k in range(40):
            damage, hits = _volleys_and_damage(power, k)
            total += damage + base[k] - hits
        values.append(total / (cooldown_of(power, DEFAULT) / 60))
    rare, epic, legendary = values
    assert rare < epic <= 1.35 * rare
    assert epic < legendary <= 1.75 * rare


@pytest.mark.parametrize(
    "pair, evolutions", GUARD_CASES, ids=lambda v: "+".join(v) if isinstance(v, tuple) else v
)
def test_higher_rarities_are_stronger_but_only_modestly(pair, evolutions) -> None:
    """Spec section 5: damage per second of cooldown, averaged over 40 fixed scenes. An epic
    beats its rare and stays at or under 1.35 times it, a legendary beats its epic and stays
    at or under 1.75 times the rare."""
    fragments = dict.fromkeys(BASES, 3) if evolutions else None
    rare, epic, legendary = (
        sum(_damage_per_second(power, k, fragments) for k in range(40))
        for power in RESULTS[frozenset(pair)]
    )
    assert rare < epic <= 1.35 * rare
    assert epic < legendary <= 1.75 * rare


# Guards --------------------------------------------------------------------------------------


@pytest.mark.parametrize(
    "change",
    [
        {"fuse_odds": (100, 0, 0)},
        {"fuse_odds": (60, -1, 41)},
        {"reroll_cost": 0},
        {"fuse_odds": (60.0, 30, 10)},
        {"lance_speed": 6.0},
        {"meteor_knock": 40.0},
        {"meteor_ticks": 10},
        {"storm_aura_interval": 0},
        {"shock_mine_speed": 0.0},
        {"fused_wide": 0.9},
        {"meteor_range": 10.0},
        {"fuse_guarantee_after": 0},
    ],
)
def test_fusion_guards(change) -> None:
    with pytest.raises(ValueError):
        dataclasses.replace(DEFAULT, **change)
