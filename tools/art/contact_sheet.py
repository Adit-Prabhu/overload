"""Render the pixel contact sheet: every character frame, pose, prop, tile, effect and icon,
plus color-vision simulations.

Usage (Python 3.12, numpy comes from the tools group):
    uv run --group tools python tools/art/contact_sheet.py [output_dir]

Writes:
- pixel_contact_sheet.png: everything on the floor color at 3x, labeled
- pixel_contact_sheet_cvd.png: grayscale, deuteranopia, protanopia and tritanopia versions

QA checks that every power, enemy and hostile projectile stays distinguishable in all four.
Simulation uses the Machado, Oliveira and Fernandes (2009) matrices at full severity,
applied in linear RGB.
"""

from __future__ import annotations

import math
import os
import sys
from collections.abc import Callable
from pathlib import Path

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import numpy as np  # noqa: E402
import pygame  # noqa: E402

from overload.art.palette import rgb  # noqa: E402
from overload.art.pixel import actors, effects, hud, regulators, robots, tiles  # noqa: E402
from overload.paths import ROOT  # noqa: E402
from overload.rooms import Room  # noqa: E402
from overload.sim.powers import ABILITIES  # noqa: E402

CELL = (128, 68)
COLUMNS = 7
SCALE = 3
DEFAULT_DIR = ROOT / "docs" / "art"

CVD = {
    "deuteranopia": np.array(
        [
            [0.367322, 0.860646, -0.227968],
            [0.280085, 0.672501, 0.047413],
            [-0.011820, 0.042940, 0.968881],
        ]
    ),
    "protanopia": np.array(
        [
            [0.152286, 1.052583, -0.204868],
            [0.114503, 0.786281, 0.099216],
            [-0.003882, -0.048116, 1.051998],
        ]
    ),
    "tritanopia": np.array(
        [
            [1.255528, -0.076749, -0.178779],
            [-0.078411, 0.930809, 0.147602],
            [0.004733, 0.691367, 0.303900],
        ]
    ),
}

SAMPLER = Room(
    name="tile sampler",
    terrain=(
        "########",
        "########",
        "#..==g,#",
        "#hh==g-#",
        "#hh..|.#",
        "########",
    ),
    decor=(
        "........",
        ".PLSVMp.",
        "..o.....",
        ".x..d...",
        "...cb...",
        "........",
    ),
)

Draw = Callable[[pygame.Surface, tuple[int, int]], None]


def centered(image: pygame.Surface) -> Draw:
    bounds = image.get_bounding_rect()
    if bounds.w > 0 and bounds.h > 0:
        image = image.subsurface(bounds).copy()
    max_w, max_h = CELL[0] - 8, CELL[1] - 18
    w, h = image.get_size()
    if w > max_w or h > max_h:
        divisor = max(2, math.ceil(max(w / max_w, h / max_h)))
        image = pygame.transform.scale(image, (max(1, w // divisor), max(1, h // divisor)))
    return lambda target, c: target.blit(image, image.get_rect(center=c))


def boss_chassis_items() -> list[tuple[str, pygame.Surface]]:
    """Three Regulator chassis rendered at true 1:1 native pixel scale in a taller strip."""
    return [
        ("linesman", regulators.regulator("clamp", False, -0.6, kind="linesman")),
        ("transformer", regulators.regulator("insulate", False, -0.6, kind="transformer")),
        ("grid core", regulators.regulator("oscillate", False, -0.6, kind="grid_core")),
    ]


def items() -> list[tuple[str, Draw]]:
    frames = actors.surge_frames()
    entries: list[tuple[str, Draw]] = []
    for i, image in enumerate(frames["idle"]):
        entries.append((f"surge idle {i + 1}", centered(image)))
    for i, image in enumerate(frames["walk"]):
        entries.append((f"surge walk {i + 1}", centered(image)))
    entries.append(("surge sockets", centered(actors.surge("idle", 0, False, ("spark", "blink")))))
    entries.append(("caster", centered(actors.caster())))
    entries.append(("app icon", centered(actors.app_icon())))
    # Maintenance robot roster (art/pixel/robots.py). Regulator chassis sit in their own 1:1 row.
    entries += [
        ("arc drone", centered(robots.drone(0, False))),
        ("relay bot", centered(robots.relay_bot(False))),
        ("breaker", centered(robots.breaker(False))),
        ("sweeper", centered(robots.sweeper(0, False))),
        ("sentry", centered(robots.sentry(False))),
    ]
    for protocol in ("clamp", "insulate", "oscillate"):
        entries.append((f"reg {protocol}", centered(actors.regulator(protocol, False, -2.4))))
    entries.append(("reg volley tell", centered(actors.regulator("oscillate", False, -2.4, True))))
    for name, image in (
        ("transformer prop", tiles.transformer()),
        ("cabinet", tiles.cabinet()),
        ("insulator", tiles.insulator()),
        ("cable reel", tiles.cable_reel()),
        ("crate", tiles.crate()),
        ("drum", tiles.drum()),
    ):
        entries.append((name, centered(image)))
    for power in ABILITIES:  # every power's icon, fused ones included
        entries.append((f"{power} icon".replace("_", " "), centered(effects.charge_icon(power))))
    for protocol in ("clamp", "insulate", "oscillate"):
        entries.append((f"{protocol} icon", centered(effects.protocol_icon(protocol))))

    def scratch() -> pygame.Surface:
        return pygame.Surface(CELL)

    entries += [
        ("hostile bolt", centered(effects.hostile_bolt())),
        ("shard", centered(robots.shard())),
        ("shell", centered(robots.shell())),
        ("needle dart", centered(robots.needle_dart())),
        ("orb", centered(robots.orb())),
        ("player shot", lambda t, c: effects.player_shot(t, scratch(), c, 0.0)),
        ("spark shot", lambda t, c: effects.spark_shot(t, scratch(), c, 0.0)),
        (
            "arc trail",
            lambda t, c: effects.arc_trail(
                t, scratch(), (c[0] - 22, c[1] + 12), (c[0] + 22, c[1] - 12), 1.0
            ),
        ),
        ("blink ghost", lambda t, c: effects.blink_ghost(t, scratch(), c)),
        (
            "aim tell",
            lambda t, c: effects.aim_tell(t, scratch(), (c[0] - 22, c[1]), 0.0, 0.7, reach=40),
        ),
        ("relay target", lambda t, c: effects.relay_destination(t, c, 0.6)),
        ("relay arming", centered(robots.relay_bot(False, arming=True))),
        ("fusion rings", lambda t, c: effects.fusion_rings(t, c, 0.7)),
        ("hazard tile", lambda t, c: effects.hazard_tile(t, scratch(), (c[0] - 8, c[1] - 8), 0.7)),
        ("reticle", centered(effects.reticle())),
        ("blast ring", lambda t, c: effects.blast_ring(t, scratch(), c, 18, 0.4)),
        ("shock mine", lambda t, c: effects.mine(t, scratch(), c, 0.5)),
        ("storm aura", lambda t, c: effects.aura(t, scratch(), c, 6)),
        ("meteor marker", lambda t, c: effects.landing_marker(t, c, 16, 0.6)),
        ("bolt lance", lambda t, c: effects.lance_streak(t, scratch(), c, 1.0, 0.0)),
    ]
    return entries


def render_sheet() -> pygame.Surface:
    entries = items()
    chassis = boss_chassis_items()
    rows = math.ceil(len(entries) / COLUMNS)
    boss_h = 112
    sampler = tiles.render_room(SAMPLER)
    room_h = sampler.background.get_height() + 20
    w, h = COLUMNS * CELL[0], rows * CELL[1] + boss_h + room_h
    sheet = pygame.Surface((w, h))
    sheet.fill(rgb("px.floor.1"))
    for i, (label, draw) in enumerate(entries):
        x, y = (i % COLUMNS) * CELL[0], (i // COLUMNS) * CELL[1]
        pygame.draw.rect(sheet, rgb("px.floor.0"), (x, y, *CELL), 1)
        draw(sheet, (x + CELL[0] // 2, y + CELL[1] // 2 - 5))
        hud.text(sheet, label, (x + CELL[0] // 2, y + CELL[1] - 2), "ui.dim", "midbottom")
    boss_top = rows * CELL[1]
    boss_cell_w = CELL[0]
    for i, (label, image) in enumerate(chassis):
        x = i * boss_cell_w
        pygame.draw.rect(sheet, rgb("px.floor.0"), (x, boss_top, boss_cell_w, boss_h), 1)
        bounds = image.get_bounding_rect()
        cropped = image.subsurface(bounds) if bounds.w > 0 and bounds.h > 0 else image
        rect = cropped.get_rect(center=(x + boss_cell_w // 2, boss_top + (boss_h - 14) // 2 + 2))
        sheet.blit(cropped, rect)
        hud.text(sheet, label, (x + boss_cell_w // 2, boss_top + boss_h - 2), "ui.dim", "midbottom")
    top = boss_top + boss_h
    hud.text(sheet, "tile sampler", (4, top + 4), "ui.text")
    background = sampler.background.copy()
    for prop in sampler.props:
        prop.draw(background, (0, 0))
    sheet.blit(background, (4, top + 16))
    return pygame.transform.scale_by(sheet, SCALE)


def _to_linear(c: np.ndarray) -> np.ndarray:
    return np.where(c <= 0.04045, c / 12.92, ((c + 0.055) / 1.055) ** 2.4)


def _to_srgb(c: np.ndarray) -> np.ndarray:
    c = np.clip(c, 0.0, 1.0)
    return np.where(c <= 0.0031308, c * 12.92, 1.055 * c ** (1 / 2.4) - 0.055)


def simulate(surface: pygame.Surface, mode: str) -> pygame.Surface:
    pixels = pygame.surfarray.array3d(surface).astype(np.float64) / 255.0
    linear = _to_linear(pixels)
    if mode == "grayscale":
        luma = linear @ np.array([0.2126, 0.7152, 0.0722])
        out = np.repeat(luma[..., None], 3, axis=2)
    else:
        out = linear @ CVD[mode].T
    result = (_to_srgb(out) * 255.0 + 0.5).astype(np.uint8)
    return pygame.surfarray.make_surface(result)


def render_cvd(sheet: pygame.Surface) -> pygame.Surface:
    small = pygame.transform.scale_by(sheet, 2 / SCALE)
    w, h = small.get_size()
    label_h = 14
    out = pygame.Surface((w * 2, (h + label_h) * 2))
    out.fill(rgb("px.void"))
    for i, mode in enumerate(("grayscale", "deuteranopia", "protanopia", "tritanopia")):
        x, y = (i % 2) * w, (i // 2) * (h + label_h)
        hud.text(out, mode.upper(), (x + 4, y + 3), "ui.text")
        out.blit(simulate(small, mode), (x, y + label_h))
    return out


def main(argv: list[str]) -> int:
    out_dir = Path(argv[1]) if len(argv) > 1 else DEFAULT_DIR
    pygame.init()
    try:
        out_dir.mkdir(parents=True, exist_ok=True)
        sheet = render_sheet()
        pygame.image.save(sheet, str(out_dir / "pixel_contact_sheet.png"))
        pygame.image.save(render_cvd(sheet), str(out_dir / "pixel_contact_sheet_cvd.png"))
    finally:
        pygame.quit()
        hud.forget()
        tiles.forget_fonts()
    print(f"wrote pixel_contact_sheet.png and pixel_contact_sheet_cvd.png to {out_dir}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
