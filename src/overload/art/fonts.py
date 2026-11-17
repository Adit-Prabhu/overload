"""The one UI font family: Chakra Petch (SIL Open Font License 1.1, see assets/fonts/OFL.txt)."""

from __future__ import annotations

from functools import cache

import pygame

from overload.paths import FONTS

_FILES = {
    "medium": FONTS / "ChakraPetch-Medium.ttf",
    "bold": FONTS / "ChakraPetch-Bold.ttf",
}


@cache
def font(size: int, weight: str = "medium") -> pygame.font.Font:
    """Cached font. Requires pygame.font to be initialized."""
    return pygame.font.Font(_FILES[weight], size)


def forget() -> None:
    """Drop cached fonts. Call after pygame.quit(), which invalidates every Font object."""
    font.cache_clear()
