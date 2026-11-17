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
    "shock_cone": "CONE",
}


@dataclass(frozen=True)
class Hud:
    charge: int
    max_charge: int
    dodge_ready: float = 1.0
    sockets: tuple[str | None, str | None] = (None, None)
    cooldowns: tuple[float, float] = (0.0, 0.0)  # fraction left
    cooldown_seconds: tuple[float, float] = (0.0, 0.0)
    rival_health: float | None = None
    rival_protocol: str | None = None
    rival_name: str = "REGULATOR"
    stamp: str = ""
    tick: int = 0
    hint: str = ""


def draw(target: pygame.Surface, hud: Hud) -> None:
    w, h = target.get_size()
    low = hud.charge <= 2
    blink = (hud.tick // 10) % 2 == 0

    # Charge: a battery with one big cell per point, the number beside it, red when low.
    cells = hud.max_charge
    width = 16 + cells * 9 + 22
    _panel(target, (4, 4, width, 24))
    if low and blink:
        pygame.draw.rect(target, rgb("hostile.danger"), (4, 4, width, 24), 1)
    body = "hostile.danger" if low else "player.core"
    pygame.draw.rect(target, rgb(body), (8, 8, 7, 11), 1)
    target.fill(rgb(body), (10, 7, 3, 1))
    for i in range(cells):
        cell = (18 + i * 9, 8, 8, 11)
        if i < hud.charge:
            target.fill(rgb("hostile.danger" if low else "player.core"), cell)
            target.fill(rgb("px.hostile.3" if low else "player.halo"), (cell[0], cell[1] + 8, 8, 3))
        else:
            pygame.draw.rect(target, rgb("px.floor.3"), cell, 1)
    text(
        target,
        f"{hud.charge}/{hud.max_charge}",
        (20 + cells * 9, 9),
        "hostile.danger" if low else "ui.text",
    )
    bar_w = width - 8
    target.fill(rgb("px.floor.2"), (8, 22, bar_w, 3))
    target.fill(rgb("power.blink"), (8, 22, round(bar_w * hud.dodge_ready), 3))

    # Power sockets, bottom right: key above, icon, name below, seconds left while cooling.
    for i, power in enumerate(hud.sockets[:2]):
        x = w - 56 + i * 28
        y = h - 38
        _panel(target, (x, y, 24, 24))
        text(target, "QE"[i], (x + 12, y - 1), "ui.dim", "midbottom")
        if not power:
            continue
        icon = pygame.transform.scale_by(effects.charge_icon(power), 2)
        target.blit(icon, icon.get_rect(center=(x + 12, y + 12)))
        if hud.cooldowns[i] > 0:
            shade = _cooldown_shade(round(22 * hud.cooldowns[i]))
            target.blit(pygame.transform.scale(shade, (22, shade.get_height())), (x + 1, y + 1))
            text(target, f"{hud.cooldown_seconds[i]:.1f}", (x + 12, y + 8), "ui.text", "midtop")
        text(target, SHORT.get(power, power.upper()), (x + 12, y + 25), "ui.dim", "midtop")

    # Boss bar, top center, with the boss's name and protocol icon.
    if hud.rival_health is not None:
        bar_w = 100
        bx = (w - bar_w) // 2
        text(target, hud.rival_name, (w // 2, 3), "ui.text", "midtop")
        target.fill(rgb("px.outline"), (bx - 1, 13, bar_w + 2, 7))
        target.fill(rgb("px.hostile.1"), (bx, 14, bar_w, 5))
        target.fill(rgb("px.hostile.3"), (bx, 14, round(bar_w * hud.rival_health), 5))
        if hud.rival_protocol:
            icon = effects.protocol_icon(hud.rival_protocol)
            target.blit(icon, icon.get_rect(midright=(bx - 4, 16)))

    if hud.hint:
        text(target, hud.hint, (4, h - 3), "px.floor.3", "bottomleft")
    if hud.stamp:
        text(target, hud.stamp, (4, h - 3), "px.floor.3", "bottomleft")
