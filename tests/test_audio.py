"""Task 11: sound is presentation only, every sound has a visual twin, and music layers
follow the campaign."""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

from overload.game.audio import (
    EVENT_SOUNDS,
    STEMS,
    STINGS,
    VISUAL_TWINS,
    Audio,
    boot_sting,
    stems_for,
)
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
    # Power events are built as f"power_{ability}" (sim/powers.py), so list them here.
    from overload.sim.powers import ABILITIES

    return kinds | {f"power_{ability}" for ability in ABILITIES}


def test_every_sound_has_a_visual_twin() -> None:
    interface = {"protocol_boot", "fusion", "confirm", "deny", "low_health", "menu_move"}
    interface |= {"roll_tick", "fuse_rare", "fuse_epic", "fuse_legendary"}
    assert set(EVENT_SOUNDS) | interface == set(VISUAL_TWINS)
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
    assert stems_for("title", 1, "playing") == {"title"}
    assert stems_for("fuse_box", 1, "clear") == {"fuse_box"}
    assert stems_for("encounter", 1, "playing") == {"hum", "pulse"}
    assert stems_for("encounter", 2, "playing") == {"hum", "pulse", "arc"}
    assert stems_for("encounter", 3, "playing") == {"hum", "pulse", "arc", "lead"}
    assert stems_for("encounter", 3, "down") == {"hum"}
    assert stems_for("ending", 3, "clear") == {"hum", "arc", "lead"}
    assert stems_for("ending", 3, "playing") == {"hum", "arc", "lead"}
    assert stems_for(None, 1, "playing") == {"hum", "pulse"}  # practice
    assert stems_for(None, 1, "clear") == {"hum", "arc", "lead"}  # practice victory resolves


def test_muted_audio_is_inert() -> None:
    audio = Audio(enabled=False)
    audio.play("shot")
    audio.events([], None)
    audio.update("encounter", 1, "playing")
    assert not audio.enabled and not audio.sounds


def test_the_protocol_sting_plays_once_as_each_fight_starts() -> None:
    from floorbot import enter

    from overload.sim.campaign import Campaign
    from overload.sim.inputs import IDLE, InputFrame

    campaign = Campaign(1)
    enter(campaign, "s1_chamber")  # the chamber locks and the Regulator boots
    stings = []
    for _ in range(120):
        campaign.step(IDLE)
        stings.append(boot_sting(campaign.world))
    assert [s for s in stings if s] == ["sting_oscillate"]
    campaign.world.player.charge = 0
    campaign.step(IDLE)
    campaign.step(InputFrame(restart=True))
    enter(campaign, "s1_chamber")
    campaign.step(IDLE)
    assert boot_sting(campaign.world) == "sting_oscillate", "a retry restarts the fight"


# The enabled path, on the dummy audio driver -------------------------------------------------


@pytest.fixture
def live_audio():
    import os

    import pygame

    os.environ["SDL_AUDIODRIVER"] = "dummy"
    pygame.mixer.quit()
    audio = Audio(enabled=True)
    assert audio.enabled and len(audio.music) == len(STEMS)
    yield audio
    pygame.mixer.quit()


def test_layers_change_on_the_next_bar_line_and_fade(live_audio) -> None:
    from overload.game.audio import BAR_MS, LEVELS

    audio = live_audio
    audio.update("encounter", 1, "playing")
    assert audio.targets == {"hum", "pulse"}
    audio.update("fuse_box", 1, "clear")
    assert audio.targets == {"hum", "pulse"}, "a change waits for the bar line"
    audio.started -= BAR_MS  # the next bar begins
    audio.update("fuse_box", 1, "clear")
    assert audio.targets == {"fuse_box"}
    for _ in range(20):
        audio.update("fuse_box", 1, "clear")
    assert audio.volumes["fuse_box"] == pytest.approx(LEVELS["fuse_box"])
    assert audio.volumes["hum"] == 0.0


def test_tells_duck_the_music(live_audio) -> None:
    from overload.game.audio import DUCK, LEVELS

    audio = live_audio
    for _ in range(20):
        audio.update("encounter", 1, "playing")
    audio.play("mite_tell")
    for _ in range(20):
        audio.update("encounter", 1, "playing")
    assert audio.volumes["hum"] == pytest.approx(LEVELS["hum"] * DUCK)


def test_effects_never_take_a_music_channel(live_audio) -> None:
    import pygame

    audio = live_audio
    for _ in range(80):
        audio.play("regulator_defeated")
    for stem, channel in audio.music.items():
        assert channel.get_sound() is audio.sounds[f"music_{stem}"], stem
    assert pygame.mixer.get_num_channels() == 32


def test_boss_cues_signal_the_outcome_and_distinguish_the_spiral(live_audio, monkeypatch) -> None:
    from overload.sim.campaign import Campaign
    from overload.sim.state import Event

    world = Campaign(1).world
    heard = []
    monkeypatch.setattr(live_audio, "play", lambda name, _: heard.append(name))
    live_audio.events([Event(kind, 0, 0) for kind in ("phase_change", "overload")], world)
    live_audio.events([Event(kind, 0, 0) for kind in ("boss_ring", "boss_spiral")], world)
    event = Event("rival_destroyed", 0, 0)
    live_audio.events([event], world)
    world.outcome = "down"
    live_audio.events([event], world)
    assert heard == ["phase_change", "ring_burst", "spiral", "boss_down"]


def test_the_boot_sting_reaches_the_mixer(live_audio) -> None:
    import pygame
    from floorbot import enter

    from overload.sim.campaign import Campaign
    from overload.sim.inputs import IDLE

    audio = live_audio
    campaign = Campaign(1)
    enter(campaign, "s1_chamber")
    campaign.step(IDLE)
    audio.events(campaign.world.events, campaign.world)
    playing = {pygame.mixer.Channel(i).get_sound() for i in range(5, 32)}
    assert audio.sounds["sting_oscillate"] in playing


def test_every_fused_power_has_its_own_cue() -> None:
    from overload.sim.powers import FUSED

    cues = {EVENT_SOUNDS[f"power_{power}"] for power in FUSED}
    assert len(cues) == len(FUSED), "no two fused powers share a cue"
    for power in FUSED:
        assert (ASSETS / "audio" / f"sfx_fused_{power}.ogg").exists(), power


def test_a_fused_cast_is_one_sound(live_audio, monkeypatch) -> None:
    from overload.sim.state import Event

    played = []
    monkeypatch.setattr(live_audio, "play", lambda name, volume=0.7: played.append(name))

    class Quiet:
        rival = None
        outcome = "playing"

    cast = [Event("blink_from", 0, 0), Event("power_impact_blink", 0, 0), Event("blink_to", 0, 0)]
    live_audio.events(cast, Quiet())
    assert played == ["fused_impact_blink", "blink_arrive"]
    played.clear()
    live_audio.events([Event("blink_from", 0, 0), Event("blink_to", 0, 0)], Quiet())
    assert played == ["blink_depart", "blink_arrive"], "a plain Blink keeps its departure"


def test_a_base_power_in_the_other_slot_keeps_its_cast(live_audio, monkeypatch) -> None:
    """Both slots fire in one tick: a plain Burst or Blink beside a fused power keeps its
    own cast sound (the PR #58 review)."""
    from overload.sim.state import Event

    played = []
    monkeypatch.setattr(live_audio, "play", lambda name, volume=0.7: played.append(name))

    class Quiet:
        rival = None
        outcome = "playing"

    tick = [
        Event("burst", 0, 0, 0, "burst"),
        Event("power_burst", 0, 0),
        Event("lance", 0, 0),
        Event("power_bolt_lance", 0, 0, 1),
    ]
    live_audio.events(tick, Quiet())
    assert played == ["lunge", "fused_bolt_lance"]
    played.clear()
    tick = [Event("blink_from", 0, 0), Event("power_blink", 0, 0), Event("power_shock_cone", 0, 0)]
    tick.append(Event("burst", 0, 0, 0, "shock_cone"))
    live_audio.events(tick, Quiet())
    assert played == ["blink_depart", "fused_shock_cone"]


def test_vent_window_rival_hit_layers_spark_cue(live_audio, monkeypatch) -> None:
    from overload.sim.state import Event

    played = []
    monkeypatch.setattr(live_audio, "play", lambda name, volume=0.7: played.append((name, volume)))

    class Quiet:
        rival = None
        outcome = "playing"

    live_audio.events([Event("rival_hit", 0, 0, 3, "")], Quiet())
    assert played == [("regulator_hit", 0.7)]
    played.clear()
    live_audio.events([Event("rival_hit", 0, 0, 5, "vent")], Quiet())
    assert played == [("regulator_hit", 0.7), ("spark", 0.45)]


def test_impact_cues_and_mutual_kill_audio_suppression(live_audio, monkeypatch) -> None:
    from overload.sim.state import Event

    played: list[tuple[str, float]] = []
    monkeypatch.setattr(live_audio, "play", lambda name, volume=0.7: played.append((name, volume)))

    class Quiet:
        rival = None
        outcome = "playing"

    world = Quiet()
    live_audio.events(
        [
            Event("armor_absorb", 0, 0),
            Event("rival_shielded", 0, 0),
            Event("slammed", 0, 0),
        ],
        world,
    )
    assert played == [
        ("bulwark_absorb", 0.7),
        ("bulwark_absorb", 0.45),
        ("charge_impact", 0.7),
    ]

    # Mutual kill suppresses rival_destroyed, boss_reward and room_clear while keeping death.
    played.clear()
    world.outcome = "down"
    live_audio.events(
        [
            Event("rival_destroyed", 0, 0),
            Event("boss_reward", 0, 0),
            Event("room_clear", 0, 0),
            Event("player_down", 0, 0),
        ],
        world,
    )
    assert played == [("death", 0.7)]
