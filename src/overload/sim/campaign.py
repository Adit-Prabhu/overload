"""The run the game plays: three sectors on the substation floor, each ending in a fight with
the Regulator, with the Fuse Box between them.

Each encounter's protocol comes from outside (the live selector, the fixed schedule or the
neutral default) through `begin_next`, the one door the rival model's choice can use to enter
the game. Encounter 1 always starts neutral. Each protocol is frozen at entry. Retrying after
going down restores the entry snapshot exactly, protocol included, so a retry never makes
another request or changes the fight.
"""

from __future__ import annotations

import copy
import hashlib
import json
import random
from dataclasses import asdict
from typing import Literal

from overload.floor import Door
from overload.sim import floorplay
from overload.sim.arena import FLOOR_ARENA, SUBSTATION, Arena
from overload.sim.inputs import InputFrame
from overload.sim.powers import Kit, equip, fuse
from overload.sim.state import Player, World, state_hash
from overload.sim.tuning import DEFAULT, Tuning
from overload.sim.world import PROTOCOLS, spawn_drone, spawn_relay, spawn_rival, step

ENCOUNTERS = 3
NEUTRAL = "lateral"
Stage = Literal["encounter", "fuse_box", "ending"]


# Which machines each encounter brings. Arc Drones carry Spark, Relays carry Blink, so the
# Surge can unlock both by encounter 2 and fuse Arc Trail before encounter 3.
ROSTER = {1: ("drone", "drone"), 2: ("drone", "relay"), 3: ("relay", "drone")}


def encounter_world(
    seed: int,
    encounter: int,
    protocol: str,
    tuning: Tuning = DEFAULT,
    arena: Arena = SUBSTATION,
    kit: Kit | None = None,
) -> World:
    """A fresh fight: full charge, the carried kit, the Regulator in its frozen protocol and
    the encounter's machines."""
    world_seed = seed * 10 + encounter
    sx, sy = arena.player_spawn
    world = World(
        seed=world_seed,
        rng=random.Random(world_seed),
        player=Player(x=sx, y=sy, charge=tuning.player_max_charge),
        encounter=encounter,
    )
    (kit or Kit()).apply(world)
    rx, ry = arena.rival_spawn
    spawn_rival(world, rx, ry, protocol, tuning)
    for kind, (x, y) in zip(ROSTER[encounter], arena.practice_spawns, strict=True):
        if kind == "relay":
            spawn_relay(world, x, y, tuning)
        else:
            spawn_drone(world, x, y, tuning)
    return world


def floor_world(seed: int, tuning: Tuning = DEFAULT, arena: Arena = FLOOR_ARENA) -> World:
    """The whole floor at the start: the Surge in sector 1's entry, every Fuse Box exit and
    the secret wall locked, encounter 1 on the neutral protocol."""
    sx, sy = arena.player_spawn
    world = World(
        seed=seed,
        rng=random.Random(seed),
        player=Player(x=sx, y=sy, charge=tuning.player_max_charge),
        encounter=1,
        mode="floor",
        protocol=NEUTRAL,
    )
    floor = arena.floor
    shut = [d.id for d in floor.doors if d.secret or _is_fuse_exit(d)]
    floorplay.lock(world, shut)
    return world


def _is_fuse_exit(door: Door) -> bool:
    """A door between a Fuse Box and the next sector's entry (either side)."""
    ends = {door.room, door.other}
    return any(e.startswith("fuse_") for e in ends) and any(e.endswith("_entry") for e in ends)


class Campaign:
    """Three sectors on one floor. Each ends in the Regulator's chamber. After the chamber
    the Surge walks into the Fuse Box (the safe room, where the rival's one request starts).
    `begin_next` freezes the next sector's protocol, opens the Fuse Box exit and takes the
    sector's checkpoint: going down restores it exactly, with no new request."""

    def __init__(self, seed: int, tuning: Tuning = DEFAULT, arena: Arena = FLOOR_ARENA) -> None:
        self.seed = seed
        self.tuning = tuning
        self.arena = arena
        self.encounter = 1
        self.stage: Stage = "encounter"
        self.protocols: dict[int, str] = {1: NEUTRAL}
        self.retries: dict[int, int] = {1: 0}
        self.kit = Kit()
        # The ending readout: playing time, shots and every power use, across retries.
        self.stats: dict = {"ticks": 0, "shots": 0, "powers": {}}
        self.world = floor_world(seed, tuning, arena)
        self.checkpoint = copy.deepcopy(self.world)

    def step(self, inp: InputFrame) -> None:
        """Advance one tick. The Surge can walk in the Fuse Box. Nothing moves after the
        ending."""
        if self.stage == "ending":
            self.world.events.clear()
            return
        if self.stage == "fuse_box":
            # The menu is open: the Surge stands still and only the aim follows the cursor.
            inp = InputFrame(aim_x=inp.aim_x, aim_y=inp.aim_y)
        if inp.restart and self.world.outcome == "down":
            self.world = copy.deepcopy(self.checkpoint)
            self.world.events.clear()
            self.retries[self.encounter] += 1
            return
        if self.world.outcome != "playing":
            self.world.events.clear()  # waiting on the retry: nothing happens
            return
        step(self.world, inp, self.tuning, self.arena)
        self._count(self.world.events)
        if self.world.outcome != "playing":
            return  # going down takes precedence over anything cleared in the same tick
        if self.stage == "encounter" and f"s{self.encounter}_chamber" in self.world.cleared:
            if self.encounter == ENCOUNTERS:
                self.stage = "ending"
                return
            player = self.world.player
            room = floorplay.room_of(self.arena.floor, player.x, player.y)
            if room is not None and room.id == f"fuse_{self.encounter}":
                self.world.player.charge = self.tuning.player_max_charge  # the safe room
                self.kit = Kit.from_world(self.world)
                self.stage = "fuse_box"

    def _count(self, events) -> None:
        self.stats["ticks"] += 1
        powers = self.stats["powers"]
        for event in events:
            if event.kind == "shot":
                self.stats["shots"] += 1
            elif event.kind.startswith("power_"):
                name = event.kind.removeprefix("power_")
                powers[name] = powers.get(name, 0) + 1

    def equip(self, slot: int, ability: str) -> bool:
        """Fuse Box: put an unlocked ability in slot 0 (Q) or 1 (E)."""
        self._require_fuse_box()
        ok = equip(self.kit, slot, ability)
        self.kit.apply(self.world)
        return ok

    def fuse(self, a: str, b: str) -> str:
        """Fuse Box: fuse two base powers. See powers.fuse for the result codes."""
        self._require_fuse_box()
        result = fuse(self.kit, a, b)
        self.kit.apply(self.world)
        return result

    def _require_fuse_box(self) -> None:
        if self.stage != "fuse_box":
            raise RuntimeError(f"the Fuse Box is not open (stage {self.stage})")

    def begin_next(self, protocol: str) -> None:
        """Leave the Fuse Box: the next sector's protocol is frozen from now on, the exit
        opens and this is the sector's checkpoint."""
        if self.stage != "fuse_box":
            raise RuntimeError(f"cannot begin an encounter from stage {self.stage}")
        if protocol not in PROTOCOLS:
            raise ValueError(f"unknown protocol {protocol!r}")
        self.encounter += 1
        self.protocols[self.encounter] = protocol
        self.retries[self.encounter] = 0
        world = self.world
        world.protocol = protocol
        world.encounter = self.encounter
        fuse_id = f"fuse_{self.encounter - 1}"
        floorplay.unlock(
            world,
            [
                d.id
                for d in self.arena.floor.doors
                if _is_fuse_exit(d) and fuse_id in (d.room, d.other)
            ],
        )
        world.events.clear()
        self.checkpoint = copy.deepcopy(world)
        self.stage = "encounter"

    def state_hash(self) -> str:
        blob = json.dumps(
            {
                "world": state_hash(self.world),
                "stage": self.stage,
                "encounter": self.encounter,
                "protocols": self.protocols,
                "retries": self.retries,
                "kit": asdict(self.kit),
                "stats": self.stats,
            },
            sort_keys=True,
            separators=(",", ":"),
        )
        return hashlib.sha256(blob.encode()).hexdigest()[:16]
