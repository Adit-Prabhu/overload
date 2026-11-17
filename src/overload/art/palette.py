"""The only place colors are defined.

Values follow docs/ART_AND_AUDIO_DIRECTION.md section 2. Shared tokens (powers, player
light, danger, UI text) come first, then the pixel art ramps. tests/test_palette.py fails
if a color literal appears anywhere else in src/.
"""

from types import MappingProxyType

TOKENS = MappingProxyType(
    {
        "player.core": "#F5F8FF",
        "player.halo": "#CFE3FF",
        "power.spark": "#FFD23F",
        "power.blink": "#3DE0FF",
        "power.burst": "#FF4FB4",
        "hostile.danger": "#FF3B3B",
        "ui.text": "#E6ECF5",
        "ui.dim": "#7D8AA3",
        "fx.flash": "#FFFFFF",
        "fx.none": "#000000",
        # Pixel art ramps (darkest first). Station materials are cool and dark so that
        # characters, powers and hostile orange read on top of them.
        "px.outline": "#0E111A",
        "px.void": "#07090E",
        "px.floor.0": "#1A2030",
        "px.floor.1": "#232B3D",
        "px.floor.2": "#2C364C",
        "px.floor.3": "#4A5878",
        "px.wall.0": "#1E2535",
        "px.wall.1": "#2F3B53",
        "px.wall.2": "#43526F",
        "px.wall.3": "#647795",
        "px.wall.4": "#93A6C6",
        "px.hazard.0": "#2A2416",
        "px.hazard.1": "#B8912F",
        "px.conduit.0": "#1B3F55",
        "px.conduit.1": "#2C6E9E",
        "px.ceramic.0": "#4E6B78",
        "px.ceramic.1": "#8DB3BE",
        "px.ceramic.2": "#D3EBF0",
        "px.helmet.0": "#7C879E",
        "px.helmet.1": "#B7C1D3",
        "px.helmet.2": "#E9EEF5",
        "px.skin.0": "#9A5E45",
        "px.skin.1": "#D18F6B",
        "px.skin.2": "#F0BE9B",
        "px.goggle.0": "#2B3142",
        "px.goggle.1": "#BFE9F5",
        "px.jacket.0": "#1F5763",
        "px.jacket.1": "#2F8A99",
        "px.jacket.2": "#5CC0C9",
        "px.pack.0": "#2E3446",
        "px.pack.1": "#4A5268",
        "px.pants.0": "#262B3B",
        "px.pants.1": "#3A4157",
        "px.boots.0": "#3A2C22",
        "px.boots.1": "#5A4536",
        "px.bot.0": "#22252F",
        "px.bot.1": "#2C3040",
        "px.bot.2": "#474E63",
        "px.bot.3": "#6A738C",
        "px.hostile.0": "#5A1E18",
        "px.hostile.1": "#8C3326",
        "px.hostile.2": "#D9572B",
        "px.hostile.3": "#FF8A47",
        # Regulator chassis shells (sim/bosses.py): the Transformer's coil brass, the Grid
        # Core's violet.
        "px.coil.0": "#3A2F12",
        "px.coil.1": "#7A6224",
        "px.coil.2": "#C79A2E",
        "px.coil.3": "#F2CB5C",
        "px.core.0": "#24143A",
        "px.core.1": "#4A2A73",
        "px.core.2": "#7E48C2",
        "px.core.3": "#B58CF0",
        # Sector light (multiplied over the scene): sector 1 is untinted, the cooling plant
        # runs cold, the grid core runs hot.
        "px.tint.1": "#FFFFFF",
        "px.tint.2": "#CCE6F2",
        "px.tint.3": "#F5CFDC",
        "px.dial.0": "#C9CED8",
        "px.dial.1": "#F2F4F8",
        "px.spark.light": "#FFF3A6",
        "px.blink.light": "#B5F6FF",
        "px.burst.light": "#FFB3E1",
        "px.concrete.0": "#1D2129",
        "px.concrete.1": "#2A2F39",
        "px.concrete.2": "#353B47",
        "px.concrete.3": "#474E5C",
        "px.wood.0": "#3B2618",
        "px.wood.1": "#62402A",
        "px.wood.2": "#8A5E3C",
        "px.lamp": "#FFB45A",
        "px.lamp.light": "#FFE2B0",
        "px.led.amber": "#FFC247",
        "px.ambient": "#7A84A6",
        "px.tile.0": "#1A1F29",
        "px.tile.1": "#262D3B",
        "px.tile.2": "#2D3546",
        "px.tile.3": "#3B465C",
        "px.paint": "#C9CED8",
    }
)


def rgb(token: str) -> tuple[int, int, int]:
    """Return the RGB triple for a palette token. Unknown tokens raise KeyError."""
    value = TOKENS[token]
    return (int(value[1:3], 16), int(value[3:5], 16), int(value[5:7], 16))


def rgba(token: str, alpha: int) -> tuple[int, int, int, int]:
    """Return a palette token with an alpha channel (0 to 255)."""
    if not 0 <= alpha <= 255:
        raise ValueError(f"alpha out of range: {alpha}")
    return (*rgb(token), alpha)
