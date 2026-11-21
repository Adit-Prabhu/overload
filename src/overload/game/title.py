"""The title screen: the wordmark over a slowly drifting, darkened view of the substation, a
four-item menu (Start, Settings, Controls, Quit), a settings page (game/settings.py) and a
controls page in the same framed-panel style as the loadout screen, where every key can be
rebound (game/keybinds.py). Pure presentation: nothing here touches the simulation."""

from __future__ import annotations

import math
import random
from functools import cache

import pygame

from overload import __version__
from overload.art.palette import rgb, rgba
from overload.art.pixel import actors, hud, tiles
from overload.art.pixel import regulators as regulators_art
from overload.floor import FLOOR
from overload.game import keybinds
from overload.game.keybinds import ACTIONS, Keybinds, RebindPage
from overload.game.settings import ROWS as SETTING_ROWS
from overload.game.settings import Settings, SettingsPage
from overload.sim.difficulty import DIFFICULTIES

ITEMS = ("START", "SETTINGS", "CONTROLS", "QUIT")
# One line on what each preset changes (sim/difficulty.py). Medium is the formal playtest's.
ABOUT = {
    "easy": "MORE CELLS, SOFTER BOTS",
    "medium": "RECOMMENDED FIRST RUN",
    "hard": "FEWER CELLS, TOUGHER BOTS",
    "nightmare": "FOUR CELLS, FAST BOLTS",
}
SURGE_FROM_RIGHT = 88  # the Surge's feet, from the right edge, clear of the menu text
BEAT_TICKS = 60 * 60 / 124  # the title music's beat (124 BPM) in 60 Hz ticks


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


def rebind_footer(page: RebindPage, nav: str = "W/S") -> str:
    """`nav` names the keys that move the rows: fixed on the title, bound in the game."""
    if page.capturing:
        return "ESC CANCELS"
    return page.notice or f"{nav} MOVE  ENTER CHANGE  ESC BACK"


def draw_settings(
    screen: pygame.Surface, page: SettingsPage, left: int, right: int, top: int
) -> int:
    """Shared settings table: volume bars, comfort toggles, fullscreen and reset."""
    for i, (field_name, title) in enumerate(SETTING_ROWS):
        y = top + i * 14
        chosen = i == page.row
        if chosen:
            screen.fill(rgb("px.wall.1"), (left - 2, y + 1, right - left + 4, 11))
        hud.text(screen, title, (left, y + 2), "ui.text" if chosen else "ui.dim")
        raw = getattr(page.settings, field_name)
        label = page.value_label(field_name)
        shown = f"< {label} >" if chosen else label
        if isinstance(raw, bool):
            token = "px.hazard.1" if raw else ("ui.text" if chosen else "ui.dim")
        else:
            token = "px.hazard.1" if chosen else "ui.text"
            # 10-segment volume bar just left of the numeric value.
            bar_x = right - 92
            lit = raw // 10
            for seg in range(10):
                rect = (bar_x + seg * 4, y + 4, 3, 5)
                if seg < lit:
                    screen.fill(rgb("px.hazard.1" if chosen else "player.core"), rect)
                else:
                    pygame.draw.rect(screen, rgb("px.floor.3"), rect, 1)
        hud.text(screen, shown, (right, y + 2), token, "topright")
    y = top + len(SETTING_ROWS) * 14
    chosen = page.row == len(SETTING_ROWS)
    if chosen:
        screen.fill(rgb("px.wall.1"), (left - 2, y + 1, right - left + 4, 11))
    hud.text(screen, "RESET DEFAULTS", (left, y + 2), "ui.text" if chosen else "ui.dim")
    return y + 14


def settings_footer(page: SettingsPage, nav: str = "W/S", side: str = "A/D") -> str:
    return page.notice or f"{nav} MOVE  {side} CHANGE  ESC BACK"


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


@cache
def _chassis() -> pygame.Surface:
    """The Grid Core in its last phase, facing the Surge, darkened to a looming shape."""
    image = regulators_art.regulator("clamp", True, kind="grid_core", phase=3, charged=True)
    image = image.copy()
    shade = pygame.Surface(image.get_size(), pygame.SRCALPHA)
    shade.fill(rgba("px.floor.3", 255))  # multiplied in: the chassis in shadow
    image.blit(shade, (0, 0), special_flags=pygame.BLEND_RGBA_MULT)
    return image


@cache
def _vignette(size: tuple[int, int]) -> pygame.Surface:
    """Darker toward the edges, so the eye lands on the wordmark and the standoff."""
    w, h = size
    veil = pygame.Surface(size, pygame.SRCALPHA)
    for ring in range(12):
        alpha = 10 + ring * 4
        inset = 12 - ring
        pygame.draw.rect(
            veil,
            (*rgb("px.outline"), alpha),
            (inset - 12, inset - 12, w + 2 * (12 - inset), h + 2 * (12 - inset)),
            2,
        )
    return veil


@cache
def _glow() -> pygame.Surface:
    """The wordmark's halo: the letters in spark yellow, spread a few pixels."""
    mark = _wordmark()
    halo = pygame.Surface((mark.get_width() + 8, mark.get_height() + 8), pygame.SRCALPHA)
    letters = pygame.transform.scale_by(
        hud.pixel_font().render("OVERLOAD", False, rgb("power.spark")), 3
    )
    for dx in (-2, 0, 2):
        for dy in (-2, 0, 2):
            halo.blit(letters, (5 + dx, 5 + dy))
    return halo


def forget() -> None:
    """Drop cached surfaces after pygame.quit()."""
    _backdrop.cache_clear()
    _wordmark.cache_clear()
    _chassis.cache_clear()
    _vignette.cache_clear()
    _glow.cache_clear()


class TitleScreen:
    """Feed it key presses with `press`. `choice` becomes "start" or "quit"."""

    def __init__(
        self,
        difficulty: str = "medium",
        binds: Keybinds | None = None,
        settings: Settings | None = None,
    ) -> None:
        self.keys = RebindPage(binds or Keybinds())
        self.settings_page = SettingsPage(settings or Settings())
        self.selected = 0
        self.difficulty = difficulty
        self.page = "menu"
        self.choice: str | None = None
        self.display_dirty = False
        self.tick = 0
        self.cosmetic = random.Random(7)
        self.sparks: list[list[float]] = []
        self.arc = 0  # ticks left on the arc between the Surge and the chassis
        self.zap = 0  # ticks left on the arc across the wordmark
        self.sounds: list[str] = []  # interface cues for the caller to play

    def press(self, key: int) -> None:
        if self.page == "controls":
            if self.keys.capturing:
                name = keybinds.key_name(key)
                self.keys.capture(name if keybinds.known(name) else "escape")
            elif self.keys.nav(TITLE_KEYS.get(key, "")) == "back":
                self.page = "menu"
            return
        if self.page == "settings":
            sound, display_changed = self.settings_page.nav(TITLE_KEYS.get(key, ""))
            if display_changed:
                self.display_dirty = True
            if sound == "back":
                self.page = "menu"
                self.sounds.append("menu_move")
            elif sound == "move":
                self.sounds.append("menu_move")
            elif sound == "confirm":
                self.sounds.append("confirm")
            return
        if key in (pygame.K_w, pygame.K_UP):
            self.selected = (self.selected - 1) % len(ITEMS)
            self.sounds.append("menu_move")
        elif key in (pygame.K_s, pygame.K_DOWN):
            self.selected = (self.selected + 1) % len(ITEMS)
            self.sounds.append("menu_move")
        elif key in (pygame.K_a, pygame.K_d, pygame.K_LEFT, pygame.K_RIGHT):
            direction = -1 if key in (pygame.K_a, pygame.K_LEFT) else 1
            index = DIFFICULTIES.index(self.difficulty)
            self.difficulty = DIFFICULTIES[(index + direction) % len(DIFFICULTIES)]
            self.sounds.append("menu_move")
        elif key in (pygame.K_RETURN, pygame.K_KP_ENTER, pygame.K_SPACE):
            self.sounds.append("confirm")
            item = ITEMS[self.selected]
            if item == "START":
                self.choice = "start"
            elif item == "SETTINGS":
                self.page = "settings"
                self.settings_page.row, self.settings_page.notice = 0, ""
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
        self.arc = max(0, self.arc - 1)
        self.zap = max(0, self.zap - 1)
        if self.arc == 0 and self.cosmetic.random() < 1 / 150:
            self.arc = 10
        if self.zap == 0 and self.cosmetic.random() < 1 / 260:
            self.zap = 8

    def draw(self, screen: pygame.Surface) -> None:
        w, h = screen.get_size()
        backdrop = _backdrop()
        span = backdrop.get_width() - w
        x = round((math.sin(self.tick / 4000) * 0.5 + 0.5) * span)  # about 15 px a second
        screen.blit(backdrop, (-x, -40))
        veil = pygame.Surface((w, h), pygame.SRCALPHA)
        veil.fill(rgba("px.outline", 200))
        screen.blit(veil, (0, 0))
        screen.blit(_vignette((w, h)), (0, 0))
        for sx, sy, _, _ in self.sparks:
            screen.fill(
                rgb("px.spark.light" if int(sx) % 3 else "power.spark"),
                (round(sx), round(sy), 1, 2),
            )
        if self.page == "controls":
            self._controls(screen)
        elif self.page == "settings":
            self._settings(screen)
        else:
            self._menu(screen)
        hud.text(screen, f"OVERLOAD {__version__}", (4, h - 3), "px.floor.3", "bottomleft")

    def _beat(self) -> float:
        """1 on the music's beat, falling to 0 before the next."""
        return 1.0 - (self.tick % BEAT_TICKS) / BEAT_TICKS

    def _menu(self, screen: pygame.Surface) -> None:
        w, h = screen.get_size()
        self._standoff(screen)
        mark = _wordmark()
        top = mark.get_rect(midtop=(w // 2, 4))
        flicker = self.tick % 240 in (100, 103)  # the sign stutters now and then
        if not flicker:
            glow = _glow()
            glow.set_alpha(round(30 + 50 * self._beat() ** 2))
            screen.blit(glow, glow.get_rect(center=top.center))
            screen.blit(mark, top)
        if self.zap:
            self._bolt(screen, (top.left + 4, top.centery), (top.right - 4, top.centery), 5)
        hud.text(screen, "SURGE VERSUS THE REGULATOR", (w // 2, top.bottom - 4), "ui.dim", "midtop")

        left = 22
        for i, item in enumerate(ITEMS):
            y = 52 + i * 10
            chosen = i == self.selected
            if chosen:
                screen.fill(rgb("px.wall.1"), (left - 4, y + 2, 92, 9))
                screen.fill(rgb("px.hazard.1"), (left - 4, y + 2, 2, 9))
            token = "px.hazard.1" if chosen else "ui.dim"
            hud.text(screen, item, (left + 2, y), token)
        y = 97
        hud.text(screen, "DIFFICULTY", (left - 2, y), "ui.dim")
        name = self.difficulty.upper()
        hud.text(screen, f"< {name} >", (left - 2, y + 10), "ui.text")
        hud.text(screen, ABOUT[self.difficulty], (left - 2, y + 20), "px.floor.3")
        hud.text(screen, "A/D DIFFICULTY  W/S ENTER", (w - 4, h - 3), "px.floor.3", "bottomright")

    def _standoff(self, screen: pygame.Surface) -> None:
        """Right of the menu: the Surge squares up to a looming chassis, red eyes lit on
        the beat, and now and then an arc jumps between them."""
        w, h = screen.get_size()
        floor = h - 16
        chassis = _chassis()
        sway = round(math.sin(self.tick / 50))
        # Its legs run off the bottom edge, so it looms without crowding the wordmark.
        crect = chassis.get_rect(midbottom=(w - 36, h + 14 + sway))
        screen.blit(chassis, crect)
        surge = actors.surge("idle", self.tick, False)
        srect = surge.get_rect(midbottom=(w - SURGE_FROM_RIGHT, floor))
        screen.fill(rgb("px.outline"), (srect.x + 2, floor - 1, srect.width - 4, 2))
        screen.blit(surge, srect)
        if self.arc:
            target = (crect.centerx - 14, crect.centery + 6)
            self._bolt(screen, (srect.right + 1, srect.centery), target, 4)

    def _bolt(self, screen: pygame.Surface, a, b, jag: int) -> None:
        """A jagged electric line from a to b, new each frame."""
        steps = 7
        points = [a]
        for i in range(1, steps):
            t = i / steps
            points.append(
                (
                    a[0] + (b[0] - a[0]) * t,
                    a[1] + (b[1] - a[1]) * t + self.cosmetic.uniform(-jag, jag),
                )
            )
        points.append(b)
        pygame.draw.lines(screen, rgb("px.spark.light"), False, points, 1)
        pygame.draw.lines(screen, rgb("power.spark"), False, [(x, y + 1) for x, y in points], 1)

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

    def _settings(self, screen: pygame.Surface) -> None:
        w, h = screen.get_size()
        panel = pygame.Rect(18, 10, w - 36, h - 20)
        screen.fill(rgb("px.outline"), panel)
        pygame.draw.rect(screen, rgb("px.wall.2"), panel, 1)
        left, right = panel.x + 6, panel.right - 6
        hud.text(screen, "SETTINGS", (left, panel.y + 4), "ui.text")
        hud.text(screen, "AUDIO AND DISPLAY", (right, panel.y + 4), "ui.dim", "topright")
        screen.fill(rgb("px.wall.1"), (left, panel.y + 14, right - left, 1))
        draw_settings(screen, self.settings_page, left, right, panel.y + 20)
        token = "px.lamp" if self.settings_page.notice else "ui.dim"
        hud.text(
            screen,
            settings_footer(self.settings_page),
            (right, panel.bottom - 11),
            token,
            "topright",
        )


TITLE_KEYS = {
    pygame.K_w: "up",
    pygame.K_UP: "up",
    pygame.K_s: "down",
    pygame.K_DOWN: "down",
    pygame.K_a: "left",
    pygame.K_LEFT: "left",
    pygame.K_d: "right",
    pygame.K_RIGHT: "right",
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
    audio=None,
    settings: Settings | None = None,
    on_display=None,
) -> str | None:
    """Return the selected difficulty on Start, or None on quit. Keys rebound on the
    controls page change `binds` (and are saved, if it has a path), and settings edits
    update `settings` live. With `audio` (game/audio.py), the title music plays and the
    menu has its sounds."""
    title = TitleScreen(difficulty, binds, settings)
    while title.choice is None:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                return None
            if event.type == pygame.KEYDOWN and title.choice is None:
                title.press(event.key)
        if title.display_dirty:
            title.display_dirty = False
            if on_display is not None:
                screen = on_display(title.settings_page.settings.fullscreen)
        if audio is not None:
            if settings is not None:
                audio.apply_settings(settings)
            for sound in title.sounds:
                audio.play(sound)
            audio.update("title", 1, "playing")
        title.sounds.clear()
        title.update()
        title.draw(screen)
        pygame.display.flip()
        clock.tick(60)
    return title.difficulty if title.choice == "start" else None
