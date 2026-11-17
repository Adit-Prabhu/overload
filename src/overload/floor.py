"""The substation floor (overhaul, Nov 17): one hand-built map of rooms joined by corridors,
shared by the art (what to draw) and the simulation (what is solid, where rooms and doors are).

Pure data, no pygame. The floor is identical in every run and in both comparison conditions
(the G1 GDD excludes procedural maps). It is laid out on a grid of cells, one room per cell,
three sectors snaking down the grid:

    sector 1   entry  ->  combat  ->  combat  ->  chamber  ->  Fuse Box
                                                                  |
    sector 2   Fuse Box  <-  chamber  <-  combat  <-  combat  <-  entry
                  |                                                 :  (secret wall)
    sector 3   entry  ->  combat  ->  combat  ->  chamber        hidden

Combat rooms lock their doors while robots are active. A chamber is where the Regulator is
fought, once per sector. The Fuse Box is the safe room between sectors. Templates use the
characters documented in overload.rooms.
"""

from __future__ import annotations

from dataclasses import dataclass

from overload.rooms import TILE, Room

CELL = (28, 22)  # tiles per grid cell
GRID = (5, 3)
CORRIDOR = 3  # tiles wide

# Room templates: terrain and decor rows. Walls: two rows on top (the 3/4 wall face), one row
# on the other sides. Door gaps are carved by the builder, so templates keep the middle of
# each wall free of decor.
_ENTRY = (
    (
        "##############",
        "##############",
        "#............#",
        "#..hh....hh..#",
        "#............#",
        "#.....==.....#",
        "#.....==.....#",
        "#............#",
        "#..hh....hh..#",
        "#............#",
        "#............#",
        "##############",
    ),
    (
        "..............",
        ".V..L....L..S.",
        "..............",
        "..............",
        "...........u..",
        "..............",
        "..............",
        "..u...........",
        "..............",
        "..............",
        "..B........K..",
        "..............",
    ),
)
_COMBAT_A = (
    (
        "######################",
        "######################",
        "#....................#",
        "#..gggg........gggg..#",
        "#....................#",
        "#....................#",
        "#.........==.........#",
        "#.........==.........#",
        "#.........==.........#",
        "#....................#",
        "#....................#",
        "#..gggg........gggg..#",
        "#....................#",
        "#....................#",
        "#....................#",
        "######################",
    ),
    (
        "......................",
        ".P.L..pppp..M...L..PP.",
        "......................",
        "......................",
        ".....I..........I.....",
        "..........u...........",
        "......................",
        "....K............K....",
        "......................",
        "......................",
        ".....I..........I.....",
        "......................",
        "...u..............u...",
        "......................",
        "..B................B..",
        "......................",
    ),
)
_COMBAT_B = (
    (
        "######################",
        "######################",
        "#....................#",
        "#.,,,,...........,,,.#",
        "#.,,,,...........,,,.#",
        "#....................#",
        "#....................#",
        "#.......----+---.....#",
        "#...........|........#",
        "#...........|........#",
        "#....................#",
        "#.hhh............hhh.#",
        "#.hhh............hhh.#",
        "#....................#",
        "#....................#",
        "######################",
    ),
    (
        "......................",
        ".S..L.....V....L..pp..",
        "......................",
        "......................",
        "......T........C......",
        "...........u..........",
        "..K...................",
        "......................",
        "......................",
        "....R.............K...",
        "......................",
        "..........T...........",
        "......................",
        "..u..............u....",
        "......................",
        "......................",
    ),
)
_COMBAT_C = (
    (
        "######################",
        "######################",
        "#....................#",
        "#....................#",
        "#..hh....######..hh..#",
        "#..hh....######..hh..#",
        "#....................#",
        "#....................#",
        "#....................#",
        "#....................#",
        "#..gg...........gg...#",
        "#..gg...........gg...#",
        "#....................#",
        "#....................#",
        "#....................#",
        "######################",
    ),
    (
        "......................",
        ".M..L...pppppp..L..V..",
        "......................",
        "....u..........u......",
        "..........SS..........",
        "......................",
        "......................",
        "..I...............I...",
        "......................",
        "......................",
        "......................",
        "......B.......K.......",
        "......................",
        ".......u......u.......",
        "......................",
        "......................",
    ),
)
_CHAMBER = (
    (
        "########################",
        "########################",
        "#......................#",
        "#..hhh............hhh..#",
        "#..hhh............hhh..#",
        "#......................#",
        "#.......--------.......#",
        "#.......|......|.......#",
        "#.......|......|.......#",
        "#.......|......|.......#",
        "#.......--------.......#",
        "#......................#",
        "#..hhh............hhh..#",
        "#..hhh............hhh..#",
        "#......................#",
        "#......................#",
        "#......................#",
        "########################",
    ),
    (
        "........................",
        ".PP.L..S...MM...S..L.PP.",
        "........................",
        "........................",
        "........................",
        "...u..............u.....",
        "........................",
        "........................",
        "...........u............",
        "........................",
        "........................",
        "........................",
        "........................",
        "........................",
        "..I..................I..",
        "...u..............u.....",
        "........................",
        "........................",
    ),
)
_FUSE = (
    (
        "##############",
        "##############",
        "#............#",
        "#.====.......#",
        "#.====.......#",
        "#............#",
        "#............#",
        "#............#",
        "#.......hhh..#",
        "#.......hhh..#",
        "#............#",
        "##############",
    ),
    (
        "..............",
        ".PP.L..M.L.PP.",
        "..............",
        "..............",
        "..........u...",
        "..............",
        "..............",
        "..u...........",
        "..............",
        "..............",
        "..C........C..",
        "..............",
    ),
)
_HIDDEN = (
    (
        "############",
        "############",
        "#..........#",
        "#.hhhhhhhh.#",
        "#.hhhhhhhh.#",
        "#..........#",
        "#..........#",
        "############",
    ),
    (
        "............",
        ".VL.......L.",
        "............",
        "............",
        "............",
        ".....u......",
        "..K......B..",
        "............",
    ),
)

# Sector looks: steel control hall, concrete transformer yard (concrete floor), the core
# (cable grates become lit conduit runs).
_THEMES = {1: {}, 2: {".": ","}, 3: {"g": "-"}}


@dataclass(frozen=True)
class FloorRoom:
    """`rect` is in tiles and includes the walls. `interior` excludes them. `spawns` are the
    tiles (absolute) where robots warp in."""

    id: str
    kind: str  # entry, combat, chamber, fuse or hidden
    sector: int
    rect: tuple[int, int, int, int]
    spawns: tuple[tuple[int, int], ...] = ()

    @property
    def interior(self) -> tuple[int, int, int, int]:
        x, y, w, h = self.rect
        return (x + 1, y + 2, w - 2, h - 3)

    @property
    def center(self) -> tuple[int, int]:
        x, y, w, h = self.interior
        return (x + w // 2, y + h // 2)


@dataclass(frozen=True)
class Door:
    """A gap in a room wall where a corridor meets it, in tiles. Doors can lock."""

    id: str
    room: str
    other: str
    rect: tuple[int, int, int, int]
    secret: bool = False


@dataclass(frozen=True)
class Floor:
    room: Room
    rooms: tuple[FloorRoom, ...]
    doors: tuple[Door, ...]

    def get(self, room_id: str) -> FloorRoom:
        return next(r for r in self.rooms if r.id == room_id)

    def room_at(self, tx: int, ty: int) -> FloorRoom | None:
        """The room whose interior contains this tile, if any (corridors are in no room)."""
        for room in self.rooms:
            x, y, w, h = room.interior
            if x <= tx < x + w and y <= ty < y + h:
                return room
        return None

    def doors_of(self, room_id: str) -> tuple[Door, ...]:
        return tuple(d for d in self.doors if d.room == room_id)


# Where robots warp in, per combat template, in tiles from the room's top-left corner. Kept
# clear of props and away from the doors (tests check both).
_SPAWNS = {
    "combat_a": ((5, 6), (16, 6), (5, 12), (16, 12), (10, 4), (11, 13), (3, 9), (18, 9)),
    "combat_b": ((9, 3), (13, 3), (4, 7), (17, 6), (6, 13), (15, 13), (9, 9), (14, 9)),
    "combat_c": ((5, 3), (17, 3), (5, 7), (16, 7), (11, 8), (4, 13), (17, 13), (11, 12)),
}

# Robot waves per combat room: each wave is a list of (robot kind, spawn index). The next wave
# warps in when the last robot of the previous one is down. Sector 1 brings Arc Drones (Spark)
# and Sweepers, sector 2 Relay Bots (Blink), Sentries and one Breaker (Burst, so Shock Cone can
# be fused before sector 3), sector 3 more Breakers and a mix.
WAVES: dict[str, tuple[tuple[tuple[str, int], ...], ...]] = {
    "s1_hall": (
        (("drone", 0), ("drone", 3)),
        (("drone", 4), ("sweeper", 6), ("sweeper", 7)),
    ),
    "s1_bay": (
        (("drone", 0), ("drone", 1), ("sweeper", 4)),
        (("drone", 2), ("sweeper", 3), ("drone", 6), ("sweeper", 7)),
    ),
    "s2_yard": (
        (("relay", 2), ("sentry", 4)),
        (("relay", 0), ("drone", 5), ("sentry", 7)),
    ),
    "s2_tanks": (
        (("relay", 2), ("relay", 3)),
        (("sentry", 0), ("relay", 4), ("breaker", 5), ("drone", 1)),
    ),
    "s3_core": (
        (("breaker", 4), ("drone", 2), ("sweeper", 3)),
        (("relay", 0), ("breaker", 5), ("sentry", 1), ("drone", 6)),
    ),
    "s3_bus": (
        (("breaker", 0), ("relay", 1), ("sentry", 5)),
        (("breaker", 2), ("relay", 3), ("sweeper", 6), ("drone", 7)),
    ),
}

TEMPLATES = {
    "entry": _ENTRY,
    "combat_a": _COMBAT_A,
    "combat_b": _COMBAT_B,
    "combat_c": _COMBAT_C,
    "chamber": _CHAMBER,
    "fuse": _FUSE,
    "hidden": _HIDDEN,
}

# (id, kind, sector, grid cell, template)
_PLAN = (
    ("s1_entry", "entry", 1, (0, 0), "entry"),
    ("s1_hall", "combat", 1, (1, 0), "combat_a"),
    ("s1_bay", "combat", 1, (2, 0), "combat_b"),
    ("s1_chamber", "chamber", 1, (3, 0), "chamber"),
    ("fuse_1", "fuse", 1, (4, 0), "fuse"),
    ("s2_entry", "entry", 2, (4, 1), "entry"),
    ("s2_yard", "combat", 2, (3, 1), "combat_b"),
    ("s2_tanks", "combat", 2, (2, 1), "combat_c"),
    ("s2_chamber", "chamber", 2, (1, 1), "chamber"),
    ("fuse_2", "fuse", 2, (0, 1), "fuse"),
    ("s3_entry", "entry", 3, (0, 2), "entry"),
    ("s3_core", "combat", 3, (1, 2), "combat_c"),
    ("s3_bus", "combat", 3, (2, 2), "combat_a"),
    ("s3_chamber", "chamber", 3, (3, 2), "chamber"),
    ("hidden", "hidden", 2, (4, 2), "hidden"),
)
_LINKS = (
    ("s1_entry", "s1_hall"),
    ("s1_hall", "s1_bay"),
    ("s1_bay", "s1_chamber"),
    ("s1_chamber", "fuse_1"),
    ("fuse_1", "s2_entry"),
    ("s2_entry", "s2_yard"),
    ("s2_yard", "s2_tanks"),
    ("s2_tanks", "s2_chamber"),
    ("s2_chamber", "fuse_2"),
    ("fuse_2", "s3_entry"),
    ("s3_entry", "s3_core"),
    ("s3_core", "s3_bus"),
    ("s3_bus", "s3_chamber"),
)
_SECRET_LINKS = (("s2_entry", "hidden"),)


def _themed(rows: tuple[str, ...], sector: int) -> list[str]:
    table = _THEMES[sector]
    return ["".join(table.get(c, c) for c in row) for row in rows]


def build() -> Floor:
    width, height = CELL[0] * GRID[0], CELL[1] * GRID[1]
    terrain = [["#"] * width for _ in range(height)]
    decor = [["."] * width for _ in range(height)]
    rooms: dict[str, FloorRoom] = {}
    for room_id, kind, sector, (cx, cy), template in _PLAN:
        t_rows, d_rows = TEMPLATES[template]
        w, h = len(t_rows[0]), len(t_rows)
        x0 = cx * CELL[0] + (CELL[0] - w) // 2
        y0 = cy * CELL[1] + (CELL[1] - h) // 2
        for dy, (t_row, d_row) in enumerate(zip(_themed(t_rows, sector), d_rows, strict=True)):
            for dx, (t, d) in enumerate(zip(t_row, d_row, strict=True)):
                terrain[y0 + dy][x0 + dx] = t
                decor[y0 + dy][x0 + dx] = d
        spawns = tuple((x0 + sx, y0 + sy) for sx, sy in _SPAWNS.get(template, ()))
        rooms[room_id] = FloorRoom(room_id, kind, sector, (x0, y0, w, h), spawns)

    doors: list[Door] = []
    for links, secret in ((_LINKS, False), (_SECRET_LINKS, True)):
        for a, b in links:
            doors += _carve(terrain, decor, rooms[a], rooms[b], secret)

    labels = tuple(
        (room.rect[0] + 2, room.rect[1] + 2, label, "floor")
        for room, label in (
            (rooms["s1_entry"], "SECTOR 1"),
            (rooms["s2_entry"], "SECTOR 2"),
            (rooms["s3_entry"], "SECTOR 3"),
            (rooms["fuse_1"], "FUSE BOX"),
            (rooms["fuse_2"], "FUSE BOX"),
        )
    )
    room = Room(
        name="substation floor",
        terrain=tuple("".join(row) for row in terrain),
        decor=tuple("".join(row) for row in decor),
        labels=labels,
    )
    return Floor(room, tuple(rooms.values()), tuple(doors))


def _carve(terrain, decor, a: FloorRoom, b: FloorRoom, secret: bool) -> list[Door]:
    """Cut a corridor between two rooms in neighboring cells and return the two doors (the
    wall gaps). Horizontal neighbors meet at their side walls, vertical ones at the bottom
    wall of the upper room and the two-row top wall of the lower room."""
    ax, ay, _, _ = a.rect
    bx, by, _, _ = b.rect
    half = CORRIDOR // 2
    if ay // CELL[1] == by // CELL[1]:  # same row: horizontal corridor
        left, right = (a, b) if ax < bx else (b, a)
        lx, _, lw, _ = left.rect
        rx = right.rect[0]
        cy = _mid_row(left, right)
        for y in range(cy - half, cy + half + 1):
            for x in range(lx + lw - 1, rx + 1):
                _clear(decor, x, y, left, right)
                terrain[y][x] = "=" if not secret else "."
        gaps = (
            (left, (lx + lw - 1, cy - half, 1, CORRIDOR)),
            (right, (rx, cy - half, 1, CORRIDOR)),
        )
    else:  # vertical corridor
        top, bottom = (a, b) if ay < by else (b, a)
        _, ty, _, th = top.rect
        bot_y = bottom.rect[1]
        cx = _mid_col(top, bottom)
        for x in range(cx - half, cx + half + 1):
            for y in range(ty + th - 1, bot_y + 2):
                _clear(decor, x, y, top, bottom)
                terrain[y][x] = "=" if not secret else "."
        gaps = (
            (top, (cx - half, ty + th - 1, CORRIDOR, 1)),
            (bottom, (cx - half, bot_y, CORRIDOR, 2)),
        )
    return [
        Door(f"{room.id}>{other.id}", room.id, other.id, rect, secret)
        for (room, rect), other in zip(gaps, (gaps[1][0], gaps[0][0]), strict=True)
    ]


def _clear(decor, x: int, y: int, a: FloorRoom, b: FloorRoom) -> None:
    """Corridors and door gaps must cut through bare wall and floor, never decor."""
    if decor[y][x] != ".":
        raise ValueError(f"the corridor {a.id} to {b.id} would erase decor at ({x}, {y})")


def _mid_row(a: FloorRoom, b: FloorRoom) -> int:
    """A corridor row inside both rooms' interiors, as central as possible."""
    lo = max(a.interior[1], b.interior[1]) + 1
    hi = min(a.interior[1] + a.interior[3], b.interior[1] + b.interior[3]) - 2
    return (lo + hi) // 2


def _mid_col(a: FloorRoom, b: FloorRoom) -> int:
    lo = max(a.interior[0], b.interior[0]) + 1
    hi = min(a.interior[0] + a.interior[2], b.interior[0] + b.interior[2]) - 2
    return (lo + hi) // 2


FLOOR = build()


def tile_rect_px(rect: tuple[int, int, int, int]) -> tuple[float, float, float, float]:
    x, y, w, h = rect
    return (float(x * TILE), float(y * TILE), float(w * TILE), float(h * TILE))
