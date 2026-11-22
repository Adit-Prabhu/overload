"""The menu (docs/POWERS_AND_FUSION.md section 7): the Tab hub, LOADOUT, FUSE with its
cards, terms, spin and reveal, CONTROLS, and how the game loop drives it."""

from __future__ import annotations

import pytest
from floorbot import FloorBot, clear_encounter, fuse_box_with
from test_flow import press_keys
from test_pixel_art import headless_pygame  # noqa: F401  (a fixture)

from overload.agent.selector import NeutralSelector
from overload.game.flow import MIN_FUSE_TICKS, Session
from overload.game.menu import (
    HUB_FUSE_BOX,
    HUB_PAUSED,
    Menu,
    loadout_rows,
    roll_terms,
    spin_delays,
    spin_steps,
)
from overload.sim.campaign import Campaign
from overload.sim.inputs import IDLE, InputFrame
from overload.sim.powers import (
    ABILITIES,
    BASE_POWERS,
    INGREDIENTS,
    RARITIES,
    RESULTS,
    owned_result,
    rarity_of,
)

ROLL = len(BASE_POWERS)  # the ROLL button's place in the cursor row


def bench(*stolen: str, bank=None) -> tuple[Session, Menu]:
    """A session in the first Fuse Box, the menu open on FUSE."""
    session = fuse_box_with(*stolen)
    session.campaign.world.bank = dict(bank or {})
    menu = Menu()
    menu.show(in_fuse_box=True)
    menu.hub = HUB_FUSE_BOX.index("FUSE")
    menu.press(session, "select")
    return session, menu


def socket(session: Session, menu: Menu, *powers: str) -> None:
    for power in powers:
        menu.cursor = BASE_POWERS.index(power)
        menu.press(session, "select")


def roll_through(session: Session, menu: Menu) -> list[str]:
    """Roll and let the spin run to the reveal. Returns every sound along the way."""
    action, sounds = menu.press(session, "roll")
    assert action == ["fuse", *menu.sockets]
    sounds = list(sounds)
    for _ in range(400):
        sounds += menu.update(16)
        if menu.roll.phase == "reveal":
            break
    return sounds


# The hub -------------------------------------------------------------------------------------


def test_the_hub_offers_resume_mid_sector_and_in_a_fuse_box() -> None:
    session = fuse_box_with("spark")
    menu = Menu()
    menu.show(in_fuse_box=True)
    assert menu.hub_items == HUB_FUSE_BOX and HUB_FUSE_BOX[0] == "RESUME"
    assert "CONTINUE" not in menu.hub_items
    assert menu.press(session, "select") == (None, ["resume"])
    assert menu.press(session, "back") == (None, ["resume"]), "Esc closes freely in a Fuse Box"
    menu.show(in_fuse_box=False)
    assert menu.hub_items == HUB_PAUSED and HUB_PAUSED[0] == "RESUME"
    assert menu.press(session, "back") == (None, ["resume"])
    menu.press(session, "up")
    assert menu.hub == 0, "no wrapping, so one press from the top never reaches QUIT"
    menu.hub = len(menu.hub_items) - 1
    assert menu.press(session, "select") == (None, ["deny"]) and menu.quitting
    menu.press(session, "up")
    menu.press(session, "down")
    assert not menu.quitting, "moving away cancels"
    menu.press(session, "select")
    assert menu.press(session, "select") == (None, ["quit"]), "QUIT asks twice"


@pytest.mark.parametrize("item", ["LOADOUT", "FUSE", "SETTINGS", "CONTROLS"])
def test_each_hub_item_opens_its_own_screen_and_back_returns(item) -> None:
    session = fuse_box_with("spark")
    menu = Menu()
    menu.show(in_fuse_box=False)
    menu.hub = HUB_PAUSED.index(item)
    menu.press(session, "select")
    assert menu.screen == item.lower()
    menu.press(session, "back")
    assert menu.screen == "hub"


# Loadout -------------------------------------------------------------------------------------


def test_the_loadout_lists_base_powers_first_and_equips_with_q_and_e() -> None:
    assert loadout_rows(["spark", "meteor", "blink"]) == ["spark", "blink", "meteor"]
    session = fuse_box_with("spark", "blink")
    session.campaign.world.unlocked.append("bolt_lance")
    menu = Menu()
    menu.show(in_fuse_box=True)
    menu.hub = HUB_FUSE_BOX.index("LOADOUT")
    menu.press(session, "select")
    menu.press(session, "up")  # wraps to the last row, the fused power
    assert menu.press(session, "q") == (["equip", 0, "bolt_lance"], ["confirm"])
    menu.press(session, "up")
    assert menu.press(session, "e") == (["equip", 1, "blink"], ["confirm"])
    assert session.campaign.world.player.slots == ["bolt_lance", "blink"]


def test_the_loadout_with_nothing_stolen_ignores_keys() -> None:
    session = fuse_box_with()
    menu = Menu()
    menu.show(in_fuse_box=True)
    menu.hub = HUB_FUSE_BOX.index("LOADOUT")
    menu.press(session, "select")
    for key in ("up", "down", "q", "e"):
        assert menu.press(session, key)[0] is None


# The bench -----------------------------------------------------------------------------------


def test_picking_two_powers_fills_the_sockets_and_moves_to_roll() -> None:
    session, menu = bench("spark", "blink", "burst")
    socket(session, menu, "spark")
    assert menu.sockets == ["spark"] and menu.cursor == BASE_POWERS.index("spark")
    socket(session, menu, "blink")
    assert menu.sockets == ["spark", "blink"] and menu.cursor == ROLL
    socket(session, menu, "burst")
    assert menu.sockets == ["spark", "burst"], "a third power replaces the second"
    socket(session, menu, "spark")
    assert menu.sockets == ["burst"], "select on a socketed power takes it out"


def test_a_power_not_stolen_cannot_be_socketed_and_roll_needs_two() -> None:
    session, menu = bench("spark")
    socket(session, menu, "blink")
    assert menu.sockets == [] and "NOT STOLEN" in menu.notice
    socket(session, menu, "spark")
    assert menu.press(session, "roll") == (None, ["deny"]) and menu.notice
    menu.cursor = ROLL
    assert menu.press(session, "select")[0] is None


def test_the_terms_show_the_odds_the_cost_and_the_guarantee() -> None:
    session, menu = bench("spark", "blink", bank={"spark": 1})
    terms = roll_terms(session, "spark", "blink")
    assert terms["results"] == RESULTS[frozenset(("spark", "blink"))]
    assert terms["odds"] == [60, 30, 10] and terms["cost"] == 0 and terms["can_roll"]
    session.campaign.world.unlocked.append("arc_trail")
    terms = roll_terms(session, "spark", "blink")
    assert terms["cost"] == 1 and not terms["can_roll"] and "BLINK" in terms["blocked"]
    session.campaign.world.streak = 2
    terms = roll_terms(session, "spark", "blink")
    assert terms["guaranteed"] and terms["odds"] == [0, 75, 25]
    assert roll_terms(session, "spark", "burst")["blocked"] == "STEAL BOTH POWERS FIRST"


@pytest.mark.parametrize("result", [0, 1, 2])
def test_the_spin_always_stops_on_the_result(result) -> None:
    steps = spin_steps(result)
    assert steps[-1] == result and len(steps) >= 10
    assert steps == [i % 3 for i in range(len(steps))], "it walks the cards in order"
    delays = spin_delays(len(steps))
    assert delays == sorted(delays) and 900 <= sum(delays) <= 1600, "slows, 1.1 to 1.5 s"


def test_a_roll_records_the_fusion_spins_and_reveals_what_the_sim_decided() -> None:
    session, menu = bench("spark", "blink")
    socket(session, menu, "spark", "blink")
    sounds = roll_through(session, menu)
    world = session.campaign.world
    power = owned_result(world.unlocked, "spark", "blink")
    assert menu.roll.result == power and menu.roll.highlight == RARITIES.index(rarity_of(power))
    assert sounds.count("roll_tick") >= 9 and sounds[-1] == f"fuse_{rarity_of(power)}"
    assert power in menu.discovered, "a revealed power is no longer a silhouette"
    assert menu.press(session, "e") == (["equip", 1, power], ["confirm"])
    assert world.player.slots[1] == power and menu.roll is None


def test_select_skips_the_spin_and_does_nothing_else() -> None:
    session, menu = bench("spark", "blink", bank={"spark": 3, "blink": 3})
    socket(session, menu, "spark", "blink")
    menu.press(session, "roll")
    action, sounds = menu.press(session, "select")
    assert action is None and menu.roll.phase == "reveal" and sounds[0].startswith("fuse_")
    assert session.campaign.world.fusions == 1, "the skip press never rolls again"


@pytest.mark.parametrize("rarity", ["epic", "legendary"])
def test_rolling_over_an_epic_or_legendary_asks_twice(rarity) -> None:
    session, menu = bench("spark", "blink", bank={"spark": 2, "blink": 2})
    owned = RESULTS[frozenset(("spark", "blink"))][RARITIES.index(rarity)]
    session.campaign.world.unlocked.append(owned)
    socket(session, menu, "spark", "blink")
    assert menu.press(session, "roll") == (None, ["deny"]) and "REPLACES" in menu.notice
    assert menu.cursor == ROLL, "on ROLL, so Space confirms as well as F"
    assert session.campaign.world.fusions == 0
    menu.press(session, "left")  # moving away cancels
    assert menu.press(session, "roll")[0] is None
    assert menu.press(session, "roll")[0] == ["fuse", "spark", "blink"]
    assert session.campaign.world.bank == {"spark": 1, "blink": 1}


def test_help_opens_and_closes_without_touching_the_bench() -> None:
    session, menu = bench("spark", "blink")
    socket(session, menu, "spark", "blink")
    menu.press(session, "help")
    assert menu.help
    assert menu.press(session, "roll") == (None, []), "the help page swallows keys"
    menu.press(session, "back")
    assert not menu.help and menu.sockets == ["spark", "blink"]


# The game loop -------------------------------------------------------------------------------


def live_setup():
    from overload.game.app import InputReader
    from overload.session.replay import Recording
    from overload.sim.arena import FLOOR_ARENA, arena_id
    from overload.sim.tuning import DEFAULT

    session = Session(Campaign(1), NeutralSelector())
    recording = Recording(
        seed=1,
        tuning_id=DEFAULT.tuning_id(),
        arena_id=arena_id(FLOOR_ARENA),
        mode="campaign",
        protocols=["lateral"],
    )
    return session, Menu(), InputReader(), recording


def test_fuse_box_auto_confirms_when_ready_and_waits_while_menu_is_open() -> None:
    import pygame
    from test_flow import Service, live_session

    from overload.game.app import complete_fuse_box, menu_frame, open_menu
    from overload.game.flow import FALLBACK_LINE

    session, menu, reader, recording = live_setup()
    session.campaign.world.unlocked.extend(["spark", "blink"])
    clear_encounter(session)
    assert session.campaign.stage == "fuse_box" and not menu.open
    assert complete_fuse_box(session, menu, recording) == (None, None)

    # Opening and closing the menu during recharge never traps the player or denies Esc.
    open_menu(menu, reader, in_fuse_box=True)
    press_keys(reader, pygame.K_q, pygame.K_ESCAPE)
    cues = menu_frame(session, menu, reader, recording, 16)
    assert "deny" not in cues and "confirm" in cues
    assert not menu.open and not reader._power_q
    assert session.campaign.stage == "fuse_box"

    # Reopen the menu and let the 5.0 s hold complete: auto-confirm waits until menu closes.
    open_menu(menu, reader, in_fuse_box=True)
    for _ in range(MIN_FUSE_TICKS):
        session.tick(IDLE)
    assert session.ready()
    assert complete_fuse_box(session, menu, recording) == (None, None)
    assert session.campaign.stage == "fuse_box"

    # Fuse and equip inside the menu after the hold finished: preserved in sector 2 checkpoint.
    session.fuse("spark", "blink")
    fused = owned_result(session.campaign.world.unlocked, "spark", "blink")
    session.equip(0, fused)
    press_keys(reader, pygame.K_q, pygame.K_RETURN)  # RESUME closes menu
    menu_frame(session, menu, reader, recording, 16)
    assert not menu.open and not reader._power_q
    decision, fallback = complete_fuse_box(session, menu, recording)
    assert decision is not None and fallback is None
    assert session.campaign.stage == "encounter" and session.campaign.encounter == 2
    assert session.campaign.checkpoint.player.slots[0] == fused

    # Live fallback captures and returns the approved D7 line on auto-confirm.
    live = live_session(Service())
    clear_encounter(live)
    live.selector.pending[2].future.result(timeout=5)
    for _ in range(MIN_FUSE_TICKS):
        live.tick(IDLE)
    live_menu = Menu()
    decision, fallback = complete_fuse_box(live, live_menu, recording)
    assert decision is not None and decision.tactic == "lateral"
    assert fallback == FALLBACK_LINE


def test_keys_while_the_menu_is_closed_are_dropped() -> None:
    import pygame

    from overload.game.app import menu_frame

    session, menu, reader, recording = live_setup()
    session.campaign.world.unlocked = ["spark", "blink"]
    press_keys(reader, pygame.K_f, pygame.K_q, pygame.K_SPACE)
    assert menu_frame(session, menu, reader, recording, 16) == []
    menu.show(in_fuse_box=False)
    assert menu_frame(session, menu, reader, recording, 16) == []
    assert not recording.menu, "nothing queued from before the menu opened"


def test_esc_goes_back_in_a_menu_and_quit_ends_the_game() -> None:
    import pygame

    from overload.game.app import menu_frame

    session, menu, reader, recording = live_setup()
    menu.show(in_fuse_box=False)
    menu.hub = HUB_PAUSED.index("FUSE")
    press_keys(reader, pygame.K_SPACE, pygame.K_ESCAPE)
    menu_frame(session, menu, reader, recording, 16)
    assert menu.open and menu.screen == "hub" and reader.take_escape()
    menu.hub = HUB_PAUSED.index("QUIT")
    press_keys(reader, pygame.K_RETURN, pygame.K_RETURN)
    menu_frame(session, menu, reader, recording, 16)
    assert reader.quit


def test_opening_the_menu_drops_keys_pressed_before_it_opened() -> None:
    """Review of PR #33: a W then Space as a sector ends must not pick a hub item."""
    import pygame

    from overload.game.app import menu_frame, open_menu

    session, menu, reader, recording = live_setup()
    clear_encounter(session)
    press_keys(reader, pygame.K_s, pygame.K_SPACE)  # pressed while the sector was ending
    open_menu(menu, reader, in_fuse_box=True)
    assert menu_frame(session, menu, reader, recording, 16) == []
    assert menu.screen == "hub" and menu.hub == 0


def test_a_key_during_the_spin_never_reveals_the_result_early() -> None:
    session, menu = bench("spark", "blink")
    socket(session, menu, "spark", "blink")
    menu.press(session, "roll")
    result = menu.roll.result
    for key in ("left", "up", "help", "q", "roll", "back"):
        menu.press(session, key)
    assert result not in menu.discovered and menu.roll.phase == "spin"


def test_odds_always_add_up_to_a_hundred() -> None:
    from overload.game.menu import percentages

    for weights in ((60, 30, 10), (0, 30, 10), (1, 1, 1), (7, 5, 3), (1, 0, 2)):
        assert sum(percentages(weights)) == 100
    assert percentages((60, 30, 10)) == [60, 30, 10]
    assert percentages((0, 30, 10)) == [0, 75, 25]


def test_tab_opens_and_closes_the_hub_mid_sector_and_in_a_fuse_box() -> None:
    from overload.game.app import can_open_menu, ticks_due, toggle_menu

    assert ticks_due(True, False, 0.05, 0.5) == (0, 0.0)
    assert ticks_due(False, True, 0.0, 0.0)[0] == 1
    menu = Menu()
    fresh = Campaign(1)
    assert can_open_menu(fresh)
    toggle_menu(menu, fresh)
    assert menu.open and not menu.in_fuse_box
    toggle_menu(menu, fresh)
    assert not menu.open
    fresh.world.player.charge = 0
    fresh.step(IDLE)
    assert not can_open_menu(fresh)
    toggle_menu(menu, fresh)
    assert not menu.open, "not while down"
    boxed = fuse_box_with("spark")
    assert can_open_menu(boxed.campaign)
    toggle_menu(menu, boxed.campaign)
    assert menu.open and menu.in_fuse_box, "Tab opens the Fuse Box menu freely"
    toggle_menu(menu, boxed.campaign)
    assert not menu.open, "Tab closes the Fuse Box menu freely"
    boxed.campaign.stage = "ending"
    assert not can_open_menu(boxed.campaign)


def test_a_session_with_menu_rolls_replays_exactly() -> None:
    import pygame

    from overload.game.app import complete_fuse_box, menu_frame
    from overload.session.replay import play

    session, menu, reader, recording = live_setup()
    campaign = session.campaign
    bot = FloorBot(campaign)

    def play_to_fuse_box(sector: int) -> None:
        for tick in range(40_000):  # real inputs, as a player would
            frame = bot.frame(tick)
            if campaign.world.outcome == "down":
                frame = InputFrame(restart=True)
            session.tick(frame)
            recording.frames.append(frame)
            if campaign.stage == "fuse_box" and campaign.encounter == sector:
                break
        assert campaign.stage == "fuse_box"
        for _ in range(MIN_FUSE_TICKS):
            session.tick(IDLE)
            recording.frames.append(IDLE)

    # Sector 1 Fuse Box: auto-confirm directly without opening the menu.
    play_to_fuse_box(1)
    decision, _ = complete_fuse_box(session, menu, recording)
    assert decision is not None and campaign.encounter == 2

    # Sector 2 Fuse Box: open the menu optionally, fuse + equip, close, then auto-confirm.
    play_to_fuse_box(2)  # sector 2 steals Blink and Burst
    assert {"spark", "blink"} <= set(campaign.world.unlocked)
    menu.show(in_fuse_box=True)
    keys = (pygame.K_s, pygame.K_s, pygame.K_SPACE)  # FUSE
    keys += (pygame.K_SPACE, pygame.K_d, pygame.K_SPACE, pygame.K_f, pygame.K_SPACE)
    press_keys(reader, *keys)  # spark + blink, roll, skip the spin
    menu_frame(session, menu, reader, recording, 16)
    press_keys(reader, pygame.K_e, pygame.K_ESCAPE, pygame.K_ESCAPE, pygame.K_ESCAPE)
    menu_frame(session, menu, reader, recording, 16)  # equip to E, back to hub, close menu
    assert not menu.open
    decision, _ = complete_fuse_box(session, menu, recording)
    assert decision is not None
    assert [entry[1] for entry in recording.menu] == ["fuse", "equip"]
    assert campaign.encounter == 3 and len(recording.starts) == 2
    for _ in range(30):
        frame = InputFrame(fire=True, aim_x=300, aim_y=150, power_e=True)
        session.tick(frame)
        recording.frames.append(frame)
    assert play(recording).state_hash() == campaign.state_hash()


# Drawing -------------------------------------------------------------------------------------


@pytest.mark.usefixtures("headless_pygame")
def test_every_screen_draws_with_rarity_frames_and_marks() -> None:
    import pygame

    from overload.art.palette import rgb
    from overload.game import menu_view

    session, menu = bench("spark", "blink", "burst", bank={"spark": 2})
    screen = pygame.Surface((256, 144))
    socket(session, menu, "spark", "burst")
    menu_view.draw_menu(screen, menu, session, session.campaign.tuning, True, None, 2)
    colors = {screen.get_at((x, y))[:3] for x in range(256) for y in range(144)}
    assert {rgb(f"px.rarity.{r}") for r in RARITIES} <= colors, "all three card frames"
    roll_through(session, menu)
    menu_view.draw_menu(screen, menu, session, session.campaign.tuning, True, None, 2)
    for screen_name in ("hub", "loadout", "controls"):
        menu.roll, menu.screen = None, screen_name
        menu_view.draw_menu(screen, menu, session, session.campaign.tuning, False, "x", 2)
    menu.screen, menu.help = "fuse", True
    menu_view.draw_menu(screen, menu, session, session.campaign.tuning, True, None, 2)


@pytest.mark.usefixtures("headless_pygame")
@pytest.mark.parametrize("ability", ABILITIES)
def test_each_power_can_be_equipped_and_drawn_in_both_slots(ability) -> None:
    import pygame

    from overload.art.pixel import hud
    from overload.game import dev, menu_view

    session = Session(Campaign(1), NeutralSelector())
    campaign = session.campaign
    campaign.world.unlocked = list(BASE_POWERS)
    if ability in INGREDIENTS:
        dev.grant(campaign.world, ability)
    menu = Menu()
    menu.show(in_fuse_box=False)
    menu.hub = HUB_PAUSED.index("LOADOUT")
    menu.press(session, "select")
    menu.row = loadout_rows(campaign.world.unlocked).index(ability)
    screen = pygame.Surface((256, 144))
    for slot, key in enumerate(("q", "e")):
        assert menu.press(session, key) == (["equip", slot, ability], ["confirm"])
        assert campaign.world.player.slots[slot] == ability
        for page in ("loadout", "hub"):
            menu.screen = page
            menu_view.draw_menu(screen, menu, session, campaign.tuning, True, None, 1)
        menu.screen = "loadout"
        hud.draw(
            screen, hud.Hud(charge=6, max_charge=6, sockets=tuple(campaign.world.player.slots))
        )
    if ability in INGREDIENTS:
        menu.screen = "fuse"
        menu.sockets = list(INGREDIENTS[ability])
        menu.discovered.update(RESULTS[frozenset(menu.sockets)])
        menu_view.draw_menu(screen, menu, session, campaign.tuning, True, None, 1)


@pytest.mark.usefixtures("headless_pygame")
def test_loadout_shows_evolution_status_and_inherited_evolutions() -> None:
    import pygame

    from overload.game import dev, menu_view
    from overload.game.view import EVOLVED_INFO

    session = Session(Campaign(1), NeutralSelector())
    world = session.campaign.world
    world.unlocked = list(BASE_POWERS)
    world.fragments = {"spark": 1, "blink": 0, "burst": 0, "bulwark": 0, "magnet": 0}
    dev.grant(world, "storm_aura")
    world.player.slots = ["storm_aura", "spark"]
    menu = Menu()
    menu.show(in_fuse_box=False)
    menu.hub = HUB_PAUSED.index("LOADOUT")
    menu.press(session, "select")
    screen = pygame.Surface((256, 144))

    def capture(row: int) -> list[tuple[str, pygame.Rect]]:
        menu.row = row
        drawn: list[tuple[str, pygame.Rect]] = []
        original = menu_view.hud.text

        def record(target, message, pos, *args, **kwargs):
            rect = original(target, message, pos, *args, **kwargs)
            drawn.append((message, rect))
            return rect

        menu_view.hud.text = record
        try:
            menu_view.draw_loadout(screen, menu, session, session.campaign.tuning)
        finally:
            menu_view.hud.text = original
        return drawn

    rows = loadout_rows(world.unlocked)
    unevolved_texts = [t for t, _ in capture(rows.index("spark"))]
    assert "EVOLVE 1/3" in unevolved_texts and "AT 3: CHAIN" in unevolved_texts
    assert "Q" in unevolved_texts and "E" in unevolved_texts

    fused_inactive = "".join(t for t, _ in capture(rows.index("storm_aura")))
    assert "USES CHAIN WIDE" in fused_inactive

    # Partial multi-inheritance (Spark evolved, Burst still unevolved) shows both.
    world.fragments["spark"] = 3
    fused_partial = "".join(t for t, _ in capture(rows.index("storm_aura")))
    assert "USES +CHAIN WIDE" in fused_partial

    # Every evolved base power displays its full EVOLVED_INFO without truncation or overflow.
    for power in BASE_POWERS:
        world.fragments[power] = 3
        drawn = capture(rows.index(power))
        joined = " ".join(t for t, _ in drawn)
        assert EVOLVED_INFO[power] in joined, f"{power} truncated: {joined}"
        for msg, rect in drawn:
            assert rect.right <= menu_view.PANEL.right - 2, f"{power} clipped right: {msg} {rect}"
            assert rect.bottom <= menu_view.PANEL.bottom, f"{power} clipped bottom: {msg} {rect}"
        if power == "spark":
            assert "TWO MORE CHARGES" not in joined

    fused_active = "".join(t for t, _ in capture(rows.index("storm_aura")))
    assert "ACTIVE +CHAIN +WIDE" in fused_active

    # Rebound 3-letter keys stay left of the divider in LOADOUT.
    menu.keys_page.binds.bind("power_q", "left shift")
    menu.keys_page.binds.bind("power_e", "right shift")
    rebound = capture(rows.index("spark"))
    assert any(t == "LSH" and r.right <= menu_view.PANEL.x + 116 for t, r in rebound)


@pytest.mark.usefixtures("headless_pygame")
def test_fuse_cards_owned_label_never_overlaps_two_line_names() -> None:
    import pygame

    from overload.game import menu_view
    from overload.sim.powers import FUSED

    screen = pygame.Surface((256, 144))
    original = menu_view.hud.text
    for power in FUSED:
        a, b = INGREDIENTS[power]
        session, menu = bench(a, b)
        session.campaign.world.unlocked.append(power)
        menu.sockets = [a, b]
        menu.discovered.update(RESULTS[frozenset((a, b))])
        drawn: list[tuple[str, pygame.Rect]] = []

        def record(target, message, pos, *args, out=drawn, fn=original, **kwargs):
            rect = fn(target, message, pos, *args, **kwargs)
            out.append((message, rect))
            return rect

        menu_view.hud.text = record
        try:
            menu_view.draw_fuse(screen, menu, session)
        finally:
            menu_view.hud.text = original
        owned = [rect for msg, rect in drawn if msg == "OWNED"]
        assert len(owned) == 1, power
        owned_rect = owned[0]
        card_bottom = menu_view.PANEL.y + 4 + 46 + menu_view.CARD_H
        assert owned_rect.bottom <= card_bottom - 1, f"{power}: OWNED hits card border"
        # Shrink font cell padding (Silkscreen has 2 px transparent top/bottom padding).
        owned_box = owned_rect.inflate(0, -3)
        for msg, rect in drawn:
            if msg == "OWNED" or rect.centerx != owned_rect.centerx:
                continue
            assert not owned_box.colliderect(rect.inflate(0, -3)), f"{power}: {msg} hit OWNED"


@pytest.mark.usefixtures("headless_pygame")
def test_fuse_reveal_fits_all_thirty_fused_powers_without_overlap() -> None:
    import pygame

    from overload.game import menu_view
    from overload.game.menu import Roll
    from overload.game.view import DESCRIPTIONS
    from overload.sim.powers import FUSED, NAMES

    screen = pygame.Surface((256, 144))
    session, menu = bench(*BASE_POWERS)
    box = pygame.Rect(0, 0, 198, 98)
    box.center = (menu_view.PANEL.centerx, menu_view.PANEL.centery - 2)
    icon_bottom = box.y + 4 + menu_view._icon("storm_aura", 3).get_height()
    original = menu_view.hud.text
    for power in FUSED:
        menu.roll = Roll(
            pair=INGREDIENTS[power],
            result=power,
            replaced="reflector_wave" if power != "reflector_wave" else "capacitor_armor",
            steps=[0],
            delays=[50],
            phase="reveal",
        )
        drawn: list[tuple[str, pygame.Rect]] = []

        def record(target, message, pos, *args, out=drawn, fn=original, **kwargs):
            rect = fn(target, message, pos, *args, **kwargs)
            out.append((message, rect))
            return rect

        menu_view.hud.text = record
        try:
            menu_view._reveal(screen, menu)
        finally:
            menu_view.hud.text = original
        joined = " ".join(msg for msg, _ in drawn)
        assert DESCRIPTIONS[power] in joined, f"{power} truncated in reveal: {joined}"
        name_rect = next(rect for msg, rect in drawn if msg == NAMES[power])
        assert name_rect.top >= icon_bottom, f"{power} name overlaps 3x icon"
        for msg, rect in drawn:
            assert box.left <= rect.left and rect.right <= box.right, f"{power}: {msg} {rect}"
            assert box.top <= rect.top and rect.bottom <= box.bottom, f"{power}: {msg} {rect}"


@pytest.mark.usefixtures("headless_pygame")
def test_fuse_terms_never_overlap_guaranteed_across_all_pairs() -> None:
    import pygame

    from overload.game import menu_view
    from overload.sim.powers import RECIPE_ORDER

    screen = pygame.Surface((256, 144))
    original = menu_view.hud.text
    for a, b in RECIPE_ORDER:
        for bank in ({a: 2, b: 2}, {a: 1, b: 0}):
            session, menu = bench(a, b, bank=bank)
            owned = RESULTS[frozenset((a, b))][0]
            session.campaign.world.unlocked.append(owned)
            session.campaign.world.streak = session.campaign.tuning.fuse_guarantee_after
            menu.sockets = [a, b]
            drawn: list[tuple[str, pygame.Rect]] = []

            def record(target, message, pos, *args, out=drawn, fn=original, **kwargs):
                rect = fn(target, message, pos, *args, **kwargs)
                out.append((message, rect))
                return rect

            menu_view.hud.text = record
            try:
                menu_view.draw_fuse(screen, menu, session)
            finally:
                menu_view.hud.text = original
            guar = next(rect for msg, rect in drawn if msg == "EPIC+ GUARANTEED")
            left_terms = [
                (msg, rect) for msg, rect in drawn if rect.y == guar.y and msg != "EPIC+ GUARANTEED"
            ]
            assert len(left_terms) == 1, (a, b, bank, left_terms)
            msg, rect = left_terms[0]
            assert rect.right <= guar.left - 4, f"{a}+{b} ({bank}): {msg!r} overlapped EPIC+"


@pytest.mark.usefixtures("headless_pygame")
def test_fuse_box_hub_status_pulses_and_respects_reduce_flash(monkeypatch) -> None:
    import pygame

    from overload.game import menu_view
    from overload.game.settings import Settings

    session = fuse_box_with("spark")
    menu = Menu()
    menu.show(in_fuse_box=True)
    screen = pygame.Surface((256, 144))
    original = menu_view.hud.text

    def capture_tokens(ticks: int, reduce_flash: bool, ready: bool = True) -> dict[str, str]:
        menu.settings_page.settings = Settings(reduce_flash=reduce_flash)
        monkeypatch.setattr(pygame.time, "get_ticks", lambda: ticks)
        seen: dict[str, str] = {}

        def record(target, message, pos, token, *args, **kwargs):
            seen[message] = token
            return original(target, message, pos, token, *args, **kwargs)

        menu_view.hud.text = record
        try:
            menu_view.draw_hub(screen, menu, session, ready, None, 2)
        finally:
            menu_view.hud.text = original
        return seen

    t0 = capture_tokens(0, reduce_flash=False, ready=True)
    t1 = capture_tokens(400, reduce_flash=False, ready=True)
    assert t0["SUIT CHARGED"] == "px.hazard.1" and t1["SUIT CHARGED"] == "ui.text"
    assert t0["RESUME TO ENTER SECTOR 2"] == "px.hazard.1"
    assert t1["RESUME TO ENTER SECTOR 2"] == "ui.text"
    assert t0["RESUME"] == "ui.text" and "CONTINUE" not in t0

    r0 = capture_tokens(0, reduce_flash=True, ready=True)
    r1 = capture_tokens(400, reduce_flash=True, ready=True)
    assert r0["SUIT CHARGED"] == r1["SUIT CHARGED"] == "px.hazard.1"
    assert r0["RESUME TO ENTER SECTOR 2"] == r1["RESUME TO ENTER SECTOR 2"] == "px.hazard.1"

    waiting = capture_tokens(0, reduce_flash=False, ready=False)
    assert waiting["RESUME"] == "ui.text", "RESUME stays active and pressable while recharging"
    assert waiting["RECHARGING SUIT..."] == "px.blink.light"
    menu.hub = menu.hub_items.index("QUIT")
    menu.quitting = True
    quitting = capture_tokens(0, reduce_flash=False, ready=True)
    assert quitting["QUIT? SPACE AGAIN"] == "px.lamp"


@pytest.mark.usefixtures("headless_pygame")
def test_menu_polish_loadout_help_reveal_controls_and_dev() -> None:
    import pygame

    from overload.art.palette import rgb
    from overload.game import dev as devmode
    from overload.game import menu_view
    from overload.game.menu import Roll
    from overload.game.settings import Settings

    screen = pygame.Surface((256, 144))
    session, menu = bench(*BASE_POWERS)
    world = session.campaign.world
    devmode.grant(world, "capacitor_armor")
    devmode.grant(world, "bolt_lance")
    devmode.grant(world, "storm_aura")
    devmode.grant(world, "meteor")
    world.player.slots = ["capacitor_armor", "bolt_lance"]
    menu.keys_page.binds.bind("power_q", "left shift")
    menu.keys_page.binds.bind("power_e", "right shift")
    menu.keys_page.binds.bind("up", "left ctrl")
    menu.keys_page.binds.bind("down", "right ctrl")
    menu.keys_page.binds.bind("left", "left alt")
    menu.keys_page.binds.bind("right", "right alt")

    original = menu_view.hud.text

    def capture(draw_fn) -> list[tuple[str, pygame.Rect, str]]:
        drawn: list[tuple[str, pygame.Rect, str]] = []

        def record(target, message, pos, token, *args, **kwargs):
            rect = original(target, message, pos, token, *args, **kwargs)
            drawn.append((message, rect, token))
            return rect

        menu_view.hud.text = record
        try:
            draw_fn()
        finally:
            menu_view.hud.text = original
        return drawn

    # LOADOUT: scrolled list clears ^ from row 0 and keeps full ARMOR with 3-char keys.
    menu.screen = "loadout"
    menu.row = len(loadout_rows(world.unlocked)) - 2
    drawn = capture(lambda: menu_view.draw_loadout(screen, menu, session, session.campaign.tuning))
    up_marker = next(rect for msg, rect, _ in drawn if msg == "^")
    first_row_y = menu_view.PANEL.y + 4 + 19
    assert up_marker.y + 5 <= first_row_y - 2, f"^ touches row 0: {up_marker}"
    assert any(msg == "ARMOR" for msg, _, _ in drawn), "ARMOR must not truncate to ARMO"

    # FUSE disabled ROLL contrast and help overlay covering legendary rays.
    menu.screen = "fuse"
    menu.sockets = ["spark", "blink"]
    menu.cursor = ROLL
    world.unlocked.append("arc_trail")
    world.bank = {}
    drawn = capture(lambda: menu_view.draw_fuse(screen, menu, session))
    assert any(msg == "ROLL" and token == "px.wall.4" for msg, _, token in drawn)
    menu.help = True
    screen.fill(rgb("px.void"))
    menu_view.draw_fuse(screen, menu, session)
    help_box = menu_view.PANEL.inflate(-2, -2)
    leaked = [
        (x, y)
        for x in range(menu_view.PANEL.left, menu_view.PANEL.right)
        for y in range(menu_view.PANEL.top, menu_view.PANEL.bottom)
        if not help_box.collidepoint(x, y)
        and screen.get_at((x, y))[:3] == rgb("px.rarity.legendary")
    ]
    assert not leaked, f"legendary rays peeked past FUSE help box: {leaked[:5]}"
    menu.help = False

    # Legendary reveal pulse: symmetric, clear of corner rays, steady under Reduce Flash.
    menu.roll = Roll(
        pair=("spark", "burst"),
        result="storm_aura",
        replaced="",
        steps=[2],
        delays=[50],
        clock=0,
        phase="reveal",
    )
    menu.settings_page.settings = Settings(reduce_flash=True)
    s0 = pygame.Surface((256, 144))
    s1 = pygame.Surface((256, 144))
    menu_view._reveal(s0, menu)
    menu.roll.clock = 200
    menu_view._reveal(s1, menu)
    assert pygame.image.tobytes(s0, "RGB") == pygame.image.tobytes(s1, "RGB")

    # In-game CONTROLS footer uses ui.dim idle and px.hazard.1 on capture or notice.
    menu.roll = None
    menu.screen = "controls"
    menu.keys_page.capturing, menu.keys_page.notice = False, ""
    idle = capture(lambda: menu_view.draw_controls(screen, menu))
    assert any("ESC BACK" in msg and token == "ui.dim" for msg, _, token in idle)
    menu.keys_page.capturing = True
    cap = capture(lambda: menu_view.draw_controls(screen, menu))
    assert any(msg == "ESC CANCELS" and token == "px.hazard.1" for msg, _, token in cap)
    menu.keys_page.capturing, menu.keys_page.notice = False, "SPACE RESERVED FOR MENUS"
    note = capture(lambda: menu_view.draw_controls(screen, menu))
    assert any(
        msg == "SPACE RESERVED FOR MENUS" and token == "px.hazard.1" for msg, _, token in note
    )

    # DEV page footer stays inside PANEL even with 3-char move keys.
    menu.dev = devmode.DevTools()
    menu.screen = "dev"
    dev_drawn = capture(lambda: menu_view.draw_dev(screen, menu))
    for msg, rect, _ in dev_drawn:
        assert rect.right <= menu_view.PANEL.right - 2, f"DEV clipped: {msg!r} {rect}"


def test_rebound_power_keys_equip_in_loadout_and_fuse_reveal() -> None:
    import pygame

    from overload.game.app import menu_frame

    session, menu, reader, recording = live_setup()
    session.campaign.world.unlocked = ["spark", "blink"]
    binds = reader.binds
    assert binds.bind("power_q", "1") and binds.bind("power_e", "2")
    reader.rebind()
    menu.keys_page.binds = binds
    menu.show(in_fuse_box=False)
    menu.hub = HUB_PAUSED.index("LOADOUT")
    press_keys(reader, pygame.K_RETURN, pygame.K_1, pygame.K_s, pygame.K_2)
    menu_frame(session, menu, reader, recording, 16)
    assert session.campaign.world.player.slots == ["spark", "blink"]

    # Equipping straight from a FUSE reveal uses the rebound key and names it in the notice.
    menu.screen = "fuse"
    socket(session, menu, "spark", "blink")
    roll_through(session, menu)
    rolled = menu.roll.result
    press_keys(reader, pygame.K_1)
    menu_frame(session, menu, reader, recording, 16)
    assert session.campaign.world.player.slots[0] == rolled
    assert menu.notice.endswith(" ON 1")
