"""Entry point: `uv run overload`.

Scaffold only. Opens the game window on the substation background with the build stamp.
Gameplay arrives with the simulation core (implementation plan task 3).
"""

from __future__ import annotations

import argparse
import os
import sys

from overload import __version__
from overload.art.palette import rgb

WIDTH, HEIGHT = 1280, 720
FPS = 60


def parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(prog="overload", description="Run Overload.")
    parser.add_argument(
        "--headless",
        action="store_true",
        help="Use SDL dummy video and audio drivers (CI and smoke tests).",
    )
    parser.add_argument(
        "--frames",
        type=int,
        default=0,
        help="Quit after this many frames. 0 runs until the window is closed.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    if args.headless:
        os.environ["SDL_VIDEODRIVER"] = "dummy"
        os.environ["SDL_AUDIODRIVER"] = "dummy"

    import pygame

    pygame.init()
    try:
        # The dummy driver has no hardware renderer, so SCALED would only warn and fall back.
        flags = 0 if args.headless else pygame.SCALED | pygame.RESIZABLE
        screen = pygame.display.set_mode((WIDTH, HEIGHT), flags)
        pygame.display.set_caption("Overload")
        font = pygame.font.Font(None, 22)
        stamp = font.render(f"overload {__version__} · scaffold", True, rgb("ui.dim"))
        clock = pygame.time.Clock()

        frame = 0
        running = True
        while running:
            for event in pygame.event.get():
                if event.type == pygame.QUIT or (
                    event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE
                ):
                    running = False
            screen.fill(rgb("bg.void"))
            screen.blit(stamp, (12, HEIGHT - stamp.get_height() - 8))
            pygame.display.flip()
            clock.tick(FPS)
            frame += 1
            if args.frames and frame >= args.frames:
                running = False
    finally:
        pygame.quit()
    return 0


if __name__ == "__main__":
    sys.exit(main())
