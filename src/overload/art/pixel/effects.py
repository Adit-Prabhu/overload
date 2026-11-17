"""Pixel effects: projectiles, charges, Arc Trail, telegraphs, dodge ghosts and hit flashes.

Functions draw onto `target` (the 320 x 180 view) and, for anything that emits light, also
onto `light` (a black surface the bloom pass reads). Coordinates are view pixels.
"""

from __future__ import annotations

import math
from functools import cache

import pygame

from overload.art.palette import rgb
from overload.art.pixel.grid import render

Point = tuple[float, float]

LEGEND = {
    "e": "px.hostile.2",
    "E": "px.hostile.3",
    "x": "px.hostile.0",
    "!": "hostile.danger",
    "Y": "power.spark",
    "y": "px.spark.light",
    "K": "power.blink",
    "k": "px.blink.light",
    "U": "power.burst",
    "u": "px.burst.light",
    "F": "player.core",
    "C": "player.core",
}

_HOSTILE_BOLT = [
    "...e...",
    ".e.E.e.",
    "..E!E..",
    "eE!.!Ee",
    "..E!E..",
    ".e.E.e.",
    "...e...",
]
_CHARGE = {
    "spark": [
        "....yY..",
        "...yY...",
        "..yYY...",
        ".YYYYYY.",
        "....YY..",
        "...YY...",
        "..Yy....",
    ],
    "blink": [
        "...k...",
        "..kKk..",
        ".kK.Kk.",
        "kK...Kk",
        ".kK.Kk.",
        "..kKk..",
        "...k...",
    ],
    "burst": [
        "..UUU..",
        ".U...U.",
        "U..u..U",
        "U.uuu.U",
        "U..u..U",
        ".U...U.",
        "..UUU..",
    ],
}
_DIAMOND = [
    "..k..",
    ".kKk.",
    "kK.Kk",
    ".kKk.",
    "..k..",
]
_PROTOCOL_ICON = {
    "clamp": [
        "e......",
        "EEe....",
        ".EEEe..",
        "..EEEE.",
        ".EEEe..",
        "EEe....",
        "e......",
    ],
    "insulate": [
        "EEEEEEE",
        "E!x!x!E",
        "Ex!x!xE",
        "E!x!x!E",
        "Ex!x!xE",
        "E!x!x!E",
        "EEEEEEE",
    ],
    "oscillate": [
        ".......",
        ".EE....",
        "E..E...",
        "....E..",
        ".....E.",
        "......E",
        ".......",
    ],
}
_RETICLE = [
    "....F....",
    "....F....",
    ".........",
    ".........",
    "FF..C..FF",
    ".........",
    ".........",
    "....F....",
    "....F....",
]


@cache
def hostile_bolt() -> pygame.Surface:
    return render(_HOSTILE_BOLT, LEGEND, outline=None)


@cache
def charge_icon(power: str) -> pygame.Surface:
    return render(_CHARGE[power], LEGEND)


@cache
def protocol_icon(protocol: str) -> pygame.Surface:
    return render(_PROTOCOL_ICON[protocol], LEGEND)


@cache
def reticle() -> pygame.Surface:
    return render(_RETICLE, LEGEND)


def _blit_center(target: pygame.Surface, image: pygame.Surface, pos: Point) -> None:
    target.blit(image, image.get_rect(center=(round(pos[0]), round(pos[1]))))


def player_shot(target: pygame.Surface, light: pygame.Surface, pos: Point, angle: float):
    x, y = pos
    tail = (x - math.cos(angle) * 4, y - math.sin(angle) * 4)
    for surface in (target, light):
        pygame.draw.line(surface, rgb("player.halo"), tail, pos, 2)
        pygame.draw.rect(surface, rgb("player.core"), (round(x) - 1, round(y) - 1, 2, 2))


def bolt(target: pygame.Surface, light: pygame.Surface, pos: Point) -> None:
    _blit_center(target, hostile_bolt(), pos)
    _blit_center(light, hostile_bolt(), pos)


def charge(target: pygame.Surface, light: pygame.Surface, pos: Point, power: str, t: float):
    bob = round(math.sin(t * 3 + pos[0] * 0.1) * 1.5)
    spot = (pos[0], pos[1] + bob)
    _blit_center(target, charge_icon(power), spot)
    _blit_center(light, charge_icon(power), spot)


def arc_trail(
    target: pygame.Surface, light: pygame.Surface, start: Point, end: Point, life: float
) -> None:
    """Spark + Blink fusion: a jagged spark line strung between two Blink diamonds."""
    if life <= 0:
        return
    sx, sy = start
    dx, dy = end[0] - sx, end[1] - sy
    length = math.hypot(dx, dy) or 1.0
    nx, ny = -dy / length, dx / length
    steps = max(2, int(length / 6))
    points = []
    for i in range(steps + 1):
        f = i / steps
        offset = 0 if i in (0, steps) else (3 if i % 2 else -3)
        points.append((round(sx + dx * f + nx * offset), round(sy + dy * f + ny * offset)))
    diamond = render(_DIAMOND, LEGEND, outline=None)
    for surface in (target, light):
        pygame.draw.lines(surface, rgb("power.spark"), False, points, 2)
        pygame.draw.lines(surface, rgb("px.spark.light"), False, points, 1)
        _blit_center(surface, diamond, start)
        _blit_center(surface, diamond, end)


def blink_ghost(target: pygame.Surface, light: pygame.Surface, pos: Point) -> None:
    diamond = render(_DIAMOND, LEGEND, outline=None)
    _blit_center(target, diamond, pos)
    _blit_center(light, diamond, pos)


def _ring_dots(
    surface: pygame.Surface, token: str, center: Point, radius: float, progress: float
) -> None:
    count = max(1, int(round(radius * 2.2)))
    lit = int(count * max(0.0, min(1.0, progress)))
    for i in range(lit):
        a = -math.pi / 2 + math.tau * i / count
        surface.set_at(
            (round(center[0] + math.cos(a) * radius), round(center[1] + math.sin(a) * radius)),
            rgb(token),
        )


def aim_tell(
    target: pygame.Surface,
    light: pygame.Surface,
    origin: Point,
    angle: float,
    progress: float,
    reach: float = 70,
) -> None:
    """Aimed-shot telegraph: a dotted line shows the locked direction while a ring of dots
    fills around the shooter. Readable without color: it is a line plus a filling ring."""
    ox, oy = origin
    for d in range(10, int(reach), 4):
        point = (round(ox + math.cos(angle) * d), round(oy + math.sin(angle) * d))
        target.fill(rgb("hostile.danger"), (*point, 2, 1))
    for surface in (target, light):
        _ring_dots(surface, "hostile.danger", origin, 11, progress)


def relay_destination(target: pygame.Surface, pos: Point, progress: float) -> None:
    """Where a Relay will land: a hatched diamond outline that fills over the tell."""
    cx, cy = round(pos[0]), round(pos[1])
    r = 7
    for dy in range(-r, r + 1):
        span = r - abs(dy)
        for dx in (-span, span):
            target.set_at((cx + dx, cy + dy), rgb("px.hostile.3"))
        if abs(dy) <= r * progress:
            for dx in range(-span + 1, span):
                if (dx + dy) % 3 == 0:
                    target.set_at((cx + dx, cy + dy), rgb("hostile.danger"))


def hazard_tile(
    target: pygame.Surface, light: pygame.Surface, top_left: Point, progress: float
) -> None:
    """Insulate protocol hazard: outline at once, hatching fills downward over the tell."""
    x, y = round(top_left[0]), round(top_left[1])
    pygame.draw.rect(target, rgb("px.hostile.3"), (x, y, 16, 16), 1)
    rows = int(14 * max(0.0, min(1.0, progress)))
    for dy in range(1, 1 + rows):
        for dx in range(1, 15):
            if (dx + dy) % 3 == 0:
                target.set_at((x + dx, y + dy), rgb("hostile.danger"))
                light.set_at((x + dx, y + dy), rgb("px.hostile.1"))


def tinted(image: pygame.Surface, token: str) -> pygame.Surface:
    """Same silhouette filled with one palette color, for hit flashes and dodge ghosts."""
    copy = image.copy()
    copy.fill(rgb(token), special_flags=pygame.BLEND_RGB_MAX)
    return copy


def ghost(target: pygame.Surface, image: pygame.Surface, top_left: Point, alpha: int) -> None:
    faded = tinted(image, "player.halo")
    faded.set_alpha(alpha)
    target.blit(faded, (round(top_left[0]), round(top_left[1])))
