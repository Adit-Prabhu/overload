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
    from overload.art.pixel import regulators, robots

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
            for kind in regulators.KINDS:
                regulators.regulator(protocol, left, needle=0.5, lit=True, kind=kind)
    for shot in (robots.shard(), robots.shell(), robots.needle_dart(), robots.orb()):
        assert shot.get_width() > 0
    with pytest.raises(KeyError):
        regulators.regulator("berserk", False)


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


def test_each_chassis_has_its_own_silhouette(headless_pygame) -> None:
    """Adit, Nov 17: the bosses were one box in three colors. Each chassis now has its own
    shape, told apart without color, on one canvas size. The old chassis shared one mask
    (overlap 1.0). The tall Linesman and the wide Transformer still share a torso band, so
    the bar is under 0.65."""
    from overload.art.pixel import regulators

    masks = {}
    for kind in regulators.KINDS:
        image = regulators.body(kind)
        assert image.get_size() == regulators.body("linesman").get_size()
        masks[kind] = pygame.mask.from_surface(image)
    for a, b in itertools.combinations(regulators.KINDS, 2):
        overlap = masks[a].overlap_area(masks[b], (0, 0))
        union = masks[a].count() + masks[b].count() - overlap
        assert overlap / union < 0.65, (a, b)


def test_the_regulator_walks_and_its_poses_read(headless_pygame) -> None:
    """Legs move through the cycle, the protocol arms change the silhouette, the signature
    charge lights the chassis, and the Grid Core cracks when it overloads."""
    from overload.art.pixel import regulators

    def raw(image):
        return pygame.image.tobytes(image, "RGBA")

    for kind in regulators.KINDS:
        still = raw(regulators.regulator("clamp", False, kind=kind))
        steps = {raw(regulators.regulator("clamp", False, kind=kind, step=s)) for s in range(8)}
        assert still not in steps and len(steps) >= 4, kind
        poses = {raw(regulators.regulator(p, False, kind=kind)) for p in ("clamp", "insulate")}
        assert len(poses) == 2
        charged = raw(regulators.regulator("clamp", False, kind=kind, charged=True))
        assert charged != still, kind
    calm = regulators.regulator("clamp", False, kind="grid_core")
    hot = regulators.regulator("clamp", False, kind="grid_core", phase=3)
    assert raw(calm) != raw(hot)


def test_regulator_feet_reach_in_the_direction_it_moves() -> None:
    from overload.game.view import Gait, rival_heading

    left = Gait(0.0, 0.0, moved=1.0, dx=-1.0)
    assert rival_heading(left, facing_left=True) == 0
    assert rival_heading(left, facing_left=False) == 4
    down = Gait(0.0, 0.0, moved=1.0, dy=1.0)
    assert rival_heading(down, facing_left=True) == rival_heading(down, facing_left=False) == 2
    upper_left = Gait(0.0, 0.0, moved=1.0, dx=-1.0, dy=-1.0)
    assert rival_heading(upper_left, facing_left=False) == 5
    assert rival_heading(upper_left, facing_left=True) == 7


def test_the_drone_core_glow_sits_on_its_core(headless_pygame) -> None:
    """The glow is drawn at the sim position minus the hover, so it must land on the yellow
    Spark core of the sprite drawn at the drone's feet minus the same hover."""
    from types import SimpleNamespace

    from overload.art.pixel import robots
    from overload.game.view import ROBOT_FEET, hover

    image = robots.drone(0, False)
    spark = rgb("power.spark")
    rows = [
        y
        for y in range(image.get_height())
        for x in range(image.get_width())
        if tuple(image.get_at((x, y)))[:3] == spark
    ]
    core_from_bottom = image.get_height() - (min(rows) + max(rows)) / 2
    for tick in (0, 17, 40):
        bot = SimpleNamespace(kind="drone", id=3)
        lift = hover(bot, tick)
        core_y = ROBOT_FEET["drone"] - lift - core_from_bottom  # relative to the sim y
        assert abs(core_y - (0 - lift)) <= 1.5, tick


def test_the_sentry_kicks_back_when_it_fires(headless_pygame) -> None:
    from types import SimpleNamespace

    from overload.game.view import RECOIL_TICKS, robot_image

    sentry = SimpleNamespace(kind="sentry", phase="", id=2, tier=1, fire_timer=50)
    rest = robot_image(sentry, 0, False, False)
    kick = robot_image(sentry, 0, False, False, recoil=RECOIL_TICKS)
    assert pygame.image.tobytes(rest, "RGBA") != pygame.image.tobytes(kick, "RGBA")


def test_footfalls_kick_dust_and_short_moves_are_walks(headless_pygame) -> None:
    from types import SimpleNamespace

    from overload.game.view import STRIDE, PixelView
    from overload.sim.campaign import Campaign

    view = PixelView(Campaign(1))
    bot = SimpleNamespace(id=9, kind="breaker", x=0.0, y=0.0, health=5)
    world = SimpleNamespace(hostiles=[bot], rival=None)
    view._walk(world)
    sparks = len(view.sparks)
    for _ in range(int(STRIDE["breaker"] * 8 / 0.5)):  # one whole cycle
        bot.x += 0.5
        view._walk(world)
    assert len(view.sparks) > sparks, "a foot came down"
    bot.x += 6.0  # the fastest real move (a Clamp dash is 3.6) is still a walk
    view._walk(world)
    assert view.gaits[9].stride > 0
    assert view.gaits[9].dx > 0, "faces the way it walked"


def test_the_floor_dressing_is_fixed_and_leaves_the_room_data_alone(headless_pygame) -> None:
    """Dressing is seeded by tile: the same floor every run. It never touches the terrain or
    decor the simulation reads, and each sector gets its own ambience."""
    from overload.floor import FLOOR
    from overload.sim.arena import FLOOR_ARENA, arena_id

    before = arena_id(FLOOR_ARENA)
    sectors = tiles.floor_sectors(FLOOR)
    a = tiles.render_room(FLOOR.room, sectors)
    b = tiles.render_room(FLOOR.room, sectors)
    assert pygame.image.tobytes(a.background, "RGB") == pygame.image.tobytes(b.background, "RGB")
    assert a.emitters == b.emitters
    assert arena_id(FLOOR_ARENA) == before
    kinds = {e.kind for e in a.emitters}
    assert {"steam", "sparks", "drip", "flicker"} <= kinds
    for emitter in a.emitters:
        tx, ty = emitter.x // 16, emitter.y // 16
        if emitter.kind == "drip":
            assert sectors(tx, ty) == 2, "puddles belong to the cooling plant"
        if emitter.kind == "sparks":
            assert sectors(tx, ty) == 3, "damaged panels belong to the grid core"
    plain = tiles.render_room(FLOOR.room)  # no sector lookup: everything as sector 1
    assert not any(e.kind in ("drip", "sparks") for e in plain.emitters)


def test_floor_sectors_follow_the_grid() -> None:
    from overload.floor import FLOOR

    sectors = tiles.floor_sectors(FLOOR)
    for room in FLOOR.rooms:
        x, y = room.center
        assert sectors(x, y) == room.sector, room.id
    assert tiles.floor_sectors(None)(3, 3) == 1


def test_ambience_animates_near_the_camera_only(headless_pygame) -> None:
    from overload.art.pixel.dressing import Emitter
    from overload.game.view import PixelView, flickering
    from overload.sim.campaign import Campaign

    view = PixelView(Campaign(1))
    view.room.emitters = [Emitter("drip", 10, 10, 0), Emitter("drip", 5000, 5000, 0)]
    view.camera = [0.0, 0.0]
    view.motes, view.ripples = [], []
    view._ambience(0)
    assert view.ripples == [(10, 10, 0)], "the far puddle stays still"
    for _ in range(40):
        view._tick_cosmetics()
    assert view.ripples == []
    assert any(flickering(t, 3) for t in range(600))
    assert not all(flickering(t, 3) for t in range(30)), "a failing lamp is mostly on"


def test_the_aimable_armor_sits_on_the_hit_circle(headless_pygame) -> None:
    from overload.art.pixel import regulators
    from overload.sim.bosses import BY_KIND

    for kind, phase in itertools.product(regulators.KINDS, (1, 2, 3)):
        image = regulators.body(kind, phase=phase)
        shell = {rgb(token) for token in regulators.SHELLS[kind]}
        width, height = image.get_size()
        armor = [
            (x, y)
            for x, y in itertools.product(range(width), range(height))
            if image.get_at((x, y))[:3] in shell
        ]
        cx, cy = width // 2, height - regulators.FEET[kind]
        radius = BY_KIND[kind].radius
        inside = sum((x - cx) ** 2 + (y - cy) ** 2 <= radius**2 for x, y in armor)
        minimum = 0.8 if phase == 1 else 0.65
        assert inside / len(armor) >= minimum, (kind, phase, inside / len(armor))


def test_each_phase_changes_the_silhouette(headless_pygame) -> None:
    from overload.art.pixel import regulators

    for kind in regulators.KINDS:
        masks = [
            pygame.mask.from_surface(regulators.body(kind, phase=phase)) for phase in (1, 2, 3)
        ]
        for before, after in zip(masks, masks[1:], strict=False):
            overlap = before.overlap_area(after, (0, 0))
            union = before.count() + after.count() - overlap
            assert overlap / union <= 0.93, kind


def test_no_chassis_pose_is_cut_off(headless_pygame) -> None:
    from overload.art.pixel import regulators

    states = tuple(itertools.product((None, *range(8)), (False, True), (1, 2, 3), (False, True)))
    for kind in regulators.KINDS:
        for step, charged, phase, vent in states:
            for protocol in ("clamp", "insulate", "oscillate"):
                image = regulators.regulator(
                    protocol, False, kind=kind, step=step, charged=charged, phase=phase, vent=vent
                )
                bounds = image.get_bounding_rect()
                assert bounds.left > 0 and bounds.top > 0, (kind, step, phase, protocol)
                assert bounds.right < image.get_width(), (kind, step, phase, protocol)
                assert bounds.bottom < image.get_height(), (kind, step, phase, protocol)


def test_directional_walk_poses_fit_the_chassis_canvas(headless_pygame) -> None:
    from overload.art.pixel import regulators

    for kind, heading, step in itertools.product(regulators.KINDS, range(8), range(8)):
        image = regulators.regulator(
            "clamp", False, kind=kind, phase=3, step=step, heading=heading, charged=True
        )
        frame = image.get_bounding_rect()
        assert frame.left > 0 and frame.top > 0
        assert frame.right < image.get_width() and frame.bottom < image.get_height()


def test_the_legacy_regulator_draws_as_the_linesman(headless_pygame) -> None:
    from overload.art.pixel import regulators

    a = regulators.regulator("clamp", False, 0.3, kind="regulator")
    b = regulators.regulator("clamp", False, 0.3, kind="linesman")
    assert pygame.image.tobytes(a, "RGBA") == pygame.image.tobytes(b, "RGBA")


def test_regulator_stance_counters_body_translation() -> None:
    from overload.art.pixel import regulators

    for heading, (dx, dy) in enumerate(regulators.DIRECTIONS):
        positions = []
        for step in range(2, 7):
            sx, sy, lift = regulators.foot_pose(step, 0, heading)
            assert lift == 0
            distance = (step - 2) * regulators.STEP_DISTANCE
            positions.append((sx + dx * distance, sy + dy * distance))
        x, y = zip(*positions, strict=True)
        assert max(x) - min(x) <= 1.5 and max(y) - min(y) <= 1.5
        assert regulators.foot_pose(0, 0, heading)[2] >= 8
        assert regulators.foot_pose(0, 1, heading)[2] == 0


def test_ambience_does_not_pile_up_while_the_world_waits(headless_pygame) -> None:
    """On the down screen and the ending the world tick stops, but the view keeps its own
    clock, so a vent breathes and a puddle ripples at their usual pace."""
    from overload.art.pixel.dressing import Emitter
    from overload.game.view import PixelView
    from overload.sim.campaign import Campaign

    campaign = Campaign(1)
    view = PixelView(campaign)
    view.room.emitters = [Emitter("steam", 10, 10, 0), Emitter("drip", 20, 20, 0)]
    view.room.lamps = []
    view.camera = [0.0, 0.0]
    campaign.world.outcome = "down"  # the world tick no longer moves
    for _ in range(240):
        view.after_tick(campaign)
    assert len(view.ripples) <= 1
    assert len(view.motes) <= 12


def test_wall_words_and_fixtures_stay_readable(headless_pygame) -> None:
    """The upper-wall runs (cable trays, pipes, conduit) never cover a wall stencil or a
    fixture on an upper face, like the practice hall's 33 KV sign."""
    from overload.art.pixel import dressing
    from overload.rooms import SUBSTATION_HALL

    plain = tiles.render_room(SUBSTATION_HALL)
    original = dressing._upper_run
    calls = []
    dressing._upper_run = lambda s, light, x0, y0, tx, sector: calls.append((x0 // 16, y0 // 16))
    try:
        tiles.render_room(SUBSTATION_HALL)
    finally:
        dressing._upper_run = original
    for tx, ty, words, place in SUBSTATION_HALL.labels:
        if place == "wall":
            assert (tx, ty) not in calls, words
    for ty, row in enumerate(SUBSTATION_HALL.decor):
        for tx, char in enumerate(row):
            if char in "PSLVMp":
                assert (tx, ty) not in calls, (char, tx, ty)
    assert plain.background.get_size() == SUBSTATION_HALL.size


def test_wide_stains_keep_off_the_walls(headless_pygame) -> None:
    from overload.floor import FLOOR

    art = tiles.render_room(FLOOR.room, tiles.floor_sectors(FLOOR))
    rows = FLOOR.room.terrain
    for emitter in art.emitters:
        if emitter.kind != "drip":
            continue
        tx, ty = emitter.x // 16, emitter.y // 16
        around = [rows[ty + dy][tx + dx] for dx in (-1, 0, 1) for dy in (-1, 0, 1)]
        assert "#" not in around, (tx, ty)


def test_floor_sectors_cover_walls_corridors_and_the_hidden_room() -> None:
    from overload.floor import CELL, FLOOR

    sectors = tiles.floor_sectors(FLOOR)
    for room in FLOOR.rooms:
        x, y, w, h = room.rect
        for tx, ty in ((x, y), (x + w - 1, y + h - 1)):  # wall corners
            assert sectors(tx, ty) == room.sector, room.id
    assert sectors(*FLOOR.get("hidden").center) == 2
    for door in FLOOR.doors:  # a door gap takes the sector of the cell it sits in
        dx, dy, _, _ = door.rect
        cell_room = next(
            r
            for r in FLOOR.rooms
            if (r.rect[0] // CELL[0], r.rect[1] // CELL[1]) == (dx // CELL[0], dy // CELL[1])
        )
        assert sectors(dx, dy) == cell_room.sector, door.id


def test_a_chassis_falls_in_a_death_sequence_then_a_banner(headless_pygame) -> None:
    """View only: the wreck flickers and sinks while explosions chain over it, then its
    name and DOWN. The room has already cleared in the sim."""
    from floorbot import enter

    from overload.game.view import DOWNED_TICKS, WRECK_TICKS, PixelView
    from overload.sim.campaign import Campaign
    from overload.sim.damage import damage_rival
    from overload.sim.inputs import IDLE

    campaign = Campaign(1)
    enter(campaign, "s1_chamber")
    view = PixelView(campaign)
    screen = pygame.Surface((256, 144))
    rival = campaign.world.rival
    rival.boot = 0
    view.after_tick(campaign)  # remembers the chassis before the killing tick
    rival.health = 1
    damage_rival(campaign.world, 1, rival.x, rival.y)
    view.consume(campaign, campaign.world.events)
    assert view.wreck is not None and view.boss_banner[0] == "LINESMAN DOWN"
    booms = 0
    for _ in range(WRECK_TICKS):
        campaign.step(IDLE)
        view.after_tick(campaign)
        booms = max(booms, len(view.booms))
        view.draw(screen, campaign, (128, 72))
    assert view.wreck is None and booms > 0
    for _ in range(DOWNED_TICKS):
        view.after_tick(campaign)
    assert view.boss_banner is None


@pytest.mark.parametrize("surge_survives", (True, False))
def test_final_boss_defeat_is_presented_only_after_a_win(
    headless_pygame, monkeypatch, surge_survives
) -> None:
    from floorbot import enter, skip_sector

    from overload.game.view import DOWNED_TICKS, WRECK_TICKS, PixelView
    from overload.sim.campaign import Campaign
    from overload.sim.inputs import IDLE, InputFrame
    from overload.sim.state import Projectile

    run = Campaign(1)
    for protocol in ("spacing", "lateral"):
        skip_sector(run)
        run.begin_next(protocol)
    enter(run, "s3_chamber")
    view = PixelView(run)
    rival = run.world.rival
    rival.boot, rival.health, rival.phase = 0, 1, 3
    view.after_tick(run)
    player = run.world.player
    player.x, player.y = rival.x - 65, rival.y + 26
    run.world.projectiles.append(Projectile(101, rival.x, rival.y, 0, 0, 1, 1, False, 5))
    if not surge_survives:
        player.charge, player.invulnerable = 1, 0
        run.world.projectiles.append(Projectile(102, player.x, player.y, 0, 0, 1, 1, True, 5))

    run.step(IDLE)
    assert any(event.kind == "rival_destroyed" for event in run.world.events)
    view.after_tick(run)
    if not surge_survives:
        assert run.world.outcome == "down"
        assert view.wreck is None and view.boss_banner is None
        run.step(InputFrame(restart=True))
        view.after_tick(run)
        assert view.boss_banner is None and not view.booms
        return

    assert run.stage == "ending" and view.wreck is not None
    assert view.boss_banner[0] == "GRID CORE DOWN"
    stable_hash = run.state_hash()
    view.camera[0] = rival.x - 275
    for _ in range(35):
        view.follow(run, (128, 72))
    assert abs(rival.x - view.camera_offset()[0] - 128) <= 2
    rendered_ending = []
    monkeypatch.setattr(view, "draw_ending", lambda *_: rendered_ending.append(True))
    screen = pygame.Surface((256, 144))
    for _ in range(WRECK_TICKS):
        view.advance_defeat()
        view.draw_campaign_ending(screen, run)
    assert view.wreck is None and view.boss_banner is not None and not rendered_ending
    for _ in range(DOWNED_TICKS - WRECK_TICKS):
        view.advance_defeat()
    view.draw_campaign_ending(screen, run)
    assert rendered_ending == [True]
    assert run.state_hash() == stable_hash


def test_windowed_replay_applies_terminal_fusion_once(headless_pygame, monkeypatch, tmp_path):
    from floorbot import enter

    from overload.game import app
    from overload.session.replay import Recording, apply_menu
    from overload.sim.arena import arena_id
    from overload.sim.campaign import Campaign
    from overload.sim.inputs import IDLE
    from overload.sim.state import Projectile

    class ReplayCampaign(Campaign):
        def __init__(self, seed):
            super().__init__(seed)
            enter(self, "s1_chamber")
            rival = self.world.rival
            rival.boot, rival.health, rival.phase = 0, 1, 3
            self.world.unlocked = ["spark", "blink"]
            self.world.projectiles.append(
                Projectile(101, rival.x - 35, rival.y, 14, 0, 1, 1, False, 5)
            )
            rival.cooldown = 180

    run = ReplayCampaign(1)
    run.step(IDLE)
    run.step(IDLE)
    assert run.world.rival is None
    recording = Recording(
        1,
        run.tuning.tuning_id(),
        arena_id(run.arena),
        [IDLE, IDLE],
        mode="campaign",
        protocols=["lateral"],
    )
    recording.fuse_box("fuse", "spark", "blink")
    apply_menu(run, recording.menu[0])
    recording.final_hash = run.state_hash()
    path = tmp_path / "terminal-fuse.json"
    recording.save(path)

    applied = []

    def track(campaign, action):
        applied.append(action)
        apply_menu(campaign, action)

    monkeypatch.setattr(app, "Campaign", ReplayCampaign)
    monkeypatch.setattr(app, "apply_menu", track)
    monkeypatch.setattr(app, "_open_window", lambda _: pygame.display.set_mode((256, 144)))
    monkeypatch.setattr(app, "ticks_due", lambda *_: (5, 0.0))
    try:
        assert app.play(app.Options(replay=path, mute=True)) == 0
    finally:
        pygame.init()  # restore the module-scoped SDL fixture after the app shuts down
    assert applied == recording.menu


def test_the_boss_bar_shows_its_phases_and_flashes_while_it_vents(headless_pygame) -> None:
    plain = pygame.Surface((256, 144))
    notched = pygame.Surface((256, 144))
    hud.draw(plain, hud.Hud(charge=6, max_charge=6, rival_health=1.0, rival_phases=1))
    hud.draw(notched, hud.Hud(charge=6, max_charge=6, rival_health=1.0, rival_phases=3))
    assert pygame.image.tobytes(plain, "RGB") != pygame.image.tobytes(notched, "RGB")
    calm = pygame.Surface((256, 144))
    venting = pygame.Surface((256, 144))
    hud.draw(calm, hud.Hud(charge=6, max_charge=6, rival_health=1.0, tick=4))
    hud.draw(venting, hud.Hud(charge=6, max_charge=6, rival_health=1.0, tick=4, rival_venting=True))
    assert pygame.image.tobytes(calm, "RGB") != pygame.image.tobytes(venting, "RGB")


@pytest.mark.parametrize("sector", (1, 2, 3))
def test_real_health_thresholds_reach_the_permanent_phase_hud(headless_pygame, monkeypatch, sector):
    from floorbot import enter, skip_sector

    from overload.game.view import VIEW, PixelView
    from overload.sim.campaign import Campaign
    from overload.sim.inputs import IDLE
    from overload.sim.state import Projectile

    run = Campaign(1)
    for _ in range(sector - 1):
        skip_sector(run)
        run.begin_next("pressure")
    enter(run, f"s{sector}_chamber")
    rival = run.world.rival
    rival.boot = 0
    run.world.player.invulnerable = 10000
    view = PixelView(run)
    display = pygame.Surface(VIEW)
    calls = []
    text = hud.text

    def track(surface, label, *rest):
        calls.append(label)
        return text(surface, label, *rest)

    monkeypatch.setattr(hud, "text", track)
    view.draw(display, run, (128, 72))
    assert "PHASE 1/3" in calls

    for phase in (2, 3):
        target_health = rival.max_health * (4 - phase) // 3
        run.world.projectiles.append(
            Projectile(
                run.world.new_id(),
                rival.x,
                rival.y,
                0,
                0,
                1,
                rival.health - target_health,
                False,
                5,
            )
        )
        for _ in range(10):
            run.step(IDLE)
            view.after_tick(run)
            if rival.phase == phase:
                break
        calls.clear()
        view.draw(display, run, (128, 72))
        assert f"PHASE {phase}/3 SHIFTING" in calls
        while rival.change:
            run.step(IDLE)
            view.after_tick(run)
        calls.clear()
        view.draw(display, run, (128, 72))
        assert f"PHASE {phase}/3" in calls


def test_the_entrance_card_and_ending_rows(headless_pygame, monkeypatch) -> None:
    from floorbot import enter

    from overload.game.view import PixelView
    from overload.sim.campaign import Campaign

    campaign = Campaign(1)
    enter(campaign, "s2_chamber")
    view = PixelView(campaign)
    campaign.world.rival.boot = campaign.tuning.rival_boot // 2
    with_card = pygame.Surface((256, 144))
    view.draw(with_card, campaign, (128, 72))
    campaign.world.rival.boot = 0
    without = pygame.Surface((256, 144))
    view.draw(without, campaign, (128, 72))
    assert pygame.image.tobytes(with_card, "RGB") != pygame.image.tobytes(without, "RGB")
    ending = pygame.Surface((256, 144))
    original = hud.text
    boxes = {}

    def track(*args):
        rect = original(*args)
        boxes[args[1]] = rect
        return rect

    monkeypatch.setattr(hud, "text", track)
    view.draw_ending(ending, 120.0, 1, 50, {}, {"1": 1500, "2": 2400})
    assert boxes["SHOTS"].bottom < boxes["BOSSES 0:25  0:40"].top
    assert boxes["BOSSES 0:25  0:40"].bottom < boxes["POWERS TRIED"].top


def test_every_chassis_pose_renders(headless_pygame) -> None:
    from overload.art.pixel import regulators

    sizes = set()
    for kind in regulators.KINDS:
        for phase, charged, vent in itertools.product((1, 2, 3), (False, True), (False, True)):
            image = regulators.body(kind, charged=charged, phase=phase, vent=vent)
            sizes.add(image.get_size())
    assert len(sizes) == 1, "every pose on one canvas, so the anchor never jumps"
