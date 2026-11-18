"""Original substation chassis, drawn on the same pixel grid as the maintenance robots.

Each phase changes the chassis silhouette. The protocol modules, aim gauge, wind-up
and vent opening are separate visual cues. See docs/BOSS_DESIGN.md.
"""

from __future__ import annotations

import math
from functools import cache, lru_cache

import pygame

from overload.art.palette import rgb
from overload.art.pixel import actors, rig
from overload.art.pixel.grid import flipped, render
from overload.art.pixel.rig import blank, paint, rows_of
from overload.art.pixel.robots import LEGEND

KINDS = ("linesman", "transformer", "grid_core")
SHELLS = {
    "linesman": ("px.hostile.0", "px.hostile.1", "px.hostile.2", "px.hostile.3"),
    "transformer": ("px.coil.0", "px.coil.1", "px.coil.2", "px.coil.3"),
    "grid_core": ("px.core.0", "px.core.1", "px.core.2", "px.core.3"),
}
SHELLS["regulator"] = SHELLS["linesman"]
SIZE = (100, 84)
CX = 50
# Standing-pose coordinates. Walking lifts the armor and gauge together.
GAUGE = {
    "linesman": ((54, 49), 3),
    "transformer": ((51, 49), 3),
    "grid_core": ((50, 52), 3),
}
MODULES = {
    "linesman": ((27, 38), (70, 40)),
    "transformer": ((24, 44), (80, 55)),
    "grid_core": ((32, 47), (68, 47)),
}
CENTER = {"linesman": 40, "transformer": 43, "grid_core": 37}
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


# Chassis construction ----------------------------------------------------------------------


def _plate(canvas, points, face: str, edge: str, shadow: str) -> None:
    """Beveled armor. List the top-left and top-right corners first."""
    _poly(canvas, points, face)
    _line(canvas, points[0], points[1], edge)
    for a, b in zip(points[1:], points[2:], strict=False):
        _line(canvas, a, b, shadow)


def _bolts(canvas, points, color: str = "X") -> None:
    for x, y in points:
        paint(canvas, [color], x, y)


def _link(canvas, hip, knee, foot, armor: str, width: int) -> None:
    _limb(canvas, hip, knee, armor, width)
    _disc(canvas, *knee, width / 2, "d")
    _disc(canvas, knee[0] - 1, knee[1] - 1, width / 4, "X")
    _limb(canvas, knee, foot, "dmM", max(2, width - 2))


def _insulator(canvas, x: int, y: int, hot: bool) -> None:
    paint(canvas, [".cQc.", "cQQCc", ".cCc.", "cQCCc", ".cCc.", "cQCCc", ".mXm."], x - 2, y)
    if hot:
        paint(canvas, [".EwE."], x - 2, y)


def _linesman(canvas, step, charged: bool, phase: int, vent: bool) -> None:
    """A switchyard gantry with climbing gaffs and a suspended welding mask."""
    y = _bob(step)
    spread = (0, 5, 10)[phase - 1]
    tilt = (0, 4, 7)[phase - 1]
    mask_y = 23 + tilt + y
    for half, side in enumerate((-1, 1)):
        swing, lift = rig.pose(step, half, _GANTRY_GAIT)
        hip = (50 + side * 7, 50 + y)
        knee = (50 + side * (11 + phase) + swing // 2, 64 - lift + y)
        foot = (50 + side * 12 + swing, 80 - lift - (2 if half == 0 else 0))
        _link(canvas, hip, knee, foot, "dmX", 7)
        _plate(
            canvas,
            [
                (foot[0] - 4, foot[1] - 3),
                (foot[0] + 3, foot[1] - 3),
                (foot[0] + 7, foot[1] + 1),
                (foot[0] - 6, foot[1] + 1),
            ],
            "M",
            "X",
            "d",
        )
        _line(canvas, (knee[0], knee[1] + 3), (knee[0] + side * 5, knee[1] + 1), "Q")
    _limb(canvas, (45, 9 + y), (48, 53 + y), "dmM", 7)
    # The crossarm swings up in phase two. The end insulators break free in phase three.
    for half, side in enumerate((-1, 1)):
        shoulder = (50 + side * 11, 24 + y)
        tip = (50 + side * (20 + spread), (21, 15, 9)[phase - 1] + y - (3 if charged else 0))
        _limb(canvas, shoulder, tip, "dmX", 6)
        _insulator(canvas, tip[0], tip[1] - 4, charged or phase == 3)
        port = (shoulder[0] + side * 5, shoulder[1] - 7)
        _insulator(canvas, *port, charged)
        swing, lift = rig.pose(step, 1 - half, _GANTRY_GAIT)
        elbow = (50 + side * (22 + spread // 2), 37 + y - (10 if charged else 0))
        claw = (elbow[0] + swing - side * 2, (44 if charged else 61) - lift + y - tilt // 2)
        _link(canvas, shoulder, elbow, claw, "RrO", 7)
        _poly(
            canvas,
            [
                (claw[0] - 3, claw[1] - 5),
                (claw[0] + 3, claw[1] - 4),
                (claw[0] + side * 2, claw[1] + 7),
                (claw[0] - side * 7, claw[1] + 10),
                (claw[0] - side * 4, claw[1] + 4),
            ],
            "M",
        )
        _line(canvas, claw, (claw[0] - side * 7, claw[1] + 10), "X", 2)
        if phase == 3:
            _line(canvas, (tip[0] - side * 5, tip[1]), (tip[0] - side * 3, tip[1] + 10), "E")
            _line(canvas, (tip[0] - side * 3, tip[1] + 10), (elbow[0] + side * 3, elbow[1]), "m", 2)

    chest = 33 + y
    _plate(
        canvas,
        [
            (33, chest),
            (64, chest - 2),
            (68, chest + 7),
            (59, chest + 22),
            (42, chest + 23),
            (32, chest + 11),
        ],
        "r",
        "O",
        "R",
    )
    for dy, left, right in ((4, 34, 65), (9, 36, 64), (14, 39, 61)):
        _line(canvas, (left, chest + dy), (right, chest + dy - 1), "R", 2)
        _line(canvas, (left + 2, chest + dy + 1), (right - 2, chest + dy), "o")
    _bolts(canvas, [(35, chest + 5), (62, chest + 5), (41, chest + 15), (58, chest + 15)], "O")
    if phase == 3:
        _line(canvas, (36, chest + 7), (45, chest + 13), "d", 3)
        _line(canvas, (45, chest + 13), (43, chest + 19), "E")
        _line(canvas, (62, chest + 3), (55, chest + 8), "E")
        _poly(canvas, [(39, chest + 20), (45, chest + 20), (44, chest + 32)], "r")
    _plate(
        canvas,
        [
            (39, mask_y),
            (56, mask_y - 4),
            (63, mask_y + 1),
            (62, mask_y + 9),
            (54, mask_y + 16),
            (43, mask_y + 11),
            (38, mask_y + 5),
        ],
        "m",
        "X",
        "d",
    )
    _poly(
        canvas,
        [(43, mask_y + 3), (60, mask_y + 1), (58, mask_y + 8), (52, mask_y + 11), (43, mask_y + 8)],
        "v",
    )
    _line(canvas, (45, mask_y + 6), (57, mask_y + 4), "E" if phase == 1 else "J", 2)
    if phase >= 2:
        _line(canvas, (54, mask_y + 8), (59, mask_y + 6), "E")
        _poly(
            canvas,
            [(46, mask_y + 10), (56, mask_y + 11), (54, mask_y + 17), (49, mask_y + 16)],
            "d",
        )
    if phase == 3:
        _line(canvas, (48, mask_y + 12), (53, mask_y + 15), "E", 2)
        _bolts(canvas, [(49, mask_y + 12), (52, mask_y + 14)], "Q")
    if vent:
        _core(canvas, 44, 43 + y, 4.0)
        _steam(canvas, 36, 40 + y, step)
    _gauge(canvas, "linesman", step)


_GANTRY_GAIT = rig.LegStyle("", "", "", "", heel=0, swing=5, lift=4)
_BULL_GAIT = rig.LegStyle("", "", "", "", heel=0, swing=4, lift=4)


def _transformer(canvas, step, charged: bool, phase: int, vent: bool) -> None:
    """An oil-cooled transformer on a low four-legged carrier."""
    y = _bob(step)
    drop = (0, 3, 7)[phase - 1] + (4 if charged else 0)
    for i, (x, hip_y, foot_y) in enumerate(
        ((26, 47, 70), (49, 44, 67), (37, 54, 79), (61, 55, 81))
    ):
        swing, lift = rig.pose(step, i % 2 ^ i // 2, _BULL_GAIT)
        knee = (x - 5 + swing // 2, hip_y + 10 - lift + y)
        foot = (x + swing, foot_y - lift)
        _link(canvas, (x, hip_y + y), knee, foot, "dmM" if i < 2 else "RrO", 9)
        _plate(
            canvas,
            [
                (foot[0] - 4, foot[1] - 4),
                (foot[0] + 3, foot[1] - 4),
                (foot[0] + 7, foot[1]),
                (foot[0] - 6, foot[1]),
            ],
            "m",
            "X",
            "d",
        )
    # Stacked fins and raised pressure stacks broaden its silhouette as it fails.
    for i, x in enumerate(range(28, 57, 4)):
        top = 32 - (i >= 3) * 4 - (phase - 1) * (2 + i // 3) + y
        _plate(
            canvas,
            [
                (x - 5, top),
                (x - 2, top - 2),
                (x + 4, top + 12),
                (x + 2, top + 16),
                (x - 1, top + 10),
            ],
            "m",
            "X",
            "d",
        )
        if phase >= 2:
            _line(canvas, (x - 3, top + 1), (x, top + 7), "E" if phase == 3 else "H")
    _plate(
        canvas,
        [
            (31, 33 + y),
            (54, 29 + y),
            (66, 35 + y),
            (67, 52 + y),
            (58, 62 + y),
            (33, 59 + y),
            (25, 50 + y),
            (25, 40 + y),
        ],
        "r",
        "O",
        "R",
    )
    _poly(canvas, [(31, 34 + y), (54, 30 + y), (62, 35 + y), (42, 41 + y), (27, 40 + y)], "o")
    _poly(canvas, [(43, 44 + y), (64, 39 + y), (64, 53 + y), (56, 59 + y), (41, 57 + y)], "R")
    _line(canvas, (30, 40 + y), (30, 53 + y), "O", 2)
    _line(canvas, (34, 41 + y), (57, 38 + y), "R")
    _line(canvas, (34, 55 + y), (58, 56 + y), "o", 2)
    _bolts(canvas, [(32, 43 + y), (33, 52 + y), (41, 35 + y), (57, 53 + y)], "O")

    if phase == 2:
        _plate(canvas, [(29, 39 + y), (45, 42 + y), (44, 53 + y), (29, 51 + y)], "R", "O", "d")
        for x in range(32, 44, 3):
            _line(canvas, (x, 44 + y), (x, 49 + y), "h", 1)
    if phase == 3:
        # The outer plate has sprung off its mount, leaving a torn-open coil stack.
        _poly(canvas, [(23, 37 + y), (29, 40 + y), (27, 56 + y), (19, 60 + y)], "r")
        _line(canvas, (23, 37 + y), (19, 60 + y), "O")
        _poly(canvas, [(31, 43 + y), (46, 43 + y), (45, 53 + y), (32, 52 + y)], "d")
        for x in range(34, 45, 3):
            _line(canvas, (x, 44 + y), (x - 1, 50 + y), "E", 2)
    if vent:
        _poly(canvas, [(29, 42 + y), (45, 41 + y), (44, 54 + y), (29, 54 + y)], "d")
        _core(canvas, 36, 47 + y, 4.5)
        _steam(canvas, 31, 42 + y, step)

    head = 37 + drop + y
    for x, dy in ((58, -5), (67, -2)):
        _insulator(canvas, x, head + dy - (phase - 1), charged or phase == 3)
        _line(canvas, (x + 1, head + dy + 3), (x + 8, head + dy - phase * 2), "Q", 2)
    _plate(
        canvas,
        [
            (54, head),
            (65, head - 3),
            (75, head + 1),
            (80, head + 10),
            (73, head + 19),
            (60, head + 17),
            (53, head + 8),
        ],
        "r",
        "O",
        "R",
    )
    _poly(
        canvas,
        [(58, head + 4), (72, head + 2), (77, head + 6), (72, head + 10), (60, head + 9)],
        "v",
    )
    _line(canvas, (62, head + 7), (73, head + 5), "J" if phase >= 2 else "E", 2)
    _line(canvas, (67, head + 13), (77, head + 10), "d", 3)
    _bolts(
        canvas,
        [(68, head + 13), (71, head + 12), (74, head + 11)],
        "J" if charged or phase == 3 else "h",
    )
    _gauge(canvas, "transformer", step)


def _grid_core(canvas, step, charged: bool, phase: int, vent: bool) -> None:
    """A reactor cage on spring-loaded switchgear legs."""
    y = _bob(step)
    spread = (0, 5, 8)[phase - 1]
    for i, (side, rear) in enumerate(((-1, True), (1, True), (-1, False), (1, False))):
        swing, lift = rig.pose(step, i % 2 ^ i // 2, _BULL_GAIT)
        hip = (50 + side * 11, (30 if rear else 42) + y)
        knee_x = 50 + side * (25 + (0 if rear else 7) + spread // 3) + swing // 2
        knee_y = (18 if rear else 39) - spread // 2 - lift - (4 if charged else 0) + y
        foot = (50 + side * (31 if rear else 40) + swing, (57 if rear else 80) - lift)
        _link(canvas, hip, (knee_x, knee_y), foot, "dmX", 6 if rear else 9)
        _line(canvas, (knee_x, knee_y), (foot[0] - side * 3, foot[1] - 7), "d", 2)
        _line(canvas, foot, (foot[0] - side * 5, foot[1] + 1), "X", 3)
        paint(canvas, ["E"], knee_x, knee_y - 1)
    for x, top in ((41 - spread, 16), (50, 10), (59 + spread, 14)):
        terminal_y = top - spread // 2 + y
        _limb(canvas, (50 + (x - 50) // 2, 31 + y), (x, terminal_y + 5), "dmX", 5)
        _insulator(canvas, x, terminal_y, charged or phase == 3)
    _plate(
        canvas,
        [
            (36, 23 + y),
            (60, 21 + y),
            (66, 27 + y),
            (68, 44 + y),
            (59, 54 + y),
            (42, 55 + y),
            (34, 46 + y),
            (32, 33 + y),
        ],
        "R",
        "o",
        "d",
    )
    _poly(
        canvas,
        [(40, 27 + y), (60, 25 + y), (64, 38 + y), (60, 48 + y), (41, 48 + y), (36, 37 + y)],
        "v",
    )
    _core(canvas, 50, 38 + y, (4.0, 6.0, 9.0)[phase - 1])
    for side in (-1, 1):
        dx = side * spread
        _plate(
            canvas,
            [
                (49 + dx, 27 + y),
                (50 + side * 12 + dx, 23 + y),
                (50 + side * (13 if phase == 3 else 16) + dx, 31 + y),
                (50 + side * 13 + dx, 43 + y),
                (50 + side * 7 + dx, 47 + y),
                (48 + dx, 36 + y),
            ],
            "r",
            "O",
            "R",
        )
        _line(canvas, (50 + side * 4 + dx, 32 + y), (50 + side * 11 + dx, 29 + y), "E", 2)
        _bolts(canvas, [(50 + side * 10 + dx, 27 + y), (50 + side * 9 + dx, 40 + y)], "O")
        if phase == 3:
            _line(canvas, (50 + side * 7, 35 + y), (50 + side * 15, 39 + y), "E")
    if phase == 1:
        _line(canvas, (46, 38 + y), (55, 37 + y), "j", 2)
    if vent:
        _core(canvas, 50, 39 + y, 6.0 if phase < 3 else 9.0)
        _steam(canvas, 34, 28 + y, step)
        _steam(canvas, 66, 28 + y, step)
    _gauge(canvas, "grid_core", step)


@lru_cache(maxsize=192)
def body(
    kind: str,
    step: int | None = None,
    charged: bool = False,
    phase: int = 1,
    vent: bool = False,
) -> pygame.Surface:
    """A chassis without its protocol modules, on a canvas every pose shares."""
    canvas = blank(*SIZE)
    kind = "linesman" if kind == "regulator" else kind
    draw = {"grid_core": _grid_core, "transformer": _transformer, "linesman": _linesman}[kind]
    draw(canvas, step, charged, phase, vent)
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


@lru_cache(maxsize=192)
def _posed(
    protocol: str,
    kind: str,
    step: int | None,
    lit: bool,
    charged: bool,
    phase: int,
    vent: bool,
) -> pygame.Surface:
    image = body(kind, step, charged, phase, vent).copy()
    left, right = MODULES[kind]
    if protocol == "clamp":
        parts = [(_recolored("clamp", kind), (right[0] + 4, right[1] + 4))]
    elif protocol == "insulate":
        plate = _recolored("plate", kind)
        parts = [(flipped(plate), left), (plate, right)]
    elif protocol == "oscillate":
        fin = _recolored("fin_lit" if lit else "fin", kind)
        parts = [(flipped(fin), left), (fin, right)]
    else:
        raise KeyError(protocol)
    for part, (x, y) in parts:
        image.blit(part, part.get_rect(center=(x + 1, y + 1 + _bob(step))))
    return image


def regulator(
    protocol: str,
    facing_left: bool,
    needle: float | None = None,
    lit: bool = False,
    kind: str = "linesman",
    phase: int = 1,
    step: int | None = None,
    charged: bool = False,
    vent: bool = False,
) -> pygame.Surface:
    """The chassis in its protocol pose, walking at `step` (None stands). `needle` (radians,
    screen space) points the gauge at the Surge. `lit` flashes the Oscillate fins before a
    volley, `charged` is the wind-up before a kit attack, `vent` its punish window with the
    core exposed."""
    kind = "linesman" if kind == "regulator" else kind
    image = _posed(protocol, kind, step, lit, charged, phase, vent)
    if needle is not None:
        image = image.copy()
        angle = math.pi - needle if facing_left else needle
        (gx, gy), r = GAUGE[kind]
        cx, cy = gx + 1, gy + 1 + _bob(step)
        tip = (round(cx + math.cos(angle) * (r - 1)), round(cy + math.sin(angle) * (r - 1)))
        pygame.draw.line(image, rgb("px.outline"), (cx, cy), tip, 1)
        image.set_at((cx, cy), rgb("hostile.danger"))
    return flipped(image) if facing_left else image
