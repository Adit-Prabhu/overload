"""The Regulator's three chassis at boss scale (boss rework, docs/BOSS_DESIGN.md section 2:
a distinct silhouette, menacing proportions, dark armor with glowing accents, about three
times the Surge's height). Adit, Nov 18: "they don't look intimidating".

- Linesman (sector 1): a gaunt, hunched giant on a utility pole spine. Its crossarm of
  insulators rides above a low hood with a slit of three red eyes. Long arms end in
  lineman's hooks, and its long legs carry climbing gaffs.
- Transformer (sector 2): a bull of a machine. A wide brass tank on four heavy legs, a low
  head with bushing horns and a grille mouth that glows, and radiator fins down its back
  like a mane.
- Grid Core (sector 3): a reactor sphere in armored plates with a ring of red eyes and a
  crown of pylons, carried high on four arching spider legs. Overloaded, its plates crack.
  In phase 3 they open on the burning core.

Every chassis has a wind-up pose before its kit attacks (`charged`), a vent pose with its
core exposed and steaming (`vent`), and walks with its legs. What keeps it the same rival:
the protocol pose (Clamp pincers forward, Insulate plates at both sides, Oscillate fins),
recolored to the shell, and the gauge needle that always points at the Surge.

Facing right, light from the top left. Built as character grids, rendered once per pose.
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
SIZE = (100, 84)
HEAD = 4  # headroom above the tallest part on rising steps
CX = 50
# Per chassis, in the standing pose (a walking body rides a pixel higher on passing steps):
# the gauge (center, radius), the right shoulder where the protocol arms mount (mirrored for
# the left), and the canvas row of the body's center, which sits on the sim position.
GAUGE = {
    "linesman": ((CX, 46), 4),
    "transformer": ((CX - 12, 47), 4),
    "grid_core": ((CX, 50), 4),
}
SHOULDER = {"linesman": (21, 32), "transformer": (20, 44), "grid_core": (20, 42)}
CENTER = {"linesman": 38, "transformer": 43, "grid_core": 34}
# How far below the sim position the feet (the image's bottom edge) are. The rendered image
# has a one pixel outline pad, so its bottom is SIZE[1] + 1 rows below the canvas top.
FEET = {kind: SIZE[1] + 1 - row for kind, row in CENTER.items()}
_HOSTILE = ("px.hostile.0", "px.hostile.1", "px.hostile.2", "px.hostile.3")


def legend(kind: str) -> dict[str, str]:
    """The shared robot legend with R r o O (dark to light) mapped to this chassis' shell."""
    dark, shade, base, light = SHELLS[kind]
    return {**LEGEND, "R": dark, "r": shade, "o": base, "O": light, "e": light}


# Drawing on a character canvas ------------------------------------------------------------


def _rect(canvas, x: int, y: int, w: int, h: int, char: str) -> None:
    paint(canvas, [char * w] * h, x, y)


def _disc(canvas, cx: float, cy: float, radius: float, char: str) -> None:
    r = math.ceil(radius)
    for dy in range(-r, r + 1):
        for dx in range(-r, r + 1):
            if dx * dx + dy * dy <= radius * radius:
                paint(canvas, [char], round(cx) + dx, round(cy) + dy)


def _line(canvas, a, b, char: str, width: int = 1) -> None:
    steps = max(abs(b[0] - a[0]), abs(b[1] - a[1]), 1)
    for i in range(round(steps) + 1):
        x = round(a[0] + (b[0] - a[0]) * i / steps)
        y = round(a[1] + (b[1] - a[1]) * i / steps)
        paint(canvas, [char * width], x - width // 2, y)


def _poly(canvas, points, char: str) -> None:
    """Fill a polygon (scanline, even-odd)."""
    ys = [p[1] for p in points]
    for y in range(math.floor(min(ys)), math.ceil(max(ys)) + 1):
        cross = []
        for (x1, y1), (x2, y2) in zip(points, points[1:] + points[:1], strict=True):
            if (y1 <= y < y2) or (y2 <= y < y1):
                cross.append(x1 + (y - y1) * (x2 - x1) / (y2 - y1))
        cross.sort()
        for left, right in zip(cross[::2], cross[1::2], strict=False):
            for x in range(round(left), round(right) + 1):
                paint(canvas, [char], x, y)


def _limb(canvas, a, b, ramp: str, width: int) -> None:
    """A thick limb from a to b, lit on its upper left edge and shaded on the right.
    `ramp` is dark, mid, light (and an optional highlight)."""
    _line(canvas, a, b, ramp[1], width)
    _line(canvas, (a[0] - width // 2, a[1]), (b[0] - width // 2, b[1]), ramp[2], 1)
    _line(canvas, (a[0] + width // 2, a[1]), (b[0] + width // 2, b[1]), ramp[0], 1)


def _bob(step: int | None) -> int:
    return -1 if rig.rising(step) else 0


def _gauge(canvas, kind: str, step: int | None) -> None:
    (cx, cy), r = GAUGE[kind]
    cy += _bob(step)
    _disc(canvas, cx, cy, r + 1, "d")
    _disc(canvas, cx, cy, r, "X")
    _disc(canvas, cx, cy, r - 1, "W")
    _disc(canvas, cx, cy, r - 2, "w")
    paint(canvas, ["E"], cx + r - 2, cy - 2)  # the red zone of the dial


def _steam(canvas, x: int, y: int, step: int | None) -> None:
    """Vent steam: pale puffs rising off an opening."""
    shift = (step or 0) % 2
    for dx, dy in ((0, 0), (-2, -3), (2, -5), (-1, -8), (1, -11)):
        _disc(canvas, x + dx + shift, y + dy, 1.2, "Q")


def _core(canvas, x: int, y: int, radius: float) -> None:
    """An exposed core: hot amber with a white heart, in a dark socket."""
    _disc(canvas, x, y, radius + 1.2, "d")
    _disc(canvas, x, y, radius, "j")
    _disc(canvas, x, y, max(1.0, radius - 1.6), "J")
    paint(canvas, ["w"], x - 1, y - 1)


# Linesman -----------------------------------------------------------------------------------

_INSULATOR = [".dAd.", "dQCcd", "QCCCc", "dQCcd", "QCCCc", "dQCcd", ".dXd."]
_LINESMAN_LEG = rig.LegStyle(
    upper="dXMMm", lower="dXMm", knee="dXXXd", foot="dXXXXXXd", heel=2, swing=3, lift=2
)


def _linesman(canvas, step, charged: bool, overload: bool, vent: bool) -> None:
    t = HEAD + 1 + _bob(step)  # the top of the crossarm's insulators
    hot = "J" if overload else "E"
    # Legs: long, with a gaff spike on each shin.
    hips = t + 47
    for half, hip in ((0, CX - 10), (1, CX + 5)):
        swing, lift = rig.pose(step, half, _LINESMAN_LEG)
        rig.leg(canvas, hip, hips, SIZE[1] - hips, swing, lift, _LINESMAN_LEG)
        gaff = hips + (SIZE[1] - hips) * 2 // 3 - lift
        paint(canvas, ["Q", "c"], hip + swing + (5 if half else -2), gaff)
    # The pole spine behind everything, from above the crossarm to the hips.
    _rect(canvas, CX - 2, t - 2, 5, hips - t + 2, "m")
    _rect(canvas, CX - 2, t - 2, 1, hips - t + 2, "M")
    _rect(canvas, CX + 2, t - 2, 1, hips - t + 2, "d")
    # The torso: a tapered cage of shell plates over the spine, ribs, a hazard belt.
    top, bottom = t + 26, t + 46
    _poly(canvas, [(CX - 14, top), (CX + 14, top), (CX + 9, bottom), (CX - 9, bottom)], "o")
    _line(canvas, (CX - 14, top), (CX - 9, bottom), "O")
    _line(canvas, (CX + 14, top), (CX + 9, bottom), "R")
    for y in range(top + 3, bottom - 3, 3):
        _line(canvas, (CX - 12 + (y - top) // 4, y), (CX + 12 - (y - top) // 4, y), "r")
    for y in (bottom - 2, bottom - 1):
        for x in range(CX - 9, CX + 10):
            paint(canvas, ["H" if (x + y) % 4 < 2 else "h"], x, y)
    if vent:  # the chest plates part on the spine's core
        _poly(
            canvas,
            [(CX - 6, top + 3), (CX + 6, top + 3), (CX + 4, top + 15), (CX - 4, top + 15)],
            "d",
        )
        _core(canvas, CX, top + 9, 3.4)
        _steam(canvas, CX - 7, top + 1, step)
        _steam(canvas, CX + 7, top + 1, step)
    # Arms: from the crossarm's ends down past the knees, swinging against the legs, raised
    # for the wind-up. Each ends in a lineman's hook.
    for half, side in ((0, -1), (1, 1)):
        shoulder = (CX + side * 20, t + 13)
        swing, _lift = rig.pose(step, 1 - half, _LINESMAN_LEG)
        if charged:
            elbow, hand = (CX + side * 28, t + 8), (CX + side * 25, t + 4)
        else:
            elbow, hand = (CX + side * 25, t + 30), (CX + side * 23 + swing, t + 50)
        _limb(canvas, shoulder, elbow, "RrO", 4)
        _limb(canvas, elbow, hand, "RrO", 3)
        _disc(canvas, elbow[0], elbow[1], 2, "X")
        hx, hy = hand
        up = -1 if charged else 1
        hook = [
            (hx, hy),
            (hx, hy + 3 * up),
            (hx - side, hy + 5 * up),
            (hx - side * 3, hy + 5 * up),
            (hx - side * 4, hy + 3 * up),
        ]
        for a, b in zip(hook, hook[1:], strict=False):
            _line(canvas, a, b, "X", 2)
        paint(canvas, ["Q"], hook[-1][0], hook[-1][1])
    # The crossarm and its insulators, the line sagging between them.
    _rect(canvas, CX - 24, t + 9, 49, 3, "X")
    _rect(canvas, CX - 24, t + 9, 49, 1, "M")
    _rect(canvas, CX - 24, t + 11, 49, 1, "m")
    for x in (CX - 23, CX - 13, CX + 9, CX + 19):
        insulator = list(_INSULATOR)
        if charged:
            insulator[0] = ".EwE."
        paint(canvas, insulator, x, t + 2)
    for a, b in ((CX - 21, CX - 11), (CX + 11, CX + 21)):
        for x in range(a + 1, b):
            sag = round(3 * math.sin(math.pi * (x - a) / (b - a)))
            paint(canvas, ["d"], x, t + 13 + sag)
    # The hood, hung low and forward under the crossarm, its face a void with three slits.
    paint(canvas, shaded_ellipse(22, 17, "dRRr"), CX - 10, t + 11)
    _poly(canvas, [(CX - 4, t + 17), (CX + 11, t + 16), (CX + 11, t + 27), (CX - 2, t + 28)], "v")
    for x in (CX, CX + 4, CX + 8):  # three slit eyes, each with a hot core
        paint(canvas, [hot * 3, "." + hot + "."], x - 1, t + 21)
    paint(canvas, ["w"], CX + 8, t + 21)
    if overload:  # cracks of light in the shell
        for x, y in (
            (CX - 10, t + 30),
            (CX - 9, t + 31),
            (CX - 9, t + 32),
            (CX + 8, t + 36),
            (CX + 9, t + 37),
            (CX - 4, t + 15),
            (CX - 3, t + 16),
        ):
            paint(canvas, ["E"], x, y)
    _gauge(canvas, "linesman", step)


# Transformer --------------------------------------------------------------------------------

_BUSHING = [".dOd.", "dQCcd", "QCCCc", "dQCcd", "QCCCc", "dMMMd"]
_TRANSFORMER_LEG = rig.LegStyle(
    upper="dXMMMMm", lower="dXMMMm", knee="dXXXXXd", foot="dXXXXXXXXd", heel=2, swing=2, lift=2
)


def _transformer(canvas, step, charged: bool, overload: bool, vent: bool) -> None:
    t = HEAD + 26 + _bob(step)  # the top of the tank
    low = 4 if charged else 0  # the head drops to charge
    hot = "J" if overload else "E"
    hips = t + 26
    for i, hip in enumerate((CX - 28, CX - 18, CX + 2, CX + 11)):
        swing, lift = rig.pose(step, i % 2, _TRANSFORMER_LEG)
        rig.leg(canvas, hip, hips, SIZE[1] - hips, swing, lift, _TRANSFORMER_LEG)
    # The tank: a deep drum lit from above, rounded at the ends.
    width, height = 46, 28
    left = CX - 31
    for r in range(height):
        tone = "O" if r < 3 else "o" if r < 13 else "r" if r < 22 else "R"
        inset = 3 if r in (0, height - 1) else 1 if r in (1, height - 2) else 0
        paint(canvas, [tone * (width - 2 * inset)], left + inset, t + r)
        if 3 <= r < 22 and not inset:
            paint(canvas, ["O"], left, t + r)
    for r in (8, 15):  # coil bands
        _rect(canvas, left + 3, t + r, 26, 1, "R")
        _rect(canvas, left + 3, t + r + 1, 26, 1, "O")
    for x in range(left + 2, left + width + 6):  # a hazard skirt
        paint(canvas, ["H" if (x // 2) % 2 else "h"], x, t + height)
    # The shoulder hump: armor rising over the front legs, a bull's mass.
    hump = [
        (CX - 6, t + 2),
        (CX - 1, t - 9),
        (CX + 9, t - 12),
        (CX + 17, t - 6),
        (CX + 19, t + 12),
        (CX + 15, t + height),
        (CX - 6, t + height),
    ]
    _poly(canvas, hump, "o")
    _line(canvas, (CX - 1, t - 9), (CX + 9, t - 12), "O", 2)
    _line(canvas, (CX - 6, t + 2), (CX - 1, t - 9), "O", 1)
    _line(canvas, (CX + 17, t - 6), (CX + 19, t + 12), "R", 1)
    _poly(
        canvas,
        [(CX - 6, t + 15), (CX + 19, t + 12), (CX + 15, t + height), (CX - 6, t + height)],
        "r",
    )
    # The radiator mane: fins standing up along its back, tallest at the hump.
    for i, x in enumerate(range(left + 3, CX - 2, 4)):
        h = 4 + i
        _rect(canvas, x, t - h, 2, h, "X")
        _rect(canvas, x, t - h, 1, h, "M")
        if vent and i % 2:
            _steam(canvas, x, t - h - 2, step)
    # The head: low and jutting forward under the hump, bushing horns sweeping forward, a
    # heavy brow over small eyes, a grille mouth that glows.
    hx, hy = CX + 14, t + 4 + low
    _poly(
        canvas,
        [
            (hx - 2, hy),
            (hx + 14, hy + 2),
            (hx + 22, hy + 10),
            (hx + 21, hy + 20),
            (hx + 6, hy + 23),
            (hx - 4, hy + 16),
        ],
        "o",
    )
    _line(canvas, (hx - 2, hy), (hx + 14, hy + 2), "O", 2)
    _line(canvas, (hx + 22, hy + 10), (hx + 21, hy + 20), "R", 2)
    _line(canvas, (hx + 6, hy + 23), (hx + 21, hy + 20), "R", 1)
    for x, rise in ((hx + 2, 7), (hx + 11, 5)):  # bushing horns
        bushing = list(_BUSHING)
        if charged:
            bushing[0] = ".EwE."
        paint(canvas, bushing, x, hy - rise)
        _line(canvas, (x + 4, hy - rise + 1), (x + 7, hy - rise - 2), "Q", 1)  # horn tip
    _rect(canvas, hx + 6, hy + 6, 17, 2, "R")  # the brow
    _poly(canvas, [(hx + 7, hy + 8), (hx + 21, hy + 9), (hx + 21, hy + 12), (hx + 8, hy + 12)], "v")
    paint(canvas, [hot + hot + "..." + hot + hot, hot + "w..." + hot + "w"], hx + 12, hy + 9)
    mouth = "J" if (charged or overload) else "j"
    _rect(canvas, hx + 8, hy + 15, 13, 5, "d")
    for x in range(hx + 9, hx + 20, 2):
        _rect(canvas, x, hy + 16, 1, 3, mouth)
    if vent:  # the side hatch blows open on its coils
        _rect(canvas, left + 8, t + 9, 14, 11, "d")
        _core(canvas, left + 15, t + 14, 3.4)
    if overload:
        for x, y in (
            (left + 10, t + 5),
            (left + 11, t + 6),
            (left + 11, t + 7),
            (CX + 8, t + 2),
            (CX + 9, t + 3),
            (left + 26, t + 22),
        ):
            paint(canvas, ["E"], x, y)
    _gauge(canvas, "transformer", step)


# Grid Core ----------------------------------------------------------------------------------


def _grid_core(canvas, step, charged: bool, overload: bool, vent: bool, opened: bool) -> None:
    t = HEAD + 12 + _bob(step)  # the top of the sphere
    center = (CX, t + 18)
    hot = "J" if overload else "E"
    # Four spider legs arching high above the body, lifting two at a time.
    legs = (
        ((CX - 8, t + 30), (CX - 20, t + 12), (CX - 24, SIZE[1] - 1)),
        ((CX + 8, t + 30), (CX + 20, t + 12), (CX + 24, SIZE[1] - 1)),
        ((CX - 15, t + 20), (CX - 36, t - 3), (CX - 44, SIZE[1] - 1)),
        ((CX + 15, t + 20), (CX + 36, t - 3), (CX + 44, SIZE[1] - 1)),
    )
    for i, (hip, knee, foot) in enumerate(legs):
        lift = swing = 0
        if step is not None:
            angle = 2 * math.pi * (step / rig.STEPS + ((i + i // 2) % 2) / 2)
            swing = round(3 * math.sin(angle))
            lift = round(3 * max(0.0, math.cos(angle)))
        k = (knee[0] + swing // 2, knee[1] - lift - (2 if charged else 0))
        f = (foot[0] + swing, foot[1] - lift)
        ramp = "dmM" if i < 2 else "dXQ"  # the inner legs sit further back, darker
        _limb(canvas, hip, k, ramp, 3)
        _limb(canvas, k, f, ramp, 2)
        _disc(canvas, k[0], k[1], 2, "d")
        paint(canvas, ["E"], k[0], k[1] - 1)  # a red joint light on each knee
        _line(canvas, (f[0], f[1] - 2), f, "X", 2)
    # The crown of pylons.
    for x, h in ((CX - 10, 7), (CX - 1, 11), (CX + 8, 7)):
        _rect(canvas, x, t - h + 3, 3, h, "X")
        _rect(canvas, x, t - h + 3, 1, h, "M")
        paint(canvas, ["UUU" if not charged else "uuu"], x, t - h + 2)
    # The sphere in armored plates.
    paint(canvas, shaded_ellipse(36, 36, "RroO"), CX - 18, t)
    for dy in (-10, 10):  # plate seams
        _line(canvas, (CX - 15, center[1] + dy), (CX + 15, center[1] + dy), "R")
    _line(canvas, (CX - 17, center[1]), (CX + 17, center[1]), "R")
    _line(canvas, (CX - 7, t + 2), (CX - 7, t + 34), "R")
    _line(canvas, (CX + 8, t + 2), (CX + 8, t + 34), "R")
    # The ring of eyes around its upper band.
    for dx, dy in ((-13, -7), (-8, -11), (-1, -13), (6, -12), (11, -9), (15, -4)):
        paint(canvas, [hot + hot], center[0] + dx, center[1] + dy)
    # The reactor window, or the open core in phase 3.
    if opened:
        for side in (-1, 1):  # its plates stand open like petals
            _poly(
                canvas,
                [
                    (CX + side * 10, t + 3),
                    (CX + side * 24, t - 3),
                    (CX + side * 26, t + 18),
                    (CX + side * 13, t + 24),
                ],
                "o",
            )
            _line(canvas, (CX + side * 24, t - 3), (CX + side * 26, t + 18), "O")
            _line(canvas, (CX + side * 13, t + 24), (CX + side * 26, t + 18), "R")
        _core(canvas, center[0], center[1] + 1, 9.0)
    else:
        _core(canvas, center[0] + 1, center[1] + 2, 5.2 if (charged or overload or vent) else 4.2)
    if vent:
        _steam(canvas, CX - 12, t + 4, step)
        _steam(canvas, CX + 12, t + 4, step)
    if overload and not opened:
        for x, y in (
            (-14, -2),
            (-13, -1),
            (-13, 0),
            (-12, 1),
            (12, 6),
            (13, 7),
            (14, 8),
            (-8, 12),
            (-7, 13),
        ):
            paint(canvas, ["E"], center[0] + x, center[1] + y)
    _gauge(canvas, "grid_core", step)


@cache
def body(
    kind: str,
    step: int | None = None,
    charged: bool = False,
    overload: bool = False,
    vent: bool = False,
    opened: bool = False,
):
    """A chassis without its protocol arms, on a canvas every pose of it shares."""
    canvas = blank(*SIZE)
    kind = "linesman" if kind == "regulator" else kind
    if kind == "grid_core":
        _grid_core(canvas, step, charged, overload, vent, opened)
    elif kind == "transformer":
        _transformer(canvas, step, charged, overload, vent)
    else:
        _linesman(canvas, step, charged, overload, vent)
    return render(rows_of(canvas), legend(kind))


_ARMS = {
    "clamp": actors.clamp_arm,
    "plate": actors.insulate_plate,
    "fin": lambda: actors.fin(False),
    "fin_lit": lambda: actors.fin(True),
}


@cache
def _recolored(part: str, kind: str) -> pygame.Surface:
    """A protocol arm in this chassis' shell colors (the arms are drawn in hostile orange)."""
    image = _ARMS[part]()
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
    protocol: str,
    kind: str,
    step: int | None,
    lit: bool,
    charged: bool,
    overload: bool,
    vent: bool,
    opened: bool,
) -> pygame.Surface:
    image = body(kind, step, charged, overload, vent, opened)
    canvas = pygame.Surface(image.get_size(), pygame.SRCALPHA)
    dx, dy = SHOULDER["linesman" if kind == "regulator" else kind]
    sx, sy = CX + 1 + dx, dy + 1 + _bob(step)
    front = []  # drawn over the body
    if protocol == "clamp":
        arm = _recolored("clamp", kind)
        front.append((arm, (sx - 3, sy - arm.get_height() // 2)))
    elif protocol == "insulate":
        plate = _recolored("plate", kind)
        pw, ph = plate.get_size()
        front.append((plate, (sx - 2, sy - ph // 2 + 2)))
        canvas.blit(plate, (2 * CX + 2 - sx - pw + 2, sy - ph // 2 + 2))
    elif protocol == "oscillate":
        right = _recolored("fin_lit" if lit else "fin", kind)
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
    vent: bool = False,
    opened: bool = False,
) -> pygame.Surface:
    """The chassis in its protocol pose, walking at `step` (None stands). `needle` (radians,
    screen space) points the gauge at the Surge. `lit` flashes the Oscillate fins before a
    volley, `charged` is the wind-up before a kit attack, `vent` its punish window with the
    core exposed, `opened` the Grid Core's open plates in phase 3."""
    image = _posed(protocol, kind, step, lit, charged, overload, vent, opened)
    if needle is not None:
        image = image.copy()
        angle = math.pi - needle if facing_left else needle
        (gx, gy), r = GAUGE["linesman" if kind == "regulator" else kind]
        cx, cy = gx + 1, gy + 1 + _bob(step)
        tip = (round(cx + math.cos(angle) * (r - 1)), round(cy + math.sin(angle) * (r - 1)))
        pygame.draw.line(image, rgb("px.outline"), (cx, cy), tip, 1)
        image.set_at((cx, cy), rgb("hostile.danger"))
    return flipped(image) if facing_left else image
