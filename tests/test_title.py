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
    from overload.art.pixel import hud
    from overload.game import title

    hud.forget()
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
    assert {"MOVE", "FIRE", "DODGE", "POWERS", "LOADOUT AND FUSION"} <= actions
