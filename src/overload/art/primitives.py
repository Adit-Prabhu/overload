"""Shared drawing primitives. Every sprite and effect is built from these.

Shapes follow the schematic grammar in docs/ART_AND_AUDIO_DIRECTION.md section 2:
junction dots, zigzags, diamonds, rings, chevrons, hatching and regular polygons.
Geometry helpers are pure functions that return point lists. Drawing helpers take a
palette token, never a raw color.
"""

from __future__ import annotations

import math
from collections.abc import Sequence

import pygame

from overload.art.palette import rgb, rgba

Point = tuple[float, float]

STROKE_DETAIL = 2
STROKE_OUTLINE = 3
STROKE_WALL = 5


# Geometry ---------------------------------------------------------------------------------


def polar(center: Point, radius: float, angle: float) -> Point:
    """Point at `radius` from `center` in direction `angle` (radians, 0 is +x)."""
    return (center[0] + math.cos(angle) * radius, center[1] + math.sin(angle) * radius)


def regular_polygon(center: Point, radius: float, sides: int, rotation: float = 0.0) -> list[Point]:
    return [polar(center, radius, rotation + math.tau * i / sides) for i in range(sides)]


def diamond(center: Point, radius: float) -> list[Point]:
    return regular_polygon(center, radius, 4, -math.pi / 2)


def rotate(points: Sequence[Point], center: Point, angle: float) -> list[Point]:
    cos_a, sin_a = math.cos(angle), math.sin(angle)
    cx, cy = center
    return [
        (cx + (x - cx) * cos_a - (y - cy) * sin_a, cy + (x - cx) * sin_a + (y - cy) * cos_a)
        for x, y in points
    ]


def translate(points: Sequence[Point], dx: float, dy: float) -> list[Point]:
    return [(x + dx, y + dy) for x, y in points]


def zigzag(start: Point, end: Point, teeth: int, amplitude: float) -> list[Point]:
    """Resistor-style zigzag from start to end with `teeth` full peaks."""
    sx, sy = start
    dx, dy = end[0] - sx, end[1] - sy
    length = math.hypot(dx, dy) or 1.0
    nx, ny = -dy / length, dx / length
    points = [start]
    steps = teeth * 2
    for i in range(1, steps):
        t = i / steps
        side = amplitude if i % 2 else -amplitude
        points.append((sx + dx * t + nx * side, sy + dy * t + ny * side))
    points.append(end)
    return points


def chevron(center: Point, size: float, angle: float, depth: float = 0.55) -> list[Point]:
    """Arrowhead outline pointing in `angle`, as a closed polygon."""
    s = size
    shape = [(s, 0.0), (-s * 0.6, -s), (-s * 0.6 + s * depth, 0.0), (-s * 0.6, s)]
    return rotate(translate(shape, *center), center, angle)


def bolt(center: Point, size: float) -> list[Point]:
    """Filled lightning-bolt polygon, the Spark symbol."""
    unit = [(0.18, -0.6), (-0.32, 0.06), (-0.02, 0.06), (-0.18, 0.6), (0.32, -0.06), (0.02, -0.06)]
    return [(center[0] + x * size, center[1] + y * size) for x, y in unit]


def sine_wave(start: Point, end: Point, cycles: float, amplitude: float, steps: int = 24):
    sx, sy = start
    dx, dy = end[0] - sx, end[1] - sy
    length = math.hypot(dx, dy) or 1.0
    nx, ny = -dy / length, dx / length
    points = []
    for i in range(steps + 1):
        t = i / steps
        offset = math.sin(t * cycles * math.tau) * amplitude
        points.append((sx + dx * t + nx * offset, sy + dy * t + ny * offset))
    return points


# Drawing ----------------------------------------------------------------------------------


def stroke(
    surface: pygame.Surface,
    token: str,
    points: Sequence[Point],
    width: int = STROKE_OUTLINE,
    closed: bool = False,
) -> None:
    """Polyline with round joints so thick strokes don't crack at corners."""
    color = rgb(token)
    pygame.draw.lines(surface, color, closed, points, width)
    if width > 2:
        joint = max(1, width // 2)
        for point in points:
            pygame.draw.circle(surface, color, point, joint)


def fill(surface: pygame.Surface, token: str, points: Sequence[Point]) -> None:
    pygame.draw.polygon(surface, rgb(token), points)


def shape(
    surface: pygame.Surface,
    points: Sequence[Point],
    fill_token: str | None,
    line_token: str,
    width: int = STROKE_OUTLINE,
) -> None:
    """Filled polygon with an outline, the standard housing for any entity."""
    if fill_token:
        fill(surface, fill_token, points)
    stroke(surface, line_token, points, width, closed=True)


def ring(surface: pygame.Surface, token: str, center: Point, radius: float, width: int) -> None:
    pygame.draw.circle(surface, rgb(token), center, radius, width)


def dot(surface: pygame.Surface, token: str, center: Point, radius: float) -> None:
    pygame.draw.circle(surface, rgb(token), center, radius)


def arc(
    surface: pygame.Surface,
    token: str,
    center: Point,
    radius: float,
    start: float,
    sweep: float,
    width: int,
) -> None:
    """Arc from `start` through `sweep` radians, clockwise on screen. Used for gauges and fills."""
    if sweep <= 0:
        return
    steps = max(2, int(abs(sweep) * radius / 4))
    points = [polar(center, radius, start + sweep * i / steps) for i in range(steps + 1)]
    stroke(surface, token, points, width)


def dashed(
    surface: pygame.Surface,
    token: str,
    start: Point,
    end: Point,
    dash: float = 8,
    gap: float = 6,
    width: int = STROKE_DETAIL,
) -> None:
    sx, sy = start
    dx, dy = end[0] - sx, end[1] - sy
    length = math.hypot(dx, dy)
    if length == 0:
        return
    ux, uy = dx / length, dy / length
    pos = 0.0
    color = rgb(token)
    while pos < length:
        seg_end = min(pos + dash, length)
        pygame.draw.line(
            surface,
            color,
            (sx + ux * pos, sy + uy * pos),
            (sx + ux * seg_end, sy + uy * seg_end),
            width,
        )
        pos = seg_end + gap


def hatch(
    surface: pygame.Surface,
    token: str,
    points: Sequence[Point],
    spacing: int = 6,
    width: int = 1,
) -> None:
    """Diagonal hatching clipped to a polygon. Marks danger without relying on color."""
    xs = [p[0] for p in points]
    ys = [p[1] for p in points]
    left, top = int(min(xs)) - 1, int(min(ys)) - 1
    w, h = int(max(xs)) - left + 2, int(max(ys)) - top + 2
    if w <= 0 or h <= 0:
        return
    lines = pygame.Surface((w, h), pygame.SRCALPHA)
    color = rgb(token)
    for offset in range(-h, w, spacing):
        pygame.draw.line(lines, color, (offset, h), (offset + h, 0), width)
    mask = pygame.Surface((w, h), pygame.SRCALPHA)
    pygame.draw.polygon(mask, rgba("fx.flash", 255), translate(points, -left, -top))
    lines.blit(mask, (0, 0), special_flags=pygame.BLEND_RGBA_MULT)
    surface.blit(lines, (left, top))
