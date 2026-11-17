"""Numbers that define how the game plays, pinned per build.

All times are in ticks at 60 per second, all speeds in pixels per tick. Both comparison
conditions always use the same Tuning. `tuning_id` goes into traces and the build stamp.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass

TICK_RATE = 60
THINNEST_OBSTACLE = 14.0  # px, the narrowest prop footprint in the arena


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

    # The Regulator. Every attack has a tell of at least 0.5 s (30 ticks).
    rival_radius: float = 14.0
    rival_health: int = 40
    rival_boot: int = 90
    rival_speed: float = 0.8
    rival_contact_damage: int = 1

    clamp_speed: float = 1.2  # closes faster than it backs off, still below the Surge's speed
    clamp_range: float = 88.0
    clamp_tell: int = 30
    clamp_dash_ticks: int = 20
    clamp_dash_speed: float = 3.6
    clamp_recovery: int = 36
    clamp_rest: int = 24

    insulate_min_distance: float = 96.0
    insulate_max_distance: float = 150.0
    insulate_hazard_interval: int = 150
    insulate_hazard_tell: int = 36
    insulate_hazard_active: int = 150
    insulate_orb_interval: int = 110
    insulate_orb_tell: int = 30
    orb_speed: float = 1.2
    orb_radius: float = 4.0
    orb_ttl: int = 400

    oscillate_speed: float = 1.0
    oscillate_turn: int = 90
    oscillate_interval: int = 84
    oscillate_tell: int = 30
    hazard_damage: int = 1

    # Powers. A power on cooldown, or a rejected Blink, costs nothing.
    charge_radius: float = 6.0
    spark_speed: float = 3.2
    spark_radius: float = 3.0
    spark_damage: int = 3
    spark_ttl: int = 45
    spark_cooldown: int = 40
    blink_distance: float = 56.0
    blink_min_distance: float = 24.0
    blink_cooldown: int = 75
    trail_ttl: int = 120
    trail_width: float = 4.0
    trail_damage: int = 1
    trail_interval: int = 12  # ticks between trail damage pulses
    arc_trail_cooldown: int = 150

    # The Relay: blinks to a marked spot, then aims and fires. It carries Blink.
    relay_radius: float = 7.0
    relay_health: int = 8
    relay_idle: int = 60
    relay_blink_tell: int = 30
    relay_aim_tell: int = 30
    relay_hop_min: float = 40.0
    relay_hop_max: float = 80.0

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
        for name in ("clamp_tell", "insulate_hazard_tell", "insulate_orb_tell", "oscillate_tell"):
            if getattr(self, name) < 0.50 * TICK_RATE:
                raise ValueError(f"{name}: Regulator tells must last at least 0.50 s")
        if self.clamp_recovery < 0.60 * TICK_RATE:
            raise ValueError("Clamp lunges need at least 0.60 s of recovery")
        reach = self.clamp_dash_speed * self.clamp_dash_ticks + self.rival_radius
        if self.clamp_range > reach + self.player_radius:
            raise ValueError("Clamp would start lunges it cannot finish")
        if self.clamp_dash_speed >= THINNEST_OBSTACLE:
            raise ValueError("Clamp dashes could tunnel through the thinnest obstacle")
        if self.spark_speed + 2 * self.spark_radius >= THINNEST_OBSTACLE:
            raise ValueError("Sparks could tunnel through the thinnest obstacle")
        if self.relay_blink_tell < 0.50 * TICK_RATE or self.relay_aim_tell < 0.40 * TICK_RATE:
            raise ValueError("Relay tells are below the readability minimums")
        if self.blink_min_distance > self.blink_distance:
            raise ValueError("Blink minimum distance exceeds its range")
        if self.shot_speed + 2 * self.shot_radius >= THINNEST_OBSTACLE:
            raise ValueError("Shots could tunnel through the thinnest obstacle")
        if self.dodge_speed >= self.player_radius:
            raise ValueError("Dodge speed must stay below the player radius to avoid tunneling")

    def tuning_id(self) -> str:
        """Short stable hash of every value, for traces and the build stamp."""
        blob = json.dumps(asdict(self), sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(blob.encode()).hexdigest()[:8]


DEFAULT = Tuning()
