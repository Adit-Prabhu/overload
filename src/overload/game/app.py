"""Playable client.

The simulation advances at a fixed 60 ticks per second regardless of frame rate. Each
tick reads exactly one InputFrame, either from the devices or from a replay. The view is
256 x 144 pixels, scaled up by whole numbers to fit the window, with a camera that follows
the Surge. Rendering and cosmetic effects never feed back into the simulation.

Controls: WASD or arrows move, mouse aims, hold left click to fire, Space dodges,
R retries after going down, Enter continues from the Fuse Box, Esc quits.
"""

from __future__ import annotations

import os
from collections.abc import Iterator
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

import pygame

from overload.agent.client import TacticClient
from overload.agent.selector import FixedSchedule, LiveSelector, NeutralSelector, Selector
from overload.art.pixel import hud, tiles
from overload.game.flow import Session
from overload.game.view import VIEW, PixelView
from overload.paths import ROOT
from overload.session.replay import Recording, check_campaign
from overload.session.trace import TraceWriter
from overload.sim.arena import arena_id
from overload.sim.campaign import Campaign
from overload.sim.inputs import IDLE, InputFrame
from overload.sim.run import Run
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
    practice: bool = False
    condition: str | None = None  # live, fixed or off. Default: live if a service URL is set
    schedule: str = "A"
    trace: Path | None = None


class InputReader:
    """Turns pygame events and device state into one InputFrame per tick.

    Dodge and retry are presses, so they are latched until the next tick consumes them.
    The mouse is read in view pixels and converted to room pixels with the camera.
    """

    def __init__(self) -> None:
        self.quit = False
        self._dodge = False
        self._restart = False
        self._confirm = False

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
            elif event.key in (pygame.K_RETURN, pygame.K_KP_ENTER):
                self._confirm = True

    def take_confirm(self) -> bool:
        """Enter in the Fuse Box. A UI action, not simulation input."""
        pressed, self._confirm = self._confirm, False
        return pressed

    def frame(self, camera: tuple[int, int]) -> InputFrame:
        keys = pygame.key.get_pressed()
        move_x = int(keys[pygame.K_d] or keys[pygame.K_RIGHT]) - int(
            keys[pygame.K_a] or keys[pygame.K_LEFT]
        )
        move_y = int(keys[pygame.K_s] or keys[pygame.K_DOWN]) - int(
            keys[pygame.K_w] or keys[pygame.K_UP]
        )
        mouse_x, mouse_y = pygame.mouse.get_pos()
        frame = InputFrame(
            move_x=move_x,
            move_y=move_y,
            aim_x=int(mouse_x) + camera[0],
            aim_y=int(mouse_y) + camera[1],
            fire=bool(pygame.mouse.get_pressed()[0]),
            dodge=self._dodge,
            restart=self._restart,
        )
        self._dodge = self._restart = False
        return frame


def _open_window(headless: bool) -> pygame.Surface:
    if headless:
        return pygame.display.set_mode(VIEW)
    flags = pygame.SCALED | pygame.RESIZABLE
    try:
        screen = pygame.display.set_mode(VIEW, flags, vsync=1)
    except pygame.error:
        screen = pygame.display.set_mode(VIEW, flags)
    pygame.mouse.set_visible(False)
    return screen


def build_selector(options: Options) -> tuple[Selector, str | None, str]:
    """The rival condition for this run. The player is never told which one is active."""
    url = os.environ.get("OVERLOAD_RIVAL_URL")
    condition = options.condition or ("live" if url else "off")
    if condition == "fixed":
        return FixedSchedule(options.schedule), None, "fixed"
    if condition == "live":
        if not url:
            print("OVERLOAD_RIVAL_URL is not set, so the rival runs on the neutral protocol.")
            return NeutralSelector(), None, "off"
        client = TacticClient(url)
        session_id = client.start_session()
        if session_id is None:
            print("The rival service is unreachable. Every encounter will use the fallback.")
        return LiveSelector(client, session_id), session_id, "live"
    return NeutralSelector(), None, "off"


def play(options: Options) -> int:
    """Run the game. Returns a process exit code."""
    if options.headless:
        os.environ["SDL_VIDEODRIVER"] = "dummy"
        os.environ["SDL_AUDIODRIVER"] = "dummy"

    replay: Recording | None = Recording.load(options.replay) if options.replay else None
    practice = replay.mode == "practice" if replay else options.practice
    seed = replay.seed if replay else options.seed
    session: Session | None = None
    starts: dict[int, str] = {}
    if practice:
        run: Run | Campaign = Run(seed)
    elif replay:
        try:
            check_campaign(replay)
        except ValueError as error:
            print(f"Replay rejected: {error}")
            return 2
        run = Campaign(seed)
        starts = dict(zip(replay.starts, replay.protocols[1:], strict=True))
    else:
        selector, session_id, condition = build_selector(options)
        run = Campaign(seed)
        trace = None
        if options.trace or not options.headless:
            stamp = datetime.now(UTC).strftime("%Y%m%d-%H%M%S")
            trace = TraceWriter(
                options.trace or ROOT / "logs" / f"trace-{stamp}.jsonl",
                condition=condition,
                tuning_id=run.tuning.tuning_id(),
                arena_id=arena_id(run.arena),
            )
        session = Session(run, selector, trace, session_id)
    room = arena_id(run.arena)
    if replay and replay.tuning_id != run.tuning.tuning_id():
        print(f"Replay uses tuning {replay.tuning_id}, this build is {run.tuning.tuning_id()}")
        return 2
    if replay and replay.arena_id != room:
        print(f"Replay uses arena {replay.arena_id}, this build is {room}")
        return 2
    recording = Recording(
        seed=seed,
        tuning_id=run.tuning.tuning_id(),
        arena_id=room,
        mode="practice" if practice else "campaign",
        protocols=[] if practice else [run.protocols[1]],
    )
    scripted: Iterator[InputFrame] | None = iter(replay.frames) if replay else None
    stats = {"ticks": 0, "shots": 0}

    pygame.init()
    try:
        screen = _open_window(options.headless)
        pygame.display.set_caption("Overload")
        view = PixelView(run)
        reader = InputReader()
        clock = pygame.time.Clock()
        accumulated = 0.0
        frames = 0
        finished = False
        cursor = (VIEW[0] // 2, VIEW[1] // 2)
        while not reader.quit and not finished:
            for event in pygame.event.get():
                reader.handle(event)
            if scripted is None and not options.headless:
                cursor = pygame.mouse.get_pos()
            elapsed = clock.tick(240) / 1000.0
            if options.headless:
                due = 1
            else:
                accumulated = min(accumulated + elapsed, MAX_TICKS_PER_FRAME * TICK_SECONDS)
                due = int(accumulated / TICK_SECONDS)
                accumulated -= due * TICK_SECONDS
            for _ in range(due):
                if scripted is not None:
                    if len(recording.frames) in starts:
                        if run.stage != "fuse_box":
                            print(
                                f"Replay rejected: start at tick {len(recording.frames)} "
                                "is not in the Fuse Box"
                            )
                            return 2
                        run.begin_next(starts[len(recording.frames)])
                        recording.begin_next(run.protocols[run.encounter])
                    frame = next(scripted, None)
                    if frame is None:
                        finished = True
                        break
                else:
                    frame = reader.frame(view.camera_offset()) if not options.headless else IDLE
                playing = getattr(run, "stage", "encounter") == "encounter"
                if session is not None:
                    session.tick(frame)
                else:
                    run.step(frame)
                recording.frames.append(frame)
                if playing and run.world.outcome == "playing":
                    stats["ticks"] += 1
                stats["shots"] += sum(1 for e in run.world.events if e.kind == "shot")
                if scripted is not None:
                    cam = view.camera_offset()
                    cursor = (frame.aim_x - cam[0], frame.aim_y - cam[1])
                view.update(run, cursor)
            if session is not None and reader.take_confirm():
                decision = session.confirm()
                if decision is not None:
                    recording.begin_next(decision.tactic)
            view.draw(screen, run, cursor)
            stage = getattr(run, "stage", None)
            if stage == "fuse_box":
                ready = session.ready() if session else False
                message = session.fuse_message() if session else None
                view.draw_fuse_box(screen, run.encounter + 1, ready, message)
            elif stage == "ending":
                view.draw_ending(
                    screen, stats["ticks"] / TICK_RATE, sum(run.retries.values()), stats["shots"]
                )
            pygame.display.flip()
            frames += 1
            if options.frames and frames >= options.frames:
                break
    finally:
        pygame.quit()
        hud.forget()
        tiles.forget_fonts()
        if session is not None and isinstance(session.selector, LiveSelector):
            session.selector.client.close()

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
