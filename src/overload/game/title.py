"""The title screen: the wordmark over a slowly drifting, darkened view of the substation, a
three-item menu (Start, Controls, Quit) and a controls page in the same framed-panel style as
the loadout screen, where every key can be rebound (game/keybinds.py). Pure presentation:
nothing here touches the simulation."""

from __future__ import annotations

import math
import random
from functools import cache

import pygame

from overload import __version__
from overload.art.palette import rgb, rgba
from overload.art.pixel import actors, hud, tiles
from overload.floor import FLOOR
from overload.game.keybinds import ACTIONS, Keybinds, RebindPage
from overload.sim.difficulty import DIFFICULTIES

ITEMS = ("START", "CONTROLS", "QUIT")


def controls(binds: Keybinds) -> tuple[tuple[str, str], ...]:
    """Every control with its current key, for the help pages."""
    return (
        ("MOVE", f"{binds.move_label()} OR ARROWS"),
        ("AIM", "MOUSE"),
        ("FIRE", "HOLD LEFT CLICK"),
        ("DODGE", binds.label("dodge")),
        ("POWERS", f"{binds.label('power_q')} AND {binds.label('power_e')}"),
        ("MENU: LOADOUT AND FUSE", f"{binds.label('menu')} OR ESC (PAUSES)"),
        ("IN MENUS: PICK, BACK", "SPACE OR ENTER, ESC"),
        ("RETRY AFTER A SHORT CIRCUIT", binds.label("retry")),
        ("QUIT", "MENU, THEN QUIT"),
    )


CONTROLS = controls(Keybinds())  # the defaults


def draw_rebind(screen: pygame.Surface, page: RebindPage, left: int, right: int, top: int):
    """The rebind rows from `top`: each action and its key, then RESET DEFAULTS, the
    chosen row marked, PRESS A KEY while it waits. Returns the y under the last row."""
    for i, (action, title) in enumerate(ACTIONS):
        y = top + i * 9
        chosen = i == page.row
        if chosen:
            screen.fill(rgb("px.wall.1"), (left - 2, y + 2, right - left + 4, 9))
        hud.text(screen, title, (left, y), "ui.text" if chosen else "ui.dim")
        if chosen and page.capturing:
            key, token = "PRESS A KEY", "px.hazard.1"
        else:
            key, token = page.binds.label(action), "ui.text"
        hud.text(screen, key, (right, y), token, "topright")
    y = top + len(ACTIONS) * 9
    chosen = page.row == len(ACTIONS)
    if chosen:
        screen.fill(rgb("px.wall.1"), (left - 2, y + 2, right - left + 4, 9))
    hud.text(screen, "RESET DEFAULTS", (left, y), "ui.text" if chosen else "ui.dim")
    return y + 10


def rebind_footer(page: RebindPage) -> str:
    if page.capturing:
        return "ESC CANCELS"
    return page.notice or "W/S MOVE  ENTER CHANGE  ESC BACK"


@cache
def _backdrop() -> pygame.Surface:
    return tiles.render_room(FLOOR.room, tiles.floor_sectors(FLOOR)).background


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

    def __init__(self, difficulty: str = "medium", binds: Keybinds | None = None) -> None:
        self.keys = RebindPage(binds or Keybinds())
        self.selected = 0
        self.difficulty = difficulty
        self.page = "menu"
        self.choice: str | None = None
        self.tick = 0
        self.cosmetic = random.Random(7)
        self.sparks: list[list[float]] = []

    def press(self, key: int) -> None:
        if self.page == "controls":
            if self.keys.capturing:
                self.keys.capture(pygame.key.name(key))
            elif self.keys.nav(TITLE_KEYS.get(key, "")) == "back":
                self.page = "menu"
            return
        if key in (pygame.K_w, pygame.K_UP):
            self.selected = (self.selected - 1) % len(ITEMS)
        elif key in (pygame.K_s, pygame.K_DOWN):
            self.selected = (self.selected + 1) % len(ITEMS)
        elif key in (pygame.K_a, pygame.K_d, pygame.K_LEFT, pygame.K_RIGHT):
            direction = -1 if key in (pygame.K_a, pygame.K_LEFT) else 1
            index = DIFFICULTIES.index(self.difficulty)
            self.difficulty = DIFFICULTIES[(index + direction) % len(DIFFICULTIES)]
        elif key in (pygame.K_RETURN, pygame.K_KP_ENTER, pygame.K_SPACE):
            item = ITEMS[self.selected]
            if item == "START":
                self.choice = "start"
            elif item == "CONTROLS":
                self.page = "controls"
                self.keys.row, self.keys.notice = 0, ""
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
        x = round((math.sin(self.tick / 4000) * 0.5 + 0.5) * span)  # about 15 px a second
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
        hud.text(screen, f"< {self.difficulty.upper()} >", (w // 2, 86), "ui.text", "midtop")
        surge = actors.surge("idle", self.tick, False)
        screen.blit(surge, surge.get_rect(midbottom=(w // 2, 83)))
        for i, item in enumerate(ITEMS):
            y = 98 + i * 11
            chosen = i == self.selected
            rect = hud.text(
                screen, item, (w // 2, y), "px.hazard.1" if chosen else "ui.dim", "midtop"
            )
            if chosen:
                hud.text(screen, ">", (rect.left - 4, y), "px.hazard.1", "topright")
        hud.text(screen, "A/D DIFFICULTY  W/S ENTER", (w - 4, h - 3), "px.floor.3", "bottomright")

    def _controls(self, screen: pygame.Surface) -> None:
        w, h = screen.get_size()
        panel = pygame.Rect(18, 10, w - 36, h - 20)
        screen.fill(rgb("px.outline"), panel)
        pygame.draw.rect(screen, rgb("px.wall.2"), panel, 1)
        left, right = panel.x + 6, panel.right - 6
        hud.text(screen, "CONTROLS", (left, panel.y + 4), "ui.text")
        hud.text(screen, "MOUSE AIMS AND FIRES", (right, panel.y + 4), "ui.dim", "topright")
        screen.fill(rgb("px.wall.1"), (left, panel.y + 14, right - left, 1))
        draw_rebind(screen, self.keys, left, right, panel.y + 18)
        token = "px.hazard.1" if self.keys.capturing or not self.keys.notice else "px.lamp"
        hud.text(screen, rebind_footer(self.keys), (right, panel.bottom - 11), token, "topright")


TITLE_KEYS = {
    pygame.K_w: "up",
    pygame.K_UP: "up",
    pygame.K_s: "down",
    pygame.K_DOWN: "down",
    pygame.K_RETURN: "select",
    pygame.K_KP_ENTER: "select",
    pygame.K_SPACE: "select",
    pygame.K_ESCAPE: "back",
    pygame.K_BACKSPACE: "back",
}


def run_title(
    screen: pygame.Surface,
    clock: pygame.time.Clock,
    difficulty: str = "medium",
    binds: Keybinds | None = None,
) -> str | None:
    """Return the selected difficulty on Start, or None on quit. Keys rebound on the
    controls page change `binds` (and are saved, if it has a path)."""
    title = TitleScreen(difficulty, binds)
    while title.choice is None:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                return None
            if event.type == pygame.KEYDOWN and title.choice is None:
                title.press(event.key)
        title.update()
        title.draw(screen)
        pygame.display.flip()
        clock.tick(60)
    return title.difficulty if title.choice == "start" else None
