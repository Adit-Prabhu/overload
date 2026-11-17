"""Pixel art checks from docs/ART_AND_AUDIO_DIRECTION.md: grids are valid, everything renders,
things that must be told apart have distinct shapes, rooms are well formed, and lighting and
the review renders work."""

from __future__ import annotations

import importlib.util
import itertools
import math
import os

import pygame
import pytest
from shapes import SIMILAR, similarity

from overload.art.palette import rgb
from overload.art.pixel import actors, effects, hud, tiles
from overload.art.pixel.grid import render
from overload.art.pixel.lighting import pool
from overload.paths import ROOT
from overload.rooms import SUBSTATION_HALL, Room


@pytest.fixture(scope="module", autouse=True)
def headless_pygame():
    os.environ["SDL_VIDEODRIVER"] = "dummy"
    os.environ["SDL_AUDIODRIVER"] = "dummy"
    pygame.init()
    yield
    pygame.quit()
    hud.forget()
    tiles.forget_fonts()


# Grids -------------------------------------------------------------------------------------


def test_grid_adds_the_shared_outline() -> None:
    image = render(["X"], {"X": "player.core"})
    assert image.get_size() == (3, 3)
    assert tuple(image.get_at((1, 1)))[:3] == rgb("player.core")
    assert tuple(image.get_at((1, 0)))[:3] == rgb("px.outline")
    assert image.get_at((0, 0)).a == 0, "corners stay transparent (4-neighbor outline)"


def test_grid_rejects_unknown_characters() -> None:
    with pytest.raises(KeyError):
        render(["XZ"], {"X": "player.core"})


# Characters --------------------------------------------------------------------------------


def test_animation_frames_share_a_size() -> None:
    for name, frames in actors.surge_frames().items():
        assert len({frame.get_size() for frame in frames}) == 1, name
    assert len({f.get_size() for f in actors.arc_mite_frames()}) == 1
    assert len({f.get_size() for f in actors.relay_frames()}) == 1


def test_every_character_renders() -> None:
    images = [
        *actors.surge_frames()["idle"],
        *actors.surge_frames()["walk"],
        actors.caster(),
        *actors.arc_mite_frames(),
        *actors.relay_frames(),
        *(actors.regulator(p, False, 0.5) for p in ("clamp", "insulate", "oscillate")),
    ]
    for image in images:
        assert pygame.mask.from_surface(image).count() > 20


def test_pack_sockets_show_equipped_powers() -> None:
    image = actors.surge("idle", 0, False, ("spark", "blink"))
    (x1, y1), (x2, y2) = actors.SURGE_SOCKETS
    assert tuple(image.get_at((x1, y1 + 1)))[:3] == rgb("power.spark")
    assert tuple(image.get_at((x2, y2 + 1)))[:3] == rgb("power.blink")


def test_facing_left_mirrors_the_sprite() -> None:
    right = actors.surge("idle", 0, False)
    left = actors.surge("idle", 0, True)
    assert left.get_at((1, 10)) == right.get_at((right.get_width() - 2, 10))


def test_regulator_needle_tracks_the_target() -> None:
    a = actors.regulator("clamp", False, 0.0)
    b = actors.regulator("clamp", False, math.pi / 2)
    assert pygame.image.tobytes(a, "RGBA") != pygame.image.tobytes(b, "RGBA")


def test_unknown_protocol_is_rejected() -> None:
    with pytest.raises(KeyError):
        actors.regulator("panic", False)


# Shapes ------------------------------------------------------------------------------------


def test_metric_flags_same_shape_at_different_sizes() -> None:
    def disk(radius):
        return lambda surface, c: pygame.draw.circle(surface, rgb("ui.text"), c, radius)

    assert similarity(disk(6), disk(20)) >= SIMILAR


def _confusable_pairs():
    groups = {
        "protocol pose parts": [actors.clamp_arm(), actors.insulate_plate(), actors.fin()],
        "protocol icons": [effects.protocol_icon(p) for p in ("clamp", "insulate", "oscillate")],
        "charges": [effects.charge_icon(p) for p in ("spark", "blink", "burst")],
        "characters": [
            actors.surge_frames()["idle"][0],
            actors.arc_mite_frames()[0],
            actors.relay_frames()[0],
        ],
    }
    for name, items in groups.items():
        for a, b in itertools.combinations(items, 2):
            yield pytest.param(a, b, id=name)

    def shot(surface, c):
        effects.player_shot(surface, pygame.Surface(surface.get_size()), c, 0.0)

    yield pytest.param(effects.hostile_bolt(), shot, id="hostile bolt vs player shot")
    yield pytest.param(
        effects.hostile_bolt(), effects.charge_icon("burst"), id="hostile bolt vs Burst charge"
    )


@pytest.mark.parametrize(("a", "b"), list(_confusable_pairs()))
def test_confusable_things_have_distinct_shapes(a, b) -> None:
    assert similarity(a, b) < SIMILAR


# Rooms -------------------------------------------------------------------------------------


def test_room_rows_must_match() -> None:
    with pytest.raises(ValueError, match="wide"):
        Room("bad", ("###", "##"), ("...", ".."))


def test_wall_decor_must_be_on_a_wall() -> None:
    with pytest.raises(ValueError, match="not on a wall"):
        Room("bad", ("###", "#.#", "###"), ("...", ".L.", "..."))


def test_props_must_be_on_the_floor() -> None:
    with pytest.raises(ValueError, match="on a wall"):
        Room("bad", ("###", "#.#", "###"), ("T..", "...", "..."))


def test_transformer_needs_a_clear_footprint() -> None:
    with pytest.raises(ValueError, match="footprint"):
        Room("bad", ("####", "#..#", "#.##", "####"), ("....", ".T..", "....", "...."))


def test_hall_renders_with_its_lights_and_props() -> None:
    art = tiles.render_room(SUBSTATION_HALL)
    decor = "".join(SUBSTATION_HALL.decor)
    assert art.background.get_size() == SUBSTATION_HALL.size
    assert len(art.lamps) == decor.count("L")
    assert len(art.ceiling) == decor.count("u")
    assert len(art.props) == sum(decor.count(c) for c in "TCRIKB")
    assert art.leds, "breaker panels register blinking LEDs"


# Lighting ----------------------------------------------------------------------------------


def test_light_pool_is_black_outside_and_colored_inside() -> None:
    image = pool(10, "px.lamp", 100)
    assert tuple(image.get_at((0, 0)))[:3] == rgb("fx.none")
    assert tuple(image.get_at((10, 10)))[:3] == rgb("px.lamp")


# Review renders ----------------------------------------------------------------------------


def test_style_frame_and_room_overview_compose() -> None:
    path = ROOT / "tools" / "art" / "pixel_style_frame.py"
    spec = importlib.util.spec_from_file_location("pixel_style_frame", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    assert module.compose().get_size() == (1280, 720)
    assert module.room_overview().get_size() == (
        SUBSTATION_HALL.size[0] * 3,
        SUBSTATION_HALL.size[1] * 3,
    )
