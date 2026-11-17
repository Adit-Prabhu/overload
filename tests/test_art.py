"""Art checks from docs/ART_AND_AUDIO_DIRECTION.md: everything renders, and shapes that
must be told apart actually differ in silhouette (shape before color)."""

import importlib.util
import itertools
import os

import pygame
import pytest

from overload.art import fonts, palette, scene, sprites
from overload.art import primitives as p
from overload.art.fonts import font
from overload.paths import ROOT

CANVAS = 160


@pytest.fixture(scope="module", autouse=True)
def headless_pygame():
    os.environ["SDL_VIDEODRIVER"] = "dummy"
    os.environ["SDL_AUDIODRIVER"] = "dummy"
    pygame.init()
    yield
    pygame.quit()
    fonts.forget()


def silhouette(draw) -> pygame.Mask:
    """Mask of whatever `draw(surface, center)` paints, or of a Sprite drawn at the center."""
    canvas = pygame.Surface((CANVAS, CANVAS), pygame.SRCALPHA)
    if isinstance(draw, sprites.Sprite):
        draw.draw(canvas, (CANVAS / 2, CANVAS / 2))
    else:
        draw(canvas, (CANVAS / 2, CANVAS / 2))
    return pygame.mask.from_surface(canvas, 127)


def outline(mask: pygame.Mask) -> pygame.Mask:
    """Boundary pixels only. Filled shapes overlap a lot even when they look different (a disk
    covers most of a square), so shapes are compared by their outlines."""
    outside = mask.copy()
    outside.invert()
    near_outside = outside.convolve(pygame.mask.Mask((3, 3), fill=True))
    return mask.overlap_mask(near_outside, (-1, -1))


def normalized(mask: pygame.Mask, size: int = 48, grow: int = 5) -> pygame.Mask:
    """Crop to the shape, scale to a fixed square and thicken slightly.

    Size and stroke width stop mattering, so two drawings of the same shape at different
    sizes compare as similar. That is the failure mode the shape-before-color rule is about.
    """
    rects = mask.get_bounding_rects()
    box = rects[0].unionall(rects[1:])
    side = max(box.w, box.h)
    square = pygame.Surface((side, side), pygame.SRCALPHA)
    crop = mask.to_surface(
        setcolor=palette.rgba("fx.flash", 255), unsetcolor=palette.rgba("bg.void", 0)
    ).subsurface(box)
    square.blit(crop, ((side - box.w) // 2, (side - box.h) // 2))
    small = pygame.mask.from_surface(pygame.transform.smoothscale(square, (size, size)), 60)
    return small.convolve(pygame.mask.Mask((grow, grow), fill=True))


def similarity(a, b) -> float:
    """Intersection over union of normalized silhouettes. 1.0 means the same shape."""
    ma, mb = normalized(outline(silhouette(a))), normalized(outline(silhouette(b)))
    both = ma.overlap_area(mb, (0, 0))
    return both / (ma.count() + mb.count() - both)


SIMILAR = 0.62


def test_metric_flags_same_shape_at_different_sizes() -> None:
    def ring(radius):
        return lambda surface, c: p.ring(surface, "ui.text", c, radius, 2)

    def diamond(radius):
        return lambda surface, c: p.stroke(surface, "ui.text", p.diamond(c, radius), 2, True)

    def disk(radius):
        return lambda surface, c: p.dot(surface, "ui.text", c, radius)

    assert similarity(ring(6), ring(14)) >= SIMILAR
    assert similarity(diamond(8), diamond(20)) >= SIMILAR
    assert similarity(disk(10), disk(25)) >= SIMILAR


def test_every_sprite_has_visible_pixels() -> None:
    for name, sprite in sprites.catalog().items():
        assert silhouette(sprite).count() > 20, name


def _confusable_pairs():
    s = sprites
    group = {
        "power icons": [s.power_icon(power, 14) for power in s.POWER_TOKENS],
        "charges": [s.charge(power) for power in s.POWER_TOKENS],
        "protocol poses": [s.protocol_pose(protocol) for protocol in s.PROTOCOLS],
        "protocol icons": [s.protocol_icon(protocol, 12) for protocol in s.PROTOCOLS],
        "characters": [s.arc_mite(), s.relay(), s.surge()],
    }
    for name, items in group.items():
        for a, b in itertools.combinations(items, 2):
            yield pytest.param(a, b, id=name)

    def bolt(surface, c):
        scene.draw_hostile_bolt(surface, c)

    def shot(surface, c):
        scene.draw_player_shot(surface, c, 0.0)

    def via(surface, c):
        p.ring(surface, "bg.trace", c, 4, 2)

    def afterimage(surface, c):
        scene.draw_blink_afterimage(surface, c, 0.6)

    def destination(surface, c):
        scene.draw_relay_destination(surface, c, 0.6)

    yield pytest.param(bolt, shot, id="hostile bolt vs player shot")
    yield pytest.param(bolt, via, id="hostile bolt vs floor via")
    yield pytest.param(bolt, s.charge("burst"), id="hostile bolt vs Burst charge")
    yield pytest.param(afterimage, destination, id="Blink afterimage vs Relay destination")


@pytest.mark.parametrize(("a", "b"), list(_confusable_pairs()))
def test_confusable_things_have_distinct_shapes(a, b) -> None:
    assert similarity(a, b) < SIMILAR


def test_rotation_cache() -> None:
    mite = sprites.arc_mite()
    rotated = mite.rotated(1.0)
    assert rotated is not mite.surface
    assert mite.rotated(1.0) is rotated, "rotations are cached"
    assert mite.rotated(0.01) is mite.surface, "near-zero angles reuse the original"


def test_unknown_names_are_rejected() -> None:
    with pytest.raises(KeyError):
        sprites.power_icon("laser", 10)
    with pytest.raises(KeyError):
        sprites.protocol_pose("panic")
    with pytest.raises(KeyError):
        scene.render_floor((64, 64), (0, 0, 64, 64), [], lighting="disco")


def test_rgba_validates_alpha() -> None:
    assert palette.rgba("fx.flash", 0) == (255, 255, 255, 0)
    with pytest.raises(ValueError):
        palette.rgba("fx.flash", 300)


def test_font_renders() -> None:
    text = font(16, "bold").render("REGULATOR", True, palette.rgb("ui.text"))
    assert text.get_width() > 40


def test_floor_lighting_states_differ() -> None:
    bounds = (16.0, 16.0, 288.0, 168.0)
    standby, _ = scene.render_floor((320, 200), bounds, [], "standby")
    overload, _ = scene.render_floor((320, 200), bounds, [], "overload")
    lit = palette.rgb("bg.trace_lit")

    def lit_pixels(surface: pygame.Surface) -> int:
        return sum(
            1
            for x in range(0, 320, 2)
            for y in range(0, 200, 2)
            if tuple(surface.get_at((x, y)))[:3] == lit
        )

    assert lit_pixels(overload) > lit_pixels(standby)


def test_style_frame_composes() -> None:
    path = ROOT / "tools" / "art" / "style_frame.py"
    spec = importlib.util.spec_from_file_location("style_frame", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    frame = module.compose()
    assert frame.get_size() == (1280, 720)
