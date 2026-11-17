"""What is solid at a point: walls and props (bucketed, so a big floor stays fast) plus any
doors that are locked right now (world state). Every collision query in the simulation goes
through here."""

from __future__ import annotations

from collections.abc import Iterable

from overload.sim.geometry import Point, Rect, circle_hits_rect

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


def blocked(world, arena, center: Point, radius: float) -> bool:
    return any(
        circle_hits_rect(center, radius, rect) for rect in solids(world, arena, center, radius)
    )
