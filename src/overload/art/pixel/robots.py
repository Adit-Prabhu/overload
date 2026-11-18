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
from overload.art.pixel import actors, rig
from overload.art.pixel.grid import add_outline, flipped, render
from overload.art.pixel.rig import blank, paint, rows_of

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

# Shading helpers -----------------------------------------------------------------------------

_LIGHT = (-0.48, -0.62, 0.62)  # from the top left and toward the viewer


def shaded_ellipse(width: int, height: int, ramp: str, top_only: bool = False) -> list[str]:
    """A round shell lit from the top left, as grid rows. `ramp` is darkest first. With
    `top_only`, the lower half is cut off flat (a dome)."""
    rx, ry = width / 2, height / 2
    norm = math.sqrt(sum(c * c for c in _LIGHT))
    lx, ly, lz = (c / norm for c in _LIGHT)
    rows = []
    for y in range(height):
        row = []
        for x in range(width):
            nx = (x + 0.5 - rx) / rx
            ny = (y + 0.5 - ry) / ry
            inside = nx * nx + ny * ny <= 1.0
            if top_only and y >= height // 2 + 1:
                inside = abs(nx) <= 1.0
                ny = min(ny, 0.2)
            if not inside:
                row.append(".")
                continue
            nz = math.sqrt(max(0.0, 1.0 - nx * nx - ny * ny))
            light = nx * lx + ny * ly + nz * lz
            level = min(len(ramp) - 1, max(0, int((light + 0.15) / 1.15 * len(ramp))))
            row.append(ramp[level])
        rows.append("".join(row))
    return rows


# Arc Drone ----------------------------------------------------------------------------------
# An orange hover drone: a spinning rotor on a mast, a round shell, one big lens looking where
# it flies, thruster pods with amber running lights, and its Spark core slung underneath.
# Carries Spark. It leans into its flight and its lens flares while it aims.

_DRONE_ROTOR = (
    "dXXXXXXXXXXXXXXXXXXXd",
    "....dXXXXXXXXXXXXd...",
    ".......dXXXXXXd......",
)
_DRONE_POD = ["dX", "XA", "Xm", "dd"]
_DRONE_CORE = [
    ".dMMMMMd.",
    "dXmYmmMMd",
    ".dmYyYmd.",
    "..dmYmd..",
    "...dMd...",
]
_DRONE_JETS = (
    ["..J...J..", "..j...j.."],
    ["..j...j..", "........."],
)
DRONE_SIZE = (23, 25)


@cache
def _drone_shell() -> list[str]:
    rows = shaded_ellipse(15, 12, "RroOO")
    rows = [list(r) for r in rows]
    for y in (4, 5, 6, 7, 8):  # the visor, on the front half
        for x in range(6, 15):
            if rows[y][x] != "." and not (y in (4, 8) and x in (6, 14)):
                rows[y][x] = "v"
    return ["".join(r) for r in rows]


@cache
def drone_frame(rotor: int, jets: int, lean: bool, aiming: bool, blink: bool) -> pygame.Surface:
    w, h = DRONE_SIZE
    canvas = blank(w, h)
    paint(canvas, [_DRONE_ROTOR[rotor]], 1, 0)
    paint(canvas, ["dMd", "dXd"], 10, 1)
    paint(canvas, _drone_shell(), 4, 3)
    if blink:
        paint(canvas, ["eeee"], 13, 10)
    else:  # the lens, toward the front (right)
        lens = ["vEEv", "EwEE", "EEeE", "vEEv"]
        if aiming:
            lens = ["EEEE", "EwwE", "EwwE", "EEEE"]
        paint(canvas, lens, 13, 8)
    paint(canvas, ["Q"], 7, 5)  # the shell's shine
    paint(canvas, _DRONE_POD, 1, 8)
    paint(canvas, [r[::-1] for r in _DRONE_POD], 20, 8)
    paint(canvas, _DRONE_CORE, 7, 15)
    paint(canvas, _DRONE_JETS[jets], 7, 20)
    if lean:  # lean into the flight: the top of the drone tips forward a pixel
        for y in range(0, 8):
            canvas[y] = ["."] + canvas[y][:-1]
    return render(rows_of(canvas), LEGEND)


def drone(
    tick: int, facing_left: bool, moving: bool = False, aiming: bool = False, seed: int = 0
) -> pygame.Surface:
    """The rotor spins every tick, the jets flicker (faster in flight), it leans while it
    flies and blinks now and then. The view adds the hover bob."""
    blink = (tick + seed * 37) % 220 >= 214 and not aiming
    image = drone_frame(
        tick % 3, (tick // (2 if moving else 5)) % 2, moving and not aiming, aiming, blink
    )
    return flipped(image) if facing_left else image


def drone_frames() -> tuple[pygame.Surface, ...]:
    return tuple(drone_frame(r, 0, False, False, False) for r in range(3))


# Relay Bot ----------------------------------------------------------------------------------
# A ceramic-blue relay cabinet on two jointed legs: a lever switch on its lid, a visor with
# two eyes looking ahead, vent slits, an amber status light and a diamond window showing its
# Blink. Carries Blink. While its landing diamond shows, the lever flips down and it crouches
# to jump.

_RELAY = [
    "..dQQQQQQQQQcd..",
    ".dQQCCCCCCCCCcd.",
    ".dQCvvvvvvvvvcd.",
    ".dQCvvvvwEvwEcd.",
    ".dQCvvvvEEvEEcd.",
    ".dQCvvvvvvvvvcd.",
    ".dQCCCCCdCCCCcd.",
    ".dQCmCCdKdCCAcd.",
    ".dQCmCdKkKdCCcd.",
    ".dQCmCCdKdCCCcd.",
    ".dcCCCCCdCCCCcd.",
    "..dcccccccccccd.",
    "...dMMMMMMMMmd..",
]
_RELAY_LEVER = {
    "up": ["..W.", "..M.", "..X."],
    "down": ["....", "....", "WMX."],
}
_RELAY_LEG = rig.LegStyle(upper="Mm", lower="Xm", knee="XX", foot="dXXM", heel=1, swing=1, lift=1)
RELAY_SIZE = (18, 21)


@cache
def relay_bot_frame(arming: bool, step: int | None) -> pygame.Surface:
    w, h = RELAY_SIZE
    canvas = blank(w, h)
    crouch = 1 if arming else 0  # a crouch before the jump
    top = (0 if rig.rising(step) else 1) + crouch
    paint(canvas, _RELAY_LEVER["down" if arming else "up"], 1, top)
    paint(canvas, _RELAY, 1, top + 3)
    hips = top + 3 + len(_RELAY)
    length = h - hips
    for half, hip in ((0, 5), (1, 11)):
        swing, lift = rig.pose(step, half, _RELAY_LEG)
        rig.leg(canvas, hip, hips, length, swing, lift, _RELAY_LEG)
    return render(rows_of(canvas), LEGEND)


def relay_bot(facing_left: bool, arming: bool = False, step: int | None = None) -> pygame.Surface:
    image = relay_bot_frame(arming, step)
    return flipped(image) if facing_left else image


def relay_bot_frames() -> dict[str, pygame.Surface]:
    return {"up": relay_bot_frame(False, None), "down": relay_bot_frame(True, None)}


# Breaker ------------------------------------------------------------------------------------
# A hazard-yellow construction brute: a gunmetal head with a hard visor, shoulder plates, a
# chest plate with its Burst ring, a striped belt, two heavy legs and two huge fists that
# swing as it stomps. Carries Burst. Raising its fists is the tell before the slam.

_BREAKER_HEAD = [
    "..dXWXd..",
    ".dXMMMMd.",
    "dXvvvvvMd",
    "dXvvEEEMd",
    ".dMMMMMd.",
]
_BREAKER_TORSO = [
    ".dXXXdHHHHHHHdXXXd.",
    "dXWWXdHHhHhHHdXMMXd",
    "dXWXXHHHHHHHHHXXMXd",
    ".dXXdHHHmUmHHHdXXd.",
    "...dHHHmUuUmHHHd...",
    "...dHHmUuuuUmHHd...",
    "...dHHHmUuUmHHHd...",
    "...dHHHHmUmHHHHd...",
    "...dhHhHhHhHhHhd...",
]
_BREAKER_FIST = [".dXXXd.", "dXWWXMd", "dXWXXMd", "dXXXXMd", ".dMMMd."]
_BREAKER_LEG = rig.LegStyle(
    upper="MXm", lower="MXm", knee="XXd", foot="dXXXXd", heel=1, swing=1, lift=2
)
_BREAKER_ARM = rig.LegStyle(upper="XMm", lower="XMm", knee="dXd", foot="", heel=0, swing=1)
BREAKER_SIZE = (29, 23)


@cache
def breaker_frame(pose: str, step: int | None) -> pygame.Surface:
    w, h = BREAKER_SIZE
    canvas = blank(w, h)
    if pose != "rest":
        step = None  # the tell and the slam stand planted
    sink = 3 if pose == "slam" else 0
    top = (2 if rig.rising(step) else 3) + sink
    torso_x = 5
    paint(canvas, _BREAKER_HEAD, 10, top)
    hips = top + 4 + len(_BREAKER_TORSO)
    length = h - hips
    spread = 2 if pose == "slam" else 0
    for half, hip in ((0, 10 - spread), (1, 16 + spread)):
        swing, lift = rig.pose(step, half, _BREAKER_LEG)
        rig.leg(canvas, hip, hips, length, swing, lift, _BREAKER_LEG)
    # Arms: from the shoulders down to fists that hang by its knees and swing against the
    # legs, held overhead for the tell, driven into the floor for the slam.
    shoulder = top + 6
    for half, x in ((0, 3), (1, 23)):
        swing, _lift = rig.pose(step, 1 - half, _BREAKER_LEG)
        side = -1 if half == 0 else 1
        if pose == "raise":
            fist = (x - 1 + (2 if half == 0 else 0), top - 3)
            paint(canvas, ["XMm", "XMm", "XMm"], x, top + 1)
        elif pose == "slam":
            fist = (x - 2 + (0 if half == 0 else 2), h - 5)
            rig.leg(canvas, x, shoulder, h - 5 - shoulder, side, 0, _BREAKER_ARM)
        else:
            arm = 6
            fist = (x - 2 + swing, shoulder + arm - 1)
            rig.leg(canvas, x, shoulder, arm, swing, 0, _BREAKER_ARM)
        paint(canvas, _BREAKER_FIST, *fist)
    paint(canvas, _BREAKER_TORSO, torso_x, top + 4)
    if pose == "slam":  # dust kicked up at the fists
        paint(canvas, ["w..w....................w..w"], 0, h - 6)
    return render(rows_of(canvas), LEGEND)


def breaker_frames() -> dict[str, pygame.Surface]:
    return {pose: breaker_frame(pose, None) for pose in ("rest", "raise", "slam")}


def breaker(
    facing_left: bool, raising: bool = False, slamming: bool = False, step: int | None = None
) -> pygame.Surface:
    image = breaker_frame("slam" if slamming else "raise" if raising else "rest", step)
    return flipped(image) if facing_left else image


# Sweeper ------------------------------------------------------------------------------------
# A white dome with a red sensor stripe and a striped bumper, scuttling on six thin legs (a
# tripod gait: three feet down while three swing). Rushes. Carries nothing. While it revs,
# its legs dig in and the dome shudders.

SWEEPER_SIZE = (25, 14)
# (hip x, which way the leg reaches, how far, gait group): two spider legs a side, reaching
# out past the dome, stepping in diagonal pairs.
_SWEEPER_LEGS = ((8, -1, 5, 0), (10, -1, 3, 1), (16, 1, 5, 1), (14, 1, 3, 0))


@cache
def _sweeper_dome() -> list[str]:
    rows = [list(r) for r in shaded_ellipse(15, 10, "gGGZ", top_only=True)]
    for x in range(1, 14):  # the red sensor stripe, its eye at the front
        if rows[5][x] != ".":
            rows[5][x] = "o"
    rows[5][10:13] = ["E", "w", "E"]
    rows[4][10:13] = ["v", "v", "v"]
    rows[6][10:13] = ["v", "v", "v"]
    for x in range(15):  # the bumper skirt, hazard striped
        if rows[7][x] != ".":
            rows[7][x] = "H" if x % 2 == 0 else "h"
    return ["".join(r) for r in rows[:8]]


def _line(canvas, a: tuple[int, int], b: tuple[int, int], char: str) -> None:
    steps = max(abs(b[0] - a[0]), abs(b[1] - a[1]), 1)
    for i in range(steps + 1):
        x = round(a[0] + (b[0] - a[0]) * i / steps)
        y = round(a[1] + (b[1] - a[1]) * i / steps)
        paint(canvas, [char], x, y)


def _sweeper_leg(canvas, hip: int, top: int, out: int, reach: int, swing: int, lift: int):
    """A spider leg: up and out from under the skirt to a knee beside the dome, then down
    to a pointed foot. A lifted leg raises its foot and knee."""
    knee = (hip + out * reach + swing, top - 2 - lift)
    foot = (knee[0] + out, top + 2 - lift)
    _line(canvas, (hip, top), knee, "M")
    _line(canvas, knee, foot, "M")
    paint(canvas, ["X"], *knee)
    paint(canvas, ["d"], *foot)


@cache
def sweeper_frame(step: int | None, dig: bool, shudder: int) -> pygame.Surface:
    w, h = SWEEPER_SIZE
    canvas = blank(w, h)
    top = (1 if rig.rising(step) else 2) + (1 if dig else 0)
    hips = h - 3
    for hip, out, reach, group in _SWEEPER_LEGS:
        if dig:  # legs splayed wide and planted
            _sweeper_leg(canvas, hip, hips, out, reach + 1, 0, 0)
            continue
        swing, lift = rig.pose(step, group, _SWEEPER_LEG)
        _sweeper_leg(canvas, hip, hips, out, reach, swing, lift)
    paint(canvas, _sweeper_dome(), 5 + shudder, top)
    return render(rows_of(canvas), LEGEND)


_SWEEPER_LEG = rig.LegStyle(upper="M", lower="M", knee="X", foot="d", heel=0, swing=1, lift=1)


def sweeper(
    step: int | None, facing_left: bool, revving: bool = False, tick: int = 0
) -> pygame.Surface:
    """`step` is its walk step (the view counts it from the distance it scuttled)."""
    shudder = (tick // 2) % 2 if revving else 0
    image = sweeper_frame(None if revving else step, revving, shudder)
    return flipped(image) if facing_left else image


def sweeper_frames() -> tuple[pygame.Surface, ...]:
    return tuple(sweeper_frame(s, False, 0) for s in range(rig.STEPS))


# Sentry -------------------------------------------------------------------------------------
# A dark armored turret on a planted tripod: a sensor eye that sweeps while it waits, an
# orange barrel with a cooling shroud, an ammo drum and an amber status light. Long tell,
# slow shell. Carries nothing. Its barrel kicks back when it fires.

_SENTRY_HEAD = [
    "...dXXXXXXd..",
    "..dXWWMMMMMd.",
    ".dXWMMMMMMMMd",
    ".dXvvvvvvvvMd",
    ".dXMMMMMMMMMd",
    ".dmmmAmmmmmmd",
    "..dddddddddd.",
]
_SENTRY_BARREL = ["dRrrrrO", "dooooOO", "dRrrrro"]
_SENTRY_DRUM = ["dXd", "XQX", "XcX", "dXd"]
_SENTRY_BASE = [
    "....dHhHhd....",
    "...dXMMMMmd...",
    "..dXd.dd.dXd..",
    ".dXd..dd..dXd.",
    "dXd..dXXd..dXd",
    "dd..........dd",
]
SENTRY_SIZE = (22, 13)


@cache
def sentry_frame(scan: int = 1, kick: int = 0) -> pygame.Surface:
    w, h = SENTRY_SIZE
    canvas = blank(w, h)
    paint(canvas, _SENTRY_DRUM, 1, 4)
    paint(canvas, _SENTRY_BARREL, 14 - kick, 3)
    paint(canvas, _SENTRY_HEAD, 3, 0)
    paint(canvas, ["E"], 6 + scan * 2, 3)  # the sensor eye sweeps across the visor
    paint(canvas, _SENTRY_BASE, 2, h - len(_SENTRY_BASE))
    return render(rows_of(canvas), LEGEND)


def sentry(facing_left: bool, scan: int = 1, kick: int = 0) -> pygame.Surface:
    image = sentry_frame(scan, kick)
    return flipped(image) if facing_left else image


# The Regulator mech -----------------------------------------------------------------------

MECH_SIZE = (36, 42)
MECH_GAUGE = (18, 23)


def _fill(s: pygame.Surface, token: str, x: int, y: int, w: int = 1, h: int = 1) -> None:
    s.fill(rgb(token), (x, y, w, h))


SHELLS = {
    "linesman": ("px.hostile.0", "px.hostile.1", "px.hostile.2", "px.hostile.3"),
    "transformer": ("px.coil.0", "px.coil.1", "px.coil.2", "px.coil.3"),
    "grid_core": ("px.core.0", "px.core.1", "px.core.2", "px.core.3"),
}
SHELLS["regulator"] = SHELLS["linesman"]


@cache
def mech_body(kind: str = "linesman", overload: bool = False) -> pygame.Surface:
    """A big armored control mech: a domed head with a red visor, a shell chest with the
    gauge face that tracks the Surge, ceramic insulator shoulders, striped hips, stubby
    legs. Protocol arms attach at the shoulders. Each chassis has its own shell and head:
    the Linesman an orange shell and one beacon, the Transformer a brass shell with ceramic
    bushings on its head and coil bands, the Grid Core a violet shell with a crown of
    magenta pylons (cracked and glowing once it overloads)."""
    dark, shade, base, light = SHELLS[kind]
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
    _fill(s, base, 4, 13, 28, 18)
    _fill(s, light, 5, 13, 26, 2)
    _fill(s, light, 4, 14, 1, 14)
    _fill(s, shade, 4, 28, 28, 3)
    _fill(s, shade, 31, 14, 1, 14)
    if kind == "transformer":  # coil bands across the chest
        for y in (17, 21, 25):
            _fill(s, shade, 5, y, 6, 1)
            _fill(s, shade, 26, y, 5, 1)
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
    eye = "px.burst.light" if overload else "hostile.danger"
    _fill(s, eye, 13, 7, 3, 2)
    _fill(s, eye, 20, 7, 3, 2)
    _fill(s, light, 13, 7, 1, 1)
    _fill(s, light, 20, 7, 1, 1)
    if kind == "transformer":  # two ceramic bushings on the head
        for x in (10, 23):
            for i, y in enumerate((0, 1, 2, 3)):
                _fill(s, "px.ceramic.1" if i % 2 else "px.ceramic.2", x, y, 3, 1)
            _fill(s, "px.led.amber", x + 1, 0)
    elif kind == "grid_core":  # a crown of three pylons with magenta tips
        for x, top in ((11, 1), (17, 0), (23, 1)):
            _fill(s, "px.bot.3", x, top + 1, 2, 3 - top)
            _fill(s, "power.burst", x, top, 2, 1)
    else:
        _fill(s, "px.bot.3", 17, 0, 2, 2)
        _fill(s, "px.led.amber", 17, 0, 2, 1)
    # Gauge face on the chest.
    cx, cy = MECH_GAUGE
    rim = "power.burst" if kind == "grid_core" else "px.bot.3"
    pygame.draw.circle(s, rgb(rim), (cx, cy), 7)
    pygame.draw.circle(s, rgb("px.bot.0"), (cx, cy), 6)
    pygame.draw.circle(s, rgb("px.dial.1"), (cx, cy), 5)
    for dx, dy in ((-3, 1), (-3, -2), (-1, -4), (2, -4), (4, -2)):
        _fill(s, "px.bot.2", cx + dx, cy + dy)
    for dx, dy in ((3, -3), (4, -2), (3, -4)):
        _fill(s, "hostile.danger", cx + dx, cy + dy)
    # Status lights.
    for i, token in enumerate((light, "px.led.amber", "px.ceramic.2")):
        _fill(s, token, 7, 17 + i * 3)
    if overload:  # glowing cracks through the shell
        for x, y in (
            (6, 15),
            (7, 16),
            (7, 17),
            (8, 18),
            (27, 14),
            (28, 15),
            (28, 16),
            (29, 17),
            (26, 24),
            (27, 25),
            (9, 25),
            (10, 26),
        ):
            _fill(s, "hostile.danger", x, y)
    add_outline(s, "px.outline")
    return s


def regulator_mech(
    protocol: str,
    facing_left: bool,
    needle: float | None = None,
    lit: bool = False,
    kind: str = "linesman",
    overload: bool = False,
) -> pygame.Surface:
    """The mech with its protocol arms: Clamp pincers, Insulate plates or Oscillate fins."""
    body = mech_body(kind, overload)
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
