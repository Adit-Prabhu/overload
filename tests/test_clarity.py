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


def test_walking_onto_a_charge_never_spawns_a_distant_flyer() -> None:
    from overload.game.view import PixelView

    campaign = Campaign(1)
    world = campaign.world
    view = PixelView(campaign)
    world.charges.append(Charge(world.new_id(), "burst", world.player.x, world.player.y + 16.0))
    for _ in range(10):
        campaign.step(InputFrame(move_y=1))
        view.after_tick(campaign)
        if "burst" in world.unlocked:
            break
    assert "burst" in world.unlocked
    assert not view.flyers, "a contact pickup within 11 px never spawns a duplicate flyer"


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


@pytest.mark.parametrize("stage", ["power", "dodge", "fuse", "fuse_box"])
def test_hints_fit_left_of_the_power_slots_with_long_keys(display, stage) -> None:
    from overload.art.pixel import hud
    from overload.game.view import HINT_RIGHT, PixelView

    binds = Keybinds()
    for action, key in (
        ("power_q", "right shift"),
        ("power_e", "right ctrl"),
        ("dodge", "left shift"),
        ("menu", "caps lock"),
    ):
        binds.bind(action, key)
    campaign = Campaign(1)
    view = PixelView(campaign)
    view.binds = view.coach.binds = binds
    world = campaign.world
    view.coach.learned |= {"move", "fire"}
    view.coach.fight = True
    if stage != "dodge":
        view.coach.learned.add("dodge")
    world.unlocked.extend(["spark", "blink"])
    world.player.slots = ["spark", "blink"]
    if stage in ("fuse", "fuse_box"):
        view.coach.learned.add("power")
    if stage == "fuse_box":
        view.coach.target = (0.0, 0.0)
    drawn = []
    original = hud.text

    def record(target, message, pos, *args, **kwargs):
        rect = original(target, message, pos, *args, **kwargs)
        drawn.append((message, rect))
        return rect

    hud.text = record
    try:
        view._coach(display, campaign, view.camera_offset())
    finally:
        hud.text = original
    ((message, rect),) = drawn
    assert rect.left >= 2 and rect.right <= HINT_RIGHT, message


def test_practice_mode_has_hints_but_no_fuse_box(display) -> None:
    from overload.game.view import PixelView
    from overload.sim.run import Run

    run = Run(1)
    view = PixelView(run)
    for _ in range(3):
        run.step(IDLE)
        view.after_tick(run)
    assert view.coach.target is None and view.coach.hint(run).endswith("MOUSE TO AIM")
    view.draw(display, run, (128, 72))


def test_the_arrow_points_from_the_edge_or_over_the_room(display) -> None:
    from overload.game.view import PixelView

    view = PixelView(Campaign(1))
    for point in ((128.0, 72.0), (900.0, 72.0), (-400.0, -400.0), (128.0, 999.0)):
        view._arrow(display, point)


@pytest.mark.parametrize("count", [0, 8, 10, 11, 16, 22, 23, 30, 35])
def test_ending_fits_many_powers_and_caps_overflow_inside_the_view(display, count) -> None:
    from overload.art.palette import rgb
    from overload.art.pixel import hud
    from overload.game.view import PixelView
    from overload.sim.powers import ABILITIES

    view = PixelView(Campaign(1))
    powers = {name: i + 1 for i, name in enumerate(ABILITIES[:count])}
    drawn: list[tuple[str, pygame.Rect]] = []
    original = hud.text

    def record(target, message, pos, *args, **kwargs):
        rect = original(target, message, pos, *args, **kwargs)
        drawn.append((message, rect))
        return rect

    hud.text = record
    try:
        view.draw_ending(
            display, 185.0, 1, 120, powers, {"1": 1800, "2": 2400, "3": 3600}, can_return=True
        )
    finally:
        hud.text = original
    texts = [msg for msg, _ in drawn]
    assert "SPACE TITLE   ESC QUIT" in texts
    if count > 22:
        assert f"+{count - 21}" in texts
    else:
        assert not any(msg.startswith("+") for msg in texts)
    if count >= 8:
        colors = {display.get_at((x, y))[:3] for x in range(256) for y in range(72, 120)}
        assert rgb("px.rarity.legendary") in colors
    for msg, rect in drawn:
        assert rect.left >= 0 and rect.right <= 256, f"{msg} clipped horizontally: {rect}"
        assert rect.top >= 0 and rect.bottom <= 144, f"{msg} clipped vertically: {rect}"

    # Non-interactive ending keeps the quit-only footer.
    drawn.clear()
    hud.text = record
    try:
        view.draw_ending(display, 185.0, 0, 50, {}, {}, can_return=False)
    finally:
        hud.text = original
    assert "ESC TO QUIT" in [msg for msg, _ in drawn]


def test_hud_slots_show_rarity_marks_and_ready_flash(display) -> None:
    from overload.art.palette import rgb
    from overload.art.pixel import hud
    from overload.game.view import PixelView
    from overload.sim.powers import COOLDOWN_KEYS

    campaign = Campaign(1)
    world = campaign.world
    world.unlocked = ["spark", "blink", "chain_jump"]
    world.player.slots = ["chain_jump", "spark"]
    view = PixelView(campaign)
    world.player.cooldowns[COOLDOWN_KEYS["chain_jump"]] = 2
    view.after_tick(campaign)
    assert view.ready_flash == [0, 0]
    world.player.cooldowns[COOLDOWN_KEYS["chain_jump"]] = 0
    view.after_tick(campaign)
    assert view.ready_flash[0] == 6 and view.ready_flash[1] == 0

    # Immediate recast cancels ready_flash so a cooling slot never flashes white.
    world.player.cooldowns[COOLDOWN_KEYS["chain_jump"]] = 10
    view.after_tick(campaign)
    assert view.ready_flash == [0, 0]

    # Natural decay runs down to 0 over 6 ticks.
    world.player.cooldowns[COOLDOWN_KEYS["chain_jump"]] = 0
    view.after_tick(campaign)
    assert view.ready_flash[0] == 6
    for _ in range(6):
        view.after_tick(campaign)
    assert view.ready_flash == [0, 0]

    # Dying while cooling and retrying never triggers a spurious ready flash.
    world.player.cooldowns[COOLDOWN_KEYS["chain_jump"]] = 10
    view.after_tick(campaign)
    world.outcome = "down"
    view.after_tick(campaign)
    world.outcome = "playing"
    world.player.cooldowns[COOLDOWN_KEYS["chain_jump"]] = 0
    view.after_tick(campaign)
    assert view.ready_flash == [0, 0]

    screen = pygame.Surface((256, 144))
    hud.draw(
        screen,
        hud.Hud(
            charge=6,
            max_charge=6,
            sockets=("chain_jump", "spark"),
            ready_flash=(6, 0),
            keys=("LSH", "RSH"),
        ),
    )
    # Slot 0 border at (210 - 1, 120 - 1) flashes fx.flash while ready_flash > 0 and ready.
    assert screen.get_at((209, 119))[:3] == rgb("fx.flash")

    # Cooling slot suppresses ready_flash even if passed nonzero.
    screen.fill(rgb("px.void"))
    hud.draw(
        screen,
        hud.Hud(
            charge=6,
            max_charge=6,
            sockets=("chain_jump", "spark"),
            cooldowns=(0.5, 0.0),
            ready_flash=(6, 0),
        ),
    )
    assert screen.get_at((209, 119))[:3] == rgb("px.wall.2")

    screen.fill(rgb("px.void"))
    hud.draw(
        screen,
        hud.Hud(charge=6, max_charge=6, sockets=("chain_jump", "spark"), ready_flash=(0, 0)),
    )
    assert screen.get_at((209, 119))[:3] == rgb("px.rarity.legendary")
    # Three legendary crosses sit below the slot inside the 256 x 144 frame.
    colors = {screen.get_at((x, y))[:3] for x in range(210, 228) for y in range(136, 141)}
    assert rgb("px.rarity.legendary") in colors
