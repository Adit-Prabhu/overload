"""Presentation-only feel and HUD checks: impact hitstop and boss HUD layout clearance."""

from __future__ import annotations

import os

import pygame
import pytest

from overload.art.palette import rgb
from overload.art.pixel import hud
from overload.game import app
from overload.sim.state import Event


def _isolate_settings(monkeypatch, tmp_path) -> None:
    from overload.game import keybinds, settings

    orig_keys_load = keybinds.Keybinds.load
    orig_prefs_load = settings.Settings.load
    monkeypatch.setattr(keybinds, "PATH", tmp_path / "keys.json")
    monkeypatch.setattr(settings, "PATH", tmp_path / "prefs.json")
    monkeypatch.setattr(
        keybinds.Keybinds,
        "load",
        classmethod(lambda cls, path=None: orig_keys_load(path or tmp_path / "keys.json")),
    )
    monkeypatch.setattr(
        settings.Settings,
        "load",
        classmethod(lambda cls, path=None: orig_prefs_load(path or tmp_path / "prefs.json")),
    )


def test_hitstop_ticks_durations() -> None:
    assert app.hitstop_ticks([]) == 0
    unrelated = [
        Event("shot", 0, 0),
        Event("hostile_hit", 0, 0),
        Event("hostile_destroyed", 0, 0),
        Event("dodge", 0, 0),
        Event("rival_hit", 0, 0, 3, ""),
    ]
    assert app.hitstop_ticks(unrelated) == 0
    assert app.hitstop_ticks([Event("rival_hit", 0, 0, 5, "vent")]) == 2
    assert app.hitstop_ticks([Event("player_hit", 0, 0)]) == 3
    assert app.hitstop_ticks([Event("phase_change", 0, 0)]) == 3
    assert app.hitstop_ticks([Event("rival_destroyed", 0, 0)]) == 4
    assert app.hitstop_ticks([Event("rival_hit", 0, 0, 5, "vent"), Event("player_hit", 0, 0)]) == 3
    assert app.hitstop_ticks([Event("player_hit", 0, 0), Event("rival_destroyed", 0, 0)]) == 4


def test_hitstop_pauses_interactive_sim_preserves_latches_and_clears_on_pause(
    monkeypatch, tmp_path
) -> None:
    _isolate_settings(monkeypatch, tmp_path)
    os.environ["SDL_VIDEODRIVER"] = "dummy"
    os.environ["SDL_AUDIODRIVER"] = "dummy"

    real_tick = app.Session.tick
    sim_frames = []
    # Frame 1: due 1 (tick 1). Frame 2: due 3, tick 2 emits player_hit -> breaks immediately.
    # Frames 3..5: due 1 each, consume the 3 hitstop ticks without stepping.
    # Frame 6: due 1, tick 3 runs and receives the Space press latched during hitstop.
    # Frame 7: due 1, tick 4 emits rival_destroyed (4-tick hitstop).
    # Frame 8: Esc pauses (clears hitstop). Frame 9: Esc unpauses, due 1 steps immediately.
    due_plan = iter([1, 3, 1, 1, 1, 1, 1, 1, 1])
    frame_idx = 0
    ticks_at_frame: list[int] = []
    real_draw = app.PixelView.draw

    def fake_ticks_due(paused, headless, accumulated, elapsed):
        if paused:
            return 0, 0.0
        return next(due_plan, 1), 0.0

    def tracked_tick(self, frame):
        real_tick(self, frame)
        sim_frames.append(frame)
        if len(sim_frames) == 2:
            self.campaign.world.events.append(Event("player_hit", 0, 0))
        elif len(sim_frames) == 4:
            self.campaign.world.events.append(Event("rival_destroyed", 0, 0))

    def tracked_draw(self, screen, run, cursor):
        nonlocal frame_idx
        frame_idx += 1
        ticks_at_frame.append(len(sim_frames))
        if frame_idx == 3:
            # Pressed during hitstop: must stay latched until sim tick 3.
            pygame.event.post(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_SPACE))
        elif frame_idx == 7:
            # Open pause menu right after rival_destroyed triggers 4-tick hitstop.
            pygame.event.post(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_ESCAPE))
        elif frame_idx == 8:
            # Close pause menu via Tab so hitstop stays cleared and tick 5 runs next frame.
            pygame.event.post(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_TAB))
        real_draw(self, screen, run, cursor)

    monkeypatch.setattr(
        app, "_open_window", lambda headless, fullscreen=False: pygame.display.set_mode(app.VIEW)
    )
    monkeypatch.setattr(app, "ticks_due", fake_ticks_due)
    monkeypatch.setattr(app.Session, "tick", tracked_tick)
    monkeypatch.setattr(app.PixelView, "draw", tracked_draw)

    options = app.Options(
        condition="off",
        mute=True,
        skip_title=True,
        frames=9,
        trace=tmp_path / "trace.jsonl",
    )
    assert app.play(options) == 0
    # Tick counts after each rendered frame:
    # f1:1, f2:2 (hitstop=3, batch broke), f3:2, f4:2, f5:2, f6:3 (dodge consumed),
    # f7:4 (hitstop=4), f8:4 (paused, hitstop cleared), f9:5 (stepped right away).
    assert ticks_at_frame == [1, 2, 2, 2, 2, 3, 4, 4, 5]
    assert sim_frames[2].dodge is True, "dodge press during hitstop must stay latched"
    assert sim_frames[3].dodge is False


def test_hitstop_never_triggers_in_headless_or_replay(monkeypatch, tmp_path) -> None:
    _isolate_settings(monkeypatch, tmp_path)
    os.environ["SDL_VIDEODRIVER"] = "dummy"
    os.environ["SDL_AUDIODRIVER"] = "dummy"

    rec_path = tmp_path / "hitstop_replay.json"
    real_session_tick = app.Session.tick
    headless_ticks = 0

    def headless_tick(self, frame):
        nonlocal headless_ticks
        real_session_tick(self, frame)
        headless_ticks += 1
        if headless_ticks == 1:
            self.campaign.world.events.append(Event("rival_destroyed", 0, 0))

    monkeypatch.setattr(app.Session, "tick", headless_tick)
    assert (
        app.play(
            app.Options(
                headless=True,
                frames=5,
                condition="off",
                mute=True,
                record=rec_path,
            )
        )
        == 0
    )
    assert headless_ticks == 5, "headless runs never freeze on impact events"

    # Windowed replay of the same recording must also step every frame with zero hitstop.
    real_step = app.Campaign.step
    replay_ticks = 0
    ticks_per_frame: list[int] = []
    real_draw = app.PixelView.draw

    def replay_step(self, frame):
        nonlocal replay_ticks
        real_step(self, frame)
        replay_ticks += 1
        if replay_ticks == 1:
            self.world.events.append(Event("rival_destroyed", 0, 0))

    def track_replay_draw(self, screen, run, cursor):
        ticks_per_frame.append(replay_ticks)
        real_draw(self, screen, run, cursor)

    monkeypatch.setattr(
        app, "_open_window", lambda headless, fullscreen=False: pygame.display.set_mode(app.VIEW)
    )
    monkeypatch.setattr(
        app, "ticks_due", lambda paused, headless, acc, elapsed: (0, 0.0) if paused else (1, 0.0)
    )
    monkeypatch.setattr(app.Campaign, "step", replay_step)
    monkeypatch.setattr(app.PixelView, "draw", track_replay_draw)
    assert app.play(app.Options(headless=False, replay=rec_path, mute=True)) == 0
    assert replay_ticks == 5
    assert ticks_per_frame[:5] == [1, 2, 3, 4, 5]


@pytest.mark.parametrize("name", ("LINESMAN", "TRANSFORMER", "GRID CORE"))
@pytest.mark.parametrize("protocol", ("clamp", "insulate", "oscillate"))
def test_boss_hud_title_and_protocol_icon_do_not_overlap(
    monkeypatch, name: str, protocol: str
) -> None:
    os.environ["SDL_VIDEODRIVER"] = "dummy"
    pygame.init()
    try:
        pygame.display.set_mode((256, 144))
        bg = rgb("px.floor.2")

        def render_hud(**overrides) -> pygame.Surface:
            surface = pygame.Surface((256, 144))
            surface.fill(bg)
            params = {
                "charge": 6,
                "max_charge": 6,
                "rival_health": 1.0,
                "rival_name": name,
                "rival_phases": 3,
                "rival_phase": 1,
                "rival_protocol": protocol,
            }
            params.update(overrides)
            hud.draw(surface, hud.Hud(**params))
            return surface

        def diff_pixels(a: pygame.Surface, b: pygame.Surface) -> set[tuple[int, int]]:
            return {
                (x, y)
                for y in range(40)
                for x in range(50, 210)
                if a.get_at((x, y))[:3] != b.get_at((x, y))[:3]
            }

        with_title = render_hud(rival_protocol=None)
        with monkeypatch.context() as ctx:
            ctx.setattr(hud, "text", lambda *args, **kwargs: pygame.Rect(0, 0, 0, 0))
            bar_only = render_hud(rival_protocol=None)
            with_icon = render_hud()

        title_pixels = diff_pixels(with_title, bar_only)
        icon_pixels = diff_pixels(with_icon, bar_only)
        assert title_pixels and icon_pixels
        assert title_pixels.isdisjoint(icon_pixels), (name, protocol)
        assert max(y for _, y in title_pixels) < min(y for _, y in icon_pixels), (name, protocol)

        # Phase-change shifting banner clears both the bar notches above and notices at y = 33.
        shifting = render_hud(rival_changing=True, rival_phase=2)
        steady = render_hud(rival_changing=False, rival_phase=2)
        banner_pixels = {(x, y) for x, y in diff_pixels(shifting, steady) if y >= 19}
        assert banner_pixels
        assert min(y for _, y in banner_pixels) >= 20
        assert max(y for _, y in banner_pixels) < 33
    finally:
        pygame.quit()
        hud.forget()
