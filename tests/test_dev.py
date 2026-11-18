"""Dev mode (game/dev.py): only on a machine with the git-ignored gate file, never study
data (no model call, no trace, no recording), and each test tool does what it says."""

from __future__ import annotations

import pytest
from floorbot import fuse_box_with

from overload.game import dev as devmode
from overload.game.app import Options, play
from overload.game.menu import HUB_PAUSED, Menu
from overload.paths import ROOT
from overload.sim.campaign import Campaign
from overload.sim.inputs import IDLE
from overload.sim.powers import BASE_POWERS, FUSED, RARITIES, owned_result, rarity_of


@pytest.fixture
def gate(tmp_path, monkeypatch):
    """Point the gate at a scratch file. Returns its path (not created yet)."""
    path = tmp_path / ".overload-dev"
    monkeypatch.setattr(devmode, "GATE", path)
    return path


def test_the_gate_file_is_git_ignored_and_never_tracked() -> None:
    import subprocess

    ignored = subprocess.run(["git", "check-ignore", "-q", ".overload-dev"], cwd=ROOT, check=False)
    tracked = subprocess.run(
        ["git", "ls-files", ".overload-dev"], cwd=ROOT, capture_output=True, text=True
    )
    assert ignored.returncode == 0 and tracked.stdout == ""


def test_dev_mode_refuses_to_start_without_the_gate(gate) -> None:
    assert not devmode.available()
    assert play(Options(dev=True, headless=True, frames=2)) == 2
    gate.write_text("")
    assert devmode.available()


def test_a_dev_run_never_calls_the_rival_or_writes_a_trace_or_recording(
    gate, tmp_path, monkeypatch
) -> None:
    gate.write_text("")
    monkeypatch.setenv("OVERLOAD_RIVAL_URL", "http://127.0.0.1:9")  # would be live otherwise

    def no_client(*args, **kwargs):
        raise AssertionError("a dev run must never build a rival client")

    monkeypatch.setattr("overload.game.app.TacticClient", no_client)
    trace, record = tmp_path / "t.jsonl", tmp_path / "r.json"
    options = Options(
        dev=True, headless=True, frames=3, condition="live", trace=trace, record=record
    )
    assert play(options) == 0
    assert options.condition == "off" and not trace.exists() and not record.exists()


def test_dev_mode_never_runs_replays_or_practice(gate, tmp_path) -> None:
    gate.write_text("")
    assert play(Options(dev=True, headless=True, practice=True)) == 2
    assert play(Options(dev=True, headless=True, replay=tmp_path / "any.json")) == 2


# The tools -----------------------------------------------------------------------------------


def test_god_mode_and_unlimited_charges_hold_every_tick() -> None:
    campaign = Campaign(1)
    tools = devmode.DevTools(no_cooldowns=True)
    world = campaign.world
    world.player.charge = 1
    world.player.cooldowns = {"teleport": 50}
    tools.before_tick(campaign)
    assert world.player.charge == campaign.tuning.player_max_charge
    assert set(BASE_POWERS) <= set(world.unlocked)
    assert all(world.bank[p] == devmode.SPARES for p in BASE_POWERS)
    assert world.player.cooldowns == {}
    world.player.charge = 0
    tools.after_tick(campaign)
    assert world.player.charge == campaign.tuning.player_max_charge


@pytest.mark.parametrize("rarity", RARITIES)
def test_next_roll_lands_on_the_forced_rarity(rarity) -> None:
    session = fuse_box_with("spark", "blink")
    tools = devmode.DevTools(force=devmode.FORCE.index(rarity.upper()))
    for _ in range(3):  # every roll, not only the first
        session.campaign.world.bank = {"spark": 9, "blink": 9}
        tools.before_roll(session, "spark", "blink")
        assert session.fuse("spark", "blink") == "fused"
        assert rarity_of(owned_result(session.campaign.world.unlocked, "spark", "blink")) == rarity


def test_grant_power_gives_it_with_its_ingredients_and_replaces_its_pair() -> None:
    world = Campaign(1).world
    devmode.grant(world, "meteor")
    assert {"blink", "burst", "meteor"} <= set(world.unlocked)
    world.player.slots = ["meteor", ""]
    devmode.grant(world, "displacer")
    assert "meteor" not in world.unlocked and world.player.slots == ["displacer", ""]
    assert set(devmode.GRANTABLE) == set(FUSED)


def test_skip_to_the_fuse_box_opens_it() -> None:
    campaign = Campaign(1)
    assert devmode.skip_sector(campaign) == "SKIPPED TO THE FUSE BOX"
    campaign.step(IDLE)
    assert campaign.stage == "fuse_box"
    assert devmode.skip_sector(campaign) == "ONLY DURING A SECTOR"


def test_the_dev_page_is_in_the_hub_only_in_dev_mode() -> None:
    session = fuse_box_with("spark")
    menu = Menu()
    menu.show(in_fuse_box=False)
    assert "DEV" not in menu.hub_items and menu.hub_items == HUB_PAUSED
    menu.dev = devmode.DevTools()
    assert menu.hub_items[-2:] == ("DEV", "QUIT")
    menu.hub = menu.hub_items.index("DEV")
    menu.press(session, "select")
    assert menu.screen == "dev"
    menu.press(session, "select")  # GOD MODE
    assert not menu.dev.god
    menu.dev_row = [r[0] for r in menu.dev.rows()].index("GRANT POWER")
    menu.press(session, "right")
    menu.press(session, "select")
    assert devmode.GRANTABLE[1] in session.campaign.world.unlocked


def test_every_dev_row_runs_in_the_fuse_box_without_error() -> None:
    session = fuse_box_with("spark")
    tools = devmode.DevTools()
    for row in range(len(tools.rows())):
        for key in ("left", "right", "select"):
            tools.press(session, row, key)
    assert session.campaign.stage == "fuse_box", "the sector tools do nothing here"


def test_clear_this_room_finishes_every_wave() -> None:
    """Review of PR #34: clearing only the live robots let the next wave warp in."""
    from floorbot import enter

    campaign = Campaign(1)
    enter(campaign, "s1_hall")
    assert campaign.world.active_room == "s1_hall" and campaign.world.wave == 0
    assert devmode.clear_room(campaign.world) == "ROOM CLEARED"
    for _ in range(3):
        campaign.step(IDLE)
    assert "s1_hall" in campaign.world.cleared and not campaign.world.active_room
    assert devmode.clear_room(campaign.world) == "NOT IN A FIGHT"


def test_defeat_the_regulator_clears_its_chamber() -> None:
    from floorbot import enter

    session = fuse_box_with("spark")
    campaign = Campaign(1)
    enter(campaign, "s1_chamber")
    session.campaign = campaign
    tools = devmode.DevTools()
    tools.press(session, [r[0] for r in tools.rows()].index("DEFEAT THE REGULATOR"), "select")
    campaign.step(IDLE)
    assert "s1_chamber" in campaign.world.cleared


def test_skipping_sector_three_goes_to_the_ending() -> None:
    from floorbot import skip_sector

    campaign = Campaign(1)
    for protocol in ("lateral", "lateral"):
        skip_sector(campaign)
        campaign.begin_next(protocol)
    assert campaign.encounter == 3
    assert devmode.skip_sector(campaign) == "SKIPPED TO THE ENDING"
    campaign.step(IDLE)
    assert campaign.stage == "ending"


def test_skipping_mid_meteor_does_not_carry_the_surge_back() -> None:
    campaign = Campaign(1)
    player = campaign.world.player
    player.leap, player.leap_x1, player.leap_y1 = 20, player.x, player.y
    devmode.skip_sector(campaign)
    campaign.step(IDLE)
    assert campaign.stage == "fuse_box" and player.leap == 0


def test_a_forced_rarity_with_no_chance_leaves_the_roll_alone() -> None:
    import dataclasses

    from overload.sim.tuning import DEFAULT

    session = fuse_box_with("spark", "blink")
    session.campaign.tuning = dataclasses.replace(DEFAULT, fuse_odds=(60, 40, 0))
    tools = devmode.DevTools(force=devmode.FORCE.index("LEGENDARY"))
    tools.before_roll(session, "spark", "blink")  # returns at once, never loops
    assert "NO CHANCE" in tools.notice and session.campaign.world.fusions == 0


def test_dev_stays_visible_over_every_menu(monkeypatch) -> None:
    import pygame

    from overload.art.palette import rgb
    from overload.art.pixel import hud
    from overload.game.app import draw_dev_tag

    monkeypatch.setenv("SDL_VIDEODRIVER", "dummy")
    pygame.init()  # the play() tests above shut pygame down
    hud.forget()

    screen = pygame.Surface((256, 144))
    screen.fill(rgb("px.outline"))  # whatever a menu or the ending drew
    draw_dev_tag(screen)
    lit = sum(
        screen.get_at((x, y))[:3] == rgb("px.hazard.1") for x in range(226, 256) for y in range(12)
    )
    assert lit > 20
