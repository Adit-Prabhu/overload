"""Render the style frame: one composed target screenshot for Adit's approval.

Usage: uv run python tools/art/style_frame.py [output.png]

Shows the Surge, the Regulator in Clamp protocol, an Arc Mite and a Relay mid-tell, an
Arc Trail, charges, shots and the HUD on the substation floor. Positions are a staged
composition, not gameplay. See docs/ART_AND_AUDIO_DIRECTION.md section 4.
"""

from __future__ import annotations

import math
import os
import sys
from pathlib import Path

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import pygame  # noqa: E402

from overload import __version__  # noqa: E402
from overload.art import scene  # noqa: E402
from overload.paths import ROOT  # noqa: E402

SIZE = (1280, 720)
BOUNDS = (16.0, 16.0, 1248.0, 688.0)
OBSTACLES = [
    (250.0, 140.0, 36.0, 140.0),
    (994.0, 140.0, 36.0, 140.0),
    (250.0, 440.0, 36.0, 140.0),
    (994.0, 440.0, 36.0, 140.0),
    (560.0, 92.0, 160.0, 32.0),
]
DEFAULT_OUTPUT = ROOT / "docs" / "art" / "style_frame.png"


def angle(a: tuple[float, float], b: tuple[float, float]) -> float:
    return math.atan2(b[1] - a[1], b[0] - a[0])


def compose() -> pygame.Surface:
    screen = pygame.Surface(SIZE)
    floor, glow = scene.render_floor(SIZE, BOUNDS, OBSTACLES, lighting="rising")
    screen.blit(floor, (0, 0))
    screen.blit(glow, (0, 0), special_flags=pygame.BLEND_RGB_ADD)

    layer = pygame.Surface(SIZE, pygame.SRCALPHA)
    scene.clear(layer)

    surge = (430.0, 430.0)
    regulator = (850.0, 330.0)
    mite = (690.0, 575.0)
    relay = (1110.0, 560.0)
    relay_target = (930.0, 620.0)
    aim = angle(surge, regulator)

    scene.draw_blink_afterimage(layer, (330.0, 575.0), 0.55)
    scene.draw_arc_trail(layer, (330.0, 575.0), surge, 0.8)
    for distance in (70, 150, 230):
        scene.draw_player_shot(
            layer, (surge[0] + math.cos(aim) * distance, surge[1] + math.sin(aim) * distance), aim
        )
    scene.draw_charge(layer, (520.0, 640.0), "spark", 0.0)
    scene.draw_charge(layer, (585.0, 655.0), "blink", 0.0)

    scene.draw_regulator(
        layer, regulator, "clamp", angle(regulator, surge), angle(regulator, surge), tell=0.65
    )
    scene.draw_aim_tell(layer, mite, angle(mite, surge), 0.7, 15)
    scene.draw_arc_mite(layer, mite, angle(mite, surge))
    scene.draw_relay_destination(layer, relay_target, 0.5)
    scene.draw_relay(layer, relay)
    scene.draw_hostile_bolt(layer, (575.0, 500.0))
    scene.draw_hostile_bolt(layer, (630.0, 530.0))
    scene.draw_surge(layer, surge, aim, ("spark", "blink"), t=0.4)

    screen.blit(layer, (0, 0))
    scene.Bloom(SIZE).apply(screen, layer)

    scene.draw_hud(
        screen,
        scene.HudState(
            charge=4,
            max_charge=6,
            sockets=(("spark", 0.0), ("blink", 0.45)),
            dodge_ready=1.0,
            rival_health=0.72,
            rival_protocol="clamp",
            build_stamp=f"overload {__version__} · style frame",
        ),
    )
    scene.draw_reticle(screen, (812.0, 300.0))
    return screen


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
