"""The only place colors are defined.

Values follow docs/ART_AND_AUDIO_DIRECTION.md section 2 and stay provisional until
they pass the contrast and color-vision check. tests/test_palette.py fails if a color
literal appears anywhere else in src/.
"""

from types import MappingProxyType

TOKENS = MappingProxyType(
    {
        "bg.void": "#0A0E17",
        "bg.trace": "#16233A",
        "bg.trace_lit": "#24406B",
        "wall.busbar": "#5B7BA8",
        "player.core": "#F5F8FF",
        "player.halo": "#CFE3FF",
        "power.spark": "#FFD23F",
        "power.blink": "#3DE0FF",
        "power.burst": "#FF4FB4",
        "hostile.line": "#FF6B35",
        "hostile.danger": "#FF3B3B",
        "rival.body": "#1C1F2B",
        "ui.text": "#E6ECF5",
        "ui.dim": "#7D8AA3",
        "fx.flash": "#FFFFFF",
    }
)


def rgb(token: str) -> tuple[int, int, int]:
    """Return the RGB triple for a palette token. Unknown tokens raise KeyError."""
    value = TOKENS[token]
    return (int(value[1:3], 16), int(value[3:5], 16), int(value[5:7], 16))
