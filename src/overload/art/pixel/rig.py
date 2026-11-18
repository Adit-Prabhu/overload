"""Walk rigs (Adit, Nov 17: "I want them to move with their legs moving"). Robots are built
from character grids: a body, then legs and arms posed for a step of the walk cycle, then
rendered once through grid.render (so the shared outline wraps the whole robot).

The cycle has eight steps. A leg swings its foot forward while lifted and pushes it back
while planted, the two legs of a pair half a cycle apart. The body rides a pixel higher on
the passing steps, when one foot is in the air. The view advances the step by the distance
the robot actually walked (game/view.py): a robot that stops stands still, a faster one
steps faster, and a jump never spins its legs. At this pixel scale a planted foot still
slips a little (its 2 px push back against about 8 px walked per half cycle), the usual
trade in small sprites, where a true contact stride would flicker.
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass

STEPS = 8


def blank(width: int, height: int) -> list[list[str]]:
    return [["."] * width for _ in range(height)]


def paint(canvas: list[list[str]], rows: Sequence[str], x: int, y: int) -> None:
    """Copy a grid onto a canvas at (x, y). "." is transparent, off-canvas pixels drop."""
    for dy, row in enumerate(rows):
        cy = y + dy
        if not 0 <= cy < len(canvas):
            continue
        for dx, char in enumerate(row):
            cx = x + dx
            if char != "." and 0 <= cx < len(canvas[cy]):
                canvas[cy][cx] = char


def rows_of(canvas: list[list[str]]) -> list[str]:
    return ["".join(row) for row in canvas]


@dataclass(frozen=True)
class LegStyle:
    """How a leg looks: `upper` and `lower` are its two pixel columns (lit then shaded) above
    and below the knee, `knee` the joint. `foot` is the foot's row, toe to the right, with
    the leg standing on `heel`. `swing` and `lift` are in pixels."""

    upper: str
    lower: str
    knee: str
    foot: str
    heel: int
    swing: int = 1
    lift: int = 1


def pose(step: int | None, half: int, style: LegStyle) -> tuple[int, int]:
    """(swing, lift) of a leg at a walk step. `half` 0 or 1 puts it half a cycle apart from
    its partner. Standing still (None) is (0, 0)."""
    if step is None:
        return 0, 0
    angle = 2 * math.pi * (step / STEPS + half / 2)
    swing = round(style.swing * math.sin(angle))
    lift = round(style.lift * max(0.0, math.cos(angle)))
    return swing, lift


def rising(step: int | None) -> bool:
    """The passing steps (one foot high), when the body rides a pixel up."""
    return step is not None and step % (STEPS // 2) == 0


def leg(canvas, hip_x: int, top: int, length: int, swing: int, lift: int, style: LegStyle):
    """Draw one leg from its hip (top row `top`) down to its foot. A lifted leg bends its
    knee forward."""
    foot_y = top + length - 1 - lift
    column = foot_y - top
    knee = column // 2
    for r in range(column):
        t = (r + 1) / max(1, column)
        x = hip_x + round(swing * t)
        if lift and r == knee:
            x += 1
        chars = style.knee if r == knee else style.upper if r < knee else style.lower
        paint(canvas, [chars], x, top + r)
    paint(canvas, [style.foot], hip_x + swing - style.heel, foot_y)
