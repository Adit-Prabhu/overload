"""The balance pass (docs/POWERS_AND_FUSION.md section 5 and section 9 step 8): measure the
current Tuning with the floor bot and print the numbers the freeze is judged on.

Usage:
    uv run python tools/balance.py [--seeds 8] [--fight-seeds 2] [--difficulty medium]

1. Campaign: the bot plays the whole floor on each seed, with the protocol order rotated
   so every protocol is met. Prints retries per sector and each chassis' fight time.
   Criterion: sectors 1 and 2 keep their retry rate, sector 3 near one retry a run.
2. Protocol check: in each chamber, under each protocol, the bot fights the chassis with
   a fused power in Q and its pair's first base power in E, against the loadout the player
   had before fusing: both base powers. (A pair can only be fused once both are owned, so
   that is what "without" means in play. A gun-only baseline is printed for reference.)
   The Surge cannot be hurt, so the time is the time to kill. Criterion: fusing never cuts
   a protocol's fight time below 0.70 of the time without. The spread of each power's
   ratio across the three protocols is printed too, so a power that helps against one
   protocol far more than the others shows. Shield and pull results deal no damage, and
   their own check (hits taken) is in tests/test_blink_and_guard_fusions.py.

Deterministic: the same Tuning gives the same numbers on every run.
"""

from __future__ import annotations

import argparse
import statistics
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tests"))
sys.path.insert(0, str(ROOT / "src"))

from floorbot import FloorBot, enter  # noqa: E402

from overload.sim.campaign import Campaign  # noqa: E402
from overload.sim.difficulty import PRESETS  # noqa: E402
from overload.sim.inputs import InputFrame  # noqa: E402
from overload.sim.powers import FUSED, INGREDIENTS  # noqa: E402

PROTOCOLS = ("pressure", "spacing", "lateral")
ORDERS = (("pressure", "spacing"), ("spacing", "lateral"), ("lateral", "pressure"))
FIGHT_LIMIT = 30_000
CAMPAIGN_LIMIT = 150_000
FLOOR = 0.70


def campaign_run(seed: int, tuning) -> dict:
    """One bot run of the whole floor: retries and boss fight ticks per sector."""
    campaign = Campaign(seed, tuning)
    bot = FloorBot(campaign)
    order = iter(ORDERS[seed % len(ORDERS)])
    for tick in range(CAMPAIGN_LIMIT):
        if campaign.stage == "fuse_box":
            campaign.begin_next(next(order))
        if campaign.stage == "ending":
            break
        frame = bot.frame(tick)
        if campaign.world.outcome == "down":
            frame = InputFrame(restart=True)
        campaign.step(frame)
    return {
        "done": campaign.stage == "ending",
        "ticks": campaign.stats["ticks"],
        "retries": dict(campaign.retries),
        "bosses": {int(k): v for k, v in campaign.stats["bosses"].items()},
        "reached": campaign.encounter,
    }


def fight(seed: int, sector: int, protocol: str, slots: tuple[str, str], tuning) -> int:
    """Ticks for the bot to beat this sector's chassis with these two slots."""
    campaign = Campaign(seed, tuning)
    campaign.encounter = campaign.world.encounter = sector
    campaign.protocols[sector] = campaign.world.protocol = protocol
    world = campaign.world
    owned = {s for s in slots if s}
    for power in list(owned):
        owned |= set(INGREDIENTS.get(power, ()))
    world.unlocked = sorted(owned)
    world.player.slots = list(slots)
    enter(campaign, f"s{sector}_chamber")
    bot = FloorBot(campaign)
    for tick in range(FIGHT_LIMIT):
        world.player.invulnerable = 10**9
        rival = world.rival
        if rival is None or rival.health <= 0:
            return tick
        campaign.step(bot.frame(tick))
    return FIGHT_LIMIT


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--seeds", type=int, default=8)
    parser.add_argument("--fight-seeds", type=int, default=2)
    parser.add_argument("--difficulty", default="medium")
    parser.add_argument("--skip-campaign", action="store_true")
    parser.add_argument("--skip-fights", action="store_true")
    args = parser.parse_args()
    tuning = PRESETS[args.difficulty]
    print(f"tuning_id {tuning.tuning_id()} ({args.difficulty})")
    ok = True

    if not args.skip_campaign:
        print(f"\n1. Campaign, {args.seeds} seeds")
        runs = []
        for seed in range(1, args.seeds + 1):
            run = campaign_run(seed, tuning)
            runs.append(run)
            bosses = " ".join(f"s{k}:{v / 60:.0f}s" for k, v in sorted(run["bosses"].items()))
            retries = " ".join(f"s{k}:{v}" for k, v in sorted(run["retries"].items()))
            state = "done" if run["done"] else f"STUCK in sector {run['reached']}"
            print(f"  seed {seed}: {state}, {run['ticks'] / 60:.0f}s, retries {retries}, {bosses}")
        for sector in (1, 2, 3):
            values = [r["retries"].get(sector, 0) for r in runs]
            fights = [r["bosses"][sector] / 60 for r in runs if sector in r["bosses"]]
            mean_fight = statistics.mean(fights) if fights else float("nan")
            print(
                f"  sector {sector}: {statistics.mean(values):.2f} retries a run "
                f"(max {max(values)}), chassis fight {mean_fight:.1f}s mean"
            )
        stuck = [i + 1 for i, r in enumerate(runs) if not r["done"]]
        if stuck:
            print(f"  STUCK seeds: {stuck}")
            ok = False

    if not args.skip_fights:
        seeds = range(1, args.fight_seeds + 1)
        print(f"\n2. Protocol check, fused (Q) + first base (E) / both bases, {len(seeds)} seeds")

        def timed(sector, protocol, slots):
            return statistics.mean(fight(s, sector, protocol, slots, tuning) for s in seeds)

        worst = (9.0, "")
        spread = {}
        for sector in (1, 2, 3):
            for protocol in PROTOCOLS:
                gun = timed(sector, protocol, ("", ""))
                bases = {}
                ratios = {}
                for power, ((a, b), _) in FUSED.items():
                    if (a, b) not in bases:
                        bases[(a, b)] = timed(sector, protocol, (a, b))
                    ratios[power] = timed(sector, protocol, (power, a)) / bases[(a, b)]
                    spread.setdefault((sector, power), []).append(ratios[power])
                low = sorted(ratios.items(), key=lambda kv: kv[1])[:3]
                text = ", ".join(f"{p} {r:.2f}" for p, r in low)
                print(f"  s{sector} {protocol:8} gun only {gun / 60:5.1f}s, lowest: {text}")
                for power, ratio in ratios.items():
                    if ratio < worst[0]:
                        worst = (ratio, f"{power} in s{sector} {protocol}")
                    if ratio < FLOOR:
                        print(f"    BELOW {FLOOR}: {power} {ratio:.2f}")
                        ok = False
        print(f"  worst: {worst[1]} at {worst[0]:.2f}")
        skew = sorted(((max(r) - min(r), key) for key, r in spread.items()), reverse=True)[:5]
        print("  widest spread across protocols (max - min ratio):")
        for gap, (sector, power) in skew:
            values = " ".join(f"{v:.2f}" for v in spread[(sector, power)])
            print(f"    s{sector} {power}: {gap:.2f} ({values}, pressure spacing lateral)")
    print("\nPASS" if ok else "\nFAIL")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
