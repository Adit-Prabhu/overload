"""Deterministic rules: invariants, valid and invalid actions, retry and replay.

Covers implementation plan task 3. Acceptance: replaying the same seed and inputs gives an
identical state hash, and a human can play, go down and retry.
"""

import random
import subprocess
import sys

import pytest

from overload.session.replay import Recording, play
from overload.sim import world as rules
from overload.sim.arena import SUBSTATION, arena_id
from overload.sim.geometry import circle_hits_rect
from overload.sim.inputs import IDLE, InputFrame
from overload.sim.run import Run
from overload.sim.state import Projectile, state_hash
from overload.sim.tuning import DEFAULT, TICK_RATE, Tuning


def scripted_inputs(seed: int, ticks: int) -> list[InputFrame]:
    """Busy pseudo-random play: moving, aiming around, firing, dodging, powers, retrying."""
    rng = random.Random(seed)
    frames = []
    move = (0, 0)
    for tick in range(ticks):
        if tick % 20 == 0:
            move = (rng.choice((-1, 0, 1)), rng.choice((-1, 0, 1)))
        frames.append(
            InputFrame(
                move_x=move[0],
                move_y=move[1],
                aim_x=rng.randrange(0, 416),
                aim_y=rng.randrange(0, 256),
                fire=rng.random() < 0.7,
                dodge=rng.random() < 0.02,
                restart=rng.random() < 0.01,
                power_q=rng.random() < 0.05,
                power_e=rng.random() < 0.05,
            )
        )
    return frames


def run_all(seed: int, frames: list[InputFrame]) -> Run:
    run = Run(seed)
    for frame in frames:
        run.step(frame)
    return run


# Determinism and replay -------------------------------------------------------------------


def test_same_seed_and_inputs_give_identical_state() -> None:
    frames = scripted_inputs(5, 1800)
    assert run_all(11, frames).state_hash() == run_all(11, frames).state_hash()


def test_different_seed_changes_the_fight() -> None:
    frames = scripted_inputs(5, 600)
    assert run_all(11, frames).state_hash() != run_all(12, frames).state_hash()


def test_replay_round_trip(tmp_path) -> None:
    frames = scripted_inputs(9, 1200)
    original = run_all(3, frames)
    recording = Recording(
        seed=3,
        tuning_id=DEFAULT.tuning_id(),
        arena_id=arena_id(SUBSTATION),
        frames=frames,
        final_hash=original.state_hash(),
    )
    path = tmp_path / "replay.json"
    recording.save(path)
    loaded = Recording.load(path)
    assert loaded.frames == frames
    assert play(loaded).state_hash() == original.state_hash() == loaded.final_hash


def test_replay_with_other_tuning_is_refused() -> None:
    recording = Recording(
        seed=1, tuning_id="00000000", arena_id=arena_id(SUBSTATION), frames=[IDLE]
    )
    with pytest.raises(ValueError, match="tuning"):
        play(recording)


def test_replay_with_other_arena_is_refused() -> None:
    recording = Recording(seed=1, tuning_id=DEFAULT.tuning_id(), arena_id="00000000", frames=[IDLE])
    with pytest.raises(ValueError, match="arena"):
        play(recording)


def test_corrupt_replay_file_is_rejected(tmp_path) -> None:
    path = tmp_path / "bad.json"
    path.write_text('{"format": "something-else", "version": 1}', encoding="utf-8")
    with pytest.raises(ValueError):
        Recording.load(path)


def test_pinned_hashes_match_across_python_versions() -> None:
    """Known results for fixed seeds and inputs, checked on every CI Python version.

    If a deliberate rule or tuning change moves these, update them in the same PR and say so
    in its description. An unexplained change means determinism broke.
    """
    assert DEFAULT.tuning_id() == "49307b98"
    assert run_all(21, scripted_inputs(21, 5000)).state_hash() == "cb79bfa8ead2a72e"
    assert run_all(3, scripted_inputs(9, 1200)).state_hash() == "793492ff13881af2"


@pytest.mark.parametrize(
    "change",
    [
        {"drone_tell": 12},
        {"drone_recovery": 5},
        {"drone_fire_interval": 40},
        {"dodge_speed": 14.0},
        {"shot_speed": 12.0},
    ],
)
def test_unreadable_or_unsafe_tuning_is_rejected(change: dict) -> None:
    with pytest.raises(ValueError):
        Tuning(**change)


def test_simulation_does_not_import_pygame() -> None:
    code = (
        "import sys\n"
        "import overload.sim.world, overload.sim.run, overload.session.replay\n"
        "print('pygame' in sys.modules)\n"
    )
    result = subprocess.run(
        [sys.executable, "-c", code], capture_output=True, text=True, check=True
    )
    assert result.stdout.strip() == "False"


# Invariants -------------------------------------------------------------------------------


def test_invariants_hold_through_long_random_play() -> None:
    run = Run(21)
    radius = DEFAULT.player_radius
    x, y, w, h = SUBSTATION.bounds
    for frame in scripted_inputs(21, 5000):
        run.step(frame)
        player = run.world.player
        assert 0 <= player.charge <= DEFAULT.player_max_charge
        assert x + radius - 1e-9 <= player.x <= x + w - radius + 1e-9
        assert y + radius - 1e-9 <= player.y <= y + h - radius + 1e-9
        for rect in SUBSTATION.obstacles:
            assert not circle_hits_rect((player.x, player.y), radius - 1e-6, rect)
        assert player.gun_cooldown >= 0 and player.dodge_cooldown >= 0
        ids = [p.id for p in run.world.projectiles] + [h.id for h in run.world.hostiles]
        assert len(ids) == len(set(ids))


def test_tells_meet_the_readability_minimums() -> None:
    assert DEFAULT.drone_tell >= 0.40 * TICK_RATE
    assert DEFAULT.drone_fire_interval - DEFAULT.drone_tell >= DEFAULT.drone_recovery
    assert DEFAULT.drone_recovery >= 0.25 * TICK_RATE


def test_every_shot_is_preceded_by_a_full_tell() -> None:
    run = Run(4)
    tell_started: dict[int, int] = {}
    for _ in range(600):
        run.step(IDLE)
        for event in run.world.events:
            if event.kind == "tell":
                tell_started[event.ref] = run.world.tick
            elif event.kind == "bolt":
                assert event.ref in tell_started
                assert run.world.tick - tell_started[event.ref] >= DEFAULT.drone_tell
                del tell_started[event.ref]


# Valid and invalid actions ----------------------------------------------------------------


def test_holding_fire_respects_the_cooldown() -> None:
    run = Run(1)
    run.world.hostiles.clear()
    rules.spawn_drone(run.world, 380, 200)
    run.world.hostiles[0].fire_timer = 10_000
    shots = 0
    for _ in range(100):
        run.step(InputFrame(aim_x=380, aim_y=60, fire=True))
        shots += sum(1 for e in run.world.events if e.kind == "shot")
    assert shots == 100 // DEFAULT.gun_cooldown


def test_dodge_moves_farther_than_walking_and_protects() -> None:
    walk = Run(1)
    dodge = Run(1)
    for run in (walk, dodge):
        for hostile in run.world.hostiles:
            hostile.fire_timer = 10_000
    start_x = dodge.world.player.x
    dodge.step(InputFrame(move_x=1, dodge=True))
    assert dodge.world.player.dodging and dodge.world.player.protected
    walk.step(InputFrame(move_x=1))
    for _ in range(DEFAULT.dodge_ticks - 1):
        dodge.step(InputFrame(move_x=1))
        walk.step(InputFrame(move_x=1))
    assert dodge.world.player.x - start_x > walk.world.player.x - start_x


def test_dodge_during_cooldown_is_ignored() -> None:
    run = Run(1)
    run.step(InputFrame(move_x=1, dodge=True))
    for _ in range(DEFAULT.dodge_ticks + 2):
        run.step(IDLE)
    before = state_hash(run.world)
    run.step(InputFrame(dodge=True))
    assert not run.world.player.dodging
    assert not any(e.kind == "dodge" for e in run.world.events)
    assert state_hash(run.world) != before  # time still passed
    assert run.world.player.dodge_cooldown > 0


def test_cannot_fire_while_dodging() -> None:
    run = Run(1)
    run.step(InputFrame(move_x=1, dodge=True, fire=True))
    assert not any(e.kind == "shot" for e in run.world.events)


def test_restart_while_playing_does_nothing() -> None:
    run = Run(1)
    run.step(IDLE)
    before = state_hash(run.world)
    run.step(InputFrame(restart=True))
    assert run.retries == 0
    assert run.world.tick == 2
    assert state_hash(run.world) != before


def test_move_input_out_of_range_is_rejected() -> None:
    with pytest.raises(ValueError):
        InputFrame(move_x=2)


def _bolt_at_player(run: Run) -> None:
    player = run.world.player
    run.world.projectiles.append(
        Projectile(
            id=run.world.new_id(),
            x=player.x - 20,
            y=player.y,
            vx=20.0,
            vy=0.0,
            radius=DEFAULT.bolt_radius,
            damage=1,
            hostile=True,
            ttl=10,
        )
    )


def test_hit_costs_one_charge_then_grants_invulnerability() -> None:
    run = Run(1)
    for hostile in run.world.hostiles:
        hostile.fire_timer = 10_000
    _bolt_at_player(run)
    run.step(IDLE)
    assert run.world.player.charge == DEFAULT.player_max_charge - 1
    _bolt_at_player(run)
    run.step(IDLE)
    assert run.world.player.charge == DEFAULT.player_max_charge - 1


def test_dodge_passes_through_bolts() -> None:
    run = Run(1)
    run.step(InputFrame(dodge=True))
    _bolt_at_player(run)
    run.step(IDLE)
    assert run.world.player.charge == DEFAULT.player_max_charge


# Outcomes and retry -----------------------------------------------------------------------


def _drain(run: Run) -> None:
    for hostile in run.world.hostiles:
        hostile.fire_timer = 10_000
    while run.world.outcome == "playing":
        run.world.player.invulnerable = 0
        _bolt_at_player(run)
        run.step(IDLE)


def test_going_down_freezes_the_world() -> None:
    run = Run(1)
    _drain(run)
    assert run.world.outcome == "down"
    frozen = state_hash(run.world)
    run.step(InputFrame(move_x=1, fire=True))
    assert state_hash(run.world) == frozen


def test_retry_restores_the_entry_checkpoint_exactly() -> None:
    run = Run(8)
    entry = state_hash(run.world)
    _drain(run)
    run.step(InputFrame(restart=True))
    assert run.retries == 1
    assert state_hash(run.world) == entry


def test_down_takes_precedence_over_clearing_in_the_same_tick() -> None:
    run = Run(1)
    world = run.world
    target = world.hostiles[0]
    world.hostiles = [target]
    target.health = 1
    target.fire_timer = 10_000
    world.player.charge = 1
    world.projectiles.append(
        Projectile(
            id=world.new_id(),
            x=target.x - 20,
            y=target.y,
            vx=20.0,
            vy=0.0,
            radius=3.0,
            damage=1,
            hostile=False,
            ttl=10,
        )
    )
    _bolt_at_player(run)
    run.step(IDLE)
    assert not world.hostiles
    assert world.outcome == "down"


def test_destroying_every_hostile_clears_the_room() -> None:
    run = Run(1)
    for hostile in run.world.hostiles:
        hostile.health = 1
        hostile.fire_timer = 10_000
        run.world.projectiles.append(
            Projectile(
                id=run.world.new_id(),
                x=hostile.x - 20,
                y=hostile.y,
                vx=20.0,
                vy=0.0,
                radius=3.0,
                damage=1,
                hostile=False,
                ttl=10,
            )
        )
    run.step(IDLE)
    assert run.world.outcome == "clear"
