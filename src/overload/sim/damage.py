"""Damage to the Regulator, shared by shots, sparks and Arc Trails."""

from __future__ import annotations

from overload.sim.state import Event, World


def damage_rival(world: World, damage: int, x: float, y: float) -> None:
    """Hurt the Regulator unless its protocol boot shield is up."""
    rival = world.rival
    if rival is None or rival.health <= 0:
        return
    if rival.boot > 0:
        world.events.append(Event("rival_shielded", x, y))
        return
    rival.health -= damage
    world.events.append(Event("rival_hit", rival.x, rival.y))
    if rival.health <= 0:
        world.events.append(Event("rival_destroyed", rival.x, rival.y))
