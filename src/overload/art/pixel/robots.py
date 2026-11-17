"""The robot roster (overhaul, Nov 17): chibi maintenance robots, all original, facing right.

Every robot has a round chunky body, a dark visor with a glowing hostile eye, and, if it
carries a power, a core window showing that power's symbol (art direction rule 4: you can see
what you will steal). Light comes from the top left. Hostile shots stay in hostile colors and
differ by shape: the Drone's spiked spark ball (effects.hostile_bolt), the Relay Bot's diamond
shard, the Sentry's shell, the Breaker's shockwave ring, the Regulator's needles and orbs.
"""

from __future__ import annotations

import math
from functools import cache

import pygame

from overload.art.palette import rgb
from overload.art.pixel import actors
from overload.art.pixel.grid import add_outline, flipped, render

LEGEND = {
    "d": "px.bot.0",
    "m": "px.bot.1",
    "M": "px.bot.2",
    "X": "px.bot.3",
    "W": "px.dial.0",
    "w": "px.dial.1",
    "v": "px.goggle.0",
    "E": "hostile.danger",
    "e": "px.hostile.3",
    "R": "px.hostile.0",
    "r": "px.hostile.1",
    "o": "px.hostile.2",
    "O": "px.hostile.3",
    "c": "px.ceramic.0",
    "C": "px.ceramic.1",
    "Q": "px.ceramic.2",
    "H": "px.hazard.1",
    "h": "px.hazard.0",
    "g": "px.helmet.0",
    "G": "px.helmet.1",
    "Z": "px.helmet.2",
    "Y": "power.spark",
    "y": "px.spark.light",
    "K": "power.blink",
    "k": "px.blink.light",
    "U": "power.burst",
    "u": "px.burst.light",
    "A": "px.led.amber",
    "j": "px.lamp",
    "J": "px.lamp.light",
}

# Arc Drone: an orange hover drone with a rotor and one big eye. Carries Spark.
_DRONE = [
    "...dXXXXXXXXXXXd...",
    "........dXd........",
    "......doOOOod......",
    "....doOOOOOOOod....",
    "...doOOOOOOOoord...",
    "..doOvvvvvvvvvord..",
    "..dOvvvWEEEevvvrd..",
    "..dOvvvEEwEEvvvrd..",
    "..dOvvveEEEevvvrd..",
    "..doOvvvvvvvvvord..",
    "...doOOOOOOOoord...",
    "....dmMMMYMMMmd....",
    "....dmMMYyYMMmd....",
    ".....dmMMYMMmd.....",
    "...dXd.......dXd...",
]
_DRONE_JETS = (
    ["...jJj.......jJj...", "....j.........j...."],
    ["...JjJ.......JjJ...", "...j...........j..."],
)

# Relay Bot: a ceramic-blue box bot with a lever switch, two eyes and a diamond window.
# Carries Blink. The lever flips down while its landing diamond shows.
_RELAY_TOP = {
    "up": [".W...............", ".X...............", ".X..............."],
    "down": [".................", ".................", "WXX.............."],
}
_RELAY = [
    "..dQQCCCCCCCCcd..",
    ".dQCCCCCCCCCCccd.",
    ".dCvvvvvvvvvvvcd.",
    ".dCvEEvvvvvEEvcd.",
    ".dCveEvvvvveEvcd.",
    ".dCvvvvvvvvvvvcd.",
    ".dCCCCCCKCCCCccd.",
    ".dCCCCCKkKCCCAcd.",
    ".dcCCCCCKCCCCccd.",
    "..dcccccccccccd..",
    ".dXXXXd...dXXXXd.",
    ".dMdMdd...dMdMdd.",
]

# Breaker: a hazard-yellow construction brute with huge fists and a Burst ring on its chest.
# Carries Burst. Raising its fists is the tell before the slam.
_BREAKER_LEGS = [
    ".....dHhHhHhHhHhHd.....",
    "......dXXMd.dXXMd......",
    ".....dddddd.dddddd.....",
]
_BREAKER = {
    "rest": [
        ".........dXWXd.........",
        "........dXvvvMd........",
        "........dvEEEvd........",
        "........dMMMMMd........",
        ".....dHHhHHhHHhHHd.....",
        "..dXXdHHHHHHHHHHHdXXd..",
        ".dXWXdHHHmmUmmHHHdXMXd.",
        ".dXWXdHHmmUuUmmHHdXMXd.",
        ".dXXXdHHmUuuuUmHHdXXXd.",
        ".dXXXdHHmmUuUmmHHdXXXd.",
        "..dddHHHHHmmmHHHHHddd..",
    ],
    "raise": [
        ".dXWXd...dXWXd...dXMXd.",
        ".dXWXd..dXvvvMd..dXMXd.",
        ".dXXXd..dvEEEvd..dXXXd.",
        "..dHd...dMMMMMd...dHd..",
        "..dHHdHHhHHhHHhHHdHHd..",
        ".....dHHHHHHHHHHHd.....",
        ".....dHHHmmUmmHHHd.....",
        ".....dHHmmUuUmmHHd.....",
        ".....dHHmUuuuUmHHd.....",
        ".....dHHmmUuUmmHHd.....",
        ".....dddHHmmmHHddd.....",
    ],
    # The impact: crouched, both fists driven into the floor, dust kicking up.
    "slam": [
        ".......................",
        ".......................",
        ".........dXWXd.........",
        "........dXvvvMd........",
        "........dvEEEvd........",
        "...dHHHdMMMMMMMdHHHd...",
        "..dHd.dHHmmUmmHHd.dHd..",
        "..dHd.dHmmUuUmmHd.dHd..",
        ".dXWXddHmUuuuUmHddXMXd.",
        "wdXXXddHHmmUmmHHddXXXdw",
        "w..w..dHHHmmmHHHd..w..w",
    ],
}

# Sweeper: a small white dome with a red stripe and a striped bumper. Rushes. Carries
# nothing.
_SWEEPER = [
    ".....dZZZd.....",
    "...dZZGGGGgd...",
    "..dZGGGGGGGgd..",
    "..dooooooooord.",
    "..dGvvvEvvvgd..",
    ".dGGGGGGGGGGgd.",
    ".HhHhHhHhHhHhH.",
]
_SWEEPER_WHEELS = (
    ["dXd.........dXd", ".d...........d."],
    ["dMd.........dMd", ".d...........d."],
)

# Sentry: a dark turret on a tripod with an orange barrel. Long tell, slow shell. Carries
# nothing.
_SENTRY = [
    ".....dXXXXd......",
    "....dXWWMMMd.....",
    "....dXvvEvvMdoooO",
    "....dXvvvvvMdrrro",
    "....dmMMMMMmd....",
    "......dHhHd......",
    ".....dXd.dXd.....",
    "....dXd...dXd....",
    "...ddd.....ddd...",
]


@cache
def drone_frames() -> tuple[pygame.Surface, ...]:
    return tuple(render(_DRONE + jets, LEGEND) for jets in _DRONE_JETS)


def drone(tick: int, facing_left: bool) -> pygame.Surface:
    image = drone_frames()[(tick // 6) % 2]
    return flipped(image) if facing_left else image


@cache
def relay_bot_frames() -> dict[str, pygame.Surface]:
    return {state: render(top + _RELAY, LEGEND) for state, top in _RELAY_TOP.items()}


def relay_bot(facing_left: bool, arming: bool = False) -> pygame.Surface:
    image = relay_bot_frames()["down" if arming else "up"]
    return flipped(image) if facing_left else image


@cache
def breaker_frames() -> dict[str, pygame.Surface]:
    return {pose: render(rows + _BREAKER_LEGS, LEGEND) for pose, rows in _BREAKER.items()}


def breaker(facing_left: bool, raising: bool = False, slamming: bool = False) -> pygame.Surface:
    image = breaker_frames()["slam" if slamming else "raise" if raising else "rest"]
    return flipped(image) if facing_left else image


@cache
def sweeper_frames() -> tuple[pygame.Surface, ...]:
    return tuple(render(_SWEEPER + wheels, LEGEND) for wheels in _SWEEPER_WHEELS)


def sweeper(tick: int, facing_left: bool, revving: bool = False) -> pygame.Surface:
    image = sweeper_frames()[(tick // (2 if revving else 6)) % 2]
    return flipped(image) if facing_left else image


@cache
def sentry_frame() -> pygame.Surface:
    return render(_SENTRY, LEGEND)


def sentry(facing_left: bool) -> pygame.Surface:
    return flipped(sentry_frame()) if facing_left else sentry_frame()


# The Regulator mech -----------------------------------------------------------------------

MECH_SIZE = (36, 42)
MECH_GAUGE = (18, 23)


def _fill(s: pygame.Surface, token: str, x: int, y: int, w: int = 1, h: int = 1) -> None:
    s.fill(rgb(token), (x, y, w, h))


@cache
def mech_body() -> pygame.Surface:
    """A big armored control mech: a domed head with a red visor, an orange chest with the
    gauge face that tracks the Surge, ceramic insulator shoulders, striped hips, stubby
    legs. Protocol arms attach at the shoulders."""
    w, h = MECH_SIZE
    s = pygame.Surface((w, h), pygame.SRCALPHA)
    # Legs and feet.
    for x in (8, 21):
        _fill(s, "px.bot.1", x + 1, 33, 5, 5)
        _fill(s, "px.bot.3", x + 1, 33, 1, 5)
        _fill(s, "px.bot.0", x - 1, 38, 9, 4)
        _fill(s, "px.bot.2", x - 1, 38, 9, 1)
    # Hips, hazard striped.
    for x in range(7, 29):
        for y in (30, 31, 32):
            _fill(s, "px.hazard.1" if ((x + y) // 2) % 2 == 0 else "px.hazard.0", x, y)
    # Chest shell, lit from the top left.
    _fill(s, "px.hostile.2", 4, 13, 28, 18)
    _fill(s, "px.hostile.3", 5, 13, 26, 2)
    _fill(s, "px.hostile.3", 4, 14, 1, 14)
    _fill(s, "px.hostile.1", 4, 28, 28, 3)
    _fill(s, "px.hostile.1", 31, 14, 1, 14)
    # Insulator shoulders.
    for x in (1, 30):
        for i, y in enumerate(range(12, 21, 2)):
            inset = i % 2
            _fill(s, "px.ceramic.1", x + inset, y, 5 - 2 * inset, 1)
            _fill(s, "px.ceramic.2", x + inset, y, 2, 1)
            _fill(s, "px.ceramic.0", x + inset, y + 1, 5 - 2 * inset, 1)
    # Head: a gunmetal dome with a wide red visor and two eyes.
    _fill(s, "px.bot.2", 9, 2, 18, 11)
    _fill(s, "px.bot.3", 10, 2, 16, 2)
    _fill(s, "px.bot.3", 9, 3, 1, 8)
    _fill(s, "px.bot.1", 9, 11, 18, 2)
    _fill(s, "px.goggle.0", 11, 5, 14, 5)
    _fill(s, "hostile.danger", 13, 7, 3, 2)
    _fill(s, "hostile.danger", 20, 7, 3, 2)
    _fill(s, "px.hostile.3", 13, 7, 1, 1)
    _fill(s, "px.hostile.3", 20, 7, 1, 1)
    _fill(s, "px.bot.3", 17, 0, 2, 2)
    _fill(s, "px.led.amber", 17, 0, 2, 1)
    # Gauge face on the chest.
    cx, cy = MECH_GAUGE
    pygame.draw.circle(s, rgb("px.bot.3"), (cx, cy), 7)
    pygame.draw.circle(s, rgb("px.bot.0"), (cx, cy), 6)
    pygame.draw.circle(s, rgb("px.dial.1"), (cx, cy), 5)
    for dx, dy in ((-3, 1), (-3, -2), (-1, -4), (2, -4), (4, -2)):
        _fill(s, "px.bot.2", cx + dx, cy + dy)
    for dx, dy in ((3, -3), (4, -2), (3, -4)):
        _fill(s, "hostile.danger", cx + dx, cy + dy)
    # Status lights.
    for i, token in enumerate(("px.hostile.3", "px.led.amber", "px.ceramic.2")):
        _fill(s, token, 7, 17 + i * 3)
    add_outline(s, "px.outline")
    return s


def regulator_mech(
    protocol: str, facing_left: bool, needle: float | None = None, lit: bool = False
) -> pygame.Surface:
    """The mech with its protocol arms: Clamp pincers, Insulate plates or Oscillate fins."""
    body = mech_body()
    bw, bh = body.get_size()
    if protocol == "clamp":
        arm = actors.clamp_arm()
        canvas = pygame.Surface((bw + arm.get_width() - 6, bh), pygame.SRCALPHA)
        canvas.blit(arm, (bw - 7, 12))
        offset = 0
    elif protocol == "insulate":
        plate = actors.insulate_plate()
        pw = plate.get_width()
        canvas = pygame.Surface((bw + 2 * pw - 4, bh), pygame.SRCALPHA)
        canvas.blit(plate, (0, 13))
        canvas.blit(plate, (bw + pw - 6, 13))
        offset = pw - 2
    elif protocol == "oscillate":
        right = actors.fin(lit)
        fw = right.get_width()
        canvas = pygame.Surface((bw + 2 * fw - 4, bh), pygame.SRCALPHA)
        canvas.blit(flipped(right), (0, 14))
        canvas.blit(right, (bw + fw - 6, 14))
        offset = fw - 2
    else:
        raise KeyError(protocol)
    canvas.blit(body, (offset, 0))
    if needle is not None:
        angle = math.pi - needle if facing_left else needle
        cx, cy = offset + MECH_GAUGE[0] + 1, MECH_GAUGE[1] + 1
        tip = (round(cx + math.cos(angle) * 4), round(cy + math.sin(angle) * 4))
        pygame.draw.line(canvas, rgb("px.outline"), (cx, cy), tip, 1)
        canvas.set_at((cx, cy), rgb("hostile.danger"))
    return flipped(canvas) if facing_left else canvas


# Hostile shots: one shape per attacker ------------------------------------------------------

_SHARD = [
    "..E..",
    ".eEe.",
    "eEwEe",
    ".eEe.",
    "..E..",
]
_SHELL = [
    "..rrr..",
    ".rooor.",
    "roeEeor",
    "roEwEor",
    "roeEeor",
    ".rooor.",
    "..rrr..",
]
_NEEDLE = [
    "rooeeEw",
    ".rooeE.",
]
_ORB = [
    "...rrr...",
    ".rr...rr.",
    ".r.oeo.r.",
    "r.oeEeo.r",
    "r.eEwEe.r",
    "r.oeEeo.r",
    ".r.oeo.r.",
    ".rr...rr.",
    "...rrr...",
]


@cache
def shard() -> pygame.Surface:
    return render(_SHARD, LEGEND, outline=None)


@cache
def shell() -> pygame.Surface:
    return render(_SHELL, LEGEND, outline=None)


@cache
def needle_dart() -> pygame.Surface:
    return render(_NEEDLE, LEGEND, outline=None)


@cache
def orb() -> pygame.Surface:
    return render(_ORB, LEGEND, outline=None)


def shockwave(target: pygame.Surface, center: tuple[float, float], radius: float) -> None:
    """The Breaker's slam: a ring of dashes that runs along the floor. Drawn as the true
    circle the simulation hits with."""
    cx, cy = center
    count = max(8, int(radius * 1.2))
    for i in range(count):
        if i % 3 == 2:
            continue
        a = 2 * math.pi * i / count
        x, y = round(cx + math.cos(a) * radius), round(cy + math.sin(a) * radius)
        target.fill(rgb("hostile.danger"), (x, y, 2, 1))
