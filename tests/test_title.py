"""The title screen: Start, Controls and Quit, and a controls page."""

from __future__ import annotations

import os

import pygame
import pytest

from overload.game.keybinds import Keybinds
from overload.game.title import CONTROLS, ITEMS, TitleScreen, controls


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
    title.press(pygame.K_ESCAPE)
    assert title.page == "menu" and title.choice is None, "Esc leaves the page, never quits"


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
    assert run_title(display, pygame.time.Clock()) is None


def test_enter_at_the_title_starts(display) -> None:
    from overload.game.title import run_title

    pygame.event.post(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_RETURN))
    assert run_title(display, pygame.time.Clock()) == "medium"


def test_start_reuses_the_fullscreen_title_window(monkeypatch, tmp_path) -> None:
    from overload.game import app
    from overload.sim.difficulty import PRESETS

    windows = []
    gameplay = []
    draw = app.PixelView.draw

    def open_fullscreen(headless):
        assert not headless
        screen = pygame.display.set_mode(app.VIEW, pygame.FULLSCREEN)
        windows.append(screen)
        for key in (pygame.K_RIGHT, pygame.K_RETURN):
            pygame.event.post(pygame.event.Event(pygame.KEYDOWN, key=key))
        return screen

    def draw_gameplay(self, screen, run, cursor):
        assert screen.get_flags() & pygame.FULLSCREEN
        assert run.tuning is PRESETS["hard"]
        gameplay.append(screen)
        draw(self, screen, run, cursor)

    monkeypatch.setattr(app, "_open_window", open_fullscreen)
    monkeypatch.setattr(app.PixelView, "draw", draw_gameplay)
    options = app.Options(condition="off", mute=True, frames=1, trace=tmp_path / "trace.jsonl")
    assert app.play(options) == 0
    assert len(windows) == 1 and gameplay == windows


def test_ending_space_returns_to_title_reusing_the_window(monkeypatch, tmp_path) -> None:
    from overload.agent.selector import LiveSelector
    from overload.game import app

    windows = []
    title_calls = []
    closed_sessions = []
    closed_clients = []
    ending_renders = []
    real_close = app.Session.close
    real_draw = app.PixelView.draw
    real_ending = app.PixelView.draw_campaign_ending

    class FakeClient:
        def close(self) -> None:
            closed_clients.append(self)

    def open_window(headless):
        assert not headless
        screen = pygame.display.set_mode(app.VIEW, pygame.FULLSCREEN)
        windows.append(screen)
        return screen

    def fake_build_selector(options):
        return LiveSelector(FakeClient(), "sess-1"), "sess-1", "live"

    def fake_run_title(screen, clock, difficulty, binds, audio):
        assert screen.get_flags() & pygame.FULLSCREEN
        title_calls.append((screen, audio, difficulty))
        if len(title_calls) == 1:
            return "hard"
        if len(title_calls) == 2:
            return "medium"
        return None

    def close_session(self):
        closed_sessions.append(self)
        real_close(self)

    def drive_run(self, screen, run, cursor):
        if len(title_calls) == 1:
            if run.stage != "ending":
                run.stage = "ending"
                self.boss_banner = None
                # Stale Space pressed before the ending renders once must be dropped.
                pygame.event.post(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_SPACE))
        else:
            # Second run starts fresh, then exits via Escape on the ending screen.
            if run.stage != "ending":
                run.stage = "ending"
                self.boss_banner = None
            else:
                pygame.event.post(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_ESCAPE))
        real_draw(self, screen, run, cursor)

    def record_ending(self, screen, run, can_return=False):
        ending_renders.append((len(title_calls), can_return))
        real_ending(self, screen, run, can_return)
        if len(title_calls) == 1 and len(ending_renders) == 2:
            # Space pressed after the ending has rendered returns to title.
            pygame.event.post(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_SPACE))

    monkeypatch.setattr(app, "_open_window", open_window)
    monkeypatch.setattr(app, "build_selector", fake_build_selector)
    monkeypatch.setattr(app, "run_title", fake_run_title)
    monkeypatch.setattr(app.Session, "close", close_session)
    monkeypatch.setattr(app.PixelView, "draw", drive_run)
    monkeypatch.setattr(app.PixelView, "draw_campaign_ending", record_ending)
    options = app.Options(condition="off", mute=True, trace=tmp_path / "trace.jsonl")
    assert app.play(options) == 0
    assert len(windows) == 1
    assert len(title_calls) == 2
    assert title_calls[0][0] is title_calls[1][0]
    assert title_calls[0][1] is title_calls[1][1]
    assert title_calls[1][2] == "hard"
    assert len(closed_sessions) == 2 and closed_sessions[0] is not closed_sessions[1]
    assert len(closed_clients) == 2 and closed_clients[0] is not closed_clients[1]
    assert ending_renders[:2] == [(1, True), (1, True)], "stale Space did not skip ending"


def test_ending_space_ignored_while_boss_banner_or_skip_title(monkeypatch, tmp_path) -> None:
    from overload.game import app

    real_draw = app.PixelView.draw
    seen_can_return = []
    real_ending = app.PixelView.draw_campaign_ending

    def drive_skip_title(self, screen, run, cursor):
        if run.stage != "ending":
            run.stage = "ending"
            self.boss_banner = ("GRID CORE DOWN", 5)
            pygame.event.post(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_SPACE))
        elif self.boss_banner is not None:
            self.boss_banner = None
            pygame.event.post(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_SPACE))
        else:
            pygame.event.post(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_ESCAPE))
        real_draw(self, screen, run, cursor)

    def record_ending(self, screen, run, can_return=False):
        if self.boss_banner is None:
            seen_can_return.append(can_return)
        real_ending(self, screen, run, can_return)

    monkeypatch.setattr(app, "_open_window", lambda _: pygame.display.set_mode(app.VIEW))
    monkeypatch.setattr(app.PixelView, "draw", drive_skip_title)
    monkeypatch.setattr(app.PixelView, "draw_campaign_ending", record_ending)
    options = app.Options(
        condition="off", mute=True, skip_title=True, trace=tmp_path / "trace.jsonl"
    )
    assert app.play(options) == 0
    assert seen_can_return and all(flag is False for flag in seen_can_return)


def test_start_returns_the_difficulty_selected_with_arrow_keys(display) -> None:
    from overload.game.title import run_title

    for key in (pygame.K_RIGHT, pygame.K_RIGHT, pygame.K_RETURN):
        pygame.event.post(pygame.event.Event(pygame.KEYDOWN, key=key))
    assert run_title(display, pygame.time.Clock()) == "nightmare"


def test_closing_the_window_in_the_same_batch_as_start_quits(display) -> None:
    from overload.game.title import run_title

    pygame.event.post(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_RETURN))
    pygame.event.post(pygame.event.Event(pygame.QUIT))
    assert run_title(display, pygame.time.Clock()) is None


def test_the_controls_page_rebinds_a_key_and_saves_it(tmp_path) -> None:
    path = tmp_path / "keys.json"
    title = TitleScreen(binds=Keybinds(path=path))
    title.press(pygame.K_s)
    title.press(pygame.K_RETURN)  # CONTROLS
    for _ in range(4):
        title.press(pygame.K_s)  # down to DODGE
    title.press(pygame.K_RETURN)
    assert title.keys.capturing
    title.press(pygame.K_LSHIFT)
    assert not title.keys.capturing and title.keys.binds.keys["dodge"] == "left shift"
    assert Keybinds.load(path).keys["dodge"] == "left shift", "saved for the next run"
    assert ("DODGE", "LEFT SHIFT") in controls(title.keys.binds)
    title.press(pygame.K_RETURN)
    title.press(pygame.K_ESCAPE)  # Esc cancels the wait, the key stays
    assert title.keys.binds.keys["dodge"] == "left shift" and title.page == "controls"


def test_the_rebind_page_draws_while_waiting(display) -> None:
    title = TitleScreen()
    title.page = "controls"
    title.keys.capturing = True
    title.draw(display)


def test_title_moves_and_picks_queue_their_sounds() -> None:
    title = TitleScreen()
    title.press(pygame.K_s)
    title.press(pygame.K_d)
    title.press(pygame.K_RETURN)
    assert title.sounds == ["menu_move", "menu_move", "confirm"]


def test_the_title_plays_its_music_and_menu_sounds(display) -> None:
    from overload.game.title import run_title

    class Recorder:
        def __init__(self) -> None:
            self.played, self.stages = [], []

        def play(self, name):
            self.played.append(name)

        def update(self, stage, encounter, outcome):
            self.stages.append(stage)

    audio = Recorder()
    for key in (pygame.K_s, pygame.K_w, pygame.K_RETURN):
        pygame.event.post(pygame.event.Event(pygame.KEYDOWN, key=key))
    assert run_title(display, pygame.time.Clock(), audio=audio) == "medium"
    assert audio.played == ["menu_move", "menu_move", "confirm"]
    assert set(audio.stages) == {"title"}


def test_every_difficulty_has_a_line_and_the_standoff_draws(display) -> None:
    from overload.game.title import ABOUT
    from overload.sim.difficulty import DIFFICULTIES

    assert set(ABOUT) == set(DIFFICULTIES)
    title = TitleScreen()
    for tick in range(400):
        title.update()
        if tick % 50 == 0:
            title.arc = title.zap = 3
            title.draw(display)


def test_the_menu_text_stays_clear_of_the_surge(display) -> None:
    """Every difficulty line ends left of the Surge (the PR #56 review found two that ran
    under its feet)."""
    from overload.art.pixel import actors, hud
    from overload.game.title import ABOUT, SURGE_FROM_RIGHT

    surge = actors.surge("idle", 0, False)
    surge_left = display.get_width() - SURGE_FROM_RIGHT - surge.get_width() // 2
    for line in (*ABOUT.values(), "< NIGHTMARE >", "DIFFICULTY", *ITEMS):
        assert 20 + hud.pixel_font().size(line)[0] < surge_left - 2, line
