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


def test_settings_save_load_and_recover_from_damaged_file(tmp_path) -> None:
    path = tmp_path / "prefs.json"
    prefs = Settings.load(path)
    assert (prefs.music_volume, prefs.sfx_volume) == (100, 100)
    assert prefs.screen_shake is True and prefs.reduce_flash is False and prefs.fullscreen is False

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

    # Damaged or wrong-type fields fall back cleanly to defaults without crashing.
    path.write_text('{"music_volume": "loud", "sfx_volume": 135, "screen_shake": 1}\n')
    recovered = Settings.load(path)
    assert recovered.music_volume == 100
    assert recovered.sfx_volume == 100
    assert recovered.screen_shake is True

    path.write_text("{not json")
    assert Settings.load(path).music_volume == 100


def test_settings_page_navigation_edits_and_reset(tmp_path) -> None:
    path = tmp_path / "prefs.json"
    prefs = Settings(path=path)
    page = SettingsPage(prefs)

    # Row 0: MUSIC VOLUME adjusts in 10% steps and clamps at 0 and 100.
    assert page.nav("left") == ("move", False) and prefs.music_volume == 90
    for _ in range(12):
        page.nav("left")
    assert prefs.music_volume == 0
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

    os.environ["SDL_AUDIODRIVER"] = "dummy"
    pygame.mixer.quit()
    audio = Audio(enabled=True)
    try:
        prefs = Settings(music_volume=50, sfx_volume=0)
        audio.apply_settings(prefs)
        assert audio.music_scale == pytest.approx(0.5)
        assert audio.sfx_scale == 0.0
        # At 0% SFX volume, tells never duck music and play returns early.
        audio.play("mite_tell")
        assert audio.duck_until == 0
        # Music stems ramp toward half their nominal LEVELS.
        for _ in range(30):
            audio.update("title", 1, "playing")
        assert audio.volumes["title"] == pytest.approx(LEVELS["title"] * 0.5, abs=0.02)
    finally:
        pygame.mixer.quit()


def test_view_respects_screen_shake_and_reduce_flash(display) -> None:
    from overload.art.palette import rgb
    from overload.game.view import PixelView
    from overload.sim.campaign import Campaign
    from overload.sim.state import Event

    campaign = Campaign(1)
    view = PixelView(campaign)
    view.apply_settings(Settings(screen_shake=False, reduce_flash=True))
    campaign.world.events = [Event("player_hit", 100.0, 100.0)]
    view.after_tick(campaign)
    assert view.shake > 0 and view.jolt() == (0, 0), "screen_shake=False suppresses jolt"

    # Unlock flash draws a 2 px border pulse instead of a full-screen white overlay.
    view.unlock_flash = 10
    view.hit_vignette = 0
    display.fill(rgb("px.void"))
    view.draw(display, campaign, (128, 72))
    assert display.get_at((0, 0))[:3] == rgb("power.spark")
    assert display.get_at((128, 72))[:3] != rgb("fx.flash")


def test_title_and_menu_settings_pages_draw_and_update_fullscreen(display, tmp_path) -> None:
    from overload.agent.selector import NeutralSelector
    from overload.game import dev as devmode
    from overload.game import menu_view
    from overload.game.flow import Session
    from overload.game.menu import HUB_FUSE_BOX, Menu
    from overload.game.title import ITEMS, TitleScreen, run_title
    from overload.sim.campaign import Campaign

    prefs = Settings(path=tmp_path / "prefs.json")
    title = TitleScreen(settings=prefs)
    title.press(pygame.K_s)
    assert ITEMS[title.selected] == "SETTINGS"
    title.press(pygame.K_RETURN)
    assert title.page == "settings"
    title.press(pygame.K_a)
    assert prefs.music_volume == 90
    title.draw(display)
    title.press(pygame.K_ESCAPE)
    assert title.page == "menu"

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

    # Pause / Fuse Box hub fits 6 items + fallback line AND 7 items with DEV enabled.
    session = Session(Campaign(1), NeutralSelector())
    menu = Menu()
    menu.settings_page.settings = prefs
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
    menu_view.draw_menu(display, menu, session, session.campaign.tuning, True, None, 2)


def test_app_icon_is_32x32_and_non_empty(display) -> None:
    from overload.art.palette import rgb
    from overload.art.pixel import actors

    icon = actors.app_icon()
    assert icon.get_size() == (32, 32)
    colors = {icon.get_at((x, y))[:3] for x in range(32) for y in range(32)}
    assert rgb("power.spark") in colors and rgb("px.helmet.2") in colors
