"""Pixel renderer for the playable game. Reads the simulation, never changes it.

Everything here is cosmetic state: the camera, animation timers, sparks, hit flashes and
dodge ghosts. It uses its own RNG, so rendering can never affect a replay.
"""

from __future__ import annotations

import math
import random
from dataclasses import dataclass

import pygame

from overload import __version__
from overload.art.palette import rgb, rgba
from overload.art.pixel import actors, effects, hud, tiles
from overload.art.pixel.light import Glow
from overload.art.pixel.lighting import Lighting
from overload.sim import world as rules
from overload.sim.run import Run
from overload.sim.state import Event

VIEW = (256, 144)
SURGE_FEET = 8  # sprite feet sit this many pixels below the body center
MITE_FEET = 5


@dataclass
class Spark:
    x: float
    y: float
    vx: float
    vy: float
    life: int
    token: str


class PixelView:
    def __init__(self, run: Run) -> None:
        self.room = tiles.render_room(run.arena.room)
        self.room_size = run.arena.size
        self.glow = Glow(VIEW)
        self.lighting = Lighting(VIEW)
        self.cosmetic = random.Random(0)
        self.sparks: list[Spark] = []
        self.flashes: dict[int, int] = {}
        self.muzzle = 0
        self.ghosts: list[tuple[float, float, int]] = []
        self.walking = 0
        self.last_player = (run.world.player.x, run.world.player.y)
        player = run.world.player
        self.camera = [player.x - VIEW[0] / 2, player.y - VIEW[1] / 2]
        self._clamp_camera()
        self.stamp = f"overload {__version__} tuning {run.tuning.tuning_id()}"

    # Camera ---------------------------------------------------------------------------

    def _clamp_camera(self) -> None:
        w, h = self.room_size
        self.camera[0] = min(max(self.camera[0], 0.0), float(w - VIEW[0]))
        self.camera[1] = min(max(self.camera[1], 0.0), float(h - VIEW[1]))

    def camera_offset(self) -> tuple[int, int]:
        return (round(self.camera[0]), round(self.camera[1]))

    def follow(self, run: Run, cursor: tuple[int, int]) -> None:
        """Ease toward the player, nudged a little toward where they are aiming."""
        player = run.world.player
        lead_x = (cursor[0] - VIEW[0] / 2) * 0.15
        lead_y = (cursor[1] - VIEW[1] / 2) * 0.15
        target = (player.x + lead_x - VIEW[0] / 2, player.y + lead_y - VIEW[1] / 2)
        self.camera[0] += (target[0] - self.camera[0]) * 0.18
        self.camera[1] += (target[1] - self.camera[1]) * 0.18
        self._clamp_camera()

    # Events ---------------------------------------------------------------------------

    def consume(self, run: Run, events: list[Event]) -> None:
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
            elif event.kind == "fizzle":
                self._burst(event.x, event.y, 2, "px.bot.3", 0.6)
        player = run.world.player
        moved = math.dist(self.last_player, (player.x, player.y)) > 0.1
        self.walking = self.walking + 1 if moved else 0
        self.last_player = (player.x, player.y)
        if player.dodging:
            self.ghosts.append((player.x, player.y, 10))

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
        self.muzzle = max(0, self.muzzle - 1)

    # Drawing --------------------------------------------------------------------------

    def draw(self, screen: pygame.Surface, run: Run, cursor: tuple[int, int]) -> None:
        self._tick_cosmetics()
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
            shade = pygame.Surface((half * 2, 5), pygame.SRCALPHA)
            pygame.draw.ellipse(shade, rgba("px.outline", 120), (0, 0, half * 2, 5))
            screen.blit(shade, (round(x - half), round(y - 3)))

        def draw_at_feet(image: pygame.Surface, feet: tuple[float, float]) -> None:
            fx, fy = v(*feet)
            screen.blit(image, (round(fx - image.get_width() / 2), round(fy - image.get_height())))

        drawables = [
            (prop.base_y, lambda prop=prop: prop.draw(screen, cam)) for prop in self.room.props
        ]

        for hostile in world.hostiles:
            feet = (hostile.x, hostile.y + MITE_FEET)
            charging = rules.telegraphing(hostile, tuning)
            left = hostile.tell_dx < 0 if charging else player.x < hostile.x

            def draw_mite(hostile=hostile, feet=feet, charging=charging, left=left) -> None:
                shadow(*v(*feet), 6)
                image = actors.arc_mite(tick, left, charging)
                if hostile.id in self.flashes:
                    image = effects.tinted(image, "fx.flash")
                draw_at_feet(image, feet)

            drawables.append((feet[1], draw_mite))

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
            image = actors.surge(state, tick, facing_left)
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
            self.glow.layer.fill(rgb("power.spark"), (round(core[0]) - 1, round(core[1]), 2, 2))

        for shot in world.projectiles:
            if shot.hostile:
                effects.bolt(screen, self.glow.layer, v(shot.x, shot.y))
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
            pulse = 90 + round(10 * math.sin(t * 2 + i))
            self.lighting.add(v(x, y + 24), 84, "px.lamp", pulse)
        for x, y in self.room.ceiling:
            self.lighting.add(v(x, y), 64, "px.lamp.light", 75)
        head = v(player.x + player.aim_x * 16, player.y + player.aim_y * 16)
        self.lighting.add(head, 40, "px.lamp.light", 70)
        for shot in world.projectiles:
            token = "px.hostile.2" if shot.hostile else "player.halo"
            self.lighting.add(v(shot.x, shot.y), 12, token, 45)
        self.lighting.apply(screen)
        self.glow.apply(screen)

        dodge_total = tuning.dodge_ticks + tuning.dodge_cooldown
        hud.draw(
            screen,
            hud.Hud(
                charge=player.charge,
                max_charge=tuning.player_max_charge,
                dodge_ready=1.0 - player.dodge_cooldown / dodge_total,
            ),
        )
        if world.outcome != "playing":
            self._banner(screen, world.outcome)
        reticle = effects.reticle()
        screen.blit(reticle, reticle.get_rect(center=cursor))

    def _banner(self, screen: pygame.Surface, outcome: str) -> None:
        w, h = screen.get_size()
        title, hint = (
            ("SHORT CIRCUIT", "R TO RETRY")
            if outcome == "down"
            else ("SECTOR CLEAR", "R TO RUN IT AGAIN")
        )
        panel = pygame.Surface((w, 34), pygame.SRCALPHA)
        panel.fill(rgba("px.outline", 200))
        screen.blit(panel, (0, h // 2 - 17))
        hud.text(screen, title, (w // 2, h // 2 - 12), "ui.text", "midtop")
        hud.text(screen, hint, (w // 2, h // 2 + 2), "px.hazard.1", "midtop")
        hud.text(screen, self.stamp, (4, h - 3), "px.floor.3", "bottomleft")
