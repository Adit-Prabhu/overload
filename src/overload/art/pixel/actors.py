"""Pixel characters: the Surge (a lineworker with a siphon glove), the Arc Mite, the Relay and
the Regulator with its three protocol poses. All sprites face right. Flip for left.
"""

from __future__ import annotations

from functools import cache

import pygame

from overload.art.pixel.grid import flipped, render, stack

LEGEND = {
    # Surge
    "W": "px.helmet.2",
    "H": "px.helmet.1",
    "h": "px.helmet.0",
    "S": "px.skin.2",
    "s": "px.skin.1",
    "z": "px.skin.0",
    "G": "px.goggle.0",
    "L": "px.goggle.1",
    "J": "px.jacket.2",
    "j": "px.jacket.1",
    "q": "px.jacket.0",
    "R": "px.helmet.2",
    "P": "px.pack.1",
    "p": "px.pack.0",
    "C": "player.core",
    "N": "px.pants.1",
    "n": "px.pants.0",
    "B": "px.boots.1",
    "b": "px.boots.0",
    "F": "player.core",
    # Machines
    "d": "px.bot.0",
    "m": "px.bot.1",
    "M": "px.bot.2",
    "X": "px.bot.3",
    "x": "px.hostile.0",
    "r": "px.hostile.1",
    "e": "px.hostile.2",
    "E": "px.hostile.3",
    "D": "px.dial.1",
    "c": "px.dial.0",
    "!": "hostile.danger",
    # Powers
    "Y": "power.spark",
    "y": "px.spark.light",
    "K": "power.blink",
    "k": "px.blink.light",
    "U": "power.burst",
    "u": "px.burst.light",
}

# Surge -------------------------------------------------------------------------------------

_HEAD = [
    "....hHHHh...",
    "..hHWWWWHh..",
    ".hHWWWWWWWh.",
    ".hHWWWWWWWHh",
    "hhhhhhhhhhhh",
    ".zSSSSSSSSs.",
    ".zGLLGSGLLG.",
    ".zsGGGsGGGs.",
    "..zsssssss..",
    "...zzsszz...",
]
_TORSO = [
    ".PPqjJJJJjF.",
    "PCPqjRRRRjFF",
    ".PPqjjJJjj..",
    "...qnNNNnq..",
]
_LEGS = {
    "stand": ["...NN..NN...", "...BB..BB..."],
    "stride": ["..NN....NN..", "..BB.....BB."],
    "pass": ["....NNNN....", "....BBbB...."],
    "stride2": ["...NN.NN....", "..BB..BB...."],
}
_BLANK = ["............"]


def _surge_rows(legs: str, raised: bool) -> list[str]:
    body = stack(_HEAD, _TORSO, _LEGS[legs])
    return stack(body, _BLANK) if raised else stack(_BLANK, body)


@cache
def surge_frames() -> dict[str, tuple[pygame.Surface, ...]]:
    """Idle (2 frames, a breathing bob) and walk (4 frames). All face right."""
    def frame(legs: str, raised: bool) -> pygame.Surface:
        return render(_surge_rows(legs, raised), LEGEND)

    return {
        "idle": (frame("stand", False), frame("stand", True)),
        "walk": (frame("stride", False), frame("pass", True), frame("stride2", False),
                 frame("pass", True)),
    }


def surge(state: str, tick: int, facing_left: bool) -> pygame.Surface:
    frames = surge_frames()[state]
    rate = 16 if state == "idle" else 6
    image = frames[(tick // rate) % len(frames)]
    return flipped(image) if facing_left else image


_CASTER = [
    "...pp....",
    "pPPMMMXXC",
    "pPPMMMMMF",
    ".pp......",
    "..p......",
]


@cache
def caster() -> pygame.Surface:
    """The spark caster the Surge holds. Rotated toward the aim at draw time."""
    return render(_CASTER, LEGEND)


# Arc Mite ----------------------------------------------------------------------------------

_MITE_BODY = [
    ".....mmmm.....",
    "...mMMMMMMm...",
    "..mMMMyYMMMm..",
    ".mMMMyYMMMMMm.",
    "mMMMYYYYMMMEEm",
    "mMMMMMYyMMMEem",
    ".mMMMMYMMMMMm.",
    "..mmmmmmmmmm..",
]
_MITE_LEGS = (
    ["..r..r..r..r..", ".r..r..r..r..."],
    [".r..r..r..r...", "..r..r..r..r.."],
)


@cache
def arc_mite_frames() -> tuple[pygame.Surface, ...]:
    return tuple(render(stack(_MITE_BODY, legs), LEGEND) for legs in _MITE_LEGS)


def arc_mite(tick: int, facing_left: bool, charging: bool = False) -> pygame.Surface:
    frames = arc_mite_frames()
    image = frames[(tick // (3 if charging else 8)) % len(frames)]
    return flipped(image) if facing_left else image


# Relay -------------------------------------------------------------------------------------

_RELAY = [
    "..X.......X..",
    "..M.......M..",
    ".mMMMMMMMMMm.",
    ".mMXXXXXXXMm.",
    ".mMXEXXXEXMm.",
    ".mMMMMKMMMMm.",
    ".mMMMKkKMMMm.",
    ".mMMKkkkKMMm.",
    ".mMMMKkKMMMm.",
    ".mMMMMKMMMMm.",
    ".mmmmmmmmmmm.",
    "..rr.....rr..",
]
_RELAY_SQUASH = [
    "..X.......X..",
    ".mMMMMMMMMMm.",
    ".mMXXXXXXXMm.",
    ".mMXEXXXEXMm.",
    ".mMMMMKMMMMm.",
    ".mMMMKkKMMMm.",
    ".mMMKkkkKMMm.",
    ".mMMMKkKMMMm.",
    ".mMMMMKMMMMm.",
    ".mmmmmmmmmmm.",
    "..rr.....rr..",
]


@cache
def relay_frames() -> tuple[pygame.Surface, ...]:
    tall = render(_RELAY, LEGEND)
    squash = render(stack(["............."], _RELAY_SQUASH), LEGEND)
    return (tall, squash)


def relay(tick: int, facing_left: bool) -> pygame.Surface:
    frames = relay_frames()
    image = frames[(tick // 10) % len(frames)]
    return flipped(image) if facing_left else image


# Regulator ---------------------------------------------------------------------------------

_GAUGE = [
    "....cccc....",
    "..ccDDDDcc..",
    ".cDDDDDD!!c.",
    ".cDDDDDd!!c.",
    "cDDDDDdDDDDc",
    "cDDDDdDDDDDc",
    ".cDDDDDDDDc.",
    ".cDDDDDDDDc.",
    "..ccDDDDcc..",
    "....cccc....",
]
_REGULATOR = [
    "........eeeeeeeeeeee........",
    "......eEEEEEEEEEEEEEEe......",
    ".....eEMMMMMMMMMMMMMMEe.....",
    "....eEMMXXXXXXXXXXXXMMEe....",
    *["...rEMXm" + row.replace(".", "m") + "mXMEr..." for row in _GAUGE],
    "...rEMMXmmmmmmmmmmmmXMMEr...",
    "....rEMMXXXXXXXXXXXXMMEr....",
    ".....rEEMMMMMMMMMMMMEEr.....",
    "......rrEEEEEEEEEEEErr......",
    ".......dddddddddddddd.......",
    "......mMMm........mMMm......",
    ".....mMXMm........mMXMm.....",
    ".....dddddd......dddddd.....",
]
_CLAMP = [
    "mMMm......",
    "mMXMMe....",
    ".mMMXEe...",
    "..mMXEEe..",
    "...mMEEEe.",
    "....mMEr..",
    "..........",
    "..........",
    "....mMEr..",
    "...mMEEEe.",
    "..mMXEEe..",
    ".mMMXEe...",
    "mMXMMe....",
    "mMMm......",
]
_INSULATE_PLATE = [
    "MXXXXM",
    "M!x!xM",
    "Mx!x!M",
    "M!x!xM",
    "Mx!x!M",
    "M!x!xM",
    "MXXXXM",
]
_FIN = [
    "e......",
    "Ee.....",
    "MEe....",
    "MXEe...",
    "MXXEe..",
    "MXEe...",
    "MEe....",
    "Ee.....",
    "e......",
]


@cache
def regulator_body() -> pygame.Surface:
    return render(_REGULATOR, LEGEND)


@cache
def clamp_arm() -> pygame.Surface:
    return render(_CLAMP, LEGEND)


@cache
def insulate_plate() -> pygame.Surface:
    return render(_INSULATE_PLATE, LEGEND)


@cache
def fin() -> pygame.Surface:
    return render(_FIN, LEGEND)


GAUGE_CENTER = (14, 10)  # needle pivot in body pixels, including the outline padding


def regulator(protocol: str, facing_left: bool) -> pygame.Surface:
    """Body plus protocol pose, composed on one canvas. Pose silhouettes differ:
    Clamp has pincers forward, Insulate has hatched plates on both sides, Oscillate has side
    thruster fins."""
    body = regulator_body()
    bw, bh = body.get_size()
    if protocol == "clamp":
        arm = clamp_arm()
        canvas = pygame.Surface((bw + arm.get_width() - 4, bh), pygame.SRCALPHA)
        canvas.blit(arm, (bw - 6, 2))
        canvas.blit(body, (0, 0))
    elif protocol == "insulate":
        plate = insulate_plate()
        pw = plate.get_width()
        canvas = pygame.Surface((bw + 2 * pw, bh), pygame.SRCALPHA)
        canvas.blit(body, (pw, 0))
        canvas.blit(plate, (1, 5))
        canvas.blit(plate, (bw + pw - 1, 5))
    elif protocol == "oscillate":
        right = fin()
        left = flipped(right)
        fw = right.get_width()
        canvas = pygame.Surface((bw + 2 * fw - 6, bh), pygame.SRCALPHA)
        canvas.blit(left, (0, 6))
        canvas.blit(right, (bw + fw - 6, 6))
        canvas.blit(body, (fw - 3, 0))
    else:
        raise KeyError(protocol)
    return flipped(canvas) if facing_left else canvas
