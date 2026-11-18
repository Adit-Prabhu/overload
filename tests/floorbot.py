"""Test helpers for the floor (overhaul): a scripted player that really walks the floor and
fights, and shortcuts that jump the campaign forward by editing state. The shortcuts are for
unit tests only. Anything replayed must use real inputs."""

from __future__ import annotations

import math
from collections import deque

from overload.rooms import PROPS, TILE, footprint_tiles
from overload.sim import floorplay
from overload.sim.campaign import Campaign
from overload.sim.collision import blocked
from overload.sim.inputs import IDLE, InputFrame

ROUTE = (
    "s1_entry", "s1_hall", "s1_bay", "s1_chamber", "fuse_1",
    "s2_entry", "s2_yard", "s2_tanks", "s2_chamber", "fuse_2",
    "s3_entry", "s3_core", "s3_bus", "s3_chamber",
)  # fmt: skip


def waypoints(campaign: Campaign) -> list[tuple[float, float]]:
    """Room centers and the door gaps between them, in walking order."""
    floor = campaign.arena.floor
    points = [floorplay.tile_center(floor.get(ROUTE[0]).center)]
    for a, b in zip(ROUTE, ROUTE[1:], strict=False):
        for door_id in (f"{a}>{b}", f"{b}>{a}"):
            x, y, w, h = next(d.rect for d in floor.doors if d.id == door_id)
            points.append(((x + w / 2) * 16, (y + h / 2) * 16))
        points.append(floorplay.tile_center(floor.get(b).center))
    return points


def solid_tiles(campaign: Campaign) -> set[tuple[int, int]]:
    room = campaign.arena.room
    solid = set()
    for y, row in enumerate(room.decor):
        for x, char in enumerate(row):
            if char in PROPS:
                size = footprint_tiles(char)
                solid |= {(x + dx, y + dy) for dx in range(size) for dy in range(size)}
    return solid


class FloorBot:
    """Walks the route along a tile path (around walls, props and locked doors), and whenever
    something hostile is around, fights it: aims at the nearest target, holds a distance band
    while strafing (or closes in when a wall is in the way), dodges as a Regulator tell ends,
    dodges out of armed hazard tiles and uses its powers now and then."""

    def __init__(self, campaign: Campaign, near: float = 70, far: float = 120) -> None:
        self.campaign = campaign
        self.points = waypoints(campaign)
        self.next = 1
        self.near, self.far = near, far
        self.props = solid_tiles(campaign)
        self.path: list[tuple[int, int]] = []
        self.goal: tuple[int, int] | None = None
        self.last = (0, 0)
        self.still = 0
        self.around = 0  # ticks left walking around a wall to its target

    def _open(self, tx: int, ty: int) -> bool:
        room = self.campaign.arena.room
        if room.is_wall(tx, ty) or (tx, ty) in self.props:
            return False
        center = (tx * TILE + TILE / 2, ty * TILE + TILE / 2)
        return not blocked(self.campaign.world, self.campaign.arena, center, 3.0)

    def _route(self, start: tuple[int, int], goal: tuple[int, int]) -> list[tuple[int, int]]:
        previous = {start: start}
        queue = deque([start])
        while queue:
            tile = queue.popleft()
            if tile == goal:
                break
            x, y = tile
            for step in ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)):
                if step not in previous and self._open(*step):
                    previous[step] = tile
                    queue.append(step)
        if goal not in previous:
            return []
        path = [goal]
        while path[-1] != start:
            path.append(previous[path[-1]])
        return path[::-1][1:]

    def _walk_to(self, point: tuple[float, float], tick: int) -> tuple[int, int]:
        player = self.campaign.world.player
        here = (int(player.x // TILE), int(player.y // TILE))
        goal = (int(point[0] // TILE), int(point[1] // TILE))
        if goal != self.goal or tick % 30 == 0 or not self.path:
            self.goal = goal
            self.path = self._route(here, goal)
        while self.path and self.path[0] == here:
            self.path.pop(0)
        tx, ty = (
            (self.path[0][0] * TILE + TILE / 2, self.path[0][1] * TILE + TILE / 2)
            if self.path
            else point
        )
        dx, dy = tx - player.x, ty - player.y
        # One axis at a time (the larger first), so corners of props never catch the body.
        if abs(dx) >= abs(dy):
            sx, sy = (0 if abs(dx) < 1.5 else (1 if dx > 0 else -1)), 0
            if sx == 0:
                sy = 0 if abs(dy) < 1.5 else (1 if dy > 0 else -1)
        else:
            sx, sy = 0, (0 if abs(dy) < 1.5 else (1 if dy > 0 else -1))
            if sy == 0:
                sx = 0 if abs(dx) < 1.5 else (1 if dx > 0 else -1)
        moved = (round(player.x), round(player.y)) != self.last
        self.last = (round(player.x), round(player.y))
        self.still = 0 if moved else self.still + 1
        if self.still > 20:  # wedged: sidestep for a moment
            sx, sy = (sy or 1) * ((tick // 40) % 2 * 2 - 1), sx
        return sx, sy

    def frame(self, tick: int) -> InputFrame:
        world = self.campaign.world
        player = world.player
        targets = [h for h in world.hostiles if h.health > 0]
        rival = world.rival
        if rival is not None and rival.health > 0:
            targets.append(rival)
        if targets:
            return self._fight(world, targets, tick)
        while self.next < len(self.points):
            px, py = self.points[self.next]
            if math.dist((player.x, player.y), (px, py)) > 6:
                break
            self.next += 1
        if self.next >= len(self.points) or world.warps:
            return IDLE
        px, py = self.points[self.next]
        sx, sy = self._walk_to((px, py), tick)
        return InputFrame(sx, sy, int(px), int(py))

    def _fight(self, world, targets, tick: int) -> InputFrame:
        player = world.player
        target = min(targets, key=lambda h: (h.x - player.x) ** 2 + (h.y - player.y) ** 2)
        dx, dy = target.x - player.x, target.y - player.y
        distance = math.sqrt(dx * dx + dy * dy) or 1.0
        ux, uy = dx / distance, dy / distance
        side = 1 if (tick // 150) % 2 == 0 else -1
        steps = max(1, int(distance / 6))
        hidden = any(
            blocked(
                world,
                self.campaign.arena,
                (player.x + dx * i / steps, player.y + dy * i / steps),
                1.5,
            )
            for i in range(1, steps)
        )
        # Hysteresis: once a wall hides the target, keep walking around it for a moment, or
        # the line of sight can flicker at a wall's end and leave the bot dithering there.
        if hidden:
            self.around = 30
        elif self.around:
            self.around -= 1
            hidden = True
        if hidden:  # a wall is in the way: walk around it toward the target
            sx, sy = self._walk_to((target.x, target.y), tick)
            mx, my = float(sx), float(sy)
        elif distance < self.near:
            mx, my = -ux, -uy
        elif distance > self.far:
            mx, my = ux, uy
        else:
            mx, my = -uy * side, ux * side
        trapped = False
        for hazard in world.hazards:
            cx, cy = hazard.x + hazard.size / 2, hazard.y + hazard.size / 2
            if abs(player.x - cx) < 16 and abs(player.y - cy) < 16:
                mx, my = player.x - cx, player.y - cy
                trapped = trapped or hazard.arming == 0
        sx = 0 if abs(mx) < 0.3 else (1 if mx > 0 else -1)
        sy = 0 if abs(my) < 0.3 else (1 if my > 0 else -1)
        rival = world.rival
        tell = rival is not None and rival.action == "tell" and rival.timer <= 4
        return InputFrame(
            sx,
            sy,
            int(target.x),
            int(target.y),
            fire=True,
            dodge=trapped or tell,
            power_q=tick % 9 == 0,
            power_e=tick % 13 == 0,
        )


def play_campaign(
    campaign: Campaign,
    protocols=("pressure", "spacing"),
    limit=60_000,
    recording=None,
    on_fuse_box=None,
):
    """Play the whole floor with the bot. In each Fuse Box, optionally run `on_fuse_box`
    (menu actions), then start the next sector in the next protocol."""
    bot = FloorBot(campaign)
    order = iter(protocols)
    for tick in range(limit):
        if campaign.stage == "fuse_box":
            if on_fuse_box is not None:
                on_fuse_box(campaign, recording)
            protocol = next(order)
            campaign.begin_next(protocol)
            if recording is not None:
                recording.begin_next(protocol)
        if campaign.stage == "ending":
            return tick
        frame = bot.frame(tick)
        if campaign.world.outcome == "down":
            frame = InputFrame(restart=True)
        campaign.step(frame)
        if recording is not None:
            recording.frames.append(frame)
    raise AssertionError(
        f"campaign stuck at stage {campaign.stage}, encounter "
        f"{campaign.encounter}, room {campaign.world.active_room!r}"
    )


def skip_sector(campaign: Campaign, tick=None) -> None:
    """Shortcut (state edit): clear the current sector's rooms and stand in its Fuse Box, so
    the next step opens the Fuse Box stage. `tick` steps the game (the campaign's own step,
    or a Session's tick so the session sees the change)."""
    world = campaign.world
    floor = campaign.arena.floor
    sector = campaign.encounter
    for room in floor.rooms:
        if room.sector == sector and room.kind in ("combat", "chamber"):
            if room.id not in world.cleared:
                world.cleared = [*world.cleared, room.id]
            floorplay.unlock(world, [d.id for d in floor.doors_of(room.id)])
    world.active_room = ""
    world.hostiles.clear()
    world.warps.clear()
    world.rival = None
    target = f"fuse_{sector}" if sector < 3 else f"s{sector}_chamber"
    world.player.x, world.player.y = floorplay.tile_center(floor.get(target).center)
    (tick or campaign.step)(IDLE)


def enter(campaign: Campaign, room_id: str, tick=None) -> None:
    """Shortcut (state edit): stand in a room's center and take one step there."""
    floor = campaign.arena.floor
    campaign.world.player.x, campaign.world.player.y = floorplay.tile_center(
        floor.get(room_id).center
    )
    (tick or campaign.step)(IDLE)


def clear_encounter(session) -> None:
    """Finish the current sector and stand in its Fuse Box (or reach the ending)."""
    skip_sector(session.campaign, session.tick)


def fuse_box_with(*abilities: str):
    """A session standing in the first Fuse Box with these powers stolen and no spares."""
    from overload.agent.selector import NeutralSelector
    from overload.game.flow import Session

    session = Session(Campaign(1), NeutralSelector())
    clear_encounter(session)
    session.campaign.world.unlocked = list(abilities)
    session.campaign.world.bank = {}
    return session
