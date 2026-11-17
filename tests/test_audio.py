"""Task 11: sound is presentation only, every sound has a visual twin, and music layers
follow the campaign."""

from __future__ import annotations

import ast
from pathlib import Path

from overload.game.audio import EVENT_SOUNDS, STINGS, VISUAL_TWINS, Audio, stems_for
from overload.paths import ASSETS

SIM = Path(__file__).resolve().parents[1] / "src" / "overload" / "sim"


def emitted_event_kinds() -> set[str]:
    kinds = set()
    for path in SIM.glob("*.py"):
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            if (
                isinstance(node, ast.Call)
                and getattr(node.func, "id", "") == "Event"
                and node.args
                and isinstance(node.args[0], ast.Constant)
            ):
                kinds.add(node.args[0].value)
    return kinds | {"power_spark", "power_blink", "power_arc_trail"}


def test_every_sound_has_a_visual_twin() -> None:
    assert set(EVENT_SOUNDS) | {"protocol_boot", "fusion"} == set(VISUAL_TWINS)
    assert all(text.strip() for text in VISUAL_TWINS.values())


def test_sounds_are_bound_to_events_the_simulation_emits() -> None:
    assert set(EVENT_SOUNDS) <= emitted_event_kinds()


def test_every_bound_sound_exists() -> None:
    names = set(EVENT_SOUNDS.values()) | {"low_health", "fusion", "confirm", "deny"}
    for name in names:
        assert (ASSETS / "audio" / f"sfx_{name}.ogg").is_file(), name
    for sting in STINGS.values():
        assert (ASSETS / "audio" / f"{sting}.ogg").is_file(), sting


def test_music_layers_follow_the_campaign() -> None:
    assert stems_for("fuse_box", 1, "clear") == {"fuse_box"}
    assert stems_for("encounter", 1, "playing") == {"hum", "pulse"}
    assert stems_for("encounter", 2, "playing") == {"hum", "pulse", "arc"}
    assert stems_for("encounter", 3, "playing") == {"hum", "pulse", "arc", "lead"}
    assert stems_for("encounter", 3, "down") == {"hum"}
    assert stems_for(None, 1, "playing") == {"hum", "pulse"}  # practice


def test_muted_audio_is_inert() -> None:
    audio = Audio(enabled=False)
    audio.play("shot")
    audio.events([], None)
    audio.update("encounter", 1, "playing")
    assert not audio.enabled and not audio.sounds
