"""Pixel effects: projectiles, charges, Arc Trail, telegraphs, dodge ghosts and hit flashes.

Functions draw onto `target` (the 256 x 144 view) and, for anything that emits light, also
onto `light` (a black surface the bloom pass reads). Coordinates are view pixels.
"""

from __future__ import annotations

import math
import random
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
    "B": "power.bulwark",
    "b": "px.bulwark.light",
    "N": "power.magnet",
    "n": "px.magnet.light",
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
    "arc_trail": [
        "kK......",
        "KkY.....",
        "..YY....",
        "...yY...",
        "....YY..",
        ".....YkK",
        "......Kk",
    ],
    "shock_cone": [
        "UU.....",
        "U.UU...",
        "U..YUU.",
        "U.YyY.U",
        "U..YUU.",
        "U.UU...",
        "UU.....",
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
    "bulwark": [  # a shield with a center ridge
        ".BBBBB.",
        "BbbBbbB",
        "BbbBbbB",
        "BbbBbbB",
        ".BbBbB.",
        "..BBB..",
        "...B...",
    ],
    "magnet": [  # a horseshoe magnet
        ".NNNNN.",
        "NNnnnNN",
        "NN...NN",
        "NN...NN",
        "NN...NN",
        "nn...nn",
        "nn...nn",
    ],
    # Fused powers: one icon per power, drawn for its own verb (POWERS_AND_FUSION section 8).
    "bolt_lance": [  # a lightning spear
        ".......",
        "k...Y..",
        "kk..YY.",
        "kKYYYYY",
        "kk..YY.",
        "k...Y..",
        ".......",
    ],
    "chain_jump": [  # hops linking three targets
        "K.....K",
        "Ky...yK",
        ".Y...Y.",
        "..Y.Y..",
        "...K...",
        "...K...",
        ".......",
    ],
    "shock_mine": [  # a spiked charge
        "...Y...",
        "..U.U..",
        ".UyYyU.",
        "UYyuyYU",
        ".UyYyU.",
        "..U.U..",
        "...U...",
    ],
    "storm_aura": [  # a ring of bolts
        ".Y.U.Y.",
        "Y.U.U.Y",
        ".U...U.",
        "U..Y..U",
        ".U...U.",
        "Y.U.U.Y",
        ".Y.U.Y.",
    ],
    "impact_blink": [  # a Blink diamond landing in a blast
        "U..k..U",
        "..kKk..",
        ".kK.Kk.",
        "UK...KU",
        ".kK.Kk.",
        "..kKk..",
        "U..k..U",
    ],
    "displacer": [  # two arrows trading places
        "..K....",
        ".KKKKK.",
        "..K..K.",
        ".......",
        ".U..U..",
        ".UUUUU.",
        "....U..",
    ],
    "meteor": [  # a rock falling with a trail
        "k......",
        ".k.....",
        "..kU...",
        "...UUU.",
        "...UuUU",
        "....UUU",
        ".......",
    ],
    # The pairs Bulwark and Magnet join (sim/pairs.py), each drawn for its own verb.
    "static_guard": [  # a shield with a bolt
        ".BBBBB.",
        "BbbYbbB",
        "BbYYbbB",
        "BbbYYbB",
        ".BbYbB.",
        "..BBB..",
        "...B...",
    ],
    "tesla_coil": [  # a coil tower throwing arcs
        "Y..B..Y",
        ".Y.B.Y.",
        "..BbB..",
        "..BbB..",
        "..BbB..",
        ".BBBBB.",
        "BBBBBBB",
    ],
    "capacitor_armor": [  # three charge cells in a shield
        ".BBBBB.",
        "BY.Y.YB",
        "BY.Y.YB",
        "BbbbbbB",
        ".BbbbB.",
        "..BbB..",
        "...B...",
    ],
    "lodestone": [  # a heavy spark with field lines
        "N.....N",
        ".N.Y.N.",
        "..YyY..",
        ".YyyyY.",
        "..YyY..",
        ".N.Y.N.",
        "N.....N",
    ],
    "ion_hook": [  # a hook on a line
        "...YY..",
        "....Y..",
        "....Y..",
        "....Y..",
        "N...Y..",
        "NN..Y..",
        ".NNNN..",
    ],
    "magrail": [  # a rail between two magnets
        "N.....N",
        "N.....N",
        "NYYYYYN",
        "NyyyyyN",
        "NYYYYYN",
        "N.....N",
        "N.....N",
    ],
    "bastion": [  # a shield ringed by a blast
        "U.BBB.U",
        ".BbbbB.",
        "UBbUbBU",
        ".BbbbB.",
        "U.BbB.U",
        "...B...",
        ".......",
    ],
    "reflector_wave": [  # a wall pushing out
        "B......",
        "BU.....",
        "B.UU...",
        "B...UUU",
        "B.UU...",
        "BU.....",
        "B......",
    ],
    "fortress": [  # a dome over a core
        "..BBB..",
        ".BbbbB.",
        "BbbUbbB",
        "BbUuUbB",
        "BbbUbbB",
        "BBBBBBB",
        ".......",
    ],
    "vortex_cone": [  # a cone that curls inward
        "UU.....",
        "U.NN...",
        "U.N.NU.",
        "U.NN.NU",
        "U...NU.",
        "U.UU...",
        "UU.....",
    ],
    "implosion": [  # everything drawn to one point
        "N..U..N",
        ".N.U.N.",
        "..NUN..",
        "UUUuUUU",
        "..NUN..",
        ".N.U.N.",
        "N..U..N",
    ],
    "gravity_well": [  # rings around a heavy heart
        "..NNN..",
        ".N...N.",
        "N.UUU.N",
        "N.UuU.N",
        "N.UUU.N",
        ".N...N.",
        "..NNN..",
    ],
    "phase_guard": ["..BBB..", ".BKKKB.", "B.K.K.B", "B..k..B", ".BK.KB.", "..BKB..", "...B..."],
    "afterimage": ["..KK...", "..KKN..", ".KKNNN.", "..K.N..", ".K.K.N.", "K...N.N", "......."],
    "rewind": ["..kkk..", ".k...k.", "kB.K..k", "BB.KK.k", ".B...k.", "..kkkk.", "......."],
    "undertow": ["K.....K", ".KN.NK.", "..KNK..", "N..k..N", ".N...N.", "..N.N..", "...N..."],
    "grapple": ["....NN.", "...N..N", "..N..NN", ".K...N.", "K......", "k......", "......."],
    "riptide": ["N.....N", ".Nn.nN.", "..KKK..", "nKK.KKn", "..KKK..", ".Nn.nN.", "N.....N"],
    "lightning_rod": ["...N...", ".N.B.N.", "N..b..N", "...B...", ".n.B.n.", "..BBB..", "NNNNNNN"],
    "shield_toss": [".....BB", "...BB.B", "NNB.N.B", ".NB.BB.", "..BB...", "NN.....", ".N....."],
    "mirror_field": ["b..N..b", ".N...N.", "..BbB..", "N.B.B.N", "..BBB..", ".N...N.", "b..N..b"],
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


def spark_shot(target: pygame.Surface, light: pygame.Surface, pos: Point, angle: float):
    """Spark: a small zigzag bolt, the Spark symbol in flight, so it never reads as the
    gun's straight streak even without color."""
    dx, dy = math.cos(angle), math.sin(angle)
    nx, ny = -dy, dx
    points = [
        (round(pos[0] - dx * along + nx * side), round(pos[1] - dy * along + ny * side))
        for along, side in ((0, 0), (3, 3), (5, -2), (8, 2), (10, -1))
    ]
    for surface in (target, light):
        pygame.draw.lines(surface, rgb("power.spark"), False, points, 2)
        pygame.draw.lines(surface, rgb("px.spark.light"), False, points, 1)


def slam_tell(
    target: pygame.Surface, light: pygame.Surface, center: Point, reach: float, progress: float
) -> None:
    """A Breaker about to slam: a dotted ring at the shockwave's full reach fills in (the
    same circle the wave can hit within)."""
    cx, cy = center
    count = 36
    lit = int(count * max(0.0, min(1.0, progress)))
    for i in range(lit):
        a = math.tau * i / count
        x, y = round(cx + math.cos(a) * reach), round(cy + math.sin(a) * reach)
        for surface in (target, light):
            surface.set_at((x, y), rgb("hostile.danger"))


def signature_tell(
    target: pygame.Surface,
    light: pygame.Surface,
    center: Point,
    name: str,
    progress: float,
    reach: float,
    aim: float,
    points: list[Point],
    arms: int = 2,
) -> None:
    """A Regulator chassis winding up its signature: a ring of dots fills around it, plus a
    shape that says what is coming. Ring: eight dotted spokes grow outward. Quake: a dotted
    ring at the shockwave's full reach fills in. Summon: warp markers close in where the
    drones will appear. Spiral: two opposite dotted arms show where it starts."""
    progress = max(0.0, min(1.0, progress))
    for surface in (target, light):
        _ring_dots(surface, "hostile.danger", center, 20, progress)
    cx, cy = center
    if name == "ring":
        for i in range(8):
            a = math.tau * i / 8
            for d in range(22, 22 + int(28 * progress), 4):
                target.fill(
                    rgb("hostile.danger"),
                    (round(cx + math.cos(a) * d), round(cy + math.sin(a) * d), 2, 2),
                )
    elif name == "quake":
        slam_tell(target, light, center, reach, progress)
    elif name == "summon":
        for point in points:
            warp_marker(target, light, point, progress)
    elif name == "spiral":
        for a in (aim + math.tau * k / arms for k in range(arms)):
            for d in range(22, 70, 4):
                target.fill(
                    rgb("power.burst"),
                    (round(cx + math.cos(a) * d), round(cy + math.sin(a) * d), 2, 1),
                )


def burst_cone(
    target: pygame.Surface,
    light: pygame.Surface,
    origin: Point,
    angle: float,
    reach: float,
    cos_half: float,
    life: float,
    shock: bool,
) -> None:
    """A Burst discharge: magenta rays fanning across the cone and an arc at its reach,
    fading over a few frames. A Shock Cone adds yellow sparks along the rays."""
    if life <= 0:
        return
    half = math.acos(max(-1.0, min(1.0, cos_half)))
    ox, oy = origin
    rays = 7
    for i in range(rays):
        a = angle - half + 2 * half * i / (rays - 1)
        end = (ox + math.cos(a) * reach * life, oy + math.sin(a) * reach * life)
        start = (ox + math.cos(a) * 6, oy + math.sin(a) * 6)
        token = "power.spark" if shock and i % 2 else "power.burst"
        for surface in (target, light):
            pygame.draw.line(surface, rgb(token), start, end, 1)
    points = [
        (
            ox + math.cos(angle - half + 2 * half * i / 10) * reach,
            oy + math.sin(angle - half + 2 * half * i / 10) * reach,
        )
        for i in range(11)
    ]
    for surface in (target, light):
        pygame.draw.lines(surface, rgb("px.burst.light"), False, points, 1)


def chain_bolt(target: pygame.Surface, light: pygame.Surface, a: Point, b: Point) -> None:
    """An evolved Spark arcing from one robot to the next: a jagged yellow line."""
    dx, dy = b[0] - a[0], b[1] - a[1]
    distance = math.hypot(dx, dy) or 1.0
    nx, ny = -dy / distance, dx / distance
    points = [
        (
            a[0] + dx * i / 6 + nx * (0 if i in (0, 6) else (3 if i % 2 else -3)),
            a[1] + dy * i / 6 + ny * (0 if i in (0, 6) else (3 if i % 2 else -3)),
        )
        for i in range(7)
    ]
    for surface in (target, light):
        pygame.draw.lines(surface, rgb("power.spark"), False, points, 2)
        pygame.draw.lines(surface, rgb("px.spark.light"), False, points, 1)


def warp_marker(target: pygame.Surface, light: pygame.Surface, pos: Point, progress: float):
    """A robot is about to warp in here: a ring of dots closes in while a beam brightens
    (shape and motion, not color alone)."""
    cx, cy = round(pos[0]), round(pos[1])
    radius = 12 - round(8 * max(0.0, min(1.0, progress)))
    for i in range(10):
        a = math.tau * i / 10 + progress * 2
        x, y = round(cx + math.cos(a) * radius), round(cy + math.sin(a) * radius * 0.6)
        for surface in (target, light):
            surface.set_at((x, y), rgb("hostile.danger"))
    height = round(18 * progress)
    for surface in (target, light):
        pygame.draw.line(surface, rgb("px.hostile.3"), (cx, cy), (cx, cy - height), 1)


def shutter(target: pygame.Surface, light: pygame.Surface, rect: pygame.Rect, blink: bool):
    """A locked blast door: a dark slab with hazard stripes and a red lock light."""
    target.fill(rgb("px.bot.1"), rect)
    clip = target.get_clip()
    target.set_clip(rect.clip(clip))
    for i in range(-rect.h, rect.w, 6):
        pygame.draw.line(
            target,
            rgb("px.hazard.1"),
            (rect.x + i, rect.bottom - 1),
            (rect.x + i + rect.h, rect.y),
            2,
        )
    target.set_clip(clip)
    pygame.draw.rect(target, rgb("px.outline"), rect, 1)
    if blink:
        lamp = (rect.centerx - 1, rect.centery - 1, 3, 3)
        for surface in (target, light):
            surface.fill(rgb("hostile.danger"), lamp)


def cracked_wall(target: pygame.Surface, rect: pygame.Rect, hits: int) -> None:
    """A secret wall: plain wall that shows more cracks each time it is shot."""
    target.fill(rgb("px.wall.1"), rect)
    pygame.draw.rect(target, rgb("px.wall.2"), (rect.x, rect.y, rect.w, 3))
    cracks = (
        (4, 5, 9, 10),
        (rect.w - 10, 6, rect.w - 4, 12),
        (rect.w // 2, 3, rect.w // 2 + 4, 11),
    )
    for x0, y0, x1, y1 in cracks[: hits + 1]:
        pygame.draw.line(
            target, rgb("px.outline"), (rect.x + x0, rect.y + y0), (rect.x + x1, rect.y + y1), 1
        )


def fusion_rings(target: pygame.Surface, center: Point, progress: float) -> None:
    """PK-03: a Spark ring and a Blink ring expand from the recipe as Arc Trail is fused."""
    cx, cy = round(center[0]), round(center[1])
    for i, token in enumerate(("power.spark", "power.blink")):
        radius = 6 + round(7 * progress) + i * 3
        pygame.draw.circle(target, rgb(token), (cx, cy), radius, 1)


def bolt(target: pygame.Surface, light: pygame.Surface, pos: Point) -> None:
    _blit_center(target, hostile_bolt(), pos)
    _blit_center(light, hostile_bolt(), pos)


def charge(target: pygame.Surface, light: pygame.Surface, pos: Point, power: str, t: float):
    bob = round(math.sin(t * 3 + pos[0] * 0.1) * 1.5)
    spot = (pos[0], pos[1] + bob)
    _blit_center(target, charge_icon(power), spot)
    _blit_center(light, charge_icon(power), spot)


def arc_trail(
    target: pygame.Surface,
    light: pygame.Surface,
    start: Point,
    end: Point,
    life: float,
    storm: bool = False,
) -> None:
    """Spark + Blink fusion: a jagged spark line strung between two Blink diamonds. A storm
    trail (Storm Step, Thunderhead) is wider: a second bolt runs zigzag against the first,
    so the epic's step shows by shape."""
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
    # The storm's second bolt: each point mirrored across the straight line.
    straight = [(sx + dx * i / steps, sy + dy * i / steps) for i in range(steps + 1)]
    twin = [
        (round(2 * bx - px), round(2 * by - py))
        for (bx, by), (px, py) in zip(straight, points, strict=True)
    ]
    for surface in (target, light):
        if storm:
            pygame.draw.lines(surface, rgb("power.spark"), False, twin, 1)
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


# Fused powers --------------------------------------------------------------------------------


def blast_ring(
    target: pygame.Surface, light: pygame.Surface, pos: Point, radius: float, life: float
) -> None:
    """A ring blast (Impact Blink, Displacer, Shock Mine, Meteor): a magenta ring that runs
    out to the blast's edge as `life` falls from 1 to 0."""
    r = max(2, round(radius * (1.0 - 0.7 * life)))
    center = (round(pos[0]), round(pos[1]))
    for surface in (target, light):
        pygame.draw.circle(surface, rgb("power.burst"), center, r, 2)
        pygame.draw.circle(surface, rgb("px.burst.light"), center, max(1, r - 3), 1)


def mine(target: pygame.Surface, light: pygame.Surface, pos: Point, fuse: float) -> None:
    """A Shock Mine: a spiked charge. Armed, a dotted ring closes in as the fuse burns
    (`fuse` from 1 at arming to 0 at the burst), the same filling tell as hostile attacks
    but in power colors."""
    _blit_center(target, charge_icon("shock_mine"), pos)
    _blit_center(light, charge_icon("shock_mine"), pos)
    if fuse < 0:
        return
    dots = 8
    lit = round(dots * (1.0 - fuse))
    for i in range(dots):
        a = math.tau * i / dots
        point = (round(pos[0] + math.cos(a) * 9), round(pos[1] + math.sin(a) * 9))
        token = "power.spark" if i < lit else "px.floor.3"
        target.fill(rgb(token), (*point, 1, 1))


def aura(target: pygame.Surface, light: pygame.Surface, pos: Point, tick: int) -> None:
    """Storm Aura: a crackling ring of short bolts turning around the Surge."""
    for i in range(6):
        a = math.tau * i / 6 + tick * 0.08
        x, y = pos[0] + math.cos(a) * 11, pos[1] + math.sin(a) * 9
        b = a + 0.5
        x2, y2 = pos[0] + math.cos(b) * 13, pos[1] + math.sin(b) * 10
        for surface in (target, light):
            pygame.draw.line(surface, rgb("power.spark"), (x, y), (x2, y2), 1)


def landing_marker(target: pygame.Surface, pos: Point, radius: float, progress: float) -> None:
    """Meteor: a ring of dashes where the Surge will land, the true circle the blast hits,
    lighting up around the ring as the fall goes on, with a cross at the center."""
    center = (round(pos[0]), round(pos[1]))
    dashes = 24
    lit = round(dashes * progress)
    for i in range(dashes):
        a = math.tau * i / dashes
        x, y = center[0] + math.cos(a) * radius, center[1] + math.sin(a) * radius
        token = "power.burst" if i < lit else "px.floor.3"
        target.fill(rgb("px.outline"), (round(x) - 2, round(y) - 2, 4, 4))
        target.fill(rgb(token), (round(x) - 1, round(y) - 1, 2, 2))
    for dx, dy in ((-3, 0), (3, 0), (0, -3), (0, 3), (0, 0)):
        target.fill(rgb("power.burst"), (center[0] + dx, center[1] + dy, 1, 1))


def lance_streak(
    target: pygame.Surface, light: pygame.Surface, pos: Point, dx: float, dy: float
) -> None:
    """Bolt Lance: a jagged bolt trailing behind the Surge as it dashes."""
    points = []
    for i in range(5):
        side = (i % 2) * 2 - 1
        points.append((pos[0] - dx * i * 4 - dy * side * 2, pos[1] - dy * i * 4 + dx * side * 2))
    for surface in (target, light):
        pygame.draw.lines(surface, rgb("power.spark"), False, points, 2)
        pygame.draw.lines(surface, rgb("px.blink.light"), False, points, 1)


def relay_beam(target: pygame.Surface, light: pygame.Surface, pos: Point, life: float) -> None:
    """A Relay Bot beaming out or in: a column of Blink light over the spot that narrows as
    it fades, so its teleport reads as a jump, not a glitch."""
    x, y = round(pos[0]), round(pos[1])
    half = max(0, round(life * 4))
    height = round(10 + 18 * life)
    for surface in (target, light):
        surface.fill(rgb("px.blink.light"), (x - half // 2, y + 10 - height, max(1, half), height))
        if half > 1:
            surface.fill(rgb("power.blink"), (x - half, y + 8, half * 2, 2))


def ripple(target: pygame.Surface, pos: Point, age: float) -> None:
    """A drop landing in a puddle: a ring that spreads and breaks up as it fades."""
    w, h = 2 + round(age * 12), 1 + round(age * 5)
    rect = pygame.Rect(0, 0, w, h)
    rect.center = (round(pos[0]), round(pos[1]))
    if age < 0.7:
        pygame.draw.ellipse(target, rgb("px.conduit.1"), rect, 1)
    else:
        pygame.draw.ellipse(target, rgb("px.conduit.0"), rect, 1)


def kit_tell(
    target: pygame.Surface,
    light: pygame.Surface,
    center: Point,
    name: str,
    progress: float,
    aim: float,
    lines: list[tuple[Point, Point]],
    marks: list[Point],
    width: float,
) -> None:
    """The boss kit's own tells, each a different shape: Live Wire's dotted lines filling
    outward, a volley's landing circles closing in, the Bull Charge's lane, the Coolant
    Spray's fan. A ring of dots fills around the chassis for all of them."""
    progress = max(0.0, min(1.0, progress))
    danger = rgb("hostile.danger")
    for surface in (target, light):
        _ring_dots(surface, "hostile.danger", center, 24, progress)
    if name == "live_wire":
        for a, b in lines:
            span = math.dist(a, b)
            for d in range(24, int(span * progress), 5):
                t = d / span
                x, y = a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t
                for surface in (target, light):
                    surface.fill(danger, (round(x), round(y), 2, 2))
    elif name == "volley":
        for mark in marks:
            radius = 4 + (1.0 - progress) * 14
            for surface in (target, light):
                _ring_dots(surface, "hostile.danger", mark, radius, 1.0)
                surface.fill(danger, (round(mark[0]) - 1, round(mark[1]) - 1, 2, 2))
    elif name == "charge":
        dx, dy = math.cos(aim), math.sin(aim)
        px, py = -dy, dx
        for d in range(int(width), int(width) + int(260 * progress), 6):
            for side in (-1, 1):
                x = center[0] + dx * d + px * width * side
                y = center[1] + dy * d + py * width * side
                for surface in (target, light):
                    surface.fill(danger, (round(x), round(y), 2, 2))
    elif name == "spray":
        for k in range(-3, 4):
            a = aim + math.radians(12 * k)
            for d in range(26, 26 + int(40 * progress), 5):
                target.fill(
                    danger,
                    (round(center[0] + math.cos(a) * d), round(center[1] + math.sin(a) * d), 2, 2),
                )


def live_wire(target: pygame.Surface, light: pygame.Surface, a: Point, b: Point, tick: int) -> None:
    """A Live Wire line while it burns: a jagged arc that jumps every couple of ticks."""
    span = math.dist(a, b)
    steps = max(2, int(span // 8))
    jitter = random.Random(tick // 2 + round(a[0]) * 7 + round(b[1]) * 13)
    points = []
    for i in range(steps + 1):
        t = i / steps
        off = 0 if i in (0, steps) else jitter.uniform(-3, 3)
        dx, dy = (b[0] - a[0]) / span, (b[1] - a[1]) / span
        points.append((a[0] + (b[0] - a[0]) * t - dy * off, a[1] + (b[1] - a[1]) * t + dx * off))
    for surface in (target, light):
        pygame.draw.lines(surface, rgb("hostile.danger"), False, points, 2)
        pygame.draw.lines(surface, rgb("px.lamp.light"), False, points, 1)


def kit_hazard(
    target: pygame.Surface,
    light: pygame.Surface,
    top_left: Point,
    size: float,
    progress: float,
    kind: str,
    burning: bool,
    tick: int,
) -> None:
    """A boss kit's floor marking, shaped unlike Insulate's tiles. A Lattice cell: corner
    brackets, then cross-hatching that grows from the middle outward, then a crackling burn.
    Debris: a shadow that grows where it will land, with a cross at its heart."""
    x, y, n = round(top_left[0]), round(top_left[1]), round(size)
    danger = rgb("hostile.danger")
    if kind == "debris":
        radius = 2 + round((n / 2 - 2) * max(0.0, min(1.0, progress)))
        center = (x + n // 2, y + n // 2)
        pygame.draw.circle(target, rgb("px.outline"), center, radius)
        for surface in (target, light):
            pygame.draw.circle(surface, danger, center, radius, 1)
            if burning:
                pygame.draw.circle(surface, rgb("px.lamp.light"), center, max(1, radius - 2))
        return
    for cx, cy, dx, dy in (
        (x, y, 1, 1),
        (x + n - 1, y, -1, 1),
        (x, y + n - 1, 1, -1),
        (x + n - 1, y + n - 1, -1, -1),
    ):
        for surface in (target, light):
            surface.fill(danger, (min(cx, cx + dx * 4), cy, 5, 1))
            surface.fill(danger, (cx, min(cy, cy + dy * 4), 1, 5))
    if burning:
        for surface in (target, light):
            for k in range(2, n - 2, 3):
                jitter = (tick // 2 + k) % 3 - 1
                surface.fill(danger, (x + 2, y + k + jitter, n - 4, 1))
        light.fill(rgb("px.lamp"), (x + n // 2 - 2, y + n // 2 - 2, 4, 4))
        return
    reach = (n / 2 - 2) * max(0.0, min(1.0, progress))
    mid = n / 2
    for dy in range(2, n - 2):
        for dx in range(2, n - 2):
            if (
                abs(dx - mid) <= reach
                and abs(dy - mid) <= reach
                and (dx + dy) % 4 == 0
                or (abs(dx - mid) <= reach and abs(dy - mid) <= reach and (dx - dy) % 4 == 0)
            ):
                target.set_at((x + dx, y + dy), danger)


def explosion(target: pygame.Surface, light: pygame.Surface, pos: Point, age: float) -> None:
    """An explosion on a dying chassis: a hot core that swells and a ring that runs out,
    in fire colors, never a power's."""
    x, y = round(pos[0]), round(pos[1])
    radius = 3 + round(age * 11)
    core = max(0, round((1.0 - age) * 6))
    for surface in (target, light):
        pygame.draw.circle(surface, rgb("px.hostile.2"), (x, y), radius, 1)
        if core:
            pygame.draw.circle(surface, rgb("px.lamp"), (x, y), core + 1)
            pygame.draw.circle(surface, rgb("px.lamp.light"), (x, y), core)


def bubble(
    target: pygame.Surface,
    light: pygame.Surface,
    center: Point,
    radius: float,
    left: float,
    tick: int,
    accent: str = "",
) -> None:
    """Bulwark's shield: a ring of hex-like dashes around the Surge, a pale inner ring, and
    a flicker as it runs out (the last quarter)."""
    if left < 0.25 and tick % 4 < 2:
        return
    x, y = round(center[0]), round(center[1])
    r = round(radius)
    count = 18
    for i in range(count):
        if i % 3 == 2:
            continue
        a = math.tau * i / count + tick * 0.03
        px, py = round(x + math.cos(a) * r), round(y + math.sin(a) * r)
        token = accent if accent and i % 3 == 1 else "power.bulwark"
        for surface in (target, light):
            surface.fill(rgb(token), (px, py, 2, 2))
    pygame.draw.circle(light, rgb("px.bulwark.light"), (x, y), r - 2, 1)


def magnet_field(
    target: pygame.Surface,
    light: pygame.Surface,
    center: Point,
    radius: float,
    left: float,
    tick: int,
    rim: str = "power.magnet",
) -> None:
    """A Magnet field: a ring at its reach and dashes running inward toward its center.
    Implosion and Gravity Well draw the same pull with a Burst rim (they end in a blast)."""
    x, y = round(center[0]), round(center[1])
    r = round(radius)
    for surface in (target, light):
        pygame.draw.circle(surface, rgb(rim), (x, y), r, 1)
        pygame.draw.circle(surface, rgb("px.magnet.light"), (x, y), 2)
    for i in range(8):
        a = math.tau * i / 8
        d = r - ((tick * 2 + i * 5) % r)  # each dash runs in, then starts again outside
        ox, oy = math.cos(a), math.sin(a)
        start = (round(x + ox * d), round(y + oy * d))
        end = (round(x + ox * max(3, d - 4)), round(y + oy * max(3, d - 4)))
        for surface in (target, light):
            pygame.draw.line(surface, rgb("power.magnet"), start, end, 1)
    if left < 0.2:  # about to end
        pygame.draw.circle(target, rgb("px.magnet.light"), (x, y), r - 3, 1)


def coil(target: pygame.Surface, light: pygame.Surface, pos: Point, tick: int) -> None:
    """A Tesla Coil: a small green tower with a spark crackling on top."""
    x, y = round(pos[0]), round(pos[1])
    for surface in (target, light):
        surface.fill(rgb("power.bulwark"), (x - 2, y - 6, 5, 8))
        surface.fill(rgb("px.bulwark.light"), (x - 1, y - 5, 1, 6))
    if tick % 6 < 3:
        for surface in (target, light):
            surface.fill(rgb("power.spark"), (x - 1 + (tick % 3) - 1, y - 9, 2, 2))


def wall_of_force(target: pygame.Surface, light: pygame.Surface, a: Point, b: Point) -> None:
    """A Reflector Wave: a bright bar of force with a magenta edge."""
    for surface in (target, light):
        pygame.draw.line(surface, rgb("power.bulwark"), a, b, 3)
        pygame.draw.line(surface, rgb("power.burst"), a, b, 1)


def dome(target: pygame.Surface, light: pygame.Surface, pos: Point, radius: float, tick: int):
    """A Fortress: a ring of shield plates with a soft inner ring."""
    x, y = round(pos[0]), round(pos[1])
    r = round(radius)
    for i in range(24):
        if (i + tick // 6) % 4 == 3:
            continue
        a = math.tau * i / 24
        px, py = round(x + math.cos(a) * r), round(y + math.sin(a) * r)
        for surface in (target, light):
            surface.fill(rgb("power.bulwark"), (px - 1, py - 1, 3, 3))
    pygame.draw.circle(light, rgb("px.bulwark.light"), (x, y), r - 3, 1)


def armor_pips(target: pygame.Surface, light: pygame.Surface, pos: Point, left: int, tick: int):
    """Capacitor Armor: one charge cell orbiting the Surge per hit it can still eat."""
    for i in range(left):
        a = tick * 0.08 + math.tau * i / max(1, left)
        x, y = round(pos[0] + math.cos(a) * 11), round(pos[1] + math.sin(a) * 9)
        for surface in (target, light):
            surface.fill(rgb("power.bulwark"), (x - 1, y - 1, 3, 3))
            surface.fill(rgb("power.spark"), (x, y, 1, 1))


def heavy_spark(target: pygame.Surface, light: pygame.Surface, pos: Point, tick: int) -> None:
    """A Lodestone: a big slow spark with field lines turning around it."""
    x, y = round(pos[0]), round(pos[1])
    for surface in (target, light):
        pygame.draw.circle(surface, rgb("power.spark"), (x, y), 4)
        pygame.draw.circle(surface, rgb("px.spark.light"), (x, y), 2)
    for i in range(4):
        a = tick * 0.15 + math.tau * i / 4
        target.fill(
            rgb("power.magnet"), (round(x + math.cos(a) * 7), round(y + math.sin(a) * 7), 1, 1)
        )


def hook_shot(target: pygame.Surface, light: pygame.Surface, pos: Point, angle: float) -> None:
    """An Ion Hook in flight: a spark with a barb behind it."""
    x, y = round(pos[0]), round(pos[1])
    bx, by = round(x - math.cos(angle) * 5), round(y - math.sin(angle) * 5)
    for surface in (target, light):
        pygame.draw.line(surface, rgb("power.magnet"), (x, y), (bx, by), 1)
        surface.fill(rgb("power.spark"), (x - 1, y - 1, 3, 3))


def fusion_orbit(
    target: pygame.Surface, light: pygame.Surface, pos: Point, radius: float, tick: int, count: int
) -> None:
    """The Mirror Field's broken indigo ring and the bolts orbiting within it."""
    x, y = (round(c) for c in pos)
    r = max(2, round(radius))
    for i in range(4):
        a = tick * 0.035 + i * math.pi / 2
        pygame.draw.arc(target, rgb("power.magnet"), (x - r, y - r, 2 * r, 2 * r), a, a + 0.9)
    for i in range(count):
        a = tick * 0.12 + math.tau * i / count
        px, py = round(x + math.cos(a) * r * 0.65), round(y + math.sin(a) * r * 0.65)
        points = [(px, py - 2), (px + 2, py), (px, py + 2), (px - 2, py)]
        for surface in (target, light):
            pygame.draw.polygon(surface, rgb("px.bulwark.light"), points)
