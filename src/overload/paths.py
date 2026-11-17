"""Filesystem locations. The game runs from the repository checkout."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
ASSETS = ROOT / "assets"
FONTS = ASSETS / "fonts"
