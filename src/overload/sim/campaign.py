"""The run the game plays: three encounters against the Regulator, with the Fuse Box between.

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

from overload.sim.arena import SUBSTATION, Arena
from overload.sim.inputs import InputFrame
from overload.sim.powers import Kit, equip, fuse
from overload.sim.state import Player, World, state_hash
from overload.sim.tuning import DEFAULT, Tuning
from overload.sim.world import PROTOCOLS, spawn_arc_mite, spawn_relay, spawn_rival, step

ENCOUNTERS = 3
NEUTRAL = "lateral"
Stage = Literal["encounter", "fuse_box", "ending"]


# Which machines each encounter brings. Arc Mites carry Spark, Relays carry Blink, so the
# Surge can unlock both by encounter 2 and fuse Arc Trail before encounter 3.
ROSTER = {1: ("arc_mite", "arc_mite"), 2: ("arc_mite", "relay"), 3: ("relay", "arc_mite")}


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
            spawn_arc_mite(world, x, y, tuning)
    return world


class Campaign:
    def __init__(self, seed: int, tuning: Tuning = DEFAULT, arena: Arena = SUBSTATION) -> None:
        self.seed = seed
        self.tuning = tuning
        self.arena = arena
        self.encounter = 1
        self.stage: Stage = "encounter"
        self.protocols: dict[int, str] = {1: NEUTRAL}
        self.retries: dict[int, int] = {1: 0}
        self.kit = Kit()
        # The ending readout: fighting time, shots and every power use, across retries.
        self.stats: dict = {"ticks": 0, "shots": 0, "powers": {}}
        self.world = encounter_world(seed, 1, NEUTRAL, tuning, arena, self.kit)
        self.checkpoint = copy.deepcopy(self.world)

    def step(self, inp: InputFrame) -> None:
        """Advance one tick. Outside an encounter (Fuse Box, ending) nothing moves, and the
        last encounter tick's events are not reported again."""
        if self.stage != "encounter":
            self.world.events.clear()
            return
        if inp.restart and self.world.outcome == "down":
            self.world = copy.deepcopy(self.checkpoint)
            self.world.events.clear()  # the checkpoint's spawn events belong to the first entry
            self.retries[self.encounter] += 1
            return
        if self.world.outcome != "playing":
            self.world.events.clear()  # waiting on the retry: nothing happens
            return
        step(self.world, inp, self.tuning, self.arena)
        self._count(self.world.events)
        if self.world.outcome == "clear":
            self.kit = Kit.from_world(self.world)
            self.stage = "fuse_box" if self.encounter < ENCOUNTERS else "ending"

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
        return equip(self.kit, slot, ability)

    def fuse(self, a: str, b: str) -> str:
        """Fuse Box: fuse two base powers. See powers.fuse for the result codes."""
        self._require_fuse_box()
        return fuse(self.kit, a, b)

    def _require_fuse_box(self) -> None:
        if self.stage != "fuse_box":
            raise RuntimeError(f"the Fuse Box is not open (stage {self.stage})")

    def begin_next(self, protocol: str) -> None:
        """Leave the Fuse Box and start the next encounter in `protocol`, frozen from now on."""
        if self.stage != "fuse_box":
            raise RuntimeError(f"cannot begin an encounter from stage {self.stage}")
        if protocol not in PROTOCOLS:
            raise ValueError(f"unknown protocol {protocol!r}")
        self.encounter += 1
        self.protocols[self.encounter] = protocol
        self.retries[self.encounter] = 0
        self.world = encounter_world(
            self.seed, self.encounter, protocol, self.tuning, self.arena, self.kit
        )
        self.checkpoint = copy.deepcopy(self.world)
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
