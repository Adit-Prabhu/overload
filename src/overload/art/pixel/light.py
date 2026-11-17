"""One glow pass for the pixel view: only what is drawn onto the light layer glows."""

from __future__ import annotations

from dataclasses import dataclass

import pygame

from overload.art.palette import rgb


@dataclass
class Glow:
    size: tuple[int, int]
    radius: int = 2
    passes: int = 1

    def __post_init__(self) -> None:
        w, h = self.size
        self.layer = pygame.Surface(self.size)
        self._small = pygame.Surface((w // 2, h // 2))
        self._scratch = pygame.Surface((w // 2, h // 2))
        self._big = pygame.Surface(self.size)

    def clear(self) -> None:
        self.layer.fill(rgb("px.void"))

    def apply(self, target: pygame.Surface) -> None:
        """Blur the light layer and add it to `target`, plus the crisp light itself."""
        self.layer.fill(rgb("px.void"), special_flags=pygame.BLEND_RGB_SUB)
        pygame.transform.smoothscale(self.layer, self._small.get_size(), self._small)
        pygame.transform.box_blur(self._small, self.radius, True, self._scratch)
        pygame.transform.box_blur(self._scratch, self.radius, True, self._small)
        pygame.transform.smoothscale(self._small, self.size, self._big)
        for _ in range(self.passes):
            target.blit(self._big, (0, 0), special_flags=pygame.BLEND_RGB_ADD)
