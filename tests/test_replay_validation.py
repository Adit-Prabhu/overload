"""Replay validation and CLI error handling (session/replay.py and game/app.py)."""

from __future__ import annotations

import json

import pytest

from overload.game.app import Options, play
from overload.session.replay import FORMAT, VERSION, Recording, check_campaign
from overload.sim.arena import FLOOR_ARENA, SUBSTATION, arena_id
from overload.sim.inputs import IDLE
from overload.sim.tuning import DEFAULT


def _valid_campaign_payload() -> dict:
    return {
        "format": FORMAT,
        "version": VERSION,
        "seed": 1,
        "tuning_id": DEFAULT.tuning_id(),
        "arena_id": arena_id(FLOOR_ARENA),
        "final_hash": None,
        "mode": "campaign",
        "protocols": ["lateral", "pressure"],
        "starts": [1],
        "menu": [],
        "frames": [IDLE.to_list(), IDLE.to_list()],
    }


def _valid_practice_payload() -> dict:
    return {
        "format": FORMAT,
        "version": VERSION,
        "seed": 1,
        "tuning_id": DEFAULT.tuning_id(),
        "arena_id": arena_id(SUBSTATION),
        "final_hash": None,
        "mode": "practice",
        "protocols": [],
        "starts": [],
        "menu": [],
        "frames": [IDLE.to_list()],
    }


@pytest.mark.parametrize(
    "protocols",
    [
        ["lateral", "bogus"],
        ["lateral", 123],
        ["lateral", "pressure", "spacing", "lateral"],
    ],
)
def test_check_campaign_rejects_bad_protocols_and_extra_encounters(protocols) -> None:
    recording = Recording(
        seed=1,
        tuning_id=DEFAULT.tuning_id(),
        arena_id=arena_id(FLOOR_ARENA),
        frames=[IDLE] * 5,
        mode="campaign",
        protocols=protocols,
        starts=list(range(1, len(protocols))),
    )
    with pytest.raises(ValueError):
        check_campaign(recording)


@pytest.mark.parametrize("starts", [["1"], [True], [1.5], [None]])
def test_check_campaign_rejects_non_integer_starts(starts) -> None:
    recording = Recording(
        seed=1,
        tuning_id=DEFAULT.tuning_id(),
        arena_id=arena_id(FLOOR_ARENA),
        frames=[IDLE] * 5,
        mode="campaign",
        protocols=["lateral", "pressure"],
        starts=starts,
    )
    with pytest.raises(ValueError, match="integers"):
        check_campaign(recording)


def test_play_rejects_missing_and_corrupt_replays_cleanly(tmp_path, capsys) -> None:
    missing = tmp_path / "does-not-exist.json"
    assert play(Options(headless=True, replay=missing)) == 2
    assert "Replay rejected:" in capsys.readouterr().out

    cases: list[tuple[str, str]] = [
        ("bad_json.json", "{not valid json"),
        ("not_dict.json", "[]"),
        ("wrong_version.json", json.dumps({"format": FORMAT, "version": 999})),
        ("missing_field.json", json.dumps({"format": FORMAT, "version": VERSION, "seed": 1})),
        (
            "bad_frame.json",
            json.dumps({**_valid_campaign_payload(), "frames": [["bad"]]}),
        ),
        (
            "bad_aim_str_campaign.json",
            json.dumps({**_valid_campaign_payload(), "frames": [[0, 0, "bad", 0, 0, 0, 0, 0, 0]]}),
        ),
        (
            "bad_aim_null_campaign.json",
            json.dumps({**_valid_campaign_payload(), "frames": [[0, 0, 0, None, 0, 0, 0, 0, 0]]}),
        ),
        (
            "bad_aim_str_practice.json",
            json.dumps({**_valid_practice_payload(), "frames": [[0, 0, "bad", 0, 0, 0, 0, 0, 0]]}),
        ),
        (
            "bad_aim_null_practice.json",
            json.dumps({**_valid_practice_payload(), "frames": [[0, 0, 0, None, 0, 0, 0, 0, 0]]}),
        ),
        (
            "bool_move.json",
            json.dumps(
                {**_valid_campaign_payload(), "frames": [[True, False, 0, 0, 0, 0, 0, 0, 0]]}
            ),
        ),
        (
            "float_aim.json",
            json.dumps({**_valid_campaign_payload(), "frames": [[0, 0, 1.5, 2.5, 0, 0, 0, 0, 0]]}),
        ),
        (
            "bad_flag_str.json",
            json.dumps({**_valid_campaign_payload(), "frames": [[0, 0, 0, 0, "yes", 0, 0, 0, 0]]}),
        ),
        (
            "bad_flag_int.json",
            json.dumps({**_valid_campaign_payload(), "frames": [[0, 0, 0, 0, 2, 0, 0, 0, 0]]}),
        ),
        (
            "bad_flag_float.json",
            json.dumps({**_valid_campaign_payload(), "frames": [[0, 0, 0, 0, 1.0, 0, 0, 0, 0]]}),
        ),
        (
            "bad_protocol.json",
            json.dumps({**_valid_campaign_payload(), "protocols": ["lateral", "bogus"]}),
        ),
        (
            "bad_start_type.json",
            json.dumps({**_valid_campaign_payload(), "starts": ["1"]}),
        ),
        (
            "bool_start.json",
            json.dumps({**_valid_campaign_payload(), "starts": [True]}),
        ),
        (
            "too_many_encounters.json",
            json.dumps(
                {
                    **_valid_campaign_payload(),
                    "protocols": ["lateral", "pressure", "spacing", "lateral"],
                    "starts": [1, 2, 3],
                    "frames": [IDLE.to_list()] * 4,
                }
            ),
        ),
    ]
    for name, body in cases:
        path = tmp_path / name
        path.write_text(body, encoding="utf-8")
        assert play(Options(headless=True, replay=path)) == 2, name
        assert "Replay rejected:" in capsys.readouterr().out, name
