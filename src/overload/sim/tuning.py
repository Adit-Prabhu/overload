"""Numbers that define how the game plays, pinned per build.

All times are in ticks at 60 per second, all speeds in pixels per tick. Both comparison
conditions always use the same Tuning. `tuning_id` goes into traces and the build stamp.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass

TICK_RATE = 60


@dataclass(frozen=True)
class Tuning:
    """Pixel scale: 16 px tiles, the view is 256 x 144. Radii are body sizes."""

    player_radius: float = 5.0
    player_speed: float = 1.3
    player_max_charge: int = 6
    hit_invulnerability: int = 40

    gun_cooldown: int = 10
    shot_speed: float = 4.5
    shot_radius: float = 1.5
    shot_damage: int = 1
    shot_ttl: int = 60

    dodge_ticks: int = 9
    dodge_speed: float = 3.2
    dodge_cooldown: int = 45

    bolt_speed: float = 1.9
    bolt_radius: float = 2.5
    bolt_damage: int = 1
    bolt_ttl: int = 240

    arc_mite_radius: float = 6.0
    arc_mite_health: int = 6
    arc_mite_fire_interval: int = 96
    arc_mite_tell: int = 27
    arc_mite_recovery: int = 18

    def __post_init__(self) -> None:
        """Reject values that would break readability rules or the tell logic."""
        if self.arc_mite_tell < 0.40 * TICK_RATE:
            raise ValueError("Arc Mite tell must last at least 0.40 s")
        if self.arc_mite_recovery < 0.25 * TICK_RATE:
            raise ValueError("Arc Mite recovery must last at least 0.25 s")
        if self.arc_mite_fire_interval - self.arc_mite_tell < self.arc_mite_recovery:
            raise ValueError("Arc Mite fire interval leaves no room for recovery")
        if self.arc_mite_fire_interval // 2 <= self.arc_mite_tell:
            raise ValueError("Arc Mite first shot could start inside its tell window")
        if self.dodge_speed >= self.player_radius:
            raise ValueError("Dodge speed must stay below the player radius to avoid tunneling")

    def tuning_id(self) -> str:
        """Short stable hash of every value, for traces and the build stamp."""
        blob = json.dumps(asdict(self), sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(blob.encode()).hexdigest()[:8]


DEFAULT = Tuning()
