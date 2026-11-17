"""Substation tiles (16 x 16) and tall props, drawn pixel by pixel from palette ramps.

Room grids use one character per tile:
    #  wall top (solid)          w  wall face, the visible front of a wall (solid)
    .  floor plate               ,  scuffed floor plate
    g  floor grate               -  lit conduit, horizontal     |  lit conduit, vertical
    T  transformer (2 x 2 footprint, solid)                      I  insulator stack (solid)
The 3/4 view shows wall tops and the front faces of walls and props, like classic top-down
RPGs. Props are drawn separately so actors can stand in front of or behind them.
"""

from __future__ import annotations

import random
from collections.abc import Sequence
from dataclasses import dataclass
from functools import cache

import pygame

from overload.art.palette import rgb
from overload.art.pixel.grid import add_outline

TILE = 16
SOLID = frozenset("#wTI")


def _px(surface: pygame.Surface, token: str, x: int, y: int, w: int = 1, h: int = 1) -> None:
    surface.fill(rgb(token), (x, y, w, h))


@cache
def floor_plate(scuffed: bool = False) -> pygame.Surface:
    s = pygame.Surface((TILE, TILE))
    s.fill(rgb("px.floor.1"))
    _px(s, "px.floor.2", 0, 0, TILE, 1)
    _px(s, "px.floor.2", 0, 0, 1, TILE)
    _px(s, "px.floor.0", 0, TILE - 1, TILE, 1)
    _px(s, "px.floor.0", TILE - 1, 0, 1, TILE)
    for x, y in ((2, 2), (12, 2), (2, 12), (12, 12)):
        _px(s, "px.floor.3", x, y)
        _px(s, "px.floor.0", x + 1, y + 1)
    if scuffed:
        for x, y in ((5, 9), (6, 8), (7, 8), (8, 7), (10, 5)):
            _px(s, "px.floor.2", x, y)
    return s


@cache
def grate() -> pygame.Surface:
    s = pygame.Surface((TILE, TILE))
    s.fill(rgb("px.floor.0"))
    _px(s, "px.floor.2", 0, 0, TILE, 1)
    _px(s, "px.floor.2", 0, 0, 1, TILE)
    for y in range(3, TILE - 2, 3):
        _px(s, "px.floor.1", 2, y, TILE - 4, 1)
    return s


@cache
def conduit(vertical: bool) -> tuple[pygame.Surface, pygame.Surface]:
    """Floor plate with a lit power line. Returns (tile, light) where light is additive."""
    s = floor_plate().copy()
    light = pygame.Surface((TILE, TILE))
    light.fill(rgb("px.void"))
    if vertical:
        _px(s, "px.conduit.0", 6, 0, 4, TILE)
        _px(s, "px.conduit.1", 7, 0, 2, TILE)
        _px(light, "px.conduit.1", 7, 0, 2, TILE)
    else:
        _px(s, "px.conduit.0", 0, 6, TILE, 4)
        _px(s, "px.conduit.1", 0, 7, TILE, 2)
        _px(light, "px.conduit.1", 0, 7, TILE, 2)
    return s, light


@cache
def wall_top() -> pygame.Surface:
    s = pygame.Surface((TILE, TILE))
    s.fill(rgb("px.wall.3"))
    _px(s, "px.wall.4", 0, 0, TILE, 1)
    _px(s, "px.wall.2", 0, TILE - 2, TILE, 2)
    for x in (3, 12):
        _px(s, "px.wall.4", x, 5)
        _px(s, "px.wall.2", x + 1, 6)
    return s


@cache
def wall_face() -> pygame.Surface:
    s = pygame.Surface((TILE, TILE))
    s.fill(rgb("px.wall.1"))
    _px(s, "px.wall.0", 0, 0, TILE, 2)
    for x in range(2, TILE, 4):
        _px(s, "px.wall.2", x, 3, 1, 8)
    for x in range(TILE):
        for y in range(11, 15):
            token = "px.hazard.1" if ((x + y) // 2) % 2 == 0 else "px.hazard.0"
            _px(s, token, x, y)
    _px(s, "px.outline", 0, TILE - 1, TILE, 1)
    return s


@cache
def transformer() -> pygame.Surface:
    """Tall prop over a 2 x 2 tile footprint: cooling-fin top and a vented front with a
    hazard placard. Drawn 32 x 44, with its footprint in the bottom 32 rows."""
    w, h = 2 * TILE, 2 * TILE + 12
    s = pygame.Surface((w, h), pygame.SRCALPHA)
    _px(s, "px.wall.3", 1, 1, w - 2, 14)
    _px(s, "px.wall.4", 1, 1, w - 2, 1)
    for x in range(4, w - 3, 3):
        _px(s, "px.wall.2", x, 3, 1, 10)
    _px(s, "px.wall.1", 1, 15, w - 2, h - 17)
    _px(s, "px.wall.0", 1, 15, w - 2, 2)
    for y in range(19, h - 6, 3):
        _px(s, "px.wall.0", 4, y, 10, 1)
    _px(s, "px.hazard.1", 19, 20, 9, 9)
    _px(s, "px.hazard.0", 23, 22, 1, 4)
    _px(s, "px.hazard.0", 23, 27, 1, 1)
    _px(s, "px.wall.0", 1, h - 4, w - 2, 2)
    pygame.draw.rect(s, rgb("px.outline"), (0, 0, w, h - 1), 1)
    return s


@cache
def insulator() -> pygame.Surface:
    """Ceramic insulator stack on a steel base. 16 x 30, footprint is the bottom 16 rows."""
    w, h = TILE, 30
    s = pygame.Surface((w, h), pygame.SRCALPHA)
    _px(s, "px.wall.1", 2, h - 7, w - 4, 5)
    _px(s, "px.wall.2", 2, h - 7, w - 4, 1)
    for i, y in enumerate(range(2, h - 8, 4)):
        inset = 3 if i % 2 else 2
        _px(s, "px.ceramic.1", inset, y, w - 2 * inset, 3)
        _px(s, "px.ceramic.2", inset + 1, y, w - 2 * inset - 3, 1)
        _px(s, "px.ceramic.0", inset, y + 2, w - 2 * inset, 1)
    _px(s, "px.ceramic.0", 7, 1, 2, h - 8)
    add_outline(s, "px.outline")
    return s


@dataclass(frozen=True)
class Prop:
    kind: str
    tile_x: int
    tile_y: int

    @property
    def footprint(self) -> tuple[int, int, int, int]:
        size = 2 if self.kind == "T" else 1
        return (self.tile_x * TILE, self.tile_y * TILE, size * TILE, size * TILE)

    @property
    def base_y(self) -> int:
        x, y, w, h = self.footprint
        return y + h

    def image(self) -> pygame.Surface:
        return transformer() if self.kind == "T" else insulator()

    def draw(self, target: pygame.Surface, camera: tuple[int, int]) -> None:
        image = self.image()
        x, y, w, h = self.footprint
        target.blit(image, (x - camera[0], y + h - image.get_height() - camera[1]))


def props(rows: Sequence[str]) -> list[Prop]:
    found: list[Prop] = []
    seen: set[tuple[int, int]] = set()
    for y, row in enumerate(rows):
        for x, char in enumerate(row):
            if char == "I":
                found.append(Prop("I", x, y))
            elif char == "T" and (x, y) not in seen:
                seen.update({(x, y), (x + 1, y), (x, y + 1), (x + 1, y + 1)})
                found.append(Prop("T", x, y))
    return found


def render_room(rows: Sequence[str], seed: int = 3) -> tuple[pygame.Surface, pygame.Surface]:
    """Return (background, light). Background has floor and walls. Light is black plus the
    glowing conduits, added once per frame. Props are drawn separately with the actors."""
    rng = random.Random(seed)
    w, h = len(rows[0]) * TILE, len(rows) * TILE
    background = pygame.Surface((w, h))
    background.fill(rgb("px.void"))
    light = pygame.Surface((w, h))
    light.fill(rgb("px.void"))
    for ty, row in enumerate(rows):
        for tx, char in enumerate(row):
            pos = (tx * TILE, ty * TILE)
            if char == "#":
                background.blit(wall_top(), pos)
            elif char == "w":
                background.blit(wall_face(), pos)
            elif char == "g":
                background.blit(grate(), pos)
            elif char in "-|":
                tile, glow = conduit(char == "|")
                background.blit(tile, pos)
                light.blit(glow, pos)
            else:
                background.blit(floor_plate(char == "," or rng.random() < 0.12), pos)
    return background, light
