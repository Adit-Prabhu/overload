"""Pixel characters, all original, all facing right (flip for left). Light comes from the
top left: every material uses a dark, mid and light tone, and the shared dark outline.

- The Surge: a lineworker with a hard-hat headlamp, goggles, a battery pack whose two sockets
  show the equipped powers, and a spark caster.
- Arc Mite: a beetle machine carrying Spark. Its bolt-shaped core is visible on its shell.
- Relay: a boxy relay machine carrying Blink, with a lever switch and a diamond core window.
- Regulator: the rival. A heavy gauge-faced machine with ceramic insulator shoulders, drawn
  procedurally at pixel level, with three protocol poses (Clamp, Insulate, Oscillate).
"""

from __future__ import annotations

import math
from functools import cache

import pygame

from overload.art.palette import rgb, rgba
from overload.art.pixel.grid import add_outline, flipped, render, stack

# Surge -------------------------------------------------------------------------------------

SURGE_LEGEND = {
    "W": "px.helmet.2",
    "H": "px.helmet.1",
    "h": "px.helmet.0",
    "Y": "px.hazard.1",
    "l": "px.lamp.light",
    "S": "px.skin.2",
    "s": "px.skin.1",
    "z": "px.skin.0",
    "G": "px.goggle.0",
    "L": "px.goggle.1",
    "k": "fx.flash",
    "c": "px.jacket.2",
    "J": "px.jacket.2",
    "j": "px.jacket.1",
    "q": "px.jacket.0",
    "R": "px.helmet.2",
    "P": "px.pack.1",
    "p": "px.pack.0",
    "Q": "px.pack.0",
    "E": "px.pack.0",
    "u": "px.wood.1",
    "U": "px.dial.0",
    "N": "px.pants.1",
    "n": "px.pants.0",
    "B": "px.boots.1",
    "b": "px.boots.0",
    "F": "player.core",
    "f": "player.halo",
}

_SURGE_TOP = [
    ".....hhhh.....",
    "...hHHWWWHh...",
    "..hHWWWWWWWh..",
    "..hHWWWWWWWHl.",
    "..hYYYYYYYYYl.",
    ".hhhhhhhhhhhh.",
    "..zSSSSSSSSs..",
    "..zGGLLGGLLGs.",
    "..zsGkLGGkLGs.",
    "..zssssssssz..",
    "...zssszzsz...",
    ".PPcJJJJJJc...",
    "PPPqjJJJJjjFf.",
    "PQPqjRRRRRjFF.",
    "PEPqjjJJJjjf..",
    ".PPquuUuuuq...",
]
_SURGE_LEGS = {
    "stand": ["...nNNNNNn....", "...nNN..NNn...", "...bBB..bBB...", "...bbb..bbb..."],
    "stride": ["...nNNNNNn....", "..nNN....NNn..", "..bBB....bBB..", "..bbb.....bbb."],
    "pass": ["...nNNNNNn....", "....nNNNn.....", "....bBBBb.....", "....bbbbb....."],
    "stride2": ["...nNNNNNn....", "...nNN.NNn....", "..bBB...bBB...", "..bbb...bbb..."],
}
_SURGE_BLANK = [".............."]
# Pack socket pixels (inside the 1 px outline padding), recolored with the equipped powers.
SURGE_SOCKETS = ((2, 15), (2, 16))


def _surge_rows(legs: str, raised: bool) -> list[str]:
    body = stack(_SURGE_TOP, _SURGE_LEGS[legs])
    return stack(body, _SURGE_BLANK) if raised else stack(_SURGE_BLANK, body)


@cache
def app_icon() -> pygame.Surface:
    """32 x 32 window and app icon (MK-02): Surge hard hat with a glowing spark bolt."""
    rows = [
        "................",
        "....hhhhhhhh....",
        "..hhHWWWYWWWHh..",
        ".hHWWWWYYWWWWWh.",
        ".hHWWWYYWWWWWWh.",
        ".hHWWYYYYYYWWWh.",
        ".hHWWWWYYWWWWWh.",
        ".hYYYYYYlYYYYYh.",
        "hhhhhhhhhhhhhhhh",
        ".hhhhhhhhhhhhhh.",
        "..zSSSSSSSSSSz..",
        "..zGGLLGGLLGGz..",
        "..zGkLGGkLGGSz..",
        "...zssssssssz...",
        "....zzzzzzzz....",
        "................",
    ]
    legend = {**SURGE_LEGEND, "Y": "power.spark", "l": "px.spark.light"}
    canvas = pygame.Surface((16, 16), pygame.SRCALPHA)
    canvas.fill(rgb("px.outline"))
    pygame.draw.rect(canvas, rgb("px.wall.2"), (0, 0, 16, 16), 1)
    art = render(rows, legend, outline=None)
    canvas.blit(art, (0, 0))
    return pygame.transform.scale_by(canvas, 2)


@cache
def surge_frames() -> dict[str, tuple[pygame.Surface, ...]]:
    """Idle (2 frames, a breathing bob) and walk (4 frames). All face right."""

    def frame(legs: str, raised: bool) -> pygame.Surface:
        return render(_surge_rows(legs, raised), SURGE_LEGEND)

    return {
        "idle": (frame("stand", False), frame("stand", True)),
        "walk": (
            frame("stride", False),
            frame("pass", True),
            frame("stride2", False),
            frame("pass", True),
        ),
    }


def surge(
    state: str, tick: int, facing_left: bool, sockets: tuple[str | None, str | None] = (None, None)
) -> pygame.Surface:
    frames = surge_frames()[state]
    rate = 16 if state == "idle" else 6
    index = (tick // rate) % len(frames)
    image = frames[index]
    if any(sockets):
        image = image.copy()
        raised = state == "walk" and index % 2 == 1 or state == "idle" and index == 1
        for (x, y), power in zip(SURGE_SOCKETS, sockets, strict=True):
            if power:
                image.set_at((x, y - (1 if raised else 0) + 1), rgb(f"power.{power}"))
    return flipped(image) if facing_left else image


_CASTER = [
    "..ddd.....",
    ".dMXXXXXwF",
    "dMMMMMMXwF",
    "dmmMMd....",
    ".dmd......",
]
_CASTER_LEGEND = {
    "d": "px.bot.0",
    "m": "px.bot.1",
    "M": "px.bot.2",
    "X": "px.bot.3",
    "w": "player.halo",
    "F": "player.core",
}


@cache
def caster() -> pygame.Surface:
    """The spark caster the Surge holds. Rotated toward the aim at draw time."""
    return render(_CASTER, _CASTER_LEGEND)


# Arc Mite ----------------------------------------------------------------------------------

MITE_LEGEND = {
    "d": "px.bot.0",
    "m": "px.bot.1",
    "M": "px.bot.2",
    "X": "px.bot.3",
    "W": "px.dial.0",
    "Y": "power.spark",
    "y": "px.spark.light",
    "a": "px.spark.light",
    "E": "px.hostile.3",
    "e": "px.hostile.2",
    "r": "px.hostile.1",
}
_MITE_BODY = [
    "...............a..",
    "........dd....a...",
    "......dmMMMd.a....",
    "....dmMXWXMMMdd...",
    "...dmMXyYYXMMMMd..",
    "..dmMMYYyYYMMMeEd.",
    "..dmMMMyYYMMMMeed.",
    ".dmmMMMMYMMMMMMmmd",
    ".dmmmmmmmmmmmmmmd.",
    "..ddrrddrrddrrdd..",
]
_MITE_LEGS = (
    ["..r..r..r..r..r...", ".r..r..r..r..r...."],
    [".r..r..r..r..r....", "..r..r..r..r..r..."],
)


@cache
def arc_mite_frames() -> tuple[pygame.Surface, ...]:
    return tuple(render(stack(_MITE_BODY, legs), MITE_LEGEND) for legs in _MITE_LEGS)


def arc_mite(tick: int, facing_left: bool, charging: bool = False) -> pygame.Surface:
    frames = arc_mite_frames()
    image = frames[(tick // (3 if charging else 8)) % len(frames)]
    return flipped(image) if facing_left else image


# Relay -------------------------------------------------------------------------------------

RELAY_LEGEND = {
    "d": "px.bot.0",
    "m": "px.bot.1",
    "M": "px.bot.2",
    "X": "px.bot.3",
    "W": "px.dial.0",
    "E": "px.hostile.3",
    "e": "px.hostile.2",
    "r": "px.hostile.1",
    "K": "power.blink",
    "k": "px.blink.light",
    "A": "px.led.amber",
}
_RELAY = [
    "..W..........W..",
    "..X.dddddd...X..",
    "..MddXXXXXdd.M..",
    ".dMMMMMMMMMMMMd.",
    ".dMXXXXXXXXXXMd.",
    ".dMXmmmmmmmmXMd.",
    ".dMXmEemmeEmXMd.",
    ".dMXmmmmmmmmXMd.",
    ".dMMMMMMMMMMMMd.",
    ".dMMMmmmKmmmMAd.",
    ".dMMmmmKkKmmmMd.",
    ".dMmmmKkkkKmmMd.",
    ".dMMmmmKkKmmmMd.",
    ".dMMMmmmKmmmMMd.",
    ".dMMMMMMMMMMMMd.",
    ".dddddddddddddd.",
    "..rXXr....rXXr..",
    "..dddd....dddd..",
]
_RELAY_LEVER_UP = ["..W..........W..", "..X.dddddd...X..", "..MddXXXXXdd.M.."]
_RELAY_LEVER_DOWN = ["..W..........W..", "..X..........X..", "..MdddXXXXXXdM.."]


@cache
def relay_frames() -> tuple[pygame.Surface, ...]:
    up = render(_RELAY, RELAY_LEGEND)
    down = render(stack(_RELAY_LEVER_DOWN, _RELAY[3:]), RELAY_LEGEND)
    return (up, down)


def relay(facing_left: bool, arming: bool = False) -> pygame.Surface:
    """The lever is up while the Relay idles or aims and flips down while its landing
    diamond is showing, so the switch itself announces the coming blink."""
    image = relay_frames()[1 if arming else 0]
    return flipped(image) if facing_left else image


# Regulator ---------------------------------------------------------------------------------

REGULATOR_SIZE = (44, 40)
GAUGE_CENTER = (22, 17)
GAUGE_RADIUS = 6


def _fill(s: pygame.Surface, token: str, x: int, y: int, w: int = 1, h: int = 1) -> None:
    s.fill(rgb(token), (x, y, w, h))


def _insulator_shoulder(s: pygame.Surface, x: int) -> None:
    _fill(s, "px.bot.3", x + 1, 0, 3, 1)
    for i, y in enumerate(range(1, 9, 2)):
        inset = 0 if i % 2 == 0 else 1
        _fill(s, "px.ceramic.1", x + inset, y, 5 - 2 * inset, 1)
        _fill(s, "px.ceramic.2", x + inset, y, 2, 1)
        _fill(s, "px.ceramic.0", x + inset, y + 1, 5 - 2 * inset, 1)
    _fill(s, "px.bot.1", x, 9, 5, 2)


@cache
def regulator_body() -> pygame.Surface:
    w, h = REGULATOR_SIZE
    s = pygame.Surface((w, h), pygame.SRCALPHA)
    # Treads.
    for x in (4, 26):
        _fill(s, "px.bot.0", x, 33, 14, 7)
        _fill(s, "px.bot.3", x, 33, 14, 1)
        for k in range(x + 1, x + 14, 3):
            _fill(s, "px.bot.2", k, 35, 2, 3)
    # Hazard-striped hip.
    for x in range(8, 36):
        for y in range(29, 33):
            token = "px.hazard.1" if ((x + y) // 2) % 2 == 0 else "px.hazard.0"
            _fill(s, token, x, y)
    # Shoulder insulators and cables.
    _insulator_shoulder(s, 6)
    _insulator_shoulder(s, 33)
    for x0, x1 in ((8, 12), (35, 31)):
        step = 1 if x1 > x0 else -1
        for i, x in enumerate(range(x0, x1, step)):
            _fill(s, "px.bot.0", x, 9 + i // 2, 1, 1)
    # Chassis: orange shell, lit from the top left.
    _fill(s, "px.hostile.2", 3, 9, 38, 21)
    _fill(s, "px.hostile.3", 4, 9, 36, 2)
    _fill(s, "px.hostile.3", 3, 10, 1, 18)
    _fill(s, "px.hostile.1", 3, 27, 38, 3)
    _fill(s, "px.hostile.1", 40, 10, 1, 18)
    _fill(s, "px.hostile.0", 3, 29, 38, 1)
    for x in (3, 40):
        s.set_at((x, 9), rgba("fx.none", 0))
    # Dark faceplate.
    _fill(s, "px.bot.2", 6, 11, 32, 16)
    _fill(s, "px.bot.1", 7, 12, 30, 14)
    # Vents on the left, status lights on the right.
    for y in range(13, 25, 2):
        _fill(s, "px.bot.0", 9, y, 6, 1)
        _fill(s, "px.bot.3", 9, y + 1, 6, 1)
    for i, token in enumerate(("px.hostile.3", "px.led.amber", "power.blink")):
        _fill(s, "px.bot.0", 32, 14 + i * 4, 3, 3)
        _fill(s, token, 33, 15 + i * 4)
    # Gauge face.
    cx, cy = GAUGE_CENTER
    pygame.draw.circle(s, rgb("px.bot.3"), (cx, cy), GAUGE_RADIUS + 2)
    pygame.draw.circle(s, rgb("px.bot.0"), (cx, cy), GAUGE_RADIUS + 1)
    pygame.draw.circle(s, rgb("px.dial.1"), (cx, cy), GAUGE_RADIUS)
    pygame.draw.circle(s, rgb("px.dial.0"), (cx, cy), GAUGE_RADIUS, 1)
    for dx, dy in ((-4, 2), (-4, -1), (-2, -4), (1, -5), (4, -3)):
        _fill(s, "px.bot.2", cx + dx, cy + dy)
    for dx, dy in ((3, -4), (4, -3), (5, -2), (4, -4)):
        _fill(s, "hostile.danger", cx + dx, cy + dy)
    add_outline(s, "px.outline")
    return s


@cache
def clamp_arm() -> pygame.Surface:
    """Upper and lower pincers that bite forward."""
    s = pygame.Surface((16, 26), pygame.SRCALPHA)
    for flip_y in (False, True):
        pincer = pygame.Surface((16, 12), pygame.SRCALPHA)
        _fill(pincer, "px.bot.2", 0, 2, 5, 6)
        _fill(pincer, "px.bot.3", 0, 2, 5, 1)
        for i in range(10):
            _fill(pincer, "px.hostile.2", 4 + i, 3 + i // 2, 3, 3)
            _fill(pincer, "px.hostile.3", 4 + i, 3 + i // 2, 3, 1)
        _fill(pincer, "px.hostile.1", 12, 8, 3, 2)
        if flip_y:
            pincer = pygame.transform.flip(pincer, False, True)
            s.blit(pincer, (0, 14))
        else:
            s.blit(pincer, (0, 0))
    add_outline(s, "px.outline")
    return s


@cache
def insulate_plate() -> pygame.Surface:
    """A hatched shield plate held at the side."""
    w, h = 9, 24
    s = pygame.Surface((w, h), pygame.SRCALPHA)
    _fill(s, "px.bot.3", 0, 0, w, h)
    _fill(s, "px.hostile.0", 1, 1, w - 2, h - 2)
    for y in range(1, h - 1):
        for x in range(1, w - 1):
            if (x + y) % 3 == 0:
                _fill(s, "hostile.danger", x, y)
    _fill(s, "px.dial.0", 0, 0, w, 1)
    add_outline(s, "px.outline")
    return s


@cache
def fin(lit: bool = False) -> pygame.Surface:
    """A side thruster fin with a nozzle, used by the Oscillate protocol. Lit fins glow
    before a volley."""
    w, h = 10, 18
    s = pygame.Surface((w, h), pygame.SRCALPHA)
    for i in range(h):
        span = max(1, w - abs(i - h // 2) - 2)
        _fill(s, "px.lamp.light" if lit else "px.hostile.2", 0, i, span, 1)
        _fill(s, "px.hostile.3", 0, i, 1, 1)
    _fill(s, "px.bot.2", 0, h // 2 - 2, 4, 5)
    _fill(s, "px.lamp.light", 0, h // 2 - 1, 1, 3)
    add_outline(s, "px.outline")
    return s


def regulator(
    protocol: str, facing_left: bool, needle: float | None = None, lit: bool = False
) -> pygame.Surface:
    """Body plus protocol pose on one canvas. Pose silhouettes differ: Clamp has pincers
    forward, Insulate has hatched plates on both sides, Oscillate has side thruster fins.
    `needle` (radians, screen space) points the gauge needle, usually at the Surge."""
    body = regulator_body()
    bw, bh = body.get_size()
    if protocol == "clamp":
        arm = clamp_arm()
        canvas = pygame.Surface((bw + arm.get_width() - 4, bh), pygame.SRCALPHA)
        canvas.blit(arm, (bw - 5, 6))
        offset = 0
    elif protocol == "insulate":
        plate = insulate_plate()
        pw = plate.get_width()
        canvas = pygame.Surface((bw + 2 * pw - 2, bh), pygame.SRCALPHA)
        canvas.blit(plate, (0, 8))
        canvas.blit(plate, (bw + pw - 3, 8))
        offset = pw - 1
    elif protocol == "oscillate":
        right = fin(lit)
        left = flipped(right)
        fw = right.get_width()
        canvas = pygame.Surface((bw + 2 * fw - 4, bh), pygame.SRCALPHA)
        canvas.blit(left, (0, 10))
        canvas.blit(right, (bw + fw - 4, 10))
        offset = fw - 2
    else:
        raise KeyError(protocol)
    canvas.blit(body, (offset, 0))
    if needle is not None:
        angle = math.pi - needle if facing_left else needle
        cx, cy = offset + GAUGE_CENTER[0] + 1, GAUGE_CENTER[1] + 1
        tip = (
            round(cx + math.cos(angle) * (GAUGE_RADIUS - 1)),
            round(cy + math.sin(angle) * (GAUGE_RADIUS - 1)),
        )
        pygame.draw.line(canvas, rgb("px.outline"), (cx, cy), tip, 1)
        canvas.set_at((cx, cy), rgb("hostile.danger"))
    return flipped(canvas) if facing_left else canvas
