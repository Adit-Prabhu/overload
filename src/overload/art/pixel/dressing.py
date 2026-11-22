"""Set dressing (Adit, Nov 17: "make the maps better, more detailed"). Cosmetic layers drawn
over the tiles once a room is built, and the spots where the view animates ambience.

Every choice is seeded by its tile, so the floor looks the same in every run, and nothing
here touches the room data the simulation reads (terrain, decor, solidity).

- Contact shadows: floor darkens where it meets a wall, so walls stand on the floor.
- Wear on every floor: scuffs, bolts and the odd replaced plate.
- Sector stories, so each part of the station reads at a glance:
  1. Switchyard: painted walk lines along the walls, oil drips, dropped bolts, cable trays
     on the upper walls.
  2. Cooling plant: puddles with a glint, rust streaks under the walls, drains, a run of
     pipes with valve wheels along the upper walls, steam from the vents.
  3. Grid core: scorch marks, cracks leaking conduit light, a lit conduit strip along the
     upper walls, damaged panels that spit sparks.
- Wall faces without a fixture get junction boxes, numbered plates and fans now and then.
"""

from __future__ import annotations

import random
from collections.abc import Callable
from dataclasses import dataclass
from functools import cache

import pygame

from overload.art.palette import rgb, rgba
from overload.rooms import TILE, Room

Point = tuple[int, int]
SectorAt = Callable[[int, int], int]


@dataclass(frozen=True)
class Emitter:
    """A spot the view animates: "steam" (a vent breathing), "sparks" (a damaged panel),
    "drip" (a puddle catching drops) or "flicker" (a failing lamp)."""

    kind: str
    x: int
    y: int
    phase: int


def _rng(x: int, y: int, salt: int) -> random.Random:
    return random.Random(x * 7919 + y * 104729 + salt * 15485863)


def _px(s: pygame.Surface, token: str, x: int, y: int, w: int = 1, h: int = 1) -> None:
    s.fill(rgb(token), (x, y, w, h))


@cache
def _patch(w: int, h: int, alpha: int) -> pygame.Surface:
    patch = pygame.Surface((w, h), pygame.SRCALPHA)
    patch.fill(rgba("px.outline", alpha))
    return patch


def _shade(s: pygame.Surface, x: int, y: int, w: int, h: int, alpha: int) -> None:
    s.blit(_patch(w, h, alpha), (x, y))


def dress(
    background: pygame.Surface,
    light: pygame.Surface,
    room: Room,
    sector_at: SectorAt,
    lamps: list[Point],
    props: set[Point],
    fixtures: set[Point],
    fuse_rooms: tuple[tuple[int, int, int, int], ...] = (),
) -> list[Emitter]:
    """Draw the dressing onto the room's background and light layers. `props` are tiles
    under props and `fixtures` wall tiles that already carry one. Returns the emitters."""
    emitters: list[Emitter] = []
    rows = room.terrain
    height, width = len(rows), len(rows[0])

    def wall(x: int, y: int) -> bool:
        return not (0 <= x < width and 0 <= y < height) or rows[y][x] == "#"

    def front(x: int, y: int) -> bool:
        return wall(x, y) and not wall(x, y + 1)

    def upper(x: int, y: int) -> bool:
        return wall(x, y) and front(x, y + 1)

    def clear(x: int, y: int) -> bool:
        """No wall among the eight neighbors: room for something wider than a tile."""
        return not any(wall(x + dx, y + dy) for dx in (-1, 0, 1) for dy in (-1, 0, 1))

    # Wall stencils (about 6 px a letter) keep their wall face bare.
    lettered = {
        (tx + k, ty)
        for tx, ty, words, place in room.labels
        if place == "wall"
        for k in range(len(words) * 6 // TILE + 2)
    }
    # Tiles covered by each Fuse Box charging bay stay free of stains, puddles and drips.
    blocked = props | {
        (rx + dx, ry + dy)
        for rx, ry, _, _ in fuse_rooms
        for dx in range(6, 9)
        for dy in range(2, 6)
    }

    for ty in range(height):
        for tx in range(width):
            x0, y0 = tx * TILE, ty * TILE
            sector = sector_at(tx, ty)
            if not wall(tx, ty):
                _grime(background, x0, y0, tx, ty)
                if room.decor[ty][tx] == "." and (tx, ty) not in blocked:
                    _floor_story(background, light, emitters, tx, ty, x0, y0, sector, clear(tx, ty))
                _contact_shadow(background, x0, y0, wall, tx, ty)
                if sector == 1:
                    _walk_line(background, x0, y0, wall, tx, ty)
            elif upper(tx, ty) and (tx, ty) not in fixtures and (tx, ty) not in lettered:
                _upper_run(background, light, x0, y0 + 4, tx, sector)
            elif upper(tx, ty):
                continue
            elif front(tx, ty) and (tx, ty) not in fixtures and room.decor[ty][tx] == ".":
                top = y0 + (4 if not wall(tx, ty - 1) else 0)
                _lower_detail(background, light, emitters, x0, top, tx, ty, sector)
    for i, (x, y) in enumerate(lamps):
        if _rng(x, y, 41).random() < 0.34:  # some lamps are failing
            emitters.append(Emitter("flicker", x, y, i))
    for ty in range(height):
        for tx in range(width):
            if room.decor[ty][tx] == "V" and sector_at(tx, ty) == 2:
                emitters.append(Emitter("steam", tx * TILE + 8, ty * TILE + 12, tx + ty))
    for rect in fuse_rooms:
        _fuse_pad(background, light, rect)
    return emitters


def fuse_pad_sockets(rect: tuple[int, int, int, int]) -> tuple[tuple[int, int], tuple[int, int]]:
    """World pixel centers of a Fuse Box room's yellow (left) and blue (right) charging sockets."""
    rx, ry, _, _ = rect
    cx = (rx + 7) * TILE + 8
    mid_y = (ry + 4) * TILE + 14
    return ((cx - 9, mid_y), (cx + 9, mid_y))


def _fuse_pad(s: pygame.Surface, light: pygame.Surface, rect: tuple[int, int, int, int]) -> None:
    """Cosmetic recessed charging and fusion bay in each Fuse Box safe room, tied by twin
    floor cables to the north wall monitor. Floor-level so the Surge walks right across it."""
    rx, ry, _, _ = rect
    left_socket, right_socket = fuse_pad_sockets(rect)
    cx = (left_socket[0] + right_socket[0]) // 2
    mid_y = left_socket[1]
    py = mid_y - 12
    wall_bottom = (ry + 2) * TILE
    # Twin insulated conduit cables from the wall monitor down to the charging bay.
    for dx in (-4, 3):
        _px(s, "px.outline", cx + dx - 1, wall_bottom, 3, py - wall_bottom)
        _px(s, "px.conduit.1", cx + dx, wall_bottom, 1, py - wall_bottom)
        _px(light, "px.conduit.1", cx + dx, wall_bottom, 1, py - wall_bottom)
    # Recessed steel bay (36 x 24 px) with beveled rim and corner bolts.
    x0, y0, w, h = cx - 18, py, 36, 24
    _px(s, "px.outline", x0, y0, w, h)
    _px(s, "px.wall.2", x0 + 1, y0 + 1, w - 2, h - 2)
    _px(s, "px.wall.4", x0 + 1, y0 + 1, w - 2, 1)
    _px(s, "px.floor.0", x0 + 3, y0 + 3, w - 6, h - 6)
    for gy in range(y0 + 5, y0 + h - 4, 3):
        _px(s, "px.floor.1", x0 + 4, gy, w - 8, 1)
    for bx, by in (
        (x0 + 2, y0 + 2),
        (x0 + w - 4, y0 + 2),
        (x0 + 2, y0 + h - 4),
        (x0 + w - 4, y0 + h - 4),
    ):
        _px(s, "px.hazard.1", bx, by, 2, 2)
    # Twin glowing fusion sockets linked by a live bus bar.
    _px(s, "px.conduit.1", cx - 5, mid_y - 1, 10, 2)
    _px(light, "px.lamp.light", cx - 4, mid_y - 1, 8, 2)
    for (sx, sy), token, glow_token in (
        (left_socket, "power.spark", "px.spark.light"),
        (right_socket, "power.blink", "px.blink.light"),
    ):
        pygame.draw.circle(s, rgb("px.outline"), (sx, sy), 6)
        pygame.draw.circle(s, rgb(token), (sx, sy), 5, 1)
        pygame.draw.circle(s, rgb(glow_token), (sx, sy), 2)
        pygame.draw.circle(light, rgb(token), (sx, sy), 5, 1)
        pygame.draw.circle(light, rgb(glow_token), (sx, sy), 2)
    _px(s, "px.lamp.light", cx - 1, mid_y - 1, 2, 2)
    _px(light, "px.lamp.light", cx - 1, mid_y - 1, 2, 2)


def _noise(x: int, y: int) -> float:
    return _rng(x, y, 53).random()


def _grime(s, x0: int, y0: int, tx: int, ty: int) -> None:
    """Low-frequency grime, so the floor does not repeat tile by tile: a value noise over
    blocks of four tiles, blended per tile."""
    gx, gy = tx / 4, ty / 4
    ix, iy = int(gx), int(gy)
    fx, fy = gx - ix, gy - iy
    top = _noise(ix, iy) * (1 - fx) + _noise(ix + 1, iy) * fx
    bottom = _noise(ix, iy + 1) * (1 - fx) + _noise(ix + 1, iy + 1) * fx
    value = top * (1 - fy) + bottom * fy
    alpha = round(max(0.0, value - 0.35) * 110)
    if alpha:
        _shade(s, x0, y0, TILE, TILE, alpha)


def _contact_shadow(s, x0: int, y0: int, wall, tx: int, ty: int) -> None:
    """Darken the floor a few pixels out from walls to the west, east and south (the north
    wall already casts its face shadow)."""
    for alpha, k in ((90, 0), (55, 1), (25, 2)):
        if wall(tx - 1, ty):
            _shade(s, x0 + k, y0, 1, TILE, alpha)
        if wall(tx + 1, ty):
            _shade(s, x0 + TILE - 1 - k, y0, 1, TILE, alpha)
        if wall(tx, ty + 1):
            _shade(s, x0, y0 + TILE - 1 - k, TILE, 1, alpha)


def _walk_line(s, x0: int, y0: int, wall, tx: int, ty: int) -> None:
    """Switchyard: a worn painted line three pixels in from the walls."""
    rng = _rng(tx, ty, 43)
    for side, rect in (
        ("W", (x0 + 3, y0, 1, TILE)),
        ("E", (x0 + TILE - 4, y0, 1, TILE)),
        ("S", (x0, y0 + TILE - 4, TILE, 1)),
    ):
        neighbor = {"W": (tx - 1, ty), "E": (tx + 1, ty), "S": (tx, ty + 1)}[side]
        if not wall(*neighbor):
            continue
        x, y, w, h = rect
        for k in range(max(w, h)):
            if rng.random() < 0.8:
                _px(
                    s,
                    "px.hazard.0" if rng.random() < 0.3 else "px.hazard.1",
                    x + (k if w > 1 else 0),
                    y + (k if h > 1 else 0),
                )


def _floor_story(
    s, light, emitters, tx: int, ty: int, x0: int, y0: int, sector: int, clear: bool
) -> None:
    """Wear, and the sector's stories. Stains and wet patches spread past their tile, so
    they only go where no wall is near (`clear`)."""
    rng = _rng(tx, ty, 37)
    roll = rng.random()
    # Wear everywhere: a scuff, a dropped bolt.
    if rng.random() < 0.35:
        x, y = x0 + rng.randrange(2, 11), y0 + rng.randrange(3, 13)
        _px(s, "px.floor.3", x, y, rng.randrange(2, 5), 1)
    if rng.random() < 0.08:
        x, y = x0 + rng.randrange(3, 12), y0 + rng.randrange(3, 12)
        _px(s, "px.outline", x, y + 1, 2, 1)
        _px(s, "px.bot.3", x, y, 2, 1)
    if sector == 1 and roll < 0.06 and clear:  # a soft oil stain
        cx, cy = x0 + rng.randrange(5, 11), y0 + rng.randrange(5, 11)
        stain = pygame.Surface((TILE + 4, TILE), pygame.SRCALPHA)
        for _ in range(3):
            r = rng.randint(2, 4)
            pygame.draw.circle(stain, rgba("px.outline", 70), (8 + rng.randint(-3, 3), 8), r)
        s.blit(stain, (cx - 10, cy - 8))
        _px(s, "px.floor.3", cx - 1, cy - 1)  # a sheen
    elif sector == 2 and roll < 0.045 and clear:  # a wet patch with a glint, now and then a drip
        cx, cy = x0 + 8, y0 + rng.randrange(7, 10)
        w, h = rng.randrange(22, 32), rng.randrange(9, 13)
        rect = pygame.Rect(0, 0, w, h)
        rect.center = (cx, cy)
        wet = pygame.Surface(rect.size, pygame.SRCALPHA)
        pygame.draw.ellipse(wet, rgba("px.outline", 120), wet.get_rect())
        # Dark wet steel, kept off the Cooled robots' teal shells, and not emissive.
        pygame.draw.ellipse(wet, rgba("px.wall.1", 150), wet.get_rect().inflate(-6, -4))
        s.blit(wet, rect)
        _px(s, "px.wall.3", rect.left + 4, rect.top + 2, w // 3, 1)
        _px(s, "px.ceramic.2", rect.left + 5, rect.top + 3)
        if rng.random() < 0.6:
            emitters.append(Emitter("drip", cx, cy, tx * 3 + ty))
    elif sector == 2 and roll < 0.07:  # a floor drain
        _px(s, "px.outline", x0 + 4, y0 + 5, 8, 6)
        _px(s, "px.concrete.3", x0 + 5, y0 + 6, 6, 4)
        for k in range(6, 10, 2):
            _px(s, "px.void", x0 + 5, y0 + k, 6, 1)
    elif sector == 3 and roll < 0.08:  # a scorch mark
        cx, cy = x0 + 8, y0 + 8
        for _ in range(30):
            dx, dy = rng.randint(-6, 6), rng.randint(-4, 4)
            if dx * dx / 36 + dy * dy / 16 <= 1:
                _px(
                    s,
                    "px.outline" if abs(dx) < 4 and abs(dy) < 3 else "px.tile.0",
                    cx + dx,
                    cy + dy,
                )
    elif sector == 3 and roll < 0.15:  # a crack leaking conduit light
        x, y = x0 + rng.randrange(2, 6), y0 + rng.randrange(4, 12)
        for _ in range(rng.randint(6, 10)):
            _px(s, "px.outline", x, y + 1)
            _px(s, "px.conduit.1", x, y)
            _px(light, "px.conduit.1", x, y)
            x += 1
            y = max(y0 + 2, min(y0 + 13, y + rng.choice((-1, 0, 0, 1))))


def _upper_run(s, light, x0: int, y0: int, tx: int, sector: int) -> None:
    """A continuous run along the upper wall faces: cable trays (switchyard), pipes with
    valve wheels (cooling plant), a lit conduit strip (grid core)."""
    if sector == 1:
        _px(s, "px.bot.0", x0, y0 + 6, TILE, 3)
        for i, token in enumerate(("px.wood.1", "px.conduit.1", "px.bot.3")):
            _px(s, token, x0, y0 + 6 + i, TILE, 1)
        for k in range(0, TILE, 8):
            _px(s, "px.wall.3", x0 + k + 3, y0 + 5, 2, 5)
    elif sector == 2:
        for py, (dark, mid, top) in (
            (3, ("px.bot.0", "px.wall.2", "px.wall.4")),
            (8, ("px.bot.0", "px.ceramic.0", "px.ceramic.1")),
        ):
            _px(s, dark, x0, y0 + py, TILE, 3)
            _px(s, mid, x0, y0 + py, TILE, 2)
            _px(s, top, x0, y0 + py, TILE, 1)
        if tx % 6 == 2:  # a valve wheel
            pygame.draw.circle(s, rgb("px.outline"), (x0 + 8, y0 + 4), 3)
            pygame.draw.circle(s, rgb("px.wall.3"), (x0 + 8, y0 + 4), 3, 1)
            _px(s, "px.wall.4", x0 + 7, y0 + 1, 2, 1)
        if tx % 4 == 0:  # a flange
            _px(s, "px.wall.3", x0, y0 + 2, 2, 5)
            _px(s, "px.ceramic.1", x0, y0 + 7, 2, 5)
    elif sector == 3:
        _px(s, "px.outline", x0, y0 + 5, TILE, 3)
        _px(s, "px.conduit.1", x0, y0 + 6, TILE, 1)
        _px(light, "px.conduit.1", x0, y0 + 6, TILE, 1)
        if tx % 3 == 0:
            _px(s, "px.wall.3", x0 + 2, y0 + 4, 2, 5)


def _lower_detail(s, light, emitters, x0: int, y0: int, tx: int, ty: int, sector: int) -> None:
    """A small fixture on a bare lower wall face, about one tile in three."""
    rng = _rng(tx, ty, 47)
    roll = rng.random()
    if roll < 0.12:  # a junction box with a status light
        _px(s, "px.outline", x0 + 4, y0 + 2, 8, 8)
        _px(s, "px.wall.3", x0 + 5, y0 + 3, 6, 6)
        _px(s, "px.wall.4", x0 + 5, y0 + 3, 6, 1)
        _px(s, "px.led.amber", x0 + 9, y0 + 5)
        _px(light, "px.led.amber", x0 + 9, y0 + 5)
        _px(s, "px.bot.0", x0 + 7, y0 + 10, 2, 2)  # its conduit down to the floor
    elif roll < 0.2:  # a numbered plate
        _px(s, "px.outline", x0 + 3, y0 + 3, 10, 6)
        _px(s, "px.paint", x0 + 4, y0 + 4, 8, 4)
        for k in range(3):
            _px(s, "px.outline", x0 + 5 + k * 2, y0 + 5, 1, 2)
    elif roll < 0.28 and sector == 2:  # rust running down from a seam
        x = x0 + rng.randrange(2, 13)
        for y in range(y0 + 1, y0 + rng.randrange(6, 10)):
            _px(s, "px.wood.1" if y % 3 else "px.wood.0", x, y)
    elif roll < 0.3 and sector == 3:  # a damaged panel that spits sparks
        _px(s, "px.outline", x0 + 3, y0 + 2, 10, 8)
        _px(s, "px.bot.2", x0 + 4, y0 + 3, 8, 6)
        for x, y in ((6, 4), (7, 5), (8, 5), (9, 6), (8, 7)):
            _px(s, "px.outline", x0 + x, y0 + y)
        emitters.append(Emitter("sparks", x0 + 8, y0 + 6, tx * 5 + ty))
    elif roll < 0.36:  # a small fan behind a grille
        pygame.draw.circle(s, rgb("px.outline"), (x0 + 8, y0 + 6), 5)
        pygame.draw.circle(s, rgb("px.wall.2"), (x0 + 8, y0 + 6), 4)
        for dx, dy in ((-2, -2), (2, 2), (-2, 2), (2, -2)):
            _px(s, "px.wall.0", x0 + 8 + dx, y0 + 6 + dy)
        _px(s, "px.wall.4", x0 + 8, y0 + 6)
