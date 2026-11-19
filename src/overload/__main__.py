"""Entry point: `uv run overload`.

Controls: WASD or arrows move, mouse aims, hold left click to fire, Space dodges,
R retries after going down, Enter continues from the Fuse Box, Esc quits.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from overload.game.app import Options, play
from overload.sim.difficulty import DIFFICULTIES


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
    parser.add_argument(
        "--practice", action="store_true", help="Practice arena: two Arc Drones, no Regulator."
    )
    parser.add_argument(
        "--condition",
        choices=("live", "fixed", "off"),
        help="Rival condition. Default: live when OVERLOAD_RIVAL_URL is set, otherwise off.",
    )
    parser.add_argument(
        "--schedule", choices=("A", "B"), default="A", help="Order for the fixed condition."
    )
    parser.add_argument("--trace", type=Path, help="Write the session trace to this file.")
    parser.add_argument(
        "--mute", action="store_true", help="No sound. The game is fully playable muted."
    )
    parser.add_argument(
        "--difficulty",
        choices=DIFFICULTIES,
        default="medium",
        help="Starting difficulty (default Medium). Replays use the recorded difficulty.",
    )
    parser.add_argument("--skip-title", action="store_true", help="Start playing at once.")
    # Test tools for the developer, deliberately left out of --help (game/dev.py).
    parser.add_argument("--dev", action="store_true", help=argparse.SUPPRESS)
    args = parser.parse_args(argv)
    return Options(
        seed=args.seed,
        difficulty=args.difficulty,
        headless=args.headless,
        frames=args.frames,
        record=args.record,
        replay=args.replay,
        practice=args.practice,
        condition=args.condition,
        schedule=args.schedule,
        trace=args.trace,
        mute=args.mute,
        skip_title=args.skip_title,
        dev=args.dev,
    )


def main(argv: list[str] | None = None) -> int:
    return play(parse_args(argv))


if __name__ == "__main__":
    sys.exit(main())
