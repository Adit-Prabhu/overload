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


def _colors(image: pygame.Surface) -> set[tuple[int, int, int]]:
    return {
        tuple(image.get_at((x, y)))[:3]
        for x in range(image.get_width())
        for y in range(image.get_height())
        if image.get_at((x, y)).a
    }


def _robot_frames(robots) -> dict[str, list[pygame.Surface]]:
    steps = (None, *range(robots.rig.STEPS))
    return {
        "drone": [
            robots.drone(t, False, moving, aiming)
            for t in range(6)
            for moving in (0, 1)
            for aiming in (False, True)
        ],
        "relay": [robots.relay_bot(False, arming, s) for arming in (False, True) for s in steps],
        "breaker": [robots.breaker(False, step=s) for s in steps]
        + [robots.breaker(False, raising=True), robots.breaker(False, slamming=True)],
        "sweeper": [robots.sweeper(s, False) for s in steps]
        + [robots.sweeper(None, False, revving=True, tick=t) for t in range(4)],
        "sentry": [robots.sentry(False, scan, kick) for scan in range(5) for kick in (0, 2)],
    }


def test_robots_never_use_power_colors_except_their_core(headless_pygame) -> None:
    """Power colors are for powers and power cores only (art direction rule), in every
    frame of every pose, legs and arms included."""
    from overload.art.pixel import robots

    power = {
        "spark": {rgb("power.spark"), rgb("px.spark.light")},
        "blink": {rgb("power.blink"), rgb("px.blink.light")},
        "burst": {rgb("power.burst"), rgb("px.burst.light")},
    }
    carries = {"drone": "spark", "relay": "blink", "breaker": "burst"}
    every_power = set().union(*power.values())
    for name, frames in _robot_frames(robots).items():
        allowed = power.get(carries.get(name, ""), set())
        for frame in frames:
            assert _colors(frame) & every_power <= allowed, name
        if name in carries:
            assert _colors(frames[0]) & allowed, f"{name} shows the core it carries"


def test_each_robot_keeps_one_frame_size(headless_pygame) -> None:
    """The view anchors a robot at the bottom middle of its frame, so every pose and walk
    step of one robot shares a size and nothing jumps when the frame changes."""
    from overload.art.pixel import robots

    for name, frames in _robot_frames(robots).items():
        assert len({frame.get_size() for frame in frames}) == 1, name


def test_walkers_move_their_legs(headless_pygame) -> None:
    """Adit, Nov 17: robots must walk on moving legs, not glide. Every step of the cycle
    differs from standing, and the cycle comes back around."""
    from overload.art.pixel import robots

    def raw(image):
        return pygame.image.tobytes(image, "RGBA")

    for make in (
        lambda s: robots.relay_bot(False, step=s),
        lambda s: robots.breaker(False, step=s),
        lambda s: robots.sweeper(s, False),
    ):
        still = raw(make(None))
        cycle = [raw(make(s)) for s in range(robots.rig.STEPS)]
        assert all(frame != still for frame in cycle)
        assert len(set(cycle)) >= 4, "at least four distinct poses in a cycle"


def test_rig_legs_alternate() -> None:
    from overload.art.pixel import rig

    style = rig.LegStyle("Mm", "Mm", "XX", "dXXd", 1, swing=2, lift=1)
    assert rig.pose(None, 0, style) == (0, 0)
    for step in range(rig.STEPS):
        a, b = rig.pose(step, 0, style), rig.pose(step, 1, style)
        assert a[0] == -b[0], "the two feet swing opposite ways"
        assert not (a[1] and b[1]), "never both feet in the air"
    assert any(rig.pose(s, 0, style)[1] for s in range(rig.STEPS)), "a foot lifts"


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


def test_the_walk_cycle_follows_distance_walked(headless_pygame) -> None:
    """A robot's step advances with the distance it moved, it stands still when it stops,
    and a jump (a Relay Bot's blink) resets its stride instead of spinning its legs."""
    from types import SimpleNamespace

    from overload.game.view import STRIDE, PixelView, walk_step
    from overload.sim.campaign import Campaign

    view = PixelView(Campaign(1))
    bot = SimpleNamespace(id=7, kind="breaker", x=100.0, y=100.0, health=5)
    world = SimpleNamespace(hostiles=[bot], rival=None)
    view._walk(world)
    assert walk_step(view.gaits[7], "breaker") is None, "just arrived: standing"
    steps = []
    for _ in range(12):
        bot.x += 0.5
        view._walk(world)
        steps.append(walk_step(view.gaits[7], "breaker"))
    assert None not in steps and len(set(steps)) > 1
    assert view.gaits[7].stride == 6.0 and STRIDE["breaker"] > 0
    view._walk(world)  # did not move this tick
    assert walk_step(view.gaits[7], "breaker") is None
    bot.x += 40  # a teleport
    view._walk(world)
    assert view.gaits[7].stride == 0.0
    world.hostiles = []
    view._walk(world)
    assert 7 not in view.gaits and 7 not in view.steps


def test_relay_teleports_beam_and_shots_recoil(headless_pygame) -> None:
    from overload.game.view import PixelView
    from overload.sim.campaign import Campaign
    from overload.sim.state import Event

    campaign = Campaign(1)
    view = PixelView(campaign)
    view.consume(campaign, [Event("relay_from", 10, 10, 3), Event("relay_blink", 50, 10, 3)])
    assert len(view.beams) == 2
    view.consume(campaign, [Event("shell", 10, 10, 4)])
    assert view.recoils[4] > 0
    for _ in range(20):
        view._tick_cosmetics()
    assert not view.beams and 4 not in view.recoils
