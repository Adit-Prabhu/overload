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
    sizzle = svf(noise(n, "hat-open" if open_ else "hat"), 7000, q=0.8, mode="high")
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


def _bell(f: float, seconds: float = 1.6) -> np.ndarray:
    """A soft struck bell: a sine with two inharmonic partials, the upper ones fading first."""
    n = samples(seconds)
    tone = sine(f, n) * decay(n, seconds)
    tone += 0.35 * sine(f * 2.01, n) * decay(n, seconds * 0.5)
    tone += 0.12 * sine(f * 3.98, n) * decay(n, seconds * 0.25)
    return tone * envelope(n, 0.004, 0.05, 1.0, 0.05)


def title() -> np.ndarray:
    """MU-05: the title. The HUM's mains drone without its bass, a slow pad on the theme's
    chords opening and closing, the motif sparse on a bell with a dotted-eighth echo, a
    quiet two-beat heartbeat, and now and then a crackle on the line. Moody and patient,
    in the same key and tempo as the rest, so the first sector's music follows on."""
    n = LOOP_SAMPLES
    t = np.arange(n) / SR
    mains = loop_hz(MAINS_HZ)
    swell = 0.8 + 0.2 * np.sin(2 * np.pi * t / (LOOP_BARS * BAR))
    out = (sine(mains, n) + 0.3 * sine(2 * mains, n)) * 0.38 * swell
    buzz = loop_svf(saw(mains, n), 200 + 80 * np.sin(2 * np.pi * t / (4 * BAR)), q=1.0)
    out += buzz * 0.08
    pad_len = samples(2 * BAR + 1.5)
    for index in range(len(CHORDS)):
        pad = np.zeros(pad_len)
        for f in chord_notes(index, 3):
            for detune in (0.996, 1.0, 1.005):
                pad += saw(f * detune, pad_len)
        cutoff = 600 + 700 * (0.5 - 0.5 * np.cos(np.linspace(0, 2 * np.pi, pad_len)))
        shaped = svf(pad, cutoff, q=1.1)
        place(out, shaped * envelope(pad_len, 1.4, 0.5, 0.8, 1.6) * 0.045, at(index * 2), wrap=True)
    # The motif, then its answer up a third over the D chord, each ringing with an echo.
    phrases = ((0, MOTIF), (4, ("D5", "F#5", "A5", "F#5")))
    for bar, notes in phrases:
        for i, note in enumerate(notes):
            bell = _bell(hz(note)) * 0.2
            start = at(bar, i)
            place(out, bell, start, wrap=True)
            place(out, bell * 0.4, start + samples(0.75 * BEAT), wrap=True)
            place(out, bell * 0.16, start + samples(1.5 * BEAT), wrap=True)
    beat = svf(kick(0.5), 220, q=0.8) * 0.32
    for bar in range(LOOP_BARS):
        place(out, beat, at(bar, 0), wrap=True)
        place(out, beat * 0.6, at(bar, 0.5), wrap=True)
    for i, (bar, beat_at) in enumerate(((1, 2.5), (3, 1.25), (5, 3.0), (6, 0.75), (7, 2.25))):
        m = samples(0.06)
        tick = svf(noise(m, f"title-crackle-{i}"), 4200, q=1.2, mode="band") * decay(m, 0.05)
        place(out, tick * 0.25, at(bar, beat_at), wrap=True)
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
    """A metal clang: deliberately inharmonic partials, the one cue outside the key."""
    n = samples(0.18)
    partials = sum(sine(f, n) * w for f, w in ((420, 0.5), (1130, 0.3), (2710, 0.2)))
    return partials * decay(n, 0.12) * 0.6


def _regulator_defeated() -> np.ndarray:
    n = samples(1.8)
    down = saw(sweep(hz("B3"), hz("B1") / 2, n), n) + saw(sweep(hz("F#3"), hz("F#1") / 2, n), n)
    rng = np.random.default_rng(7)
    crackle = noise(n, "defeat") * (rng.random(n) > 0.9) * decay(n, 1.2)
    return drive(svf(down, sweep(2500, 120, n), q=1.2) * 0.4 + crackle * 0.5, 1.5) * decay(n, 1.6)


def _boss_charge() -> np.ndarray:
    """A chassis winding up its signature: a rising, beating saw pair, louder than a robot
    tell so it reads as the bigger threat."""
    n = samples(0.75)
    rise = sweep(hz("B1"), hz("F#3"), n)
    pair = saw(rise, n) + saw(rise * 1.012, n)
    return svf(pair, sweep(200, 2600, n), q=3.0) * envelope(n, 0.05, 0.05, 0.9, 0.05) * 0.3


def _ring_burst() -> np.ndarray:
    """Eight bolts at once: a bright crack with a short falling zap."""
    n = samples(0.32)
    zap = square(sweep(hz("B5"), hz("B3"), n), n, duty=0.3) * decay(n, 0.12)
    return crush(zap * 0.5 + noise(n, "ring") * decay(n, 0.03) * 0.5, bits=7)


def _quake() -> np.ndarray:
    """The Transformer's stomp: a deep drop with rumble trailing behind the ring."""
    n = samples(0.9)
    boom = sine(sweep(80, 28, n), n) * decay(n, 0.5)
    rumble = svf(noise(n, "quake"), 140, q=1.2) * decay(n, 0.7)
    return drive(boom * 0.9 + rumble * 0.7 + noise(n, "crack") * decay(n, 0.02) * 0.4, 2.0) * 0.8


def _summon() -> np.ndarray:
    """The Grid Core calls drones: two rising blips, a fifth apart."""
    n = samples(0.5)
    half = n // 2
    out = np.zeros(n)
    for i, note in enumerate(("B3", "F#4")):
        part = sine(sweep(hz(note), hz(note) * 2, half), half) * decay(half, 0.18)
        out[i * half : (i + 1) * half] += part
    return out * 0.5


def _overload() -> np.ndarray:
    """Phase 2: a two-tone alarm over a crackling surge."""
    n = samples(1.4)
    rng = np.random.default_rng(23)
    tone = square(np.where((np.arange(n) // samples(0.14)) % 2 == 0, hz("B4"), hz("F4")), n)
    crackle = noise(n, "overload") * (rng.random(n) > 0.92)
    return (svf(tone, 1800) * 0.35 + crackle * 0.4) * envelope(n, 0.02, 0.1, 0.8, 0.4)


# The boss kits (docs/BOSS_DESIGN.md): each attack its own sound, so two never share a read.


def _live_wire() -> np.ndarray:
    """Live Wire's lines going live: a buzzing arc at the mains hum's harmonic, crackling."""
    n = samples(0.45)
    rng = np.random.default_rng(31)
    buzz = square(MAINS_HZ * 4 * (1 + 0.02 * sine(37, n)), n, duty=0.2)
    crackle = noise(n, "wire") * (rng.random(n) > 0.8)
    return crush(svf(buzz, 2600) * 0.45 + crackle * 0.45, bits=6) * envelope(
        n, 0.005, 0.05, 0.85, 0.15
    )


def _volley() -> np.ndarray:
    """Insulators bursting where they landed: three ceramic pops, falling a fourth."""
    n = samples(0.42)
    out = np.zeros(n)
    for i, note in enumerate(("F#5", "D5", "B4")):
        m = samples(0.12)
        pop = sine(sweep(hz(note), hz(note) * 0.75, m), m) * decay(m, 0.05)
        place(out, pop * 0.5 + noise(m, f"pop{i}") * decay(m, 0.01) * 0.3, samples(0.11 * i))
    return out


def _charge() -> np.ndarray:
    """The Bull Charge: hooves hammering faster under a rising growl."""
    n = samples(0.9)
    out = svf(saw(sweep(hz("B1"), hz("D2"), n), n), 400, q=1.5) * 0.4
    t = 0.0
    gap = 0.16
    while t < 0.85:
        m = samples(0.08)
        place(out, sine(sweep(90, 40, m), m) * decay(m, 0.05) * 0.8, samples(t))
        t += gap
        gap = max(0.07, gap * 0.85)
    return drive(out, 1.6) * envelope(n, 0.02, 0.05, 0.9, 0.1)


def _charge_impact() -> np.ndarray:
    """A chassis hits the wall: a metal crash on a deep thud, ringing off."""
    n = samples(1.0)
    thud = sine(sweep(70, 30, n), n) * decay(n, 0.35)
    clang = sum(sine(f, n) * w for f, w in ((310, 0.4), (870, 0.3), (1990, 0.2))) * decay(n, 0.5)
    return drive(thud + clang * 0.6 + noise(n, "crash") * decay(n, 0.08) * 0.6, 2.2) * 0.75


def _spray() -> np.ndarray:
    """Coolant Spray: a pressurized hiss that opens up, with a gurgle under it."""
    n = samples(0.55)
    hiss = svf(noise(n, "spray"), sweep(1200, 5000, n), q=0.9, mode="high")
    gurgle = sine(hz("B2") * (1 + 0.1 * sine(22, n)), n)
    return (hiss * 0.6 + gurgle * 0.25) * envelope(n, 0.01, 0.1, 0.7, 0.2)


def _lattice() -> np.ndarray:
    """The Lattice catching: the grid's hum swelling into a hard chord of fifths."""
    n = samples(0.7)
    chord = sum(saw(hz(note), n) for note in ("B2", "F#3", "B3"))
    return svf(chord, sweep(300, 3000, n), q=2.0) * envelope(n, 0.02, 0.1, 0.8, 0.3) * 0.25


def _spiral() -> np.ndarray:
    """The Grid Core spiral: a descending coil sweep with a rotating upper voice."""
    n = samples(0.58)
    rotor = 0.55 + 0.45 * sine(11, n)
    low = saw(sweep(hz("B3"), hz("B2"), n), n)
    high = sine(sweep(hz("B4"), hz("F#5"), n), n) * rotor
    mix = svf(low, sweep(2400, 550, n), q=1.3) * 0.36 + high * 0.28
    return mix * envelope(n, 0.012, 0.08, 0.8, 0.23)


def _vent() -> np.ndarray:
    """Venting: a long steam release that falls away. The cue that says hit it now."""
    n = samples(1.1)
    steam = svf(noise(n, "vent"), sweep(4000, 900, n), q=0.8, mode="high")
    sigh = sine(sweep(hz("F#4"), hz("B3"), n), n) * 0.15
    return (steam * 0.7 + sigh) * envelope(n, 0.01, 0.1, 0.7, 0.6)


def _phase_change() -> np.ndarray:
    """A new phase: a mechanical roar (detuned saws diving) under a rising alarm."""
    n = samples(1.3)
    roar = saw(sweep(hz("B2"), hz("B1"), n), n) + saw(sweep(hz("B2") * 1.03, hz("B1") * 1.03, n), n)
    alarm = square(sweep(hz("B4"), hz("F#5"), n), n, duty=0.3)
    mix = svf(roar, 900, q=1.4) * 0.5 + svf(alarm, 2200) * 0.2
    return drive(mix, 1.8) * envelope(n, 0.03, 0.1, 0.8, 0.4)


def _boss_down() -> np.ndarray:
    """A chassis falls: rolling explosions, then the motif rising in major. The win."""
    n = samples(2.6)
    out = np.zeros(n)
    rng = np.random.default_rng(41)
    for i in range(6):
        m = samples(0.4)
        boom = sine(sweep(110 - i * 8, 30, m), m) * decay(m, 0.25)
        place(
            out,
            drive(boom + noise(m, f"boom{i}") * decay(m, 0.05) * 0.5, 1.8) * 0.6,
            samples(i * 0.17 + rng.random() * 0.03),
        )
    place(out, _motif(("B3", "D#4", "F#4", "A#4", "B4"), 0.11, 0.5) * 1.2, samples(1.2))
    return out


# Bulwark and Magnet (powers spec section 8).


def _bulwark_up() -> np.ndarray:
    """A shield snapping up: a bright rising fifth over a glassy shimmer."""
    n = samples(0.4)
    rise = sine(sweep(hz("B4"), hz("F#5"), n), n) * envelope(n, 0.01, 0.1, 0.6, 0.2)
    shimmer = svf(noise(n, "shield"), 6000, q=0.7, mode="high") * decay(n, 0.15)
    return rise * 0.5 + shimmer * 0.25


def _bulwark_absorb() -> np.ndarray:
    """A shot eaten by the shield: a short dull tick with a glassy ring."""
    n = samples(0.14)
    return (sine(hz("F#5"), n) * 0.4 + noise(n, "absorb") * 0.3) * decay(n, 0.05)


def _bulwark_reflect() -> np.ndarray:
    """A shot sent back: a ping that flips upward."""
    n = samples(0.2)
    return square(sweep(hz("B4"), hz("B5"), n), n, duty=0.25) * decay(n, 0.12) * 0.4


def _magnet_field() -> np.ndarray:
    """A Magnet field: a low wobbling hum that pulls in."""
    n = samples(0.55)
    hum = saw(hz("B2") * (1 + 0.04 * sine(9, n)), n)
    return svf(hum, sweep(1800, 400, n), q=2.0) * envelope(n, 0.02, 0.1, 0.7, 0.2) * 0.4


def _magnet_crush() -> np.ndarray:
    """CRUSH: the field slams shut, a metal crunch."""
    n = samples(0.3)
    crunch = noise(n, "crush") * decay(n, 0.08)
    thud = sine(sweep(120, 50, n), n) * decay(n, 0.2)
    return drive(crunch * 0.5 + thud * 0.7, 2.0) * 0.7


def _motif(notes: tuple[str, ...], step: float, length: float, octave_up: bool = True):
    out = np.zeros(samples(step * len(notes) + length))
    for i, note in enumerate(notes):
        f = hz(note) * (2 if octave_up else 1)
        n = samples(length)
        tone = (square(f, n, duty=0.25) * 0.5 + sine(f, n)) * envelope(n, 0.003, 0.1, 0.3, 0.1)
        place(out, tone * 0.35, samples(step * i))
    return out


# Fused powers (powers spec section 8: each result its own use cue). One recipe per result:
# its two ingredients' voices, shaped by what it does, with a rarity layer on top. Every
# voice sits on a chord tone of B minor, so the cues belong to the same piece.


def _voice(power: str, n: int, f: float, tag: str) -> np.ndarray:
    """An ingredient's sound DNA at pitch f over n samples."""
    if power == "spark":  # a bright falling zap with crackle
        zap = saw(sweep(f * 4, f * 2, n), n) * decay(n, n / SR * 0.7)
        crackle = noise(n, f"{tag}-spark") * decay(n, n / SR * 0.5)
        return crush(zap * 0.5 + svf(crackle, 5000, q=0.7, mode="high") * 0.4, bits=7)
    if power == "blink":  # a rising glide through a sweeping band of air
        glide = sine(sweep(f, f * 4, n), n) * envelope(n, 0.005, 0.1, 0.4, 0.05)
        air = svf(noise(n, f"{tag}-blink"), sweep(900, 6000, n), q=1.4, mode="band")
        return glide * 0.45 + air * envelope(n, 0.02, 0.1, 0.3, 0.05) * 0.5
    if power == "burst":  # a low thump with a puff of grit
        body = sine(sweep(f, f / 3, n), n) * decay(n, n / SR * 0.8)
        grit = noise(n, f"{tag}-burst") * decay(n, 0.03)
        return drive(body + grit * 0.5, 2.0) * 0.7
    if power == "bulwark":  # a struck metal plate: inharmonic partials, ringing
        ring = sine(f * 2, n) + 0.5 * sine(f * 2 * 2.76, n) + 0.25 * sine(f * 2 * 5.4, n)
        return ring * decay(n, n / SR) * envelope(n, 0.003, 0.05, 1.0, 0.05) * 0.35
    # magnet: a wobbling low hum that pulls inward
    hum = saw(f / 2 * (1 + 0.05 * sine(10, n)), n)
    return svf(hum, sweep(2200, 350, n), q=2.0) * envelope(n, 0.02, 0.1, 0.7, 0.1) * 0.45


def _shape(verb: str, a: str, b: str, f: float, tag: str) -> np.ndarray:
    """What the power does, in time: a bolt, a chain, a placed device, a blast, a dash, a
    held field, a shield, a pull or a rewind."""
    if verb == "bolt":
        n = samples(0.28)
        return _voice(a, n, f, tag) + _voice(b, n, f * 1.5, tag) * 0.6
    if verb == "chain":
        out = np.zeros(samples(0.5))
        for i, step in enumerate((1.0, 1.26, 1.5)):  # up the chord, a hop each
            n = samples(0.14)
            place(
                out,
                (_voice(a, n, f * step, f"{tag}{i}") + _voice(b, n, f * step, tag)) * 0.6,
                samples(i * 0.11),
            )
        return out
    if verb == "place":
        out = np.zeros(samples(0.7))
        m = samples(0.05)
        click = svf(noise(m, f"{tag}-click"), 3000, q=1.5, mode="band") * decay(m, 0.03)
        place(out, click * 0.8, 0)
        place(out, _voice(a, samples(0.18), f, tag) * 0.7, samples(0.04))
        tail = _voice(b, samples(0.5), f, tag) * 0.4
        place(out, tail * (1 + 0.5 * sine(14, len(tail))), samples(0.18))
        return out
    if verb == "blast":
        out = np.zeros(samples(0.7))
        rise = samples(0.18)
        place(out, _voice(a, rise, f * 1.5, tag) * 0.5, 0)
        place(out, _voice(b, samples(0.5), f, tag), rise)
        place(out, _voice("burst", samples(0.4), f / 2, tag) * 0.8, rise)
        return out
    if verb == "dash":
        out = np.zeros(samples(0.5))
        place(out, _voice(a, samples(0.18), f, tag), 0)
        place(out, _voice(b, samples(0.3), f * 2, tag) * 0.8, samples(0.12))
        return out
    if verb == "field":
        n = samples(0.8)
        swell = envelope(n, 0.15, 0.2, 0.7, 0.3)
        held = _voice(a, n, f, tag) * 0.5 + _voice(b, n, f * 0.75, tag) * 0.6
        return held * swell * (1 + 0.35 * sine(7, n))
    if verb == "shield":
        out = np.zeros(samples(0.7))
        place(out, _bulwark_up() * 0.6, 0)
        other = a if a != "bulwark" else b
        place(out, _voice(other, samples(0.4), f, tag) * 0.6, samples(0.05))
        place(out, _voice("bulwark", samples(0.6), f, tag) * 0.5, samples(0.1))
        return out
    if verb == "pull":
        n = samples(0.6)
        inward = _voice(a, n, f, tag) * 0.6 + _voice(b, n, f, tag) * 0.6
        return svf(inward, sweep(600, 4000, n), q=1.6) * envelope(n, 0.15, 0.1, 0.8, 0.1)
    # rewind: the ingredients played backwards, a tape spun back
    out = _shape("dash", a, b, f, tag)
    return out[::-1] * envelope(len(out), 0.05, 0.1, 0.9, 0.02)


def _rarity(out: np.ndarray, rarity: str, f: float) -> np.ndarray:
    """An epic adds a shimmer a fifth up. A legendary also ends on the motif, quick and
    high, so the best results sound like a payoff."""
    if rarity == "rare":
        return out
    n = len(out)
    shimmer = (sine(f * 3, n) + 0.4 * sine(f * 6, n)) * decay(n, n / SR * 0.6) * 0.12
    out = out + shimmer
    if rarity == "legendary":
        tail = _motif(MOTIF, 0.05, 0.18) * 0.6
        longer = np.zeros(max(n, samples(0.12) + len(tail)))
        place(longer, out, 0)
        place(longer, tail, samples(0.12))
        out = longer
    return out


# Each result: its pair (first ingredient leads), its verb and its pitch on a chord tone.
FUSED_RECIPES = {
    "arc_trail": ("blink", "spark", "dash", "B3"),
    "bolt_lance": ("spark", "blink", "bolt", "D4"),
    "chain_jump": ("spark", "blink", "chain", "F#3"),
    "shock_cone": ("spark", "burst", "blast", "B3"),
    "shock_mine": ("spark", "burst", "place", "D4"),
    "storm_aura": ("spark", "burst", "field", "F#3"),
    "impact_blink": ("blink", "burst", "dash", "A3"),
    "displacer": ("blink", "burst", "rewind", "E4"),
    "meteor": ("blink", "burst", "blast", "B2"),
    "static_guard": ("spark", "bulwark", "shield", "D4"),
    "tesla_coil": ("spark", "bulwark", "place", "F#3"),
    "capacitor_armor": ("bulwark", "spark", "shield", "B3"),
    "lodestone": ("magnet", "spark", "bolt", "B3"),
    "ion_hook": ("spark", "magnet", "bolt", "F#4"),
    "magrail": ("spark", "magnet", "pull", "D4"),
    "bastion": ("burst", "bulwark", "shield", "A3"),
    "reflector_wave": ("bulwark", "burst", "blast", "E4"),
    "fortress": ("burst", "bulwark", "field", "B2"),
    "vortex_cone": ("magnet", "burst", "pull", "F#3"),
    "implosion": ("magnet", "burst", "blast", "D3"),
    "gravity_well": ("magnet", "burst", "field", "B2"),
    "phase_guard": ("blink", "bulwark", "shield", "F#4"),
    "afterimage": ("blink", "bulwark", "dash", "D4"),
    "rewind": ("blink", "bulwark", "rewind", "B3"),
    "undertow": ("magnet", "blink", "pull", "A3"),
    "grapple": ("magnet", "blink", "dash", "E4"),
    "riptide": ("magnet", "blink", "blast", "F#3"),
    "lightning_rod": ("bulwark", "magnet", "place", "D4"),
    "shield_toss": ("bulwark", "magnet", "bolt", "B3"),
    "mirror_field": ("bulwark", "magnet", "field", "F#4"),
}


def fused_cue(power: str, rarity: str) -> Callable[[], np.ndarray]:
    a, b, verb, note = FUSED_RECIPES[power]

    def render() -> np.ndarray:
        f = hz(note)
        out = _shape(verb, a, b, f, power)
        return _rarity(out, rarity, f)

    render.__name__ = f"_fused_{power}"
    return render


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


# The menu and the Fuse screen's roll (docs/POWERS_AND_FUSION.md section 8). The stings
# climb with the rarity: a two-note rare, a three-note epic, and the full fusion swell
# under a higher motif for a legendary.
def _menu_move() -> np.ndarray:
    return _motif(("E5",), 0.0, 0.035) * 0.5


def _roll_tick() -> np.ndarray:
    return _motif(("B5",), 0.0, 0.025) * 0.6


def _fuse_rare() -> np.ndarray:
    return _motif(("B4", "E5"), 0.07, 0.18)


def _fuse_epic() -> np.ndarray:
    return _motif(("B4", "E5", "G#5"), 0.07, 0.26)


def _fuse_legendary() -> np.ndarray:
    out = _fusion()
    place(out, _motif(("E5", "G#5", "B5", "E6"), 0.08, 0.3, octave_up=False) * 0.8, 0)
    return out


MUSIC: dict[str, Callable[[], np.ndarray]] = {
    "music_hum": hum,
    "music_pulse": pulse,
    "music_arc": arc,
    "music_lead": lead,
    "music_fuse_box": fuse_box,
    "music_title": title,
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
    "sfx_boss_charge": _boss_charge,
    "sfx_ring_burst": _ring_burst,
    "sfx_quake": _quake,
    "sfx_summon": _summon,
    "sfx_overload": _overload,
    "sfx_bulwark_up": _bulwark_up,
    "sfx_bulwark_absorb": _bulwark_absorb,
    "sfx_bulwark_reflect": _bulwark_reflect,
    "sfx_magnet_field": _magnet_field,
    "sfx_magnet_crush": _magnet_crush,
    "sfx_live_wire": _live_wire,
    "sfx_volley": _volley,
    "sfx_charge": _charge,
    "sfx_charge_impact": _charge_impact,
    "sfx_spray": _spray,
    "sfx_lattice": _lattice,
    "sfx_spiral": _spiral,
    "sfx_vent": _vent,
    "sfx_phase_change": _phase_change,
    "sfx_boss_down": _boss_down,
    "sfx_pickup": _pickup,
    "sfx_unlock": _unlock,
    "sfx_fusion": _fusion,
    "sfx_confirm": _confirm,
    "sfx_deny": _deny,
    "sfx_menu_move": _menu_move,
    "sfx_roll_tick": _roll_tick,
    "sfx_fuse_rare": _fuse_rare,
    "sfx_fuse_epic": _fuse_epic,
    "sfx_fuse_legendary": _fuse_legendary,
}


def one_shot(render: Callable[[], np.ndarray]) -> np.ndarray:
    return fade_edges(render())


def _fused_cues() -> dict[str, Callable[[], np.ndarray]]:
    from overload.sim.powers import FUSED

    return {f"sfx_fused_{power}": fused_cue(power, rarity) for power, (_, rarity) in FUSED.items()}


SFX.update(_fused_cues())
