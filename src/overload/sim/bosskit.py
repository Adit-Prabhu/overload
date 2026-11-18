"""The chassis kits (boss rework, Nov 18, docs/BOSS_DESIGN.md): phases, phase changes, the
rotation of attacks no robot uses, and the vent window after a chassis' biggest attack.

The protocol still moves the Regulator and fires its protocol attack. A kit attack starts
only between protocol attacks (action "move"), and the protocol waits while one runs.
Deterministic, no trig at runtime, no reads of the rival model's observations.
"""

from __future__ import annotations

from overload.sim import floorplay
from overload.sim.bosses import (
    BY_KIND,
    RING,
    RING_OFFSET,
    SIX,
    SPRAY,
    SPRAY_GAPS,
    VENTS,
    WIRES,
    WIRES_GAPS,
    Boss,
    phase_for,
    turn,
)
from overload.sim.collision import move_body
from overload.sim.damage import hurt_player
from overload.sim.geometry import circles_overlap, length, normalize
from overload.sim.state import Event, Hazard, Projectile, Rival, Shockwave, Warp, World
from overload.sim.tuning import Tuning

COS20 = 0.9396926207859084
SIN20 = 0.3420201433256687


def tell_ticks(name: str, tuning: Tuning) -> int:
    """How long a kit attack's tell lasts."""
    return {
        "ring": tuning.ring_tell,
        "double_ring": tuning.ring_tell,
        "live_wire": tuning.wire_tell,
        "live_wire_twice": tuning.wire_tell,
        "volley": tuning.volley_tell,
        "quake": tuning.quake_tell,
        "double_quake": tuning.quake_tell,
        "charge": tuning.charge_tell,
        "charge_twice": tuning.charge_tell,
        "spray": tuning.spray_tell,
        "summon": tuning.summon_tell,
        "lattice": tuning.lattice_tell,
        "lattice_twice": tuning.lattice_tell,
        "spiral": tuning.spiral_tell,
        "core_spiral": tuning.spiral_tell,
    }[name]


def current_tell(rival: Rival, tuning: Tuning) -> int:
    """The length of the tell running now: a re-aimed second charge has a shorter one."""
    if rival.sig_name == "charge_twice" and rival.sig_step == 1:
        return tuning.charge_again_tell
    return tell_ticks(rival.sig_name, tuning)


def charging(rival: Rival) -> bool:
    """True while a Bull Charge is running down its lane."""
    return rival.sig_action == "active" and rival.sig_name.startswith("charge")


def lock_aim(rival: Rival, world: World) -> None:
    player = world.player
    dx, dy = normalize(player.x - rival.x, player.y - rival.y)
    rival.aim_x, rival.aim_y = (dx, dy) if (dx or dy) else (1.0, 0.0)


def shoot(world: World, x: float, y: float, dx: float, dy: float, tuning: Tuning, orb=False):
    """A hostile bolt (or a slow orb) from (x, y), heading (dx, dy)."""
    speed = tuning.orb_speed if orb else tuning.bolt_speed
    radius = tuning.orb_radius if orb else tuning.bolt_radius
    world.projectiles.append(
        Projectile(
            id=world.new_id(),
            x=x,
            y=y,
            vx=dx * speed,
            vy=dy * speed,
            radius=radius,
            damage=tuning.bolt_damage,
            hostile=True,
            ttl=tuning.orb_ttl if orb else tuning.bolt_ttl,
            kind="orb" if orb else "needle",
        )
    )


def _from_rival(world: World, rival: Rival, dx: float, dy: float, tuning: Tuning, orb=False):
    radius = tuning.orb_radius if orb else tuning.bolt_radius
    offset = rival.radius + radius + 1.0
    shoot(world, rival.x + dx * offset, rival.y + dy * offset, dx, dy, tuning, orb)


# Phases -------------------------------------------------------------------------------------


def phase_change(world: World, rival: Rival, boss: Boss, tuning: Tuning) -> bool:
    """Start the next phase if its health has crossed a threshold: shielded for a moment,
    every hostile shot wiped, the rotation back to its start. True while the change runs."""
    target = phase_for(boss, rival.health, rival.max_health)
    if target > rival.phase and rival.health > 0:
        rival.phase = target
        rival.change = tuning.phase_change
        if rival.vent:
            world.events.append(Event("vent_end", rival.x, rival.y))
        rival.vent = 0
        rival.sig_action, rival.sig_name, rival.sig_index, rival.sig_step = "idle", "", 0, 0
        rival.sig_timer = boss.phases[target - 1].every // 2
        rival.wires, rival.marks = [], []
        rival.action, rival.timer, rival.cooldown = "move", 30, 30
        world.projectiles = [shot for shot in world.projectiles if not shot.hostile]
        world.events.append(Event("phase_change", rival.x, rival.y, target))
        if boss.kind == "grid_core" and target == 2:
            world.events.append(Event("overload", rival.x, rival.y))
    if rival.change > 0:
        rival.change -= 1
        return True
    return False


def pace(rival: Rival) -> float:
    """The protocol's rest multiplier for the chassis' current phase."""
    boss = BY_KIND[rival.kind]
    if not boss.phases:
        return 1.0
    return boss.phases[rival.phase - 1].pace


# The kit ------------------------------------------------------------------------------------


def run(world: World, rival: Rival, tuning: Tuning, arena) -> bool:
    """Advance the chassis kit one tick. True while it is busy (the protocol waits)."""
    boss = BY_KIND[rival.kind]
    if not boss.phases:
        return False
    if rival.vent > 0:
        rival.vent -= 1
        if rival.vent == 0:
            world.events.append(Event("vent_end", rival.x, rival.y))
        return True
    phase = boss.phases[rival.phase - 1]
    if rival.sig_action == "idle":
        rival.sig_timer -= 1
        if rival.sig_timer > 0 or rival.action != "move":
            return False
        name = phase.rotation[rival.sig_index % len(phase.rotation)]
        rival.sig_index += 1
        if name == "summon" and not _can_summon(world, arena, tuning):
            rival.sig_timer = 30  # the room is busy: the next attack in the rotation, soon
            return False
        _begin(world, rival, name, tuning, arena)
        return True
    if rival.sig_action == "tell":
        rival.sig_timer -= 1
        if rival.sig_timer <= 0:
            _strike(world, rival, tuning, arena)
        return True
    if rival.sig_action == "active":
        _active(world, rival, tuning, arena)
        return True
    rival.sig_timer -= 1  # quiet: shots and waves still out
    if rival.sig_timer <= 0:
        rival.sig_action, rival.sig_timer = "idle", phase.every
    return True


def _begin(world: World, rival: Rival, name: str, tuning: Tuning, arena) -> None:
    rival.sig_name, rival.sig_step = name, 0
    rival.sig_action, rival.sig_timer = "tell", tell_ticks(name, tuning)
    lock_aim(rival, world)
    rival.wires, rival.marks = [], []
    if name.startswith("live_wire"):
        rival.wires = [turn(rival.aim_x, rival.aim_y, d) for d in WIRES]
    elif name == "volley":
        p = world.player
        s = tuning.volley_spread
        rival.marks = [(p.x, p.y), (p.x - s, p.y + s / 2), (p.x + s, p.y + s / 2)]
    elif name.startswith("lattice"):
        _lattice(world, rival, tuning, arena, 0, tuning.lattice_tell)
    world.events.append(Event("boss_tell", rival.x, rival.y, 0, name))


def _strike(world: World, rival: Rival, tuning: Tuning, arena) -> None:
    """The moment the tell ends."""
    name = rival.sig_name
    if name in ("ring", "double_ring"):
        for dx, dy in RING:
            _from_rival(world, rival, dx, dy, tuning)
        world.events.append(Event("boss_ring", rival.x, rival.y))
        if name == "double_ring":
            rival.sig_action, rival.sig_timer = "active", tuning.ring_gap
            return
    elif name.startswith("live_wire"):
        world.events.append(Event("live_wire", rival.x, rival.y))
        rival.sig_action, rival.sig_timer = "active", tuning.wire_active
        return
    elif name == "volley":
        for mx, my in rival.marks:
            for dx, dy in SIX:
                shoot(world, mx, my, dx, dy, tuning)
        world.events.append(Event("volley", rival.x, rival.y))
        rival.marks = []
    elif name in ("quake", "double_quake"):
        _quake(world, rival, tuning)
        if name == "double_quake":
            rival.sig_action, rival.sig_timer = "active", tuning.quake_gap
            return
    elif name.startswith("charge"):
        world.events.append(Event("charge", rival.x, rival.y))
        rival.sig_action, rival.sig_timer = "active", tuning.charge_ticks
        return
    elif name == "spray":
        for d in SPRAY:
            _from_rival(world, rival, *turn(rival.aim_x, rival.aim_y, d), tuning, orb=True)
        world.events.append(Event("spray", rival.x, rival.y))
        rival.sig_action, rival.sig_timer = "active", tuning.spray_gap
        return
    elif name == "summon":
        _summon(world, arena, tuning)
        world.events.append(Event("summon", rival.x, rival.y))
    elif name.startswith("lattice"):
        world.events.append(Event("lattice", rival.x, rival.y))
        if name == "lattice_twice":  # the other color arms while the first burns
            _lattice(world, rival, tuning, arena, 1, tuning.lattice_active + tuning.lattice_again)
            rival.sig_timer = tuning.lattice_active + tuning.lattice_again + tuning.lattice_active
        else:
            rival.sig_timer = tuning.lattice_active
        rival.sig_action = "active"
        return
    elif name in ("spiral", "core_spiral"):
        rival.spin_x, rival.spin_y = rival.aim_x, rival.aim_y
        ticks = tuning.core_spiral_ticks if name == "core_spiral" else tuning.spiral_ticks
        rival.sig_action, rival.sig_timer = "active", ticks
        world.events.append(Event("boss_spiral", rival.x, rival.y, 0, name))
        return
    _finish(world, rival, tuning)


def _active(world: World, rival: Rival, tuning: Tuning, arena) -> None:
    """Attacks that last: live lines, a charge, a spiral, the second half of a pair."""
    name = rival.sig_name
    rival.sig_timer -= 1
    if name.startswith("live_wire"):
        _wires_hurt(world, rival, tuning)
        if rival.sig_timer <= 0:
            if name == "live_wire_twice" and rival.sig_step == 0:
                rival.sig_step = 1
                rival.wires = [turn(rival.aim_x, rival.aim_y, d) for d in WIRES_GAPS]
                rival.sig_action, rival.sig_timer = "tell", tuning.wire_tell
                world.events.append(Event("boss_tell", rival.x, rival.y, 1, name))
                return
            rival.wires = []
            _finish(world, rival, tuning)
        return
    if name.startswith("charge"):
        _charge(world, rival, tuning, arena)
        return
    if name in ("spiral", "core_spiral"):
        if rival.sig_timer % tuning.spiral_gap == 0:
            sx, sy = rival.spin_x, rival.spin_y
            arms = ((sx, sy), (-sx, -sy))
            if name == "core_spiral":
                arms += ((-sy, sx), (sy, -sx))
            for dx, dy in arms:
                _from_rival(world, rival, dx, dy, tuning)
            rival.spin_x, rival.spin_y = sx * COS20 - sy * SIN20, sx * SIN20 + sy * COS20
        if rival.sig_timer <= 0:
            _finish(world, rival, tuning)
        return
    if rival.sig_timer > 0:
        return
    if name == "double_ring":
        for dx, dy in RING_OFFSET:
            _from_rival(world, rival, dx, dy, tuning)
        world.events.append(Event("boss_ring", rival.x, rival.y, 1))
    elif name == "double_quake":
        _quake(world, rival, tuning)
    elif name == "spray":
        for d in SPRAY_GAPS:
            _from_rival(world, rival, *turn(rival.aim_x, rival.aim_y, d), tuning, orb=True)
        world.events.append(Event("spray", rival.x, rival.y, 1))
    _finish(world, rival, tuning)


def _finish(world: World, rival: Rival, tuning: Tuning) -> None:
    """After an attack: vent if it was the chassis' big one, else a quiet spell."""
    if rival.sig_name in VENTS:
        ticks = tuning.core_vent_ticks if rival.sig_name == "core_spiral" else tuning.vent_ticks
        _vent(world, rival, ticks)
    rival.sig_action, rival.sig_timer = "quiet", tuning.signature_quiet


def _vent(world: World, rival: Rival, ticks: int) -> None:
    rival.vent = ticks
    world.events.append(Event("vent", rival.x, rival.y, ticks))


def _quake(world: World, rival: Rival, tuning: Tuning) -> None:
    world.shockwaves.append(
        Shockwave(world.new_id(), rival.x, rival.y, rival.radius, False, tuning.quake_reach)
    )
    world.events.append(Event("quake", rival.x, rival.y))


def wire_segments(rival: Rival, tuning: Tuning) -> list[tuple[float, float, float, float]]:
    """Live Wire's lines as segments from the crossarm outward (also for the view)."""
    reach = tuning.wire_reach
    return [
        (rival.x, rival.y, rival.x + dx * reach, rival.y + dy * reach) for dx, dy in rival.wires
    ]


def _wires_hurt(world: World, rival: Rival, tuning: Tuning) -> None:
    player = world.player
    for x1, y1, x2, y2 in wire_segments(rival, tuning):
        if _near_segment(player.x, player.y, x1, y1, x2, y2) <= (
            tuning.wire_width + tuning.player_radius
        ):
            hurt_player(world, tuning.bolt_damage, tuning)
            return


def _near_segment(px: float, py: float, x1: float, y1: float, x2: float, y2: float) -> float:
    vx, vy = x2 - x1, y2 - y1
    span = vx * vx + vy * vy
    t = 0.0 if span == 0 else max(0.0, min(1.0, ((px - x1) * vx + (py - y1) * vy) / span))
    return length(px - (x1 + vx * t), py - (y1 + vy * t))


def _charge(world: World, rival: Rival, tuning: Tuning, arena) -> None:
    """Run down the locked lane. A wall stops it hard and stuns it (its vent window). A
    second charge (phase 3) re-aims first, and its wall impact also drops debris."""
    vx, vy = rival.aim_x * tuning.charge_speed, rival.aim_y * tuning.charge_speed
    before = (rival.x, rival.y)
    rival.x, rival.y = move_body(rival.x, rival.y, vx, vy, rival.radius, arena, world)
    player = world.player
    if circles_overlap(
        (rival.x, rival.y), rival.radius, (player.x, player.y), tuning.player_radius
    ):
        hurt_player(world, tuning.rival_contact_damage, tuning)
    moved = length(rival.x - before[0], rival.y - before[1])
    hit_wall = moved < tuning.charge_speed * 0.5
    if not hit_wall and rival.sig_timer > 0:
        return
    if hit_wall:
        world.events.append(Event("charge_impact", rival.x, rival.y))
    if rival.sig_name == "charge_twice" and rival.sig_step == 0:
        rival.sig_step = 1
        lock_aim(rival, world)
        rival.sig_action, rival.sig_timer = "tell", tuning.charge_again_tell
        world.events.append(Event("boss_tell", rival.x, rival.y, 1, rival.sig_name))
        return
    if hit_wall:
        if rival.sig_name == "charge_twice":
            _debris(world, rival, tuning, arena)
        _vent(world, rival, tuning.vent_ticks)
    rival.sig_action, rival.sig_timer = "quiet", tuning.signature_quiet


def _debris(world: World, rival: Rival, tuning: Tuning, arena) -> None:
    """Three marked tiles of falling debris near the impact, at fixed offsets."""
    for ox, oy in ((-24.0, -16.0), (24.0, -16.0), (0.0, 24.0)):
        x, y = ((rival.x + ox) // 16) * 16, ((rival.y + oy) // 16) * 16
        _hazard(world, arena, rival, x, y, 16.0, tuning.lattice_tell, tuning, "debris")


def _lattice(world: World, rival: Rival, tuning: Tuning, arena, parity: int, arming: int):
    """A checkerboard of 32 px cells around the Surge, one color now and the other for the
    second Lattice. Cells are two tiles wide, so a body fits in a dark one and a dodge
    crosses one. The protocol's own tiles are swept away first, so they never cover a
    dark cell. Only cells inside the chamber burn."""
    if parity == 0:
        world.hazards = [h for h in world.hazards if h.kind != "insulate"]
    size = tuning.lattice_cell
    player = world.player
    cx, cy = int(player.x // size), int(player.y // size)
    for gy in range(cy - tuning.lattice_rows, cy + tuning.lattice_rows + 1):
        for gx in range(cx - tuning.lattice_cols, cx + tuning.lattice_cols + 1):
            if (gx + gy) % 2 == parity:
                _hazard(world, arena, rival, gx * size, gy * size, size, arming, tuning, "lattice")


def _hazard(world, arena, rival, x: float, y: float, size: float, arming: int, tuning, kind):
    center = (x + size / 2, y + size / 2)
    if not floorplay.same_room(arena, center, (rival.x, rival.y)):
        return
    world.hazards.append(Hazard(world.new_id(), x, y, size, arming, tuning.lattice_active, kind))


# Summons ------------------------------------------------------------------------------------


def summon_points(arena) -> list[tuple[float, float]]:
    """Where the Grid Core warps its drones in: either side of the chamber's middle row."""
    floor = arena.floor
    if floor is None:
        return []
    points = []
    for room in floor.rooms:
        if room.kind == "chamber" and room.sector == 3:
            x, y, w, _ = room.rect
            for tx in (x + 6, x + w - 7):
                points.append((tx * 16 + 8.0, (y + 9) * 16 + 8.0))
    return points


def _can_summon(world: World, arena, tuning: Tuning) -> bool:
    alive = sum(1 for h in world.hostiles if h.health > 0) + len(world.warps)
    return bool(summon_points(arena)) and alive < tuning.summon_cap


def _summon(world: World, arena, tuning: Tuning) -> None:
    for x, y in summon_points(arena):
        world.warps.append(Warp(world.new_id(), "drone", x, y, tuning.warp_tell))
        world.events.append(Event("warp", x, y))
