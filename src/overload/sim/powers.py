"""Stolen powers: the base powers, their evolutions and chance fusion.

Destroying a machine breaks its charge loose. Absorbing the first charge of a power unlocks
it and fills an empty slot (Q, then E). Every later charge goes into that power's bank and
counts toward its evolution. In the loadout menu the player equips abilities to the two
slots and fuses two base powers. Each fusion rolls a rarity (rare, epic or legendary) from a
stream fed only by the run seed and the number of fusions so far. The first fusion of a pair
is free, a reroll spends banked charges. Fusing never removes its ingredients
(docs/POWERS_AND_FUSION.md). The kit (unlocked abilities, absorbed and banked charges,
rarities, slots) carries from one encounter to the next. A retry restores the kit the
encounter started with, fusion count included, so the same rolls come back.

Every rule here is deterministic and lives in the simulation. Nothing here is visible to the
rival model except, later, counts of power uses.
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field

from overload.sim.aiming import launch_point
from overload.sim.arena import Arena
from overload.sim.bosses import RING
from overload.sim.collision import blocked, move_body
from overload.sim.damage import damage_rival
from overload.sim.geometry import (
    circles_overlap,
    length,
    normalize,
    outside_bounds,
    segment_distance_sq,
)
from overload.sim.inputs import InputFrame
from overload.sim.state import Charge, Event, Projectile, Trail, World
from overload.sim.tuning import DEFAULT, Tuning

BASE_POWERS = ("spark", "blink", "burst")
# The recipe order is the order F tries them in the Fuse Box. Blink + Burst stays unsupported.
RECIPE_ORDER = (("spark", "blink"), ("spark", "burst"))
RECIPES = {
    frozenset(("spark", "blink")): "arc_trail",
    frozenset(("spark", "burst")): "shock_cone",
}
INGREDIENTS = {RECIPES[frozenset(pair)]: pair for pair in RECIPE_ORDER}
ABILITIES = ("spark", "blink", "burst", "arc_trail", "shock_cone")
DROPS = {"drone": "spark", "relay": "blink", "breaker": "burst"}
SLOTS = 2
# Blink and Arc Trail are both teleports, Burst and Shock Cone both pulses: each pair shares a
# cooldown, so two slots can never chain them into a double jump or a double pulse.
COOLDOWN_KEYS = {
    "spark": "spark",
    "blink": "teleport",
    "arc_trail": "teleport",
    "burst": "pulse",
    "shock_cone": "pulse",
}
# One evolution per base power, unlocked by two more charges after the first (GDD).
EVOLUTIONS = {"spark": "CHAIN", "blink": "OVERDRIVE", "burst": "WIDE"}
# Every fusion rolls one of these. Each rarity of a pair is its own named power.
RARITIES = ("rare", "epic", "legendary")
FUSION_NAMES = {
    "arc_trail": ("ARC TRAIL", "STORM STEP", "THUNDERHEAD"),
    "shock_cone": ("SHOCK CONE", "SHOCK FAN", "OVERCURRENT"),
}


def fused_name(ability: str, rarity: str) -> str:
    """The name of a fused power at a rarity, e.g. STORM STEP for an epic Arc Trail."""
    return FUSION_NAMES[ability][RARITIES.index(rarity)]


def evolved(fragments: dict[str, int], power: str, tuning: Tuning) -> bool:
    return fragments.get(power, 0) >= tuning.evolve_at


@dataclass
class Kit:
    """What the Surge carries between encounters."""

    unlocked: list[str] = field(default_factory=list)
    fragments: dict[str, int] = field(default_factory=dict)  # every charge absorbed
    slots: list[str] = field(default_factory=lambda: [""] * SLOTS)
    bank: dict[str, int] = field(default_factory=dict)  # spare charges, spent on rerolls
    rarity: dict[str, str] = field(default_factory=dict)  # each fused power's rarity
    fusions: int = 0  # fusions so far this run: the roll stream's index
    streak: int = 0  # rares in a row, for the guarantee

    @classmethod
    def from_world(cls, world: World) -> Kit:
        return cls(
            list(world.unlocked),
            dict(world.fragments),
            list(world.player.slots),
            dict(world.bank),
            dict(world.rarity),
            world.fusions,
            world.streak,
        )

    def apply(self, world: World) -> None:
        world.unlocked = list(self.unlocked)
        world.fragments = dict(self.fragments)
        world.player.slots = list(self.slots)
        world.bank = dict(self.bank)
        world.rarity = dict(self.rarity)
        world.fusions = self.fusions
        world.streak = self.streak


# Fuse Box ------------------------------------------------------------------------------------


def fuse(kit: Kit, a: str, b: str, seed: int, tuning: Tuning = DEFAULT) -> str:
    """Fuse two base powers and roll the result's rarity. The first fusion of a pair is
    free. Fusing it again is a reroll: it spends `reroll_cost` banked charges of each
    ingredient and the new rarity replaces the old one, better or worse. Returns "fused",
    "missing" (an ingredient is not unlocked), "unsupported" (no such recipe) or
    "no_charges" (a reroll the bank cannot pay for). Only "fused" changes the kit, and it
    never removes the ingredients."""
    recipe = RECIPES.get(frozenset((a, b)))
    if recipe is None or a == b:
        return "unsupported"
    if a not in kit.unlocked or b not in kit.unlocked:
        return "missing"
    if recipe in kit.unlocked:
        cost = tuning.reroll_cost
        if kit.bank.get(a, 0) < cost or kit.bank.get(b, 0) < cost:
            return "no_charges"
        kit.bank[a] -= cost
        kit.bank[b] -= cost
    else:
        kit.unlocked.append(recipe)
    rarity = roll_rarity(seed, kit.fusions, kit.streak >= tuning.fuse_guarantee_after, tuning)
    kit.rarity[recipe] = rarity
    kit.fusions += 1
    kit.streak = kit.streak + 1 if rarity == "rare" else 0
    return "fused"


def rarity_of(world: World, ability: str) -> str:
    """A fused power's rarity ("rare" until rolled otherwise), "" for a base power."""
    if ability not in FUSION_NAMES:
        return ""
    return world.rarity.get(ability, "rare")


def roll_rarity(seed: int, n: int, guaranteed: bool, tuning: Tuning = DEFAULT) -> str:
    """The rarity of fusion n of a run. Its own stream, fed only by the run seed and n,
    never the world's RNG, so a fusion cannot shift any combat roll and the nth fusion rolls
    the same in both conditions. Guaranteed (after enough rares in a row), rare is out and
    epic and legendary keep their ratio."""
    weights = list(tuning.fuse_odds)
    if guaranteed:
        weights[0] = 0
    pick = random.Random(f"overload-fusion:{seed}:{n}").randrange(sum(weights))
    for rarity, weight in zip(RARITIES, weights, strict=True):
        if pick < weight:
            return rarity
        pick -= weight
    raise AssertionError("unreachable: pick is below the sum of the weights")


def equip(kit: Kit, slot: int, ability: str) -> bool:
    """Put an unlocked ability in a slot ("" empties it). An ability already in the other
    slot swaps places. Returns False, changing nothing, for an invalid request."""
    if not 0 <= slot < SLOTS or (ability and ability not in kit.unlocked):
        return False
    if ability and ability in kit.slots:
        other = kit.slots.index(ability)
        kit.slots[other] = kit.slots[slot]
    kit.slots[slot] = ability
    return True


# Encounter rules -----------------------------------------------------------------------------


def use_powers(world: World, inp: InputFrame, tuning: Tuning, arena: Arena) -> None:
    """Q uses slot 0, E slot 1. Nothing happens while dodging, on cooldown or with an empty
    slot. A Blink with nowhere valid to land is rejected and keeps its cooldown free."""
    player = world.player
    for slot, pressed in enumerate((inp.power_q, inp.power_e)):
        ability = player.slots[slot]
        if not pressed or not ability or ability not in world.unlocked or player.dodging:
            continue
        key = COOLDOWN_KEYS[ability]
        if player.cooldowns.get(key, 0) > 0:
            continue
        if ability == "spark":
            if not _spark(world, tuning, arena):
                continue  # fizzled against a wall at point blank: no cost, not a use
            player.cooldowns[key] = tuning.spark_cooldown
        elif ability in ("burst", "shock_cone"):
            _burst(world, tuning, arena, rarity_of(world, ability))
            player.cooldowns[key] = (
                tuning.shock_cone_cooldown if ability == "shock_cone" else tuning.burst_cooldown
            )
        elif _blink(world, inp, tuning, arena, rarity_of(world, ability)):
            cooldown = (
                tuning.arc_trail_cooldown if ability == "arc_trail" else tuning.blink_cooldown
            )
            player.cooldowns[key] = cooldown
        else:
            continue  # rejected Blink: no cost, and it does not count as a use
        world.events.append(Event(f"power_{ability}", player.x, player.y, slot))


def _spark(world: World, tuning: Tuning, arena: Arena, direction=None, arc="", damage=None) -> bool:
    player = world.player
    start = launch_point(world, tuning, arena)
    if start is None:
        return False
    _add_spark(world, tuning, start, direction or (player.aim_x, player.aim_y), arc, damage)
    return True


def _add_spark(world: World, tuning: Tuning, start, direction, arc: str = "", damage=None) -> None:
    ax, ay = direction
    world.projectiles.append(
        Projectile(
            id=world.new_id(),
            x=start[0],
            y=start[1],
            vx=ax * tuning.spark_speed,
            vy=ay * tuning.spark_speed,
            radius=tuning.spark_radius,
            damage=tuning.spark_damage if damage is None else damage,
            hostile=False,
            ttl=tuning.spark_ttl,
            kind="spark",
            arc=arc,
        )
    )


def _spark_ring(world: World, tuning: Tuning, arena: Arena, x: float, y: float) -> None:
    """Thunderhead: eight light sparks out from a point, the boss ring's exact vectors. They
    never chain. A spark whose start is inside a prop, outside the room or behind a wall is
    not fired."""
    offset = tuning.player_radius + tuning.spark_radius + 1.0
    for dx, dy in RING:
        start = (x + dx * offset, y + dy * offset)
        if _free(world, start, tuning.spark_radius, arena) and _clear_path(
            world, (x, y), start, arena
        ):
            _add_spark(world, tuning, start, (dx, dy), "none", tuning.thunder_spark_damage)


# The Shock Cone's spark fans: rotations by 20 and 40 degrees as exact constants (no runtime
# trig). Rare fires three sparks, epic and legendary five.
_COS20 = 0.9396926207859084
_SIN20 = 0.3420201433256687
_COS40 = 0.766044443118978
_SIN40 = 0.6427876096865393


def _fan(ax: float, ay: float, wide: bool) -> list[tuple[float, float]]:
    turns = [(_COS20, _SIN20)] + ([(_COS40, _SIN40)] if wide else [])
    directions = [(ax, ay)]
    for c, s in turns:
        directions.append((ax * c - ay * s, ax * s + ay * c))
        directions.append((ax * c + ay * s, -ax * s + ay * c))
    return directions


def _burst(world: World, tuning: Tuning, arena: Arena, rarity: str = "") -> None:
    """A short discharge cone along the aim: damages and knocks back every robot in it,
    clears hostile shots in it and dents the Regulator (too heavy to push). Evolved, the
    cone is wider and longer. A robot counts when its center is in the cone (its body may
    poke out), and the pulse passes over props. With a rarity it is a Shock Cone and adds a
    fan of sparks: three for Shock Cone (rare), five for Shock Fan (epic), five for
    Overcurrent (legendary), whose inner three chain twice."""
    shock = bool(rarity)
    player = world.player
    wide = evolved(world.fragments, "burst", tuning)
    reach = tuning.burst_wide_range if wide else tuning.burst_range
    cone = tuning.burst_wide_cos if wide else tuning.burst_cos
    ax, ay = player.aim_x, player.aim_y

    def inside(x: float, y: float, radius: float) -> bool:
        dx, dy = x - player.x, y - player.y
        distance = length(dx, dy)
        if distance > reach + radius:
            return False
        return distance == 0.0 or (dx * ax + dy * ay) / distance >= cone

    for robot in world.hostiles:
        if robot.health > 0 and inside(robot.x, robot.y, robot.radius):
            robot.health -= tuning.burst_damage
            world.events.append(Event("hostile_hit", robot.x, robot.y, robot.id))
            for _ in range(2):  # two half steps, each under the thinnest obstacle
                robot.x, robot.y = move_body(
                    robot.x,
                    robot.y,
                    ax * tuning.burst_knock / 2,
                    ay * tuning.burst_knock / 2,
                    robot.radius,
                    arena,
                    world,
                )
    rival = world.rival
    if rival is not None and rival.health > 0 and inside(rival.x, rival.y, rival.radius):
        damage_rival(world, tuning.burst_damage, rival.x, rival.y)
    kept = []
    for shot in world.projectiles:
        if shot.hostile and inside(shot.x, shot.y, shot.radius):
            world.events.append(Event("fizzle", shot.x, shot.y, shot.id))
        else:
            kept.append(shot)
    world.projectiles = kept
    world.events.append(
        Event("burst", player.x, player.y, 1 if wide else 0, "shock_cone" if shock else "burst")
    )
    if shock:
        # The outer pair of a five-spark fan (the 40 degree ones) hits lighter, and only the
        # inner three of Overcurrent's chain.
        for i, direction in enumerate(_fan(ax, ay, wide=rarity != "rare")):
            damage = tuning.fan_spark_damage if i >= 3 else None
            arc = "overcurrent" if rarity == "legendary" and i < 3 else ""
            _spark(world, tuning, arena, direction, arc, damage)


def spark_chain(world: World, tuning: Tuning, hit, overcurrent: bool = False) -> None:
    """Evolved Spark: a spark that hits a robot arcs on to the nearest other robot.
    An Overcurrent spark chains evolved or not (lighter if not), then arcs on once more
    from that robot to the next, so it always reaches one robot further than an evolved
    Spark's."""
    chained = evolved(world.fragments, "spark", tuning)
    if not (overcurrent or chained):
        return
    damage = tuning.spark_chain_damage if chained else tuning.overcurrent_chain_damage
    struck = {hit.id}
    source = hit
    for jump in range(2 if overcurrent else 1):
        others = [
            r
            for r in world.hostiles
            if r.health > 0
            and r.id not in struck
            and length(r.x - source.x, r.y - source.y) <= tuning.spark_chain_range
        ]
        if not others:
            return
        target = min(others, key=lambda r: (length(r.x - source.x, r.y - source.y), r.id))
        target.health -= damage if jump == 0 else tuning.overcurrent_chain_damage
        world.events.append(Event("chain_from", source.x, source.y, source.id))
        world.events.append(Event("chain", target.x, target.y, target.id))
        world.events.append(Event("hostile_hit", target.x, target.y, target.id))
        struck.add(target.id)
        source = target


def blink_destination(
    world: World, inp: InputFrame, tuning: Tuning, arena: Arena
) -> tuple[float, float] | None:
    """Where a Blink toward the cursor would land, or None if nowhere is valid. The Surge
    lands as far along the aim as it can, up to the cursor and the Blink range, but never
    inside a wall or prop, outside the room, or on the far side of a wall."""
    player = world.player
    dx, dy = inp.aim_x - player.x, inp.aim_y - player.y
    ux, uy = normalize(dx, dy)
    if not (ux or uy):
        ux, uy = player.aim_x, player.aim_y
    reach = min(max(length(dx, dy), tuning.blink_min_distance), tuning.blink_distance)
    distance = reach
    while distance >= tuning.blink_min_distance:
        spot = (player.x + ux * distance, player.y + uy * distance)
        if _free(world, spot, tuning.player_radius, arena) and _clear_path(
            world, (player.x, player.y), spot, arena
        ):
            return spot
        distance -= 4.0
    return None


def _free(world: World, spot: tuple[float, float], radius: float, arena: Arena) -> bool:
    if outside_bounds(spot, radius, arena.bounds):
        return False
    return not blocked(world, arena, spot, radius)


def _clear_path(
    world: World, start: tuple[float, float], end: tuple[float, float], arena: Arena
) -> bool:
    """No wall or prop crosses the straight line. Samples every 4 px, well under the
    thinnest obstacle."""
    dx, dy = end[0] - start[0], end[1] - start[1]
    steps = max(1, int(length(dx, dy) / 4.0))
    for i in range(1, steps + 1):
        point = (start[0] + dx * i / steps, start[1] + dy * i / steps)
        if blocked(world, arena, point, 1.0):
            return False
    return True


def _blink(world: World, inp: InputFrame, tuning: Tuning, arena: Arena, rarity: str) -> bool:
    """A Blink, or with a rarity an Arc Trail: the trail is Arc Trail's (rare), longer and
    wider for Storm Step (epic), and Thunderhead (legendary) adds a ring of sparks."""
    player = world.player
    spot = blink_destination(world, inp, tuning, arena)
    if spot is None:
        world.events.append(Event("blink_rejected", player.x, player.y))
        return False
    start = (player.x, player.y)
    world.events.append(Event("blink_from", *start))
    player.x, player.y = spot
    world.events.append(Event("blink_to", *spot))
    if rarity:
        storm = rarity != "rare"
        world.trails.append(
            Trail(
                world.new_id(),
                start[0],
                start[1],
                spot[0],
                spot[1],
                tuning.storm_trail_ttl if storm else tuning.trail_ttl,
                tuning.storm_trail_width if storm else tuning.trail_width,
            )
        )
        if rarity == "legendary":
            _spark_ring(world, tuning, arena, *spot)
    if evolved(world.fragments, "blink", tuning):
        player.boost = tuning.boost_ticks  # Overdrive: a burst of speed on arrival
    return True


def tick_trails(world: World, tuning: Tuning) -> None:
    """Each Arc Trail pulses damage into everything touching it every `trail_interval`
    ticks, then fades. The Regulator's boot shield blocks it like any other hit."""
    survivors = []
    for trail in world.trails:
        trail.ttl -= 1
        if trail.ttl % tuning.trail_interval == 0:
            a, b = (trail.x1, trail.y1), (trail.x2, trail.y2)
            for hostile in world.hostiles:
                reach = hostile.radius + trail.width
                if hostile.health > 0 and segment_distance_sq((hostile.x, hostile.y), a, b) < (
                    reach * reach
                ):
                    hostile.health -= tuning.trail_damage
                    world.events.append(Event("hostile_hit", hostile.x, hostile.y, hostile.id))
            rival = world.rival
            if rival is not None and rival.health > 0:
                reach = rival.radius + trail.width
                if segment_distance_sq((rival.x, rival.y), a, b) < reach * reach:
                    damage_rival(world, tuning.trail_damage, rival.x, rival.y)
        if trail.ttl > 0:
            survivors.append(trail)
    world.trails = survivors


def drop_charge(world: World, kind: str, x: float, y: float) -> None:
    power = DROPS.get(kind)
    if power:
        world.charges.append(Charge(world.new_id(), power, x, y))


def absorb_charges(world: World, tuning: Tuning, everything: bool = False) -> None:
    """Absorb charges the Surge touches (or all of them, when the encounter is won)."""
    player = world.player
    left = []
    for charge in world.charges:
        if everything or circles_overlap(
            (player.x, player.y), tuning.player_radius, (charge.x, charge.y), tuning.charge_radius
        ):
            _absorb(world, charge, tuning)
        else:
            left.append(charge)
    world.charges = left


def _absorb(world: World, charge: Charge, tuning: Tuning) -> None:
    world.fragments[charge.kind] = world.fragments.get(charge.kind, 0) + 1
    if charge.kind in world.unlocked:
        world.bank[charge.kind] = world.bank.get(charge.kind, 0) + 1  # spare, for rerolls
        count = world.fragments[charge.kind]
        if count == tuning.evolve_at:
            event = Event("evolve", charge.x, charge.y, charge.id, charge.kind)
        elif count > tuning.evolve_at:  # GDD: a pickup after the evolution says so
            event = Event("fully_evolved", charge.x, charge.y, charge.id, charge.kind)
        else:
            event = Event("absorb", charge.x, charge.y, charge.id, charge.kind)
        world.events.append(event)
        return
    world.unlocked.append(charge.kind)
    world.events.append(Event("unlock", charge.x, charge.y, charge.id, charge.kind))
    slots = world.player.slots
    if "" in slots:
        slots[slots.index("")] = charge.kind


def tick_cooldowns(world: World) -> None:
    world.player.cooldowns = {k: v - 1 for k, v in world.player.cooldowns.items() if v > 1}
