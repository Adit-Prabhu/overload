"""Shape comparison for the shape-before-color rule, tuned for pixel art.

In pixel art the dark outline wraps every sprite, so outer silhouettes all look alike. What
a player reads is the bright pattern inside: a bolt, a diamond, a ring. So shapes are
compared by their bright pixels (linear luminance above a cut), cropped, scaled to a fixed
square with nearest-neighbor and thickened by one pixel. A score near 1.0 means the same
pattern. This is a coarse automated guard. The color-vision contact sheet stays the main
review (docs/art/pixel_contact_sheet_cvd.png).
"""

from __future__ import annotations

import pygame

from overload.art import palette

CANVAS = 160
SIMILAR = 0.62
LUMA_CUT = 0.12


def _canvas(draw) -> pygame.Surface:
    canvas = pygame.Surface((CANVAS, CANVAS), pygame.SRCALPHA)
    center = (CANVAS // 2, CANVAS // 2)
    if isinstance(draw, pygame.Surface):
        canvas.blit(draw, draw.get_rect(center=center))
    else:
        draw(canvas, center)
    return canvas


def _linear(channel: int) -> float:
    c = channel / 255
    return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4


def bright_pattern(draw) -> pygame.Mask:
    canvas = _canvas(draw)
    opaque = pygame.mask.from_surface(canvas, 127)
    mask = pygame.mask.Mask((CANVAS, CANVAS))
    for box in opaque.get_bounding_rects():
        for y in range(box.top, box.bottom):
            for x in range(box.left, box.right):
                color = canvas.get_at((x, y))
                if color.a > 127:
                    r, g, b = (_linear(v) for v in color[:3])
                    if 0.2126 * r + 0.7152 * g + 0.0722 * b > LUMA_CUT:
                        mask.set_at((x, y), 1)
    return mask


def normalized(mask: pygame.Mask, size: int = 32, grow: int = 3) -> pygame.Mask:
    rects = mask.get_bounding_rects()
    box = rects[0].unionall(rects[1:])
    side = max(box.w, box.h)
    square = pygame.Surface((side, side), pygame.SRCALPHA)
    crop = mask.to_surface(
        setcolor=palette.rgba("fx.flash", 255), unsetcolor=palette.rgba("fx.none", 0)
    ).subsurface(box)
    square.blit(crop, ((side - box.w) // 2, (side - box.h) // 2))
    small = pygame.mask.from_surface(pygame.transform.scale(square, (size, size)), 127)
    return small.convolve(pygame.mask.Mask((grow, grow), fill=True))


def similarity(a, b) -> float:
    ma, mb = normalized(bright_pattern(a)), normalized(bright_pattern(b))
    both = ma.overlap_area(mb, (0, 0))
    return both / (ma.count() + mb.count() - both)
