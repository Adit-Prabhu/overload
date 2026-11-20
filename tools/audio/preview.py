"""One listen-through file for Adit's audio review: the music layers as they build through
the campaign, then every sting and sound effect, with a cue sheet of timestamps.

Usage (Python 3.12, tools group), after tools/audio/render.py:
    uv run --group tools python -m tools.audio.preview [output.ogg]

The default output is logs/audio-preview.ogg (git-ignored). It reads the rendered files in
assets/audio/, so it plays exactly what the game ships.
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import soundfile as sf

from tools.audio.cues import SFX, STINGS
from tools.audio.render import encode
from tools.audio.synth import normalize
from tools.audio.theory import SR

ROOT = Path(__file__).resolve().parents[2]
AUDIO = ROOT / "assets" / "audio"
GAP = np.zeros(round(0.5 * SR))
# Relative stem levels for the preview mix. The game sets its own levels at runtime.
LAYERS = (
    ("Title (MU-05)", {"music_title": 0.8}),
    ("Fuse Box (MU-02)", {"music_fuse_box": 0.8}),
    ("Encounter 1: HUM and PULSE", {"music_hum": 0.7, "music_pulse": 0.6}),
    ("Encounter 2: adds ARC", {"music_hum": 0.7, "music_pulse": 0.6, "music_arc": 0.35}),
    (
        "Encounter 3: adds LEAD",
        {"music_hum": 0.7, "music_pulse": 0.6, "music_arc": 0.35, "music_lead": 0.5},
    ),
)


def load(name: str) -> np.ndarray:
    data, rate = sf.read(AUDIO / f"{name}.ogg", dtype="float64")
    if rate != SR:
        raise ValueError(f"{name} is {rate} Hz, expected {SR}")
    return data


def main(argv: list[str]) -> int:
    out = Path(argv[0]) if argv else ROOT / "logs" / "audio-preview.ogg"
    parts: list[np.ndarray] = []
    sheet: list[str] = []
    clock = 0.0

    def add(label: str, signal: np.ndarray) -> None:
        nonlocal clock
        sheet.append(f"{int(clock // 60):02d}:{clock % 60:05.2f}  {label}")
        parts.extend([signal, GAP])
        clock += (len(signal) + len(GAP)) / SR

    for label, stems in LAYERS:
        mix = sum(load(name) * level for name, level in stems.items())
        add(label, np.tile(mix, 2))  # two passes, so the loop point can be heard
    for name in (*STINGS, *SFX):
        add(name, load(name))
    out.parent.mkdir(parents=True, exist_ok=True)
    mix = normalize(np.concatenate(parts), -1.5).astype(np.float32)
    encode(out, mix)
    out.with_suffix(".txt").write_text("\n".join(sheet) + "\n", encoding="utf-8")
    print(f"Wrote {out} ({clock / 60:.1f} min) and its cue sheet {out.with_suffix('.txt')}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
