"""The Regulator's three chassis, redrawn (Adit, Nov 17: "hate the main bosses, they don't
look good"). One rival, three bodies with their own silhouettes, all walking on legs:

- Linesman (sector 1, orange): a tall biped with a utility pole's crossarm of insulators
  over a hooded lamp head. Its insulator tips light up before its ring of bolts.
- Transformer (sector 2, brass): a wide, low quadruped tank with radiator fins and three
  bushings, trotting on four stubby legs. Its bushings light up before its quake.
- Grid Core (sector 3, violet): a reactor sphere with a crown of pylons and a ring of eyes,
  stalking on three arched legs. Overloaded, its shell cracks and its core blazes.

What stays the same rival on every chassis: the protocol pose (Clamp pincers forward,
Insulate hatched plates at both sides, Oscillate thruster fins), recolored to the shell,
and the gauge needle that always points at the Surge.

Facing right, light from the top left. Built as character grids (rig.py), rendered once.
"""

from __future__ import annotations

import math
from functools import cache

import pygame

from overload.art.palette import rgb
from overload.art.pixel import actors, rig
from overload.art.pixel.grid import flipped, render
from overload.art.pixel.rig import blank, paint, rows_of
from overload.art.pixel.robots import LEGEND, shaded_ellipse

KINDS = ("linesman", "transformer", "grid_core")
SHELLS = {
    "linesman": ("px.hostile.0", "px.hostile.1", "px.hostile.2", "px.hostile.3"),
    "transformer": ("px.coil.0", "px.coil.1", "px.coil.2", "px.coil.3"),
    "grid_core": ("px.core.0", "px.core.1", "px.core.2", "px.core.3"),
}
SHELLS["regulator"] = SHELLS["linesman"]
SIZE = (68, 50)
CX = 34
# Per chassis, in the standing pose (a walking body rides a pixel higher on passing steps):
# where the gauge sits (center, radius), where the protocol arms mount (the right shoulder,
# mirrored for the left), and how far below the body center its feet are.
GAUGE = {"linesman": ((CX, 29), 3), "transformer": ((CX - 2, 25), 3), "grid_core": ((CX, 26), 3)}
SHOULDER = {"linesman": (14, 25), "transformer": (19, 20), "grid_core": (13, 17)}
FEET = {"linesman": 20, "transformer": 18, "grid_core": 22}
_HOSTILE = ("px.hostile.0", "px.hostile.1", "px.hostile.2", "px.hostile.3")


def legend(kind: str) -> dict[str, str]:
    """The shared robot legend with R r o O (dark to light) mapped to this chassis' shell."""
    dark, shade, base, light = SHELLS[kind]
    return {**LEGEND, "R": dark, "r": shade, "o": base, "O": light, "e": light}


def _rect(canvas, x: int, y: int, w: int, h: int, char: str) -> None:
    paint(canvas, [char * w] * h, x, y)


def _disc(canvas, cx: int, cy: int, radius: float, char: str) -> None:
    r = math.ceil(radius)
    for dy in range(-r, r + 1):
        for dx in range(-r, r + 1):
            if dx * dx + dy * dy <= radius * radius:
                paint(canvas, [char], cx + dx, cy + dy)


def _line(canvas, a, b, char: str, width: int = 1) -> None:
    steps = max(abs(b[0] - a[0]), abs(b[1] - a[1]), 1)
    for i in range(steps + 1):
        x = round(a[0] + (b[0] - a[0]) * i / steps)
        y = round(a[1] + (b[1] - a[1]) * i / steps)
        paint(canvas, [char * width], x, y)


def _bob(step: int | None) -> int:
    return -1 if rig.rising(step) else 0


def _gauge(canvas, kind: str, step: int | None) -> None:
    (cx, cy), r = GAUGE[kind]
    cy += _bob(step)
    _disc(canvas, cx, cy, r + 1, "X")
    _disc(canvas, cx, cy, r, "W")
    _disc(canvas, cx, cy, r - 1, "w")
    for dx, dy in ((-r + 1, 0), (0, -r + 1), (r - 1, -1)):
        paint(canvas, ["M"], cx + dx, cy + dy)
    paint(canvas, ["E"], cx + r - 1, cy - 2)  # the red zone of the dial


# Linesman -----------------------------------------------------------------------------------

_INSULATOR = [".dAd.", ".QCc.", "QCCCc", ".QCc.", "QCCCc", ".dMd."]
_LINESMAN_LEG = rig.LegStyle(
    upper="XMMm", lower="XMMm", knee="dXXXd", foot="dXXXXXXd", heel=2, swing=3, lift=2
)


def _linesman(canvas, step, charged: bool, overload: bool) -> None:
    top = 0 if rig.rising(step) else 1
    # Two long legs.
    hips = top + 35
    for half, hip in ((0, CX - 8), (1, CX + 4)):
        swing, lift = rig.pose(step, half, _LINESMAN_LEG)
        rig.leg(canvas, hip, hips, SIZE[1] - hips, swing, lift, _LINESMAN_LEG)
    # The crossarm, with its three insulators and sagging line between them.
    for x in (CX - 17, CX - 2, CX + 13):
        insulator = list(_INSULATOR)
        if charged:
            insulator[0] = ".EwE."
        paint(canvas, insulator, x, top)
    _rect(canvas, CX - 20, top + 6, 41, 1, "X")
    _rect(canvas, CX - 20, top + 7, 41, 1, "M")
    _rect(canvas, CX - 19, top + 8, 39, 1, "m")
    for x in range(CX - 18, CX + 20, 4):
        paint(canvas, ["d"], x, top + 7)
    for a, b in ((CX - 15, CX), (CX, CX + 15)):
        for x in range(a + 2, b - 1):
            sag = round(2 * math.sin(math.pi * (x - a) / (b - a)))
            paint(canvas, ["d"], x, top + 9 + sag)
    _rect(canvas, CX - 1, top + 9, 3, 3, "M")
    # The torso: a tapered shell with a hazard belt and the gauge on the chest.
    for i in range(14):
        y = top + 21 + i
        half = 13 - i // 3
        row = "O" + "o" * (2 * half - 3) + "rR"
        if i == 0:
            row = "O" * (2 * half - 2) + "rR"
        if i >= 11:
            row = "".join("H" if (x + y) % 4 < 2 else "h" for x in range(2 * half))
        paint(canvas, [row], CX - half, y)
    _gauge(canvas, "linesman", step)
    for x, y in ((CX - 8, top + 24), (CX + 7, top + 24), (CX - 8, top + 30), (CX + 7, top + 30)):
        paint(canvas, ["R"], x, y)
    paint(canvas, ["A", ".", "A"], CX + 8, top + 26)
    # Shoulder joints.
    for x in (CX - 14, CX + 14):
        _disc(canvas, x, top + 24, 2.5, "X")
        paint(canvas, ["M"], x + 1, top + 25)
    # The hooded head with one great lamp eye.
    paint(canvas, shaded_ellipse(16, 11, "RroO"), CX - 8, top + 10)
    _rect(canvas, CX - 6, top + 19, 13, 2, "R")
    _rect(canvas, CX - 6, top + 21, 13, 1, "m")
    _disc(canvas, CX + 3, top + 15, 3.2, "v")
    _disc(canvas, CX + 3, top + 15, 2.0, "e" if overload else "E")
    paint(canvas, ["w"], CX + 2, top + 14)
    paint(canvas, ["Q"], CX - 4, top + 12)


# Transformer --------------------------------------------------------------------------------

_BUSHING = [".dOd.", ".QCc.", "QCCCc", ".QCc.", "QCCCc", ".QCc.", "dMMMd"]
_TRANSFORMER_LEG = rig.LegStyle(
    upper="XMMMm", lower="XMMm", knee="dXXXd", foot="dXXXXXXd", heel=2, swing=2, lift=2
)


def _transformer(canvas, step, charged: bool, overload: bool) -> None:
    top = 6 if rig.rising(step) else 7
    hips = top + 27
    # Four stubby legs on a trot: diagonal pairs step together.
    for i, hip in enumerate((CX - 16, CX - 8, CX + 4, CX + 12)):
        swing, lift = rig.pose(step, i % 2, _TRANSFORMER_LEG)
        rig.leg(canvas, hip, hips, SIZE[1] - hips, swing, lift, _TRANSFORMER_LEG)
    # Bushings on the back of the lid.
    for x in (CX - 17, CX - 10, CX - 3):
        bushing = list(_BUSHING)
        if charged:
            bushing[0] = ".EwE."
        paint(canvas, bushing, x, top - 6)
    # The tank: a wide drum lit from above, with rounded ends.
    width, height = 38, 26
    left = CX - width // 2
    for r in range(height):
        y = top + r
        tone = "O" if r < 2 else "o" if r < 13 else "r" if r < 22 else "R"
        inset = 2 if r in (0, height - 1) else 1 if r in (1, height - 2) else 0
        row = tone * (width - 2 * inset)
        paint(canvas, [row], left + inset, y)
        if 3 <= r < 22 and not inset:
            paint(canvas, ["O"], left, y)
            paint(canvas, ["R"], left + width - 1, y)
    # Radiator fins down the back end, coil bands across the side.
    for r in range(4, 21):
        for x in (left + 2, left + 4, left + 6):
            paint(canvas, ["R" if r % 2 else "r"], x, top + r)
    for r in (8, 14, 20):
        _rect(canvas, left + 9, top + r, 20, 1, "r")
    _gauge(canvas, "transformer", step)
    paint(canvas, ["A"], CX - 7, top + 17)
    # The cab head on the front corner of the lid: a hood, a visor, two eyes, a grille.
    hx, hy = CX + 5, top - 7
    paint(canvas, shaded_ellipse(15, 12, "RroO"), hx, hy)
    _rect(canvas, hx + 4, hy + 4, 11, 3, "v")
    eye = "e" if overload else "E"
    paint(canvas, [eye + eye + "." + eye + eye, eye + "w." + eye + "w"], hx + 8, hy + 4)
    for x in range(hx + 5, hx + 14, 2):
        paint(canvas, ["d", "d"], x, hy + 8)
    paint(canvas, ["Q"], hx + 3, hy + 2)
    # A hazard band under the tank.
    for x in range(left + 2, left + width - 2):
        paint(canvas, ["H" if (x // 2) % 2 else "h"], x, top + height)


# Grid Core ----------------------------------------------------------------------------------


def _grid_core(canvas, step, charged: bool, overload: bool) -> None:
    top = 4 if rig.rising(step) else 5
    center = (CX, top + 13)
    # Three arched legs, lifting one at a time.
    for i, (hip, knee, foot) in enumerate(
        (
            ((CX - 11, top + 18), (CX - 22, top + 10), (CX - 26, SIZE[1] - 1)),
            ((CX + 11, top + 18), (CX + 22, top + 10), (CX + 26, SIZE[1] - 1)),
            ((CX - 1, top + 24), (CX + 6, top + 30), (CX + 2, SIZE[1] - 1)),
        )
    ):
        lift = swing = 0
        if step is not None:
            angle = 2 * math.pi * (step / rig.STEPS + i / 3)
            swing = round(2 * math.sin(angle))
            lift = round(3 * max(0.0, math.cos(angle)))
        k = (knee[0] + swing // 2, knee[1] - lift)
        f = (foot[0] + swing, foot[1] - lift)
        _line(canvas, hip, k, "M", 2)
        _line(canvas, k, f, "X", 2)
        _disc(canvas, k[0], k[1], 1.5, "d")
        paint(canvas, ["dXd"], f[0] - 1, f[1])
    # The crown of pylons.
    for x, h in ((CX - 8, 6), (CX - 1, 8), (CX + 6, 6)):
        _rect(canvas, x, top - h + 2, 2, h, "X")
        _rect(canvas, x + 1, top - h + 2, 1, h, "M")
        paint(canvas, ["UU" if not charged else "uu"], x, top - h + 1)
    # The sphere, its equator ring and the core window.
    paint(canvas, shaded_ellipse(26, 24, "RroO"), CX - 13, top + 1)
    _rect(canvas, CX - 13, top + 16, 26, 2, "X")
    _rect(canvas, CX - 13, top + 17, 26, 1, "M")
    for x in range(CX - 11, CX + 12, 4):
        paint(canvas, ["d"], x, top + 16)
    glow = 4.6 if (charged or overload) else 3.6
    _disc(canvas, center[0] + 1, center[1] - 2, glow + 1.2, "d")
    _disc(canvas, center[0] + 1, center[1] - 2, glow, "U")
    _disc(canvas, center[0] + 1, center[1] - 2, glow - 1.8, "u")
    paint(canvas, ["w"], center[0], center[1] - 3)
    # A ring of eyes above the core.
    for dx, dy in ((-7, -6), (-3, -9), (5, -9), (9, -6)):
        paint(canvas, ["e" if overload else "E"], center[0] + dx, center[1] + dy)
    if overload:  # glowing cracks through the shell
        for x, y in ((-10, -4), (-9, -3), (-9, -2), (-8, -1), (8, 2), (9, 3), (10, 4), (-6, 6)):
            paint(canvas, ["E"], center[0] + x, center[1] + y)
    _gauge(canvas, "grid_core", step)


_BUILD = {"linesman": _linesman, "transformer": _transformer, "grid_core": _grid_core}


@cache
def body(kind: str, step: int | None = None, charged: bool = False, overload: bool = False):
    """A chassis without its protocol arms, on a canvas every pose of it shares."""
    canvas = blank(*SIZE)
    _BUILD["linesman" if kind == "regulator" else kind](canvas, step, charged, overload)
    return render(rows_of(canvas), legend(kind))


@cache
def _recolored(image: pygame.Surface, kind: str) -> pygame.Surface:
    """A protocol arm in this chassis' shell colors (the arms are drawn in hostile orange)."""
    if SHELLS[kind] == _HOSTILE:
        return image
    swapped = image.copy()
    pixels = pygame.PixelArray(swapped)
    for source, target in zip(_HOSTILE, SHELLS[kind], strict=True):
        pixels.replace(rgb(source), rgb(target))
    pixels.close()
    return swapped


@cache
def _posed(
    protocol: str, kind: str, step: int | None, lit: bool, charged: bool, overload: bool
) -> pygame.Surface:
    image = body(kind, step, charged, overload)
    canvas = pygame.Surface(image.get_size(), pygame.SRCALPHA)
    dx, dy = SHOULDER["linesman" if kind == "regulator" else kind]
    sx, sy = CX + 1 + dx, dy + 1 + _bob(step)
    front = []  # drawn over the body
    if protocol == "clamp":
        arm = _recolored(actors.clamp_arm(), kind)
        front.append((arm, (sx - 3, sy - arm.get_height() // 2)))
    elif protocol == "insulate":
        plate = _recolored(actors.insulate_plate(), kind)
        pw, ph = plate.get_size()
        front.append((plate, (sx - 2, sy - ph // 2 + 2)))
        canvas.blit(plate, (2 * CX + 2 - sx - pw + 2, sy - ph // 2 + 2))
    elif protocol == "oscillate":
        right = _recolored(actors.fin(lit), kind)
        fw, fh = right.get_size()
        front.append((right, (sx - 1, sy - fh // 2)))
        canvas.blit(flipped(right), (2 * CX + 2 - sx - fw + 1, sy - fh // 2))
    else:
        raise KeyError(protocol)
    canvas.blit(image, (0, 0))
    for part, pos in front:
        canvas.blit(part, pos)
    return canvas


def regulator(
    protocol: str,
    facing_left: bool,
    needle: float | None = None,
    lit: bool = False,
    kind: str = "linesman",
    overload: bool = False,
    step: int | None = None,
    charged: bool = False,
) -> pygame.Surface:
    """The chassis in its protocol pose, walking at `step` (None stands). `needle` (radians,
    screen space) points the gauge at the Surge. `lit` flashes the Oscillate fins before a
    volley, `charged` lights the chassis before its signature attack."""
    image = _posed(protocol, kind, step, lit, charged, overload)
    if needle is not None:
        image = image.copy()
        angle = math.pi - needle if facing_left else needle
        (gx, gy), r = GAUGE["linesman" if kind == "regulator" else kind]
        cx, cy = gx + 1, gy + 1 + _bob(step)
        tip = (round(cx + math.cos(angle) * (r - 1)), round(cy + math.sin(angle) * (r - 1)))
        pygame.draw.line(image, rgb("px.outline"), (cx, cy), tip, 1)
        image.set_at((cx, cy), rgb("hostile.danger"))
    return flipped(image) if facing_left else image
