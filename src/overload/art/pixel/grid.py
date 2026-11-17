"""Turn text grids into pixel surfaces.

A grid is a list of equal-purpose strings. Each character maps to a palette token through
a legend, and "." is transparent. `render` pads the sprite by one pixel and adds the shared
dark outline around every opaque pixel, which keeps the outline style identical everywhere.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence

import pygame

from overload.art.palette import rgb

TRANSPARENT = "."


def render(
    rows: Sequence[str],
    legend: Mapping[str, str],
    outline: str | None = "px.outline",
) -> pygame.Surface:
    """Render a grid. Unknown characters raise KeyError so typos never pass silently."""
    height = len(rows)
    width = max(len(row) for row in rows)
    pad = 1 if outline else 0
    surface = pygame.Surface((width + 2 * pad, height + 2 * pad), pygame.SRCALPHA)
    for y, row in enumerate(rows):
        for x, char in enumerate(row):
            if char != TRANSPARENT:
                surface.set_at((x + pad, y + pad), rgb(legend[char]))
    if outline:
        add_outline(surface, outline)
    return surface


def add_outline(surface: pygame.Surface, token: str) -> None:
    """Paint `token` on every transparent pixel that touches an opaque one (4 neighbors)."""
    mask = pygame.mask.from_surface(surface, 1)
    w, h = surface.get_size()
    color = rgb(token)
    edges = []
    for y in range(h):
        for x in range(w):
            if mask.get_at((x, y)):
                continue
            for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                nx, ny = x + dx, y + dy
                if 0 <= nx < w and 0 <= ny < h and mask.get_at((nx, ny)):
                    edges.append((x, y))
                    break
    for point in edges:
        surface.set_at(point, color)


def flipped(surface: pygame.Surface) -> pygame.Surface:
    return pygame.transform.flip(surface, True, False)


def stack(*parts: Sequence[str]) -> list[str]:
    """Join grid fragments top to bottom (for frames that share a head or body)."""
    rows: list[str] = []
    for part in parts:
        rows.extend(part)
    return rows
