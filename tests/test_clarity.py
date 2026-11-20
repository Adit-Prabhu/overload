"""The clarity pass (pilot playtest, Nov 19): first-run hints, the Fuse Box way on, charges
visibly pulled in, and the boss reward shown. All cosmetic: none of it touches the sim."""

from __future__ import annotations

import os

import pygame
import pytest
from floorbot import enter

from overload.game.coach import Coach
from overload.game.keybinds import Keybinds
from overload.sim.campaign import Campaign
from overload.sim.inputs import IDLE, InputFrame
from overload.sim.state import Charge, Projectile


@pytest.fixture(autouse=True)
def display():
    os.environ["SDL_VIDEODRIVER"] = "dummy"
    pygame.init()
    yield pygame.display.set_mode((256, 144))
    pygame.quit()
    from overload.art.pixel import hud, tiles

    hud.forget()
    tiles.forget_fonts()


def step(campaign: Campaign, coach: Coach, frame: InputFrame = IDLE, ticks: int = 1) -> None:
    for _ in range(ticks):
        campaign.step(frame)
        coach.update(campaign)


def test_hints_come_one_at_a_time_and_go_once_learned() -> None:
    campaign, coach = Campaign(1), Coach()
    step(campaign, coach)
    assert coach.hint(campaign) == "WASD TO MOVE  MOUSE TO AIM"
    step(campaign, coach, InputFrame(move_x=1), 40)
    assert coach.hint(campaign) == "HOLD LEFT CLICK TO FIRE"
    world = campaign.world
    step(campaign, coach, InputFrame(fire=True, aim_x=world.player.x + 50, aim_y=world.player.y))
    assert coach.hint(campaign) is None, "no dodge hint before any fight"
    coach.fight = True
    assert coach.hint(campaign) == "SPACE TO DODGE THROUGH SHOTS"
    coach.learned.add("dodge")
    world.unlocked.extend(["spark", "blink"])
    world.player.slots = ["spark", "blink"]
    assert coach.hint(campaign) == "Q OR E USES A STOLEN POWER"
    coach.learned.add("power")
    assert coach.hint(campaign) == "TAB THEN FUSE: MIX TWO POWERS"
    world.fusions = 1
    step(campaign, coach)
    assert coach.hint(campaign) is None


def test_hints_name_the_bound_keys() -> None:
    binds = Keybinds()
    binds.bind("up", "i")
    binds.bind("dodge", "left shift")
    campaign, coach = Campaign(1), Coach(binds)
    step(campaign, coach)
    assert coach.hint(campaign).startswith("IASD")
    coach.learned |= {"move", "fire"}
    coach.fight = True
    assert coach.hint(campaign) == "LEFT SHIFT TO DODGE THROUGH SHOTS"


def test_after_a_chamber_the_hint_points_to_the_fuse_box() -> None:
    campaign, coach = Campaign(1), Coach()
    enter(campaign, "s1_chamber")
    rival = campaign.world.rival
    rival.boot, rival.health, rival.phase = 0, 1, 3
    campaign.world.projectiles.append(Projectile(101, rival.x, rival.y, 0, 0, 1, 1, False, 5))
    for _ in range(10):
        campaign.world.player.invulnerable = 10**9
        step(campaign, coach)
    assert "s1_chamber" in campaign.world.cleared
    assert coach.hint(campaign) == "FOLLOW THE ARROW TO THE FUSE BOX"
    assert coach.target is not None


def test_charges_left_on_the_floor_fly_into_the_surge_at_a_clear() -> None:
    from overload.game.view import PixelView

    campaign = Campaign(1)
    enter(campaign, "s1_hall")
    world = campaign.world
    view = PixelView(campaign)
    if "spark" not in world.unlocked:
        world.unlocked.append("spark")  # an absorb (a first steal shows SPARK STOLEN instead)
    world.charges.append(Charge(world.new_id(), "spark", world.player.x + 80, world.player.y))
    world.hostiles = []
    world.warps = []
    from overload.floor import WAVES

    world.wave = len(WAVES["s1_hall"]) - 1
    before = campaign.state_hash()
    campaign.step(IDLE)
    view.after_tick(campaign)
    assert not world.charges and view.flyers, "the absorbed charge flies, not vanishes"
    assert view.notice[0] == "ROOM CLEAR. CHARGES PULLED IN"
    for _ in range(70):
        campaign.step(IDLE)
        view.after_tick(campaign)
    assert not view.flyers, "every flyer lands within its time"
    assert before != campaign.state_hash()  # the sim moved on, untouched by the view


def test_a_beaten_chassis_shows_its_reward_and_not_room_clear() -> None:
    from overload.game.view import PixelView

    campaign = Campaign(1)
    enter(campaign, "s1_chamber")
    world = campaign.world
    world.unlocked.extend(p for p in ("spark", "blink") if p not in world.unlocked)
    rival = world.rival
    rival.boot, rival.health, rival.phase = 0, 1, 3
    view = PixelView(campaign)
    world.player.invulnerable = 10**9
    campaign.step(IDLE)
    view.after_tick(campaign)
    world.projectiles.append(Projectile(101, rival.x, rival.y, 0, 0, 1, 1, False, 5))
    for _ in range(5):
        world.player.invulnerable = 10**9
        campaign.step(IDLE)
        view.after_tick(campaign)
    assert view.boss_banner is not None and view.reward == ["spark", "blink"]
    assert view.notice is None or "ROOM CLEAR" not in view.notice[0]
    assert len(view.flyers) == 2
    screen = pygame.Surface((256, 144))
    view.boss_banner = (view.boss_banner[0], 60)
    view.draw(screen, campaign, (128, 72))


def test_the_fuse_box_hub_shows_ready_and_the_spares(display) -> None:
    from overload.game import menu_view
    from overload.game.flow import Session
    from overload.game.menu import Menu

    campaign = Campaign(1)
    campaign.world.unlocked.extend(["spark", "blink"])
    campaign.world.bank = {"spark": 2, "blink": 1}
    session = Session.__new__(Session)
    session.campaign = campaign
    menu = Menu()
    menu.show(in_fuse_box=True)
    texts = []
    original = menu_view.hud.text

    def record(target, message, *args, **kwargs):
        texts.append(message)
        return original(target, message, *args, **kwargs)

    menu_view.hud.text = record
    try:
        menu_view.draw_hub(display, menu, session, True, None, 2)
        assert "READY" in texts and "CONTINUE >>" in texts
        assert "SPACE ON CONTINUE: ENTER SECTOR 2" in texts
        assert "SPARE CHARGES" in texts and "2" in texts
        texts.clear()
        menu_view.draw_hub(display, menu, session, False, None, 2)
        assert "ROUTING POWER..." in texts and "CONTINUE" in texts
    finally:
        menu_view.hud.text = original
