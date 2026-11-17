"""Collision geometry with deterministic float math (sqrt only)."""

from __future__ import annotations

import math

Point = tuple[float, float]
Rect = tuple[float, float, float, float]


def length(dx: float, dy: float) -> float:
    return math.sqrt(dx * dx + dy * dy)


def normalize(dx: float, dy: float) -> Point:
    """Unit vector, or (0, 0) for a zero vector."""
    size = length(dx, dy)
    if size == 0.0:
        return (0.0, 0.0)
    return (dx / size, dy / size)


def circles_overlap(a: Point, ra: float, b: Point, rb: float) -> bool:
    dx, dy = a[0] - b[0], a[1] - b[1]
    reach = ra + rb
    return dx * dx + dy * dy < reach * reach


def circle_hits_rect(center: Point, radius: float, rect: Rect) -> bool:
    x, y, w, h = rect
    nearest_x = min(max(center[0], x), x + w)
    nearest_y = min(max(center[1], y), y + h)
    dx, dy = center[0] - nearest_x, center[1] - nearest_y
    return dx * dx + dy * dy < radius * radius


def push_out_of_rect(center: Point, radius: float, rect: Rect) -> Point:
    """Move a circle the shortest distance so it no longer overlaps `rect`."""
    x, y, w, h = rect
    cx, cy = center
    nearest_x = min(max(cx, x), x + w)
    nearest_y = min(max(cy, y), y + h)
    dx, dy = cx - nearest_x, cy - nearest_y
    dist_sq = dx * dx + dy * dy
    if dist_sq >= radius * radius:
        return center
    if dist_sq > 0.0:
        dist = math.sqrt(dist_sq)
        push = radius - dist
        return (cx + dx / dist * push, cy + dy / dist * push)
    # Center is inside the rectangle: leave by the nearest edge.
    exits = [
        (cx - x + radius, (x - radius, cy)),
        (x + w - cx + radius, (x + w + radius, cy)),
        (cy - y + radius, (cx, y - radius)),
        (y + h - cy + radius, (cx, y + h + radius)),
    ]
    return min(exits, key=lambda item: item[0])[1]


def clamp_inside(center: Point, radius: float, bounds: Rect) -> Point:
    x, y, w, h = bounds
    return (
        min(max(center[0], x + radius), x + w - radius),
        min(max(center[1], y + radius), y + h - radius),
    )


def outside_bounds(center: Point, radius: float, bounds: Rect) -> bool:
    x, y, w, h = bounds
    cx, cy = center
    return cx - radius < x or cx + radius > x + w or cy - radius < y or cy + radius > y + h
