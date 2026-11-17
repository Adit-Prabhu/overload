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
from overload.sim.tuning import Tuning

BASE_POWERS = ("spark", "blink", "burst")
# The recipe order is the order F tries them in the Fuse Box. Blink + Burst stays unsupported.
RECIPE_ORDER = (("spark", "blink"), ("spark", "burst"))
RECIPES = {
    frozenset(("spark", "blink")): "arc_trail",
    frozenset(("spark", "burst")): "shock_cone",
}
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


def evolved(fragments: dict[str, int], power: str, tuning: Tuning) -> bool:
    return fragments.get(power, 0) >= tuning.evolve_at


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
        key = COOLDOWN_KEYS[ability]
        if player.cooldowns.get(key, 0) > 0:
            continue
        if ability == "spark":
            if not _spark(world, tuning, arena):
                continue  # fizzled against a wall at point blank: no cost, not a use
            player.cooldowns[key] = tuning.spark_cooldown
        elif ability in ("burst", "shock_cone"):
            _burst(world, tuning, arena, shock=ability == "shock_cone")
            player.cooldowns[key] = (
                tuning.shock_cone_cooldown if ability == "shock_cone" else tuning.burst_cooldown
            )
        elif _blink(world, inp, tuning, arena, trail=ability == "arc_trail"):
            cooldown = (
                tuning.arc_trail_cooldown if ability == "arc_trail" else tuning.blink_cooldown
            )
            player.cooldowns[key] = cooldown
        else:
            continue  # rejected Blink: no cost, and it does not count as a use
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
        for dx, dy in (
            (ax, ay),
            (ax * _COS20 - ay * _SIN20, ax * _SIN20 + ay * _COS20),
            (ax * _COS20 + ay * _SIN20, -ax * _SIN20 + ay * _COS20),
        ):
            _spark(world, tuning, arena, (dx, dy))


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
