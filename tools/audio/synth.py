"""The one small synth everything is made with: saw, square, sine, triangle and noise, an
envelope, one resonant filter and a light bit-crush (docs/ART_AND_AUDIO_DIRECTION.md).

Signals are mono float64 numpy arrays at theory.SR. Noise is seeded per cue, so a render is
repeatable.
"""

from __future__ import annotations

import math
import zlib

import numpy as np

from tools.audio.theory import SR

Freq = float | np.ndarray


def _phase(freq: Freq, n: int) -> np.ndarray:
    if np.isscalar(freq):
        return np.arange(n) * (float(freq) / SR)
    return np.cumsum(np.asarray(freq, dtype=np.float64)) / SR


def sine(freq: Freq, n: int) -> np.ndarray:
    return np.sin(2 * np.pi * _phase(freq, n))


def saw(freq: Freq, n: int) -> np.ndarray:
    return 2.0 * (_phase(freq, n) % 1.0) - 1.0


def square(freq: Freq, n: int, duty: float = 0.5) -> np.ndarray:
    """Pulse wave with its DC offset removed, so narrow duty cycles stay centered."""
    return np.where((_phase(freq, n) % 1.0) < duty, 1.0, -1.0) - (2.0 * duty - 1.0)


def triangle(freq: Freq, n: int) -> np.ndarray:
    return 2.0 * np.abs(saw(freq, n)) - 1.0


def noise(n: int, name: str) -> np.ndarray:
    """White noise, seeded by the cue name so every render matches."""
    return np.random.default_rng(zlib.crc32(name.encode())).uniform(-1.0, 1.0, n)


def sweep(start: float, end: float, n: int) -> np.ndarray:
    """An exponential pitch glide, for zaps, drops and risers."""
    return np.geomspace(start, end, n)


def envelope(
    n: int, attack: float = 0.005, decay: float = 0.1, sustain: float = 0.0, release: float = 0.05
) -> np.ndarray:
    """ADSR across n samples: the release ends exactly at the last sample."""
    a, d, r = (max(1, round(x * SR)) for x in (attack, decay, release))
    a = min(a, n)
    d = min(d, n - a)
    r = min(r, max(0, n - a - d))
    hold = n - a - d - r
    return np.concatenate(
        [
            np.linspace(0.0, 1.0, a, endpoint=False),
            np.linspace(1.0, sustain, d, endpoint=False),
            np.full(hold, sustain),
            np.linspace(sustain, 0.0, r),
        ]
    )[:n]


def decay(n: int, seconds: float) -> np.ndarray:
    """Exponential fade, down about 60 dB after `seconds`."""
    return np.exp(-6.9 * np.arange(n) / (seconds * SR))


def svf(x: np.ndarray, cutoff: Freq, q: float = 0.7, mode: str = "low") -> np.ndarray:
    """State-variable filter (Chamberlin), the one resonant filter. `cutoff` may sweep."""
    n = len(x)
    cut = np.broadcast_to(np.asarray(cutoff, dtype=np.float64), (n,))
    f = 2.0 * np.sin(np.pi * np.minimum(cut, SR / 6.0) / SR)
    damp = 1.0 / max(q, 0.5)
    low = band = 0.0
    out = np.empty(n)
    xs, fs = x.tolist(), f.tolist()
    pick = {"low": 0, "band": 1, "high": 2}[mode]
    for i in range(n):
        fi = fs[i]
        low += fi * band
        high = xs[i] - low - damp * band
        band += fi * high
        out[i] = (low, band, high)[pick]
    return out


def loop_svf(x: np.ndarray, cutoff: Freq, q: float = 0.7, mode: str = "low") -> np.ndarray:
    """Filter a loop in its steady state: run it twice and keep the second pass, so the
    filter's state at the end matches the start and the loop point does not click."""
    n = len(x)
    cut = cutoff if np.isscalar(cutoff) else np.tile(np.asarray(cutoff), 2)
    return svf(np.tile(x, 2), cut, q, mode)[n:]


def crush(x: np.ndarray, bits: int = 8, hold: int = 2) -> np.ndarray:
    """Light bit-crush: fewer levels and a sample-and-hold, for the grit of a machine."""
    levels = 2 ** (bits - 1)
    held = np.repeat(x[::hold], hold)[: len(x)]
    return np.round(held * levels) / levels


def drive(x: np.ndarray, amount: float = 2.0) -> np.ndarray:
    return np.tanh(x * amount) / math.tanh(amount)


def place(buffer: np.ndarray, sound: np.ndarray, start: int, wrap: bool = False) -> None:
    """Add `sound` into `buffer` at `start`. With wrap, a tail past the end comes back in at
    the beginning, which is what makes a loop seamless."""
    n = len(buffer)
    if wrap:
        for offset in range(0, len(sound), n):
            chunk = sound[offset : offset + n]
            begin = (start + offset) % n
            first = min(len(chunk), n - begin)
            buffer[begin : begin + first] += chunk[:first]
            buffer[: len(chunk) - first] += chunk[first:]
        return
    end = min(n, start + len(sound))
    if end > start:
        buffer[start:end] += sound[: end - start]


def normalize(x: np.ndarray, peak_db: float = -1.5) -> np.ndarray:
    """Scale so the loudest sample sits at `peak_db` (the limit is -1 dBFS after encoding)."""
    peak = float(np.max(np.abs(x))) or 1.0
    return x * (10 ** (peak_db / 20) / peak)


def fade_edges(x: np.ndarray, seconds: float = 0.003) -> np.ndarray:
    """Tiny fades at both ends of a one-shot so it never clicks."""
    k = min(len(x) // 2, max(1, round(seconds * SR)))
    out = x.copy()
    ramp = np.linspace(0.0, 1.0, k)
    out[:k] *= ramp
    out[-k:] *= ramp[::-1]
    return out
