"""Render the pixel style frame: one staged screenshot for Adit's approval.

Usage: uv run python tools/art/pixel_style_frame.py [output.png]

Internal view is 256 x 144 with a camera into a larger room. The image is saved at 5x
(1280 x 720) with nearest-neighbor scaling, exactly as the game window shows it.
"""

from __future__ import annotations

import math
import os
import sys
from pathlib import Path

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import pygame  # noqa: E402

from overload.art.pixel import actors, effects, hud, tiles  # noqa: E402
from overload.art.pixel.light import Glow  # noqa: E402
from overload.paths import ROOT  # noqa: E402

VIEW = (256, 144)
SCALE = 5
DEFAULT_OUTPUT = ROOT / "docs" / "art" / "pixel_style_frame.png"

ROOM = [
    "########################",
    "#wwwwwwwwwwwwwwwwwwwwww#",
    "#......,......|.......,#",
    "#.TT..........|....I...#",
    "#.TT....g.....|........#",
    "#.......g.....|...,....#",
    "#-------------+--------#",
    "#.......,.....|........#",
    "#...I.........|....TT..#",
    "#.........,...|....TT..#",
    "#.............|........#",
    "#.....g.......|..,.....#",
    "########################",
]


def angle(a, b) -> float:
    return math.atan2(b[1] - a[1], b[0] - a[0])


def compose() -> pygame.Surface:
    rows = [row.replace("+", "|") for row in ROOM]
    background, conduit_light = tiles.render_room(rows)
    camera = (44, 18)
    view = pygame.Surface(VIEW)
    view.blit(background, (-camera[0], -camera[1]))
    glow = Glow(VIEW)
    glow.clear()
    glow.layer.blit(conduit_light, (-camera[0], -camera[1]))

    def v(point):  # room to view coordinates
        return (point[0] - camera[0], point[1] - camera[1])

    surge_feet = (150, 128)
    regulator_feet = (250, 112)
    mite_feet = (204, 150)
    relay_feet = (112, 98)
    relay_target = (128, 112)
    aim = angle((surge_feet[0], surge_feet[1] - 9), (regulator_feet[0], regulator_feet[1] - 12))

    effects.arc_trail(view, glow.layer, v((100, 150)), v((150, 120)), 0.8)
    effects.blink_ghost(view, glow.layer, v((100, 150)))
    effects.charge(view, glow.layer, v((122, 146)), "spark", 0.0)
    effects.charge(view, glow.layer, v((136, 150)), "blink", 0.6)
    effects.relay_destination(view, v(relay_target), 0.6)

    drawables = []
    for prop in tiles.props(rows):
        drawables.append((prop.base_y, lambda prop=prop: prop.draw(view, camera)))

    def draw_feet(image, feet):
        x, y = v(feet)
        view.blit(image, (round(x - image.get_width() / 2), round(y - image.get_height())))

    drawables.append((regulator_feet[1], lambda: draw_feet(
        actors.regulator("clamp", facing_left=True), regulator_feet)))
    drawables.append((mite_feet[1], lambda: draw_feet(
        actors.arc_mite(5, facing_left=True, charging=True), mite_feet)))
    drawables.append((relay_feet[1], lambda: draw_feet(
        actors.relay(0, facing_left=True), relay_feet)))

    def draw_surge():
        sprite = actors.surge("walk", 6, facing_left=False)
        x, y = v(surge_feet)
        top_left = (round(x - sprite.get_width() / 2), round(y - sprite.get_height()))
        effects.ghost(view, sprite, (top_left[0] - 10, top_left[1] + 4), 70)
        effects.ghost(view, sprite, (top_left[0] - 5, top_left[1] + 2), 110)
        view.blit(sprite, top_left)
        caster = pygame.transform.rotate(actors.caster(), -math.degrees(aim))
        hand = (x + 5, y - 7)
        view.blit(caster, caster.get_rect(center=(round(hand[0] + math.cos(aim) * 4),
                                                 round(hand[1] + math.sin(aim) * 4))))

    drawables.append((surge_feet[1], draw_surge))
    for _, draw in sorted(drawables, key=lambda item: item[0]):
        draw()

    effects.aim_tell(view, glow.layer, v((mite_feet[0], mite_feet[1] - 6)),
                     angle(mite_feet, surge_feet), 0.7)
    for d in (22, 44, 66):
        shot = (surge_feet[0] + 5 + math.cos(aim) * d, surge_feet[1] - 9 + math.sin(aim) * d)
        effects.player_shot(view, glow.layer, v(shot), aim)
    effects.bolt(view, glow.layer, v((184, 142)))
    effects.bolt(view, glow.layer, v((171, 137)))
    glow.apply(view)

    hud.draw(view, hud.Hud(
        charge=4, max_charge=6, dodge_ready=0.6, sockets=("spark", "blink"),
        cooldowns=(0.0, 0.45), rival_health=0.72, rival_protocol="clamp",
    ))
    reticle = effects.reticle()
    view.blit(reticle, reticle.get_rect(center=v((236, 100))))
    return pygame.transform.scale_by(view, SCALE)


def main(argv: list[str]) -> int:
    output = Path(argv[1]) if len(argv) > 1 else DEFAULT_OUTPUT
    pygame.init()
    try:
        output.parent.mkdir(parents=True, exist_ok=True)
        pygame.image.save(compose(), str(output))
    finally:
        pygame.quit()
    print(f"wrote {output}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
