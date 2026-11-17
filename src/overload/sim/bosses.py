"""The Regulator's three chassis (overhaul, Nov 17): one per sector chamber, each with its
own health, pace and signature attack, layered on top of the protocol it runs.

The protocol (pressure, spacing or lateral) stays the only thing the rival model chooses. The
chassis is fixed per sector and identical in both comparison conditions, so the experiment
still compares protocol choice alone. A signature attack has its own tell (at least 0.5 s,
validated in Tuning) and the protocol waits while it runs, so the two never overlap.

- Linesman (sector 1): the gentlest. Every so often it stops and throws a ring of 8 bolts.
- Transformer (sector 2): tougher and quicker. It stomps a wide shockwave that runs along the
  floor, the Breaker's slam at boss size.
- Grid Core (sector 3): the toughest. It warps in two Arc Drones to fight beside it, and at
  half health it overloads (phase 2): a shield flicker, then a faster pace and a twin spiral
  of bolts in place of the summons.

The legacy single-arena mode keeps the plain "regulator" with no signature.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Boss:
    kind: str
    name: str
    health: int
    pace: float  # multiplies the protocol's rest between attacks (lower is more often)
    signature: str  # "", "ring", "quake", "summon" or "spiral"
    overload: str = ""  # the phase 2 signature, if any
    overload_pace: float = 1.0


REGULATOR = Boss("regulator", "REGULATOR", 0, 1.0, "")
BOSSES = {
    1: Boss("linesman", "LINESMAN", 36, 1.0, "ring"),
    2: Boss("transformer", "TRANSFORMER", 52, 0.85, "quake"),
    3: Boss("grid_core", "GRID CORE", 66, 0.85, "summon", overload="spiral", overload_pace=0.65),
}
BY_KIND = {boss.kind: boss for boss in (REGULATOR, *BOSSES.values())}

# Exact unit vectors, so the sim stays free of trig: eight compass directions for the ring,
# and a 20 degree turn for the spiral.
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
COS20 = 0.9396926207859084
SIN20 = 0.3420201433256687
