"""One tick of player input. Integers and booleans only, so replays are exact."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class InputFrame:
    move_x: int = 0
    move_y: int = 0
    aim_x: int = 0
    aim_y: int = 0
    fire: bool = False
    dodge: bool = False
    restart: bool = False

    def __post_init__(self) -> None:
        if self.move_x not in (-1, 0, 1) or self.move_y not in (-1, 0, 1):
            raise ValueError(f"move must be -1, 0 or 1, got ({self.move_x}, {self.move_y})")

    def to_list(self) -> list[int]:
        return [
            self.move_x,
            self.move_y,
            self.aim_x,
            self.aim_y,
            int(self.fire),
            int(self.dodge),
            int(self.restart),
        ]

    @classmethod
    def from_list(cls, values: list[int]) -> InputFrame:
        mx, my, ax, ay, fire, dodge, restart = values
        return cls(mx, my, ax, ay, bool(fire), bool(dodge), bool(restart))


IDLE = InputFrame()
