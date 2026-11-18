"""Playable client.

The simulation advances at a fixed 60 ticks per second regardless of frame rate. Each
tick reads exactly one InputFrame, either from the devices or from a replay. The view is
256 x 144 pixels, scaled up by whole numbers to fit the window, with a camera that follows
the Surge. Rendering and cosmetic effects never feed back into the simulation.

Controls: WASD or arrows move, mouse aims, hold left click to fire, Space dodges,
Q and E use powers, R retries after going down. Tab or Esc opens the menu (game/menu.py),
where Space or Enter picks and Esc goes back. Esc quits only when no menu can open.
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
from overload.game import dev as devmode
from overload.game import menu_view
from overload.game import title as title_screen
from overload.game.audio import Audio
from overload.game.flow import Session
from overload.game.menu import Menu
from overload.game.title import run_title
from overload.game.view import VIEW, PixelView
from overload.paths import ROOT
from overload.session.replay import Recording, apply_menu, check_campaign, menu_by_frame
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
    mute: bool = False
    skip_title: bool = False
    dev: bool = False  # test tools, gated by a local git-ignored file (game/dev.py)


class InputReader:
    """Turns pygame events and device state into one InputFrame per tick.

    Dodge and retry are presses, so they are latched until the next tick consumes them.
    The mouse is read in view pixels and converted to room pixels with the camera.
    """

    def __init__(self) -> None:
        self.quit = False
        self._dodge = False
        self._restart = False
        self._toggle = False
        self._power_q = False
        self._power_e = False
        self._escape = False
        self._menu: list[str] = []

    def handle(self, event: pygame.event.Event) -> None:
        if event.type == pygame.QUIT:
            self.quit = True
        elif event.type == pygame.KEYDOWN:
            if event.key == pygame.K_ESCAPE:
                self._escape = True  # back in a menu, quit outside one (the caller decides)
            elif event.key == pygame.K_SPACE:
                self._dodge = True
            elif event.key == pygame.K_r:
                self._restart = True
            elif event.key == pygame.K_TAB:
                self._toggle = True
            if event.key == pygame.K_q:
                self._power_q = True
            elif event.key == pygame.K_e:
                self._power_e = True
            key = MENU_KEYS.get(event.key)
            if key:
                self._menu.append(key)

    def take_escape(self) -> bool:
        pressed, self._escape = self._escape, False
        return pressed

    def take_toggle(self) -> bool:
        """Tab: open or close the menu."""
        pressed, self._toggle = self._toggle, False
        return pressed

    def drop_power_latches(self) -> None:
        """Forget presses made in a menu (Q, E, Space, R), so none of them acts on the first
        tick after it closes."""
        self._power_q = self._power_e = self._dodge = self._restart = False

    def take_menu(self) -> list[str]:
        """Menu keys pressed since the last call. Read every frame, used while a menu is
        open, dropped otherwise."""
        keys, self._menu = self._menu, []
        return keys

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
            power_q=self._power_q,
            power_e=self._power_e,
        )
        self._dodge = self._restart = self._power_q = self._power_e = False
        return frame


MENU_KEYS = {
    pygame.K_w: "up",
    pygame.K_UP: "up",
    pygame.K_s: "down",
    pygame.K_DOWN: "down",
    pygame.K_a: "left",
    pygame.K_LEFT: "left",
    pygame.K_d: "right",
    pygame.K_RIGHT: "right",
    pygame.K_SPACE: "select",
    pygame.K_RETURN: "select",
    pygame.K_KP_ENTER: "select",
    pygame.K_f: "roll",
    pygame.K_ESCAPE: "back",
    pygame.K_BACKSPACE: "back",
    pygame.K_q: "q",
    pygame.K_e: "e",
    pygame.K_h: "help",
}
# Menu sounds to the cue that plays them (game/menu.py names them by what happened).
MENU_SOUNDS = {"move": "menu_move", "roll_tick": "roll_tick"}


def menu_frame(
    session: Session,
    menu: Menu,
    reader: InputReader,
    recording: Recording,
    ms: int,
) -> list[str]:
    """Menu keys once per rendered frame after the tick batch, then the spin's clock. The
    Fuse Box keeps the menu open. CONTINUE starts the next sector once the hold is over,
    RESUME closes the paused menu, and leaving either drops any power press still latched so
    it cannot fire on the next tick. Returns the cues to play."""
    keys = reader.take_menu()
    if not menu.open:
        return []
    cues: list[str] = []
    for key in keys:
        action, sounds = menu.press(session, key)
        if action is not None:
            recording.fuse_box(*action)
        for sound in sounds:
            if sound == "continue":
                decision = session.confirm()
                if decision is None:
                    cues.append("deny")  # still routing power
                    continue
                recording.begin_next(decision.tactic)
                menu.close()
                reader.drop_power_latches()
                cues.append("confirm")
            elif sound == "quit":
                reader.quit = True
            elif sound == "resume":
                menu.close()
                reader.drop_power_latches()
                cues.append("confirm")
            else:
                cues.append(MENU_SOUNDS.get(sound, sound))
        if not menu.open:
            break
    cues.extend(MENU_SOUNDS.get(s, s) for s in menu.update(ms))
    return cues


def draw_dev_marks(screen: pygame.Surface, tools, run, fps: float) -> None:
    """DEV on screen whenever dev mode runs, so no dev capture can pass for real play, and
    the debug overlay when it is on."""
    hud.text(screen, "DEV", (VIEW[0] // 2, 2), "px.hazard.1", "midtop")
    if tools.overlay:
        for i, line in enumerate(devmode.overlay_lines(run, fps)):
            hud.text(screen, line, (4, VIEW[1] - 60 + i * 9), "ui.dim")


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


def open_menu(menu: Menu, reader: InputReader, in_fuse_box: bool) -> None:
    """Open the hub. Keys pressed before it opened (the Esc that opened it, a W or Space
    as the sector ended) are dropped, so none of them becomes a menu choice."""
    menu.show(in_fuse_box=in_fuse_box)
    reader.take_menu()


def can_open_menu(run) -> bool:
    return run.stage == "encounter" and run.world.outcome == "playing"


def toggle_menu(menu: Menu, run) -> None:
    """Tab: close the menu if open, else open the hub, but only mid-sector with the Surge up
    (not while down or at the ending). In a Fuse Box the menu stays open."""
    if run.stage == "fuse_box":
        return
    if menu.open:
        menu.close()
    elif can_open_menu(run):
        menu.show(in_fuse_box=False)


def ticks_due(paused: bool, headless: bool, accumulated: float, elapsed: float):
    """How many fixed ticks to run this frame, and the time left over. The loadout menu stops
    time: nothing runs and nothing carries over while it is open."""
    if paused:
        return 0, 0.0
    if headless:
        return 1, accumulated
    accumulated = min(accumulated + elapsed, MAX_TICKS_PER_FRAME * TICK_SECONDS)
    due = int(accumulated / TICK_SECONDS)
    return due, accumulated - due * TICK_SECONDS


def play(options: Options) -> int:
    """Run the game. Returns a process exit code."""
    if options.dev:
        if not devmode.available():
            print("Dev mode is not available on this machine.")
            return 2
        if options.replay or options.practice:
            print("Dev mode runs the campaign only, not replays or practice.")
            return 2
        # Dev runs are never study data: no model call, no trace, no recording.
        options.condition, options.trace, options.record = "off", None, None
        print("Dev mode: the rival is off, and no trace or recording is written.")
    if options.headless:
        os.environ["SDL_VIDEODRIVER"] = "dummy"
        os.environ["SDL_AUDIODRIVER"] = "dummy"

    if not (options.headless or options.replay or options.skip_title):
        # The title comes first: no rival session or trace exists until the player starts.
        pygame.init()
        started = False
        try:
            started = run_title(_open_window(False), pygame.time.Clock())
        finally:
            if not started:
                pygame.quit()
                hud.forget()
                tiles.forget_fonts()
                title_screen.forget()
        if not started:
            return 0

    replay: Recording | None = Recording.load(options.replay) if options.replay else None
    practice = replay.mode == "practice" if replay else options.practice
    seed = replay.seed if replay else options.seed
    session: Session | None = None
    starts: dict[int, str] = {}
    replay_menu: dict[int, list[list]] = {}
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
        replay_menu = menu_by_frame(replay)
    else:
        selector, session_id, condition = build_selector(options)
        run = Campaign(seed)
        trace = None
        if not options.dev and (options.trace or not options.headless):
            stamp = datetime.now(UTC).strftime("%Y%m%d-%H%M%S")
            trace = TraceWriter(
                options.trace or ROOT / "logs" / f"trace-{stamp}.jsonl",
                condition=condition,
                tuning_id=run.tuning.tuning_id(),
                arena_id=arena_id(run.arena),
            )
        try:
            session = Session(run, selector, trace, session_id)
        except Exception:
            if isinstance(selector, LiveSelector):
                selector.client.close()
            raise
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

    pygame.init()
    try:
        screen = _open_window(options.headless)
        pygame.display.set_caption("Overload")
        view = PixelView(run)
        reader = InputReader()
        menu = Menu()
        dev_tools = devmode.DevTools() if options.dev else None
        menu.dev = dev_tools
        audio = Audio(enabled=not (options.mute or options.headless))
        clock = pygame.time.Clock()
        accumulated = 0.0
        frames = 0
        finished = False
        cursor = (VIEW[0] // 2, VIEW[1] // 2)
        while not reader.quit and not finished:
            for event in pygame.event.get():
                reader.handle(event)
            if reader.take_escape() and not menu.open:
                # Esc outside a menu opens it (QUIT lives there), and quits only when no
                # menu can open (down, the ending, practice or a replay).
                if session is None or not can_open_menu(run):
                    break
                open_menu(menu, reader, in_fuse_box=False)
            if scripted is None and not options.headless:
                cursor = pygame.mouse.get_pos()
            elapsed = clock.tick(240) / 1000.0
            if reader.take_toggle() and session is not None:
                was_open = menu.open
                toggle_menu(menu, run)
                if was_open and not menu.open:
                    reader.drop_power_latches()
                if menu.open and not was_open:
                    reader.take_menu()  # keys from before the menu opened are not choices
            paused = menu.open and getattr(run, "stage", None) != "fuse_box"
            due, accumulated = ticks_due(paused, options.headless, accumulated, elapsed)
            for _ in range(due):
                if scripted is not None:
                    for action in replay_menu.get(len(recording.frames), []):
                        try:
                            apply_menu(run, action)
                        except ValueError as error:
                            print(f"Replay rejected: {error}")
                            return 2
                        recording.fuse_box(*action[1:])
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
                    # Move the camera first, so the cursor is read against the same camera
                    # the frame will be drawn with: the reticle and the aim point agree.
                    view.follow(run, cursor)
                    frame = reader.frame(view.camera_offset()) if not options.headless else IDLE
                if dev_tools is not None:
                    dev_tools.before_tick(run)
                if session is not None:
                    session.tick(frame)
                else:
                    run.step(frame)
                if dev_tools is not None:
                    dev_tools.after_tick(run)
                recording.frames.append(frame)
                audio.events(run.world.events, run.world)
                if scripted is not None:
                    cam = view.camera_offset()
                    cursor = (frame.aim_x - cam[0], frame.aim_y - cam[1])
                    view.update(run, cursor)
                else:
                    view.after_tick(run)
            if session is not None:
                if run.stage == "fuse_box" and not menu.open:
                    open_menu(menu, reader, in_fuse_box=True)  # arriving opens the hub
                for sound in menu_frame(session, menu, reader, recording, round(elapsed * 1000)):
                    audio.play(sound)
            audio.update(
                getattr(run, "stage", None), getattr(run, "encounter", 1), run.world.outcome
            )
            view.draw(screen, run, cursor)
            stage = getattr(run, "stage", None)
            if dev_tools is not None:
                draw_dev_marks(screen, dev_tools, run, clock.get_fps())
            if menu.open and session is not None:
                in_box = stage == "fuse_box"
                menu_view.draw_menu(
                    screen,
                    menu,
                    session,
                    run.tuning,
                    session.ready() if in_box else True,
                    session.fuse_message() if in_box else None,
                    run.encounter + (1 if in_box else 0),
                )
            elif stage == "ending":
                view.draw_ending(
                    screen,
                    run.stats["ticks"] / TICK_RATE,
                    sum(run.retries.values()),
                    run.stats["shots"],
                    run.stats["powers"],
                )
            pygame.display.flip()
            frames += 1
            if options.frames and frames >= options.frames:
                break
    finally:
        if session is not None:
            session.close()
        pygame.quit()
        hud.forget()
        tiles.forget_fonts()
        title_screen.forget()
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
