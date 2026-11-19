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
    # Fused powers (sim/fusions.py). Bolt Lance rides the dodge: `lance` marks a dodge that
    # strikes, `struck` the bodies it already hit. Meteor: `leap` ticks left in the air, from
    # (leap_x0, leap_y0) to (leap_x1, leap_y1). Storm Aura: `aura` ticks left.
    lance: bool = False
    struck: list[int] = field(default_factory=list)
    leap: int = 0
    leap_x0: float = 0.0
    leap_y0: float = 0.0
    leap_x1: float = 0.0
    leap_y1: float = 0.0
    aura: int = 0
    shield: int = 0  # Bulwark: ticks the bubble has left
    shield_kind: str = ""  # which power raised it: bulwark, static_guard or bastion
    armor: int = 0  # Capacitor Armor: hits it can still absorb
    armor_ticks: int = 0  # and ticks it has left
    mirror: int = 0  # Mirror Field: ticks left catching shots
    caught: int = 0  # and the shots it has caught so far
    # Rewind: where the Surge stood and the charge it had, one entry a tick, newest last.
    history: list[tuple[float, float, int]] = field(default_factory=list)

    @property
    def dodging(self) -> bool:
        return self.dodge_ticks > 0

    @property
    def busy(self) -> bool:
        """Dodging, lancing or in the air: no shots, no powers, no new dodge."""
        return self.dodge_ticks > 0 or self.leap > 0

    @property
    def protected(self) -> bool:
        return self.dodge_ticks > 0 or self.leap > 0 or self.invulnerable > 0


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


CHARGE_BODY_RADIUS = 2.0


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
    stun: int = 0  # ticks it stands frozen (Ion Hook)


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
    # The chassis kit (sim/bosses.py): which attack runs and where it is in its rotation.
    sig_action: str = "idle"  # idle, tell, active (lines live, charging, spiral) or quiet
    sig_timer: int = 0
    spin_x: float = 1.0
    spin_y: float = 0.0
    sig_name: str = ""
    sig_index: int = 0  # how far round the phase's rotation it is
    sig_step: int = 0  # which part of a multi-part attack (the second ring, the second charge)
    vent: int = 0  # ticks left venting: standing still, taking extra damage
    change: int = 0  # ticks left of a phase change: shielded, nothing fires
    wires: list[tuple[float, float]] = field(default_factory=list)  # Live Wire directions
    marks: list[tuple[float, float]] = field(default_factory=list)  # where volleys land


@dataclass(slots=True)
class Hazard:
    """A hazard tile: it arms (the telegraph), then hurts while active. `kind` is who laid
    it, so each reads differently: Insulate's tiles, a Lattice cell or falling debris."""

    id: int
    x: float
    y: float
    size: float
    arming: int
    active: int
    kind: str = "insulate"


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
class Shockwave:
    """A Breaker's slam: a ring running along the floor. It hurts once as it passes."""

    id: int
    x: float
    y: float
    radius: float
    hit: bool
    reach: float = 0.0  # where the ring stops (0 means a Breaker's wave_reach)


@dataclass(slots=True)
class Device:
    """Something a fused power leaves in the room. A Shock Mine flies to (tx, ty), then
    counts `timer` down and bursts."""

    id: int
    kind: str
    x: float
    y: float
    tx: float
    ty: float
    timer: int
    hit: list[int] = field(default_factory=list)  # bodies it struck already (a Reflector Wave)


@dataclass(slots=True)
class Decoy:
    """Afterimage: a copy of the Surge left behind. Robots and the Regulator aim at it while
    it lasts. Nothing can hurt it, and it hurts nothing."""

    x: float
    y: float
    ticks: int


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
    devices: list[Device] = field(default_factory=list)
    fields: list[Device] = field(default_factory=list)  # Magnet fields: (x, y), ticks left
    decoy: Decoy | None = None  # Afterimage: what robots and the Regulator aim at instead
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
        "devices": [asdict(d) for d in world.devices],
        "fields": [asdict(f) for f in world.fields],
        "decoy": asdict(world.decoy) if world.decoy else None,
        "unlocked": world.unlocked,
        "fragments": world.fragments,
        "bank": world.bank,
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


def target_of(world: World) -> Player | Decoy:
    """What robots and the Regulator aim at: the Afterimage decoy while one stands, else the
    Surge. Hits, contact and shockwaves still land on the Surge itself."""
    return world.decoy if world.decoy is not None else world.player
