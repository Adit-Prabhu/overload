"""Pixel renderer for the playable game. Reads the simulation, never changes it.

Everything here is cosmetic state: the camera, animation timers, sparks, hit flashes and
dodge ghosts. It uses its own RNG, so rendering can never affect a replay.
"""

from __future__ import annotations

import math
import random
from dataclasses import dataclass
from functools import cache

import pygame

from overload import __version__
from overload.art.palette import rgb, rgba
from overload.art.pixel import actors, effects, hud, tiles
from overload.art.pixel.light import Glow
from overload.art.pixel.lighting import Lighting, pool, quantize
from overload.sim import world as rules
from overload.sim.arena import arena_id
from overload.sim.campaign import Campaign
from overload.sim.powers import COOLDOWN_KEYS, Kit
from overload.sim.run import Run
from overload.sim.state import Event

VIEW = (256, 144)
SURGE_FEET = 8  # sprite feet sit this many pixels below the body center
MITE_FEET = 5
RELAY_FEET = 7
SOCKET_TOKENS = {"spark": "spark", "blink": "blink", "arc_trail": "spark"}
NAMES = {"spark": "SPARK", "blink": "BLINK", "arc_trail": "ARC TRAIL"}
COOLDOWNS = {
    "spark": "spark_cooldown",
    "blink": "blink_cooldown",
    "arc_trail": "arc_trail_cooldown",
}
RIVAL_FEET = 19
RIVAL_FLASH = -1  # flash key for the Regulator (hostile IDs are positive)
POSES = {"pressure": "clamp", "spacing": "insulate", "lateral": "oscillate"}


@cache
def _shadow(half: int) -> pygame.Surface:
    shade = pygame.Surface((half * 2, 5), pygame.SRCALPHA)
    pygame.draw.ellipse(shade, rgba("px.outline", 120), (0, 0, half * 2, 5))
    return shade


@cache
def _orb() -> pygame.Surface:
    return pygame.transform.scale_by(effects.hostile_bolt(), 2)


@cache
def _banner_panel(width: int) -> pygame.Surface:
    panel = pygame.Surface((width, 34), pygame.SRCALPHA)
    panel.fill(rgba("px.outline", 200))
    return panel


@cache
def _flash(size: tuple[int, int], alpha: int) -> pygame.Surface:
    panel = pygame.Surface(size, pygame.SRCALPHA)
    panel.fill(rgba("fx.flash", alpha))
    return panel


@cache
def _dim(size: tuple[int, int], alpha: int = 190) -> pygame.Surface:
    panel = pygame.Surface(size, pygame.SRCALPHA)
    panel.fill(rgba("px.outline", alpha))
    return panel


def _wrap(text: str, width: int) -> list[str]:
    lines: list[str] = []
    for word in text.split():
        if lines and len(lines[-1]) + 1 + len(word) <= width:
            lines[-1] += " " + word
        else:
            lines.append(word)
    return lines


def prewarm_lights() -> None:
    """Build every light pool the view uses before the first frame, so play never stutters."""
    for strength in range(80, 101, 5):
        pool(84, "px.lamp", strength)
        pool(84, "px.lamp", strength * Lighting.TINT // 100)
    for radius, token, strength in (
        (64, "px.lamp.light", 75),
        (40, "px.lamp.light", 70),
        (12, "px.hostile.2", 45),
        (12, "player.halo", 45),
        (40, "px.hostile.2", 25),
    ):
        pool(radius, token, strength)
        pool(radius, token, strength * Lighting.TINT // 100)


@dataclass
class Spark:
    x: float
    y: float
    vx: float
    vy: float
    life: int
    token: str


class PixelView:
    def __init__(self, run: Run | Campaign) -> None:
        self.room = tiles.render_room(run.arena.room)
        self.room_size = run.arena.size
        self.glow = Glow(VIEW)
        self.lighting = Lighting(VIEW)
        self.cosmetic = random.Random(0)
        self.sparks: list[Spark] = []
        self.flashes: dict[int, int] = {}
        self.muzzle = 0
        self.ghosts: list[tuple[float, float, int]] = []
        self.blinks: list[tuple[float, float, int]] = []
        self.notice: tuple[str, int] | None = None
        self.unlock_flash = 0
        self.walking = 0
        self.last_player = (run.world.player.x, run.world.player.y)
        player = run.world.player
        self.camera = [player.x - VIEW[0] / 2, player.y - VIEW[1] / 2]
        self._clamp_camera()
        self.stamp = (
            f"overload {__version__} tuning {run.tuning.tuning_id()} arena {arena_id(run.arena)}"
        )
        prewarm_lights()

    # Camera ---------------------------------------------------------------------------

    def _clamp_camera(self) -> None:
        """Keep the view inside the room. A room smaller than the view is centered."""
        for axis in (0, 1):
            spare = self.room_size[axis] - VIEW[axis]
            if spare <= 0:
                self.camera[axis] = spare / 2
            else:
                self.camera[axis] = min(max(self.camera[axis], 0.0), float(spare))

    def camera_offset(self) -> tuple[int, int]:
        return (round(self.camera[0]), round(self.camera[1]))

    def update(self, run: Run | Campaign, cursor: tuple[int, int]) -> None:
        """Advance cosmetic state by one simulation tick. Called once per tick, never per
        rendered frame, so effects and camera behave the same at any display rate."""
        self.consume(run, run.world.events)
        self._tick_cosmetics()
        self.follow(run, cursor)

    def follow(self, run: Run | Campaign, cursor: tuple[int, int]) -> None:
        """Ease toward the player, nudged a little toward where they are aiming. In a fight
        the camera frames the player and the Regulator together, so the Regulator's tells
        stay on screen at the distances the fight is played at."""
        player = run.world.player
        lead_x = (cursor[0] - VIEW[0] / 2) * 0.15
        lead_y = (cursor[1] - VIEW[1] / 2) * 0.15
        rival = run.world.rival
        if rival is not None and rival.health > 0:
            lead_x = (rival.x - player.x) * 0.5
            lead_y = (rival.y - player.y) * 0.5
        target = (player.x + lead_x - VIEW[0] / 2, player.y + lead_y - VIEW[1] / 2)
        self.camera[0] += (target[0] - self.camera[0]) * 0.18
        self.camera[1] += (target[1] - self.camera[1]) * 0.18
        self._clamp_camera()

    # Events ---------------------------------------------------------------------------

    def consume(self, run: Run | Campaign, events: list[Event]) -> None:
        stolen: list[str] = []
        for event in events:
            if event.kind == "shot":
                self.muzzle = 3
            elif event.kind == "hostile_hit":
                self.flashes[event.ref] = 4
                self._burst(event.x, event.y, 4, "px.spark.light", 1.2)
            elif event.kind == "hostile_destroyed":
                self._burst(event.x, event.y, 14, "px.hostile.3", 1.8)
                self._burst(event.x, event.y, 8, "power.spark", 1.4)
            elif event.kind == "player_hit":
                self._burst(event.x, event.y, 10, "player.core", 1.6)
            elif event.kind == "rival_hit":
                self.flashes[RIVAL_FLASH] = 4
                self._burst(event.x, event.y, 3, "px.hostile.3", 1.2)
            elif event.kind == "rival_destroyed":
                self._burst(event.x, event.y, 30, "px.hostile.3", 2.4)
                self._burst(event.x, event.y, 18, "px.lamp.light", 2.0)
            elif event.kind == "rival_shielded":
                self._burst(event.x, event.y, 2, "ui.dim", 0.8)
            elif event.kind == "blink_from":
                self.blinks.append((event.x, event.y, 16))
                self._burst(event.x, event.y, 6, "power.blink", 1.0)
            elif event.kind == "blink_to":
                self.blinks.append((event.x, event.y, 10))
                self._burst(event.x, event.y, 8, "px.blink.light", 1.4)
            elif event.kind == "blink_rejected":
                self._burst(event.x, event.y, 4, "ui.dim", 0.6)
                self.toast("NO ROOM TO BLINK", 40)
            elif event.kind == "unlock":
                self._burst(event.x, event.y, 24, f"power.{event.power}", 2.2)
                self.unlock_flash = 12
                stolen.append(NAMES.get(event.power, event.power.upper()))
            elif event.kind == "absorb":
                self._burst(event.x, event.y, 10, f"power.{event.power}", 1.4)
            elif event.kind == "relay_from":
                self.blinks.append((event.x, event.y, 12))
            elif event.kind == "fizzle":
                self._burst(event.x, event.y, 2, "px.bot.3", 0.6)
        if stolen:
            self.toast(" AND ".join(stolen) + " STOLEN", 120)
        player = run.world.player
        moved = math.dist(self.last_player, (player.x, player.y)) > 0.1
        self.walking = self.walking + 1 if moved else 0
        self.last_player = (player.x, player.y)
        if player.dodging:
            self.ghosts.append((player.x, player.y, 10))

    def toast(self, message: str, ticks: int) -> None:
        self.notice = (message, ticks)

    def _burst(self, x: float, y: float, count: int, token: str, speed: float) -> None:
        for _ in range(count):
            angle = self.cosmetic.uniform(0, math.tau)
            pace = self.cosmetic.uniform(0.3, 1.0) * speed
            self.sparks.append(
                Spark(
                    x,
                    y,
                    math.cos(angle) * pace,
                    math.sin(angle) * pace,
                    self.cosmetic.randint(10, 18),
                    token,
                )
            )

    def _tick_cosmetics(self) -> None:
        for spark in self.sparks:
            spark.x += spark.vx
            spark.y += spark.vy
            spark.vx *= 0.88
            spark.vy *= 0.88
            spark.life -= 1
        self.sparks = [s for s in self.sparks if s.life > 0]
        self.flashes = {k: v - 1 for k, v in self.flashes.items() if v > 1}
        self.ghosts = [(x, y, life - 1) for x, y, life in self.ghosts if life > 1]
        self.blinks = [(x, y, life - 1) for x, y, life in self.blinks if life > 1]
        self.unlock_flash = max(0, self.unlock_flash - 1)
        if self.notice:
            message, ticks = self.notice
            self.notice = (message, ticks - 1) if ticks > 1 else None
        self.muzzle = max(0, self.muzzle - 1)

    # Drawing --------------------------------------------------------------------------

    def draw(self, screen: pygame.Surface, run: Run | Campaign, cursor: tuple[int, int]) -> None:
        world, tuning = run.world, run.tuning
        player = world.player
        cam = self.camera_offset()
        tick = world.tick
        t = tick / 60

        def v(x: float, y: float) -> tuple[float, float]:
            return (x - cam[0], y - cam[1])

        screen.blit(self.room.background, (-cam[0], -cam[1]))
        self.glow.clear()
        self.glow.layer.blit(self.room.light, (-cam[0], -cam[1]))

        aim = math.atan2(player.aim_y, player.aim_x)
        facing_left = player.aim_x < 0

        def shadow(x: float, y: float, half: int) -> None:
            screen.blit(_shadow(half), (round(x - half), round(y - 3)))

        def draw_at_feet(image: pygame.Surface, feet: tuple[float, float]) -> None:
            fx, fy = v(*feet)
            screen.blit(image, (round(fx - image.get_width() / 2), round(fy - image.get_height())))

        for hazard in world.hazards:
            arming = tuning.insulate_hazard_tell
            progress = 1.0 - hazard.arming / arming if hazard.arming > 0 else 1.0
            effects.hazard_tile(screen, self.glow.layer, v(hazard.x, hazard.y), progress)

        drawables = [
            (prop.base_y, lambda prop=prop: prop.draw(screen, cam)) for prop in self.room.props
        ]

        for trail in world.trails:
            effects.arc_trail(
                screen,
                self.glow.layer,
                v(trail.x1, trail.y1),
                v(trail.x2, trail.y2),
                trail.ttl / tuning.trail_ttl,
            )
        for hostile in world.hostiles:
            if hostile.kind == "relay" and hostile.phase == "blink":
                effects.relay_destination(
                    screen, v(hostile.dest_x, hostile.dest_y), rules.tell_progress(hostile, tuning)
                )
        for gx, gy, _life in self.blinks:
            effects.blink_ghost(screen, self.glow.layer, v(gx, gy))

        for hostile in world.hostiles:
            relay = hostile.kind == "relay"
            feet = (hostile.x, hostile.y + (RELAY_FEET if relay else MITE_FEET))
            charging = rules.telegraphing(hostile, tuning)
            left = hostile.tell_dx < 0 if charging else player.x < hostile.x

            def draw_machine(
                hostile=hostile, feet=feet, charging=charging, left=left, relay=relay
            ) -> None:
                shadow(*v(*feet), 7 if relay else 6)
                image = actors.relay(tick, left) if relay else actors.arc_mite(tick, left, charging)
                if hostile.id in self.flashes:
                    image = effects.tinted(image, "fx.flash")
                draw_at_feet(image, feet)

            drawables.append((feet[1], draw_machine))

        for charge in world.charges:
            effects.charge(screen, self.glow.layer, v(charge.x, charge.y), charge.kind, t)

        rival = world.rival
        if rival is not None and rival.health > 0:
            rival_feet = (rival.x, rival.y + RIVAL_FEET)
            needle = math.atan2(player.y - rival.y, player.x - rival.x)
            busy = rival.action in ("tell", "dash")
            rival_left = rival.aim_x < 0 if busy else player.x < rival.x

            def draw_rival() -> None:
                shadow(*v(*rival_feet), 18)
                image = actors.regulator(POSES[rival.protocol], rival_left, needle)
                if RIVAL_FLASH in self.flashes:
                    image = effects.tinted(image, "fx.flash")
                draw_at_feet(image, rival_feet)
                if rival.boot > 0 and (tick // 4) % 3:
                    cx, cy = v(rival.x, rival.y)
                    ring = pygame.Rect(0, 0, 40, 46)
                    ring.center = (round(cx), round(cy) + 2)
                    for surface in (screen, self.glow.layer):
                        pygame.draw.ellipse(surface, rgb("px.hostile.2"), ring, 1)
                if rival.boot > 0:
                    icon = pygame.transform.scale_by(
                        effects.protocol_icon(POSES[rival.protocol]), 2
                    )
                    top = v(rival.x, rival.y + RIVAL_FEET - image.get_height() - 12)
                    screen.blit(icon, icon.get_rect(center=(round(top[0]), round(top[1]))))

            drawables.append((rival_feet[1], draw_rival))

        surge_feet = (player.x, player.y + SURGE_FEET)
        hit_blink = player.invulnerable > 0 and (tick // 4) % 2 == 0

        def draw_surge() -> None:
            for gx, gy, life in self.ghosts:
                ghost = actors.surge("walk", tick, facing_left)
                fx, fy = v(gx, gy + SURGE_FEET)
                effects.ghost(
                    screen, ghost, (fx - ghost.get_width() / 2, fy - ghost.get_height()), life * 12
                )
            shadow(*v(*surge_feet), 5)
            state = "walk" if self.walking > 2 else "idle"
            sockets = tuple(SOCKET_TOKENS.get(slot) for slot in player.slots)
            image = actors.surge(state, tick, facing_left, sockets)
            if hit_blink:
                image = effects.tinted(image, "fx.flash")
            draw_at_feet(image, surge_feet)
            hand = v(player.x + (-3 if facing_left else 3), player.y + 1)
            caster = pygame.transform.rotate(actors.caster(), -math.degrees(aim))
            screen.blit(
                caster,
                caster.get_rect(
                    center=(round(hand[0] + player.aim_x * 4), round(hand[1] + player.aim_y * 4))
                ),
            )
            if self.muzzle:
                tip = (hand[0] + player.aim_x * 9, hand[1] + player.aim_y * 9)
                for surface in (screen, self.glow.layer):
                    pygame.draw.circle(
                        surface, rgb("player.core"), (round(tip[0]), round(tip[1])), 2
                    )

        drawables.append((surge_feet[1], draw_surge))
        for _, draw in sorted(drawables, key=lambda item: item[0]):
            draw()

        for (x, y), token, phase in self.room.leds:
            if (tick // 20 + phase) % 3:
                px, py = v(x, y)
                for surface in (screen, self.glow.layer):
                    surface.fill(rgb(token), (round(px), round(py), 1, 1))

        for hostile in world.hostiles:
            if rules.telegraphing(hostile, tuning):
                effects.aim_tell(
                    screen,
                    self.glow.layer,
                    v(hostile.x, hostile.y),
                    math.atan2(hostile.tell_dy, hostile.tell_dx),
                    rules.tell_progress(hostile, tuning),
                    reach=64,
                )
            core = v(hostile.x, hostile.y - 2)
            token = "power.blink" if hostile.kind == "relay" else "power.spark"
            self.glow.layer.fill(rgb(token), (round(core[0]) - 1, round(core[1]), 2, 2))
        if rival is not None and rival.health > 0 and rules.rival_telegraphing(rival):
            effects.aim_tell(
                screen,
                self.glow.layer,
                v(rival.x, rival.y),
                math.atan2(rival.aim_y, rival.aim_x),
                rules.rival_tell_progress(rival, tuning),
                reach=96,
            )

        for shot in world.projectiles:
            if shot.hostile and shot.radius > tuning.bolt_radius:
                orb = _orb()
                for surface in (screen, self.glow.layer):
                    surface.blit(orb, orb.get_rect(center=tuple(map(round, v(shot.x, shot.y)))))
            elif shot.hostile:
                effects.bolt(screen, self.glow.layer, v(shot.x, shot.y))
            elif shot.kind == "spark":
                effects.spark_shot(
                    screen, self.glow.layer, v(shot.x, shot.y), math.atan2(shot.vy, shot.vx)
                )
            else:
                effects.player_shot(
                    screen, self.glow.layer, v(shot.x, shot.y), math.atan2(shot.vy, shot.vx)
                )

        for spark in self.sparks:
            sx, sy = v(spark.x, spark.y)
            for surface in (screen, self.glow.layer):
                pygame.draw.line(
                    surface, rgb(spark.token), (sx, sy), (sx - spark.vx * 2, sy - spark.vy * 2), 1
                )

        self.lighting.begin()
        for i, (x, y) in enumerate(self.room.lamps):
            pulse = quantize(90 + 10 * math.sin(t * 2 + i))
            self.lighting.add(v(x, y + 24), 84, "px.lamp", pulse)
        for x, y in self.room.ceiling:
            self.lighting.add(v(x, y), 64, "px.lamp.light", 75)
        head = v(player.x + player.aim_x * 16, player.y + player.aim_y * 16)
        self.lighting.add(head, 40, "px.lamp.light", 70)
        for shot in world.projectiles:
            token = "px.hostile.2" if shot.hostile else "player.halo"
            self.lighting.add(v(shot.x, shot.y), 12, token, 45)
        for charge in world.charges:
            self.lighting.add(v(charge.x, charge.y), 12, "player.halo", 45)
        for trail in world.trails:
            mid = v((trail.x1 + trail.x2) / 2, (trail.y1 + trail.y2) / 2)
            self.lighting.add(mid, 40, "px.lamp.light", 70)
        if rival is not None and rival.health > 0:
            self.lighting.add(v(rival.x, rival.y), 40, "px.hostile.2", 25)
        self.lighting.apply(screen)
        self.glow.apply(screen)

        dodge_total = tuning.dodge_ticks + tuning.dodge_cooldown
        hud.draw(
            screen,
            hud.Hud(
                charge=player.charge,
                max_charge=tuning.player_max_charge,
                dodge_ready=1.0 - player.dodge_cooldown / dodge_total,
                sockets=tuple(slot or None for slot in player.slots),
                cooldowns=tuple(
                    min(
                        1.0,
                        player.cooldowns.get(COOLDOWN_KEYS[slot], 0)
                        / getattr(tuning, COOLDOWNS[slot]),
                    )
                    if slot
                    else 0.0
                    for slot in player.slots
                ),
                rival_health=(max(0, rival.health) / rival.max_health) if rival else None,
                rival_protocol=POSES[rival.protocol] if rival else None,
            ),
        )
        if self.unlock_flash:
            screen.blit(_flash(VIEW, self.unlock_flash * 8), (0, 0))
        if self.notice:
            message, ticks = self.notice
            if ticks > 8 or ticks % 2:
                hud.text(screen, message, (VIEW[0] // 2, 26), "power.spark", "midtop")
        stage = getattr(run, "stage", None)
        if world.outcome == "down" or (stage is None and world.outcome == "clear"):
            self._banner(screen, world.outcome)
        reticle = effects.reticle()
        screen.blit(reticle, reticle.get_rect(center=cursor))

    def draw_fuse_box(
        self,
        screen: pygame.Surface,
        encounter: int,
        ready: bool,
        message: str | None,
        kit: Kit | None = None,
        selected: int = 0,
        notice: str | None = None,
    ) -> None:
        """Between encounters: the stolen powers, the two slots and the one recipe."""
        kit = kit or Kit()
        w, h = screen.get_size()
        screen.blit(_dim(screen.get_size(), 235), (0, 0))
        hud.text(screen, "FUSE BOX", (w // 2, 3), "ui.text", "midtop")
        hud.text(screen, f"ENCOUNTER {encounter} OF 3 NEXT", (w // 2, 12), "ui.dim", "midtop")

        hud.text(screen, "POWERS", (24, 25), "ui.dim")
        if not kit.unlocked:
            hud.text(screen, "NONE STOLEN YET", (24, 36), "px.floor.3")
        for i, ability in enumerate(kit.unlocked):
            y = 36 + i * 10
            chosen = i == min(selected, len(kit.unlocked) - 1)
            if chosen:
                hud.text(screen, ">", (16, y), "px.hazard.1")
            icon = effects.charge_icon(ability)
            screen.blit(icon, icon.get_rect(midleft=(24, y + 3)))
            hud.text(screen, NAMES[ability], (36, y), "ui.text" if chosen else "ui.dim")

        hud.text(screen, "LOADOUT", (150, 25), "ui.dim")
        for i, ability in enumerate(kit.slots):
            x = 150 + i * 26
            pygame.draw.rect(screen, rgb("px.floor.3"), (x, 35, 20, 20), 1)
            hud.text(screen, "QE"[i], (x + 10, 56), "ui.dim", "midtop")
            if ability:
                icon = effects.charge_icon(ability)
                screen.blit(icon, icon.get_rect(center=(x + 10, 45)))

        hud.text(screen, "RECIPE", (150, 65), "ui.dim")
        for i, ability in enumerate(("spark", "blink", "arc_trail")):
            icon = effects.charge_icon(ability)
            screen.blit(icon, icon.get_rect(center=(156 + i * 22, 78)))
        hud.text(screen, "+", (167, 74), "ui.dim", "midtop")
        hud.text(screen, "=", (189, 74), "ui.dim", "midtop")
        if "arc_trail" in kit.unlocked:
            status, token = "FUSED", "power.blink"
        elif "spark" in kit.unlocked and "blink" in kit.unlocked:
            status, token = "F TO FUSE", "px.hazard.1"
        else:
            status, token = "STEAL BOTH", "px.floor.3"
        hud.text(screen, status, (178, 85), token, "midtop")

        lines = [(line, "px.lamp") for line in _wrap(message.upper(), 40)] if message else []
        if notice:
            lines.append((notice, "power.spark"))
        for i, (line, token) in enumerate(lines[:3]):
            hud.text(screen, line, (w // 2, 96 + i * 9), token, "midtop")
        hud.text(screen, "W S PICK   Q E EQUIP   F FUSE", (w // 2, 123), "ui.dim", "midtop")
        prompt = "ENTER TO CONTINUE" if ready else "ROUTING POWER..."
        hud.text(screen, prompt, (w // 2, 131), "px.hazard.1" if ready else "ui.dim", "midtop")

    def draw_ending(self, screen: pygame.Surface, seconds: float, retries: int, shots: int) -> None:
        w, h = screen.get_size()
        screen.blit(_dim(screen.get_size()), (0, 0))
        hud.text(screen, "SECTOR CLEAR", (w // 2, 34), "ui.text", "midtop")
        minutes, rest = divmod(int(seconds), 60)
        lines = (f"TIME {minutes:02d}:{rest:02d}", f"RETRIES {retries}", f"SHOTS {shots}")
        for i, line in enumerate(lines):
            hud.text(screen, line, (w // 2, 58 + i * 12), "ui.dim", "midtop")
        hud.text(screen, "ESC TO QUIT", (w // 2, h - 30), "px.hazard.1", "midtop")
        hud.text(screen, self.stamp, (4, h - 3), "px.floor.3", "bottomleft")

    def _banner(self, screen: pygame.Surface, outcome: str) -> None:
        w, h = screen.get_size()
        title, hint = (
            ("SHORT CIRCUIT", "R TO RETRY")
            if outcome == "down"
            else ("SECTOR CLEAR", "R TO RUN IT AGAIN")
        )
        screen.blit(_banner_panel(w), (0, h // 2 - 17))
        hud.text(screen, title, (w // 2, h // 2 - 12), "ui.text", "midtop")
        hud.text(screen, hint, (w // 2, h // 2 + 2), "px.hazard.1", "midtop")
        hud.text(screen, self.stamp, (4, h - 3), "px.floor.3", "bottomleft")
