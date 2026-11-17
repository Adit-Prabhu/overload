"""A play session: the world plus its retry checkpoint.

The checkpoint is taken on entry. Restarting after the Surge goes down (or after a clear)
restores that exact snapshot, including the RNG, so a retry never secretly changes the
fight. Later, encounter entry will also freeze the loadout and the accepted rival tactic
here (AGENTS.md design invariants).
"""

from __future__ import annotations

import copy

from overload.sim.arena import SUBSTATION, Arena
from overload.sim.inputs import InputFrame
from overload.sim.state import World, state_hash
from overload.sim.tuning import DEFAULT, Tuning
from overload.sim.world import new_world, step


class Run:
    def __init__(self, seed: int, tuning: Tuning = DEFAULT, arena: Arena = SUBSTATION) -> None:
        self.seed = seed
        self.tuning = tuning
        self.arena = arena
        self.world: World = new_world(seed, tuning, arena)
        self.checkpoint: World = copy.deepcopy(self.world)
        self.retries = 0

    def step(self, inp: InputFrame) -> None:
        if inp.restart and self.world.outcome != "playing":
            self.world = copy.deepcopy(self.checkpoint)
            self.retries += 1
            return
        step(self.world, inp, self.tuning, self.arena)

    def state_hash(self) -> str:
        return state_hash(self.world)
