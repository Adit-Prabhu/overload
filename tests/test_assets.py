"""Manifest completeness from docs/ART_AND_AUDIO_DIRECTION.md section 6."""

import hashlib
import json
from pathlib import Path

from overload.paths import ASSETS, ROOT

MANIFEST = ASSETS / "ASSET_MANIFEST.json"
REQUIRED = {
    "id",
    "path",
    "kind",
    "creator",
    "source",
    "license",
    "license_file",
    "sha256",
    "added",
    "approval",
}


def entries() -> list[dict]:
    return json.loads(MANIFEST.read_text(encoding="utf-8"))["assets"]


def test_entries_have_required_fields() -> None:
    for entry in entries():
        missing = REQUIRED - entry.keys()
        assert not missing, f"{entry.get('id')} is missing {sorted(missing)}"
        assert all(str(entry[key]).strip() for key in REQUIRED), entry["id"]


def test_ids_are_unique() -> None:
    ids = [entry["id"] for entry in entries()]
    assert len(ids) == len(set(ids))


def test_every_asset_file_is_listed() -> None:
    listed = {entry["path"] for entry in entries()}
    on_disk = {
        str(path.relative_to(ROOT))
        for path in ASSETS.rglob("*")
        if path.is_file() and path != MANIFEST and not path.name.startswith(".")
    }
    assert not on_disk - listed, f"Unlisted asset files: {sorted(on_disk - listed)}"


def test_listed_files_exist_and_match_hashes() -> None:
    for entry in entries():
        path = ROOT / entry["path"]
        assert path.is_file(), entry["path"]
        assert (ROOT / entry["license_file"]).is_file(), entry["license_file"]
        digest = hashlib.sha256(Path(path).read_bytes()).hexdigest()
        assert digest == entry["sha256"], f"{entry['path']} changed since it was recorded"
