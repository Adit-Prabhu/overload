"""Scene rendering shared by the game and the review tools.

Frame order:
1. Blit the pre-rendered floor (traces, walls, insulator blocks) and its static glow.
2. Draw entities and effects onto a transparent layer, then blit the layer.
3. Add one shared bloom computed from that layer, so everything glows the same way.
4. Draw the HUD and reticle on top, unbloomed so text stays crisp.

Functions take plain positions and numbers, never simulation objects, so the art stays
independent of game rules.
"""

from __future__ import annotations

import math
import random
from collections.abc import Sequence
from dataclasses import dataclass

import pygame

from overload.art import primitives as p
from overload.art import sprites
from overload.art.fonts import font
from overload.art.palette import rgb, rgba

Rect = tuple[float, float, float, float]
LIGHTING = ("standby", "rising", "overload")
TRACE_GRID = 40


# Floor ------------------------------------------------------------------------------------


def _trace_paths(size: tuple[int, int], rng: random.Random, count: int) -> list[list[p.Point]]:
    """Circuit-board traces: grid-aligned runs with 45 degree bends, ending in vias."""
    w, h = size
    directions = [(1, 0), (0, 1), (-1, 0), (0, -1)]
    paths = []
    for _ in range(count):
        x = rng.randrange(1, w // TRACE_GRID) * TRACE_GRID
        y = rng.randrange(1, h // TRACE_GRID) * TRACE_GRID
        dx, dy = rng.choice(directions)
        path = [(float(x), float(y))]
        for _segment in range(rng.randint(2, 4)):
            length = rng.randint(1, 4) * TRACE_GRID
            x, y = x + dx * length, y + dy * length
            path.append((float(x), float(y)))
            bend = rng.choice((-1, 1))
            diag = (dx - bend * dy, dy + bend * dx)
            step = TRACE_GRID // 2
            x, y = x + diag[0] * step, y + diag[1] * step
            path.append((float(x), float(y)))
            dx, dy = (dx, dy) if rng.random() < 0.5 else (-bend * dy, bend * dx)
        paths.append(path)
    return paths


def render_floor(
    size: tuple[int, int],
    bounds: Rect,
    obstacles: Sequence[Rect],
    lighting: str = "standby",
    seed: int = 7,
) -> tuple[pygame.Surface, pygame.Surface]:
    """Return (floor, glow). Floor is opaque. Glow is black plus light, for additive blending.

    Lighting by encounter: standby (dim traces), rising (some traces powered), overload
    (most traces powered). The layout is identical in every comparison condition.
    """
    if lighting not in LIGHTING:
        raise KeyError(lighting)
    rng = random.Random(seed)
    floor = pygame.Surface(size)
    floor.fill(rgb("bg.void"))
    emissive = pygame.Surface(size)
    emissive.fill(rgb("bg.void"))
    lit_share = {"standby": 0.0, "rising": 0.2, "overload": 0.6}[lighting]
    for path in _trace_paths(size, rng, 30):
        lit = rng.random() < lit_share
        token = "bg.trace_lit" if lit else "bg.trace"
        p.stroke(floor, token, path, 2)
        p.ring(floor, token, path[-1], 4, 2)
        p.dot(floor, "bg.void", path[-1], 2)
        if lit:
            p.stroke(emissive, "bg.trace_lit", path, 2)

    for rect in obstacles:
        _insulator_block(floor, rect)
        _insulator_block(emissive, rect)
    x, y, w, h = bounds
    border = [(x, y), (x + w, y), (x + w, y + h), (x, y + h)]
    for surface in (floor, emissive):
        p.stroke(surface, "wall.busbar", border, p.STROKE_WALL, closed=True)
        for bx in range(int(x) + 160, int(x + w), 160):
            for by in (y, y + h):
                pygame.draw.rect(surface, rgb("wall.busbar"), (bx - 5, by - 5, 10, 10))
    glow = _blur(emissive, factor=2, radius=6)
    glow.fill(rgb("bg.void"), special_flags=pygame.BLEND_RGB_SUB)
    return floor, glow


def _insulator_block(surface: pygame.Surface, rect: Rect) -> None:
    x, y, w, h = rect
    pygame.draw.rect(surface, rgb("hostile.body"), (x, y, w, h), border_radius=6)
    vertical = h >= w
    span = w if vertical else h
    for offset in range(8, int(h if vertical else w) - 4, 9):
        if vertical:
            pygame.draw.line(
                surface, rgb("bg.trace_lit"), (x + 5, y + offset), (x + span - 5, y + offset), 1
            )
        else:
            pygame.draw.line(
                surface, rgb("bg.trace_lit"), (x + offset, y + 5), (x + offset, y + span - 5), 1
            )
    pygame.draw.rect(surface, rgb("wall.busbar"), (x, y, w, h), 3, border_radius=6)


# Bloom ------------------------------------------------------------------------------------


def _blur(source: pygame.Surface, factor: int, radius: int) -> pygame.Surface:
    """One-off high quality blur, used for static layers rendered once."""
    w, h = source.get_size()
    small = pygame.transform.smoothscale(source, (max(1, w // factor), max(1, h // factor)))
    small = pygame.transform.gaussian_blur(small, radius)
    return pygame.transform.smoothscale(small, (w, h))


@dataclass
class Bloom:
    """One glow for everything: downscale the entity layer, blur it, add it back.

    Runs every frame, so all buffers are allocated once and the blur is two box-blur passes
    (a close, much cheaper approximation of a Gaussian). About 3 ms at 1280 x 720.
    """

    size: tuple[int, int]
    factor: int = 4
    radius: int = 2
    passes: int = 2

    def __post_init__(self) -> None:
        w, h = self.size
        small = (max(1, w // self.factor), max(1, h // self.factor))
        self._source = pygame.Surface(self.size)
        self._small = pygame.Surface(small)
        self._scratch = pygame.Surface(small)
        self._glow = pygame.Surface(self.size)

    def apply(self, target: pygame.Surface, layer: pygame.Surface) -> None:
        self._source.fill(rgb("bg.void"))
        self._source.blit(layer, (0, 0))
        self._source.fill(rgb("bg.void"), special_flags=pygame.BLEND_RGB_SUB)
        pygame.transform.smoothscale(self._source, self._small.get_size(), self._small)
        pygame.transform.box_blur(self._small, self.radius, True, self._scratch)
        pygame.transform.box_blur(self._scratch, self.radius, True, self._small)
        pygame.transform.smoothscale(self._small, self.size, self._glow)
        for _ in range(self.passes):
            target.blit(self._glow, (0, 0), special_flags=pygame.BLEND_RGB_ADD)


def clear(layer: pygame.Surface) -> None:
    layer.fill(rgba("bg.void", 0))


# Entities and effects ---------------------------------------------------------------------


def draw_surge(
    layer: pygame.Surface,
    pos: p.Point,
    aim: float,
    sockets: Sequence[str | None] = (None, None),
    t: float = 0.0,
    invulnerable: bool = False,
    low_charge: bool = False,
) -> None:
    """The player. Aim lead points at the cursor. Sockets orbit, shaped by equipped powers."""
    if low_charge and int(t * 12) % 3 == 0:
        return
    lead_start = p.polar(pos, sprites.SURGE_RADIUS + 3, aim)
    lead_end = p.polar(pos, sprites.SURGE_RADIUS + 15, aim)
    p.stroke(layer, "player.halo", [lead_start, lead_end], 2)
    if invulnerable:
        p.ring(layer, "player.core", pos, sprites.SURGE_RADIUS + 1, 2)
        p.ring(layer, "player.halo", pos, sprites.SURGE_RADIUS + 5, 1)
    else:
        sprites.surge().draw(layer, pos)
    for i, power in enumerate(sockets):
        angle = t * 1.6 + math.pi * i
        spot = p.polar(pos, sprites.SURGE_RADIUS + 16, angle)
        if power:
            sprites.draw_power_symbol(layer, power, spot, 6)
        else:
            p.ring(layer, "ui.dim", spot, 4, 1)


def draw_dodge_streak(layer: pygame.Surface, start: p.Point, end: p.Point) -> None:
    p.stroke(layer, "player.halo", [start, end], 6)
    p.stroke(layer, "player.core", [start, end], 2)


def draw_player_shot(layer: pygame.Surface, pos: p.Point, angle: float) -> None:
    tail = p.polar(pos, -18, angle)
    p.stroke(layer, "player.core", [tail, pos], 4)


def draw_hostile_bolt(layer: pygame.Surface, pos: p.Point) -> None:
    """Hostile projectiles are hollow and spiked: never filled like the player's shots, never
    a plain ring like floor vias or the Burst symbol."""
    p.ring(layer, "hostile.line", pos, 5, 2)
    for i in range(4):
        angle = math.pi / 4 + i * math.pi / 2
        p.stroke(layer, "hostile.line", [p.polar(pos, 5, angle), p.polar(pos, 10, angle)], 2)


def draw_aim_tell(
    layer: pygame.Surface, origin: p.Point, angle: float, progress: float, body_radius: float
) -> None:
    """Aimed-shot telegraph: a capacitor ring fills around the shooter, a dashed line shows
    the locked direction. `progress` runs 0 to 1 over the tell time."""
    progress = max(0.0, min(1.0, progress))
    start = p.polar(origin, body_radius + 6, angle)
    end = p.polar(origin, body_radius + 150, angle)
    p.dashed(layer, "hostile.danger", start, end)
    p.arc(layer, "hostile.danger", origin, body_radius + 7, -math.pi / 2, math.tau * progress, 3)


def draw_arc_mite(layer: pygame.Surface, pos: p.Point, facing: float) -> None:
    sprites.arc_mite().draw(layer, pos, facing)


def draw_relay(layer: pygame.Surface, pos: p.Point) -> None:
    sprites.relay().draw(layer, pos)


def draw_relay_destination(layer: pygame.Surface, pos: p.Point, progress: float) -> None:
    """Where a Relay is about to blink. Visible for the whole 0.5 s tell."""
    r = sprites.RELAY_RADIUS
    outline = p.diamond(pos, r)
    p.hatch(layer, "hostile.danger", outline, spacing=5, width=2)
    p.stroke(layer, "hostile.line", outline, 2, closed=True)
    p.arc(layer, "hostile.danger", pos, r + 5, -math.pi / 2, math.tau * max(0.0, progress), 2)


def draw_regulator(
    layer: pygame.Surface,
    pos: p.Point,
    protocol: str,
    facing: float,
    needle: float,
    tell: float = 0.0,
) -> None:
    """The rival. Pose shows the protocol. The gauge needle always points at the Surge.
    `tell` (0 to 1) fills the Clamp plates while a lunge winds up."""
    pose = sprites.protocol_pose(protocol)
    pose.draw(layer, pos, facing)
    sprites.regulator_body().draw(layer, pos)
    if protocol == "clamp" and tell > 0:
        r = sprites.REGULATOR_RADIUS
        tip = p.chevron(p.polar(pos, r * 1.5, facing), 13 * min(1.0, tell), facing)
        p.fill(layer, "hostile.danger", tip)
    p.stroke(layer, "fx.flash", [pos, p.polar(pos, sprites.GAUGE_RADIUS - 2, needle)], 3)
    p.dot(layer, "hostile.line", pos, 2.5)


def draw_oscillate_trail(layer: pygame.Surface, pos: p.Point, facing: float, t: float) -> None:
    back = p.polar(pos, -(sprites.REGULATOR_RADIUS + 70), facing)
    start = p.polar(pos, -(sprites.REGULATOR_RADIUS + 6), facing)
    wave = p.sine_wave(start, back, 2.0, 7 + math.sin(t * 6) * 2)
    p.stroke(layer, "hostile.line", wave, 1)


def draw_hazard_tile(layer: pygame.Surface, center: p.Point, half: float, progress: float) -> None:
    """Insulate protocol hazard: outline appears, hatching fills in over the tell."""
    cx, cy = center
    square = [
        (cx - half, cy - half),
        (cx + half, cy - half),
        (cx + half, cy + half),
        (cx - half, cy + half),
    ]
    inner = max(0.0, min(1.0, progress)) * half
    if inner > 2:
        filled = [
            (cx - inner, cy - inner),
            (cx + inner, cy - inner),
            (cx + inner, cy + inner),
            (cx - inner, cy + inner),
        ]
        p.hatch(layer, "hostile.danger", filled, spacing=5, width=2)
    p.stroke(layer, "hostile.line", square, 2, closed=True)


def draw_charge(layer: pygame.Surface, pos: p.Point, power: str, t: float) -> None:
    bob = math.sin(t * 3 + pos[0] * 0.05) * 3
    sprites.charge(power).draw(layer, (pos[0], pos[1] + bob))


def draw_arc_trail(layer: pygame.Surface, start: p.Point, end: p.Point, life: float) -> None:
    """Spark + Blink: a Spark zigzag strung between two Blink diamonds. `life` 1 to 0."""
    if life <= 0:
        return
    teeth = max(2, int(math.dist(start, end) / 22))
    width = 3 if life > 0.35 else 2
    p.stroke(layer, "power.spark", p.zigzag(start, end, teeth, 6), width)
    for point in (start, end):
        p.stroke(layer, "power.blink", p.diamond(point, 9), 3, closed=True)


def draw_blink_afterimage(layer: pygame.Surface, pos: p.Point, life: float) -> None:
    if life > 0:
        p.stroke(layer, "power.blink", p.diamond(pos, 8 + (1 - life) * 10), 2, closed=True)


# HUD --------------------------------------------------------------------------------------


@dataclass(frozen=True)
class HudState:
    charge: int
    max_charge: int
    sockets: tuple[tuple[str | None, float], ...] = ((None, 0.0), (None, 0.0))
    dodge_ready: float = 1.0
    rival_health: float | None = None
    rival_protocol: str | None = None
    build_stamp: str = ""


def draw_hud(screen: pygame.Surface, hud: HudState) -> None:
    w, h = screen.get_size()
    base_y = h - 84
    # Charge cells: a battery with one cell per point of charge.
    cell_w, cell_h, gap = 16, 18, 4
    total_w = hud.max_charge * (cell_w + gap) + gap
    pygame.draw.rect(screen, rgb("ui.dim"), (24, base_y, total_w, cell_h + 8), 2, border_radius=3)
    pygame.draw.rect(screen, rgb("ui.dim"), (24 + total_w, base_y + 8, 4, cell_h - 8))
    for i in range(hud.max_charge):
        x = 24 + gap + i * (cell_w + gap)
        if i < hud.charge:
            pygame.draw.rect(screen, rgb("player.core"), (x, base_y + 4, cell_w, cell_h))
        else:
            pygame.draw.rect(screen, rgb("ui.dim"), (x, base_y + 4, cell_w, cell_h), 1)

    # Power sockets with gauge-style cooldowns.
    sx = 24 + total_w + 52
    for i, (power, cooldown) in enumerate(hud.sockets[:2]):
        center = (sx + i * 58, base_y + 12)
        p.ring(screen, "ui.dim", center, 20, 2)
        if power:
            sprites.draw_power_symbol(screen, power, center, 10)
            if cooldown > 0:
                p.arc(screen, "ui.text", center, 20, -math.pi / 2, math.tau * cooldown, 3)
        label = font(14, "bold").render("QE"[i], True, rgb("ui.dim"))
        screen.blit(label, label.get_rect(center=(center[0], center[1] + 30)))

    # Dodge readiness pip.
    pip_x = sx + 2 * 58 - 6
    pygame.draw.rect(screen, rgb("ui.dim"), (pip_x, base_y + 4, 40, 8), 1, border_radius=3)
    pygame.draw.rect(
        screen,
        rgb("player.halo"),
        (pip_x + 1, base_y + 5, int(38 * hud.dodge_ready), 6),
        border_radius=3,
    )
    dodge = font(12, "medium").render("DODGE", True, rgb("ui.dim"))
    screen.blit(dodge, (pip_x, base_y + 18))

    # Regulator bar with protocol icon. Shape only, no protocol name.
    if hud.rival_health is not None:
        bar_w = 360
        bx, by = (w - bar_w) // 2, 58
        title = font(16, "bold").render("REGULATOR", True, rgb("ui.text"))
        screen.blit(title, title.get_rect(midbottom=(w // 2, by - 4)))
        pygame.draw.rect(screen, rgb("hostile.line"), (bx, by, bar_w, 10), 2)
        fill_w = int((bar_w - 4) * max(0.0, min(1.0, hud.rival_health)))
        pygame.draw.rect(screen, rgb("hostile.line"), (bx + 2, by + 2, fill_w, 6))
        if hud.rival_protocol:
            sprites.protocol_icon(hud.rival_protocol, 10).draw(screen, (bx - 22, by + 5))

    if hud.build_stamp:
        stamp = font(12, "medium").render(hud.build_stamp, True, rgb("ui.dim"))
        screen.blit(stamp, stamp.get_rect(bottomright=(w - 32, h - 30)))


def draw_reticle(screen: pygame.Surface, pos: p.Point) -> None:
    """Junction reticle: a plus with a center gap and a junction dot."""
    x, y = pos
    for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
        pygame.draw.line(
            screen, rgb("ui.text"), (x + dx * 4, y + dy * 4), (x + dx * 11, y + dy * 11), 2
        )
    p.dot(screen, "player.core", pos, 2)


def draw_banner(screen: pygame.Surface, title: str, subtitle: str = "") -> None:
    w, h = screen.get_size()
    heading = font(44, "bold").render(title, True, rgb("ui.text"))
    screen.blit(heading, heading.get_rect(center=(w // 2, h // 2 - 16)))
    if subtitle:
        line = font(18, "medium").render(subtitle, True, rgb("ui.dim"))
        screen.blit(line, line.get_rect(center=(w // 2, h // 2 + 28)))
