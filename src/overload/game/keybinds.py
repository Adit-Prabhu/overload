"""Rebindable keys (pilot playtest, Nov 19). Each action has one key, saved by name in a
git-ignored local file, so a change lasts across runs. The arrow keys always move as well,
unless one is bound to another action. Esc is never bindable: it backs out of every menu
and cancels a rebind. Aim and fire stay on the mouse.

Keys are stored as pygame key names ("w", "space", "left shift"). The bindings and the
rebind page are plain data, so the menu logic stays free of pygame and unit tested. Only
`code` and `key_name` call into pygame, after it is initialized.

Bindings only change which key makes an InputFrame. Recordings and replays store frames, so
a replay plays the same on any bindings.
"""

from __future__ import annotations

import json
import warnings
from dataclasses import dataclass, field
from pathlib import Path

from overload.paths import ROOT

ACTIONS = (
    ("up", "MOVE UP"),
    ("down", "MOVE DOWN"),
    ("left", "MOVE LEFT"),
    ("right", "MOVE RIGHT"),
    ("dodge", "DODGE"),
    ("power_q", "POWER 1"),
    ("power_e", "POWER 2"),
    ("retry", "RETRY"),
    ("menu", "MENU"),
)
DEFAULTS = {
    "up": "w",
    "down": "s",
    "left": "a",
    "right": "d",
    "dodge": "space",
    "power_q": "q",
    "power_e": "e",
    "retry": "r",
    "menu": "tab",
}
ARROWS = {"up": "up", "down": "down", "left": "left", "right": "right"}
# Esc, Enter and Backspace are reserved for menus so no binding can break navigation.
UNBINDABLE = {"escape", "return", "enter", "kp_enter", "backspace"}
# Space is menu select, so actions that must also fire inside menus cannot hold Space.
# Dodge (default Space) and Retry are gameplay-only and keep Space fully valid.
MENU_ACTIONS = {"up", "down", "left", "right", "power_q", "power_e", "menu"}
PATH = ROOT / "settings" / "keys.json"
# Short labels for long key names, for the 3 by 5 glyphs over the power slots.
_SHORT = {
    "space": "SPC",
    "left shift": "LSH",
    "right shift": "RSH",
    "left ctrl": "LCT",
    "right ctrl": "RCT",
    "left alt": "LAL",
    "right alt": "RAL",
    "return": "ENT",
    "enter": "ENT",
    "backspace": "BSP",
    "caps lock": "CAP",
}
_LABEL = {
    "return": "ENTER",
    "enter": "ENTER",
    "kp_enter": "ENTER",
    "left": "LEFT ARROW",
    "right": "RIGHT ARROW",
    "up": "UP ARROW",
    "down": "DOWN ARROW",
}


def allowed(action: str, name: str) -> bool:
    """True if `name` can legally be bound to `action` without conflicting with menus."""
    if action not in DEFAULTS or not name or name in UNBINDABLE:
        return False
    return not (name == "space" and action in MENU_ACTIONS)


def key_label(name: str) -> str:
    """How a key is written on screen: "W", "SPACE", "LEFT SHIFT"."""
    return _LABEL.get(name, name.upper())


def short_label(name: str) -> str:
    """At most three letters or digits, for the small glyphs."""
    if name in _SHORT:
        return _SHORT[name]
    letters = "".join(c for c in name.upper() if c.isalnum())
    return letters[:3] or "?"


@dataclass
class Keybinds:
    keys: dict[str, str] = field(default_factory=lambda: dict(DEFAULTS))
    path: Path | None = None  # None: never saved (tests, replays)

    @classmethod
    def load(cls, path: Path = PATH) -> Keybinds:
        """The saved bindings, or the defaults if there are none or they are damaged
        (an unknown action, a missing one, a key used twice or an unbindable key)."""
        binds = cls(path=path)
        try:
            saved = json.loads(path.read_text())
        except (OSError, ValueError):
            return binds
        if (
            isinstance(saved, dict)
            and set(saved) == set(DEFAULTS)
            and all(isinstance(v, str) and allowed(k, v) for k, v in saved.items())
            and len(set(saved.values())) == len(saved)
        ):
            binds.keys = dict(saved)
        return binds

    def save(self) -> None:
        if self.path is None:
            return
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            self.path.write_text(json.dumps(self.keys, indent=2, sort_keys=True) + "\n")
        except OSError:
            pass  # a read-only checkout still plays, with the bindings for this run only

    def bind(self, action: str, name: str) -> bool:
        """Put `name` on `action`. A key already on another action swaps over to it when
        both actions legally accept their new keys, so no key is ever used twice and no
        menu action ever receives a reserved menu key."""
        if not allowed(action, name):
            return False
        for other, key in self.keys.items():
            if key == name and other != action:
                if not allowed(other, self.keys[action]):
                    return False
                self.keys[other] = self.keys[action]
                break
        self.keys[action] = name
        self.save()
        return True

    def reset(self) -> None:
        self.keys = dict(DEFAULTS)
        self.save()

    def label(self, action: str) -> str:
        return key_label(self.keys[action])

    def short(self, action: str) -> str:
        return short_label(self.keys[action])

    def pair(self, a: str, b: str) -> str:
        """Two actions' keys for a footer, like W/S or Q/E."""
        return f"{self.short(a)}/{self.short(b)}"

    def move_label(self) -> str:
        """The four move keys as one word when they spell one, like WASD or ARROWS."""
        keys = [self.keys[a] for a in ("up", "left", "down", "right")]
        if keys == ["up", "left", "down", "right"]:
            return "ARROWS"
        if all(len(k) == 1 for k in keys):
            return "".join(keys).upper()
        return "/".join(short_label(k) for k in keys)

    def arrows(self) -> dict[str, str]:
        """The arrow keys that still move: those not bound to some action."""
        used = set(self.keys.values())
        return {action: key for action, key in ARROWS.items() if key not in used}


@dataclass
class RebindPage:
    """The CONTROLS page as an editor, shared by the title and the in-game menu. Rows are
    the actions, then RESET. Select on an action waits for the next key. Esc cancels the
    wait, or leaves the page."""

    binds: Keybinds = field(default_factory=Keybinds)
    row: int = 0
    capturing: bool = False
    notice: str = ""

    @property
    def rows(self) -> int:
        return len(ACTIONS) + 1

    def nav(self, key: str) -> str | None:
        """A menu key name (up, down, select, back). Returns "back" when the page closes,
        "move" or "confirm" for a sound, else None."""
        if key == "back":
            self.notice = ""
            return "back"
        if key in ("up", "down"):
            self.row = (self.row + (1 if key == "down" else -1)) % self.rows
            self.notice = ""
            return "move"
        if key == "select":
            if self.row == len(ACTIONS):
                self.binds.reset()
                self.notice = "DEFAULT KEYS RESTORED"
            else:
                self.capturing = True
                self.notice = ""
            return "confirm"
        return None

    def capture(self, name: str) -> str:
        """The key pressed while waiting. Esc cancels. Reserved menu keys are refused with
        a notice and a deny cue. Returns a sound."""
        self.capturing = False
        if not name or name == "escape":
            self.notice = ""
            return "move"
        action, title = ACTIONS[self.row]
        if not allowed(action, name):
            self.notice = f"{key_label(name)} RESERVED FOR MENUS"
            return "deny"
        for other, key in self.binds.keys.items():
            if key == name and other != action and not allowed(other, self.binds.keys[action]):
                other_title = dict(ACTIONS)[other]
                self.notice = f"REBIND {other_title} FIRST"
                return "deny"
        if not self.binds.bind(action, name):
            self.notice = ""
            return "move"
        self.notice = f"{title}: {key_label(name)}"
        return "confirm"


def code(name: str) -> int:
    """A key name as a pygame key code. Raises ValueError for an unknown name."""
    import pygame

    with warnings.catch_warnings():
        # The name tables are SDL's own and need no display: pygame warns before init
        # only because some of its key functions do.
        warnings.simplefilter("ignore")
        return pygame.key.key_code(name)


def known(name: str) -> bool:
    """True if pygame can turn this key name back into a key (a key with no name, or a
    name that does not round trip, is never bound)."""
    if not name:
        return False
    try:
        code(name)
    except ValueError:
        return False
    return True


def key_name(key: int) -> str:
    import pygame

    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        return pygame.key.name(key)
