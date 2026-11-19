"""Dev mode: test tools for Adit, never for players or playtesters.

How it stays private:
- It needs both `--dev` on the command line and a file named `.overload-dev` at the
  repository root. That file is git-ignored, so it is never committed, never in a release
  and never on a playtester's machine. Without it, `--dev` refuses to start, and no menu
  item, key or option reaches these tools.
- The code is public, so this is a gate against accidents and curious players, not a
  secret: anyone who reads the source can create the file on their own machine. Nothing
  here touches the rival service, the study data or anyone else's game.

How it stays out of the study:
- A dev run uses the rival's neutral "off" condition (no model call, no spending), writes
  no trace and no recording, and shows DEV on screen, so no dev footage or log can pass
  for real evidence (AGENTS.md: label fixture, replay and live evidence distinctly).
- The tools edit the world between simulation ticks. The simulation itself has no dev
  code, so normal play and replays are unchanged. A retry restores the sector's checkpoint
  as usual, so grants and evolutions made mid-sector are undone by going down.
"""

from __future__ import annotations

from dataclasses import dataclass

from overload.floor import WAVES
from overload.paths import ROOT
from overload.sim import floorplay
from overload.sim.damage import damage_rival
from overload.sim.powers import (
    BASE_POWERS,
    FUSED,
    INGREDIENTS,
    RARITIES,
    owned_result,
    roll_rarity,
)

GATE = ROOT / ".overload-dev"
SPARES = 99  # "unlimited" spare charges, topped up every tick
FORCE = ("ANY", "RARE", "EPIC", "LEGENDARY")
GRANTABLE = tuple(FUSED)


def available() -> bool:
    """True only on a machine where the git-ignored gate file exists."""
    return GATE.is_file()


@dataclass
class DevTools:
    god: bool = True  # the battery refills every tick, so nothing can short the Surge
    charges: bool = True  # every base power stolen, with 99 spare charges each
    no_cooldowns: bool = False
    overlay: bool = True  # tick, room, protocol, position and roll state on screen
    force: int = 0  # index into FORCE: the rarity the next roll lands on
    grant: int = 0  # index into GRANTABLE: the power GRANT POWER gives
    notice: str = ""

    # Every tick ------------------------------------------------------------------------

    def before_tick(self, run) -> None:
        world = run.world
        player = world.player
        if self.god:
            player.charge = run.tuning.player_max_charge
        if self.charges:
            for power in BASE_POWERS:
                if power not in world.unlocked:
                    world.unlocked.append(power)
                world.bank[power] = SPARES
        if self.no_cooldowns:
            player.cooldowns.clear()

    def after_tick(self, run) -> None:
        if self.god:
            run.world.player.charge = run.tuning.player_max_charge

    # The DEV page ----------------------------------------------------------------------

    def rows(self) -> list[tuple[str, str]]:
        """Each row of the DEV page: its label and its current value ("" for actions)."""
        on = {True: "ON", False: "OFF"}
        return [
            ("GOD MODE", on[self.god]),
            ("UNLIMITED CHARGES", on[self.charges]),
            ("NO COOLDOWNS", on[self.no_cooldowns]),
            ("DEBUG OVERLAY", on[self.overlay]),
            ("NEXT ROLL", FORCE[self.force]),
            ("GRANT POWER", GRANTABLE[self.grant].replace("_", " ").upper()),
            ("EVOLVE ALL POWERS", ""),
            ("CLEAR THIS ROOM", ""),
            ("DEFEAT THE REGULATOR", ""),
            ("SKIP THIS SECTOR", ""),
        ]

    def press(self, session, row: int, key: str) -> list:
        """Space toggles or runs a row, left and right cycle NEXT ROLL and GRANT POWER.
        Returns the simulation actions taken, for nothing: dev runs are not recorded."""
        label = self.rows()[row][0]
        step = {"left": -1, "right": 1}.get(key, 0)
        if label == "NEXT ROLL" and step:
            self.force = (self.force + step) % len(FORCE)
        elif label == "GRANT POWER" and step:
            self.grant = (self.grant + step) % len(GRANTABLE)
        if key != "select":
            return []
        campaign = session.campaign
        world = campaign.world
        if label == "GOD MODE":
            self.god = not self.god
        elif label == "UNLIMITED CHARGES":
            self.charges = not self.charges
        elif label == "NO COOLDOWNS":
            self.no_cooldowns = not self.no_cooldowns
        elif label == "DEBUG OVERLAY":
            self.overlay = not self.overlay
        elif label == "NEXT ROLL":
            self.force = (self.force + 1) % len(FORCE)
        elif label == "GRANT POWER":
            self.notice = grant(world, GRANTABLE[self.grant])
        elif label == "EVOLVE ALL POWERS":
            for power in BASE_POWERS:
                if power not in world.unlocked:
                    world.unlocked.append(power)
                evolve_at = campaign.tuning.evolve_at
                world.fragments[power] = max(world.fragments.get(power, 0), evolve_at)
            self.notice = "EVERY BASE POWER EVOLVED"
        elif label == "CLEAR THIS ROOM":
            self.notice = clear_room(world)
        elif label == "DEFEAT THE REGULATOR":
            if world.rival is not None and world.rival.health > 0:
                # A real killing hit, so the death sequence and its banner play as in a fight.
                rival = world.rival
                rival.boot, rival.change, rival.vent, rival.health = 0, 0, 0, 1
                damage_rival(world, 1, rival.x, rival.y)
                self.notice = "REGULATOR DOWN"
            else:
                self.notice = "NO REGULATOR HERE"
        elif label == "SKIP THIS SECTOR":
            self.notice = skip_sector(campaign)
        return []

    def before_roll(self, session, a: str, b: str) -> None:
        """NEXT ROLL: move the run's roll counter to the next fusion that lands on the forced
        rarity. The roll itself is unchanged, it is only aimed at a later draw."""
        if self.force == 0:
            return
        world, tuning = session.campaign.world, session.campaign.tuning
        want = RARITIES[self.force - 1]
        if want == "rare":
            world.streak = 0  # a guaranteed roll is never rare, so clear the guarantee
        guaranteed = world.streak >= tuning.fuse_guarantee_after
        weight = 0 if guaranteed and want == "rare" else tuning.fuse_odds[self.force - 1]
        if weight == 0:  # this tuning can never roll it: leave the roll alone
            self.notice = f"{want.upper()} HAS NO CHANCE IN THIS TUNING"
            return
        n = world.fusions
        while roll_rarity(session.campaign.seed, n, guaranteed, tuning) != want:
            n += 1
        world.fusions = n


def grant(world, power: str) -> str:
    """Give a fused power at once, with its ingredients, replacing its pair's result."""
    for ingredient in INGREDIENTS[power]:
        if ingredient not in world.unlocked:
            world.unlocked.append(ingredient)
    current = owned_result(world.unlocked, *INGREDIENTS[power])
    if current:
        world.unlocked[world.unlocked.index(current)] = power
        world.player.slots = [power if s == current else s for s in world.player.slots]
    else:
        world.unlocked.append(power)
    return f"GRANTED {power.replace('_', ' ').upper()}"


def clear_room(world) -> str:
    """Finish the room the Surge is fighting in: every wave, not only the current one."""
    if not world.active_room:
        return "NOT IN A FIGHT"
    if world.active_room in WAVES:
        world.wave = len(WAVES[world.active_room]) - 1  # no wave left to queue
    for robot in world.hostiles:
        robot.health = 0
    world.warps.clear()
    return "ROOM CLEARED"


def skip_sector(campaign) -> str:
    """Clear the sector's rooms and stand in its Fuse Box. Sector 3 has no Fuse Box: its
    chamber is cleared too, so the run goes to the ending."""
    if campaign.stage != "encounter":
        return "ONLY DURING A SECTOR"
    world = campaign.world
    player = world.player
    # Stop anything that would carry the Surge back: a Meteor in the air, a lance, an aura.
    player.leap, player.dodge_ticks, player.lance, player.aura = 0, 0, False, 0
    floor = campaign.arena.floor
    sector = campaign.encounter
    for room in floor.rooms:
        if room.sector == sector and room.kind in ("combat", "chamber"):
            if room.id not in world.cleared:
                world.cleared = [*world.cleared, room.id]
            floorplay.unlock(world, [d.id for d in floor.doors_of(room.id)])
    world.active_room = ""
    world.hostiles.clear()
    world.warps.clear()
    world.rival = None
    target = f"fuse_{sector}" if sector < 3 else f"s{sector}_chamber"
    world.player.x, world.player.y = floorplay.tile_center(floor.get(target).center)
    return "SKIPPED TO THE FUSE BOX" if sector < 3 else "SKIPPED TO THE ENDING"


def overlay_lines(run, fps: float) -> list[str]:
    world = run.world
    player = world.player
    cooldowns = " ".join(f"{k[0].upper()}{v}" for k, v in sorted(player.cooldowns.items()))
    return [
        f"TICK {world.tick}  FPS {fps:.0f}",
        f"ROOM {world.active_room or '-'}  WAVE {world.wave}",
        f"PROTOCOL {world.protocol}  STAGE {getattr(run, 'stage', '-')}",
        f"POS {player.x:.0f},{player.y:.0f}  CD {cooldowns}",
        f"FUSIONS {world.fusions}  STREAK {world.streak}",
    ]
