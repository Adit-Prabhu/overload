"""Stolen powers: Spark, Blink and their fusion, Arc Trail.

Destroying a machine breaks its charge loose. Absorbing the first charge of a power unlocks
it and fills an empty slot (Q, then E). In the Fuse Box the player equips abilities to the
two slots and fuses two base powers into a recipe. Fusing never consumes its ingredients.
The kit (unlocked abilities, absorbed charges, slots) carries from one encounter to the
next. A retry restores the kit the encounter started with.

Every rule here is deterministic and lives in the simulation. Nothing here is visible to the
rival model except, later, counts of power uses.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from overload.sim.arena import Arena
from overload.sim.damage import damage_rival
from overload.sim.geometry import (
    circle_hits_rect,
    circles_overlap,
    length,
    normalize,
    outside_bounds,
    segment_distance_sq,
)
from overload.sim.inputs import InputFrame
from overload.sim.state import Charge, Event, Projectile, Trail, World
from overload.sim.tuning import Tuning

BASE_POWERS = ("spark", "blink")
RECIPES = {frozenset(("spark", "blink")): "arc_trail"}
ABILITIES = ("spark", "blink", "arc_trail")
DROPS = {"arc_mite": "spark", "relay": "blink"}
SLOTS = 2


@dataclass
class Kit:
    """What the Surge carries between encounters."""

    unlocked: list[str] = field(default_factory=list)
    fragments: dict[str, int] = field(default_factory=dict)
    slots: list[str] = field(default_factory=lambda: [""] * SLOTS)

    @classmethod
    def from_world(cls, world: World) -> Kit:
        return cls(list(world.unlocked), dict(world.fragments), list(world.player.slots))

    def apply(self, world: World) -> None:
        world.unlocked = list(self.unlocked)
        world.fragments = dict(self.fragments)
        world.player.slots = list(self.slots)


# Fuse Box ------------------------------------------------------------------------------------


def fuse(kit: Kit, a: str, b: str) -> str:
    """Fuse two base powers. Returns "fused", "already_fused", "missing" (an ingredient is
    not unlocked) or "unsupported" (no such recipe). Only "fused" changes the kit, and it
    never removes the ingredients."""
    recipe = RECIPES.get(frozenset((a, b)))
    if recipe is None or a == b:
        return "unsupported"
    if a not in kit.unlocked or b not in kit.unlocked:
        return "missing"
    if recipe in kit.unlocked:
        return "already_fused"
    kit.unlocked.append(recipe)
    return "fused"


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
        if player.cooldowns.get(ability, 0) > 0:
            continue
        if ability == "spark":
            _spark(world, tuning)
            player.cooldowns[ability] = tuning.spark_cooldown
        elif _blink(world, inp, tuning, arena, trail=ability == "arc_trail"):
            cooldown = (
                tuning.arc_trail_cooldown if ability == "arc_trail" else tuning.blink_cooldown
            )
            player.cooldowns[ability] = cooldown
        else:
            continue  # rejected Blink: no cost, and it does not count as a use
        world.events.append(Event(f"power_{ability}", player.x, player.y, slot))


def _spark(world: World, tuning: Tuning) -> None:
    player = world.player
    offset = tuning.player_radius + tuning.spark_radius + 2.0
    world.projectiles.append(
        Projectile(
            id=world.new_id(),
            x=player.x + player.aim_x * offset,
            y=player.y + player.aim_y * offset,
            vx=player.aim_x * tuning.spark_speed,
            vy=player.aim_y * tuning.spark_speed,
            radius=tuning.spark_radius,
            damage=tuning.spark_damage,
            hostile=False,
            ttl=tuning.spark_ttl,
            kind="spark",
        )
    )


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
        if _free(spot, tuning.player_radius, arena) and _clear_path(
            (player.x, player.y), spot, arena
        ):
            return spot
        distance -= 4.0
    return None


def _free(spot: tuple[float, float], radius: float, arena: Arena) -> bool:
    if outside_bounds(spot, radius, arena.bounds):
        return False
    return not any(circle_hits_rect(spot, radius, rect) for rect in arena.obstacles)


def _clear_path(start: tuple[float, float], end: tuple[float, float], arena: Arena) -> bool:
    """No wall or prop crosses the straight line. Samples every 4 px, well under the
    thinnest obstacle."""
    dx, dy = end[0] - start[0], end[1] - start[1]
    steps = max(1, int(length(dx, dy) / 4.0))
    for i in range(1, steps + 1):
        point = (start[0] + dx * i / steps, start[1] + dy * i / steps)
        if any(circle_hits_rect(point, 1.0, rect) for rect in arena.obstacles):
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
            _absorb(world, charge)
        else:
            left.append(charge)
    world.charges = left


def _absorb(world: World, charge: Charge) -> None:
    world.fragments[charge.kind] = world.fragments.get(charge.kind, 0) + 1
    if charge.kind in world.unlocked:
        world.events.append(Event("absorb", charge.x, charge.y, charge.id))
        return
    world.unlocked.append(charge.kind)
    world.events.append(Event("unlock", charge.x, charge.y, charge.id))
    slots = world.player.slots
    if "" in slots:
        slots[slots.index("")] = charge.kind


def tick_cooldowns(world: World) -> None:
    world.player.cooldowns = {k: v - 1 for k, v in world.player.cooldowns.items() if v > 1}
