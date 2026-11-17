"""Render the contact sheet: every sprite and effect, plus color-vision simulations.

Usage (Python 3.12, numpy comes from the tools group):
    uv run --group tools python tools/art/contact_sheet.py [output_dir]

Writes three files:
- contact_sheet.png: every item at 1x on the real floor color
- contact_sheet_2x.png: the same sheet at 2x, every item included
- contact_sheet_cvd.png: grayscale, deuteranopia, protanopia and tritanopia versions

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

from overload.art import scene, sprites  # noqa: E402
from overload.art.fonts import font  # noqa: E402
from overload.art.palette import rgb  # noqa: E402
from overload.paths import ROOT  # noqa: E402

CELL = 150
COLUMNS = 8
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

Draw = Callable[[pygame.Surface, tuple[float, float]], None]


def items() -> list[tuple[str, Draw]]:
    """Everything the player can see, drawn centered in a cell."""

    def sprite(s: sprites.Sprite, angle: float = 0.0) -> Draw:
        return lambda layer, c: s.draw(layer, c, angle)

    def regulator(protocol: str) -> Draw:
        return lambda layer, c: scene.draw_regulator(layer, c, protocol, 0.0, -0.6, 0.6)

    entries: list[tuple[str, Draw]] = [
        ("Surge", lambda layer, c: scene.draw_surge(layer, c, -0.5, ("spark", "blink"), 0.3)),
        ("Surge dodge", lambda layer, c: scene.draw_surge(layer, c, -0.5, invulnerable=True)),
        ("Arc Mite", sprite(sprites.arc_mite())),
        ("Relay", sprite(sprites.relay())),
        ("Regulator Clamp", regulator("clamp")),
        ("Regulator Insulate", regulator("insulate")),
        ("Regulator Oscillate", regulator("oscillate")),
        ("Aim tell", lambda layer, c: scene.draw_aim_tell(layer, (c[0] - 50, c[1]), 0.0, 0.7, 15)),
    ]
    for power in sprites.POWER_TOKENS:
        entries.append((f"{power.title()} icon", sprite(sprites.power_icon(power, 14))))
    for power in sprites.POWER_TOKENS:
        entries.append((f"{power.title()} charge", sprite(sprites.charge(power))))
    entries += [
        ("Player shot", lambda layer, c: scene.draw_player_shot(layer, c, 0.0)),
        ("Hostile bolt", lambda layer, c: scene.draw_hostile_bolt(layer, c)),
        (
            "Arc Trail",
            lambda layer, c: scene.draw_arc_trail(
                layer, (c[0] - 50, c[1] + 30), (c[0] + 50, c[1] - 30), 0.9
            ),
        ),
        ("Blink afterimage", lambda layer, c: scene.draw_blink_afterimage(layer, c, 0.6)),
        ("Relay destination", lambda layer, c: scene.draw_relay_destination(layer, c, 0.6)),
        ("Hazard tile", lambda layer, c: scene.draw_hazard_tile(layer, c, 26, 0.7)),
    ]
    for protocol in sprites.PROTOCOLS:
        entries.append((f"{protocol.title()} icon", sprite(sprites.protocol_icon(protocol, 12))))
    entries.append(
        (
            "Dodge streak",
            lambda layer, c: scene.draw_dodge_streak(layer, (c[0] - 40, c[1]), (c[0] + 40, c[1])),
        )
    )
    return entries


def render_sheet(scale: int) -> pygame.Surface:
    entries = items()
    rows = math.ceil(len(entries) / COLUMNS)
    size = (COLUMNS * CELL, rows * CELL)
    layer = pygame.Surface(size, pygame.SRCALPHA)
    scene.clear(layer)
    for i, (_, draw) in enumerate(entries):
        cx = (i % COLUMNS) * CELL + CELL / 2
        cy = (i // COLUMNS) * CELL + CELL / 2 - 8
        draw(layer, (cx, cy))
    sheet = pygame.Surface(size)
    sheet.fill(rgb("bg.void"))
    for i in range(len(entries)):
        x, y = (i % COLUMNS) * CELL, (i // COLUMNS) * CELL
        pygame.draw.rect(sheet, rgb("bg.trace"), (x, y, CELL, CELL), 1)
    sheet.blit(layer, (0, 0))
    scene.Bloom(size).apply(sheet, layer)
    for i, (label, _) in enumerate(entries):
        text = font(13).render(label, True, rgb("ui.dim"))
        x, y = (i % COLUMNS) * CELL, (i // COLUMNS) * CELL
        sheet.blit(text, text.get_rect(midbottom=(x + CELL / 2, y + CELL - 6)))
    if scale != 1:
        sheet = pygame.transform.scale_by(sheet, scale)
    return sheet


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
    w, h = sheet.get_size()
    label_h = 30
    modes = ["grayscale", "deuteranopia", "protanopia", "tritanopia"]
    out = pygame.Surface((w * 2, (h + label_h) * 2))
    out.fill(rgb("bg.void"))
    for i, mode in enumerate(modes):
        x, y = (i % 2) * w, (i // 2) * (h + label_h)
        title = font(18, "bold").render(mode.upper(), True, rgb("ui.text"))
        out.blit(title, (x + 12, y + 6))
        out.blit(simulate(sheet, mode), (x, y + label_h))
    return out


def main(argv: list[str]) -> int:
    out_dir = Path(argv[1]) if len(argv) > 1 else DEFAULT_DIR
    pygame.init()
    try:
        out_dir.mkdir(parents=True, exist_ok=True)
        base = render_sheet(1)
        pygame.image.save(base, str(out_dir / "contact_sheet.png"))
        pygame.image.save(render_sheet(2), str(out_dir / "contact_sheet_2x.png"))
        pygame.image.save(render_cvd(base), str(out_dir / "contact_sheet_cvd.png"))
    finally:
        pygame.quit()
    print(f"wrote contact_sheet.png, contact_sheet_2x.png and contact_sheet_cvd.png to {out_dir}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
