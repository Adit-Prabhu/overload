"""The menu (docs/POWERS_AND_FUSION.md section 7): a hub with RESUME, LOADOUT, FUSE,
SETTINGS and CONTROLS, each a screen with one job. No pygame: menu_view.py draws it, app.py
feeds it keys and time.

Keys arrive as names: up, down, left, right, select (Space or Enter), back (Esc or
Backspace), q, e, help (H), roll (F). The menu key (Tab by default) is handled by the
caller (it opens or closes the menu, both mid-sector and in a Fuse Box). CONTROLS rebinds
keys (game/keybinds.py): while it waits for a key, the caller feeds the raw key to
`keys_page.capture` instead.

FUSE is the crafting bench:
1. Pick two base powers into the sockets. Left and right move along the powers and the
   ROLL button after them. Select on a power puts it in a socket or takes it out, and a
   third power replaces the second. With both sockets full the cursor jumps to ROLL.
2. Three cards show the pair's rare, epic and legendary powers, with odds. A power never
   seen this session shows as a silhouette and ???.
3. Select on ROLL (or F anywhere) rolls. The simulation decides the result at once
   (powers.fuse, recorded for the replay). The spin is presentation only: a highlight
   steps across the cards, slowing, and always stops on the result, then the result is
   revealed. Select skips the spin.
Rolling over an epic or legendary the Surge owns asks for a second select first.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from overload.game.dev import DevTools
from overload.game.flow import Session
from overload.game.keybinds import RebindPage
from overload.game.settings import SettingsPage
from overload.sim.powers import (
    BASE_POWERS,
    FUSED,
    RARITIES,
    RESULTS,
    owned_result,
    rarity_of,
)

HUB_FUSE_BOX = ("RESUME", "LOADOUT", "FUSE", "SETTINGS", "CONTROLS", "QUIT")
HUB_PAUSED = ("RESUME", "LOADOUT", "FUSE", "SETTINGS", "CONTROLS", "QUIT")
LOADOUT_ROWS = 7  # rows visible at once in the loadout list
# The spin: at least this many steps, each a little longer than the last.
SPIN_MIN_STEPS = 10
SPIN_FIRST_MS = 35  # quickened Nov 19 (Adit: "can be a bit faster")
SPIN_GROWTH_MS = 16


def spin_steps(result: int, cards: int = 3) -> list[int]:
    """The card index highlighted at each step of the spin. It walks the cards in order and
    its last step is always `result`."""
    count = SPIN_MIN_STEPS
    while (count - 1) % cards != result:
        count += 1
    return [i % cards for i in range(count)]


def spin_delays(steps: int) -> list[int]:
    """How long each step of the spin lasts, in ms: fast, then slowing (1.1 to 1.5 s)."""
    return [SPIN_FIRST_MS + SPIN_GROWTH_MS * i for i in range(steps)]


@dataclass
class Roll:
    """A roll being shown. `phase` is "spin", then "reveal"."""

    pair: tuple[str, str]
    result: str
    replaced: str
    steps: list[int]
    delays: list[int]
    step: int = 0
    clock: int = 0  # ms into the current step (spin) or the reveal
    phase: str = "spin"

    @property
    def highlight(self) -> int:
        return self.steps[min(self.step, len(self.steps) - 1)]


@dataclass
class Menu:
    open: bool = False
    in_fuse_box: bool = False
    screen: str = "hub"  # hub, loadout, fuse, settings, controls, dev
    hub: int = 0
    row: int = 0  # loadout selection
    cursor: int = 0  # fuse: a base power's index, or len(BASE_POWERS) for the ROLL button
    sockets: list[str] = field(default_factory=list)
    help: bool = False
    armed: bool = False  # a reroll over an epic or legendary waiting for its second roll
    quitting: bool = False  # QUIT waiting for its second select
    roll: Roll | None = None
    notice: str = ""
    discovered: set[str] = field(default_factory=set)  # powers seen this session
    dev: DevTools | None = None  # dev mode only (game/dev.py): adds the DEV page
    dev_row: int = 0
    keys_page: RebindPage = field(default_factory=RebindPage)  # CONTROLS, the rebind editor
    settings_page: SettingsPage = field(default_factory=SettingsPage)  # SETTINGS page

    # Opening and closing ---------------------------------------------------------------

    def show(self, in_fuse_box: bool) -> None:
        self.open, self.in_fuse_box = True, in_fuse_box
        self.screen, self.hub, self.notice, self.quitting = "hub", 0, "", False
        self._reset_fuse()

    def close(self) -> None:
        self.open = False
        self._reset_fuse()

    def _reset_fuse(self) -> None:
        self.sockets, self.help, self.armed, self.roll = [], False, False, None

    @property
    def hub_items(self) -> tuple[str, ...]:
        items = HUB_FUSE_BOX if self.in_fuse_box else HUB_PAUSED
        if self.dev is not None:
            items = (*items[:-1], "DEV", items[-1])  # QUIT stays last
        return items

    # Keys --------------------------------------------------------------------------------

    def press(self, session: Session, key: str) -> tuple[list | None, list[str]]:
        """Handle one key. Returns the simulation action to record (or None) and the
        interface sounds to play. RESUME and QUIT are reported as the sounds "resume" and
        "quit" for the caller to act on."""
        if not self.open:
            return None, []
        if self.roll is None:  # mid-spin, the result stays a silhouette until the reveal
            self.discovered.update(p for p in session.campaign.world.unlocked if p in FUSED)
        handler = {
            "hub": self._hub,
            "loadout": self._loadout,
            "fuse": self._fuse,
            "settings": self._settings,
            "controls": self._controls,
            "dev": self._dev,
        }[self.screen]
        return handler(session, key)

    def _hub(self, session: Session, key: str):
        items = self.hub_items
        if key in ("up", "down"):
            # No wrapping: one press from the top item can never land on QUIT.
            self.hub = max(0, min(len(items) - 1, self.hub + (1 if key == "down" else -1)))
            self.quitting = False
            return None, ["move"]
        if key == "back":
            return None, ["resume"]
        if key != "select":
            return None, []
        item = items[self.hub]
        if item == "QUIT":
            if not self.quitting:  # quitting ends the run: ask once more
                self.quitting = True
                return None, ["deny"]
            return None, ["quit"]
        if item == "RESUME":
            return None, ["resume"]
        self.screen = item.lower()
        self.row, self.cursor, self.notice = 0, 0, ""
        self.keys_page.row, self.keys_page.capturing, self.keys_page.notice = 0, False, ""
        self.settings_page.row, self.settings_page.notice = 0, ""
        self._reset_fuse()
        return None, ["confirm"]

    def _back(self) -> tuple[None, list[str]]:
        self.screen, self.notice = "hub", ""
        self._reset_fuse()
        return None, ["move"]

    def _settings(self, session: Session, key: str):
        sound, _display_changed = self.settings_page.nav(key)
        if sound == "back":
            return self._back()
        return None, [sound] if sound else []

    def _controls(self, session: Session, key: str):
        sound = self.keys_page.nav(key)
        if sound == "back":
            return self._back()
        return None, [sound] if sound else []

    @property
    def capturing(self) -> bool:
        """CONTROLS is waiting for the key to bind."""
        return self.open and self.screen == "controls" and self.keys_page.capturing

    def _dev(self, session: Session, key: str):
        if key == "back":
            return self._back()
        rows = len(self.dev.rows())
        if key in ("up", "down"):
            self.dev_row = (self.dev_row + (1 if key == "down" else -1)) % rows
            return None, ["move"]
        if key in ("left", "right", "select"):
            self.dev.press(session, self.dev_row, key)
            return None, ["confirm" if key == "select" else "move"]
        return None, []

    def _loadout(self, session: Session, key: str):
        rows = loadout_rows(session.campaign.world.unlocked)
        if key == "back":
            return self._back()
        if key in ("up", "down") and rows:
            self.row = (self.row + (1 if key == "down" else -1)) % len(rows)
            return None, ["move"]
        if key in ("q", "e") and rows:
            slot = 0 if key == "q" else 1
            ability = rows[min(self.row, len(rows) - 1)]
            session.equip(slot, ability)
            return ["equip", slot, ability], ["confirm"]
        return None, []

    # The bench ---------------------------------------------------------------------------

    def _fuse(self, session: Session, key: str):
        world = session.campaign.world
        if self.roll is not None:
            return self._rolling(session, key)
        if key == "help":
            self.help = not self.help
            return None, ["move"]
        if self.help:
            if key in ("back", "select"):
                self.help = False
                return None, ["move"]
            return None, []
        if key == "back":
            return self._back()
        if key in ("left", "right"):
            step = 1 if key == "right" else -1
            self.cursor = (self.cursor + step) % (len(BASE_POWERS) + 1)
            self.armed, self.notice = False, ""
            return None, ["move"]
        if key == "roll" or (key == "select" and self.cursor == len(BASE_POWERS)):
            if len(self.sockets) < 2:
                self.notice = "PICK TWO POWERS FIRST"
                return None, ["deny"]
            return self._roll(session)
        if key == "select":
            return self._socket(world)
        return None, []

    def _socket(self, world) -> tuple[None, list[str]]:
        """Select on a power: put it in the next empty socket (replacing the second when
        both are full), or take it out. Filling the second socket moves to ROLL."""
        power = BASE_POWERS[self.cursor]
        self.armed, self.notice = False, ""
        if power in self.sockets:
            self.sockets.remove(power)
            return None, ["move"]
        if power not in world.unlocked:
            self.notice = f"{power.upper()} NOT STOLEN YET"
            return None, ["deny"]
        self.sockets = self.sockets[:1] + [power]
        if len(self.sockets) == 2:
            self.cursor = len(BASE_POWERS)
        return None, ["confirm"]

    def _roll(self, session: Session):
        world = session.campaign.world
        a, b = self.sockets
        owned = owned_result(world.unlocked, a, b)
        terms = roll_terms(session, a, b)
        if not terms["can_roll"]:
            self.notice = terms["blocked"]
            return None, ["deny"]
        if owned and rarity_of(owned) != "rare" and not self.armed:
            self.armed = True
            self.cursor = len(BASE_POWERS)  # on ROLL, so Space and F both confirm
            self.notice = f"REPLACES {owned_name(owned)}. ROLL AGAIN"
            return None, ["deny"]
        self.armed, self.notice = False, ""
        if self.dev is not None:
            self.dev.before_roll(session, a, b)
        result = session.fuse(a, b)
        if result != "fused":  # cannot happen after roll_terms said yes, but never animate
            self.notice = "CANNOT ROLL"
            return ["fuse", a, b], ["deny"]  # recorded anyway: every fuse call is
        power = owned_result(world.unlocked, a, b)
        steps = spin_steps(RARITIES.index(rarity_of(power)))
        self.roll = Roll((a, b), power, owned, steps, spin_delays(len(steps)))
        return ["fuse", a, b], ["roll_tick"]

    def _rolling(self, session: Session, key: str):
        roll = self.roll
        if roll.phase == "spin":
            if key == "select":  # skip to the reveal, and this press does nothing else
                self._reveal()
                return None, [self._sting()]
            return None, []
        if key in ("q", "e"):
            slot = 0 if key == "q" else 1
            session.equip(slot, roll.result)
            self.roll = None
            slot_key = self.keys_page.binds.short(("power_q", "power_e")[slot])
            self.notice = f"{owned_name(roll.result)} ON {slot_key}"
            return ["equip", slot, roll.result], ["confirm"]
        if key in ("select", "back"):
            self.roll = None
            return None, ["move"]
        return None, []

    def _reveal(self) -> None:
        roll = self.roll
        roll.phase, roll.step, roll.clock = "reveal", len(roll.steps) - 1, 0
        self.discovered.add(roll.result)

    def _sting(self) -> str:
        return f"fuse_{rarity_of(self.roll.result)}"

    # Time ----------------------------------------------------------------------------------

    def update(self, ms: int) -> list[str]:
        """Advance the spin by real time. Returns the sounds to play (a tick per step, the
        rarity's sting at the reveal)."""
        roll = self.roll
        if roll is None:
            return []
        roll.clock += ms
        if roll.phase == "reveal":
            return []
        sounds = []
        while roll.phase == "spin" and roll.clock >= roll.delays[roll.step]:
            roll.clock -= roll.delays[roll.step]
            if roll.step == len(roll.steps) - 1:
                self._reveal()
                sounds.append(self._sting())
            else:
                roll.step += 1
                sounds.append("roll_tick")
        return sounds


# What the screens show (shared with menu_view and tests) -----------------------------------


def loadout_rows(unlocked) -> list[str]:
    """Base powers first, then fused ones, each in the order they were gained."""
    return [p for p in unlocked if p not in FUSED] + [p for p in unlocked if p in FUSED]


def owned_name(power: str) -> str:
    from overload.sim.powers import NAMES

    return NAMES[power]


def percentages(weights) -> list[int]:
    """Whole percentages that always add up to 100 (largest remainder)."""
    total = sum(weights)
    exact = [100 * w / total for w in weights]
    whole = [int(x) for x in exact]
    order = sorted(range(len(exact)), key=lambda i: (whole[i] - exact[i], i))
    for i in order[: 100 - sum(whole)]:
        whole[i] += 1
    return whole


def roll_terms(session: Session, a: str, b: str) -> dict:
    """Everything the bench says about rolling this pair: the three results, the odds (the
    guarantee shown), the cost, the guarantee meter, and whether a roll can happen now."""
    campaign = session.campaign
    world, tuning = campaign.world, campaign.tuning
    results = RESULTS.get(frozenset((a, b)), ())
    owned = owned_result(world.unlocked, a, b)
    guaranteed = world.streak >= tuning.fuse_guarantee_after
    weights = list(tuning.fuse_odds)
    if guaranteed:
        weights[0] = 0
    odds = percentages(weights)
    cost = tuning.reroll_cost if owned else 0
    short = [p for p in (a, b) if world.bank.get(p, 0) < cost]
    blocked = ""
    if not results:
        blocked = "NOT IN THIS BUILD"  # a planned pair whose powers are not built yet
    elif a not in world.unlocked or b not in world.unlocked:
        blocked = "STEAL BOTH POWERS FIRST"
    elif short:
        blocked = f"NEED A SPARE {short[0].upper()} CHARGE"
    return {
        "results": results,
        "owned": owned,
        "odds": odds,
        "cost": cost,
        "guaranteed": guaranteed,
        "streak": min(world.streak, tuning.fuse_guarantee_after),
        "streak_max": tuning.fuse_guarantee_after,
        "can_roll": not blocked,
        "blocked": blocked,
    }
