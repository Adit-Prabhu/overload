"""Player preferences saved in a git-ignored local file (settings/prefs.json).

Pure data, no pygame (mirrors game/keybinds.py). Replays and headless runs never read or
write the file, and none of these options ever touch simulation state, RNG or replays:
music and SFX volume scale mixer output, screen shake gates the cosmetic camera jolt,
reduce flash swaps white flashes for steady outline cues (docs/ART_AND_AUDIO_DIRECTION.md
section 5), and fullscreen toggles the display mode.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from overload.paths import ROOT

PATH = ROOT / "settings" / "prefs.json"
VOLUME_STEP = 10

ROWS = (
    ("music_volume", "MUSIC VOLUME"),
    ("sfx_volume", "SFX VOLUME"),
    ("screen_shake", "SCREEN SHAKE"),
    ("reduce_flash", "REDUCE FLASH"),
    ("fullscreen", "FULLSCREEN"),
)


def _clamp_volume(value: int) -> int:
    snapped = round(value / VOLUME_STEP) * VOLUME_STEP
    return max(0, min(100, snapped))


@dataclass
class Settings:
    music_volume: int = 100
    sfx_volume: int = 100
    screen_shake: bool = True
    reduce_flash: bool = False
    fullscreen: bool = False
    path: Path | None = None  # None: never saved (tests, replays, headless)

    def __post_init__(self) -> None:
        self.music_volume = _clamp_volume(self.music_volume)
        self.sfx_volume = _clamp_volume(self.sfx_volume)

    @classmethod
    def load(cls, path: Path = PATH) -> Settings:
        """Load saved settings, falling back to defaults for any missing or damaged field."""
        prefs = cls(path=path)
        try:
            saved = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return prefs
        if not isinstance(saved, dict):
            return prefs
        if type(saved.get("music_volume")) is int:
            prefs.music_volume = _clamp_volume(saved["music_volume"])
        if type(saved.get("sfx_volume")) is int:
            prefs.sfx_volume = _clamp_volume(saved["sfx_volume"])
        if type(saved.get("screen_shake")) is bool:
            prefs.screen_shake = saved["screen_shake"]
        if type(saved.get("reduce_flash")) is bool:
            prefs.reduce_flash = saved["reduce_flash"]
        if type(saved.get("fullscreen")) is bool:
            prefs.fullscreen = saved["fullscreen"]
        return prefs

    def save(self) -> None:
        if self.path is None:
            return
        payload = {
            "music_volume": self.music_volume,
            "sfx_volume": self.sfx_volume,
            "screen_shake": self.screen_shake,
            "reduce_flash": self.reduce_flash,
            "fullscreen": self.fullscreen,
        }
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            self.path.write_text(
                json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8"
            )
        except OSError:
            pass  # a read-only checkout still runs with the preferences for this session

    def reset(self) -> None:
        self.music_volume = 100
        self.sfx_volume = 100
        self.screen_shake = True
        self.reduce_flash = False
        self.fullscreen = False
        self.save()

    def music_scale(self) -> float:
        return self.music_volume / 100.0

    def sfx_scale(self) -> float:
        return self.sfx_volume / 100.0


@dataclass
class SettingsPage:
    """Shared SETTINGS screen controller used on the title screen and the in-game menu."""

    settings: Settings = None  # type: ignore[assignment]
    row: int = 0
    notice: str = ""

    def __post_init__(self) -> None:
        if self.settings is None:
            self.settings = Settings()

    @property
    def rows(self) -> int:
        return len(ROWS) + 1

    def value_label(self, field_name: str) -> str:
        value = getattr(self.settings, field_name)
        if isinstance(value, bool):
            return "ON" if value else "OFF"
        return f"{value}%"

    def nav(self, key: str) -> tuple[str | None, bool]:
        """Handle a menu key (up, down, left, right, select, back). Returns `(sound,
        display_changed)` where `sound` is "back", "move", "confirm" or None."""
        if key == "back":
            self.notice = ""
            return "back", False
        if key in ("up", "down"):
            self.row = (self.row + (1 if key == "down" else -1)) % self.rows
            self.notice = ""
            return "move", False
        if self.row == len(ROWS):
            if key == "select":
                was_full = self.settings.fullscreen
                self.settings.reset()
                self.notice = "DEFAULT SETTINGS RESTORED"
                return "confirm", self.settings.fullscreen != was_full
            return None, False
        if key not in ("left", "right", "select"):
            return None, False
        field_name, _ = ROWS[self.row]
        self.notice = ""
        if field_name in ("music_volume", "sfx_volume"):
            current = getattr(self.settings, field_name)
            if key == "select":
                updated = (current + VOLUME_STEP) % (100 + VOLUME_STEP)
            else:
                delta = VOLUME_STEP if key == "right" else -VOLUME_STEP
                updated = _clamp_volume(current + delta)
            if updated == current:
                return "move", False
            setattr(self.settings, field_name, updated)
            self.settings.save()
            return "move", False
        updated_bool = not getattr(self.settings, field_name)
        setattr(self.settings, field_name, updated_bool)
        self.settings.save()
        return "confirm", field_name == "fullscreen"
