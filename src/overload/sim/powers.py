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

BASE_POWERS = ("spark", "blink", "burst", "bulwark", "magnet")
RARITIES = ("rare", "epic", "legendary")
# Each pair fuses into one of three powers, one per rarity, each its own verb
# (docs/POWERS_AND_FUSION.md section 5). The order is the order the menu offers the pairs.
RECIPE_ORDER = (("spark", "blink"), ("spark", "burst"), ("blink", "burst"))
RESULTS = {
    frozenset(("spark", "blink")): ("arc_trail", "bolt_lance", "chain_jump"),
    frozenset(("spark", "burst")): ("shock_cone", "shock_mine", "storm_aura"),
    frozenset(("blink", "burst")): ("impact_blink", "displacer", "meteor"),
}
# Every fused power: its ingredients and its rarity.
FUSED = {
    result: (pair, rarity)
    for pair in RECIPE_ORDER
    for result, rarity in zip(RESULTS[frozenset(pair)], RARITIES, strict=True)
}
INGREDIENTS = {result: pair for result, (pair, _) in FUSED.items()}
ABILITIES = BASE_POWERS + tuple(FUSED)
NAMES = {
    "spark": "SPARK",
    "blink": "BLINK",
    "burst": "BURST",
    "arc_trail": "ARC TRAIL",
    "bolt_lance": "BOLT LANCE",
    "chain_jump": "CHAIN JUMP",
    "shock_cone": "SHOCK CONE",
    "shock_mine": "SHOCK MINE",
    "storm_aura": "STORM AURA",
    "impact_blink": "IMPACT BLINK",
    "displacer": "DISPLACER",
    "meteor": "METEOR",
    "bulwark": "BULWARK",
    "magnet": "MAGNET",
}
DROPS = {
    "drone": "spark",
    "relay": "blink",
    "breaker": "burst",
    "sentry": "bulwark",
    "sweeper": "magnet",
}
SLOTS = 2
# Every teleport shares one cooldown and every pulse another, so two slots can never chain
# them into a double jump or a double pulse.
COOLDOWN_KEYS = {
    "spark": "spark",
    "blink": "teleport",
    "arc_trail": "teleport",
    "bolt_lance": "teleport",
    "chain_jump": "teleport",
    "impact_blink": "teleport",
    "displacer": "teleport",
    "meteor": "teleport",
    "burst": "pulse",
    "shock_cone": "pulse",
    "shock_mine": "pulse",
    "storm_aura": "pulse",
    "bulwark": "shield",
    "magnet": "pull",
}
# One evolution per base power, unlocked by two more charges after the first (GDD).
EVOLUTIONS = {
    "spark": "CHAIN",
    "blink": "OVERDRIVE",
    "burst": "WIDE",
    "bulwark": "REFLECT",
    "magnet": "CRUSH",
}


def cooldown_of(ability: str, tuning: Tuning) -> int:
    return getattr(tuning, f"{ability}_cooldown")


def rarity_of(ability: str) -> str:
    """A fused power's rarity, "" for a base power."""
    return FUSED[ability][1] if ability in FUSED else ""


def owned_result(unlocked, a: str, b: str) -> str:
    """The power the pair a + b has fused into so far, or ""."""
    return next((r for r in RESULTS.get(frozenset((a, b)), ()) if r in unlocked), "")


def evolved(fragments: dict[str, int], power: str, tuning: Tuning) -> bool:
    return fragments.get(power, 0) >= tuning.evolve_at


@dataclass
class Kit:
    """What the Surge carries between encounters."""

    unlocked: list[str] = field(default_factory=list)
    fragments: dict[str, int] = field(default_factory=dict)  # every charge absorbed
    slots: list[str] = field(default_factory=lambda: [""] * SLOTS)
    bank: dict[str, int] = field(default_factory=dict)  # spare charges, spent on rerolls
    fusions: int = 0  # fusions so far this run: the roll stream's index
    streak: int = 0  # rares in a row, for the guarantee

    @classmethod
    def from_world(cls, world: World) -> Kit:
        return cls(
            list(world.unlocked),
            dict(world.fragments),
            list(world.player.slots),
            dict(world.bank),
            world.fusions,
            world.streak,
        )

    def apply(self, world: World) -> None:
        world.unlocked = list(self.unlocked)
        world.fragments = dict(self.fragments)
        world.player.slots = list(self.slots)
        world.bank = dict(self.bank)
        world.fusions = self.fusions
        world.streak = self.streak


# Fuse Box ------------------------------------------------------------------------------------


def fuse(kit: Kit, a: str, b: str, seed: int, tuning: Tuning = DEFAULT) -> str:
    """Fuse two base powers: roll a rarity and take the pair's power of that rarity. The
    first fusion of a pair is free. Fusing it again is a reroll: it spends `reroll_cost`
    banked charges of each ingredient, and the new power replaces the old one in the list
    and in any slot, better or worse. Returns "fused", "missing" (an ingredient is not
    unlocked), "unsupported" (no such recipe) or "no_charges" (a reroll the bank cannot pay
    for). Only "fused" changes the kit, and it never removes the ingredients."""
    results = RESULTS.get(frozenset((a, b)))
    if results is None or a == b:
        return "unsupported"
    if a not in kit.unlocked or b not in kit.unlocked:
        return "missing"
    current = owned_result(kit.unlocked, a, b)
    if current:
        cost = tuning.reroll_cost
        if kit.bank.get(a, 0) < cost or kit.bank.get(b, 0) < cost:
            return "no_charges"
        kit.bank[a] -= cost
        kit.bank[b] -= cost
    rarity = roll_rarity(seed, kit.fusions, kit.streak >= tuning.fuse_guarantee_after, tuning)
    new = results[RARITIES.index(rarity)]
    if current:
        kit.unlocked[kit.unlocked.index(current)] = new
        kit.slots = [new if slot == current else slot for slot in kit.slots]
    else:
        kit.unlocked.append(new)
    kit.fusions += 1
    kit.streak = kit.streak + 1 if rarity == "rare" else 0
    return "fused"


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
    """Q uses slot 0, E slot 1. Nothing happens while dodging, lancing or in the air, on
    cooldown or with an empty slot. A power with nothing valid to do (a Blink with nowhere to
    land, a Chain Jump with no robot in reach) is rejected, keeps its cooldown free and does
    not count as a use."""
    from overload.sim import defenses, fusions  # both build on this module's helpers

    player = world.player
    for slot, pressed in enumerate((inp.power_q, inp.power_e)):
        ability = player.slots[slot]
        if not pressed or not ability or ability not in world.unlocked or player.busy:
            continue
        key = COOLDOWN_KEYS[ability]
        if player.cooldowns.get(key, 0) > 0:
            continue
        if ability == "spark":
            used = _spark(world, tuning, arena)  # False: fizzled against a wall
        elif ability in ("burst", "shock_cone"):
            _burst(world, tuning, arena, shock=ability == "shock_cone")
            used = True
        elif ability in ("blink", "arc_trail"):
            used = _blink(world, inp, tuning, arena, trail=ability == "arc_trail")
        elif ability == "bulwark":
            used = defenses.bulwark(world, inp, tuning, arena)
        elif ability == "magnet":
            used = defenses.magnet(world, inp, tuning, arena)  # False: nowhere to set it
        else:
            used = fusions.USE[ability](world, inp, tuning, arena)
        if not used:
            continue
        player.cooldowns[key] = cooldown_of(ability, tuning)
        world.events.append(Event(f"power_{ability}", player.x, player.y, slot))


def _spark(world: World, tuning: Tuning, arena: Arena, direction=None) -> bool:
    player = world.player
    start = launch_point(world, tuning, arena)
    if start is None:
        return False
    ax, ay = direction or (player.aim_x, player.aim_y)
    world.projectiles.append(
        Projectile(
            id=world.new_id(),
            x=start[0],
            y=start[1],
            vx=ax * tuning.spark_speed,
            vy=ay * tuning.spark_speed,
            radius=tuning.spark_radius,
            damage=tuning.spark_damage,
            hostile=False,
            ttl=tuning.spark_ttl,
            kind="spark",
        )
    )
    return True


# The Shock Cone's spark fan: rotation by 20 degrees as exact constants (no runtime trig).
_COS20 = 0.9396926207859084
_SIN20 = 0.3420201433256687


def _burst(world: World, tuning: Tuning, arena: Arena, shock: bool) -> None:
    """A short discharge cone along the aim: damages and knocks back every robot in it,
    clears hostile shots in it and dents the Regulator (too heavy to push). Evolved, the
    cone is wider and longer. Shock Cone adds a fan of three sparks. A robot counts when its
    center is in the cone (its body may poke out), and the pulse passes over props."""
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
            knock(world, robot, ax, ay, tuning.burst_knock, arena)
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
        for dx, dy in (
            (ax, ay),
            (ax * _COS20 - ay * _SIN20, ax * _SIN20 + ay * _COS20),
            (ax * _COS20 + ay * _SIN20, -ax * _SIN20 + ay * _COS20),
        ):
            _spark(world, tuning, arena, (dx, dy))


def knock(world: World, robot, ux: float, uy: float, distance: float, arena: Arena) -> None:
    """Push a robot `distance` along (ux, uy) in two half steps, each under the thinnest
    obstacle (tuning guards), so walls and props always win."""
    for _ in range(2):
        robot.x, robot.y = move_body(
            robot.x, robot.y, ux * distance / 2, uy * distance / 2, robot.radius, arena, world
        )


def spark_chain(world: World, tuning: Tuning, hit) -> None:
    """Evolved Spark: a spark that hits a robot arcs on to the nearest other robot."""
    if not evolved(world.fragments, "spark", tuning):
        return
    others = [
        r
        for r in world.hostiles
        if r.health > 0
        and r.id != hit.id
        and length(r.x - hit.x, r.y - hit.y) <= tuning.spark_chain_range
    ]
    if not others:
        return
    target = min(others, key=lambda r: (length(r.x - hit.x, r.y - hit.y), r.id))
    target.health -= tuning.spark_chain_damage
    world.events.append(Event("chain_from", hit.x, hit.y, hit.id))
    world.events.append(Event("chain", target.x, target.y, target.id))
    world.events.append(Event("hostile_hit", target.x, target.y, target.id))


def blink_destination(
    world: World, inp: InputFrame, tuning: Tuning, arena: Arena, reach: float = 0.0
) -> tuple[float, float] | None:
    """Where a Blink toward the cursor would land, or None if nowhere is valid. The Surge
    lands as far along the aim as it can, up to the cursor and the Blink range (or `reach`),
    but never inside a wall or prop, outside the room, or on the far side of a wall."""
    player = world.player
    dx, dy = inp.aim_x - player.x, inp.aim_y - player.y
    ux, uy = normalize(dx, dy)
    if not (ux or uy):
        ux, uy = player.aim_x, player.aim_y
    limit = reach or tuning.blink_distance
    distance = min(max(length(dx, dy), tuning.blink_min_distance), limit)
    while distance >= tuning.blink_min_distance:
        spot = (player.x + ux * distance, player.y + uy * distance)
        if _free(world, spot, tuning.player_radius, arena) and _clear_path(
            world, (player.x, player.y), spot, arena
        ):
            return spot
        distance -= 4.0
    return None


def place_point(
    world: World, inp: InputFrame, tuning: Tuning, arena: Arena, reach: float, radius: float
) -> tuple[float, float] | None:
    """Where something set at the cursor lands (a Magnet field): as far along the aim as it
    can, up to the cursor and `reach`, never inside a wall or prop, outside the room or past
    a wall. None if nowhere is valid."""
    player = world.player
    dx, dy = inp.aim_x - player.x, inp.aim_y - player.y
    ux, uy = normalize(dx, dy)
    if not (ux or uy):
        ux, uy = player.aim_x, player.aim_y
    distance = min(max(length(dx, dy), 4.0), reach)
    while distance >= 4.0:
        spot = (player.x + ux * distance, player.y + uy * distance)
        if _free(world, spot, radius, arena) and _clear_path(
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


def _blink(world: World, inp: InputFrame, tuning: Tuning, arena: Arena, trail: bool) -> bool:
    player = world.player
    spot = blink_destination(world, inp, tuning, arena)
    if spot is None:
        world.events.append(Event("blink_rejected", player.x, player.y))
        return False
    start = (player.x, player.y)
    world.events.append(Event("blink_from", *start))
    player.x, player.y = spot
    world.events.append(Event("blink_to", *spot))
    if trail:
        world.trails.append(
            Trail(world.new_id(), start[0], start[1], spot[0], spot[1], tuning.trail_ttl)
        )
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
                reach = hostile.radius + tuning.trail_width
                if hostile.health > 0 and segment_distance_sq((hostile.x, hostile.y), a, b) < (
                    reach * reach
                ):
                    hostile.health -= tuning.trail_damage
                    world.events.append(Event("hostile_hit", hostile.x, hostile.y, hostile.id))
            rival = world.rival
            if rival is not None and rival.health > 0:
                reach = rival.radius + tuning.trail_width
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
