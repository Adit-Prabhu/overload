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


def test_the_hub_offers_continue_in_a_fuse_box_and_resume_mid_sector() -> None:
    session = fuse_box_with("spark")
    menu = Menu()
    menu.show(in_fuse_box=True)
    assert menu.hub_items == HUB_FUSE_BOX and HUB_FUSE_BOX[0] == "CONTINUE"
    assert menu.press(session, "select") == (None, ["continue"])
    assert menu.press(session, "back") == (None, ["deny"]), "a Fuse Box is left by CONTINUE"
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


@pytest.mark.parametrize("item", ["LOADOUT", "FUSE", "CONTROLS"])
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


def test_continue_waits_for_the_hold_then_starts_the_next_sector() -> None:
    import pygame

    from overload.game.app import menu_frame

    session, menu, reader, recording = live_setup()
    clear_encounter(session)
    menu.show(in_fuse_box=True)
    press_keys(reader, pygame.K_q, pygame.K_RETURN)
    assert "deny" in menu_frame(session, menu, reader, recording, 16), "still routing power"
    assert session.campaign.stage == "fuse_box"
    for _ in range(MIN_FUSE_TICKS):
        session.tick(IDLE)
    press_keys(reader, pygame.K_q, pygame.K_RETURN)
    menu_frame(session, menu, reader, recording, 16)
    assert session.campaign.stage == "encounter" and session.campaign.encounter == 2
    assert not menu.open and not reader._power_q, "Q from the menu never fires a power"


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


def test_tab_opens_the_hub_only_mid_sector_with_the_surge_up() -> None:
    from overload.game.app import ticks_due, toggle_menu

    assert ticks_due(True, False, 0.05, 0.5) == (0, 0.0)
    assert ticks_due(False, True, 0.0, 0.0)[0] == 1
    menu = Menu()
    fresh = Campaign(1)
    toggle_menu(menu, fresh)
    assert menu.open and not menu.in_fuse_box
    toggle_menu(menu, fresh)
    assert not menu.open
    fresh.world.player.charge = 0
    fresh.step(IDLE)
    toggle_menu(menu, fresh)
    assert not menu.open, "not while down"
    boxed = fuse_box_with("spark")
    menu.show(in_fuse_box=True)
    toggle_menu(menu, boxed.campaign)
    assert menu.open, "Tab never closes the Fuse Box menu"


def test_a_session_with_menu_rolls_replays_exactly() -> None:
    import pygame

    from overload.game.app import menu_frame
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
        menu.show(in_fuse_box=True)

    play_to_fuse_box(1)
    press_keys(reader, pygame.K_RETURN)  # CONTINUE
    menu_frame(session, menu, reader, recording, 16)
    play_to_fuse_box(2)  # sector 2 steals Blink and Burst
    assert {"spark", "blink"} <= set(campaign.world.unlocked)
    keys = (pygame.K_s, pygame.K_s, pygame.K_SPACE)  # FUSE
    keys += (pygame.K_SPACE, pygame.K_d, pygame.K_SPACE, pygame.K_f, pygame.K_SPACE)
    press_keys(reader, *keys)  # spark + blink, roll, skip the spin
    menu_frame(session, menu, reader, recording, 16)
    press_keys(reader, pygame.K_e, pygame.K_ESCAPE, pygame.K_ESCAPE, pygame.K_w, pygame.K_w)
    press_keys(reader, pygame.K_RETURN)  # equip to E, back to the hub, CONTINUE
    menu_frame(session, menu, reader, recording, 16)
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
