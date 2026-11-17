"""Audio technical checks (docs/ART_AND_AUDIO_DIRECTION.md): every P0 cue exists, peaks stay
at or below -1 dBFS, stems share one length and loop without a click. Decoded with the
game's own mixer, so no tools dependencies are needed."""

from __future__ import annotations

import os
from array import array
from functools import cache

import pytest

from overload.paths import ASSETS

AUDIO = ASSETS / "audio"
RATE = 44_100
LOOP_SAMPLES = 682_839  # 8 bars at 124 BPM (tools/audio/theory.py)
CEILING = round(32767 * 10 ** (-1 / 20))
MUSIC = ("music_hum", "music_pulse", "music_arc", "music_lead", "music_fuse_box")
STINGS = ("sting_clamp", "sting_insulate", "sting_oscillate")
SFX = (
    "shot", "player_hit", "dodge", "death", "low_health",
    "spark", "blink_depart", "blink_arrive", "blink_deny", "arc_trail",
    "mite_tell", "mite_zap", "relay_click", "relay_blink", "enemy_death",
    "tread", "lunge", "hazard_fill", "orb_fire", "regulator_hit", "regulator_defeated",
    "pickup", "unlock", "fusion",
)  # fmt: skip
ALL = MUSIC + STINGS + tuple(f"sfx_{name}" for name in SFX)


@pytest.fixture(scope="module", autouse=True)
def mixer():
    os.environ["SDL_AUDIODRIVER"] = "dummy"
    import pygame

    pygame.mixer.quit()  # another test may have started it in stereo
    pygame.mixer.init(frequency=RATE, size=-16, channels=1)
    assert pygame.mixer.get_init() == (RATE, -16, 1)
    yield
    pygame.mixer.quit()


@cache
def samples(name: str) -> array:
    import pygame

    raw = pygame.mixer.Sound(str(AUDIO / f"{name}.ogg")).get_raw()
    return array("h", raw)


@pytest.mark.parametrize("name", ALL)
def test_every_p0_cue_exists_and_peaks_at_or_below_minus_1_dbfs(name: str) -> None:
    data = samples(name)
    assert len(data) > 0
    assert max(max(data), -min(data)) <= CEILING, f"{name} peaks above -1 dBFS"


def test_music_stems_share_one_length() -> None:
    lengths = {name: len(samples(name)) for name in MUSIC}
    assert set(lengths.values()) == {LOOP_SAMPLES}, lengths


@pytest.mark.parametrize("name", ("music_hum", "music_arc", "music_lead", "music_fuse_box"))
def test_tonal_stems_loop_without_a_click(name: str) -> None:
    """The jump from the last sample back to the first is no bigger than the movement right
    around the loop point (the drum stem starts on a kick, a deliberate attack)."""
    data = samples(name)
    edge = list(data[-2000:]) + list(data[:2000])
    steps = sorted(abs(edge[i + 1] - edge[i]) for i in range(len(edge) - 1) if i != 1999)
    typical = steps[int(len(steps) * 0.99)]
    assert abs(data[0] - data[-1]) <= max(typical * 1.5, 64), name
