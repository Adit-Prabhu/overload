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
    phase: str = ""  # Relay: "", "blink" (landing marker showing) or "aim"
    dest_x: float = 0.0
    dest_y: float = 0.0


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


@dataclass(slots=True)
class Event:
    """Something that happened this tick, for rendering, audio and traces. Not hashed."""

    kind: str
    x: float = 0.0
    y: float = 0.0
    ref: int = 0


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
        "rng": rng_state,
    }
    blob = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(blob.encode()).hexdigest()[:16]
