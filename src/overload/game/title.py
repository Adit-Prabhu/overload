"""The title screen: the wordmark over a slowly drifting, darkened view of the substation, a
three-item menu (Start, Controls, Quit) and a controls page in the same framed-panel style as
the loadout screen. Pure presentation: nothing here touches the simulation."""

from __future__ import annotations

import math
import random
from functools import cache

import pygame

from overload import __version__
from overload.art.palette import rgb, rgba
from overload.art.pixel import actors, hud, tiles
from overload.floor import FLOOR

ITEMS = ("START", "CONTROLS", "QUIT")
CONTROLS = (
    ("MOVE", "WASD OR ARROWS"),
    ("AIM", "MOUSE"),
    ("FIRE", "HOLD LEFT CLICK"),
    ("DODGE", "SPACE"),
    ("POWERS", "Q AND E"),
    ("LOADOUT AND FUSION", "TAB (PAUSES)"),
    ("FUSE BOX: CONTINUE", "ENTER"),
    ("RETRY AFTER A SHORT CIRCUIT", "R"),
    ("QUIT", "ESC"),
)


@cache
def _backdrop() -> pygame.Surface:
    return tiles.render_room(FLOOR.room).background


@cache
def _wordmark() -> pygame.Surface:
    """OVERLOAD in the pixel font at 3x, with the shared outline."""
    letters = hud.pixel_font().render("OVERLOAD", False, rgb("power.spark"))
    big = pygame.transform.scale_by(letters, 3)
    canvas = pygame.Surface((big.get_width() + 6, big.get_height() + 6), pygame.SRCALPHA)
    shadow = pygame.transform.scale_by(
        hud.pixel_font().render("OVERLOAD", False, rgb("px.outline")), 3
    )
    for dx, dy in ((0, 3), (3, 3), (3, 0), (0, 0)):
        canvas.blit(shadow, (dx, dy))
    canvas.blit(big, (1, 1))
    return canvas


def forget() -> None:
    """Drop cached surfaces after pygame.quit()."""
    _backdrop.cache_clear()
    _wordmark.cache_clear()


class TitleScreen:
    """Feed it key presses with `press`. `choice` becomes "start" or "quit"."""

    def __init__(self) -> None:
        self.selected = 0
        self.page = "menu"
        self.choice: str | None = None
        self.tick = 0
        self.cosmetic = random.Random(7)
        self.sparks: list[list[float]] = []

    def press(self, key: int) -> None:
        if self.page == "controls":
            if key in (pygame.K_RETURN, pygame.K_KP_ENTER, pygame.K_ESCAPE, pygame.K_BACKSPACE):
                self.page = "menu"
            return
        if key in (pygame.K_w, pygame.K_UP):
            self.selected = (self.selected - 1) % len(ITEMS)
        elif key in (pygame.K_s, pygame.K_DOWN):
            self.selected = (self.selected + 1) % len(ITEMS)
        elif key in (pygame.K_RETURN, pygame.K_KP_ENTER, pygame.K_SPACE):
            item = ITEMS[self.selected]
            if item == "START":
                self.choice = "start"
            elif item == "CONTROLS":
                self.page = "controls"
            else:
                self.choice = "quit"
        elif key == pygame.K_ESCAPE:
            self.choice = "quit"

    def update(self) -> None:
        self.tick += 1
        if self.tick % 6 == 0:
            self.sparks.append(
                [
                    self.cosmetic.uniform(0, 256),
                    150.0,
                    self.cosmetic.uniform(-0.3, 0.3),
                    self.cosmetic.uniform(-0.9, -0.4),
                ]
            )
        for spark in self.sparks:
            spark[0] += spark[2]
            spark[1] += spark[3]
        self.sparks = [s for s in self.sparks if s[1] > -4]

    def draw(self, screen: pygame.Surface) -> None:
        w, h = screen.get_size()
        backdrop = _backdrop()
        span = backdrop.get_width() - w
        x = round((math.sin(self.tick / 900) * 0.5 + 0.5) * span)
        screen.blit(backdrop, (-x, -40))
        veil = pygame.Surface((w, h), pygame.SRCALPHA)
        veil.fill(rgba("px.outline", 200))
        screen.blit(veil, (0, 0))
        for sx, sy, _, _ in self.sparks:
            screen.fill(
                rgb("px.spark.light" if int(sx) % 3 else "power.spark"),
                (round(sx), round(sy), 1, 2),
            )
        if self.page == "controls":
            self._controls(screen)
        else:
            self._menu(screen)
        hud.text(screen, f"OVERLOAD {__version__}", (4, h - 3), "px.floor.3", "bottomleft")

    def _menu(self, screen: pygame.Surface) -> None:
        w, h = screen.get_size()
        mark = _wordmark()
        flicker = self.tick % 240 in (100, 103)  # the sign stutters now and then
        if not flicker:
            screen.blit(mark, mark.get_rect(midtop=(w // 2, 22)))
        hud.text(screen, "SURGE VERSUS THE REGULATOR", (w // 2, 52), "ui.dim", "midtop")
        surge = actors.surge("idle", self.tick, False)
        screen.blit(surge, surge.get_rect(midbottom=(w // 2, 92)))
        for i, item in enumerate(ITEMS):
            y = 98 + i * 11
            chosen = i == self.selected
            rect = hud.text(
                screen, item, (w // 2, y), "px.hazard.1" if chosen else "ui.dim", "midtop"
            )
            if chosen:
                hud.text(screen, ">", (rect.left - 4, y), "px.hazard.1", "topright")
        hud.text(screen, "W S AND ENTER", (w - 4, h - 3), "px.floor.3", "bottomright")

    def _controls(self, screen: pygame.Surface) -> None:
        w, h = screen.get_size()
        panel = pygame.Rect(18, 10, w - 36, h - 20)
        screen.fill(rgb("px.outline"), panel)
        pygame.draw.rect(screen, rgb("px.wall.2"), panel, 1)
        left, right = panel.x + 6, panel.right - 6
        hud.text(screen, "CONTROLS", (left, panel.y + 4), "ui.text")
        screen.fill(rgb("px.wall.1"), (left, panel.y + 15, right - left, 1))
        for i, (action, keys) in enumerate(CONTROLS):
            y = panel.y + 20 + i * 10
            hud.text(screen, action, (left, y), "ui.dim")
            hud.text(screen, keys, (right, y), "ui.text", "topright")
        hud.text(screen, "ENTER BACK", (right, panel.bottom - 11), "px.hazard.1", "topright")


def run_title(screen: pygame.Surface, clock: pygame.time.Clock) -> bool:
    """Show the title until the player starts (True) or quits (False)."""
    title = TitleScreen()
    while title.choice is None:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                return False
            if event.type == pygame.KEYDOWN:
                title.press(event.key)
        title.update()
        title.draw(screen)
        pygame.display.flip()
        clock.tick(60)
    return title.choice == "start"
