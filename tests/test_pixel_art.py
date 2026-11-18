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
        "charges": [
            effects.charge_icon(p) for p in ("spark", "blink", "arc_trail", "burst", "shock_cone")
        ],
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

    def spark(surface, c):
        effects.spark_shot(surface, pygame.Surface(surface.get_size()), c, 0.0)

    yield pytest.param(effects.hostile_bolt(), spark, id="hostile bolt vs Spark shot")
    yield pytest.param(shot, spark, id="player shot vs Spark shot")
    yield pytest.param(
        effects.charge_icon("arc_trail"),
        effects.protocol_icon("oscillate"),
        id="Arc Trail charge vs Oscillate icon",
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


def test_the_unlock_notice_names_the_power_from_the_event(headless_pygame) -> None:
    from overload.game.view import PixelView
    from overload.sim.run import Run
    from overload.sim.state import Event

    run = Run(1)
    view = PixelView(run)
    view.consume(run, [Event("unlock", 10, 10, 99, "blink")])
    assert view.notice[0] == "BLINK STOLEN"
    view.consume(run, [Event("unlock", 10, 10, 5, "spark"), Event("unlock", 9, 9, 6, "blink")])
    assert view.notice[0] == "SPARK AND BLINK STOLEN"


def test_tell_states_look_different_from_rest_states(headless_pygame) -> None:
    """The Oscillate volley tell lights the fins and the Relay's blink tell flips its lever,
    so each tell changes the sprite itself, not only the overlay."""
    rest, lit = actors.regulator("oscillate", False), actors.regulator("oscillate", False, lit=True)
    assert pygame.image.tobytes(rest, "RGBA") != pygame.image.tobytes(lit, "RGBA")
    idle, arming = actors.relay(False), actors.relay(False, arming=True)
    assert pygame.image.tobytes(idle, "RGBA") != pygame.image.tobytes(arming, "RGBA")


def test_the_fusion_flash_lasts_a_fixed_number_of_ticks(headless_pygame) -> None:
    from overload.game.view import FUSION_TICKS, PixelView
    from overload.sim.campaign import Campaign
    from overload.sim.powers import Kit

    campaign = Campaign(1)
    view = PixelView(campaign)
    view.flash_fusion()
    screen = pygame.Surface((256, 144))
    for _ in range(50):  # drawing many frames does not shorten it
        view.draw_fuse_box(screen, 2, True, None, Kit(), 0, None)
    assert view.fusion_flash == FUSION_TICKS
    for _ in range(FUSION_TICKS):
        view.update(campaign, (128, 72))
    assert view.fusion_flash == 0


def test_every_robot_and_shot_renders(headless_pygame) -> None:
    from overload.art.pixel import robots

    for left in (False, True):
        robots.drone(0, left)
        robots.drone(6, left)
        robots.relay_bot(left)
        robots.relay_bot(left, arming=True)
        robots.breaker(left)
        robots.breaker(left, raising=True)
        robots.sweeper(0, left, revving=True)
        robots.sentry(left)
        for protocol in ("clamp", "insulate", "oscillate"):
            robots.regulator_mech(protocol, left, needle=0.5, lit=True)
    for shot in (robots.shard(), robots.shell(), robots.needle_dart(), robots.orb()):
        assert shot.get_width() > 0
    with pytest.raises(KeyError):
        robots.regulator_mech("berserk", False)


def test_robots_never_use_power_colors_except_their_core(headless_pygame) -> None:
    """Power colors are for powers and power cores only (art direction rule)."""
    from overload.art.pixel import robots

    for name, rows, allowed in (
        ("drone", robots._DRONE, {"Y", "y"}),
        ("relay", robots._RELAY, {"K", "k"}),
        ("breaker", robots._BREAKER["rest"], {"U", "u"}),
        ("sweeper", robots._SWEEPER, set()),
        ("sentry", robots._SENTRY, set()),
    ):
        used = {c for row in rows for c in row} & set("YyKkUu")
        assert used <= allowed, name


def test_the_slam_shake_never_moves_the_aim(headless_pygame) -> None:
    from overload.game.view import PixelView
    from overload.sim.campaign import Campaign

    view = PixelView(Campaign(1))
    still = view.camera_offset()
    view.shake = 10
    assert view.camera_offset() == still, "aiming converts the cursor with this"
    assert view.jolt() != (0, 0) and max(map(abs, view.jolt())) <= 2


def test_sector_variants_recolor_the_shell_but_not_the_danger_red(headless_pygame) -> None:
    from overload.art.pixel import robots
    from overload.game.view import tier_colors

    stock = robots.drone(0, False)
    for tier in (2, 3):
        variant = tier_colors(stock, tier)
        assert variant is tier_colors(stock, tier), "cached per frame"
        colors = {
            tuple(variant.get_at((x, y)))[:3]
            for x in range(variant.get_width())
            for y in range(variant.get_height())
        }
        assert rgb("px.hostile.2") not in colors
        assert rgb("hostile.danger") in colors
    assert tier_colors(stock, 1) is stock


@pytest.mark.parametrize(
    "power, rarity",
    [("arc_trail", "rare"), ("bolt_lance", "epic"), ("chain_jump", "legendary")],
)
def test_the_menu_marks_each_fused_power_with_its_rarity(headless_pygame, power, rarity) -> None:
    from overload.art.palette import rgb
    from overload.game.view import PixelView
    from overload.sim.campaign import Campaign
    from overload.sim.powers import Kit

    kit = Kit(["spark", "blink", power], {"spark": 2}, [power, ""], bank={"spark": 1})
    screen = pygame.Surface((256, 144))
    PixelView(Campaign(1)).draw_fuse_box(screen, 1, True, None, kit, 2, None, title="LOADOUT")
    mark = rgb(f"px.rarity.{rarity}")
    # The marks sit at the right end of the power's row (row 3, the third 11 px row): count
    # the crosses there, 5 lit pixels each.
    left, row_y = 16, 8 + 4 + 15 + 11 + 2 * 11
    lit = [
        (x, y)
        for x in range(left + 86, left + 102)
        for y in range(row_y, row_y + 8)
        if screen.get_at((x, y))[:3] == mark
    ]
    assert len(lit) == 5 * ("rare", "epic", "legendary").index(rarity) + 5
    spare_row = row_y - 2 * 11  # Spark's row shows its one spare charge as +1
    dim = rgb("ui.dim")
    assert any(
        screen.get_at((x, y))[:3] == dim
        for x in range(left + 74, left + 87)
        for y in range(spare_row, spare_row + 8)
    )
