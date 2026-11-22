"""First-run hints (pilot playtest, Nov 19: a new player did not know to move, shoot, dodge,
use Q and E, fuse, or walk into the Fuse Box). One hint at a time, in order of need, and each
goes for good once the player has done it. Cosmetic only: it reads the world and its events
after each tick and never writes to either. No pygame, so it is unit tested.

The hints name the player's bound keys (game/keybinds.py). They are identical in every rival
condition.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from overload.game.keybinds import Keybinds
from overload.sim import floorplay
from overload.sim.powers import BASE_POWERS

WALK = 48.0  # px walked before the move hint counts as learned


@dataclass
class Coach:
    binds: Keybinds = field(default_factory=Keybinds)
    learned: set[str] = field(default_factory=set)
    walked: float = 0.0
    last: tuple[float, float] | None = None
    fight: bool = False  # a room has locked, so robots are shooting
    target: tuple[float, float] | None = None  # where the Fuse Box hint points

    def update(self, run) -> None:
        """Read one tick: what the player did, and what is happening."""
        world = run.world
        player = world.player
        here = (player.x, player.y)
        if self.last is not None:
            step = abs(here[0] - self.last[0]) + abs(here[1] - self.last[1])
            if step < 8:  # a retry or a blink is not walking
                self.walked += step
        self.last = here
        if self.walked >= WALK:
            self.learned.add("move")
        for event in world.events:
            kind = event.kind
            if kind == "shot":
                self.learned.add("fire")
            elif kind == "dodge":
                self.learned.add("dodge")
            elif kind.startswith("power_"):
                self.learned.add("power")
            elif kind == "room_lock":
                self.fight = True
        if world.fusions > 0:
            self.learned.add("fuse")
        self.target = _fuse_box(run)

    def hint(self, run, short: bool = False) -> str | None:
        """The one hint to show now, or None. `short` writes keys as three letters at
        most (LSH, RCT), for a hint that would not fit beside the power slots."""
        world = run.world
        if world.outcome != "playing" or getattr(run, "stage", None) not in (None, "encounter"):
            return None
        keys = self.binds
        name = keys.short if short else keys.label
        if self.target is not None:
            return "FOLLOW THE ARROW TO THE FUSE BOX"
        if "move" not in self.learned:
            move = keys.move_label()
            if short:
                return f"{move} MOVE  MOUSE AIM"
            return f"{move} TO MOVE  MOUSE TO AIM"
        if "fire" not in self.learned:
            return "HOLD LEFT CLICK TO FIRE"
        if "dodge" not in self.learned and self.fight:
            return f"{name('dodge')} TO DODGE THROUGH SHOTS"
        if "power" not in self.learned and any(world.player.slots):
            q, e = name("power_q"), name("power_e")
            return f"{q} OR {e} USES A STOLEN POWER"
        stolen = [p for p in BASE_POWERS if p in world.unlocked]
        if "fuse" not in self.learned and len(stolen) >= 2:
            return f"{name('menu')} THEN FUSE: MIX TWO POWERS"
        return None


def _fuse_box(run) -> tuple[float, float] | None:
    """The Fuse Box's center once this sector's chamber is cleared and before the Surge
    has walked in, else None."""
    floor = run.arena.floor
    stage = getattr(run, "stage", None)
    if floor is None or stage != "encounter" or run.encounter >= 3:
        return None
    if f"s{run.encounter}_chamber" not in run.world.cleared:
        return None
    room = floor.get(f"fuse_{run.encounter}")
    return floorplay.tile_center(room.center)
