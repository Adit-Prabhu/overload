"""Render the three chassis phases in their chambers and the victory sequence.

Usage: uv run python tools/art/boss_review.py [output_dir]
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import pygame  # noqa: E402

from overload.art.palette import rgb  # noqa: E402
from overload.art.pixel import hud  # noqa: E402
from overload.game.view import VIEW, WRECK_TICKS, PixelView  # noqa: E402
from overload.sim import floorplay  # noqa: E402
from overload.sim.campaign import Campaign  # noqa: E402
from overload.sim.inputs import IDLE  # noqa: E402
from overload.sim.state import Projectile  # noqa: E402


def chamber(sector: int, protocol: str) -> tuple[Campaign, PixelView]:
    campaign = Campaign(1)
    campaign.encounter = campaign.world.encounter = sector
    campaign.world.protocol = protocol
    room = campaign.arena.floor.get(f"s{sector}_chamber")
    player = campaign.world.player
    player.x, player.y = floorplay.tile_center(room.center)
    campaign.step(IDLE)
    rival = campaign.world.rival
    player.x, player.y = rival.x - 65, rival.y + 26
    view = PixelView(campaign)
    for _ in range(80):
        view.follow(campaign, (128, 72))
    view.sector = sector
    view.tint = list(rgb(f"px.tint.{sector}"))
    return campaign, view


def shot(campaign: Campaign, view: PixelView) -> pygame.Surface:
    screen = pygame.Surface(VIEW)
    view.draw(screen, campaign, (197, 82))
    view.draw_campaign_ending(screen, campaign)
    return screen


def reach_phase(campaign: Campaign, view: PixelView, phase: int) -> None:
    """Cross a breakpoint with a projectile, then capture the actual phase transition."""
    rival = campaign.world.rival
    player = campaign.world.player
    player.invulnerable = 1000
    for _ in range(campaign.tuning.phase_change + 2):
        if not rival.change:
            break
        campaign.step(IDLE)
        view.update(campaign, (197, 82))
    target = rival.max_health * (4 - phase) // 3
    campaign.world.projectiles.append(
        Projectile(
            campaign.world.new_id(), rival.x, rival.y, 0, 0, 1, rival.health - target, False, 5
        )
    )
    for _ in range(24):
        campaign.step(IDLE)
        view.update(campaign, (197, 82))
    assert rival.phase == phase and rival.change > 0


def main(output: Path) -> None:
    pygame.init()
    pygame.display.set_mode((1, 1))
    output.mkdir(parents=True, exist_ok=True)
    width, height = VIEW
    pitch_x, pitch_y = width + 6, height + 28
    sheet = pygame.Surface((3 * pitch_x + 6, 3 * pitch_y + 6))
    sheet.fill(rgb("px.outline"))
    protocols = ("pressure", "spacing", "lateral")
    for sector, protocol in enumerate(protocols, 1):
        campaign, view = chamber(sector, protocol)
        rival = campaign.world.rival
        rival.boot = campaign.tuning.rival_boot // 2
        if sector == 1:
            pygame.image.save(
                pygame.transform.scale_by(shot(campaign, view), 3), output / "boss_entrance.png"
            )
        rival.boot = 0
        for phase in range(1, 4):
            if phase > 1:
                reach_phase(campaign, view, phase)
            screen = shot(campaign, view)
            x, y = 6 + (phase - 1) * pitch_x, 6 + (sector - 1) * pitch_y
            sheet.blit(screen, (x, y + 15))
            hud.text(
                sheet,
                f"{rival.kind.upper().replace('_', ' ')} / PHASE {phase}",
                (x + 5, y),
                "ui.text",
            )
            if (sector, phase) == (2, 3):
                pygame.image.save(pygame.transform.scale_by(screen, 3), output / "boss_in_play.png")
    pygame.image.save(pygame.transform.scale_by(sheet, 2), output / "bosses.png")

    campaign, view = chamber(3, "lateral")
    rival = campaign.world.rival
    rival.boot, rival.phase, rival.health = 0, 3, 1
    view.after_tick(campaign)
    campaign.world.projectiles.append(Projectile(101, rival.x, rival.y, 0, 0, 1, 1, False, 5))
    campaign.step(IDLE)
    view.after_tick(campaign)
    assert campaign.stage == "ending" and view.wreck is not None
    for _ in range(WRECK_TICKS + 5):
        view.advance_defeat()
    pygame.image.save(pygame.transform.scale_by(shot(campaign, view), 3), output / "boss_down.png")
    pygame.quit()


if __name__ == "__main__":
    main(Path(sys.argv[1]) if len(sys.argv) > 1 else Path("docs/art"))
