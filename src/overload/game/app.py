"""Playable client.

The simulation advances at a fixed 60 ticks per second regardless of frame rate. Each
tick reads exactly one InputFrame, either from the devices or from a replay. Rendering
and cosmetic effects use their own RNG and never feed back into the simulation.

Controls: WASD or arrows move, mouse aims, hold left click to fire, Space dodges,
R retries after going down or clearing, Esc quits.
"""

from __future__ import annotations

import math
import os
import random
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path

import pygame

from overload import __version__
from overload.art import fonts, scene
from overload.art import primitives as p
from overload.session.replay import Recording
from overload.sim import world as rules
from overload.sim.inputs import IDLE, InputFrame
from overload.sim.run import Run
from overload.sim.state import Event
from overload.sim.tuning import TICK_RATE

TICK_SECONDS = 1.0 / TICK_RATE
MAX_TICKS_PER_FRAME = 5


@dataclass
class Options:
    seed: int = 1
    headless: bool = False
    frames: int = 0
    record: Path | None = None
    replay: Path | None = None


class InputReader:
    """Turns pygame events and device state into one InputFrame per tick.

    Dodge and retry are presses, so they are latched until the next tick consumes them.
    """

    def __init__(self) -> None:
        self.quit = False
        self._dodge = False
        self._restart = False

    def handle(self, event: pygame.event.Event) -> None:
        if event.type == pygame.QUIT:
            self.quit = True
        elif event.type == pygame.KEYDOWN:
            if event.key == pygame.K_ESCAPE:
                self.quit = True
            elif event.key == pygame.K_SPACE:
                self._dodge = True
            elif event.key == pygame.K_r:
                self._restart = True

    def frame(self) -> InputFrame:
        keys = pygame.key.get_pressed()
        move_x = int(keys[pygame.K_d] or keys[pygame.K_RIGHT]) - int(
            keys[pygame.K_a] or keys[pygame.K_LEFT]
        )
        move_y = int(keys[pygame.K_s] or keys[pygame.K_DOWN]) - int(
            keys[pygame.K_w] or keys[pygame.K_UP]
        )
        aim_x, aim_y = pygame.mouse.get_pos()
        frame = InputFrame(
            move_x=move_x,
            move_y=move_y,
            aim_x=int(aim_x),
            aim_y=int(aim_y),
            fire=bool(pygame.mouse.get_pressed()[0]),
            dodge=self._dodge,
            restart=self._restart,
        )
        self._dodge = self._restart = False
        return frame


@dataclass
class Spark:
    x: float
    y: float
    vx: float
    vy: float
    life: float
    token: str


class Renderer:
    """Draws the world with the approved art. Owns only cosmetic state."""

    def __init__(self, run: Run) -> None:
        arena = run.arena
        self.size = arena.size
        self.floor, self.glow = scene.render_floor(
            arena.size, arena.bounds, arena.obstacles, "standby"
        )
        self.layer = pygame.Surface(arena.size, pygame.SRCALPHA)
        self.bloom = scene.Bloom(arena.size)
        self.stamp = f"overload {__version__} · tuning {run.tuning.tuning_id()}"
        self.cosmetic = random.Random(0)
        self.sparks: list[Spark] = []
        self.flashes: dict[int, int] = {}

    def consume(self, events: list[Event]) -> None:
        for event in events:
            if event.kind == "hostile_hit":
                self.flashes[event.ref] = 4
                self._burst(event.x, event.y, 4, "fx.flash", 3.0)
            elif event.kind == "hostile_destroyed":
                self._burst(event.x, event.y, 14, "hostile.line", 5.0)
                self._burst(event.x, event.y, 8, "power.spark", 4.0)
            elif event.kind == "player_hit":
                self._burst(event.x, event.y, 10, "player.core", 4.5)

    def _burst(self, x: float, y: float, count: int, token: str, speed: float) -> None:
        for _ in range(count):
            angle = self.cosmetic.uniform(0, math.tau)
            pace = self.cosmetic.uniform(0.4, 1.0) * speed
            self.sparks.append(
                Spark(x, y, math.cos(angle) * pace, math.sin(angle) * pace, 1.0, token)
            )

    def _update_cosmetics(self) -> None:
        for spark in self.sparks:
            spark.x += spark.vx
            spark.y += spark.vy
            spark.vx *= 0.9
            spark.vy *= 0.9
            spark.life -= 0.06
        self.sparks = [s for s in self.sparks if s.life > 0]
        self.flashes = {k: v - 1 for k, v in self.flashes.items() if v > 1}

    def draw(self, screen: pygame.Surface, run: Run, t: float, cursor: p.Point) -> None:
        world, tuning = run.world, run.tuning
        player = world.player
        self._update_cosmetics()
        screen.blit(self.floor, (0, 0))
        screen.blit(self.glow, (0, 0), special_flags=pygame.BLEND_RGB_ADD)
        scene.clear(self.layer)

        for hostile in world.hostiles:
            pos = (hostile.x, hostile.y)
            if rules.telegraphing(hostile, tuning):
                facing = math.atan2(hostile.tell_dy, hostile.tell_dx)
                scene.draw_aim_tell(
                    self.layer, pos, facing, rules.tell_progress(hostile, tuning), hostile.radius
                )
            else:
                facing = math.atan2(player.y - hostile.y, player.x - hostile.x)
            scene.draw_arc_mite(self.layer, pos, facing)
            if hostile.id in self.flashes:
                p.ring(self.layer, "fx.flash", pos, hostile.radius + 3, 2)

        for shot in world.projectiles:
            if shot.hostile:
                scene.draw_hostile_bolt(self.layer, (shot.x, shot.y))
            else:
                scene.draw_player_shot(self.layer, (shot.x, shot.y), math.atan2(shot.vy, shot.vx))

        for spark in self.sparks:
            tail = (spark.x - spark.vx * 2, spark.y - spark.vy * 2)
            p.stroke(self.layer, spark.token, [tail, (spark.x, spark.y)], 2)

        if player.dodging:
            start = (player.x - player.dodge_dx * 36, player.y - player.dodge_dy * 36)
            scene.draw_dodge_streak(self.layer, start, (player.x, player.y))
        hit_flicker = player.invulnerable > 0 and (world.tick // 4) % 2 == 0
        scene.draw_surge(
            self.layer,
            (player.x, player.y),
            math.atan2(player.aim_y, player.aim_x),
            (None, None),
            t,
            invulnerable=player.dodging or hit_flicker,
            low_charge=world.outcome == "playing" and player.charge <= 2,
        )

        screen.blit(self.layer, (0, 0))
        self.bloom.apply(screen, self.layer)

        dodge_total = tuning.dodge_ticks + tuning.dodge_cooldown
        scene.draw_hud(
            screen,
            scene.HudState(
                charge=player.charge,
                max_charge=tuning.player_max_charge,
                dodge_ready=1.0 - player.dodge_cooldown / dodge_total,
                build_stamp=self.stamp,
            ),
        )
        if world.outcome == "down":
            scene.draw_banner(screen, "SHORT CIRCUIT", "Press R to retry from the checkpoint")
        elif world.outcome == "clear":
            scene.draw_banner(screen, "SECTOR CLEAR", "Press R to run it again")
        scene.draw_reticle(screen, cursor)


def _open_window(size: tuple[int, int], headless: bool) -> pygame.Surface:
    if headless:
        return pygame.display.set_mode(size)
    flags = pygame.SCALED | pygame.RESIZABLE
    try:
        screen = pygame.display.set_mode(size, flags, vsync=1)
    except pygame.error:
        screen = pygame.display.set_mode(size, flags)
    pygame.mouse.set_visible(False)
    return screen


def play(options: Options) -> int:
    """Run the game. Returns a process exit code."""
    if options.headless:
        os.environ["SDL_VIDEODRIVER"] = "dummy"
        os.environ["SDL_AUDIODRIVER"] = "dummy"

    replay: Recording | None = Recording.load(options.replay) if options.replay else None
    seed = replay.seed if replay else options.seed
    run = Run(seed)
    if replay and replay.tuning_id != run.tuning.tuning_id():
        print(f"Replay uses tuning {replay.tuning_id}, this build is {run.tuning.tuning_id()}")
        return 2
    recording = Recording(seed=seed, tuning_id=run.tuning.tuning_id())
    scripted: Iterator[InputFrame] | None = iter(replay.frames) if replay else None

    pygame.init()
    try:
        screen = _open_window(run.arena.size, options.headless)
        pygame.display.set_caption("Overload")
        renderer = Renderer(run)
        reader = InputReader()
        clock = pygame.time.Clock()
        accumulated = 0.0
        frames = 0
        finished = False
        cursor: p.Point = (0.0, 0.0)
        while not reader.quit and not finished:
            for event in pygame.event.get():
                reader.handle(event)
            elapsed = clock.tick(240) / 1000.0
            if options.headless:
                due = 1
            else:
                accumulated = min(accumulated + elapsed, MAX_TICKS_PER_FRAME * TICK_SECONDS)
                due = int(accumulated / TICK_SECONDS)
                accumulated -= due * TICK_SECONDS
            for _ in range(due):
                if scripted is not None:
                    frame = next(scripted, None)
                    if frame is None:
                        finished = True
                        break
                else:
                    frame = reader.frame() if not options.headless else IDLE
                run.step(frame)
                recording.frames.append(frame)
                renderer.consume(run.world.events)
                if scripted is not None:
                    cursor = (frame.aim_x, frame.aim_y)
            if scripted is None:
                cursor = pygame.mouse.get_pos()
            renderer.draw(screen, run, run.world.tick / TICK_RATE, cursor)
            pygame.display.flip()
            frames += 1
            if options.frames and frames >= options.frames:
                break
    finally:
        pygame.quit()
        fonts.forget()

    recording.final_hash = run.state_hash()
    if options.record:
        recording.save(options.record)
        print(f"Recorded {len(recording.frames)} ticks to {options.record}")
    if replay is not None:
        if not finished:
            print(
                f"Replay stopped early after {len(recording.frames)} of {len(replay.frames)} "
                "ticks. Not verified."
            )
            return 3
        if replay.final_hash and replay.final_hash != recording.final_hash:
            print(f"Replay mismatch: expected {replay.final_hash}, got {recording.final_hash}")
            return 1
        print(f"Replay matched: {recording.final_hash}")
    return 0
