"""Authoritative game state. The game owns all of it. Nothing here is ever sent to a model."""

from __future__ import annotations

import hashlib
import json
import random
from dataclasses import asdict, dataclass, field
from typing import Literal

Outcome = Literal["playing", "down", "clear"]


@dataclass(slots=True)
class Player:
    x: float
    y: float
    charge: int
    aim_x: float = 1.0
    aim_y: float = 0.0
    facing: int = 1  # 1 right, -1 left: the side the caster is held on
    boost: int = 0  # Overdrive Blink: ticks of extra speed left
    gun_cooldown: int = 0
    dodge_ticks: int = 0
    dodge_cooldown: int = 0
    dodge_dx: float = 0.0
    dodge_dy: float = 0.0
    invulnerable: int = 0
    slots: list[str] = field(default_factory=lambda: ["", ""])  # Q and E, "" when empty
    cooldowns: dict[str, int] = field(default_factory=dict)  # per ability, in ticks

    @property
    def dodging(self) -> bool:
        return self.dodge_ticks > 0

    @property
    def protected(self) -> bool:
        return self.dodge_ticks > 0 or self.invulnerable > 0


@dataclass(slots=True)
class Projectile:
    id: int
    x: float
    y: float
    vx: float
    vy: float
    radius: float
    damage: int
    hostile: bool
    ttl: int
    kind: str = "shot"  # shot, spark, bolt or orb
    # How a spark arcs on from a robot it hits: "" when Spark is evolved, "overcurrent"
    # always and twice, "none" never (Thunderhead's ring).
    arc: str = ""


@dataclass(slots=True)
class Hostile:
    id: int
    kind: str
    x: float
    y: float
    radius: float
    health: int
    max_health: int
    fire_timer: int
    tell_dx: float = 0.0
    tell_dy: float = 0.0
    phase: str = ""  # Relay Bot: blink or aim. Breaker: raise or recover. Sweeper: rev, rush, rest
    dest_x: float = 0.0
    dest_y: float = 0.0
    tier: int = 1  # the sector it was built for: 2 Cooled, 3 Overcharged (sim/robots.py)


@dataclass(slots=True)
class Rival:
    """The Regulator. `protocol` is fixed for the whole encounter (frozen at entry)."""

    x: float
    y: float
    radius: float
    health: int
    max_health: int
    protocol: str
    boot: int
    action: str = "move"
    timer: int = 0
    cooldown: int = 0
    aim_x: float = 1.0
    aim_y: float = 0.0
    strafe: int = 1
    strafe_timer: int = 90
    # The chassis (sim/bosses.py) and its signature attack, on a timer of its own.
    kind: str = "regulator"
    phase: int = 1
    sig_action: str = "idle"  # idle, tell, fire (the spiral) or quiet
    sig_timer: int = 0
    spin_x: float = 1.0
    spin_y: float = 0.0


@dataclass(slots=True)
class Hazard:
    """An Insulate hazard tile: it arms (the telegraph), then hurts while active."""

    id: int
    x: float
    y: float
    size: float
    arming: int
    active: int


@dataclass(slots=True)
class Charge:
    """A power charge that broke loose from a destroyed machine, waiting to be absorbed."""

    id: int
    kind: str
    x: float
    y: float


@dataclass(slots=True)
class Trail:
    """Arc Trail: an electric line from the blink's departure to its arrival."""

    id: int
    x1: float
    y1: float
    x2: float
    y2: float
    ttl: int
    width: float = 4.0  # how far from the line it reaches past a body's edge


@dataclass(slots=True)
class Shockwave:
    """A Breaker's slam: a ring running along the floor. It hurts once as it passes."""

    id: int
    x: float
    y: float
    radius: float
    hit: bool
    reach: float = 0.0  # where the ring stops (0 means a Breaker's wave_reach)


@dataclass(slots=True)
class Warp:
    """A robot about to warp in: the marker shows for the whole timer (the tell)."""

    id: int
    kind: str
    x: float
    y: float
    timer: int


@dataclass(slots=True)
class Event:
    """Something that happened this tick, for rendering, audio and traces. Not hashed."""

    kind: str
    x: float = 0.0
    y: float = 0.0
    ref: int = 0
    power: str = ""  # for absorb and unlock: which power the charge carried


@dataclass
class World:
    seed: int
    rng: random.Random
    player: Player
    tick: int = 0
    outcome: Outcome = "playing"
    next_id: int = 1
    projectiles: list[Projectile] = field(default_factory=list)
    hostiles: list[Hostile] = field(default_factory=list)
    rival: Rival | None = None
    hazards: list[Hazard] = field(default_factory=list)
    encounter: int = 0
    charges: list[Charge] = field(default_factory=list)
    trails: list[Trail] = field(default_factory=list)
    unlocked: list[str] = field(default_factory=list)  # abilities, in unlock order
    fragments: dict[str, int] = field(default_factory=dict)  # charges absorbed per power
    bank: dict[str, int] = field(default_factory=dict)  # spare charges per power (rerolls)
    rarity: dict[str, str] = field(default_factory=dict)  # each fused power's rarity
    fusions: int = 0  # fusions so far this run, the roll stream's index
    streak: int = 0  # rare fusions in a row, for the guarantee
    locked: list[str] = field(default_factory=list)  # ids of doors that are shut right now
    # The floor (overhaul): rooms lock while robots are active and clear for good.
    mode: str = "room"  # "room": one arena, cleared when empty. "floor": rooms and sectors
    protocol: str = "lateral"  # the Regulator's protocol in the current sector
    active_room: str = ""
    wave: int = 0
    cleared: list[str] = field(default_factory=list)
    warps: list[Warp] = field(default_factory=list)
    shockwaves: list[Shockwave] = field(default_factory=list)
    secret_hits: dict[str, int] = field(default_factory=dict)
    events: list[Event] = field(default_factory=list)

    def new_id(self) -> int:
        value = self.next_id
        self.next_id += 1
        return value


def state_hash(world: World) -> str:
    """Stable fingerprint of everything that affects future play. Events are excluded."""
    rng_state = hashlib.sha256(repr(world.rng.getstate()).encode()).hexdigest()
    payload = {
        "seed": world.seed,
        "tick": world.tick,
        "outcome": world.outcome,
        "next_id": world.next_id,
        "player": asdict(world.player),
        "projectiles": [asdict(p) for p in world.projectiles],
        "hostiles": [asdict(h) for h in world.hostiles],
        "rival": asdict(world.rival) if world.rival else None,
        "hazards": [asdict(h) for h in world.hazards],
        "encounter": world.encounter,
        "charges": [asdict(c) for c in world.charges],
        "trails": [asdict(t) for t in world.trails],
        "unlocked": world.unlocked,
        "fragments": world.fragments,
        "bank": world.bank,
        "rarity": world.rarity,
        "fusions": world.fusions,
        "streak": world.streak,
        "locked": world.locked,
        "mode": world.mode,
        "protocol": world.protocol,
        "active_room": world.active_room,
        "wave": world.wave,
        "cleared": world.cleared,
        "warps": [asdict(w) for w in world.warps],
        "shockwaves": [asdict(s) for s in world.shockwaves],
        "secret_hits": world.secret_hits,
        "rng": rng_state,
    }
    blob = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(blob.encode()).hexdigest()[:16]
