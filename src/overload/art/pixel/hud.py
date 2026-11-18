"""Pixel HUD at 256 x 144, in the spirit of action roguelikes: status panel top left, power
sockets bottom right, Regulator bar top center. Text uses Silkscreen (SIL OFL 1.1)."""

from __future__ import annotations

from dataclasses import dataclass
from functools import cache

import pygame

from overload.art.palette import rgb, rgba
from overload.art.pixel import effects
from overload.paths import FONTS

_SILKSCREEN = FONTS / "silkscreen" / "Silkscreen-Regular.ttf"


@cache
def pixel_font() -> pygame.font.Font:
    """Silkscreen at its native 8 px size. Requires pygame.font to be initialized."""
    return pygame.font.Font(_SILKSCREEN, 8)


def forget() -> None:
    """Drop the cached font after pygame.quit()."""
    pixel_font.cache_clear()


def text(
    target: pygame.Surface, message: str, pos: tuple[int, int], token: str, anchor: str = "topleft"
) -> pygame.Rect:
    image = pixel_font().render(message, False, rgb(token))
    rect = image.get_rect(**{anchor: pos})
    shadow = pixel_font().render(message, False, rgb("px.outline"))
    target.blit(shadow, rect.move(1, 1))
    target.blit(image, rect)
    return rect


@cache
def _cooldown_shade(height: int) -> pygame.Surface:
    shade = pygame.Surface((18, max(1, height)), pygame.SRCALPHA)
    shade.fill(rgba("px.outline", 170))
    return shade


def _panel(target: pygame.Surface, rect: tuple[int, int, int, int]) -> None:
    pygame.draw.rect(target, rgb("px.outline"), rect)
    pygame.draw.rect(target, rgb("px.wall.2"), rect, 1)


SHORT = {
    "spark": "SPARK",
    "blink": "BLINK",
    "burst": "BURST",
    "arc_trail": "TRAIL",
    "bolt_lance": "LANCE",
    "chain_jump": "JUMP",
    "shock_cone": "CONE",
    "shock_mine": "MINE",
    "storm_aura": "AURA",
    "impact_blink": "BLAST",
    "displacer": "SWAP",
    "meteor": "METEOR",
}


def rarity_marks(target: pygame.Surface, rarity: str, x: int, y: int) -> None:
    """1, 2 or 3 small crosses in the rarity's color, left to right from (x, y), the top
    left of the first one's 3 x 3 box. Crosses, so they never read as the square evolution
    pips."""
    token = f"px.rarity.{rarity}"
    for p in range(("rare", "epic", "legendary").index(rarity) + 1):
        left = x + p * 4
        target.fill(rgb(token), (left + 1, y, 1, 3))
        target.fill(rgb(token), (left, y + 1, 3, 1))


# 3 x 5 key letters drawn inside a slot's corner (the 8 px font is too big for that).
_KEYS = {
    "Q": (".#.", "#.#", "#.#", ".#.", "..#"),
    "E": ("###", "#..", "##.", "#..", "###"),
}


def key_glyph(target: pygame.Surface, key: str, x: int, y: int, token: str) -> None:
    target.fill(rgb("px.outline"), (x - 1, y - 1, 5, 7))
    for dy, row in enumerate(_KEYS[key]):
        for dx, char in enumerate(row):
            if char == "#":
                target.fill(rgb(token), (x + dx, y + dy, 1, 1))


def _outlined_rect(target: pygame.Surface, rect: tuple[int, int, int, int], token: str) -> None:
    x, y, w, h = rect
    target.fill(rgb("px.outline"), (x - 1, y - 1, w + 2, h + 2))
    target.fill(rgb(token), rect)


@dataclass(frozen=True)
class Hud:
    charge: int
    max_charge: int
    dodge_ready: float = 1.0
    sockets: tuple[str | None, str | None] = (None, None)
    cooldowns: tuple[float, float] = (0.0, 0.0)  # fraction left
    rival_health: float | None = None
    rival_protocol: str | None = None
    rival_name: str = "REGULATOR"
    rival_phases: int = 1  # a chassis with three phases shows two notches on its bar
    rival_phase: int = 1
    rival_changing: bool = False
    rival_venting: bool = False  # its punish window: the bar flashes
    stamp: str = ""
    tick: int = 0


def draw(target: pygame.Surface, hud: Hud) -> None:
    """The in-play HUD (art direction, HUD layout): health top left, powers bottom right,
    the boss bar top center during a fight. The minimap is drawn by the view."""
    w, h = target.get_size()
    low = hud.charge <= 2
    pulse = (hud.tick // 8) % 2 == 0

    # Health: a battery glyph and one pip per point, red and pulsing when low.
    body = "hostile.danger" if low and pulse else "player.core"
    target.fill(rgb("px.outline"), (3, 3, 7, 11))
    pygame.draw.rect(target, rgb(body), (4, 5, 5, 8), 1)
    target.fill(rgb(body), (5, 4, 3, 1))
    for i in range(hud.max_charge):
        x = 12 + i * 6
        if i < hud.charge:
            _outlined_rect(target, (x, 5, 5, 7), "hostile.danger" if low else "player.core")
            target.fill(rgb("px.hostile.3" if low else "player.halo"), (x, 10, 5, 2))
        else:
            target.fill(rgb("px.outline"), (x - 1, 4, 7, 9))
            pygame.draw.rect(target, rgb("px.floor.3"), (x, 5, 5, 7), 1)
    width = hud.max_charge * 6 - 1
    target.fill(rgb("px.outline"), (11, 14, width + 2, 3))
    target.fill(rgb("power.blink"), (12, 15, round(width * hud.dodge_ready), 1))

    # Powers: two slots with the key in the corner. A dark fill drains while cooling.
    for i, power in enumerate(hud.sockets[:2]):
        x, y = w - 4 - 20 * (2 - i) - 2 * (1 - i), h - 24
        ready = bool(power) and hud.cooldowns[i] <= 0
        target.fill(rgb("px.outline"), (x - 1, y - 1, 20, 20))
        pygame.draw.rect(
            target, rgb("player.core" if ready else "px.wall.2"), (x - 1, y - 1, 20, 20), 1
        )
        if power:
            icon = pygame.transform.scale_by(effects.charge_icon(power), 2)
            target.blit(icon, icon.get_rect(center=(x + 9, y + 9)))
            if hud.cooldowns[i] > 0:
                shade = _cooldown_shade(round(18 * hud.cooldowns[i]))
                target.blit(shade, (x, y))
        key_glyph(target, "QE"[i], x + 7, y - 7, "ui.text" if ready else "ui.dim")  # a tab above

    # The boss: name and a thin bar, top center, only while it fights.
    if hud.rival_health is not None:
        bar_w = 100
        bx = (w - bar_w) // 2
        text(target, hud.rival_name, (w // 2, 2), "ui.text", "midtop")
        target.fill(rgb("px.outline"), (bx - 1, 11, bar_w + 2, 5))
        target.fill(rgb("px.hostile.1"), (bx, 12, bar_w, 3))
        fill = "fx.flash" if hud.rival_venting and (hud.tick // 4) % 2 else "px.hostile.3"
        target.fill(rgb(fill), (bx, 12, round(bar_w * hud.rival_health), 3))
        for k in range(1, hud.rival_phases):  # where the next phases begin
            nx = bx + round(bar_w * k / hud.rival_phases)
            target.fill(rgb("px.outline"), (nx, 11, 1, 5))
            target.fill(rgb("ui.text"), (nx, 16, 1, 1))
        if hud.rival_phases > 1:
            phase_color = ("ui.text", "px.lamp.light", "px.hostile.3")[hud.rival_phase - 1]
            # The active phase stays visible after the shielded transition finishes.
            panel = pygame.Rect(0, 18, 102 if hud.rival_changing else 70, 13)
            panel.centerx = w // 2
            target.fill(rgb("px.outline"), panel)
            if hud.rival_changing:
                pygame.draw.rect(target, rgb(phase_color), panel, 1)
            label = f"PHASE {hud.rival_phase}/{hud.rival_phases}"
            if hud.rival_changing:
                label += " SHIFTING"
            text(target, label, (w // 2, 20), phase_color, "midtop")
        if hud.rival_protocol:
            icon = effects.protocol_icon(hud.rival_protocol)
            target.blit(icon, icon.get_rect(midright=(bx - 3, 13)))

    if hud.stamp:
        text(target, hud.stamp, (4, h - 3), "px.floor.3", "bottomleft")
