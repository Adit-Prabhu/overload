"""Cached, code-drawn sprites for every character, power and protocol.

Each builder draws once into a transparent surface centered on the sprite's origin and
facing +x. `Sprite.draw` rotates at draw time using a cache in 5 degree steps.
See docs/ART_AND_AUDIO_DIRECTION.md section 3 for what each design represents.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from functools import cache

import pygame

from overload.art import primitives as p

POWER_TOKENS = {
    "spark": "power.spark",
    "blink": "power.blink",
    "burst": "power.burst",
}
PROTOCOLS = ("clamp", "insulate", "oscillate")

SURGE_RADIUS = 12
ARC_MITE_RADIUS = 15
RELAY_RADIUS = 17
REGULATOR_RADIUS = 38
_ROTATION_STEP = 5


@dataclass(eq=False)
class Sprite:
    surface: pygame.Surface
    _rotations: dict[int, pygame.Surface] = field(default_factory=dict, repr=False)

    def rotated(self, angle: float) -> pygame.Surface:
        """Surface rotated to `angle` radians (screen space, 0 is +x, clockwise positive)."""
        bucket = round(math.degrees(angle) / _ROTATION_STEP) % (360 // _ROTATION_STEP)
        if bucket == 0:
            return self.surface
        if bucket not in self._rotations:
            self._rotations[bucket] = pygame.transform.rotate(
                self.surface, -bucket * _ROTATION_STEP
            )
        return self._rotations[bucket]

    def draw(self, target: pygame.Surface, center: p.Point, angle: float = 0.0) -> None:
        image = self.rotated(angle)
        target.blit(image, image.get_rect(center=(round(center[0]), round(center[1]))))


def _canvas(half: int) -> tuple[pygame.Surface, p.Point]:
    size = half * 2
    return pygame.Surface((size, size), pygame.SRCALPHA), (half, half)


# Powers -----------------------------------------------------------------------------------


def draw_power_symbol(surface: pygame.Surface, power: str, center: p.Point, r: float) -> None:
    """The one symbol per power used on enemies, pickups, HUD and effects."""
    token = POWER_TOKENS[power]
    width = max(2, round(r / 4))
    if power == "spark":
        p.fill(surface, token, p.bolt(center, r / 0.6))
    elif power == "blink":
        p.stroke(surface, token, p.diamond(center, r), width, closed=True)
    elif power == "burst":
        p.ring(surface, token, center, r, width)
        p.ring(surface, token, center, r * 0.45, max(1, width - 1))
    else:
        raise KeyError(power)


@cache
def power_icon(power: str, r: int) -> Sprite:
    surface, c = _canvas(r + 4)
    draw_power_symbol(surface, power, c, r)
    return Sprite(surface)


@cache
def charge(power: str) -> Sprite:
    """A dropped charge: the power symbol inside a thin ring of the same color."""
    surface, c = _canvas(16)
    p.ring(surface, POWER_TOKENS[power], c, 12, 1)
    draw_power_symbol(surface, power, c, 7)
    return Sprite(surface)


# Player -----------------------------------------------------------------------------------


@cache
def surge() -> Sprite:
    """The Surge: a junction dot with a halo ring. Its aim lead and sockets are drawn live."""
    surface, c = _canvas(SURGE_RADIUS + 10)
    p.ring(surface, "player.halo", c, SURGE_RADIUS + 5, 2)
    p.dot(surface, "player.core", c, SURGE_RADIUS - 1)
    return Sprite(surface)


# Components (enemies) ---------------------------------------------------------------------


@cache
def arc_mite() -> Sprite:
    """Spark carrier: a diode triangle with a resistor tail and a visible Spark core."""
    r = ARC_MITE_RADIUS
    surface, c = _canvas(round(r * 2))
    cx, cy = c
    body = [(cx + r, cy), (cx - r * 0.7, cy - r * 0.85), (cx - r * 0.7, cy + r * 0.85)]
    p.stroke(surface, "hostile.line", p.zigzag((cx - r * 0.7, cy), (cx - r * 1.7, cy), 2, 4), 2)
    p.shape(surface, body, "hostile.body", "hostile.line")
    p.stroke(surface, "hostile.line", [(cx + r, cy - r * 0.8), (cx + r, cy + r * 0.8)], 3)
    draw_power_symbol(surface, "spark", (cx - r * 0.12, cy), r * 0.42)
    return Sprite(surface)


@cache
def relay() -> Sprite:
    """Blink carrier: a relay housing with an open switch and a visible Blink core."""
    r = RELAY_RADIUS
    surface, c = _canvas(r + 6)
    cx, cy = c
    p.shape(surface, p.regular_polygon(c, r, 6), "hostile.body", "hostile.line")
    left, right = (cx - r * 0.5, cy + r * 0.45), (cx + r * 0.5, cy + r * 0.45)
    p.stroke(surface, "hostile.line", [left, (cx + r * 0.38, cy + r * 0.12)], 2)
    p.dot(surface, "hostile.line", left, 2.5)
    p.dot(surface, "hostile.line", right, 2.5)
    draw_power_symbol(surface, "blink", (cx, cy - r * 0.2), r * 0.38)
    return Sprite(surface)


# Regulator --------------------------------------------------------------------------------

GAUGE_RADIUS = 13
GAUGE_START = math.radians(135)
GAUGE_SWEEP = math.radians(270)


@cache
def regulator_body() -> Sprite:
    """Octagonal housing with a gauge face. The needle is drawn live to track the Surge."""
    r = REGULATOR_RADIUS
    surface, c = _canvas(r + 6)
    octagon = p.regular_polygon(c, r, 8, math.pi / 8)
    p.shape(surface, octagon, "rival.body", "hostile.line")
    p.stroke(surface, "hostile.line", p.regular_polygon(c, r * 0.78, 8, math.pi / 8), 1, True)
    p.ring(surface, "hostile.line", c, GAUGE_RADIUS, 2)
    for i in range(7):
        a = GAUGE_START + GAUGE_SWEEP * i / 6
        pygame.draw.line(
            surface,
            p.rgb("ui.dim"),
            p.polar(c, GAUGE_RADIUS - 5, a),
            p.polar(c, GAUGE_RADIUS - 2, a),
            1,
        )
    p.arc(
        surface,
        "hostile.danger",
        c,
        GAUGE_RADIUS - 3.5,
        GAUGE_START + GAUGE_SWEEP * 0.78,
        GAUGE_SWEEP * 0.22,
        2,
    )
    return Sprite(surface)


def _plate(center: p.Point, radius: float, angle: float, w: float, h: float) -> list[p.Point]:
    """A rectangular plate at `radius` from center, tangent to the circle at `angle`."""
    mx, my = p.polar(center, radius, angle)
    corners = [(-h / 2, -w / 2), (h / 2, -w / 2), (h / 2, w / 2), (-h / 2, w / 2)]
    return p.rotate(p.translate(corners, mx, my), (mx, my), angle)


@cache
def protocol_pose(protocol: str) -> Sprite:
    """Overlay drawn around the Regulator body, facing +x. Distinct silhouette per protocol."""
    r = REGULATOR_RADIUS
    surface, c = _canvas(r + 30)
    cx, cy = c
    if protocol == "clamp":
        upper = [
            (cx + r * 0.5, cy - r * 0.95),
            (cx + r * 1.45, cy - r * 0.38),
            (cx + r * 1.22, cy - r * 0.14),
            (cx + r * 0.6, cy - r * 0.5),
        ]
        lower = [(x, cy - (y - cy)) for x, y in upper]
        for plate in (upper, lower):
            p.shape(surface, plate, "hostile.body", "hostile.line", 2)
        p.shape(surface, p.chevron((cx + r * 1.5, cy), 13, 0), "hostile.body", "hostile.line", 2)
    elif protocol == "insulate":
        for i in range(8):
            plate = _plate(c, r + 12, math.tau * i / 8 + math.tau / 16, 16, 8)
            p.shape(surface, plate, "hostile.body", "hostile.line", 2)
            p.hatch(surface, "hostile.danger", plate, spacing=4)
    elif protocol == "oscillate":
        for side in (-1, 1):
            fin = [
                (cx - r * 0.4, cy + side * r * 0.86),
                (cx + r * 0.3, cy + side * r * 0.86),
                (cx - r * 0.3, cy + side * (r + 18)),
            ]
            p.shape(surface, fin, "hostile.body", "hostile.line", 2)
    else:
        raise KeyError(protocol)
    return Sprite(surface)


@cache
def protocol_icon(protocol: str, r: int) -> Sprite:
    """Small HUD symbol for the active protocol. Shape only, no text."""
    surface, c = _canvas(r + 4)
    cx, cy = c
    if protocol == "clamp":
        p.stroke(
            surface,
            "hostile.line",
            [(cx - r * 0.6, cy - r), (cx + r * 0.6, cy), (cx - r * 0.6, cy + r)],
            3,
        )
    elif protocol == "insulate":
        square = [(cx - r, cy - r), (cx + r, cy - r), (cx + r, cy + r), (cx - r, cy + r)]
        p.hatch(surface, "hostile.danger", square, spacing=4, width=2)
        p.stroke(surface, "hostile.line", square, 2, closed=True)
    elif protocol == "oscillate":
        p.stroke(surface, "hostile.line", p.sine_wave((cx - r, cy), (cx + r, cy), 1.5, r * 0.6), 3)
    else:
        raise KeyError(protocol)
    return Sprite(surface)


def catalog() -> dict[str, Sprite]:
    """Every cached sprite, keyed by a readable name. Used by the contact sheet and tests."""
    items: dict[str, Sprite] = {
        "surge": surge(),
        "arc_mite": arc_mite(),
        "relay": relay(),
        "regulator": regulator_body(),
    }
    for power in POWER_TOKENS:
        items[f"icon.{power}"] = power_icon(power, 12)
        items[f"charge.{power}"] = charge(power)
    for protocol in PROTOCOLS:
        items[f"pose.{protocol}"] = protocol_pose(protocol)
        items[f"protocol_icon.{protocol}"] = protocol_icon(protocol, 10)
    return items
