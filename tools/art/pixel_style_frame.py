"""Render the pixel style frame: one staged screenshot for Adit's approval.

Usage: uv run python tools/art/pixel_style_frame.py [output.png]

Internal view is 256 x 144 with a camera into the substation hall (overload.rooms). The image
is saved at 5x (1280 x 720) with nearest-neighbor scaling, exactly as the game window shows it.
Frame order: floor and walls, props and actors sorted by their base, telegraphs and effects,
blackout lighting, glow, then the HUD.
"""

from __future__ import annotations

import math
import os
import sys
from pathlib import Path

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import pygame  # noqa: E402

from overload.art.palette import rgb, rgba  # noqa: E402
from overload.art.pixel import actors, effects, hud, tiles  # noqa: E402
from overload.art.pixel.light import Glow  # noqa: E402
from overload.art.pixel.lighting import Lighting  # noqa: E402
from overload.paths import ROOT  # noqa: E402
from overload.rooms import SUBSTATION_HALL  # noqa: E402

VIEW = (256, 144)
SCALE = 5
TICK = 40
DEFAULT_OUTPUT = ROOT / "docs" / "art" / "pixel_style_frame.png"


def angle(a, b) -> float:
    return math.atan2(b[1] - a[1], b[0] - a[0])


def compose() -> pygame.Surface:
    room = tiles.render_room(SUBSTATION_HALL)
    camera = (40, 8)

    def v(point):
        return (point[0] - camera[0], point[1] - camera[1])

    view = pygame.Surface(VIEW)
    view.blit(room.background, (-camera[0], -camera[1]))

    surge_feet = (146, 112)
    regulator_feet = (246, 96)
    mite_feet = (206, 138)
    relay_feet = (178, 60)
    relay_target = (196, 76)
    hand = (surge_feet[0] + 5, surge_feet[1] - 10)
    aim = angle(hand, (regulator_feet[0] - 6, regulator_feet[1] - 22))

    effects.relay_destination(view, v(relay_target), 0.6)

    def draw_feet(image, feet, shadow=8):
        x, y = v(feet)
        shade = pygame.Surface((shadow * 2, 5), pygame.SRCALPHA)
        pygame.draw.ellipse(shade, rgba("px.outline", 120), (0, 0, shadow * 2, 5))
        view.blit(shade, (round(x - shadow), round(y - 3)))
        view.blit(image, (round(x - image.get_width() / 2), round(y - image.get_height())))

    drawables = [(prop.base_y, lambda prop=prop: prop.draw(view, camera)) for prop in room.props]
    needle = angle((regulator_feet[0], regulator_feet[1] - 22), surge_feet)
    drawables.append(
        (
            regulator_feet[1],
            lambda: draw_feet(
                actors.regulator("clamp", facing_left=True, needle=needle), regulator_feet, 20
            ),
        )
    )
    drawables.append(
        (
            mite_feet[1],
            lambda: draw_feet(actors.arc_mite(5, facing_left=True, charging=True), mite_feet, 7),
        )
    )
    drawables.append((relay_feet[1], lambda: draw_feet(actors.relay(0, False), relay_feet, 7)))

    def draw_surge():
        sprite = actors.surge("walk", 6, facing_left=False, sockets=("spark", "blink"))
        x, y = v(surge_feet)
        top_left = (round(x - sprite.get_width() / 2), round(y - sprite.get_height()))
        effects.ghost(view, sprite, (top_left[0] - 10, top_left[1] + 4), 70)
        effects.ghost(view, sprite, (top_left[0] - 5, top_left[1] + 2), 110)
        draw_feet(sprite, surge_feet, 6)
        caster = pygame.transform.rotate(actors.caster(), -math.degrees(aim))
        hx, hy = v(hand)
        view.blit(
            caster,
            caster.get_rect(center=(round(hx + math.cos(aim) * 4), round(hy + math.sin(aim) * 4))),
        )

    drawables.append((surge_feet[1], draw_surge))
    for _, draw in sorted(drawables, key=lambda item: item[0]):
        draw()

    glow = Glow(VIEW)
    glow.clear()
    glow.layer.blit(room.light, (-camera[0], -camera[1]))
    for (x, y), token, phase in room.leds:
        if (TICK // 20 + phase) % 3:
            px, py = v((x, y))
            view.fill(rgb(token), (round(px), round(py), 1, 1))
            glow.layer.fill(rgb(token), (round(px), round(py), 1, 1))

    effects.arc_trail(view, glow.layer, v((100, 132)), v((144, 106)), 0.8)
    effects.blink_ghost(view, glow.layer, v((100, 132)))
    effects.charge(view, glow.layer, v((122, 138)), "spark", 0.0)
    effects.charge(view, glow.layer, v((136, 142)), "blink", 0.6)
    effects.aim_tell(
        view, glow.layer, v((mite_feet[0], mite_feet[1] - 6)), angle(mite_feet, surge_feet), 0.7
    )
    for d in (20, 40, 60):
        shot = (hand[0] + math.cos(aim) * d, hand[1] + math.sin(aim) * d)
        effects.player_shot(view, glow.layer, v(shot), aim)
    effects.bolt(view, glow.layer, v((190, 126)))
    effects.bolt(view, glow.layer, v((177, 121)))

    lighting = Lighting(VIEW)
    lighting.begin()
    for x, y in room.lamps:
        lighting.add(v((x, y + 24)), 84, "px.lamp", 100)
    for x, y in room.ceiling:
        lighting.add(v((x, y)), 64, "px.lamp.light", 75)
    lighting.add(v((surge_feet[0] + 14, surge_feet[1] - 10)), 40, "px.lamp.light", 70)
    lighting.add(v((regulator_feet[0], regulator_feet[1] - 8)), 40, "px.hostile.2", 22)
    lighting.apply(view)
    glow.apply(view)

    hud.draw(
        view,
        hud.Hud(
            charge=4,
            max_charge=6,
            dodge_ready=0.6,
            sockets=("spark", "blink"),
            cooldowns=(0.0, 0.45),
            rival_health=0.72,
            rival_protocol="clamp",
        ),
    )
    reticle = effects.reticle()
    view.blit(reticle, reticle.get_rect(center=v((236, 76))))
    return pygame.transform.scale_by(view, SCALE)


def room_overview() -> pygame.Surface:
    """The whole hall with props and lighting but no actors or HUD, for judging the tileset."""
    room = tiles.render_room(SUBSTATION_HALL)
    size = SUBSTATION_HALL.size
    view = room.background.copy()
    for prop in sorted(room.props, key=lambda prop: prop.base_y):
        prop.draw(view, (0, 0))
    glow = Glow(size)
    glow.clear()
    glow.layer.blit(room.light, (0, 0))
    for (x, y), token, _ in room.leds:
        view.fill(rgb(token), (x, y, 1, 1))
        glow.layer.fill(rgb(token), (x, y, 1, 1))
    lighting = Lighting(size)
    lighting.begin()
    for x, y in room.lamps:
        lighting.add((x, y + 24), 84, "px.lamp", 100)
    for x, y in room.ceiling:
        lighting.add((x, y), 64, "px.lamp.light", 75)
    lighting.apply(view)
    glow.apply(view)
    return pygame.transform.scale_by(view, 3)


def main(argv: list[str]) -> int:
    output = Path(argv[1]) if len(argv) > 1 else DEFAULT_OUTPUT
    pygame.init()
    try:
        output.parent.mkdir(parents=True, exist_ok=True)
        pygame.image.save(compose(), str(output))
        overview = output.with_name("pixel_room.png")
        pygame.image.save(room_overview(), str(overview))
    finally:
        pygame.quit()
    print(f"wrote {output} and {overview}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
