"""Render every audio cue to assets/audio/ as 44.1 kHz mono OGG Vorbis and record each file in
assets/ASSET_MANIFEST.json.

Usage (Python 3.12, numpy and soundfile come from the tools group):
    uv run --group tools python -m tools.audio.render

Peaks are normalized to -1.5 dBFS, then checked again after encoding, so the committed files
stay at or below -1 dBFS (docs/ART_AND_AUDIO_DIRECTION.md, audio technical checks).
"""

from __future__ import annotations

import hashlib
import json
import sys
from datetime import date
from pathlib import Path

import numpy as np
import soundfile as sf

from tools.audio.cues import MUSIC, SFX, STINGS, one_shot
from tools.audio.synth import normalize
from tools.audio.theory import LOOP_SAMPLES, SR

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "assets" / "audio"
MANIFEST = ROOT / "assets" / "ASSET_MANIFEST.json"
LICENSE = "assets/audio/LICENSE.txt"
CEILING = 10 ** (-1 / 20)
IDS = {
    "music_hum": "MU-01.hum",
    "music_pulse": "MU-01.pulse",
    "music_arc": "MU-01.arc",
    "music_lead": "MU-01.lead",
    "music_fuse_box": "MU-02",
    "sting_clamp": "MU-03.clamp",
    "sting_insulate": "MU-03.insulate",
    "sting_oscillate": "MU-03.oscillate",
}


def encode(path: Path, signal: np.ndarray) -> None:
    """Mono OGG Vorbis, streamed in one-second blocks (libsndfile's Vorbis encoder can crash
    on one very large write)."""
    with sf.SoundFile(path, "w", SR, 1, format="OGG", subtype="VORBIS") as handle:
        for start in range(0, len(signal), SR):
            handle.write(signal[start : start + SR])


def write(name: str, signal: np.ndarray) -> Path:
    path = OUT / f"{name}.ogg"
    peak = -1.5
    for _ in range(6):
        encode(path, normalize(signal, peak).astype(np.float32))
        decoded, _ = sf.read(path, dtype="float32")
        if float(np.max(np.abs(decoded))) <= CEILING:
            return path
        peak -= 0.5  # Vorbis can overshoot the source peak a little: back off and retry
    raise RuntimeError(f"{name} still peaks above -1 dBFS after encoding")


def render_all() -> dict[str, Path]:
    OUT.mkdir(parents=True, exist_ok=True)
    written = {}
    for name, render in MUSIC.items():
        signal = render()
        if len(signal) != LOOP_SAMPLES:
            raise RuntimeError(f"{name} has {len(signal)} samples, stems need {LOOP_SAMPLES}")
        written[name] = write(name, signal)
        print(f"  {name}: {len(signal) / SR:.2f} s loop")
    for name, render in {**STINGS, **SFX}.items():
        signal = one_shot(render)
        written[name] = write(name, signal)
        print(f"  {name}: {len(signal) / SR:.2f} s")
    return written


def update_manifest(written: dict[str, Path]) -> None:
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    keep = [e for e in manifest["assets"] if not e["path"].startswith("assets/audio/")]
    today = date.today().isoformat()
    audio = []
    for name, path in sorted(written.items()):
        audio.append(
            {
                "id": IDS.get(name, "SFX." + name.removeprefix("sfx_")),
                "path": str(path.relative_to(ROOT)),
                "kind": "audio",
                "creator": "Overload project, composed in code",
                "source": "tools/audio/cues.py (rendered by tools/audio/render.py)",
                "license": "Original work, see assets/audio/LICENSE.txt",
                "license_file": LICENSE,
                "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                "added": today,
                "approval": "Pending Adit's listen-through",
            }
        )
    license_path = ROOT / LICENSE
    audio.append(
        {
            "id": "AUDIO.license",
            "path": LICENSE,
            "kind": "license",
            "creator": "Overload project",
            "source": "Written for this project",
            "license": "Original work",
            "license_file": LICENSE,
            "sha256": hashlib.sha256(license_path.read_bytes()).hexdigest(),
            "added": today,
            "approval": "Pending Adit's choice of a project license",
        }
    )
    manifest["assets"] = keep + audio
    MANIFEST.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")


def main() -> int:
    written = render_all()
    update_manifest(written)
    print(f"Rendered {len(written)} cues to {OUT.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
