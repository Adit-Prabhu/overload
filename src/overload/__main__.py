"""Entry point: `uv run overload`.

Controls: WASD or arrows move, mouse aims, hold left click to fire, Space dodges,
R retries after going down or clearing, Esc quits.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from overload.game.app import Options, play


def parse_args(argv: list[str] | None) -> Options:
    parser = argparse.ArgumentParser(prog="overload", description="Run Overload.")
    parser.add_argument("--seed", type=int, default=1, help="Simulation seed (default 1).")
    parser.add_argument(
        "--headless",
        action="store_true",
        help="Use SDL dummy video and audio drivers and step one tick per frame (CI).",
    )
    parser.add_argument(
        "--frames", type=int, default=0, help="Quit after this many frames. 0 runs until closed."
    )
    parser.add_argument(
        "--record", type=Path, help="Save this session's inputs as a replay file on exit."
    )
    parser.add_argument(
        "--replay", type=Path, help="Play back a replay file and check its final state hash."
    )
    args = parser.parse_args(argv)
    return Options(
        seed=args.seed,
        headless=args.headless,
        frames=args.frames,
        record=args.record,
        replay=args.replay,
    )


def main(argv: list[str] | None = None) -> int:
    return play(parse_args(argv))


if __name__ == "__main__":
    sys.exit(main())
