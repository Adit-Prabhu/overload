"""The title screen: Start, Controls and Quit, and a controls page."""

from __future__ import annotations

import os

import pygame
import pytest

from overload.game.title import CONTROLS, ITEMS, TitleScreen


@pytest.fixture(autouse=True)
def display():
    os.environ["SDL_VIDEODRIVER"] = "dummy"
    pygame.init()
    screen = pygame.display.set_mode((256, 144))
    yield screen
    pygame.quit()
    from overload.art.pixel import hud, tiles
    from overload.game import title

    hud.forget()
    tiles.forget_fonts()
    title.forget()


def test_start_is_selected_first_and_enter_starts() -> None:
    title = TitleScreen()
    assert ITEMS[title.selected] == "START"
    title.press(pygame.K_RETURN)
    assert title.choice == "start"


def test_the_controls_page_opens_and_closes() -> None:
    title = TitleScreen()
    title.press(pygame.K_s)
    title.press(pygame.K_RETURN)
    assert title.page == "controls" and title.choice is None
    title.press(pygame.K_RETURN)
    assert title.page == "menu"


def test_quit_and_escape_quit() -> None:
    title = TitleScreen()
    title.press(pygame.K_w)  # wraps to QUIT
    title.press(pygame.K_RETURN)
    assert title.choice == "quit"
    other = TitleScreen()
    other.press(pygame.K_ESCAPE)
    assert other.choice == "quit"


def test_both_pages_draw_and_list_every_control(display) -> None:
    title = TitleScreen()
    for _ in range(30):
        title.update()
    title.draw(display)
    title.page = "controls"
    title.draw(display)
    actions = {action for action, _ in CONTROLS}
    assert {"MOVE", "FIRE", "DODGE", "POWERS", "MENU: LOADOUT AND FUSE"} <= actions


def test_closing_the_window_at_the_title_quits(display) -> None:
    from overload.game.title import run_title

    pygame.event.post(pygame.event.Event(pygame.QUIT))
    assert run_title(display, pygame.time.Clock()) is False


def test_enter_at_the_title_starts(display) -> None:
    from overload.game.title import run_title

    pygame.event.post(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_RETURN))
    assert run_title(display, pygame.time.Clock()) is True


def test_start_reuses_the_fullscreen_title_window(monkeypatch, tmp_path) -> None:
    from overload.game import app

    windows = []
    gameplay = []
    draw = app.PixelView.draw

    def open_fullscreen(headless):
        assert not headless
        screen = pygame.display.set_mode(app.VIEW, pygame.FULLSCREEN)
        windows.append(screen)
        pygame.event.post(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_RETURN))
        return screen

    def draw_gameplay(self, screen, run, cursor):
        assert screen.get_flags() & pygame.FULLSCREEN
        gameplay.append(screen)
        draw(self, screen, run, cursor)

    monkeypatch.setattr(app, "_open_window", open_fullscreen)
    monkeypatch.setattr(app.PixelView, "draw", draw_gameplay)
    options = app.Options(condition="off", mute=True, frames=1, trace=tmp_path / "trace.jsonl")
    assert app.play(options) == 0
    assert len(windows) == 1 and gameplay == windows
