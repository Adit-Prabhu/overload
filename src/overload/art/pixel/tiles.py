"""The substation tileset: floors, autotiled walls, wall fixtures, floor decals and props.

How a room is drawn (16 px tiles, 3/4 top-down view):
- Floors: concrete slabs with 2 x 2 tile joints, a diamond-plate steel walkway, cable trench
  grates with cables underneath, hazard-painted keep-out zones and lit conduit channels.
  Materials draw their own borders where they meet a different material.
- Walls: a wall with floor below shows its front face. The wall above that shows the upper
  face with a lit rim on top, so walls stand two tiles tall. Side walls show a rim along the
  floor edge. Faces cast a short shadow onto the floor.
- Decor: fixtures on wall faces, decals on the floor, and props with their own height that
  are drawn later, sorted with the actors.
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field
from functools import cache

import pygame

from overload.art.palette import rgb, rgba
from overload.art.pixel.grid import add_outline
from overload.rooms import TILE, Room, footprint_tiles

Point = tuple[int, int]


def _px(s: pygame.Surface, token: str, x: int, y: int, w: int = 1, h: int = 1) -> None:
    s.fill(rgb(token), (x, y, w, h))


def _rng(x: int, y: int, salt: int = 0) -> random.Random:
    return random.Random(x * 7919 + y * 104729 + salt * 15485863)


@dataclass
class RoomArt:
    background: pygame.Surface
    light: pygame.Surface
    lamps: list[Point] = field(default_factory=list)
    ceiling: list[Point] = field(default_factory=list)
    leds: list[tuple[Point, str, int]] = field(default_factory=list)
    props: list[Prop] = field(default_factory=list)


# Floors ------------------------------------------------------------------------------------


def _floor_tile(s: pygame.Surface, x0: int, y0: int, tx: int, ty: int) -> None:
    """Steel floor tile: per-tile shade, a dark gap on two sides, a bevel and light wear."""
    rng = _rng(tx, ty, 11)
    base = rng.choice(("px.tile.1", "px.tile.1", "px.tile.2"))
    _px(s, base, x0, y0, TILE, TILE)
    _px(s, "px.tile.3", x0 + 1, y0 + 1, TILE - 2, 1)
    _px(s, "px.tile.3", x0 + 1, y0 + 1, 1, TILE - 2)
    _px(s, "px.tile.0", x0 + 1, y0 + TILE - 2, TILE - 2, 1)
    _px(s, "px.tile.0", x0 + TILE - 2, y0 + 1, 1, TILE - 2)
    _px(s, "px.outline", x0, y0 + TILE - 1, TILE, 1)
    _px(s, "px.outline", x0 + TILE - 1, y0, 1, TILE)
    for _ in range(4):
        _px(
            s,
            rng.choice(("px.tile.0", "px.tile.3")),
            x0 + rng.randrange(3, 13),
            y0 + rng.randrange(3, 13),
        )
    if rng.random() < 0.15:
        corner = rng.choice(((2, 2), (11, 2), (2, 11), (11, 11)))
        _px(s, "px.tile.0", x0 + corner[0], y0 + corner[1], 3, 2)
    if rng.random() < 0.2:
        y = y0 + rng.randrange(4, 12)
        _px(s, "px.tile.3", x0 + rng.randrange(3, 7), y, rng.randrange(3, 7), 1)


def _concrete(s: pygame.Surface, x0: int, y0: int, tx: int, ty: int) -> None:
    rng = _rng(tx, ty)
    _px(s, "px.concrete.1", x0, y0, TILE, TILE)
    for _ in range(10):
        token = "px.concrete.0" if rng.random() < 0.6 else "px.concrete.2"
        _px(s, token, x0 + rng.randrange(TILE), y0 + rng.randrange(TILE))
    if ty % 2 == 0:
        _px(s, "px.concrete.0", x0, y0, TILE, 1)
        _px(s, "px.concrete.2", x0, y0 + 1, TILE, 1)
    if tx % 2 == 0:
        _px(s, "px.concrete.0", x0, y0, 1, TILE)
        _px(s, "px.concrete.2", x0 + 1, y0 + 1, 1, TILE - 1)
    if rng.random() < 0.18:
        x, y = x0 + rng.randrange(3, 12), y0 + rng.randrange(3, 12)
        for _ in range(rng.randint(4, 7)):
            _px(s, "px.concrete.0", x, y)
            x += rng.choice((-1, 0, 1))
            y += 1


def _plate(
    s: pygame.Surface, x0: int, y0: int, tx: int, ty: int, open_sides: dict[str, bool]
) -> None:
    """Diamond-plate walkway with painted yellow edge lines and direction arrows.
    `open_sides[d]` is True where the neighbor is not walkway."""
    _px(s, "px.floor.2", x0, y0, TILE, TILE)
    for row, py in enumerate(range(1, TILE, 4)):
        for px in range(1 + (row % 2) * 2, TILE - 1, 4):
            _px(s, "px.floor.3", x0 + px, y0 + py)
            _px(s, "px.floor.2", x0 + px + 1, y0 + py)
            _px(s, "px.floor.0", x0 + px + 1, y0 + py + 1)
    if open_sides["N"]:
        _px(s, "px.outline", x0, y0, TILE, 1)
        _px(s, "px.floor.3", x0, y0 + 1, TILE, 1)
    if open_sides["S"]:
        _px(s, "px.floor.0", x0, y0 + TILE - 2, TILE, 1)
        _px(s, "px.outline", x0, y0 + TILE - 1, TILE, 1)
    if open_sides["W"]:
        _px(s, "px.outline", x0, y0, 1, TILE)
        _px(s, "px.floor.3", x0 + 1, y0, 1, TILE)
    if open_sides["E"]:
        _px(s, "px.floor.0", x0 + TILE - 2, y0, 1, TILE)
        _px(s, "px.outline", x0 + TILE - 1, y0, 1, TILE)
    for side, (x, y, w, h) in (
        ("N", (0, 3, TILE, 1)),
        ("S", (0, TILE - 4, TILE, 1)),
        ("W", (3, 0, 1, TILE)),
        ("E", (TILE - 4, 0, 1, TILE)),
    ):
        if open_sides[side]:
            for k in range(0, max(w, h), 4):
                if w > 1:
                    _px(s, "px.hazard.1", x0 + x + k, y0 + y, 3, 1)
                else:
                    _px(s, "px.hazard.1", x0 + x, y0 + y + k, 1, 3)
    horizontal = not open_sides["W"] or not open_sides["E"]
    vertical = not open_sides["N"] or not open_sides["S"]
    if horizontal != vertical and (tx + ty) % 4 == 0:
        cx, cy = x0 + 8, y0 + 8
        for k in range(3):
            if horizontal:
                _px(s, "px.paint", cx - 2 + k, cy - 2 + k, 1, 1)
                _px(s, "px.paint", cx - 2 + k, cy + 2 - k, 1, 1)
            else:
                _px(s, "px.paint", cx - 2 + k, cy - 2 + k, 1, 1)
                _px(s, "px.paint", cx + 2 - k, cy - 2 + k, 1, 1)


def _trench(
    s: pygame.Surface, x0: int, y0: int, open_sides: dict[str, bool], horizontal: bool
) -> None:
    """Cable trench under a grate: dark pit, bundled cables, steel bars, a frame at edges."""
    _px(s, "px.void", x0, y0, TILE, TILE)
    cables = (
        ("px.wood.0", "px.wood.1"),
        ("px.conduit.0", "px.conduit.1"),
        ("px.bot.0", "px.bot.2"),
    )
    for i, (dark, light) in enumerate(cables):
        offset = 4 + i * 3
        if horizontal:
            _px(s, dark, x0, y0 + offset, TILE, 2)
            _px(s, light, x0, y0 + offset, TILE, 1)
        else:
            _px(s, dark, x0 + offset, y0, 2, TILE)
            _px(s, light, x0 + offset, y0, 1, TILE)
    for k in range(0, TILE, 3):
        if horizontal:
            _px(s, "px.floor.2", x0 + k, y0, 1, TILE)
        else:
            _px(s, "px.floor.2", x0, y0 + k, TILE, 1)
    for side, rect in (
        ("N", (0, 0, TILE, 2)),
        ("S", (0, TILE - 2, TILE, 2)),
        ("W", (0, 0, 2, TILE)),
        ("E", (TILE - 2, 0, 2, TILE)),
    ):
        if open_sides[side]:
            x, y, w, h = rect
            _px(s, "px.floor.3", x0 + x, y0 + y, w, h)
            _px(
                s,
                "px.outline",
                x0 + x + (w - 1 if side == "E" else 0),
                y0 + y + (h - 1 if side == "S" else 0),
                1 if side in "WE" else w,
                1 if side in "NS" else h,
            )


def _hazard(
    s: pygame.Surface, x0: int, y0: int, tx: int, ty: int, open_sides: dict[str, bool]
) -> None:
    """Keep-out zone: concrete with a worn, striped yellow band along the zone border."""
    _concrete(s, x0, y0, tx, ty)
    rng = _rng(tx, ty, 3)
    for y in range(TILE):
        for x in range(TILE):
            near = (
                (open_sides["N"] and y < 4)
                or (open_sides["S"] and y > TILE - 5)
                or (open_sides["W"] and x < 4)
                or (open_sides["E"] and x > TILE - 5)
            )
            if near and ((x0 + x + y0 + y) // 3) % 2 == 0 and rng.random() < 0.85:
                _px(s, "px.hazard.1", x0 + x, y0 + y)


def _conduit(
    s: pygame.Surface, light: pygame.Surface, x0: int, y0: int, tx: int, ty: int, char: str
) -> None:
    _concrete(s, x0, y0, tx, ty)
    runs = {"-": ("h",), "|": ("v",), "+": ("h", "v")}[char]
    for run in runs:
        if run == "h":
            _px(s, "px.concrete.0", x0, y0 + 6, TILE, 4)
            _px(s, "px.conduit.0", x0, y0 + 7, TILE, 2)
            _px(s, "px.conduit.1", x0, y0 + 7, TILE, 1)
            _px(light, "px.conduit.1", x0, y0 + 7, TILE, 1)
        else:
            _px(s, "px.concrete.0", x0 + 6, y0, 4, TILE)
            _px(s, "px.conduit.0", x0 + 7, y0, 2, TILE)
            _px(s, "px.conduit.1", x0 + 7, y0, 1, TILE)
            _px(light, "px.conduit.1", x0 + 7, y0, 1, TILE)


# Floor decals ------------------------------------------------------------------------------


def _decal(s: pygame.Surface, char: str, x0: int, y0: int, tx: int, ty: int) -> None:
    rng = _rng(tx, ty, 7)
    if char == "o":
        cx, cy = x0 + 8, y0 + 9
        for _ in range(26):
            dx, dy = rng.randint(-5, 5), rng.randint(-3, 3)
            if dx * dx / 30 + dy * dy / 11 <= 1:
                _px(
                    s,
                    "px.outline" if abs(dx) < 3 and abs(dy) < 2 else "px.concrete.0",
                    cx + dx,
                    cy + dy,
                )
        _px(s, "px.concrete.3", cx - 2, cy - 1, 2, 1)
    elif char == "x":
        cx, cy = x0 + 8, y0 + 8
        _px(s, "px.outline", cx - 1, cy - 1, 3, 3)
        for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1), (1, 1), (-1, -1), (1, -1), (-1, 1)):
            for step in range(2, rng.randint(4, 7)):
                _px(s, "px.concrete.0", cx + dx * step, cy + dy * step)
        _px(s, "px.hostile.0", cx + 2, cy - 1)
        _px(s, "px.hostile.1", cx - 1, cy + 2)
    elif char == "c":
        y = y0 + 4
        for x in range(x0, x0 + TILE):
            _px(s, "px.bot.0", x, y, 1, 2)
            _px(s, "px.bot.2", x, y)
            if rng.random() < 0.35:
                y = max(y0 + 2, min(y0 + 12, y + rng.choice((-1, 1))))
        _px(s, "px.bot.3", x0 + TILE - 3, y - 1, 3, 3)
        _px(s, "px.hazard.1", x0 + TILE - 2, y, 1, 1)
    elif char == "d":
        _px(s, "px.concrete.3", x0 + 3, y0 + 3, 10, 10)
        _px(s, "px.void", x0 + 4, y0 + 4, 8, 8)
        for k in range(5, 12, 2):
            _px(s, "px.concrete.2", x0 + 4, y0 + k, 8, 1)
        _px(s, "px.concrete.0", x0 + 3, y0 + 12, 10, 1)
    elif char == "b":
        for _ in range(5):
            x, y = x0 + rng.randrange(2, 14), y0 + rng.randrange(2, 14)
            _px(s, rng.choice(("px.bot.3", "px.wall.3", "px.wood.1")), x, y, rng.choice((1, 2)), 1)
            _px(s, "px.concrete.0", x, y + 1)


# Walls -------------------------------------------------------------------------------------


def _rim_top(s: pygame.Surface, x0: int, y0: int) -> None:
    _px(s, "px.wall.4", x0, y0, TILE, 1)
    _px(s, "px.wall.3", x0, y0 + 1, TILE, 2)
    _px(s, "px.outline", x0, y0 + 3, TILE, 1)


def _rim_side(s: pygame.Surface, x0: int, y0: int, east: bool, h: int = TILE) -> None:
    x = x0 + TILE - 4 if east else x0
    _px(s, "px.wall.3", x, y0, 4, h)
    _px(s, "px.wall.4", x + (3 if east else 0), y0, 1, h)
    _px(s, "px.outline", x if east else x + 3, y0, 1, h)


def _face_upper(s: pygame.Surface, x0: int, y0: int, tx: int) -> None:
    """Upper wall face below the rim: riveted steel panels."""
    _px(s, "px.wall.1", x0, y0, TILE, TILE - 4)
    _px(s, "px.wall.0", x0, y0, TILE, 1)
    seam = 0 if tx % 2 == 0 else 8
    _px(s, "px.wall.0", x0 + seam, y0, 1, TILE - 4)
    _px(s, "px.wall.2", x0 + seam + 1, y0, 1, TILE - 4)
    for x in range(x0 + 3, x0 + TILE, 8):
        _px(s, "px.wall.3", x, y0 + 3)
        _px(s, "px.wall.3", x, y0 + 9)


def _face_lower(s: pygame.Surface, x0: int, y0: int, h: int = TILE) -> None:
    """Lower wall face: trim rail, panels and a hazard-striped kick plate."""
    _px(s, "px.wall.1", x0, y0, TILE, h)
    _px(s, "px.wall.3", x0, y0, TILE, 1)
    _px(s, "px.wall.2", x0, y0 + 1, TILE, 1)
    _px(s, "px.wall.0", x0, y0 + 2, TILE, 1)
    for x in range(x0 + 4, x0 + TILE, 8):
        _px(s, "px.wall.0", x, y0 + 3, 1, h - 8)
    for x in range(TILE):
        for y in range(h - 5, h - 1):
            token = "px.hazard.1" if ((x + y) // 2) % 2 == 0 else "px.hazard.0"
            _px(s, token, x0 + x, y0 + y)
    _px(s, "px.outline", x0, y0 + h - 1, TILE, 1)


def _fixture(
    s: pygame.Surface, art: RoomArt, char: str, x0: int, y0: int, room: Room, tx: int, ty: int
) -> None:
    """Something mounted on a wall face. (x0, y0) is the top of the lower face cell."""
    if char == "P":
        _px(s, "px.outline", x0 + 1, y0 + 2, 14, 12)
        _px(s, "px.bot.2", x0 + 2, y0 + 3, 12, 10)
        _px(s, "px.bot.3", x0 + 2, y0 + 3, 12, 1)
        for i in range(3):
            _px(s, "px.bot.0", x0 + 3 + i * 3, y0 + 5, 2, 4)
            _px(s, "px.dial.0", x0 + 3 + i * 3, y0 + (5 if (tx + i) % 2 else 7), 2, 2)
        _px(s, "px.bot.1", x0 + 12, y0 + 5, 1, 6)
        for i, token in enumerate(("power.blink", "px.led.amber")):
            art.leds.append(((x0 + 4 + i * 4, y0 + 11), token, (tx * 3 + i * 5) % 7))
    elif char == "S":
        cx = x0 + 8
        for row in range(9):
            _px(s, "px.outline", cx - row // 2 - 1, y0 + 2 + row, row + 3, 1)
        for row in range(1, 8):
            _px(s, "px.hazard.1", cx - row // 2, y0 + 2 + row, row + 1, 1)
        for x, y in ((8, 5), (7, 6), (8, 7), (9, 7), (8, 8), (7, 9)):
            _px(s, "px.outline", x0 + x, y0 + y)
    elif char == "L":
        _px(s, "px.outline", x0 + 3, y0 + 2, 10, 7)
        _px(s, "px.bot.1", x0 + 4, y0 + 3, 8, 5)
        _px(s, "px.lamp", x0 + 5, y0 + 4, 6, 3)
        _px(s, "px.lamp.light", x0 + 6, y0 + 4, 3, 1)
        art.lamps.append((x0 + 8, y0 + 6))
        _px(art.light, "px.lamp", x0 + 5, y0 + 4, 6, 3)
    elif char == "V":
        _px(s, "px.outline", x0 + 2, y0 + 3, 12, 9)
        _px(s, "px.wall.3", x0 + 3, y0 + 4, 10, 7)
        for y in range(5, 11, 2):
            _px(s, "px.void", x0 + 4, y0 + y, 8, 1)
    elif char == "M":
        cx, cy = x0 + 8, y0 + 7
        pygame.draw.circle(s, rgb("px.outline"), (cx, cy), 6)
        pygame.draw.circle(s, rgb("px.wall.3"), (cx, cy), 5)
        pygame.draw.circle(s, rgb("px.dial.1"), (cx, cy), 4)
        _px(s, "hostile.danger", cx + 2, cy - 3, 2, 1)
        for i in range(4):
            _px(s, "px.outline", cx - i // 2, cy - i, 1, 1)
        _px(s, "px.outline", cx, cy, 1, 1)
    elif char == "p":
        for py in (4, 9):
            _px(s, "px.bot.3", x0, y0 + py, TILE, 1)
            _px(s, "px.bot.2", x0, y0 + py + 1, TILE, 1)
            _px(s, "px.bot.0", x0, y0 + py + 2, TILE, 1)
        if room.decor[ty][tx - 1] != "p":
            for py in (3, 8):
                _px(s, "px.outline", x0, y0 + py, 3, 5)
                _px(s, "px.wall.4", x0 + 1, y0 + py + 1, 1, 3)


# Props -------------------------------------------------------------------------------------


@cache
def transformer() -> pygame.Surface:
    """Power transformer: radiator fins, three ceramic bushings with cables, placard, gauge.
    32 x 50, footprint is the bottom 32 x 32."""
    w, h = 32, 50
    s = pygame.Surface((w, h), pygame.SRCALPHA)
    for i, x in enumerate((7, 15, 23)):
        _px(s, "px.bot.0", x, 0, 2, 3)
        for k in range(4):
            y = 3 + k * 3
            _px(s, "px.ceramic.1", x - 1, y, 4, 2)
            _px(s, "px.ceramic.2", x - 1, y, 3, 1)
            _px(s, "px.ceramic.0", x - 1, y + 2, 4, 1)
        _px(s, "px.bot.3", x, 0, 2, 1)
        _px(s, "px.bot.0", x + 2, 1 + i % 2, 3, 1)
    _px(s, "px.wall.3", 3, 15, w - 6, 8)
    _px(s, "px.wall.4", 3, 15, w - 6, 1)
    _px(s, "px.wall.2", 3, 22, w - 6, 1)
    _px(s, "px.wall.2", 4, 23, w - 8, 22)
    _px(s, "px.wall.3", 4, 23, 1, 22)
    _px(s, "px.wall.1", w - 5, 23, 1, 22)
    for x in (0, 2, w - 3, w - 1):
        _px(s, "px.wall.3" if x in (0, w - 3) else "px.wall.1", x, 24, 1, 20)
    _px(s, "px.dial.0", 8, 27, 8, 5)
    for y in (28, 30):
        _px(s, "px.bot.1", 9, y, 6, 1)
    for row in range(6):
        _px(s, "px.hazard.1", 22 - row // 2, 26 + row, row + 1, 1)
    _px(s, "px.outline", 22, 28, 1, 2)
    pygame.draw.circle(s, rgb("px.dial.1"), (12, 39), 3)
    _px(s, "hostile.danger", 13, 37, 1, 1)
    _px(s, "px.outline", 12, 39, 1, 1)
    _px(s, "px.bot.1", 2, 45, w - 4, 4)
    for x in (4, 14, 24):
        _px(s, "px.bot.3", x, 46, 2, 1)
    add_outline(s, "px.outline")
    return s


@cache
def cabinet() -> pygame.Surface:
    """Switchgear cabinet: louvers, door, handle, status LEDs. 16 x 30."""
    w, h = 16, 30
    s = pygame.Surface((w, h), pygame.SRCALPHA)
    _px(s, "px.bot.3", 1, 1, w - 2, 5)
    _px(s, "px.dial.0", 1, 1, w - 2, 1)
    _px(s, "px.bot.2", 1, 6, w - 2, h - 8)
    _px(s, "px.bot.1", 1, 6, w - 2, 1)
    for y in range(9, 16, 2):
        _px(s, "px.bot.0", 3, y, w - 6, 1)
    _px(s, "px.bot.1", 7, 17, 1, 10)
    _px(s, "px.dial.0", 9, 20, 1, 3)
    _px(s, "power.blink", 3, 18, 1, 1)
    _px(s, "px.led.amber", 5, 18, 1, 1)
    _px(s, "px.bot.0", 1, h - 2, w - 2, 1)
    add_outline(s, "px.outline")
    return s


@cache
def cable_reel() -> pygame.Surface:
    """Wooden cable drum seen end-on, cable wound on top. 18 x 20."""
    w, h = 18, 20
    s = pygame.Surface((w, h), pygame.SRCALPHA)
    pygame.draw.circle(s, rgb("px.wood.0"), (9, 11), 8)
    pygame.draw.circle(s, rgb("px.wood.1"), (9, 11), 7)
    pygame.draw.circle(s, rgb("px.wood.2"), (9, 11), 7, 1)
    for dx, dy in ((0, -5), (0, 5), (-5, 0), (5, 0)):
        _px(s, "px.wood.0", 9 + dx // 2, 11 + dy // 2, 1, 1)
    pygame.draw.circle(s, rgb("px.bot.2"), (9, 11), 2)
    _px(s, "px.bot.0", 2, 2, 14, 3)
    _px(s, "px.bot.2", 2, 2, 14, 1)
    _px(s, "px.bot.0", 15, 4, 2, 3)
    add_outline(s, "px.outline")
    return s


@cache
def insulator() -> pygame.Surface:
    """Ceramic insulator stack on a steel base. 14 x 28."""
    w, h = 14, 28
    s = pygame.Surface((w, h), pygame.SRCALPHA)
    _px(s, "px.wall.2", 1, h - 6, w - 2, 5)
    _px(s, "px.wall.3", 1, h - 6, w - 2, 1)
    _px(s, "px.bot.3", 6, 0, 2, 2)
    for i, y in enumerate(range(2, h - 7, 3)):
        inset = 2 if i % 2 else 1
        _px(s, "px.ceramic.1", inset, y, w - 2 * inset, 2)
        _px(s, "px.ceramic.2", inset + 1, y, w - 2 * inset - 3, 1)
        _px(s, "px.ceramic.0", inset, y + 2, w - 2 * inset, 1)
    add_outline(s, "px.outline")
    return s


@cache
def crate() -> pygame.Surface:
    w, h = 16, 18
    s = pygame.Surface((w, h), pygame.SRCALPHA)
    _px(s, "px.wall.3", 1, 1, w - 2, 4)
    _px(s, "px.wall.4", 1, 1, w - 2, 1)
    _px(s, "px.wall.2", 1, 5, w - 2, h - 6)
    _px(s, "px.wall.3", 1, 5, 2, h - 6)
    _px(s, "px.wall.3", w - 3, 5, 2, h - 6)
    for i in range(w - 6):
        _px(s, "px.wall.1", 3 + i, 6 + (i * (h - 8)) // (w - 6), 1, 2)
    _px(s, "px.hazard.1", 6, 12, 4, 2)
    add_outline(s, "px.outline")
    return s


@cache
def drum() -> pygame.Surface:
    w, h = 12, 18
    s = pygame.Surface((w, h), pygame.SRCALPHA)
    _px(s, "px.bot.3", 1, 1, w - 2, 3)
    _px(s, "px.bot.1", 3, 2, w - 6, 1)
    _px(s, "px.bot.2", 1, 4, w - 2, h - 5)
    _px(s, "px.bot.3", 2, 4, 1, h - 5)
    for y in (7, 13):
        _px(s, "px.bot.1", 1, y, w - 2, 1)
    _px(s, "px.hazard.1", 1, 9, w - 2, 2)
    add_outline(s, "px.outline")
    return s


_PROP_IMAGES = {
    "T": transformer,
    "C": cabinet,
    "R": cable_reel,
    "I": insulator,
    "K": crate,
    "B": drum,
}


@dataclass(frozen=True)
class Prop:
    kind: str
    tile_x: int
    tile_y: int

    @property
    def footprint(self) -> tuple[int, int, int, int]:
        size = footprint_tiles(self.kind)
        return (self.tile_x * TILE, self.tile_y * TILE, size * TILE, size * TILE)

    @property
    def base_y(self) -> int:
        _, y, _, h = self.footprint
        return y + h

    def image(self) -> pygame.Surface:
        return _PROP_IMAGES[self.kind]()

    def draw(self, target: pygame.Surface, camera: Point) -> None:
        image = self.image()
        x, y, w, h = self.footprint
        left = x + (w - image.get_width()) // 2
        target.blit(image, (left - camera[0], y + h - image.get_height() - camera[1]))


def _shadow(s: pygame.Surface, x: int, y: int, w: int, h: int, alpha: int = 110) -> None:
    shade = pygame.Surface((w, h), pygame.SRCALPHA)
    pygame.draw.ellipse(shade, rgba("px.outline", alpha), (0, 0, w, h))
    s.blit(shade, (x, y))


# Room --------------------------------------------------------------------------------------


@cache
def stencil_font() -> pygame.font.Font:
    from overload.paths import FONTS

    return pygame.font.Font(FONTS / "silkscreen" / "Silkscreen-Regular.ttf", 8)


def forget_fonts() -> None:
    stencil_font.cache_clear()


def render_room(room: Room) -> RoomArt:
    w, h = room.size
    background = pygame.Surface((w, h))
    background.fill(rgb("px.void"))
    light = pygame.Surface((w, h))
    light.fill(rgb("fx.none"))
    art = RoomArt(background, light)
    rows, decor = room.terrain, room.decor

    def same(x: int, y: int, char: str) -> bool:
        return room.at(x, y) == char

    # Floors.
    for ty, row in enumerate(rows):
        for tx, char in enumerate(row):
            if char == "#":
                continue
            x0, y0 = tx * TILE, ty * TILE
            if char in "=g":
                open_sides = {
                    "N": not same(tx, ty - 1, char),
                    "S": not same(tx, ty + 1, char),
                    "W": not same(tx - 1, ty, char),
                    "E": not same(tx + 1, ty, char),
                }
                if char == "=":
                    _plate(background, x0, y0, tx, ty, open_sides)
                else:
                    horizontal = same(tx - 1, ty, "g") or same(tx + 1, ty, "g")
                    _trench(background, x0, y0, open_sides, horizontal)
            elif char == "h":
                open_sides = {
                    "N": not same(tx, ty - 1, "h"),
                    "S": not same(tx, ty + 1, "h"),
                    "W": not same(tx - 1, ty, "h"),
                    "E": not same(tx + 1, ty, "h"),
                }
                _hazard(background, x0, y0, tx, ty, open_sides)
            elif char in "-|+":
                _conduit(background, light, x0, y0, tx, ty, char)
            elif char == ",":
                _concrete(background, x0, y0, tx, ty)
            else:
                _floor_tile(background, x0, y0, tx, ty)
            if decor[ty][tx] in "oxcdb":
                _decal(background, decor[ty][tx], x0, y0, tx, ty)
            elif decor[ty][tx] == "u":
                art.ceiling.append((x0 + 8, y0 + 8))

    # Walls.
    def front(x: int, y: int) -> bool:
        return room.is_wall(x, y) and not room.is_wall(x, y + 1)

    def face(x: int, y: int) -> bool:
        return front(x, y) or (room.is_wall(x, y) and front(x, y + 1))

    for ty, row in enumerate(rows):
        for tx, char in enumerate(row):
            if char != "#":
                continue
            x0, y0 = tx * TILE, ty * TILE
            floor_above = not room.is_wall(tx, ty - 1)
            if front(tx, ty):
                if floor_above:
                    _rim_top(background, x0, y0)
                    _face_lower(background, x0, y0 + 4, TILE - 4)
                else:
                    _face_lower(background, x0, y0)
                shade = pygame.Surface((TILE, 5), pygame.SRCALPHA)
                for k, alpha in enumerate((150, 110, 70, 40, 15)):
                    shade.fill(rgba("px.outline", alpha), (0, k, TILE, 1))
                background.blit(shade, (x0, y0 + TILE))
            elif face(tx, ty):
                _rim_top(background, x0, y0)
                _face_upper(background, x0, y0 + 4, tx)
            else:
                if floor_above:
                    _rim_top(background, x0, y0)
                    _px(background, "px.wall.0", x0, y0 + 4, TILE, TILE - 4)
                    _px(background, "px.outline", x0, y0 + TILE - 1, TILE, 1)
                for east, nx in ((True, tx + 1), (False, tx - 1)):
                    neighbor_open = not room.is_wall(nx, ty) or face(nx, ty)
                    if neighbor_open:
                        _rim_side(background, x0, y0, east)
                for dx, dy in ((1, 1), (-1, 1), (1, -1), (-1, -1)):
                    if (
                        not room.is_wall(tx + dx, ty + dy)
                        and room.is_wall(tx + dx, ty)
                        and room.is_wall(tx, ty + dy)
                    ):
                        cx = x0 + (TILE - 4 if dx > 0 else 0)
                        cy = y0 + (TILE - 4 if dy > 0 else 0)
                        _px(background, "px.wall.3", cx, cy, 4, 4)
                        _px(
                            background,
                            "px.outline",
                            cx + (0 if dx > 0 else 3),
                            cy + (0 if dy > 0 else 3),
                            1,
                            1,
                        )
            # Side edges of faces get a dark line so wall blocks read as solid.
            if face(tx, ty):
                if not room.is_wall(tx - 1, ty):
                    _px(background, "px.outline", x0, y0, 1, TILE)
                if not room.is_wall(tx + 1, ty):
                    _px(background, "px.outline", x0 + TILE - 1, y0, 1, TILE)

    # Wall fixtures sit on the lower face cell (or the upper one when the sign is placed there).
    for ty, row in enumerate(decor):
        for tx, char in enumerate(row):
            if char in "PSLVMp" and face(tx, ty):
                y0 = ty * TILE + (4 if not front(tx, ty) or not room.is_wall(tx, ty - 1) else 0)
                _fixture(background, art, char, tx * TILE, y0, room, tx, ty)

    # Stenciled signage: wall words sit on the upper face, floor words are worn paint.
    for tx, ty, words, place in room.labels:
        token = "px.wall.3" if place == "wall" else "px.hazard.1"
        text = stencil_font().render(words, False, rgb(token))
        image = pygame.Surface(text.get_size(), pygame.SRCALPHA)
        image.blit(text, (0, 0))
        x, y = tx * TILE + 2, ty * TILE + (7 if place == "wall" else 4)
        if place == "floor":
            rng = _rng(tx, ty, 21)
            for _ in range(image.get_width() // 2):
                image.set_at(
                    (rng.randrange(image.get_width()), rng.randrange(image.get_height())),
                    rgba("fx.none", 0),
                )
        background.blit(image, (x, y))

    # Props, with baked contact shadows.
    seen: set[tuple[int, int]] = set()
    for ty, row in enumerate(decor):
        for tx, char in enumerate(row):
            if char in _PROP_IMAGES and (tx, ty) not in seen:
                prop = Prop(char, tx, ty)
                art.props.append(prop)
                x, y, pw, ph = prop.footprint
                _shadow(background, x - 1, y + ph - 7, pw + 2, 9)
                if char == "T":
                    seen.update({(tx, ty), (tx + 1, ty), (tx, ty + 1), (tx + 1, ty + 1)})
    return art
