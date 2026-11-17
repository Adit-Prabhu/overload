"""Aiming: the caster is held at the Surge's hand, aim pivots there and shots leave its tip,
so every shot passes exactly through the cursor and visibly comes out of the caster."""

from __future__ import annotations

from overload.sim.arena import Arena
from overload.sim.geometry import circle_hits_rect, normalize
from overload.sim.inputs import InputFrame
from overload.sim.state import Event, Player, World
from overload.sim.tuning import DEFAULT, Tuning


def hand(player: Player, tuning: Tuning = DEFAULT) -> tuple[float, float]:
    """Where the Surge holds the caster. Aim pivots here, so a shot leaves the caster's tip
    and passes exactly through the cursor."""
    return (player.x + player.facing * tuning.hand_x, player.y + tuning.hand_y)


def muzzle(player: Player, tuning: Tuning = DEFAULT) -> tuple[float, float]:
    hx, hy = hand(player, tuning)
    return (hx + player.aim_x * tuning.barrel, hy + player.aim_y * tuning.barrel)


def aim(player: Player, inp: InputFrame, tuning: Tuning = DEFAULT) -> None:
    """Point the caster at the cursor, pivoting at the hand."""
    if inp.aim_x != round(player.x):
        player.facing = -1 if inp.aim_x < player.x else 1
    hx, hy = hand(player, tuning)
    ax, ay = normalize(inp.aim_x - hx, inp.aim_y - hy)
    if ax or ay:
        player.aim_x, player.aim_y = ax, ay


def launch_point(world: World, tuning: Tuning, arena: Arena) -> tuple[float, float] | None:
    """The caster's tip, or None when a wall or prop stands between the body and the tip
    (the shot fizzles against it instead of starting on the far side)."""
    player = world.player
    tip = muzzle(player, tuning)
    dx, dy = tip[0] - player.x, tip[1] - player.y
    for i in range(1, 5):
        point = (player.x + dx * i / 4, player.y + dy * i / 4)
        if any(circle_hits_rect(point, 1.0, rect) for rect in arena.obstacles):
            world.events.append(Event("fizzle", point[0], point[1]))
            return None
    return tip
