"""The fused powers that are more than a base power with a twist: every epic and legendary,
and Blink + Burst's rare (docs/POWERS_AND_FUSION.md section 5). Each is its own verb.

| Pair | Rare | Epic | Legendary |
| Spark + Blink | Arc Trail (powers.py) | Bolt Lance | Chain Jump |
| Spark + Burst | Shock Cone (powers.py) | Shock Mine | Storm Aura |
| Blink + Burst | Impact Blink | Displacer | Meteor |

Each use function returns False when it has nothing valid to do, so the use costs nothing
and is not counted. Everything is deterministic and trig-free, like the rest of the
simulation. Anything that damages a robot damages the Regulator the same way (through its
boot shield), but nothing moves the Regulator: it is too heavy to knock, swap or pull.
"""

from __future__ import annotations

from overload.sim.arena import Arena
from overload.sim.damage import damage_rival
from overload.sim.geometry import circles_overlap, length, normalize, outside_bounds
from overload.sim.inputs import InputFrame
from overload.sim.powers import (
    INGREDIENTS,
    _clear_path,
    _free,
    blink_destination,
    evolved,
    knock,
    spark_chain,
)
from overload.sim.state import Device, Event, World
from overload.sim.tuning import Tuning

RIVAL_ID = -1  # stands for the Regulator in a list of struck bodies


# Fused powers inherit the evolutions their pair's rare inherits, so a higher rarity never
# loses out once an ingredient evolves: Arc Trail takes Overdrive, Shock Cone takes CHAIN and
# WIDE (its sparks chain, its cone widens), Impact Blink takes Overdrive. This narrows spec
# section 3 ("a fused power uses its ingredients' evolutions"): inheriting both ingredients
# measured Bolt Lance at 1.50 times Arc Trail and Displacer below Impact Blink, outside the
# power step guard (recorded in docs/DECISIONS_AND_OPEN_QUESTIONS.md).
INHERITS = {
    frozenset(("spark", "blink")): ("blink",),
    frozenset(("spark", "burst")): ("spark", "burst"),
    frozenset(("blink", "burst")): ("blink",),
    # The pairs Bulwark and Magnet join inherit nothing yet: their evolutions (REFLECT,
    # CRUSH) do not carry into fused powers (DECISIONS, Nov 19).
    frozenset(("spark", "bulwark")): (),
    frozenset(("spark", "magnet")): (),
    frozenset(("burst", "bulwark")): (),
    frozenset(("burst", "magnet")): (),
    frozenset(("blink", "bulwark")): (),
    frozenset(("blink", "magnet")): (),
    frozenset(("bulwark", "magnet")): (),
}


def _evolved(world: World, power: str, ingredient: str, tuning: Tuning) -> bool:
    """True when `power` inherits `ingredient`'s evolution and it has evolved: an evolved
    Spark makes its strikes chain, an evolved Burst widens its blasts and field, an evolved
    Blink gives Overdrive after it moves the Surge."""
    inherited = INHERITS[frozenset(INGREDIENTS[power])]
    return ingredient in inherited and evolved(world.fragments, ingredient, tuning)


def _overdrive(world: World, power: str, tuning: Tuning) -> None:
    if _evolved(world, power, "blink", tuning):
        world.player.boost = tuning.boost_ticks


def _reach(world: World, power: str, radius: float, tuning: Tuning) -> float:
    """An evolved Burst widens the blasts and field of the powers that inherit it."""
    return radius * tuning.fused_wide if _evolved(world, power, "burst", tuning) else radius


def _targets(world: World):
    """Every living body a power can strike: robots, then the Regulator."""
    bodies = [h for h in world.hostiles if h.health > 0]
    rival = world.rival
    if rival is not None and rival.health > 0:
        bodies.append(rival)
    return bodies


def _id(body) -> int:
    return getattr(body, "id", RIVAL_ID)


# Fused powers that keep striking a body in reach: the Tesla Coil, the Fortress and the
# Shield Toss. A chassis is big and stays close under Clamp and Oscillate, so they strike it
# for `chassis_field_damage` (balance pass, Nov 19: the protocol check).
CHASSIS_FIELDS = ("fortress",)


def _strike(
    world: World,
    body,
    damage: int,
    power: str = "",
    tuning: Tuning | None = None,
    field: bool = False,
):
    if _id(body) == RIVAL_ID:
        if tuning is not None and (field or power in CHASSIS_FIELDS):
            damage = min(damage, tuning.chassis_field_damage)
        damage_rival(world, damage, body.x, body.y)
        return
    body.health -= damage
    world.events.append(Event("hostile_hit", body.x, body.y, body.id))
    if power and tuning is not None and _evolved(world, power, "spark", tuning):
        spark_chain(world, tuning, body)


def blast(
    world: World,
    tuning: Tuning,
    arena: Arena,
    x: float,
    y: float,
    radius: float,
    damage: int,
    push: float,
    power: str,
    skip: int | None = None,
) -> None:
    """A full ring blast: damages every body that reaches into the ring (but `skip`), knocks
    robots straight out from the center and erases hostile shots inside it. A robot right at
    the center is pushed away from the Surge."""
    radius = _reach(world, power, radius, tuning)
    player = world.player
    for body in _targets(world):
        if _id(body) == skip or length(body.x - x, body.y - y) > radius + body.radius:
            continue
        _strike(world, body, damage, power, tuning)
        if _id(body) != RIVAL_ID and push:
            ux, uy = normalize(body.x - x, body.y - y)
            if not (ux or uy):
                ux, uy = normalize(body.x - player.x, body.y - player.y)
            if not (ux or uy):
                ux, uy = player.aim_x, player.aim_y
            knock(world, body, ux, uy, push, arena)
    kept = []
    for shot in world.projectiles:
        if shot.hostile and length(shot.x - x, shot.y - y) <= radius + shot.radius:
            world.events.append(Event("fizzle", shot.x, shot.y, shot.id))
        else:
            kept.append(shot)
    world.projectiles = kept
    world.events.append(Event("blast", x, y, round(radius), power))


def _arc(world: World, start, end) -> None:
    """A lightning arc for the view (the same pair of events as an evolved Spark's chain)."""
    world.events.append(Event("chain_from", start[0], start[1]))
    world.events.append(Event("chain", end[0], end[1]))


# Spark + Blink -------------------------------------------------------------------------------


def bolt_lance(world: World, inp: InputFrame, tuning: Tuning, arena: Arena) -> bool:
    """The Surge becomes a bolt and dashes along the aim, untouchable, striking every body
    it passes once. It rides the dodge: walls stop it, bodies do not."""
    player = world.player
    player.dodge_dx, player.dodge_dy = player.aim_x, player.aim_y
    player.dodge_ticks = tuning.lance_ticks
    player.lance = True
    player.struck = []
    world.events.append(Event("lance", player.x, player.y))
    return True


def _lance_strikes(world: World, tuning: Tuning) -> None:
    player = world.player
    for body in _targets(world):
        if _id(body) in player.struck:
            continue
        if circles_overlap(
            (player.x, player.y),
            tuning.player_radius + tuning.lance_reach,
            (body.x, body.y),
            body.radius,
        ):
            _strike(world, body, tuning.lance_damage, "bolt_lance", tuning)
            player.struck.append(_id(body))


def chain_jump(world: World, inp: InputFrame, tuning: Tuning, arena: Arena) -> bool:
    """Hop to the body nearest the cursor (within reach of the Surge) and strike it, then
    hop on to the nearest body not struck yet, up to `chain_jump_hops` strikes. The Surge
    lands beside each one, on the side it came from. A hop needs a free spot and a clear
    line, else the chain ends there. Rejected if not even the first hop can land."""
    player = world.player
    near = [
        b
        for b in _targets(world)
        if length(b.x - player.x, b.y - player.y) <= tuning.chain_jump_range
    ]
    if not near:
        world.events.append(Event("blink_rejected", player.x, player.y, 0, "chain_jump"))
        return False
    near.sort(key=lambda b: (length(b.x - inp.aim_x, b.y - inp.aim_y), _id(b)))
    origin = (player.x, player.y)
    # The first hop goes to the body nearest the cursor that has room beside it.
    target = next((b for b in near if _landing(world, tuning, arena, b, origin)), None)
    struck: list[int] = []
    while target is not None and len(struck) < tuning.chain_jump_hops:
        spot = _landing(world, tuning, arena, target, origin)
        if spot is None:
            break
        _arc(world, origin, spot)
        player.x, player.y = spot
        _strike(world, target, tuning.chain_jump_damage, "chain_jump", tuning)
        struck.append(_id(target))
        origin = spot
        rest = [
            b
            for b in _targets(world)
            if _id(b) not in struck
            and length(b.x - target.x, b.y - target.y) <= tuning.chain_jump_hop
        ]
        target = min(
            rest, key=lambda b: (length(b.x - spot[0], b.y - spot[1]), _id(b)), default=None
        )
    if not struck:
        world.events.append(Event("blink_rejected", player.x, player.y, 0, "chain_jump"))
        return False
    player.invulnerable = max(player.invulnerable, tuning.chain_jump_grace)
    _overdrive(world, "chain_jump", tuning)
    return True


def _landing(world: World, tuning: Tuning, arena: Arena, target, origin):
    """Where a Chain Jump hop lands beside `target`, on the side it comes from, or None
    when that spot is blocked or out of a clear line."""
    ux, uy = normalize(origin[0] - target.x, origin[1] - target.y)
    if not (ux or uy):
        ux, uy = -world.player.aim_x, -world.player.aim_y
    gap = target.radius + tuning.player_radius + 2.0
    spot = (target.x + ux * gap, target.y + uy * gap)
    if _free(world, spot, tuning.player_radius, arena) and _clear_path(world, origin, spot, arena):
        return spot
    return None


# Spark + Burst -------------------------------------------------------------------------------


def shock_mine(world: World, inp: InputFrame, tuning: Tuning, arena: Arena) -> bool:
    """Lob a charge toward the cursor (at most `shock_mine_range` away). It stops early at a
    wall, then bursts after its fuse."""
    player = world.player
    dx, dy = inp.aim_x - player.x, inp.aim_y - player.y
    ux, uy = normalize(dx, dy)
    if not (ux or uy):
        ux, uy = player.aim_x, player.aim_y
    reach = min(length(dx, dy), tuning.shock_mine_range)
    target = (player.x + ux * reach, player.y + uy * reach)
    world.devices.append(
        Device(world.new_id(), "mine", player.x, player.y, target[0], target[1], -1)
    )
    return True


def storm_aura(world: World, inp: InputFrame, tuning: Tuning, arena: Arena) -> bool:
    """For `storm_aura_ticks`, a field around the Surge strikes the nearest body in reach
    every `storm_aura_interval` ticks."""
    world.player.aura = tuning.storm_aura_ticks
    return True


# Blink + Burst -------------------------------------------------------------------------------


def impact_blink(world: World, inp: InputFrame, tuning: Tuning, arena: Arena) -> bool:
    """Blink, then a full ring blast on landing."""
    player = world.player
    spot = blink_destination(world, inp, tuning, arena)
    if spot is None:
        world.events.append(Event("blink_rejected", player.x, player.y, 0, "impact_blink"))
        return False
    world.events.append(Event("blink_from", player.x, player.y))
    player.x, player.y = spot
    world.events.append(Event("blink_to", *spot))
    _overdrive(world, "impact_blink", tuning)
    blast(
        world,
        tuning,
        arena,
        *spot,
        tuning.impact_radius,
        tuning.impact_damage,
        tuning.impact_knock,
        "impact_blink",
    )
    return True


def displacer(world: World, inp: InputFrame, tuning: Tuning, arena: Arena) -> bool:
    """Swap places with the robot nearest the cursor (within reach, in clear line), then
    both spots blast. Rejected when no robot is in reach or either spot cannot hold the
    body that would land there."""
    player = world.player
    here = (player.x, player.y)
    near = [
        h
        for h in world.hostiles
        if h.health > 0
        and length(h.x - player.x, h.y - player.y) <= tuning.displacer_range
        and _clear_path(world, here, (h.x, h.y), arena)
    ]
    near.sort(key=lambda h: (length(h.x - inp.aim_x, h.y - inp.aim_y), h.id))
    for robot in near:
        there = (robot.x, robot.y)
        if _free(world, there, tuning.player_radius, arena) and _free(
            world, here, robot.radius, arena
        ):
            world.events.append(Event("blink_from", *here))
            player.x, player.y = there
            robot.x, robot.y = here
            world.events.append(Event("blink_to", *there))
            world.events.append(Event("swap", here[0], here[1], robot.id))
            _overdrive(world, "displacer", tuning)
            # The blast where the Surge lands, then the one where the robot lands. The
            # swapped robot is hit once, by its own blast, however close the swap was.
            blast(
                world,
                tuning,
                arena,
                *there,
                tuning.displacer_radius,
                tuning.displacer_damage,
                tuning.displacer_knock,
                "displacer",
                skip=robot.id,
            )
            blast(
                world,
                tuning,
                arena,
                *here,
                tuning.displacer_radius,
                tuning.displacer_damage,
                tuning.displacer_knock,
                "displacer",
            )
            return True
    world.events.append(Event("blink_rejected", player.x, player.y, 0, "displacer"))
    return False


def meteor(world: World, inp: InputFrame, tuning: Tuning, arena: Arena) -> bool:
    """Leap toward the cursor (up to `meteor_range`), untouchable in the air for
    `meteor_ticks` with a marker where it will land, and crash down in a blast."""
    player = world.player
    spot = blink_destination(world, inp, tuning, arena, reach=tuning.meteor_range)
    if spot is None:
        world.events.append(Event("blink_rejected", player.x, player.y, 0, "meteor"))
        return False
    player.leap = tuning.meteor_ticks
    player.leap_x0, player.leap_y0 = player.x, player.y
    player.leap_x1, player.leap_y1 = spot
    world.events.append(Event("leap", player.x, player.y))
    return True


USE = {
    "bolt_lance": bolt_lance,
    "chain_jump": chain_jump,
    "shock_mine": shock_mine,
    "storm_aura": storm_aura,
    "impact_blink": impact_blink,
    "displacer": displacer,
    "meteor": meteor,
}


# Every tick ----------------------------------------------------------------------------------


def tick(world: World, tuning: Tuning, arena: Arena) -> None:
    """Run what fused powers leave going: a lance's strikes, a leap in the air, the aura's
    strikes and the mines."""
    player = world.player
    if player.lance and player.dodging:
        _lance_strikes(world, tuning)
        if player.dodge_ticks == 1:  # the last tick of the dash
            _overdrive(world, "bolt_lance", tuning)
    if player.leap > 0:
        player.leap -= 1
        done = (tuning.meteor_ticks - player.leap) / tuning.meteor_ticks
        player.x = player.leap_x0 + (player.leap_x1 - player.leap_x0) * done
        player.y = player.leap_y0 + (player.leap_y1 - player.leap_y0) * done
        if player.leap == 0:
            _overdrive(world, "meteor", tuning)
            player.invulnerable = max(player.invulnerable, tuning.meteor_grace)
            blast(
                world,
                tuning,
                arena,
                player.x,
                player.y,
                tuning.meteor_radius,
                tuning.meteor_damage,
                tuning.meteor_knock,
                "meteor",
            )
    if player.aura > 0:
        player.aura -= 1
        if player.aura % tuning.storm_aura_interval == 0:
            near = [
                b
                for b in _targets(world)
                if length(b.x - player.x, b.y - player.y)
                <= _reach(world, "storm_aura", tuning.storm_aura_range, tuning) + b.radius
            ]
            if near:
                body = min(near, key=lambda b: (length(b.x - player.x, b.y - player.y), _id(b)))
                _arc(world, (player.x, player.y), (body.x, body.y))
                _strike(world, body, tuning.storm_aura_damage, "storm_aura", tuning)
    _tick_mines(world, tuning, arena)


def _tick_mines(world: World, tuning: Tuning, arena: Arena) -> None:
    kept = []
    for mine in world.devices:
        if mine.timer < 0:  # in flight
            dx, dy = mine.tx - mine.x, mine.ty - mine.y
            gap = length(dx, dy)
            speed = tuning.shock_mine_speed
            ahead = (
                (mine.tx, mine.ty)
                if gap <= speed
                else (mine.x + dx / gap * speed, mine.y + dy / gap * speed)
            )
            if outside_bounds(ahead, 2.0, arena.bounds) or not _clear_path(
                world, (mine.x, mine.y), ahead, arena
            ):
                mine.timer = tuning.shock_mine_fuse  # stopped by a wall: arm here
            else:
                mine.x, mine.y = ahead
                if gap <= speed:
                    mine.timer = tuning.shock_mine_fuse
            kept.append(mine)
            continue
        mine.timer -= 1
        if mine.timer > 0:
            kept.append(mine)
            continue
        blast(
            world,
            tuning,
            arena,
            mine.x,
            mine.y,
            tuning.shock_mine_radius,
            tuning.shock_mine_damage,
            tuning.shock_mine_knock,
            "shock_mine",
        )
    world.devices = kept
