"""The fused powers of the pairs Bulwark and Magnet join (docs/POWERS_AND_FUSION.md section
5), first half: Spark + Bulwark, Spark + Magnet, Burst + Bulwark and Burst + Magnet. Each is
its own verb.

| Pair | Rare | Epic | Legendary |
| Spark + Bulwark (shield) | Static Guard | Tesla Coil | Capacitor Armor |
| Spark + Magnet (shot) | Lodestone | Ion Hook | Magrail |
| Burst + Bulwark (shield) | Bastion | Reflector Wave | Fortress |
| Burst + Magnet (pulse) | Vortex Cone | Implosion | Gravity Well |

Placed things live in `world.fields` beside Magnet's fields, each with its `kind`. As
everywhere else, anything that damages a robot dents the Regulator (through its shields),
nothing moves the Regulator, nothing new hurts the Surge, and everything is deterministic
and trig-free.
"""

from __future__ import annotations

from overload.sim.arena import Arena
from overload.sim.collision import move_body
from overload.sim.geometry import circles_overlap, length, normalize, segment_distance_sq
from overload.sim.inputs import InputFrame
from overload.sim.state import Device, Event, Projectile, World
from overload.sim.tuning import Tuning

# Eight directions for the Capacitor Armor's ring (exact constants, no runtime trig).
_D = 0.7071067811865476
RING = (
    (1.0, 0.0),
    (_D, _D),
    (0.0, 1.0),
    (-_D, _D),
    (-1.0, 0.0),
    (-_D, -_D),
    (0.0, -1.0),
    (_D, -_D),
)


def _spark(world: World, x: float, y: float, dx: float, dy: float, tuning: Tuning, kind="spark"):
    world.projectiles.append(
        Projectile(
            id=world.new_id(),
            x=x,
            y=y,
            vx=dx * tuning.spark_speed,
            vy=dy * tuning.spark_speed,
            radius=tuning.spark_radius,
            damage=tuning.spark_damage,
            hostile=False,
            ttl=tuning.spark_ttl,
            kind=kind,
        )
    )


def _nearest_robot(world: World, x: float, y: float, reach: float):
    near = [
        h for h in world.hostiles if h.health > 0 and length(h.x - x, h.y - y) <= reach + h.radius
    ]
    return min(near, key=lambda h: (length(h.x - x, h.y - y), h.id), default=None)


def _pull(world: World, robot, x: float, y: float, step: float, arena: Arena) -> None:
    """Drag a robot toward (x, y) by up to `step`, walls winning."""
    dx, dy = x - robot.x, y - robot.y
    distance = length(dx, dy)
    if distance <= 0.0:
        return
    step = min(step, distance)
    robot.x, robot.y = move_body(
        robot.x, robot.y, dx / distance * step, dy / distance * step, robot.radius, arena, world
    )


# Spark + Bulwark -----------------------------------------------------------------------------


def static_guard(world: World, inp: InputFrame, tuning: Tuning, arena: Arena) -> bool:  # noqa: ARG001
    """A Bulwark bubble that fires a spark at the nearest robot for every shot it eats."""
    player = world.player
    player.shield, player.shield_kind = tuning.bulwark_ticks, "static_guard"
    world.events.append(Event("bulwark_up", player.x, player.y, 0, "static_guard"))
    return True


def tesla_coil(world: World, inp: InputFrame, tuning: Tuning, arena: Arena) -> bool:
    """Plant a coil at the aim point. For its life it strikes the nearest robot every
    `coil_interval` ticks and soaks the hostile shots that hit it."""
    from overload.sim.powers import place_point

    spot = place_point(world, inp, tuning, arena, tuning.coil_range, tuning.coil_radius)
    if spot is None:
        world.events.append(
            Event("blink_rejected", world.player.x, world.player.y, 0, "tesla_coil")
        )
        return False
    world.fields.append(Device(world.new_id(), "coil", *spot, *spot, tuning.coil_ticks))
    world.events.append(Event("coil_planted", *spot))
    return True


def capacitor_armor(world: World, inp: InputFrame, tuning: Tuning, arena: Arena) -> bool:  # noqa: ARG001
    """For `capacitor_ticks`, the next `capacitor_hits` hits of any kind are absorbed. Then
    the stored charge bursts out as a ring of sparks."""
    player = world.player
    player.armor, player.armor_ticks = tuning.capacitor_hits, tuning.capacitor_ticks
    world.events.append(Event("armor_up", player.x, player.y))
    return True


def _release_armor(world: World, tuning: Tuning) -> None:
    """The stored charge bursts out: eight sparks, aimed at the nearest robots in turn (or
    in a ring when none is near)."""
    player = world.player
    near = sorted(
        (h for h in world.hostiles if h.health > 0),
        key=lambda h: (length(h.x - player.x, h.y - player.y), h.id),
    )[:4]
    for i, (dx, dy) in enumerate(RING):
        if near:
            robot = near[i % len(near)]
            dx, dy = normalize(robot.x - player.x, robot.y - player.y)
        _spark(world, player.x + dx * 8, player.y + dy * 8, dx, dy, tuning)
    player.armor = player.armor_ticks = 0
    world.events.append(Event("armor_release", player.x, player.y))


# Spark + Magnet ------------------------------------------------------------------------------


def lodestone(world: World, inp: InputFrame, tuning: Tuning, arena: Arena) -> bool:
    """A slow, heavy spark that drags the robots near its path toward it as it flies."""
    from overload.sim.aiming import launch_point

    start = launch_point(world, tuning, arena)
    if start is None:
        return False
    player = world.player
    world.projectiles.append(
        Projectile(
            id=world.new_id(),
            x=start[0],
            y=start[1],
            vx=player.aim_x * tuning.lodestone_speed,
            vy=player.aim_y * tuning.lodestone_speed,
            radius=tuning.lodestone_radius,
            damage=tuning.lodestone_damage,
            hostile=False,
            ttl=tuning.lodestone_ttl,
            kind="lodestone",
        )
    )
    return True


def ion_hook(world: World, inp: InputFrame, tuning: Tuning, arena: Arena) -> bool:
    """A fast hook spark. The first robot it hits is yanked to the Surge and stunned."""
    from overload.sim.aiming import launch_point

    start = launch_point(world, tuning, arena)
    if start is None:
        return False
    player = world.player
    world.projectiles.append(
        Projectile(
            id=world.new_id(),
            x=start[0],
            y=start[1],
            vx=player.aim_x * tuning.hook_speed,
            vy=player.aim_y * tuning.hook_speed,
            radius=tuning.spark_radius,
            damage=tuning.hook_damage,
            hostile=False,
            ttl=tuning.hook_ttl,
            kind="hook",
        )
    )
    return True


def hook_hit(world: World, robot, tuning: Tuning, arena: Arena) -> None:
    """Ion Hook's catch: the robot is dragged to beside the Surge and stunned. Walls win, so
    a robot behind cover stops at it."""
    player = world.player
    gap = robot.radius + tuning.player_radius + 2.0
    ux, uy = normalize(robot.x - player.x, robot.y - player.y)
    target = (player.x + ux * gap, player.y + uy * gap)
    for _ in range(32):  # in small steps, each under the thinnest obstacle
        if length(robot.x - target[0], robot.y - target[1]) < 1.0:
            break
        _pull(world, robot, *target, 6.0, arena)
    robot.stun = max(robot.stun, tuning.hook_stun)
    world.events.append(Event("hooked", robot.x, robot.y, robot.id))


def magrail(world: World, inp: InputFrame, tuning: Tuning, arena: Arena) -> bool:
    """An instant rail along the aim, stopped by the first wall: it pierces every body on
    the line and drags the robots along it. A robot driven into a wall takes extra damage."""
    from overload.sim.fusions import _strike, _targets
    from overload.sim.powers import _clear_path

    player = world.player
    ax, ay = player.aim_x, player.aim_y
    start = (player.x, player.y)
    reach = tuning.magrail_range
    while reach > 8.0 and not _clear_path(
        world, start, (start[0] + ax * reach, start[1] + ay * reach), arena
    ):
        reach -= 4.0
    end = (start[0] + ax * reach, start[1] + ay * reach)
    world.events.append(Event("rail", end[0], end[1], 0, "magrail"))
    for body in _targets(world):
        width = tuning.magrail_width + body.radius
        if segment_distance_sq((body.x, body.y), start, end) > width * width:
            continue
        _strike(world, body, tuning.magrail_damage)
        if getattr(body, "id", -1) == -1:
            continue  # the Regulator is never moved
        before = (body.x, body.y)
        for _ in range(4):
            body.x, body.y = move_body(
                body.x,
                body.y,
                ax * tuning.magrail_drag / 4,
                ay * tuning.magrail_drag / 4,
                body.radius,
                arena,
                world,
            )
        if length(body.x - before[0], body.y - before[1]) < tuning.magrail_drag * 0.5:
            _strike(world, body, tuning.magrail_slam)  # slammed into a wall
            world.events.append(Event("slammed", body.x, body.y, body.id))
    return True


# Burst + Bulwark -----------------------------------------------------------------------------


def bastion(world: World, inp: InputFrame, tuning: Tuning, arena: Arena) -> bool:  # noqa: ARG001
    """A Bulwark bubble that ends in a full ring blast."""
    player = world.player
    player.shield, player.shield_kind = tuning.bulwark_ticks, "bastion"
    world.events.append(Event("bulwark_up", player.x, player.y, 0, "bastion"))
    return True


def reflector_wave(world: World, inp: InputFrame, tuning: Tuning, arena: Arena) -> bool:  # noqa: ARG001
    """A wall of force rolls forward along the aim. It shoves the robots it meets and turns
    the hostile shots it meets into the Surge's sparks."""
    player = world.player
    wave = Device(
        world.new_id(),
        "wave",
        player.x,
        player.y,
        player.aim_x,
        player.aim_y,
        tuning.reflector_ticks,
    )
    world.fields.append(wave)
    world.events.append(Event("wave_out", player.x, player.y))
    return True


def fortress(world: World, inp: InputFrame, tuning: Tuning, arena: Arena) -> bool:  # noqa: ARG001
    """Plant a dome around the Surge. No hostile shot enters it, and robots touching it are
    blasted back every `fortress_interval` ticks."""
    player = world.player
    world.fields.append(
        Device(world.new_id(), "fortress", player.x, player.y, 0.0, 0.0, tuning.fortress_ticks)
    )
    world.events.append(Event("fortress_up", player.x, player.y))
    return True


# Burst + Magnet ------------------------------------------------------------------------------


def vortex_cone(world: World, inp: InputFrame, tuning: Tuning, arena: Arena) -> bool:
    """A Burst cone that pulls the robots in it toward the Surge, then pops."""
    from overload.sim.fusions import _strike, _targets

    player = world.player
    ax, ay = player.aim_x, player.aim_y

    def inside(body) -> bool:
        dx, dy = body.x - player.x, body.y - player.y
        distance = length(dx, dy)
        if distance > tuning.vortex_range + body.radius:
            return False
        return distance == 0.0 or (dx * ax + dy * ay) / distance >= tuning.burst_cos

    for body in _targets(world):
        if not inside(body):
            continue
        if getattr(body, "id", -1) != -1:
            _pull(world, body, player.x, player.y, tuning.vortex_pull, arena)
        _strike(world, body, tuning.vortex_damage)
    world.events.append(Event("burst", player.x, player.y, 0, "vortex_cone"))
    return True


def implosion(world: World, inp: InputFrame, tuning: Tuning, arena: Arena) -> bool:
    """A field at the cursor that drags robots together, then ends in a blast."""
    return _well(world, inp, tuning, arena, "implosion", tuning.implosion_ticks)


def gravity_well(world: World, inp: InputFrame, tuning: Tuning, arena: Arena) -> bool:
    """A long well at the cursor that pulls in robots, charges and hostile shots (eating the
    shots that reach its heart), then ends in a heavy blast."""
    return _well(world, inp, tuning, arena, "well", tuning.well_ticks)


def _well(world, inp, tuning, arena, kind: str, ticks: int) -> bool:
    from overload.sim.powers import place_point

    spot = place_point(world, inp, tuning, arena, tuning.well_range, tuning.charge_radius)
    if spot is None:
        world.events.append(Event("magnet_rejected", world.player.x, world.player.y))
        return False
    world.fields.append(Device(world.new_id(), kind, *spot, *spot, ticks))
    world.events.append(Event("well_open", *spot, 0, kind))
    return True


USE = {
    "static_guard": static_guard,
    "tesla_coil": tesla_coil,
    "capacitor_armor": capacitor_armor,
    "lodestone": lodestone,
    "ion_hook": ion_hook,
    "magrail": magrail,
    "bastion": bastion,
    "reflector_wave": reflector_wave,
    "fortress": fortress,
    "vortex_cone": vortex_cone,
    "implosion": implosion,
    "gravity_well": gravity_well,
}


# Every tick ----------------------------------------------------------------------------------


def tick(world: World, tuning: Tuning, arena: Arena) -> None:
    """Lodestones drag, armor runs out, robots shake off their stun."""
    for shot in world.projectiles:
        if shot.kind == "lodestone":
            for robot in world.hostiles:
                if robot.health > 0 and length(robot.x - shot.x, robot.y - shot.y) <= (
                    tuning.lodestone_reach + robot.radius
                ):
                    _pull(world, robot, shot.x, shot.y, tuning.lodestone_pull, arena)
    player = world.player
    if player.armor_ticks > 0:
        player.armor_ticks -= 1
        if player.armor_ticks == 0 or player.armor == 0:
            _release_armor(world, tuning)


def tick_object(world: World, field: Device, tuning: Tuning, arena: Arena) -> bool:
    """Advance one placed thing (not a Magnet field). False when it is gone."""
    from overload.sim.fusions import _strike, blast

    field.timer -= 1
    if field.kind == "coil":
        _soak(world, field.x, field.y, tuning.coil_radius)
        if field.timer % tuning.coil_interval == 0:
            robot = _nearest_robot(world, field.x, field.y, tuning.coil_reach)
            if robot is not None:
                world.events.append(Event("chain_from", field.x, field.y))
                world.events.append(Event("chain", robot.x, robot.y, robot.id))
                _strike(world, robot, tuning.coil_damage)
    elif field.kind == "wave":
        _roll_wave(world, field, tuning, arena)
    elif field.kind == "fortress":
        _soak(world, field.x, field.y, tuning.fortress_radius)
        if field.timer % tuning.fortress_interval == 0:
            blast(
                world,
                tuning,
                arena,
                field.x,
                field.y,
                tuning.fortress_radius,
                tuning.fortress_damage,
                tuning.fortress_knock,
                "fortress",
            )
    elif field.kind in ("implosion", "well"):
        well = field.kind == "well"
        reach = tuning.well_radius if well else tuning.implosion_radius
        pull = tuning.well_pull if well else tuning.implosion_pull
        for robot in world.hostiles:
            if robot.health > 0 and length(robot.x - field.x, robot.y - field.y) <= reach:
                _pull(world, robot, field.x, field.y, pull, arena)
        if well:
            for charge in world.charges:
                if length(charge.x - field.x, charge.y - field.y) <= reach:
                    _pull(world, charge, field.x, field.y, pull, arena)
            _drag_shots(world, field, reach, pull)
        if field.timer <= 0:
            damage = tuning.well_damage if well else tuning.implosion_damage
            radius = tuning.well_blast if well else tuning.implosion_blast
            blast(
                world,
                tuning,
                arena,
                field.x,
                field.y,
                radius,
                damage,
                tuning.burst_knock,
                "gravity_well" if well else "implosion",
            )
    return field.timer > 0


def _soak(world: World, x: float, y: float, radius: float) -> None:
    """Hostile shots that touch a coil or reach into a dome fizzle."""
    kept = []
    for shot in world.projectiles:
        if shot.hostile and circles_overlap((shot.x, shot.y), shot.radius, (x, y), radius):
            world.events.append(Event("shield_absorb", shot.x, shot.y, shot.id))
            continue
        kept.append(shot)
    world.projectiles = kept


def _drag_shots(world: World, field: Device, reach: float, pull: float) -> None:
    kept = []
    for shot in world.projectiles:
        if shot.hostile:
            dx, dy = field.x - shot.x, field.y - shot.y
            distance = length(dx, dy)
            if distance <= 8.0:
                world.events.append(Event("shield_absorb", shot.x, shot.y, shot.id))
                continue
            if distance <= reach:
                shot.x += dx / distance * pull
                shot.y += dy / distance * pull
        kept.append(shot)
    world.projectiles = kept


def _roll_wave(world: World, wave: Device, tuning: Tuning, arena: Arena) -> None:
    """The wall moves on. Robots it meets take damage once and are shoved ahead of it,
    hostile shots it meets become the Surge's sparks along its path."""
    from overload.sim.fusions import _strike
    from overload.sim.powers import knock

    dx, dy = wave.tx, wave.ty
    wave.x += dx * tuning.reflector_speed
    wave.y += dy * tuning.reflector_speed
    px, py = -dy, dx  # along the wall
    half = tuning.reflector_width / 2
    a = (wave.x + px * half, wave.y + py * half)
    b = (wave.x - px * half, wave.y - py * half)
    for robot in world.hostiles:
        reach = robot.radius + 3.0
        if robot.health > 0 and segment_distance_sq((robot.x, robot.y), a, b) <= reach * reach:
            if robot.id not in wave.hit:
                wave.hit.append(robot.id)
                _strike(world, robot, tuning.reflector_damage)
            knock(world, robot, dx, dy, tuning.reflector_speed * 2, arena)
    rival = world.rival
    if rival is not None and rival.health > 0 and -1 not in wave.hit:
        reach = rival.radius + 3.0
        if segment_distance_sq((rival.x, rival.y), a, b) <= reach * reach:
            wave.hit.append(-1)
            _strike(world, rival, tuning.reflector_damage)
    kept, turned = [], []
    for shot in world.projectiles:
        reach = shot.radius + 3.0
        if shot.hostile and segment_distance_sq((shot.x, shot.y), a, b) <= reach * reach:
            turned.append(shot)
            world.events.append(Event("shield_reflect", shot.x, shot.y, shot.id))
            continue
        kept.append(shot)
    world.projectiles = kept
    for shot in turned:  # each turned shot flies on as a spark along the wave's path
        _spark(world, shot.x, shot.y, dx, dy, tuning, "reflect")
