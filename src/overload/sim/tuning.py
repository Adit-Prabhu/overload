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
    hand_x: float = 3.0  # the caster is held this far to the facing side of the body center
    hand_y: float = 1.0  # and this far below it
    barrel: float = 9.0  # shots leave the caster's tip, this far along the aim
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

    drone_radius: float = 6.0
    drone_health: int = 6
    drone_fire_interval: int = 96
    drone_tell: int = 27
    drone_recovery: int = 18

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
    relay_landing_gap: float = 12.0  # never lands this close to the Surge
    shard_speed: float = 2.0
    shard_radius: float = 2.5

    # The rest of the roster (overhaul): every robot has its own attack.
    drone_speed: float = 0.45
    drone_near: float = 56.0
    drone_far: float = 110.0
    breaker_radius: float = 9.0
    breaker_health: int = 16
    breaker_speed: float = 0.55
    breaker_reach: float = 44.0
    breaker_tell: int = 36
    breaker_recover: int = 48
    wave_speed: float = 1.6
    wave_width: float = 4.0
    wave_reach: float = 72.0
    sweeper_radius: float = 5.0
    sweeper_health: int = 4
    sweeper_speed: float = 0.9
    sweeper_trigger: float = 90.0
    sweeper_tell: int = 30
    sweeper_rush_speed: float = 3.0
    sweeper_rush_ticks: int = 22
    sweeper_rest: int = 50
    sentry_radius: float = 7.0
    sentry_health: int = 10
    sentry_interval: int = 150
    sentry_tell: int = 48
    shell_speed: float = 1.2
    shell_radius: float = 3.5
    shell_ttl: int = 300

    # Burst, evolutions and Shock Cone (overhaul step 4).
    evolve_at: int = 3  # charges of one power: the first unlocks it, two more evolve it
    burst_range: float = 44.0
    burst_cos: float = 0.82  # cone half-angle of about 35 degrees
    burst_wide_range: float = 56.0
    burst_wide_cos: float = 0.55  # evolved: about 57 degrees
    burst_damage: int = 2
    burst_knock: float = 12.0
    burst_cooldown: int = 60
    shock_cone_cooldown: int = 110
    spark_chain_range: float = 52.0
    spark_chain_damage: int = 2
    boost_ticks: int = 60
    boost_factor: float = 1.5

    # Regulator chassis signatures (sim/bosses.py): time between them, and their tells.
    ring_tell: int = 48
    quake_tell: int = 48
    quake_reach: float = 120.0
    summon_tell: int = 48
    summon_cap: int = 2  # no summon while this many robots are already up
    spiral_tell: int = 48
    spiral_ticks: int = 60
    spiral_gap: int = 5
    # Sector 3's Overcharged robots (sim/spawns.py tiers). Sector 2's Cooled ones are stock.
    overcharged_health_pct: int = 110  # rounded up, so a 4-health Sweeper gets 5
    overcharged_speed: float = 1.05
    overcharged_rest: float = 0.9

    # Chance fusion (docs/POWERS_AND_FUSION.md): rare, epic and legendary weights, the rares
    # in a row that guarantee epic or better, and the banked charges of each ingredient a
    # reroll costs.
    fuse_odds: tuple[int, int, int] = (60, 30, 10)
    fuse_guarantee_after: int = 2
    reroll_cost: int = 1
    # The fused powers (sim/fusions.py). Each has its own cooldown.
    bolt_lance_cooldown: int = 100
    lance_ticks: int = 15
    lance_speed: float = 4.6
    lance_reach: float = 3.0  # past the Surge's body
    lance_damage: int = 6
    chain_jump_cooldown: int = 240
    chain_jump_range: float = 96.0  # the first hop, from the Surge
    chain_jump_hop: float = 72.0  # each later hop, from the last body struck
    chain_jump_hops: int = 4
    chain_jump_damage: int = 4
    chain_jump_grace: int = 12  # untouchable for a moment after the last hop
    shock_mine_cooldown: int = 120
    shock_mine_range: float = 80.0
    shock_mine_speed: float = 3.0
    shock_mine_fuse: int = 30
    shock_mine_radius: float = 34.0
    shock_mine_damage: int = 4
    shock_mine_knock: float = 12.0
    storm_aura_cooldown: int = 330
    storm_aura_ticks: int = 180
    storm_aura_interval: int = 15
    storm_aura_range: float = 64.0
    storm_aura_damage: int = 2
    impact_blink_cooldown: int = 135
    impact_radius: float = 30.0
    impact_damage: int = 3
    impact_knock: float = 12.0
    displacer_cooldown: int = 150
    displacer_range: float = 110.0
    displacer_radius: float = 26.0
    displacer_damage: int = 2
    displacer_knock: float = 10.0
    meteor_cooldown: int = 270
    meteor_range: float = 96.0
    meteor_ticks: int = 30
    meteor_radius: float = 48.0
    meteor_damage: int = 4
    meteor_knock: float = 12.0
    meteor_grace: int = 12  # untouchable for a moment after landing
    fused_wide: float = 1.25  # an evolved Burst widens its fused powers' blasts and field

    # The boss kits (docs/BOSS_DESIGN.md): the phase change, the vent window and the
    # attacks no robot uses.
    phase_change: int = 72  # shielded, every hostile shot wiped
    vent_ticks: int = 90  # the punish window after a chassis' biggest attack
    core_vent_ticks: int = 105  # after the Grid Core's core spiral
    wire_tell: int = 54
    wire_active: int = 24
    wire_width: float = 3.0
    wire_reach: float = 220.0
    ring_gap: int = 15  # between a Double Ring's rings
    volley_tell: int = 60
    volley_spread: float = 44.0
    charge_tell: int = 60
    charge_again_tell: int = 45  # a re-aimed second charge
    charge_speed: float = 3.6
    charge_ticks: int = 110
    spray_tell: int = 48
    spray_gap: int = 24
    quake_gap: int = 30  # between a Double Quake's rings
    lattice_tell: int = 60
    lattice_active: int = 48
    lattice_again: int = 36  # the second Lattice arms this long after the first burns out
    lattice_cell: float = 32.0  # two tiles: a body fits in a dark cell, a dodge crosses one
    lattice_cols: int = 2  # cells each side of the Surge
    lattice_rows: int = 1
    core_spiral_ticks: int = 90
    # Bulwark (from the Sentry) and Magnet (from the Sweeper), powers spec section 3.
    bulwark_ticks: int = 45
    bulwark_radius: float = 14.0  # the Surge's radius (5) plus 9
    bulwark_cooldown: int = 180  # 150 in the spec: 45 of every 150 ticks left a floor of 0.70
    magnet_range: float = 72.0
    magnet_radius: float = 44.0
    magnet_ticks: int = 30
    magnet_pull: float = 1.5  # px a tick, under the thinnest obstacle: walls win
    magnet_cooldown: int = 120
    magnet_crush_damage: int = 2
    signature_quiet: int = 66  # the protocol rests this long after a signature (a quake's run)

    # Rooms (overhaul): robots warp in after a visible marker, secret walls crack open.
    warp_tell: int = 36
    secret_wall_hits: int = 3

    def __post_init__(self) -> None:
        """Reject values that would break readability rules or the tell logic."""
        if self.drone_tell < 0.40 * TICK_RATE:
            raise ValueError("Arc Drone tell must last at least 0.40 s")
        if self.drone_recovery < 0.25 * TICK_RATE:
            raise ValueError("Arc Drone recovery must last at least 0.25 s")
        if self.drone_fire_interval - self.drone_tell < self.drone_recovery:
            raise ValueError("Arc Drone fire interval leaves no room for recovery")
        if self.drone_fire_interval // 2 <= self.drone_tell:
            raise ValueError("Arc Drone first shot could start inside its tell window")
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
        if self.warp_tell < 0.50 * TICK_RATE:
            raise ValueError("Robots must show their warp marker for at least 0.50 s")
        if not (self.overcharged_health_pct >= 100 and 0.5 <= self.overcharged_rest <= 1.0):
            raise ValueError("Overcharged robots must be at least stock health, rest at most stock")
        rest = self.overcharged_rest
        if round(self.drone_fire_interval * rest) - self.drone_tell < self.drone_recovery:
            raise ValueError("An Overcharged Arc Drone's interval leaves no room for recovery")
        if round(self.sentry_interval * rest) <= self.sentry_tell:
            raise ValueError("An Overcharged Sentry's interval is shorter than its tell")
        if (
            max(self.drone_speed, self.breaker_speed, self.sweeper_speed) * (self.overcharged_speed)
            >= THINNEST_OBSTACLE
        ):
            raise ValueError("Overcharged robots could walk through the thinnest obstacle")
        kit_tells = (
            "ring_tell",
            "quake_tell",
            "summon_tell",
            "spiral_tell",
            "wire_tell",
            "volley_tell",
            "charge_tell",
            "charge_again_tell",
            "spray_tell",
            "lattice_tell",
        )
        for name in kit_tells:
            if getattr(self, name) < 0.75 * TICK_RATE:
                raise ValueError(f"{name}: boss attack tells must last at least 0.75 s")
        if self.charge_speed >= THINNEST_OBSTACLE:
            raise ValueError("A Bull Charge could tunnel through the thinnest obstacle")
        if self.vent_ticks < TICK_RATE or self.phase_change < TICK_RATE:
            raise ValueError("Vent windows and phase changes must last at least 1 s")
        if self.lattice_cell < 2 * (self.player_radius + 1) + 16:
            raise ValueError("A Lattice cell must hold the Surge with room to spare")
        # The second Lattice lights the cells the Surge stepped onto: from a cell's middle to
        # the next cell's middle at walking speed, and never under half a second.
        crossing = (self.lattice_cell / 2 + self.player_radius) / self.player_speed
        if self.lattice_again < max(crossing, 0.5 * TICK_RATE):
            raise ValueError("The second Lattice must leave time to step off its tiles")
        for name in ("breaker_tell", "sweeper_tell", "sentry_tell"):
            if getattr(self, name) < 0.50 * TICK_RATE:
                raise ValueError(f"{name}: robot tells must last at least 0.50 s")
        if self.sentry_interval // 2 <= self.sentry_tell:
            raise ValueError("A Sentry's first shot could start inside its tell window")
        if self.burst_knock / 2 >= THINNEST_OBSTACLE:
            raise ValueError("Burst knockback steps could push a robot through a prop")
        if self.player_speed * self.boost_factor >= self.player_radius:
            raise ValueError("Overdrive speed must stay below the player radius")
        if self.sweeper_rush_speed >= THINNEST_OBSTACLE:
            raise ValueError("A Sweeper's rush could tunnel through the thinnest obstacle")
        if self.blink_min_distance > self.blink_distance:
            raise ValueError("Blink minimum distance exceeds its range")
        if (abs(self.hand_x) + abs(self.hand_y) + self.barrel) / 4 > 4.0:
            raise ValueError("The caster tip is too far out to check for props between")
        if self.shot_speed + 2 * self.shot_radius >= THINNEST_OBSTACLE:
            raise ValueError("Shots could tunnel through the thinnest obstacle")
        odds = self.fuse_odds
        if len(odds) != 3 or any(type(w) is not int or w < 0 for w in odds) or sum(odds[1:]) <= 0:
            raise ValueError("Fusion odds need three whole weights and a chance of epic or better")
        if self.reroll_cost < 1 or self.fuse_guarantee_after < 1:
            raise ValueError("A reroll must cost a charge and the guarantee needs a streak")
        if self.lance_speed >= self.player_radius:
            raise ValueError(
                "Bolt Lance speed must stay below the player radius to avoid tunneling"
            )
        for name in ("shock_mine_knock", "impact_knock", "displacer_knock", "meteor_knock"):
            if getattr(self, name) / 2 >= THINNEST_OBSTACLE:
                raise ValueError(f"{name}: knockback steps could push a robot through a prop")
        if self.shock_mine_speed >= THINNEST_OBSTACLE or self.meteor_ticks < 0.4 * TICK_RATE:
            raise ValueError("A mine could tunnel, or a Meteor's landing marker shows too briefly")
        positive = ("storm_aura_interval", "shock_mine_fuse", "chain_jump_hops", "lance_ticks")
        if any(getattr(self, name) < 1 for name in positive) or self.shock_mine_speed <= 0:
            raise ValueError("Fused power timers, counts and speeds must be positive")
        if self.fused_wide < 1.0:
            raise ValueError("An evolution never shrinks a blast")
        if self.blink_min_distance > self.meteor_range:
            raise ValueError("Meteor range is below the Blink minimum")
        if self.bulwark_radius <= self.player_radius or self.bulwark_ticks < 1:
            raise ValueError("The Bulwark bubble must reach past the Surge and last a tick")
        if self.magnet_pull >= THINNEST_OBSTACLE or self.magnet_pull <= 0:
            raise ValueError("A Magnet step must be positive and under the thinnest obstacle")
        if self.magnet_radius <= 0 or self.magnet_range <= 0 or self.magnet_ticks < 1:
            raise ValueError("Magnet range, radius and duration must be positive")
        if self.dodge_speed >= self.player_radius:
            raise ValueError("Dodge speed must stay below the player radius to avoid tunneling")

    def tuning_id(self) -> str:
        """Short stable hash of every value, for traces and the build stamp."""
        blob = json.dumps(asdict(self), sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(blob.encode()).hexdigest()[:8]


DEFAULT = Tuning()
