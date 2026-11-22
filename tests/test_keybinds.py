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
    assert binds.bind("power_q", "e")
    assert binds.keys["power_q"] == "e" and binds.keys["power_e"] == "q"
    assert binds.bind("dodge", "r")
    assert binds.keys["dodge"] == "r" and binds.keys["retry"] == "space"
    assert len(set(binds.keys.values())) == len(binds.keys)
    for reserved in ("escape", "return", "enter", "kp_enter", "backspace"):
        assert not binds.bind("dodge", reserved), f"{reserved} is never bindable"
    assert not binds.bind("jump", "j")


def test_menu_actions_refuse_space_and_unsafe_swaps(tmp_path) -> None:
    binds = Keybinds(path=tmp_path / "keys.json")
    for action in ("up", "down", "left", "right", "power_q", "power_e", "menu"):
        assert not binds.bind(action, "space"), f"{action} must not hold space"
    # Swapping dodge (currently space) onto a menu action would push space onto that action.
    assert not binds.bind("dodge", "q")
    assert not binds.bind("dodge", "tab")
    assert binds.keys["dodge"] == "space" and binds.keys["power_q"] == "q"
    # Once dodge no longer holds space, swapping with menu or power_q works cleanly.
    assert binds.bind("dodge", "left shift")
    assert binds.bind("dodge", "tab")
    assert binds.keys["dodge"] == "tab" and binds.keys["menu"] == "left shift"


def test_saved_keys_load_and_damaged_files_fall_back(tmp_path) -> None:
    path = tmp_path / "keys.json"
    binds = Keybinds(path=path)
    binds.bind("up", "i")
    assert Keybinds.load(path).keys["up"] == "i"
    for broken in (
        "not json",
        json.dumps({"up": "i"}),
        json.dumps({**DEFAULTS, "up": "s"}),
        json.dumps({**DEFAULTS, "dodge": "return"}),
        json.dumps({**DEFAULTS, "dodge": "RETURN"}),
        json.dumps({**DEFAULTS, "dodge": "ESCAPE"}),
        json.dumps({**DEFAULTS, "dodge": "backspace"}),
        json.dumps({**DEFAULTS, "dodge": "tab", "menu": "space"}),
        json.dumps({**DEFAULTS, "dodge": "tab", "menu": "SPACE"}),
        json.dumps({**DEFAULTS, "dodge": "q", "power_q": "space"}),
        json.dumps({**DEFAULTS, "up": "W", "dodge": "w"}),
    ):
        path.write_text(broken)
        assert Keybinds.load(path).keys == DEFAULTS
    # Valid uppercase keys normalize cleanly to lowercase on load and bind.
    path.write_text(json.dumps({**DEFAULTS, "up": "I"}))
    assert Keybinds.load(path).keys["up"] == "i"
    assert Keybinds.load(tmp_path / "missing.json").keys == DEFAULTS


def test_case_insensitive_reserved_keys_and_swaps_are_enforced() -> None:
    binds = Keybinds()
    for bad in ("RETURN", "Enter", "KP_ENTER", "BackSpace", "ESCAPE"):
        assert not binds.bind("dodge", bad)
    assert not binds.bind("menu", "SPACE")
    assert not binds.bind("power_q", "Space")
    assert not binds.bind("dodge", "Q")
    assert binds.bind("power_q", "E")
    assert binds.keys["power_q"] == "e" and binds.keys["power_e"] == "q"
    page = RebindPage(Keybinds())
    page.nav("select")
    assert page.capture("RETURN") == "deny" and page.notice == "ENTER RESERVED FOR MENUS"
    page.nav("select")
    assert page.capture("SPACE") == "deny" and page.notice == "SPACE RESERVED FOR MENUS"


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
    for action in ("up", "down", "left", "right"):
        assert binds.bind(action, action)
    assert binds.move_label() == "ARROWS"


def test_the_page_waits_for_a_key_and_esc_cancels() -> None:
    page = RebindPage(Keybinds())
    assert page.nav("down") == "move" and page.row == 1
    page.nav("select")
    assert page.capturing
    assert page.capture("escape") == "move"
    assert not page.capturing and page.binds.keys["down"] == "s" and page.notice == ""
    page.nav("select")
    assert page.capture("return") == "deny"
    assert page.notice == "ENTER RESERVED FOR MENUS" and page.binds.keys["down"] == "s"
    page.nav("select")
    assert page.capture("space") == "deny"
    assert page.notice == "SPACE RESERVED FOR MENUS" and page.binds.keys["down"] == "s"
    page.nav("select")
    assert page.capture("k") == "confirm"
    assert page.binds.keys["down"] == "k" and page.notice == "MOVE DOWN: K"
    page.row = [a for a, _ in ACTIONS].index("dodge")
    page.nav("select")
    assert page.capture("tab") == "deny"
    assert page.notice == "REBIND MENU FIRST" and page.binds.keys["dodge"] == "space"
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
    # Attempting to swap dodge (space) onto menu (tab) is refused so space cannot soft-lock menus.
    press(reader, pygame.K_TAB)
    assert reader.take_toggle()
    cues = menu_frame(session, menu, reader, recording, 16)
    assert cues == ["deny"] and binds.keys["dodge"] == "space" and binds.keys["menu"] == "tab"
    assert menu.keys_page.notice == "REBIND MENU FIRST"
    # Cancelling capture with Esc plays menu_move (mapped from "move").
    press(reader, pygame.K_RETURN)
    menu_frame(session, menu, reader, recording, 16)
    press(reader, pygame.K_ESCAPE)
    assert menu_frame(session, menu, reader, recording, 16) == ["menu_move"]
    # Move dodge off space first, then capture TAB to swap cleanly with menu.
    press(reader, pygame.K_RETURN)
    menu_frame(session, menu, reader, recording, 16)
    press(reader, pygame.K_LSHIFT)
    assert menu_frame(session, menu, reader, recording, 16) == ["confirm"]
    press(reader, pygame.K_RETURN)
    menu_frame(session, menu, reader, recording, 16)
    press(reader, pygame.K_TAB)
    assert reader.take_toggle()
    assert menu_frame(session, menu, reader, recording, 16) == ["confirm"]
    assert binds.keys["dodge"] == "tab" and binds.keys["menu"] == "left shift"
    press(reader, pygame.K_LSHIFT)
    assert reader.take_toggle(), "the reader picked up the new menu key"


def test_no_binding_takes_away_select_or_back(display) -> None:
    from overload.game.app import InputReader

    binds = Keybinds()
    assert not binds.bind("up", "space")
    assert not binds.bind("down", "return")
    assert not binds.bind("left", "enter")
    assert not binds.bind("right", "backspace")
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
