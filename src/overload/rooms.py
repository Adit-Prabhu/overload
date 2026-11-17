"""Room layouts, shared by the art (what to draw) and the simulation (what is solid).

Pure data, no pygame. Each room is two equal-size text grids, one character per 16 px tile.

Terrain:
    #  wall              .  steel floor tile     ,  cracked concrete patch
    =  steel walkway (diamond plate, painted edges and arrows)
    g  cable trench grate                        h  hazard-painted concrete
    -  |  +  lit conduit channel in the floor (horizontal, vertical, junction)

Decor (drawn on top of terrain, "." means nothing):
    On wall faces:  P breaker panel   S danger sign   L emergency lamp   V vent
                    M meter gauge     p pipe run
    On the floor:   o oil stain   x scorch mark   c loose cable   d drain   b debris
                    u overhead emergency light (a pool of light, no visible fixture)
    Props (solid):  T transformer (top-left of a 2 x 2 footprint)   C switchgear cabinet
                    R cable reel   I insulator stack   K crate   B oil drum
"""

from __future__ import annotations

from dataclasses import dataclass

TILE = 16
WALL_DECOR = frozenset("PSLVMp")
FLOOR_DECALS = frozenset("oxcdbu")
PROPS = frozenset("TCRIKB")


@dataclass(frozen=True)
class Room:
    """`labels` are stenciled words: (tile x, tile y, text, "wall" or "floor")."""

    name: str
    terrain: tuple[str, ...]
    decor: tuple[str, ...]
    labels: tuple[tuple[int, int, str, str], ...] = ()

    def __post_init__(self) -> None:
        width = len(self.terrain[0])
        if any(len(row) != width for row in self.terrain + self.decor):
            raise ValueError(f"{self.name}: every row must be {width} characters wide")
        if len(self.terrain) != len(self.decor):
            raise ValueError(f"{self.name}: terrain and decor need the same number of rows")
        for y, row in enumerate(self.decor):
            for x, char in enumerate(row):
                on_wall = self.terrain[y][x] == "#"
                if char in WALL_DECOR and not on_wall:
                    raise ValueError(
                        f"{self.name}: wall decor {char!r} at ({x}, {y}) is not on a wall"
                    )
                if (char in FLOOR_DECALS or char in PROPS) and on_wall:
                    raise ValueError(f"{self.name}: floor item {char!r} at ({x}, {y}) is on a wall")

    @property
    def size(self) -> tuple[int, int]:
        return (len(self.terrain[0]) * TILE, len(self.terrain) * TILE)

    def at(self, x: int, y: int) -> str:
        if 0 <= y < len(self.terrain) and 0 <= x < len(self.terrain[0]):
            return self.terrain[y][x]
        return "#"

    def is_wall(self, x: int, y: int) -> bool:
        return self.at(x, y) == "#"


SUBSTATION_HALL = Room(
    name="substation hall",
    terrain=(
        "##########################",
        "##########################",
        "#...........==...........#",
        "#.hhhhhh....==....gggggg.#",
        "#.hhhhhh..,,==...........#",
        "#.hhhhhh..,,==...........#",
        "#.hhhhhh....==....--+---.#",
        "#...........==......|....#",
        "#=======================.#",
        "#...........==......|....#",
        "#..gggg.....==..,,..|.hhh#",
        "#...........==..,...|.hhh#",
        "#.....###...==......|.hhh#",
        "#.....###...==...........#",
        "#...........==...........#",
        "##########################",
    ),
    decor=(
        "..........................",
        ".PP.L.ppppp.S..M.V.L.PP.p.",
        "...............CCC...KK...",
        "......I...b......c........",
        "...T......x...........u...",
        "......I..........o........",
        ".....o...u......b.........",
        "..........................",
        "..........................",
        "....u..........x....b.....",
        "..........d...........u...",
        ".......................B..",
        "......S..........b........",
        "...b.........u........R...",
        "..B.......o...............",
        "..........................",
    ),
    labels=(
        (14, 0, "SUBSTATION 07", "wall"),
        (2, 0, "33 KV", "wall"),
        (2, 7, "BAY 1", "floor"),
        (19, 13, "BAY 2", "floor"),
    ),
)
