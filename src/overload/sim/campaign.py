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
from typing import Literal

from overload.sim.arena import SUBSTATION, Arena
from overload.sim.inputs import InputFrame
from overload.sim.state import Player, World, state_hash
from overload.sim.tuning import DEFAULT, Tuning
from overload.sim.world import PROTOCOLS, spawn_arc_mite, spawn_rival, step

ENCOUNTERS = 3
NEUTRAL = "lateral"
Stage = Literal["encounter", "fuse_box", "ending"]


def encounter_world(
    seed: int, encounter: int, protocol: str, tuning: Tuning = DEFAULT, arena: Arena = SUBSTATION
) -> World:
    """A fresh fight: full charge, the Regulator in its frozen protocol, two Arc Mites."""
    world_seed = seed * 10 + encounter
    sx, sy = arena.player_spawn
    world = World(
        seed=world_seed,
        rng=random.Random(world_seed),
        player=Player(x=sx, y=sy, charge=tuning.player_max_charge),
        encounter=encounter,
    )
    rx, ry = arena.rival_spawn
    spawn_rival(world, rx, ry, protocol, tuning)
    for x, y in arena.practice_spawns:
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
        self.world = encounter_world(seed, 1, NEUTRAL, tuning, arena)
        self.checkpoint = copy.deepcopy(self.world)

    def step(self, inp: InputFrame) -> None:
        """Advance one tick. Outside an encounter (Fuse Box, ending) nothing moves."""
        if self.stage != "encounter":
            return
        if inp.restart and self.world.outcome == "down":
            self.world = copy.deepcopy(self.checkpoint)
            self.retries[self.encounter] += 1
            return
        step(self.world, inp, self.tuning, self.arena)
        if self.world.outcome == "clear":
            self.stage = "fuse_box" if self.encounter < ENCOUNTERS else "ending"

    def begin_next(self, protocol: str) -> None:
        """Leave the Fuse Box and start the next encounter in `protocol`, frozen from now on."""
        if self.stage != "fuse_box":
            raise RuntimeError(f"cannot begin an encounter from stage {self.stage}")
        if protocol not in PROTOCOLS:
            raise ValueError(f"unknown protocol {protocol!r}")
        self.encounter += 1
        self.protocols[self.encounter] = protocol
        self.retries[self.encounter] = 0
        self.world = encounter_world(self.seed, self.encounter, protocol, self.tuning, self.arena)
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
            },
            sort_keys=True,
            separators=(",", ":"),
        )
        return hashlib.sha256(blob.encode()).hexdigest()[:16]
