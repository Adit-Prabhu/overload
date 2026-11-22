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


@pytest.mark.parametrize(
    ("chamber", "sector", "protocol", "expected"),
    [
        ("s1_chamber", 1, "pressure", "CLAMP PROTOCOL"),
        ("s2_chamber", 2, "spacing", "INSULATE PROTOCOL"),
        ("s3_chamber", 3, "lateral", "OSCILLATE PROTOCOL"),
        (None, 1, "lateral", "OSCILLATE PROTOCOL"),
    ],
)
def test_boss_intro_card_names_active_protocol(
    display, chamber, sector, protocol, expected
) -> None:
    from overload.art.pixel import hud
    from overload.game.view import PixelView
    from overload.sim.run import Run

    if chamber is None:
        from overload.sim.spawns import spawn_rival

        run = Run(1)
        rival = spawn_rival(run.world, 128.0, 72.0, protocol, run.tuning)
    else:
        run = Campaign(1)
        enter(run, chamber)
        rival = run.world.rival
    rival.protocol = protocol
    view = PixelView(run)
    view.sector = sector
    # Slide start (elapsed == 0) renders safely without error.
    rival.boot = run.tuning.rival_boot
    view._intro_card(display, rival, run.tuning)
    # Fully slid in (elapsed >= INTRO_SLIDE): verify text and bounds.
    rival.boot = run.tuning.rival_boot - 20
    drawn: list[tuple[str, pygame.Rect]] = []
    original = hud.text

    def record(target, message, pos, *args, **kwargs):
        rect = original(target, message, pos, *args, **kwargs)
        drawn.append((message, rect))
        return rect

    hud.text = record
    try:
        view._intro_card(display, rival, run.tuning)
    finally:
        hud.text = original
    texts = [msg for msg, _ in drawn]
    assert expected in texts
    assert f"SECTOR {sector} REGULATOR" in texts
    panel_left = (256 - 170) // 2
    panel_right = panel_left + 170
    for msg, rect in drawn:
        assert panel_left < rect.left and rect.right < panel_right, f"{msg} clipped card: {rect}"
        assert rect.bottom <= 112, f"{msg} overlaps HUD key tabs: {rect}"


def test_vent_crit_heavy_hit_shield_deflect_and_player_hit_feedback(display) -> None:
    from overload.art.palette import rgb
    from overload.game.view import BLAST_TICKS, DEFLECT_TICKS, PixelView
    from overload.sim.difficulty import PRESETS
    from overload.sim.state import Event

    campaign = Campaign(1)
    view = PixelView(campaign)
    # Normal light hit: no shake, no blast ring.
    campaign.world.events = [Event("rival_hit", 100.0, 100.0, 2, "")]
    view.after_tick(campaign)
    assert view.shake == 0 and not view.blasts
    # Heavy non-vent hit (damage >= 6): micro-jolt.
    campaign.world.events = [Event("rival_hit", 100.0, 100.0, 6, "")]
    view.after_tick(campaign)
    assert view.shake >= 2 and abs(view.jolt()[0]) >= 1
    # Vent crit hit: full-duration gold blast ring + stronger jolt + longer flash.
    view.shake = 0
    campaign.world.events = [Event("rival_hit", 100.0, 100.0, 4, "vent")]
    view.after_tick(campaign)
    assert view.shake >= 3 and view.flashes[-1] == 4
    assert any(life == BLAST_TICKS - 1 and p == "spark" for _, _, _, life, p in view.blasts)
    # Shield deflection spawns a deflect ring and decays to empty over DEFLECT_TICKS.
    campaign.world.events = [Event("rival_shielded", 100.0, 100.0)]
    view.after_tick(campaign)
    assert len(view.deflects) == 1
    view.draw(display, campaign, (128, 72))
    campaign.world.events = []
    for _ in range(DEFLECT_TICKS):
        view.after_tick(campaign)
    assert not view.deflects
    # Player hit produces a real 2 px jolt on the very next draw and lights the danger vignette.
    view.shake = 0
    campaign.world.events = [Event("player_hit", 100.0, 100.0)]
    view.after_tick(campaign)
    assert abs(view.jolt()[0]) == 2 and view.hit_vignette == 9
    campaign.world.events = []
    display.fill(rgb("px.void"))
    view._draw_vignette(display, campaign.world.player, "playing", "encounter")
    assert display.get_at((0, 0))[:3] != rgb("px.void"), "hit vignette drew red edge"
    # Single-cell low battery draws the breathing edge vignette only while playing, not at 2
    # cells (even on Nightmare max_charge == 4), not when down and not during ending.
    view.hit_vignette = 0
    campaign.world.player.charge = 1
    display.fill(rgb("px.void"))
    view._draw_vignette(display, campaign.world.player, "playing", "encounter")
    assert display.get_at((0, 0))[:3] != rgb("px.void")
    for outcome, stage in (("down", "encounter"), ("playing", "ending")):
        display.fill(rgb("px.void"))
        view._draw_vignette(display, campaign.world.player, outcome, stage)
        assert display.get_at((0, 0))[:3] == rgb("px.void")
    nightmare = Campaign(1, PRESETS["nightmare"])
    nightmare.world.player.charge = 2
    display.fill(rgb("px.void"))
    view._draw_vignette(display, nightmare.world.player, "playing", "encounter")
    assert display.get_at((0, 0))[:3] == rgb("px.void")


def test_sector_arrival_banners_and_fuse_box_charging_bay(display) -> None:
    from overload.art.palette import rgb
    from overload.art.pixel import hud
    from overload.game.view import SECTOR_BANNER_TICKS, PixelView

    campaign = Campaign(1)
    view = PixelView(campaign)
    assert view.sector_banner is None
    enter(campaign, "s2_entry")
    view.after_tick(campaign)
    assert view.sector_banner is not None
    assert view.sector_banner[:2] == ("SECTOR 2", "COOLING PLANT")
    # Notice toast shifts below the sector banner while it is visible (no overlap).
    view.toast("A HIDDEN ROOM", 40)
    drawn: list[tuple[str, pygame.Rect]] = []
    original = hud.text

    def record(target, message, pos, *args, **kwargs):
        rect = original(target, message, pos, *args, **kwargs)
        drawn.append((message, rect))
        return rect

    hud.text = record
    try:
        view.draw(display, campaign, (128, 72))
    finally:
        hud.text = original
    notice_rect = next(rect for msg, rect in drawn if msg == "A HIDDEN ROOM")
    assert notice_rect.top >= 48, f"notice overlapped sector banner: {notice_rect}"
    # Decays to None over SECTOR_BANNER_TICKS and does not re-announce on revisit.
    for _ in range(SECTOR_BANNER_TICKS):
        view.after_tick(campaign)
    assert view.sector_banner is None
    view.after_tick(campaign)
    assert view.sector_banner is None
    # Sector 3 announces once, clears on down, and stays suppressed on retry.
    enter(campaign, "s3_entry")
    view.after_tick(campaign)
    assert view.sector_banner is not None
    assert view.sector_banner[:2] == ("SECTOR 3", "GRID CORE")
    campaign.world.outcome = "down"
    view.after_tick(campaign)
    assert view.sector_banner is None
    campaign.world.outcome = "playing"
    view.after_tick(campaign)
    assert view.sector_banner is None

    # Both Fuse Box rooms render the glowing recessed charging bay without rarity tokens.
    for room_id in ("fuse_1", "fuse_2"):
        room = campaign.arena.floor.get(room_id)
        cx = (room.rect[0] + 7) * 16 + 8
        cy = (room.rect[1] + 4) * 16 + 14
        light_colors = {
            view.room.light.get_at((x, y))[:3]
            for x in range(cx - 14, cx + 15)
            for y in range(cy - 6, cy + 7)
        }
        assert rgb("power.spark") in light_colors and rgb("power.blink") in light_colors
        assert rgb("px.rarity.epic") not in light_colors


def test_move_hint_fits_with_arrow_and_three_char_keys(display) -> None:
    from overload.art.pixel import hud
    from overload.game.view import HINT_RIGHT, PixelView

    # Arrow-bound move keys display compact ARROWS label inside the panel.
    arrow_binds = Keybinds()
    for action in ("up", "down", "left", "right"):
        assert arrow_binds.bind(action, action)
    campaign = Campaign(1)
    view = PixelView(campaign)
    view.binds = view.coach.binds = arrow_binds
    assert view.coach.hint(campaign) == "ARROWS TO MOVE  MOUSE TO AIM"

    # Worst-case four 3-char keys fall back to the short move hint and stay inside HINT_RIGHT.
    long_binds = Keybinds()
    for action, key in (
        ("up", "left shift"),
        ("down", "right shift"),
        ("left", "left ctrl"),
        ("right", "right ctrl"),
    ):
        assert long_binds.bind(action, key)
    view.binds = view.coach.binds = long_binds
    drawn: list[tuple[str, pygame.Rect]] = []
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
    assert message == "LSH/LCT/RSH/RCT MOVE  MOUSE AIM"
    assert rect.left >= 4 and rect.right <= HINT_RIGHT - 2


def test_short_circuit_and_ending_stamp_stay_clear_of_slots_and_edges(display) -> None:
    from overload.art.pixel import hud
    from overload.game.view import HINT_RIGHT, PixelView

    campaign = Campaign(1)
    view = PixelView(campaign)
    for prefix in ("", "DEV "):
        view.stamp = f"{prefix}overload 0.1.0 624e3a96 cff616dc"
        for render in (
            lambda: view._banner(display, "down"),
            lambda: view.draw_ending(display, 120.0, 0, 50, {}, {}, can_return=True),
        ):
            drawn: list[tuple[str, pygame.Rect]] = []
            original = hud.text

            def record(target, message, pos, *args, out=drawn, fn=original, **kwargs):
                rect = fn(target, message, pos, *args, **kwargs)
                out.append((message, rect))
                return rect

            hud.text = record
            try:
                render()
            finally:
                hud.text = original
            stamp_rect = next(rect for msg, rect in drawn if msg == view.stamp)
            assert stamp_rect.left >= 0 and stamp_rect.right <= HINT_RIGHT, (
                f"{view.stamp!r} crossed power slots or edge: {stamp_rect}"
            )


def test_mutual_kill_suppresses_room_clear_and_boss_reward_visuals(display) -> None:
    from overload.game.view import PixelView
    from overload.sim.state import Event

    campaign = Campaign(1)
    world = campaign.world
    world.unlocked.extend(["spark", "blink"])
    view = PixelView(campaign)
    world.outcome = "down"
    world.events = [
        Event("rival_destroyed", 100.0, 100.0),
        Event("boss_reward", 100.0, 100.0),
        Event("room_clear", 100.0, 100.0),
        Event("player_down", 80.0, 80.0),
    ]
    view.after_tick(campaign)
    assert view.boss_banner is None
    assert view.reward == []
    assert view.flyers == []
    assert view.notice is None
