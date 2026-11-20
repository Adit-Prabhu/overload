"""Rebindable keys (game/keybinds.py, pilot playtest Nov 19): the bindings, their saved file,
the rebind page, and the input reader and menu reading them."""

from __future__ import annotations

import json
import os

import pygame
import pytest

from overload.game.keybinds import ACTIONS, DEFAULTS, Keybinds, RebindPage, short_label


@pytest.fixture
def display():
    os.environ["SDL_VIDEODRIVER"] = "dummy"
    pygame.init()
    yield pygame.display.set_mode((256, 144))
    pygame.quit()
    from overload.art.pixel import hud, tiles

    hud.forget()
    tiles.forget_fonts()


def test_every_action_has_a_default_and_no_key_is_used_twice() -> None:
    assert {a for a, _ in ACTIONS} == set(DEFAULTS)
    assert len(set(DEFAULTS.values())) == len(DEFAULTS)


def test_binding_a_used_key_swaps_it(tmp_path) -> None:
    binds = Keybinds(path=tmp_path / "keys.json")
    assert binds.bind("dodge", "q")
    assert binds.keys["dodge"] == "q" and binds.keys["power_q"] == "space"
    assert len(set(binds.keys.values())) == len(binds.keys)
    assert not binds.bind("dodge", "escape"), "Esc is never bindable"
    assert not binds.bind("jump", "j")


def test_saved_keys_load_and_damaged_files_fall_back(tmp_path) -> None:
    path = tmp_path / "keys.json"
    binds = Keybinds(path=path)
    binds.bind("up", "i")
    assert Keybinds.load(path).keys["up"] == "i"
    for broken in ("not json", json.dumps({"up": "i"}), json.dumps({**DEFAULTS, "up": "s"})):
        path.write_text(broken)
        assert Keybinds.load(path).keys == DEFAULTS
    assert Keybinds.load(tmp_path / "missing.json").keys == DEFAULTS


def test_unsaved_bindings_never_write(tmp_path) -> None:
    binds = Keybinds()
    binds.bind("up", "i")
    binds.reset()
    assert binds.keys == DEFAULTS and not list(tmp_path.iterdir())


def test_arrows_move_unless_bound_elsewhere() -> None:
    binds = Keybinds()
    assert set(binds.arrows()) == {"up", "down", "left", "right"}
    binds.bind("dodge", "down")
    assert "down" not in binds.arrows()


def test_labels() -> None:
    assert short_label("space") == "SPC" and short_label("q") == "Q"
    assert short_label("[1]") == "1" and short_label("left shift") == "LSH"
    binds = Keybinds()
    assert binds.move_label() == "WASD" and binds.pair("power_q", "power_e") == "Q/E"


def test_the_page_waits_for_a_key_and_esc_cancels() -> None:
    page = RebindPage(Keybinds())
    assert page.nav("down") == "move" and page.row == 1
    page.nav("select")
    assert page.capturing
    page.capture("escape")
    assert not page.capturing and page.binds.keys["down"] == "s"
    page.nav("select")
    page.capture("k")
    assert page.binds.keys["down"] == "k" and page.notice == "MOVE DOWN: K"
    page.row = len(ACTIONS)  # RESET DEFAULTS
    page.nav("select")
    assert page.binds.keys == DEFAULTS
    assert page.nav("back") == "back"


def press(reader, *keys) -> None:
    for key in keys:
        reader.handle(pygame.event.Event(pygame.KEYDOWN, key=key))


def test_the_reader_follows_the_bindings(display) -> None:
    from overload.game.app import InputReader

    binds = Keybinds()
    binds.bind("dodge", "left shift")
    binds.bind("power_q", "1")
    reader = InputReader(binds)
    press(reader, pygame.K_SPACE, pygame.K_q)
    frame = reader.frame((0, 0))
    assert not frame.dodge and not frame.power_q, "the old keys do nothing"
    press(reader, pygame.K_LSHIFT, pygame.K_1)
    frame = reader.frame((0, 0))
    assert frame.dodge and frame.power_q
    assert "q" in [k for k, _ in reader.take_menu_raw()], "the power key equips in menus"


def test_rebinding_in_the_game_menu(display, tmp_path) -> None:
    from overload.agent.selector import NeutralSelector
    from overload.game.app import InputReader, menu_frame
    from overload.game.flow import Session
    from overload.game.menu import Menu
    from overload.session.replay import Recording
    from overload.sim.campaign import Campaign

    session = Session(Campaign(1), NeutralSelector())
    binds = Keybinds(path=tmp_path / "keys.json")
    reader = InputReader(binds)
    menu = Menu()
    menu.keys_page.binds = binds
    menu.show(in_fuse_box=False)
    menu.screen = "controls"
    recording = Recording(seed=1, tuning_id="x", arena_id="y", mode="campaign")
    press(reader, pygame.K_s, pygame.K_s, pygame.K_s, pygame.K_s, pygame.K_RETURN)
    menu_frame(session, menu, reader, recording, 16)
    assert menu.capturing
    press(reader, pygame.K_TAB)  # the menu key itself can be captured
    assert reader.take_toggle()
    menu_frame(session, menu, reader, recording, 16)
    assert binds.keys["dodge"] == "tab" and binds.keys["menu"] == "space"
    press(reader, pygame.K_SPACE)
    assert reader.take_toggle(), "the reader picked up the new menu key"


def test_no_binding_takes_away_select_or_back(display) -> None:
    from overload.game.app import InputReader

    binds = Keybinds()
    binds.bind("up", "space")
    binds.bind("down", "return")
    binds.bind("left", "enter")
    binds.bind("right", "backspace")
    reader = InputReader(binds)
    press(reader, pygame.K_SPACE, pygame.K_RETURN, pygame.K_KP_ENTER, pygame.K_BACKSPACE)
    assert reader.take_menu() == ["select", "select", "select", "back"]
    press(reader, pygame.K_UP, pygame.K_DOWN)
    assert reader.take_menu() == ["up", "down"], "the free arrows still move"


def test_a_key_with_no_name_is_never_bound() -> None:
    page = RebindPage(Keybinds())
    page.nav("select")
    assert page.capture("") == "move" and page.notice == ""
    assert page.binds.keys == DEFAULTS
