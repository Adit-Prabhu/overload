"""Blackout lighting for the pixel view.

The scene is multiplied by a light map: a dim blue ambient plus additive pools of light
(emergency lamps, the Surge's headlamp). Emissive things (conduits, cores, projectiles)
are added afterwards through the glow pass, so they stay bright in the dark.
"""

from __future__ import annotations

from functools import cache

import pygame

from overload.art.palette import rgb


@cache
def pool(radius: int, token: str, strength: int) -> pygame.Surface:
    """Radial light pool, drawn as concentric filled circles from the rim inward (fast, and
    identical every time). `strength` is a percentage, so the cache stays small."""
    size = radius * 2 + 1
    surface = pygame.Surface((size, size))
    surface.fill(rgb("fx.none"))
    r, g, b = rgb(token)
    for ring in range(radius, 0, -1):
        k = (1.0 - ring / radius) ** 1.6 * strength / 100
        shade = (min(255, round(r * k)), min(255, round(g * k)), min(255, round(b * k)))
        pygame.draw.circle(surface, shade, (radius, radius), ring)
    k = strength / 100
    surface.set_at(
        (radius, radius), (min(255, round(r * k)), min(255, round(g * k)), min(255, round(b * k)))
    )
    return surface


def quantize(strength: float, step: int = 5) -> int:
    """Round a varying strength (for example a pulsing lamp) so pools come from the cache."""
    return int(round(strength / step) * step)


class Lighting:
    """Two passes: multiply by the light map (darkness with lit areas), then add a faint tint
    of each light so pools read as warm, lit floor rather than just less dark."""

    TINT = 22  # percent of each light's color added on top after the multiply

    def __init__(self, size: tuple[int, int], ambient: str = "px.ambient") -> None:
        self.size = size
        self.ambient = ambient
        self.map = pygame.Surface(size)
        self.tint = pygame.Surface(size)

    def begin(self) -> None:
        self.map.fill(rgb(self.ambient))
        self.tint.fill(rgb("fx.none"))

    def add(self, pos: tuple[float, float], radius: int, token: str, strength: int = 100):
        center = (round(pos[0]), round(pos[1]))
        image = pool(radius, token, strength)
        self.map.blit(image, image.get_rect(center=center), special_flags=pygame.BLEND_RGB_ADD)
        tint = pool(radius, token, strength * self.TINT // 100)
        self.tint.blit(tint, tint.get_rect(center=center), special_flags=pygame.BLEND_RGB_ADD)

    def apply(self, target: pygame.Surface) -> None:
        target.blit(self.map, (0, 0), special_flags=pygame.BLEND_RGB_MULT)
        target.blit(self.tint, (0, 0), special_flags=pygame.BLEND_RGB_ADD)
