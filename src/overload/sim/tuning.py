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
    player_radius: float = 12.0
    player_speed: float = 4.2
    player_max_charge: int = 6
    hit_invulnerability: int = 40

    gun_cooldown: int = 10
    shot_speed: float = 13.0
    shot_radius: float = 3.0
    shot_damage: int = 1
    shot_ttl: int = 70

    dodge_ticks: int = 9
    dodge_speed: float = 11.0
    dodge_cooldown: int = 45

    bolt_speed: float = 6.0
    bolt_radius: float = 6.0
    bolt_damage: int = 1
    bolt_ttl: int = 240

    arc_mite_radius: float = 15.0
    arc_mite_health: int = 6
    arc_mite_fire_interval: int = 96
    arc_mite_tell: int = 27
    arc_mite_recovery: int = 18

    def tuning_id(self) -> str:
        """Short stable hash of every value, for traces and the build stamp."""
        blob = json.dumps(asdict(self), sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(blob.encode()).hexdigest()[:8]


DEFAULT = Tuning()
