"""Render the robot roster style frame (overhaul, Nov 17) for Adit's approval: every robot
next to the Surge for scale, the Regulator's three chassis (each in one of the protocols),
and one hostile shot shape per attacker.

Usage: uv run python tools/art/robot_style_frame.py docs/art/robot_style_frame.png
"""

from __future__ import annotations

import os
import sys

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")

import pygame  # noqa: E402

from overload.art.palette import rgb  # noqa: E402
from overload.art.pixel import actors, effects, hud, regulators, robots  # noqa: E402

SIZE = (320, 160)


def main(argv: list[str]) -> int:
    out = argv[0] if argv else "docs/art/robot_style_frame.png"
    pygame.init()
    pygame.display.set_mode((10, 10))
    sheet = pygame.Surface(SIZE)
    sheet.fill(rgb("px.floor.1"))
    for x in range(0, SIZE[0], 16):
        for y in range(0, SIZE[1], 16):
            if (x // 16 + y // 16) % 2:
                sheet.fill(rgb("px.floor.2"), (x, y, 16, 16))

    def put(image: pygame.Surface, cx: int, feet: int, label: str = "") -> None:
        sheet.blit(image, (cx - image.get_width() // 2, feet - image.get_height()))
        if label:
            hud.text(sheet, label, (cx, feet + 3), "ui.text", "midtop")

    put(actors.surge("idle", 0, False), 14, 56, "SURGE")
    put(robots.drone(0, False), 50, 56, "DRONE")
    put(robots.relay_bot(False), 92, 56, "RELAY")
    put(robots.breaker(False), 140, 56, "BREAKER")
    put(robots.breaker(False, raising=True), 172, 56)
    put(robots.sweeper(0, False), 214, 56, "SWEEPER")
    put(robots.sentry(False), 258, 56, "SENTRY")
    for i, (kind, protocol) in enumerate(
        zip(regulators.KINDS, ("clamp", "insulate", "oscillate"), strict=True)
    ):
        image = regulators.regulator(protocol, False, -0.6, kind=kind)
        put(image, 38 + i * 72, 140, kind.replace("_", " ").upper())
    shots = (effects.hostile_bolt(), robots.shard(), robots.shell(), robots.needle_dart())
    for i, image in enumerate((*shots, robots.orb())):
        x, y = 236 + (i % 3) * 26, 84 + (i // 3) * 22
        sheet.blit(image, (x - image.get_width() // 2, y))
    robots.shockwave(sheet, (280, 136), 12)
    pygame.image.save(pygame.transform.scale_by(sheet, 4), out)
    pygame.quit()
    print(f"wrote {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
