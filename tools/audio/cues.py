"""Every cue in the game, composed in code from the theme (theory.py) and the synth (synth.py).

Music stems all have exactly LOOP_SAMPLES samples and wrap their tails into the start, so
they loop seamlessly and stay in sync when layered. Sound effects are short one-shots tuned
to B minor. IDs match docs/ART_AND_AUDIO_DIRECTION.md (MU-01 to MU-03, sound effect groups).
"""

from __future__ import annotations

from collections.abc import Callable

import numpy as np

from tools.audio.synth import (
    crush,
    decay,
    drive,
    envelope,
    fade_edges,
    loop_svf,
    noise,
    place,
    saw,
    sine,
    square,
    svf,
    sweep,
    triangle,
)
from tools.audio.theory import (
    BAR,
    BEAT,
    CHORDS,
    LOOP_BARS,
    LOOP_SAMPLES,
    MAINS_HZ,
    MOTIF,
    ROOTS,
    SR,
    chord_at,
    hz,
    loop_hz,
    midi,
    samples,
)

EIGHTH = BEAT / 2
SIXTEENTH = BEAT / 4


def at(bar: int, beat: float = 0.0) -> int:
    return round((bar * BAR + beat * BEAT) * SR)


def chord_notes(index: int, octave: int) -> list[float]:
    return [hz(f"{name}{octave}") for name in CHORDS[index]]


# Music stems (MU-01, MU-02) -----------------------------------------------------------------


def hum() -> np.ndarray:
    """HUM: the mains drone, slightly detuned under B1, and a pulsing eighth-note bass."""
    n = LOOP_SAMPLES
    t = np.arange(n) / SR
    wobble = 1.0 + 0.15 * np.sin(2 * np.pi * t / (2 * BAR * LOOP_BARS / 8))
    mains = loop_hz(MAINS_HZ)
    drone = (sine(mains, n) + 0.35 * sine(2 * mains, n)) * 0.5 * wobble
    buzz = loop_svf(saw(mains, n), 260 + 120 * np.sin(2 * np.pi * t / (4 * BAR)), q=1.2) * 0.18
    out = drone + buzz
    note_len = samples(EIGHTH * 0.92)
    for step in range(LOOP_BARS * 8):
        bar = step // 8
        root = midi(ROOTS[chord_at(bar)])
        pitch = root + (12 if step % 8 == 7 else 0)
        f = hz(pitch)
        tone = saw(f, note_len) + 0.5 * square(f * 1.005, note_len)
        cutoff = 180 + 900 * decay(note_len, 0.12)
        accent = 1.0 if step % 2 == 0 else 0.75
        bass = svf(tone, cutoff, q=1.6) * envelope(note_len, 0.004, 0.08, 0.55, 0.03)
        place(out, drive(bass * 0.55 * accent, 1.6), round(step * EIGHTH * SR), wrap=True)
    return out


def kick(seconds: float = 0.42) -> np.ndarray:
    n = samples(seconds)
    body = sine(sweep(160, 44, n), n) * decay(n, 0.38)
    click = noise(n, "kick") * decay(n, 0.006) * 0.4
    return drive(body + click, 1.8)


def snare() -> np.ndarray:
    n = samples(0.24)
    hiss = svf(noise(n, "snare"), 1900, q=0.9, mode="band") * decay(n, 0.2) * 1.4
    tone = sine(sweep(220, 170, n), n) * decay(n, 0.08) * 0.6
    return hiss + tone


def hat(open_: bool = False) -> np.ndarray:
    n = samples(0.22 if open_ else 0.05)
    sizzle = svf(noise(n, "hat-open" if open_ else "hat"), 7500, q=0.8, mode="high")
    return sizzle * decay(n, 0.2 if open_ else 0.04) * 0.3


def pulse() -> np.ndarray:
    """PULSE: four-on-the-floor drum machine, backbeat snare, offbeat hats, a fill in bar 8."""
    out = np.zeros(LOOP_SAMPLES)
    k, s, h, oh = kick(), snare(), hat(), hat(open_=True)
    for bar in range(LOOP_BARS):
        for beat in range(4):
            place(out, k, at(bar, beat), wrap=True)
            if beat in (1, 3):
                place(out, s, at(bar, beat), wrap=True)
            place(out, oh if (beat == 3 and bar % 2 == 1) else h, at(bar, beat + 0.5), wrap=True)
            place(out, h * 0.35, at(bar, beat), wrap=True)
        if bar == LOOP_BARS - 1:
            for sixteenth in range(4):
                place(out, s * (0.5 + 0.15 * sixteenth), at(bar, 3 + sixteenth / 4), wrap=True)
    return out


def arc() -> np.ndarray:
    """ARC: a sixteenth-note arpeggio of the chord tones (layered in from encounter 2)."""
    out = np.zeros(LOOP_SAMPLES)
    note_len = samples(SIXTEENTH * 0.8)
    for step in range(LOOP_BARS * 16):
        notes = chord_notes(chord_at(step // 16), 4)
        f = notes[[0, 1, 2, 1][step % 4]] * (2 if step % 8 >= 4 else 1)
        tone = square(f, note_len, duty=0.25) * envelope(note_len, 0.002, 0.05, 0.2, 0.02)
        place(out, svf(tone, 2600, q=1.1) * 0.22, round(step * SIXTEENTH * SR), wrap=True)
    return out


def lead() -> np.ndarray:
    """LEAD: the four-note motif, once per two bars, on a detuned saw (encounter 3)."""
    out = np.zeros(LOOP_SAMPLES)
    note_len = samples(BEAT * 0.95)
    for phrase in range(LOOP_BARS // 2):
        for i, note in enumerate(MOTIF):
            f = hz(note)
            tone = saw(f, note_len) + saw(f * 1.006, note_len) + 0.5 * square(f / 2, note_len)
            shaped = svf(tone, 1400 + 1600 * decay(note_len, 0.3), q=1.4)
            amp = envelope(note_len, 0.01, 0.15, 0.6, 0.08) * 0.16
            place(out, shaped * amp, at(phrase * 2, i), wrap=True)
    return out


def fuse_box() -> np.ndarray:
    """MU-02: the HUM through a closed low-pass, with a slow pad on the same chords."""
    out = loop_svf(hum(), 240, q=0.8) * 0.9
    pad_len = samples(2 * BAR + 1.5)
    for index in range(len(CHORDS)):
        pad = np.zeros(pad_len)
        for f in chord_notes(index, 3):
            for detune in (0.997, 1.0, 1.004):
                pad += saw(f * detune, pad_len)
        shaped = svf(pad, 700 + 300 * sine(0.25, pad_len), q=0.9)
        place(out, shaped * envelope(pad_len, 1.2, 0.5, 0.8, 1.4) * 0.05, at(index * 2), wrap=True)
    return out


# Protocol stings (MU-03) --------------------------------------------------------------------


def _bar() -> np.ndarray:
    return np.zeros(samples(BAR + 0.6))


def sting_clamp() -> np.ndarray:
    """Clamp: three heavy descending stabs closing in, then a low impact."""
    out = _bar()
    for i, note in enumerate(("B3", "F#3", "B2")):
        n = samples(0.28)
        f = hz(note)
        stab = svf(square(f, n) + saw(f * 1.01, n), 1800 * decay(n, 0.2) + 200, q=2.0)
        place(out, drive(stab * envelope(n, 0.002, 0.18, 0.2, 0.05), 2.5) * 0.5, at(0, i * 0.5))
    place(out, kick(0.8) * 0.9, at(0, 1.75))
    n = samples(0.5)
    place(out, svf(noise(n, "clamp"), 400, q=1.0) * decay(n, 0.4) * 0.5, at(0, 1.75))
    return out


def sting_insulate() -> np.ndarray:
    """Insulate: pings that step back and away while the filter closes."""
    out = _bar()
    for i, note in enumerate(("B5", "F#5", "D5", "B4")):
        n = samples(0.6)
        f = hz(note)
        ping = (sine(f, n) + 0.3 * triangle(f * 2, n)) * decay(n, 0.5) * (0.5 - i * 0.08)
        place(out, ping, at(0, i * 0.75))
        place(out, ping * 0.3, at(0, i * 0.75 + 0.375))  # a short echo, held at range
    return svf(out, np.linspace(5000, 900, len(out)), q=0.8)


def sting_oscillate() -> np.ndarray:
    """Oscillate: a fast side-to-side figure between B and F#, landing on E."""
    out = _bar()
    n = samples(SIXTEENTH * 0.85)
    for step in range(12):
        f = hz("B4" if step % 2 == 0 else "F#4")
        tone = square(f, n, duty=0.3) * envelope(n, 0.002, 0.05, 0.4, 0.02) * 0.4
        place(out, svf(tone, 3000, q=1.2), at(0, step / 4))
    n = samples(0.6)
    place(out, saw(hz("E5"), n) * envelope(n, 0.005, 0.2, 0.4, 0.2) * 0.3, at(0, 3))
    return out


# Sound effects ------------------------------------------------------------------------------


def _shot(n: int = samples(0.07)) -> np.ndarray:
    tone = square(sweep(hz("F#6"), hz("B4"), n), n, duty=0.25)
    return crush(tone * decay(n, 0.06), bits=6) * 0.5


def _player_hit() -> np.ndarray:
    n = samples(0.25)
    return drive(noise(n, "hit") * decay(n, 0.12) + saw(sweep(300, 80, n), n) * decay(n, 0.2), 2)


def _dodge() -> np.ndarray:
    n = samples(0.18)
    return (
        svf(noise(n, "dodge"), sweep(800, 5000, n), q=1.5, mode="band")
        * envelope(n, 0.02, 0.1, 0.3, 0.06)
        * 0.8
    )


def _death() -> np.ndarray:
    """A tape-stop power cut: the chord slows to nothing, then silence."""
    n = samples(1.4)
    slow = sweep(1.0, 0.05, n)
    tones = sum(saw(f * slow, n) for f in chord_notes(0, 3))
    return svf(tones, 1800 * slow + 80, q=0.8) * envelope(n, 0.005, 1.2, 0.0, 0.15) * 0.35


def _low_health() -> np.ndarray:
    n = samples(0.09)
    beep = sine(hz("B5"), n) * envelope(n, 0.003, 0.05, 0.6, 0.02)
    out = np.zeros(samples(0.3))
    place(out, beep, 0)
    place(out, beep, samples(0.16))
    return out * 0.5


def _spark() -> np.ndarray:
    n = samples(0.22)
    zap = saw(sweep(hz("B6"), hz("B4"), n), n) * decay(n, 0.18)
    crackle = noise(n, "spark") * (np.random.default_rng(3).random(n) > 0.92) * decay(n, 0.15)
    return crush(zap * 0.5 + crackle * 0.6, bits=7)


def _blink_depart() -> np.ndarray:
    n = samples(0.16)
    return sine(sweep(hz("B4"), hz("B6"), n), n) * envelope(n, 0.005, 0.1, 0.3, 0.05) * 0.5


def _blink_arrive() -> np.ndarray:
    n = samples(0.18)
    pop = sine(sweep(hz("F#6"), hz("B4"), n), n) * decay(n, 0.15)
    return pop * 0.5 + svf(noise(n, "arrive"), 3000, q=1, mode="band") * decay(n, 0.04) * 0.3


def _blink_deny() -> np.ndarray:
    n = samples(0.07)
    buzz = square(hz("B2"), n) * envelope(n, 0.002, 0.04, 0.5, 0.02)
    out = np.zeros(samples(0.2))
    place(out, buzz, 0)
    place(out, buzz, samples(0.1))
    return svf(out, 900, q=1.0) * 0.6


def _arc_trail() -> np.ndarray:
    n = samples(0.6)
    buzz = saw(hz("B2"), n) + square(hz("B2") * 1.5, n) * 0.5
    return svf(buzz, 1200 + 600 * sine(12, n), q=2.0) * envelope(n, 0.01, 0.2, 0.5, 0.2) * 0.4


def _mite_tell() -> np.ndarray:
    n = samples(0.45)
    whine = sine(sweep(hz("B4"), hz("F#5"), n), n) * (0.7 + 0.3 * square(16, n))
    return whine * envelope(n, 0.02, 0.1, 0.6, 0.05) * 0.35


def _mite_zap() -> np.ndarray:
    n = samples(0.12)
    return crush(square(hz("F#5"), n) * decay(n, 0.1) + noise(n, "zap") * decay(n, 0.03), 6) * 0.4


def _relay_click() -> np.ndarray:
    n = samples(0.05)
    return (noise(n, "click") * decay(n, 0.01) + square(hz("D6"), n) * decay(n, 0.02)) * 0.5


def _relay_blink() -> np.ndarray:
    n = samples(0.2)
    return sine(sweep(hz("D6"), hz("D4"), n), n) * decay(n, 0.18) * 0.45


def _enemy_death() -> np.ndarray:
    n = samples(0.45)
    rng = np.random.default_rng(11)
    bursts = noise(n, "short") * (rng.random(n) > 0.85) * decay(n, 0.35)
    fall = saw(sweep(hz("B4"), hz("B2"), n), n) * decay(n, 0.3)
    return crush(bursts * 0.6 + fall * 0.4, bits=6)


def _tread() -> np.ndarray:
    n = samples(0.6)
    return svf(noise(n, "tread"), 110, q=1.5) * envelope(n, 0.05, 0.2, 0.7, 0.2) * 1.6


def _lunge() -> np.ndarray:
    n = samples(0.35)
    return (
        drive(sine(sweep(110, 38, n), n) * decay(n, 0.3) + noise(n, "thunk") * decay(n, 0.02), 2.2)
        * 0.8
    )


def _hazard_fill() -> np.ndarray:
    n = samples(0.6)
    rise = square(sweep(hz("B2"), hz("F#3"), n), n)
    return svf(rise, sweep(300, 3500, n), q=2.5) * envelope(n, 0.05, 0.1, 0.8, 0.05) * 0.35


def _orb_fire() -> np.ndarray:
    n = samples(0.3)
    return sine(hz("D5") * (1 + 0.05 * sine(18, n)), n) * decay(n, 0.25) * 0.45


def _regulator_hit() -> np.ndarray:
    n = samples(0.18)
    partials = sum(sine(f, n) * w for f, w in ((420, 0.5), (1130, 0.3), (2710, 0.2)))
    return partials * decay(n, 0.12) * 0.6


def _regulator_defeated() -> np.ndarray:
    n = samples(1.8)
    down = saw(sweep(hz("B3"), hz("B1") / 2, n), n) + saw(sweep(hz("F#3"), hz("F#1") / 2, n), n)
    rng = np.random.default_rng(7)
    crackle = noise(n, "defeat") * (rng.random(n) > 0.9) * decay(n, 1.2)
    return drive(svf(down, sweep(2500, 120, n), q=1.2) * 0.4 + crackle * 0.5, 1.5) * decay(n, 1.6)


def _motif(notes: tuple[str, ...], step: float, length: float, octave_up: bool = True):
    out = np.zeros(samples(step * len(notes) + length))
    for i, note in enumerate(notes):
        f = hz(note) * (2 if octave_up else 1)
        n = samples(length)
        tone = (square(f, n, duty=0.25) * 0.5 + sine(f, n)) * envelope(n, 0.003, 0.1, 0.3, 0.1)
        place(out, tone * 0.35, samples(step * i))
    return out


def _pickup() -> np.ndarray:
    return _motif(MOTIF[:2], 0.06, 0.14)


def _unlock() -> np.ndarray:
    return _motif(MOTIF, 0.08, 0.3)


def _fusion() -> np.ndarray:
    out = _motif(MOTIF, 0.12, 0.4)
    n = samples(1.2)
    swell = sum(saw(f, n) for f in chord_notes(0, 4))
    place(
        out,
        svf(swell, sweep(400, 4000, n), q=1.0) * envelope(n, 0.6, 0.3, 0.4, 0.3) * 0.12,
        samples(0.36),
    )
    return out


def _confirm() -> np.ndarray:
    return _motif(("B4", "F#5"), 0.05, 0.1)


def _deny() -> np.ndarray:
    return _blink_deny()


MUSIC: dict[str, Callable[[], np.ndarray]] = {
    "music_hum": hum,
    "music_pulse": pulse,
    "music_arc": arc,
    "music_lead": lead,
    "music_fuse_box": fuse_box,
}
STINGS: dict[str, Callable[[], np.ndarray]] = {
    "sting_clamp": sting_clamp,
    "sting_insulate": sting_insulate,
    "sting_oscillate": sting_oscillate,
}
SFX: dict[str, Callable[[], np.ndarray]] = {
    "sfx_shot": _shot,
    "sfx_player_hit": _player_hit,
    "sfx_dodge": _dodge,
    "sfx_death": _death,
    "sfx_low_health": _low_health,
    "sfx_spark": _spark,
    "sfx_blink_depart": _blink_depart,
    "sfx_blink_arrive": _blink_arrive,
    "sfx_blink_deny": _blink_deny,
    "sfx_arc_trail": _arc_trail,
    "sfx_mite_tell": _mite_tell,
    "sfx_mite_zap": _mite_zap,
    "sfx_relay_click": _relay_click,
    "sfx_relay_blink": _relay_blink,
    "sfx_enemy_death": _enemy_death,
    "sfx_tread": _tread,
    "sfx_lunge": _lunge,
    "sfx_hazard_fill": _hazard_fill,
    "sfx_orb_fire": _orb_fire,
    "sfx_regulator_hit": _regulator_hit,
    "sfx_regulator_defeated": _regulator_defeated,
    "sfx_pickup": _pickup,
    "sfx_unlock": _unlock,
    "sfx_fusion": _fusion,
    "sfx_confirm": _confirm,
    "sfx_deny": _deny,
}


def one_shot(render: Callable[[], np.ndarray]) -> np.ndarray:
    return fade_edges(render())
