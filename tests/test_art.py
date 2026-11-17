"""Art checks from docs/ART_AND_AUDIO_DIRECTION.md: everything renders, and shapes that
must be told apart actually differ in silhouette (shape before color)."""

import importlib.util
import itertools
import os

import pygame
import pytest

from overload.art import palette, scene, sprites
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


def silhouette(sprite: sprites.Sprite) -> pygame.Mask:
    canvas = pygame.Surface((CANVAS, CANVAS), pygame.SRCALPHA)
    sprite.draw(canvas, (CANVAS / 2, CANVAS / 2))
    return pygame.mask.from_surface(canvas, 127)


def overlap_ratio(a: pygame.Mask, b: pygame.Mask) -> float:
    """Intersection over union of two silhouettes. 1.0 means identical shapes."""
    both = a.overlap_area(b, (0, 0))
    union = a.count() + b.count() - both
    return both / union if union else 1.0


def test_every_sprite_has_visible_pixels() -> None:
    for name, sprite in sprites.catalog().items():
        assert silhouette(sprite).count() > 20, name


@pytest.mark.parametrize(
    "group",
    [
        [sprites.power_icon(power, 14) for power in sprites.POWER_TOKENS],
        [sprites.protocol_pose(protocol) for protocol in sprites.PROTOCOLS],
        [sprites.protocol_icon(protocol, 12) for protocol in sprites.PROTOCOLS],
        [sprites.arc_mite(), sprites.relay(), sprites.surge()],
    ],
    ids=["power icons", "protocol poses", "protocol icons", "characters"],
)
def test_silhouettes_are_distinct(group: list[sprites.Sprite]) -> None:
    for a, b in itertools.combinations(group, 2):
        assert overlap_ratio(silhouette(a), silhouette(b)) < 0.6


def test_rotation_keeps_the_shape() -> None:
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
