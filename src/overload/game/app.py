"""Playable client.

The simulation advances at a fixed 60 ticks per second regardless of frame rate. Each
tick reads exactly one InputFrame, either from the devices or from a replay. The view is
256 x 144 pixels, scaled up by whole numbers to fit the window, with a camera that follows
the Surge. Rendering and cosmetic effects never feed back into the simulation.

Controls (defaults, rebindable in CONTROLS, game/keybinds.py): WASD or arrows move, mouse
aims, hold left click to fire, Space dodges, Q and E use powers, R retries after going down.
Tab or Esc opens the menu (game/menu.py), where Space or Enter picks and Esc goes back. Esc
quits only when no menu can open.
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
from overload.art.palette import rgb
from overload.art.pixel import actors, hud, tiles
from overload.game import dev as devmode
from overload.game import keybinds, menu_view
from overload.game import title as title_screen
from overload.game.audio import Audio
from overload.game.flow import Session
from overload.game.keybinds import Keybinds
from overload.game.menu import Menu
from overload.game.settings import Settings
from overload.game.title import run_title
from overload.game.view import VIEW, PixelView
from overload.paths import ROOT
from overload.session.replay import (
    Recording,
    apply_menu,
    check_campaign,
    menu_by_frame,
    recorded_tuning,
)
from overload.session.trace import TraceWriter
from overload.sim.arena import arena_id
from overload.sim.campaign import Campaign
from overload.sim.difficulty import PRESETS
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
    difficulty: str = "medium"


class InputReader:
    """Turns pygame events and device state into one InputFrame per tick, through the
    player's key bindings (game/keybinds.py).

    Dodge and retry are presses, so they are latched until the next tick consumes them.
    The mouse is read in view pixels and converted to room pixels with the camera.
    """

    def __init__(self, binds: Keybinds | None = None) -> None:
        self.quit = False
        self._dodge = False
        self._restart = False
        self._toggle = False
        self._power_q = False
        self._power_e = False
        self._escape = False
        self._menu: list[tuple[str | None, str]] = []  # (menu key, raw key name), in order
        self.binds = binds or Keybinds()
        self.rebind()

    def rebind(self) -> None:
        """Read the bindings again (after the CONTROLS page changes one). A damaged
        binding falls back to the defaults."""
        try:
            self._codes = {action: keybinds.code(key) for action, key in self.binds.keys.items()}
        except ValueError:
            self.binds.reset()
            self._codes = {action: keybinds.code(key) for action, key in self.binds.keys.items()}
        self._arrows = {a: keybinds.code(k) for a, k in self.binds.arrows().items()}
        self._menu_keys = menu_keys(self._codes, self._arrows)

    def handle(self, event: pygame.event.Event) -> None:
        if event.type == pygame.QUIT:
            self.quit = True
        elif event.type == pygame.KEYDOWN:
            codes = self._codes
            if event.key == pygame.K_ESCAPE:
                self._escape = True  # back in a menu, quit outside one (the caller decides)
            elif event.key == codes["dodge"]:
                self._dodge = True
            elif event.key == codes["retry"]:
                self._restart = True
            elif event.key == codes["menu"]:
                self._toggle = True
            if event.key == codes["power_q"]:
                self._power_q = True
            elif event.key == codes["power_e"]:
                self._power_e = True
            self._menu.append((self._menu_keys.get(event.key), keybinds.key_name(event.key)))

    def take_escape(self) -> bool:
        pressed, self._escape = self._escape, False
        return pressed

    def take_toggle(self) -> bool:
        """The menu key: open or close the menu."""
        pressed, self._toggle = self._toggle, False
        return pressed

    def drop_power_latches(self) -> None:
        """Forget presses made in a menu (powers, dodge, retry), so none of them acts on the
        first tick after it closes."""
        self._power_q = self._power_e = self._dodge = self._restart = False

    def take_menu(self) -> list[str]:
        """Menu keys pressed since the last call. Read every frame, used while a menu is
        open, dropped otherwise."""
        return [key for key, _ in self.take_menu_raw() if key]

    def take_menu_raw(self) -> list[tuple[str | None, str]]:
        """Every key pressed since the last call, as (menu key or None, raw key name), so
        the CONTROLS page can catch any key for a rebind."""
        keys, self._menu = self._menu, []
        return keys

    def frame(self, camera: tuple[int, int]) -> InputFrame:
        keys = pygame.key.get_pressed()
        codes, arrows = self._codes, self._arrows

        def held(action: str) -> bool:
            return bool(keys[codes[action]] or (action in arrows and keys[arrows[action]]))

        move_x = int(held("right")) - int(held("left"))
        move_y = int(held("down")) - int(held("up"))
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


# Menu keys that never move. Select and back always win, so no binding can take away the
# way to pick CONTINUE or leave a page. Roll and help give way to a bound key.
MENU_ALWAYS = {
    pygame.K_SPACE: "select",
    pygame.K_RETURN: "select",
    pygame.K_KP_ENTER: "select",
    pygame.K_ESCAPE: "back",
    pygame.K_BACKSPACE: "back",
}
MENU_EXTRAS = {pygame.K_f: "roll", pygame.K_h: "help"}


def menu_keys(codes: dict[str, int], arrows: dict[str, int]) -> dict[int, str]:
    """Key code to menu key: the bound move keys and the free arrows navigate, the bound
    power keys equip, F rolls and H opens help unless bound, and Space, Enter, Esc and
    Backspace always select or go back."""
    keys = dict(MENU_EXTRAS)
    for action, code in arrows.items():
        keys[code] = action
    keys[codes["power_q"]] = "q"
    keys[codes["power_e"]] = "e"
    for action in ("up", "down", "left", "right"):
        keys[codes[action]] = action
    keys.update(MENU_ALWAYS)
    return keys


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
    keys = reader.take_menu_raw()
    if not menu.open:
        return []
    cues: list[str] = []
    for key, raw in keys:
        if menu.capturing:  # CONTROLS waits for a key: any key but Esc binds
            cues.append(menu.keys_page.capture(raw if keybinds.known(raw) else "escape"))
            reader.rebind()
            continue
        if key is None:
            continue
        on_controls = menu.screen == "controls"
        action, sounds = menu.press(session, key)
        if on_controls:
            reader.rebind()  # RESET DEFAULTS may have changed every key
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


def draw_dev_overlay(screen: pygame.Surface, tools, run, fps: float) -> None:
    """The debug overlay, over play (menus cover it)."""
    if tools.overlay:
        for i, line in enumerate(devmode.overlay_lines(run, fps)):
            hud.text(screen, line, (4, VIEW[1] - 58 + i * 9), "ui.dim")


def draw_dev_tag(screen: pygame.Surface) -> None:
    """DEV in the top right corner on a backing box, drawn last in every frame (over menus,
    the Fuse Box and the ending), so no dev capture can pass for real play (AGENTS.md)."""
    rect = pygame.Rect(VIEW[0] - 23, 0, 21, 10)
    screen.fill(rgb("px.outline"), rect)
    pygame.draw.rect(screen, rgb("px.hazard.1"), rect, 1)
    hud.text(screen, "DEV", rect.center, "px.hazard.1", "center")


def _open_window(headless: bool, fullscreen: bool = False) -> pygame.Surface:
    if headless:
        return pygame.display.set_mode(VIEW)
    pygame.display.set_icon(actors.app_icon())
    flags = pygame.SCALED | (pygame.FULLSCREEN if fullscreen else pygame.RESIZABLE)
    try:
        screen = pygame.display.set_mode(VIEW, flags, vsync=1)
    except pygame.error:
        screen = pygame.display.set_mode(VIEW, flags)
    pygame.mouse.set_visible(False)
    return screen


def _open_display(headless: bool, fullscreen: bool) -> pygame.Surface:
    """Open the window, matching saved fullscreen state while keeping 1-arg `_open_window`
    calls intact for windowed startup."""
    if headless or not fullscreen:
        return _open_window(headless)
    return _open_window(False, True)


def _apply_fullscreen(screen: pygame.Surface, fullscreen: bool, headless: bool) -> pygame.Surface:
    """Switch display mode only when fullscreen actually changed, never reopening an already
    matching fullscreen window."""
    if headless or bool(screen.get_flags() & pygame.FULLSCREEN) == fullscreen:
        return screen
    return _open_display(False, fullscreen)


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

    screen = None
    audio: Audio | None = None
    difficulty = options.difficulty
    # A replay or a headless run never reads or writes saved keys or settings.
    binds = Keybinds() if options.replay or options.headless else Keybinds.load()
    settings = Settings() if options.replay or options.headless else Settings.load()
    show_title = not (options.headless or options.replay or options.skip_title)
    can_return = show_title and not (options.practice or options.record)
    replay: Recording | None = Recording.load(options.replay) if options.replay else None
    if replay is not None:
        try:
            recorded_tuning(replay.tuning_id)
        except ValueError as error:
            print(f"Replay rejected: {error}")
            return 2
        if replay.mode != "practice":
            try:
                check_campaign(replay)
            except ValueError as error:
                print(f"Replay rejected: {error}")
                return 2

    def on_display(fullscreen: bool) -> pygame.Surface:
        nonlocal screen
        screen = _apply_fullscreen(screen, fullscreen, options.headless)
        return screen

    try:
        while True:
            if show_title:
                # The title comes first: no rival session or trace exists until the player starts.
                if screen is None:
                    pygame.init()
                    screen = _open_display(False, settings.fullscreen)
                    pygame.display.set_caption("Overload")
                    # The same Audio carries on into play, so the title music hands over to the
                    # first sector on a bar line instead of cutting out.
                    audio = Audio(enabled=not options.mute)
                    audio.apply_settings(settings)
                selected = run_title(
                    screen,
                    pygame.time.Clock(),
                    difficulty,
                    binds,
                    audio,
                    settings=settings,
                    on_display=on_display,
                )
                if selected is None:
                    return 0
                difficulty = selected

            tuning = recorded_tuning(replay.tuning_id) if replay else PRESETS[difficulty]
            practice = replay.mode == "practice" if replay else options.practice
            seed = replay.seed if replay else options.seed
            session: Session | None = None
            starts: dict[int, str] = {}
            replay_menu: dict[int, list[list]] = {}
            if practice:
                run: Run | Campaign = Run(seed, tuning)
            elif replay:
                run = Campaign(seed, tuning)
                starts = dict(zip(replay.starts, replay.protocols[1:], strict=True))
                replay_menu = menu_by_frame(replay)
            else:
                selector, session_id, condition = build_selector(options)
                run = Campaign(seed, tuning)
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
            return_to_title = False
            replay_complete = False

            try:
                # Keep the title's display mode. Reopening fullscreen can crash SDL on macOS.
                if screen is None:
                    pygame.init()
                    screen = _open_display(options.headless, settings.fullscreen)
                    pygame.display.set_caption("Overload")
                view = PixelView(run)
                view.binds = view.coach.binds = binds
                view.apply_settings(settings)
                if options.dev:
                    view.stamp = f"DEV {view.stamp}"  # the build stamp on banners and the ending
                reader = InputReader(binds)
                menu = Menu()
                menu.keys_page.binds = binds
                menu.settings_page.settings = settings
                dev_tools = devmode.DevTools() if options.dev else None
                menu.dev = dev_tools
                if audio is None:
                    audio = Audio(enabled=not (options.mute or options.headless))
                audio.apply_settings(settings)
                clock = pygame.time.Clock()
                accumulated = 0.0
                frames = 0
                finished = False
                ending_shown = False
                replay_coda = 0
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
                    if reader.take_toggle() and session is not None and not menu.capturing:
                        was_open = menu.open
                        toggle_menu(menu, run)
                        if was_open and not menu.open:
                            reader.drop_power_latches()
                        if menu.open and not was_open:
                            reader.take_menu()  # keys from before the menu opened are not choices
                    paused = menu.open and getattr(run, "stage", None) != "fuse_box"
                    due, accumulated = ticks_due(paused, options.headless, accumulated, elapsed)
                    for _ in range(due):
                        if replay_complete:
                            if replay_coda == 0:
                                finished = True
                                break
                            view.advance_defeat()
                            view.follow(run, cursor)
                            replay_coda -= 1
                            continue
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
                                replay_complete = True
                                if options.headless:
                                    finished = True
                                else:
                                    if view.boss_banner is not None:
                                        replay_coda = view.boss_banner[1]
                                    if isinstance(run, Campaign) and run.stage == "ending":
                                        replay_coda += 2 * TICK_RATE
                                break
                        else:
                            # Move the camera first, so the cursor is read against the same camera
                            # the frame will be drawn with: the reticle and the aim point agree.
                            view.follow(run, cursor)
                            frame = (
                                reader.frame(view.camera_offset()) if not options.headless else IDLE
                            )
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
                    stage = getattr(run, "stage", None)
                    if session is not None:
                        if run.stage == "fuse_box" and not menu.open:
                            open_menu(menu, reader, in_fuse_box=True)  # arriving opens the hub
                        if (
                            stage == "ending"
                            and view.boss_banner is None
                            and can_return
                            and not menu.open
                        ):
                            ending_keys = reader.take_menu()
                            if ending_shown and "select" in ending_keys and not reader.quit:
                                audio.play("confirm")
                                return_to_title = True
                                break
                        else:
                            was_full = settings.fullscreen
                            cues = menu_frame(
                                session, menu, reader, recording, round(elapsed * 1000)
                            )
                            audio.apply_settings(settings)
                            view.apply_settings(settings)
                            if settings.fullscreen != was_full:
                                screen = _apply_fullscreen(
                                    screen, settings.fullscreen, options.headless
                                )
                            for sound in cues:
                                audio.play(sound)
                    audio.update(stage, getattr(run, "encounter", 1), run.world.outcome)
                    view.draw(screen, run, cursor)
                    if dev_tools is not None:
                        draw_dev_overlay(screen, dev_tools, run, clock.get_fps())
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
                        view.draw_campaign_ending(screen, run, can_return)
                        if view.boss_banner is None:
                            ending_shown = True
                    if dev_tools is not None:
                        draw_dev_tag(screen)
                    pygame.display.flip()
                    frames += 1
                    if options.frames and frames >= options.frames:
                        break
            finally:
                if session is not None:
                    try:
                        session.close()
                    finally:
                        if isinstance(session.selector, LiveSelector):
                            session.selector.client.close()

            if return_to_title:
                continue
            break
    finally:
        if pygame.get_init():
            pygame.quit()
            actors.app_icon.cache_clear()
            hud.forget()
            tiles.forget_fonts()
            title_screen.forget()

    recording.final_hash = run.state_hash()
    if options.record:
        recording.save(options.record)
        print(f"Recorded {len(recording.frames)} ticks to {options.record}")
    if replay is not None:
        if not replay_complete:
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
