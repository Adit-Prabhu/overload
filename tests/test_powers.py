"""Task 8: stolen powers. Acceptance: the full loop works, collect, equip, fuse, use."""

from __future__ import annotations

import dataclasses
import math

import pytest
from floorbot import enter, play_campaign, skip_sector

from overload.session.replay import Recording, play
from overload.sim.arena import FLOOR_ARENA, SUBSTATION, Arena, arena_id
from overload.sim.campaign import Campaign, encounter_world
from overload.sim.inputs import IDLE, InputFrame
from overload.sim.powers import Kit, blink_destination, equip, fuse
from overload.sim.state import Charge, Trail, state_hash
from overload.sim.tuning import DEFAULT, TICK_RATE
from overload.sim.world import spawn_drone, spawn_relay, step

# A plain 160 x 120 room with one wall across the middle (x 96 to 112, y 0 to 80).
WALL = (96.0, 0.0, 16.0, 80.0)
ROOM = Arena(
    room=SUBSTATION.room,
    size=(160, 120),
    bounds=(0.0, 0.0, 160.0, 120.0),
    obstacles=(WALL,),
    player_spawn=(40.0, 40.0),
    practice_spawns=((20.0, 20.0), (140.0, 20.0)),
    rival_spawn=(140.0, 100.0),
)


def bare_world(kit: Kit | None = None, arena: Arena = ROOM):
    """The test room with the Surge and one idle Arc Mite in the far corner, so the room is
    never cleared by accident."""
    world = encounter_world(1, 1, "lateral", arena=arena, kit=kit)
    world.hostiles.clear()
    world.rival = None
    world.player.x, world.player.y = arena.player_spawn
    spawn_drone(world, 150, 110).fire_timer = 1_000_000
    return world


def kit_with(*abilities: str, slots=("", "")) -> Kit:
    return Kit(unlocked=list(abilities), fragments={a: 1 for a in abilities}, slots=list(slots))


def press(world, arena=ROOM, **fields) -> None:
    fields.setdefault("aim_x", int(world.player.x) + 40)
    fields.setdefault("aim_y", int(world.player.y))
    step(world, InputFrame(**fields), arena=arena)


# Collect -------------------------------------------------------------------------------------


def test_machines_drop_the_power_they_carry() -> None:
    world = bare_world()
    mite = spawn_drone(world, 60, 40)
    relay = spawn_relay(world, 60, 90)
    mite.health = relay.health = 0
    step(world, IDLE, arena=ROOM)
    assert sorted(c.kind for c in world.charges) == ["blink", "spark"]


def test_first_charge_unlocks_and_equips_later_ones_only_count() -> None:
    world = bare_world()
    world.charges.append(Charge(99, "spark", world.player.x, world.player.y))
    step(world, IDLE, arena=ROOM)
    assert world.unlocked == ["spark"] and world.player.slots == ["spark", ""]
    assert "unlock" in {e.kind for e in world.events}
    world.charges.append(Charge(98, "spark", world.player.x, world.player.y))
    step(world, IDLE, arena=ROOM)
    assert world.fragments == {"spark": 2} and world.unlocked == ["spark"]
    assert "absorb" in {e.kind for e in world.events}


def test_clearing_a_room_absorbs_every_charge_left() -> None:
    campaign = Campaign(1)
    world = campaign.world
    enter(campaign, "s1_hall")
    while world.active_room == "s1_hall":
        for hostile in world.hostiles:
            hostile.health = 0
        campaign.step(IDLE)
    # 3 Drones and 2 Sweepers: Spark first, then Magnet fills the other slot.
    assert world.unlocked == ["spark", "magnet"]
    assert world.fragments == {"spark": 3, "magnet": 2}
    assert world.player.slots == ["spark", "magnet"]
    assert world.charges == []


# Use -----------------------------------------------------------------------------------------


def test_spark_fires_a_heavy_bolt_on_a_cooldown() -> None:
    world = bare_world(kit_with("spark", slots=("spark", "")))
    press(world, power_q=True)
    sparks = [p for p in world.projectiles if p.kind == "spark"]
    assert len(sparks) == 1 and sparks[0].damage == DEFAULT.spark_damage
    for _ in range(DEFAULT.spark_cooldown - 1):
        press(world, power_q=True)
    assert sum(1 for e in world.events if e.kind == "power_spark") == 0
    press(world, power_q=True)
    assert "power_spark" in {e.kind for e in world.events}


def test_empty_slot_and_dodging_do_nothing() -> None:
    world = bare_world(kit_with("spark", slots=("spark", "")))
    press(world, power_e=True)
    assert not world.projectiles
    press(world, dodge=True)
    press(world, power_q=True)
    assert not any(p.kind == "spark" for p in world.projectiles)


def test_blink_lands_at_the_cursor_within_range() -> None:
    world = bare_world(kit_with("blink", slots=("blink", "")))
    world.player.x, world.player.y = 40.0, 100.0
    press(world, power_q=True, aim_x=70, aim_y=100)
    assert (world.player.x, world.player.y) == (70.0, 100.0)
    world.player.cooldowns.clear()
    press(world, power_q=True, aim_x=150, aim_y=100)
    assert world.player.x == pytest.approx(70.0 + DEFAULT.blink_distance)


def test_blink_never_crosses_a_wall_and_a_rejected_blink_costs_nothing() -> None:
    world = bare_world(kit_with("blink", slots=("blink", "")))
    world.player.x, world.player.y = 90.0, 40.0  # right against the wall
    press(world, power_q=True, aim_x=140, aim_y=40)
    assert (world.player.x, world.player.y) == (90.0, 40.0)
    assert "blink_rejected" in {e.kind for e in world.events}
    assert "power_blink" not in {e.kind for e in world.events}
    assert world.player.cooldowns == {}


def test_blink_stops_short_of_an_obstacle() -> None:
    world = bare_world(kit_with("blink", slots=("blink", "")))
    world.player.x, world.player.y = 40.0, 40.0
    spot = blink_destination(world, InputFrame(aim_x=140, aim_y=40), DEFAULT, ROOM)
    assert spot is not None and spot[0] + DEFAULT.player_radius <= WALL[0]


def test_blink_stays_inside_the_room() -> None:
    world = bare_world(kit_with("blink", slots=("blink", "")))
    world.player.x, world.player.y = 20.0, 60.0
    press(world, power_q=True, aim_x=-200, aim_y=60)
    assert world.player.x == 20.0, "nowhere valid to the left, so the Blink is rejected"


def test_arc_trail_blinks_and_leaves_a_damaging_line() -> None:
    world = bare_world(kit_with("spark", "blink", "arc_trail", slots=("arc_trail", "")))
    world.player.x, world.player.y = 30.0, 100.0
    mite = spawn_drone(world, 55, 100)
    mite.fire_timer = 10_000
    press(world, power_q=True, aim_x=80, aim_y=100)
    assert len(world.trails) == 1
    assert world.player.cooldowns["teleport"] == DEFAULT.arc_trail_cooldown - 1
    for _ in range(DEFAULT.trail_interval * 3):
        step(world, IDLE, arena=ROOM)
    assert mite.health == DEFAULT.drone_health - 3 * DEFAULT.trail_damage
    for _ in range(DEFAULT.trail_ttl):
        step(world, IDLE, arena=ROOM)
    assert world.trails == []


def test_the_boot_shield_blocks_arc_trail() -> None:
    world = encounter_world(1, 1, "lateral", kit=kit_with("spark", "blink", "arc_trail"))
    rival = world.rival
    world.trails.append(
        Trail(1, rival.x - 20, rival.y, rival.x + 20, rival.y, DEFAULT.trail_interval + 1)
    )
    step(world, IDLE)
    assert rival.health == rival.max_health
    assert "rival_shielded" in {e.kind for e in world.events}


def test_arc_trail_hurts_the_regulator_after_boot() -> None:
    world = encounter_world(1, 1, "lateral", kit=kit_with("spark", "blink", "arc_trail"))
    rival = world.rival
    rival.boot = 0
    world.trails.append(
        Trail(1, rival.x - 20, rival.y, rival.x + 20, rival.y, DEFAULT.trail_interval + 1)
    )
    step(world, IDLE)
    assert rival.health == rival.max_health - DEFAULT.trail_damage
    assert "rival_hit" in {e.kind for e in world.events}


def test_blink_and_arc_trail_share_one_cooldown() -> None:
    world = bare_world(kit_with("spark", "blink", "arc_trail", slots=("blink", "arc_trail")))
    world.player.x, world.player.y = 20.0, 100.0
    press(world, power_q=True, power_e=True, aim_x=150, aim_y=100)
    assert world.player.x == pytest.approx(20.0 + DEFAULT.blink_distance), "one jump per tick"
    assert world.trails == []
    press(world, power_e=True, aim_x=150, aim_y=100)
    assert world.trails == [], "Arc Trail waits for the Blink cooldown"


# Equip and fuse ------------------------------------------------------------------------------


def test_fusion_needs_both_ingredients_and_keeps_them() -> None:
    kit = kit_with("spark")
    assert fuse(kit, "spark", "blink", seed=1) == "missing"
    assert kit.unlocked == ["spark"], "a failed fusion changes nothing"
    kit.unlocked.append("blink")
    assert fuse(kit, "spark", "spark", seed=1) == "unsupported"
    assert fuse(kit, "blink", "spark", seed=1) == "fused"
    assert kit.unlocked[:2] == ["spark", "blink"] and len(kit.unlocked) == 3
    assert kit.fragments == {"spark": 1}, "fusing consumes nothing"
    assert fuse(kit, "spark", "blink", seed=1) == "no_charges", "a reroll needs spare charges"
    assert fuse(kit, "arc_trail", "spark", seed=1) == "unsupported", "no recursive fusion"


def test_equip_swaps_and_rejects_what_is_not_unlocked() -> None:
    kit = kit_with("spark", "blink", slots=("spark", "blink"))
    assert equip(kit, 1, "spark") and kit.slots == ["blink", "spark"]
    assert not equip(kit, 0, "arc_trail") and kit.slots == ["blink", "spark"]
    assert not equip(kit, 2, "spark")
    assert equip(kit, 0, "") and kit.slots == ["", "spark"]


def test_the_loadout_changes_any_time_the_surge_is_up() -> None:
    """Adit, Nov 17: equip and fuse whenever you want, not only in the Fuse Box."""
    campaign = Campaign(1)
    world = campaign.world
    world.unlocked = ["spark", "blink"]
    assert campaign.fuse("spark", "blink") == "fused"
    fused = world.unlocked[-1]
    assert campaign.equip(0, fused) and world.player.slots[0] == fused
    world.player.charge = 0
    campaign.step(IDLE)
    with pytest.raises(RuntimeError):  # not while down
        campaign.equip(1, "spark")


# The Relay -----------------------------------------------------------------------------------


def test_relay_marks_its_landing_before_blinking_and_aims_before_firing() -> None:
    world = encounter_world(3, 2, "lateral")
    world.rival = None
    relay = next(h for h in world.hostiles if h.kind == "relay")
    world.hostiles = [relay]
    marked = blinked = aimed = None
    for _ in range(600):
        world.player.invulnerable = 1_000
        step(world, IDLE)
        kinds = {e.kind for e in world.events if e.ref == relay.id}
        if "relay_mark" in kinds:
            marked = world.tick
            target = (relay.dest_x, relay.dest_y)
        if "relay_blink" in kinds:
            assert world.tick - marked >= 0.50 * TICK_RATE
            assert (relay.x, relay.y) == target
            blinked = aimed = world.tick
        if "shards" in kinds:
            assert aimed is not None and world.tick - aimed >= 0.40 * TICK_RATE
            return
    pytest.fail(f"no full Relay cycle (marked {marked}, blinked {blinked})")


# The campaign carries the kit -----------------------------------------------------------------


def test_the_kit_carries_over_and_a_retry_restores_the_entry_kit() -> None:
    campaign = Campaign(1)
    world = campaign.world
    world.charges.append(Charge(400, "spark", world.player.x, world.player.y))
    campaign.step(IDLE)
    skip_sector(campaign)
    assert campaign.kit.unlocked == ["spark"]
    assert campaign.fuse("spark", "blink") == "missing"
    campaign.begin_next("pressure")
    assert campaign.world.unlocked == ["spark"] and campaign.world.player.slots == ["spark", ""]
    entry = state_hash(campaign.world)
    campaign.world.charges.append(
        Charge(500, "blink", campaign.world.player.x, campaign.world.player.y)
    )
    campaign.step(IDLE)
    assert "blink" in campaign.world.unlocked
    campaign.world.player.charge = 0
    campaign.step(IDLE)
    campaign.step(InputFrame(restart=True))
    assert state_hash(campaign.world) == entry
    assert campaign.world.unlocked == ["spark"], "a retry restores the entry loadout"


def full_loop(seed: int) -> tuple[Campaign, Recording, set[str]]:
    """Steal Spark in sector 1 and Blink in sector 2, fuse and equip in the second Fuse Box,
    use both in sector 3. Real inputs throughout, so the recording replays exactly."""
    campaign = Campaign(seed)
    recording = Recording(
        seed=seed,
        tuning_id=DEFAULT.tuning_id(),
        arena_id=arena_id(FLOOR_ARENA),
        mode="campaign",
        protocols=["lateral"],
    )
    used: set[str] = set()

    def fuse_box(campaign: Campaign, recording: Recording) -> None:
        if campaign.encounter == 2:
            assert campaign.fuse("spark", "blink") == "fused"
            recording.fuse_box("fuse", "spark", "blink")
            assert campaign.equip(0, "arc_trail")
            recording.fuse_box("equip", 0, "arc_trail")
            assert campaign.equip(1, "spark")
            recording.fuse_box("equip", 1, "spark")

    original_step = campaign.step

    def step(frame: InputFrame) -> None:
        original_step(frame)
        if campaign.encounter == 3:
            used.update(e.kind for e in campaign.world.events if e.kind.startswith("power_"))

    campaign.step = step
    play_campaign(campaign, recording=recording, on_fuse_box=fuse_box)
    campaign.step = original_step
    recording.final_hash = campaign.state_hash()
    return campaign, recording, used


def test_full_loop_collect_equip_fuse_use(tmp_path) -> None:
    campaign, recording, used = full_loop(2)
    assert campaign.stage == "ending"
    assert {"spark", "blink", "arc_trail"} <= set(campaign.kit.unlocked)
    assert {"power_arc_trail", "power_spark"} <= used
    path = tmp_path / "loop.json"
    recording.save(path)
    assert play(Recording.load(path)).state_hash() == recording.final_hash
    assert recording.final_hash == "eb5a3e9d64093866", "pinned on Python 3.11 and 3.12"


@pytest.mark.parametrize(
    "menu",
    [
        [[0, "teleport", 0, "spark"]],  # unknown action
        [[3, "fuse", "a", "b"], [2, "fuse", "a", "b"]],  # out of order
        [[99, "fuse", "spark", "blink"]],  # beyond the frames
        [[5, "equip", None, "spark"]],  # slot is not an integer
        [[5, "equip", [0], "spark"]],
        [[5, "equip", 1.7, "spark"]],
        [[5, "equip", "1", "spark"]],
        [[True, "fuse", "spark", "blink"]],  # a bool is not a frame index
        [[5, "fuse", 1, "blink"]],
        [7],  # not a list
    ],
)
def test_malformed_fuse_box_actions_are_rejected(menu) -> None:
    recording = Recording(
        seed=1,
        tuning_id=DEFAULT.tuning_id(),
        arena_id=arena_id(FLOOR_ARENA),
        mode="campaign",
        protocols=["lateral"],
        frames=[IDLE] * 10,
        menu=menu,
    )
    with pytest.raises(ValueError):
        play(recording)


def test_power_tuning_guards() -> None:
    with pytest.raises(ValueError):
        dataclasses.replace(DEFAULT, spark_speed=12.0)
    with pytest.raises(ValueError):
        dataclasses.replace(DEFAULT, relay_blink_tell=10)
    with pytest.raises(ValueError):
        dataclasses.replace(DEFAULT, blink_min_distance=90.0)


def test_a_saved_file_with_a_malformed_menu_is_rejected(tmp_path) -> None:
    recording = Recording(
        seed=1,
        tuning_id=DEFAULT.tuning_id(),
        arena_id=arena_id(FLOOR_ARENA),
        mode="campaign",
        protocols=["lateral"],
        frames=[IDLE] * 10,
    )
    path = tmp_path / "r.json"
    recording.save(path)
    path.write_text(path.read_text().replace('"menu":[]', '"menu":[7, "x"]'))
    with pytest.raises(ValueError):
        play(Recording.load(path))


def test_relay_never_lands_on_the_surge() -> None:
    for seed in range(20):
        world = encounter_world(seed, 2, "lateral")
        world.rival = None
        relay = next(h for h in world.hostiles if h.kind == "relay")
        world.hostiles = [relay]
        for _ in range(400):
            world.player.invulnerable = 1_000
            world.player.x, world.player.y = relay.x + 30, relay.y  # stand in its hop range
            step(world, IDLE)
            if relay.phase == "blink":
                gap = math.dist((relay.dest_x, relay.dest_y), (world.player.x, world.player.y))
                assert gap >= relay.radius + DEFAULT.relay_landing_gap + DEFAULT.player_radius
