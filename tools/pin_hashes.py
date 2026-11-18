"""Print the pinned determinism values, to re-pin them after a change to simulation state,
state_hash or Tuning.

Usage, on both supported Pythons (the values must match):
    uv run python tools/pin_hashes.py
    uv run --isolated --python 3.11 python tools/pin_hashes.py

Then copy each value into the test that pins it (listed in the output), run the full suite
with `-W error` on both Pythons, and say in the PR body why the values changed.
"""

from __future__ import annotations

import platform
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tests"))
sys.path.insert(0, str(ROOT / "src"))

from floorbot import play_campaign  # noqa: E402
from test_powers import full_loop  # noqa: E402
from test_sim import run_all, scripted_inputs  # noqa: E402

from overload.sim.campaign import Campaign  # noqa: E402
from overload.sim.tuning import DEFAULT  # noqa: E402


def values() -> dict[str, str]:
    campaign = Campaign(9)
    play_campaign(campaign)
    return {
        "tests/test_sim.py tuning_id": DEFAULT.tuning_id(),
        "tests/test_sim.py run 21": run_all(21, scripted_inputs(21, 5000)).state_hash(),
        "tests/test_sim.py run 3": run_all(3, scripted_inputs(9, 1200)).state_hash(),
        "tests/test_campaign.py campaign": campaign.state_hash(),
        "tests/test_powers.py full loop": full_loop(2)[1].final_hash,
    }


def main() -> int:
    print(f"Python {platform.python_version()}")
    for where, value in values().items():
        print(f"  {where}: {value}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
