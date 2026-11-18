"""The Regulator's three chassis (boss rework, Nov 18, docs/BOSS_DESIGN.md): one per sector
chamber, each with three phases and its own rotation of attacks that no robot uses.

The protocol (pressure, spacing or lateral) stays the only thing the rival model chooses: it
decides how the Regulator moves and its protocol attack. The chassis kit is fixed per sector
and identical in both comparison conditions, so the experiment still compares protocol
choice alone. Each kit attack has its own tell (at least 0.75 s, validated in Tuning). The
protocol waits while one runs, as it waited for the old signatures.

- Linesman (sector 1), "read the pattern, find the gap": rings of bolts, Live Wire lines
  fanned from its crossarm, insulator volleys that burst where they land. It vents after
  Live Wire.
- Transformer (sector 2), "bait it, then punish it": quakes, coolant sprays of slow orbs,
  and the Bull Charge, which stuns it when it hits a wall.
- Grid Core (sector 3), the finale: drone summons, the Lattice (half the floor burns in a
  checkerboard), spirals, and in phase 3 its core opens for a four-arm spiral. It vents
  after the Lattice, the spiral and the core spiral.

Phases change at two thirds and one third of its health. The legacy single-arena mode keeps
the plain "regulator" with no kit.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Phase:
    rotation: tuple[str, ...]  # kit attacks, in order, round and round
    every: int  # ticks between kit attacks
    pace: float  # multiplies the protocol's rest between attacks (lower is more often)


@dataclass(frozen=True)
class Boss:
    kind: str
    name: str
    health: int
    radius: float = 0.0  # 0 uses Tuning.rival_radius (the legacy Regulator)
    phases: tuple[Phase, ...] = ()


REGULATOR = Boss("regulator", "REGULATOR", 0)
BOSSES = {
    1: Boss(
        "linesman",
        "LINESMAN",
        48,
        18.0,
        (
            Phase(("ring", "live_wire"), 270, 1.0),
            Phase(("double_ring", "live_wire", "volley"), 210, 0.9),
            Phase(("double_ring", "live_wire_twice", "volley"), 180, 0.8),
        ),
    ),
    2: Boss(
        "transformer",
        "TRANSFORMER",
        64,
        22.0,  # the widest chassis: a bigger circle covers its tank and hump
        (
            Phase(("quake", "charge"), 220, 0.9),
            Phase(("spray", "double_quake", "charge"), 190, 0.8),
            Phase(("spray", "double_quake", "charge_twice"), 160, 0.7),
        ),
    ),
    3: Boss(
        "grid_core",
        "GRID CORE",
        80,
        18.0,
        (
            Phase(("summon", "lattice"), 280, 0.85),
            Phase(("spiral", "lattice_twice", "summon"), 240, 0.75),
            Phase(("core_spiral", "lattice_twice"), 210, 0.65),
        ),
    ),
}
BY_KIND = {boss.kind: boss for boss in (REGULATOR, *BOSSES.values())}
# The kit attacks the chassis stands still to vent after (its punish window). The Bull
# Charge vents only if it hits a wall.
VENTS = {
    "live_wire",
    "live_wire_twice",
    "lattice",
    "lattice_twice",
    "spiral",
    "core_spiral",
}


def phase_for(boss: Boss, health: int, max_health: int) -> int:
    """1, 2 or 3: the next phase starts at two thirds and at one third of its health."""
    if not boss.phases:
        return 1
    phase = 1
    for k in (2, 1):
        if health * 3 <= max_health * k:
            phase += 1
    return min(phase, len(boss.phases))


# Exact unit vectors and rotations, so the sim stays free of trig at runtime.
_D = 0.7071067811865476
RING = (
    (1.0, 0.0),
    (_D, _D),
    (0.0, 1.0),
    (-_D, _D),
    (-1.0, 0.0),
    (-_D, -_D),
    (0.0, -1.0),
    (_D, -_D),
)
_A, _B = 0.9238795325112867, 0.3826834323650898
RING_OFFSET = (  # the second ring of a Double Ring, half a gap round (22.5 degrees)
    (_A, _B),
    (_B, _A),
    (-_B, _A),
    (-_A, _B),
    (-_A, -_B),
    (-_B, -_A),
    (_B, -_A),
    (_A, -_B),
)
_H = 0.8660254037844386
SIX = ((1.0, 0.0), (0.5, _H), (-0.5, _H), (-1.0, 0.0), (-0.5, -_H), (0.5, -_H))
COS20 = 0.9396926207859084
SIN20 = 0.3420201433256687
# (cos, sin) of the turns that fan lines and sprays, in degrees.
TURN = {
    6: (0.9945218953682733, 0.10452846326765347),
    10: (0.984807753012208, 0.17364817766693033),
    12: (0.9781476007338057, 0.20791169081775934),
    18: (0.9510565162951535, 0.3090169943749474),
    20: (COS20, SIN20),
    24: (0.9135454576426009, 0.4067366430758002),
    30: (0.8660254037844387, 0.5),
    36: (0.8090169943749475, 0.5877852522924731),
}
WIRES = (-20, 0, 20)  # Live Wire's lines, degrees off the aim
WIRES_GAPS = (-30, -10, 10, 30)  # its second set, in the first set's gaps
SPRAY = (-36, -24, -12, 0, 12, 24, 36)  # Coolant Spray's first fan
SPRAY_GAPS = (-30, -18, -6, 6, 18, 30)  # and its second, into the gaps


def turn(dx: float, dy: float, degrees: int) -> tuple[float, float]:
    """Rotate a unit vector by one of the TURN angles (negative turns the other way)."""
    if degrees == 0:
        return dx, dy
    c, s = TURN[abs(degrees)]
    if degrees < 0:
        s = -s
    return dx * c - dy * s, dx * s + dy * c
