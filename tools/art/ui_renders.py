"""Render the review UI images in docs/art/: title, controls, settings, in-play HUD and loadout.

Usage: uv run python tools/art/ui_renders.py [output_dir]
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import pygame  # noqa: E402

from overload.agent.selector import NeutralSelector  # noqa: E402
from overload.art.pixel import hud, tiles  # noqa: E402
from overload.game import dev, menu_view  # noqa: E402
from overload.game import title as title_mod  # noqa: E402
from overload.game.flow import Session  # noqa: E402
from overload.game.menu import HUB_PAUSED, Menu, loadout_rows  # noqa: E402
from overload.game.settings import Settings  # noqa: E402
from overload.game.title import TitleScreen  # noqa: E402
from overload.game.view import VIEW, PixelView  # noqa: E402
from overload.paths import ROOT  # noqa: E402
from overload.sim.campaign import Campaign  # noqa: E402
from overload.sim.powers import BASE_POWERS, COOLDOWN_KEYS  # noqa: E402

SCALE = 3
DEFAULT_DIR = ROOT / "docs" / "art"


def _save(surface: pygame.Surface, path: Path) -> None:
    pygame.image.save(pygame.transform.scale_by(surface, SCALE), str(path))


def main(argv: list[str]) -> int:
    out_dir = Path(argv[1]) if len(argv) > 1 else DEFAULT_DIR
    pygame.init()
    try:
        pygame.display.set_mode((1, 1))
        out_dir.mkdir(parents=True, exist_ok=True)
        screen = pygame.Surface(VIEW)

        # Title, Controls, and Settings pages.
        prefs = Settings(music_volume=80, sfx_volume=70, screen_shake=True, reduce_flash=False)
        title = TitleScreen(settings=prefs)
        title.draw(screen)
        _save(screen, out_dir / "title.png")

        title.page = "controls"
        title.draw(screen)
        _save(screen, out_dir / "title_controls.png")

        title.page = "settings"
        title.draw(screen)
        _save(screen, out_dir / "title_settings.png")

        # In-play HUD in Sector 1 entry with rarity-bordered fused slots and clean stencil.
        campaign = Campaign(1)
        world = campaign.world
        world.unlocked = list(BASE_POWERS)
        world.fragments = {"spark": 3, "blink": 2, "burst": 3, "bulwark": 1, "magnet": 0}
        dev.grant(world, "storm_aura")
        dev.grant(world, "bolt_lance")
        world.player.slots = ["storm_aura", "bolt_lance"]
        world.player.cooldowns[COOLDOWN_KEYS["bolt_lance"]] = 36
        view = PixelView(campaign)
        view.after_tick(campaign)
        view.draw(screen, campaign, (164, 72))
        _save(screen, out_dir / "hud_in_play.png")

        # Loadout screen showing square evolution pips and active inherited evolutions.
        session = Session(campaign, NeutralSelector())
        menu = Menu()
        menu.show(in_fuse_box=False)
        menu.hub = HUB_PAUSED.index("LOADOUT")
        menu.press(session, "select")
        menu.row = loadout_rows(world.unlocked).index("storm_aura")
        menu_view.draw_loadout(screen, menu, session, campaign.tuning)
        _save(screen, out_dir / "hud_loadout.png")
    finally:
        pygame.quit()
        hud.forget()
        tiles.forget_fonts()
        title_mod.forget()
    print(f"wrote UI review renders to {out_dir}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
