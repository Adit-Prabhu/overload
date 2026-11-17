"""What is solid at a point: walls and props (bucketed, so a big floor stays fast) plus any
doors that are locked right now (world state). Every collision query in the simulation goes
through here."""

from __future__ import annotations

from collections.abc import Iterable

from overload.sim.geometry import Point, Rect, circle_hits_rect, clamp_inside, push_out_of_rect

BUCKET = 64  # px


def build_index(rects: Iterable[Rect]) -> dict[tuple[int, int], tuple[Rect, ...]]:
    """Each rectangle listed under every bucket it touches."""
    index: dict[tuple[int, int], list[Rect]] = {}
    for rect in rects:
        x, y, w, h = rect
        for bx in range(int(x // BUCKET), int((x + w) // BUCKET) + 1):
            for by in range(int(y // BUCKET), int((y + h) // BUCKET) + 1):
                index.setdefault((bx, by), []).append(rect)
    return {key: tuple(value) for key, value in index.items()}


def solids(world, arena, center: Point, reach: float) -> list[Rect]:
    """Walls and props within `reach` of `center` plus every locked door (there are few),
    each once, in a fixed order (index order, then doors in the arena's order), so results
    stay deterministic."""
    x, y = center
    seen: set[Rect] = set()
    found: list[Rect] = []
    for bx in range(int((x - reach) // BUCKET), int((x + reach) // BUCKET) + 1):
        for by in range(int((y - reach) // BUCKET), int((y + reach) // BUCKET) + 1):
            for rect in arena.index.get((bx, by), ()):
                if rect not in seen:
                    seen.add(rect)
                    found.append(rect)
    if world is not None and world.locked:
        locked = set(world.locked)
        found.extend(rect for door_id, rect in arena.doors if door_id in locked)
    return found


def line_clear(world, arena, start: Point, end: Point) -> bool:
    """No wall, prop or locked door crosses the straight line (sampled every 4 px, well
    under the thinnest obstacle)."""
    dx, dy = end[0] - start[0], end[1] - start[1]
    steps = max(1, int(max(abs(dx), abs(dy)) / 4.0))
    return not any(
        blocked(world, arena, (start[0] + dx * i / steps, start[1] + dy * i / steps), 1.0)
        for i in range(1, steps + 1)
    )


def blocked(world, arena, center: Point, radius: float) -> bool:
    return any(
        circle_hits_rect(center, radius, rect) for rect in solids(world, arena, center, radius)
    )


def move_body(x: float, y: float, vx: float, vy: float, radius: float, arena, world):
    """Move a circle and push it out of walls, props and locked doors. Speeds stay below the
    thinnest obstacle, so nothing tunnels."""
    pos = (x + vx, y + vy)
    nearby = solids(world, arena, pos, radius + abs(vx) + abs(vy) + 2.0)
    for _ in range(2):
        for rect in nearby:
            pos = push_out_of_rect(pos, radius, rect)
        pos = clamp_inside(pos, radius, arena.bounds)
    return pos
