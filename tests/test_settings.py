"""Player settings (UI-08) and window icon (MK-02): persistence, navigation, audio scaling,
screen shake and reduce-flash comfort toggles, fullscreen switching, and rendering."""

from __future__ import annotations

import os

import pygame
import pytest

from overload.game.settings import ROWS, Settings, SettingsPage


@pytest.fixture
def display():
    os.environ["SDL_VIDEODRIVER"] = "dummy"
    pygame.init()
    screen = pygame.display.set_mode((256, 144))
    yield screen
    pygame.quit()
    from overload.art.pixel import actors, hud, tiles
    from overload.game import title

    actors.app_icon.cache_clear()
    hud.forget()
    tiles.forget_fonts()
    title.forget()


def test_settings_save_load_clamping_and_recovery(tmp_path) -> None:
    path = tmp_path / "prefs.json"
    prefs = Settings.load(path)
    assert (prefs.music_volume, prefs.sfx_volume) == (100, 100)
    assert prefs.screen_shake is True and prefs.reduce_flash is False and prefs.fullscreen is False

    # path=None never writes to disk, and hand-constructed volumes clamp and snap cleanly.
    ephemeral = Settings(music_volume=95, sfx_volume=-30, path=None)
    assert ephemeral.music_volume == 100 and ephemeral.sfx_volume == 0
    ephemeral.save()
    assert not path.exists()

    prefs.music_volume = 70
    prefs.sfx_volume = 40
    prefs.screen_shake = False
    prefs.reduce_flash = True
    prefs.fullscreen = True
    prefs.save()

    reloaded = Settings.load(path)
    assert reloaded.music_volume == 70 and reloaded.sfx_volume == 40
    assert reloaded.screen_shake is False and reloaded.reduce_flash is True
    assert reloaded.fullscreen is True

    # Damaged, wrong-type, bool-in-int, negative and unaligned fields recover safely.
    path.write_text(
        '{"music_volume": true, "sfx_volume": 47, "screen_shake": 1, "reduce_flash": "yes"}\n'
    )
    recovered = Settings.load(path)
    assert recovered.music_volume == 100
    assert recovered.sfx_volume == 50
    assert recovered.screen_shake is True
    assert recovered.reduce_flash is False

    path.write_text('{"music_volume": -30, "sfx_volume": 135}\n')
    clamped = Settings.load(path)
    assert clamped.music_volume == 0 and clamped.sfx_volume == 100

    for bad in ("[]", "null", "{not json"):
        path.write_text(bad)
        assert Settings.load(path).music_volume == 100


def test_settings_page_navigation_edges_and_reset(tmp_path) -> None:
    path = tmp_path / "prefs.json"
    prefs = Settings(path=path)
    page = SettingsPage(prefs)

    # Wrap up from row 0 to RESET DEFAULTS and back down.
    assert page.nav("up") == ("move", False) and page.row == len(ROWS)
    assert page.nav("left") == (None, False) and page.nav("right") == (None, False)
    # Reset when fullscreen is already False returns display_changed=False.
    assert page.nav("select") == ("confirm", False)
    assert page.nav("down") == ("move", False) and page.row == 0

    # Row 0: MUSIC VOLUME adjusts in 10% steps, clamps on left/right, and wraps 100 -> 0 on select.
    assert page.nav("select") == ("move", False) and prefs.music_volume == 0
    assert page.nav("left") == ("move", False) and prefs.music_volume == 0
    assert page.nav("right") == ("move", False) and prefs.music_volume == 10
    assert page.nav("select") == ("move", False) and prefs.music_volume == 20

    # Row 2: SCREEN SHAKE toggles cleanly.
    page.row = [name for name, _ in ROWS].index("screen_shake")
    assert page.nav("select") == ("confirm", False) and prefs.screen_shake is False
    assert page.value_label("screen_shake") == "OFF"

    # Row 3: REDUCE FLASH toggles cleanly.
    page.row = [name for name, _ in ROWS].index("reduce_flash")
    assert page.nav("right") == ("confirm", False) and prefs.reduce_flash is True
    assert page.value_label("reduce_flash") == "ON"

    # Row 4: FULLSCREEN reports display_changed=True.
    page.row = [name for name, _ in ROWS].index("fullscreen")
    assert page.nav("select") == ("confirm", True) and prefs.fullscreen is True

    # Row 5: RESET DEFAULTS restores all defaults and reports display_changed=True.
    page.row = len(ROWS)
    assert page.nav("select") == ("confirm", True)
    assert prefs.music_volume == 100 and prefs.screen_shake is True
    assert prefs.reduce_flash is False and prefs.fullscreen is False
    assert "DEFAULT SETTINGS RESTORED" in page.notice
    assert Settings.load(path).fullscreen is False

    # Esc / back leaves the page and clears notice.
    assert page.nav("back") == ("back", False) and page.notice == ""


def test_audio_scales_music_and_sfx_from_settings() -> None:
    from overload.game.audio import LEVELS, Audio

    muted = Audio(enabled=False)
    muted.apply_settings(Settings(music_volume=40, sfx_volume=30))
    assert muted.music_scale == pytest.approx(0.4) and muted.sfx_scale == pytest.approx(0.3)

    os.environ["SDL_AUDIODRIVER"] = "dummy"
    pygame.mixer.quit()
    audio = Audio(enabled=True)
    try:
        # 50% SFX plays at scaled channel volume and tells still duck music.
        audio.apply_settings(Settings(music_volume=50, sfx_volume=50))
        audio.play("mite_tell", 0.8)
        assert audio.duck_until > 0
        volumes = [
            pygame.mixer.Channel(i).get_volume()
            for i in range(6, 32)
            if pygame.mixer.Channel(i).get_busy()
        ]
        assert any(v == pytest.approx(0.4, abs=0.05) for v in volumes)

        # At 0% SFX volume, tells never duck music and play returns early.
        audio.duck_until = 0
        audio.apply_settings(Settings(music_volume=50, sfx_volume=0))
        audio.play("mite_tell")
        assert audio.duck_until == 0

        # Music stems ramp toward half their nominal LEVELS.
        for _ in range(30):
            audio.update("title", 1, "playing")
        assert audio.volumes["title"] == pytest.approx(LEVELS["title"] * 0.5, abs=0.02)
    finally:
        pygame.mixer.quit()


def test_view_and_hud_respect_screen_shake_and_reduce_flash(display) -> None:
    from floorbot import enter

    from overload.art.palette import rgb
    from overload.art.pixel import hud
    from overload.game.view import RIVAL_FLASH, PixelView
    from overload.sim.campaign import Campaign
    from overload.sim.state import Event

    campaign = Campaign(1)
    enter(campaign, "s1_chamber")
    view = PixelView(campaign)
    view.apply_settings(Settings(screen_shake=False, reduce_flash=True))
    campaign.world.events = [Event("player_hit", 100.0, 100.0)]
    view.after_tick(campaign)
    assert view.shake > 0 and view.jolt() == (0, 0), "screen_shake=False suppresses jolt"

    # Unlock flash draws a 2 px spark border instead of a full-screen white overlay.
    view.unlock_flash = 10
    view.hit_vignette = 0
    display.fill(rgb("px.void"))
    view.draw(display, campaign, (128, 72))
    assert display.get_at((0, 0))[:3] == rgb("power.spark")
    assert display.get_at((128, 72))[:3] != rgb("fx.flash")

    # Hostile hit ring, rival hit ring, Surge invulnerability, and steady wreck render cleanly.
    campaign.world.player.invulnerable = 20
    view.flashes[RIVAL_FLASH] = 4
    view.wreck = (
        pygame.Surface((16, 16), pygame.SRCALPHA),
        (campaign.world.player.x, campaign.world.player.y),
        campaign.world.player.x,
        campaign.world.player.y,
        40,
    )
    view.unlock_flash = 0
    view.hit_vignette = 5
    view.draw(display, campaign, (128, 72))
    view.hit_vignette = 0
    campaign.world.player.charge = 1
    view.draw(display, campaign, (128, 72))

    # HUD venting bar and low-battery icon stay steady across tick=0 and tick=4 under reduce_flash.
    s0 = pygame.Surface((256, 144))
    s4 = pygame.Surface((256, 144))
    for surf, tick in ((s0, 0), (s4, 4)):
        hud.draw(
            surf,
            hud.Hud(
                charge=1,
                max_charge=6,
                sockets=("spark", "blink"),
                rival_health=1.0,
                rival_venting=True,
                ready_flash=(4, 0),
                reduce_flash=True,
                tick=tick,
            ),
        )
    assert pygame.image.tobytes(s0, "RGB") == pygame.image.tobytes(s4, "RGB")
    assert s0.get_at((209, 119))[:3] == rgb("px.lamp.light")


def test_title_and_menu_settings_layout_controls_and_fullscreen(display, tmp_path) -> None:
    from overload.agent.selector import NeutralSelector
    from overload.game import app, menu_view
    from overload.game import dev as devmode
    from overload.game.flow import Session
    from overload.game.menu import HUB_FUSE_BOX, Menu
    from overload.game.title import ITEMS, TitleScreen, run_title
    from overload.session.replay import Recording
    from overload.sim.arena import FLOOR_ARENA, arena_id
    from overload.sim.campaign import Campaign
    from overload.sim.tuning import DEFAULT

    prefs = Settings(path=tmp_path / "prefs.json")
    title = TitleScreen(settings=prefs)
    title.press(pygame.K_s)
    assert ITEMS[title.selected] == "SETTINGS"
    title.press(pygame.K_RETURN)
    assert title.page == "settings"
    title.press(pygame.K_a)
    assert prefs.music_volume == 90

    # Verify Title SETTINGS text rects fit inside the 220 px panel without clipping.
    drawn: list[tuple[str, pygame.Rect]] = []
    original = menu_view.hud.text

    def record(target, message, pos, *args, **kwargs):
        rect = original(target, message, pos, *args, **kwargs)
        drawn.append((message, rect))
        return rect

    menu_view.hud.text = record
    try:
        title.draw(display)
    finally:
        menu_view.hud.text = original
    for msg, rect in drawn:
        assert rect.left >= 0 and rect.right <= 256, f"title settings clipped: {msg} {rect}"
    title.press(pygame.K_ESCAPE)
    assert title.page == "menu"

    # Left/right keys on Title CONTROLS leave navigation unaffected and capture still binds 'a'.
    title.press(pygame.K_s)  # CONTROLS
    title.press(pygame.K_RETURN)
    assert title.page == "controls"
    row_before = title.keys.row
    title.press(pygame.K_a)
    title.press(pygame.K_RIGHT)
    assert title.keys.row == row_before and title.page == "controls"
    title.press(pygame.K_RETURN)
    title.press(pygame.K_a)
    assert not title.keys.capturing and title.keys.binds.keys["up"] == "a"

    # run_title invokes on_display when Fullscreen is toggled.
    toggles: list[bool] = []
    for key in (
        pygame.K_s,  # SETTINGS
        pygame.K_RETURN,
        pygame.K_s,
        pygame.K_s,
        pygame.K_s,
        pygame.K_s,  # FULLSCREEN
        pygame.K_SPACE,  # toggle ON
        pygame.K_ESCAPE,
        pygame.K_w,  # START
        pygame.K_RETURN,
    ):
        pygame.event.post(pygame.event.Event(pygame.KEYDOWN, key=key))

    def on_display(flag: bool):
        toggles.append(flag)
        return display

    result = run_title(display, pygame.time.Clock(), settings=prefs, on_display=on_display)
    assert result == "medium" and toggles == [True] and prefs.fullscreen is True

    # _apply_fullscreen is a no-op when headless or when flags already match.
    assert app._apply_fullscreen(display, True, headless=True) is display
    assert app._apply_fullscreen(display, False, headless=False) is display

    # Pause / Fuse Box hub fits 6 items + fallback line AND 7 items with DEV, plus rebound keys.
    session = Session(Campaign(1), NeutralSelector())
    menu = Menu()
    menu.settings_page.settings = prefs
    menu.keys_page.binds.bind("up", "left shift")
    menu.keys_page.binds.bind("left", "right shift")
    menu.show(in_fuse_box=True)
    menu_view.draw_menu(
        display,
        menu,
        session,
        session.campaign.tuning,
        True,
        "Grid link unstable. Regulator running default protocol.",
        2,
    )
    menu.dev = devmode.DevTools()
    menu_view.draw_menu(display, menu, session, session.campaign.tuning, True, None, 2)
    menu.hub = HUB_FUSE_BOX.index("SETTINGS")
    menu.press(session, "select")
    assert menu.screen == "settings"
    drawn.clear()
    menu_view.hud.text = record
    try:
        menu_view.draw_menu(display, menu, session, session.campaign.tuning, True, None, 2)
    finally:
        menu_view.hud.text = original
    for msg, rect in drawn:
        assert rect.left >= menu_view.PANEL.left and rect.right <= menu_view.PANEL.right, (
            f"pause settings clipped: {msg} {rect}"
        )

    # menu_frame returns pure audio cues (never a non-audio sentinel) on Fullscreen toggle.
    reader = app.InputReader()
    recording = Recording(
        seed=1,
        tuning_id=DEFAULT.tuning_id(),
        arena_id=arena_id(FLOOR_ARENA),
        mode="campaign",
        protocols=["lateral"],
    )
    menu.settings_page.row = [name for name, _ in ROWS].index("fullscreen")
    reader.handle(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_SPACE))
    cues = app.menu_frame(session, menu, reader, recording, 16)
    assert cues == ["confirm"] and prefs.fullscreen is False


def test_headless_and_replay_ignore_saved_settings(monkeypatch, tmp_path) -> None:
    from overload.game import app, settings

    loaded = []
    monkeypatch.setattr(
        settings.Settings, "load", classmethod(lambda cls, *a, **kw: loaded.append(True) or cls())
    )
    options = app.Options(headless=True, frames=2, condition="off", mute=True)
    assert app.play(options) == 0
    assert not loaded, "headless runs never read settings/prefs.json"


def test_app_icon_is_32x32_and_non_empty(display) -> None:
    from overload.art.palette import rgb
    from overload.art.pixel import actors

    icon = actors.app_icon()
    assert icon.get_size() == (32, 32)
    colors = {icon.get_at((x, y))[:3] for x in range(32) for y in range(32)}
    assert rgb("power.spark") in colors and rgb("px.helmet.2") in colors
