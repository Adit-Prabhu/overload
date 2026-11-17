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


@dataclass(frozen=True)
class Hud:
    charge: int
    max_charge: int
    dodge_ready: float = 1.0
    sockets: tuple[str | None, str | None] = (None, None)
    cooldowns: tuple[float, float] = (0.0, 0.0)
    rival_health: float | None = None
    rival_protocol: str | None = None
    stamp: str = ""


def draw(target: pygame.Surface, hud: Hud) -> None:
    w, h = target.get_size()

    # Status panel: battery icon, one cell per point of charge, dodge readiness underneath.
    _panel(target, (4, 4, 14 + hud.max_charge * 7, 17))
    pygame.draw.rect(target, rgb("player.core"), (7, 7, 5, 7), 1)
    target.fill(rgb("player.core"), (8, 6, 3, 1))
    for i in range(hud.max_charge):
        cell = (14 + i * 7, 7, 6, 7)
        if i < hud.charge:
            target.fill(rgb("player.core"), cell)
            target.fill(rgb("player.halo"), (cell[0], cell[1] + 5, 6, 2))
        else:
            pygame.draw.rect(target, rgb("px.floor.3"), cell, 1)
    bar_w = hud.max_charge * 7 + 7
    target.fill(rgb("px.floor.2"), (7, 16, bar_w, 2))
    target.fill(rgb("power.blink"), (7, 16, round(bar_w * hud.dodge_ready), 2))

    # Power sockets, bottom right.
    for i, power in enumerate(hud.sockets[:2]):
        x = w - 52 + i * 24
        y = h - 28
        _panel(target, (x, y, 20, 20))
        if power:
            icon = effects.charge_icon(power)
            target.blit(icon, icon.get_rect(center=(x + 10, y + 10)))
            if hud.cooldowns[i] > 0:
                target.blit(_cooldown_shade(round(18 * hud.cooldowns[i])), (x + 1, y + 1))
        text(target, "QE"[i], (x + 10, y - 2), "ui.dim", "midbottom")

    # Regulator bar, top center.
    if hud.rival_health is not None:
        bar_w = 96
        bx = (w - bar_w) // 2
        text(target, "REGULATOR", (w // 2, 4), "ui.text", "midtop")
        target.fill(rgb("px.outline"), (bx - 1, 14, bar_w + 2, 6))
        target.fill(rgb("px.hostile.1"), (bx, 15, bar_w, 4))
        target.fill(rgb("px.hostile.3"), (bx, 15, round(bar_w * hud.rival_health), 4))
        if hud.rival_protocol:
            icon = effects.protocol_icon(hud.rival_protocol)
            target.blit(icon, icon.get_rect(midright=(bx - 4, 17)))

    if hud.stamp:
        text(target, hud.stamp, (4, h - 3), "px.floor.3", "bottomleft")
