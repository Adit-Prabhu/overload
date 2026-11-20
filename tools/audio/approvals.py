"""Which approval an audio file's manifest entry carries after a render. No audio
dependencies, so the rule is tested on every Python the game supports."""

from __future__ import annotations

PENDING = "Pending Adit's listen-through"


def approval(old_entry: dict | None, digest: str) -> str:
    """Keep Adit's approval while the file's bytes are unchanged. A changed or new sound is
    pending, since what he approved is no longer what ships."""
    if old_entry and old_entry.get("sha256") == digest and old_entry.get("approval"):
        return old_entry["approval"]
    return PENDING
