"""Damage to the Surge and to the Regulator, shared by shots, powers, robots and hazards."""

from __future__ import annotations

from overload.sim.state import Event, World
from overload.sim.tuning import Tuning


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


def hurt_player(world: World, damage: int, tuning: Tuning) -> None:
    """Apply damage unless the Surge is dodging or recently hit."""
    player = world.player
    if player.protected:
        return
    player.charge = max(0, player.charge - damage)
    player.invulnerable = tuning.hit_invulnerability
    world.events.append(Event("player_hit", player.x, player.y))
