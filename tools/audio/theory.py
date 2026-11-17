"""The theme's constants: one key, one tempo, one progression, one motif.

Every cue, music and sound effects alike, is built from these, so the game sounds like one
piece (docs/ART_AND_AUDIO_DIRECTION.md, Music).
"""

from __future__ import annotations

SR = 44_100
BPM = 124
BEAT = 60.0 / BPM
BAR = 4 * BEAT
LOOP_BARS = 8
LOOP_SAMPLES = round(LOOP_BARS * BAR * SR)  # every stem has exactly this many samples

# B minor: Bm, G, D, A, two bars each.
CHORDS = (("B", "D", "F#"), ("G", "B", "D"), ("D", "F#", "A"), ("A", "C#", "E"))
ROOTS = ("B1", "G1", "D2", "A1")
MOTIF = ("B4", "D5", "F#5", "E5")
MAINS_HZ = 60.0  # US mains hum, just under B1 (61.7 Hz): the drone, slightly detuned


def loop_hz(freq: float) -> float:
    """The nearest frequency that completes a whole number of cycles per loop, so a
    continuous tone has no click at the loop point."""
    cycles = max(1, round(freq * LOOP_SAMPLES / SR))
    return cycles * SR / LOOP_SAMPLES


_STEPS = {
    "C": 0,
    "C#": 1,
    "D": 2,
    "D#": 3,
    "E": 4,
    "F": 5,
    "F#": 6,
    "G": 7,
    "G#": 8,
    "A": 9,
    "A#": 10,
    "B": 11,
}


def midi(note: str) -> int:
    """'F#3' -> 54."""
    name, octave = note[:-1], int(note[-1])
    return 12 * (octave + 1) + _STEPS[name]


def hz(note: str | int) -> float:
    number = midi(note) if isinstance(note, str) else note
    return 440.0 * 2.0 ** ((number - 69) / 12)


def samples(seconds: float) -> int:
    return round(seconds * SR)


def chord_at(bar: int) -> int:
    """Index into CHORDS for a bar of the 8-bar loop."""
    return (bar // 2) % len(CHORDS)
