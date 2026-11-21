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
from overload.art.pixel import actors, effects, hud, rig, tiles
from overload.art.pixel import regulators as regulators_art
from overload.art.pixel import robots as robots_art
from overload.art.pixel.light import Glow
from overload.art.pixel.lighting import Lighting, pool, quantize
from overload.floor import CELL, GRID, TILE
from overload.game.coach import Coach
from overload.game.keybinds import Keybinds
from overload.sim import aiming, bosskit, floorplay
from overload.sim import world as rules
from overload.sim.arena import arena_id
from overload.sim.bosses import BY_KIND
from overload.sim.campaign import Campaign
from overload.sim.powers import (
    BASE_POWERS,
    COOLDOWN_KEYS,
    EVOLUTIONS,
    NAMES,
    RARITIES,
    cooldown_of,
    rarity_of,
)
from overload.sim.run import Run
from overload.sim.state import Event
from overload.sim.tuning import DEFAULT, TICK_RATE

VIEW = (256, 144)
BLAST_TICKS = 12
# Why a fused power did nothing (it costs nothing and is not counted).
REJECTED = {
    "chain_jump": "NO ROBOT IN REACH",
    "displacer": "NO ROBOT TO SWAP WITH",
    "meteor": "NO ROOM TO LAND",
    "tesla_coil": "NO ROOM FOR A COIL",
    "rewind": "NO SAFE SPOT TO REWIND",
    "grapple": "NOTHING TO GRAPPLE",
}
SURGE_FEET = 8  # sprite feet sit this many pixels below the body center
# The glow on the Surge's pack for an equipped power: a fused power shows the ingredient
# its effect leans on.
SOCKET_TOKENS = {
    "spark": "spark",
    "blink": "blink",
    "bulwark": "bulwark",
    "magnet": "magnet",
    "static_guard": "bulwark",
    "tesla_coil": "spark",
    "capacitor_armor": "bulwark",
    "lodestone": "magnet",
    "ion_hook": "spark",
    "magrail": "magnet",
    "bastion": "bulwark",
    "reflector_wave": "burst",
    "fortress": "bulwark",
    "vortex_cone": "burst",
    "implosion": "magnet",
    "gravity_well": "magnet",
    "phase_guard": "bulwark",
    "afterimage": "blink",
    "rewind": "blink",
    "undertow": "magnet",
    "grapple": "magnet",
    "riptide": "magnet",
    "lightning_rod": "magnet",
    "shield_toss": "bulwark",
    "mirror_field": "magnet",
    "burst": "burst",
    "arc_trail": "spark",
    "bolt_lance": "spark",
    "chain_jump": "spark",
    "shock_cone": "burst",
    "shock_mine": "burst",
    "storm_aura": "spark",
    "impact_blink": "burst",
    "displacer": "blink",
    "meteor": "burst",
}
DESCRIPTIONS = {
    "spark": "A HEAVY BOLT. TWO MORE CHARGES EVOLVE IT",
    "blink": "TELEPORT TOWARD THE CURSOR",
    "bulwark": "A SHIELD BUBBLE THAT EATS SHOTS",
    "magnet": "A FIELD AT THE AIM THAT DRAGS ROBOTS IN",
    "static_guard": "A SHIELD. EACH SHOT IT EATS SPARKS BACK",
    "tesla_coil": "PLANT A COIL THAT STRIKES AND SOAKS SHOTS",
    "capacitor_armor": "EAT THE NEXT 3 HITS, THEN A RING OF SPARKS",
    "lodestone": "A SLOW HEAVY SPARK THAT DRAGS ROBOTS",
    "ion_hook": "HOOK A ROBOT TO YOU AND STUN IT",
    "magrail": "A RAIL THAT PIERCES AND DRAGS. WALLS HURT",
    "bastion": "A SHIELD THAT ENDS IN A BLAST",
    "reflector_wave": "A ROLLING WALL. SHOVES ROBOTS, TURNS SHOTS",
    "fortress": "A DOME NO SHOT ENTERS. IT BLASTS INTRUDERS",
    "vortex_cone": "A CONE THAT PULLS ROBOTS IN, THEN POPS",
    "implosion": "A FIELD THAT DRAWS ROBOTS IN, THEN BLASTS",
    "gravity_well": "A LONG WELL. PULLS EVERYTHING, BIG BLAST",
    "phase_guard": "BLINK AND ARRIVE INSIDE A SHIELD",
    "afterimage": "BLINK AND LEAVE A DECOY FOR 2 S",
    "rewind": "GO BACK 2 S WITH YOUR BATTERY CHARGE",
    "undertow": "BLINK. THE TAKEOFF POINT PULLS ROBOTS IN",
    "grapple": "ZIP TO A WALL OR KNOCK A ROBOT BACK",
    "riptide": "BLINK, YANK ROBOTS IN AND STUN THEM",
    "lightning_rod": "PLANT A ROD THAT DRAWS IN HOSTILE SHOTS",
    "shield_toss": "THROW A SHIELD THAT SOAKS SHOTS AND RETURNS",
    "mirror_field": "CATCH SHOTS IN ORBIT AND FIRE THEM BACK",
    "burst": "KNOCKBACK CONE THAT WIPES SHOTS",
    "arc_trail": "A BLINK THAT LEAVES A SHOCK LINE",
    "bolt_lance": "DASH AS A BOLT, STRIKING ALL YOU PASS",
    "chain_jump": "HOP ROBOT TO ROBOT, STRIKING EACH",
    "shock_cone": "A BURST PLUS A FAN OF SPARKS",
    "shock_mine": "LOB A CHARGE THAT BURSTS IN A RING",
    "storm_aura": "3 S OF BOLTS AT THE NEAREST ROBOT",
    "impact_blink": "BLINK, THEN A RING BLAST ON LANDING",
    "displacer": "SWAP PLACES WITH A ROBOT. BOTH SPOTS BLAST",
    "meteor": "LEAP, UNTOUCHABLE, AND CRASH DOWN",
}
EVOLVED_INFO = {
    "spark": "EVOLVED. HITS CHAIN TO A SECOND ROBOT",
    "blink": "EVOLVED. A BURST OF SPEED ON ARRIVAL",
    "burst": "EVOLVED. A WIDER, LONGER CONE",
    "bulwark": "EVOLVED. EATEN SHOTS FLY BACK AS SPARKS",
    "magnet": "EVOLVED. ROBOTS LEFT INSIDE ARE CRUSHED",
}
RIVAL_FEET = regulators_art.FEET  # per chassis: feet below the body center
ROBOT_FEET = {"drone": 9, "relay": 10, "breaker": 12, "sweeper": 7, "sentry": 8}
CORE_GLOW = {
    "drone": "power.spark",
    "relay": "power.blink",
    "breaker": "power.burst",
    "sentry": "power.bulwark",
    "sweeper": "power.magnet",
}
SHOT_ART = {
    "shard": robots_art.shard,
    "shell": robots_art.shell,
    "needle": robots_art.needle_dart,
    "orb": robots_art.orb,
}


@dataclass
class Gait:
    """How far a body has walked, for its walk cycle. Cosmetic only: the view keeps it."""

    x: float
    y: float
    stride: float = 0.0  # pixels walked so far
    moved: float = 0.0  # pixels moved on the last tick
    dx: float = 0.0  # actual direction of the last move
    dy: float = 0.0


STRIDE = {
    "relay": 2.0,
    "breaker": 2.0,
    "sweeper": 1.5,
    "regulator": regulators_art.STEP_DISTANCE,
}  # px per step
WALKING = 0.05  # moved at least this far on the last tick: walking, not standing
SCAN = (0, 1, 2, 3, 3, 2, 1, 0)  # the Sentry's eye sweeping its visor
RECOIL_TICKS = 12
# A fused shield's bubble shows the power it was fused with (art direction rule 5).
BUBBLE_ACCENTS = {
    "static_guard": "power.spark",
    "bastion": "power.burst",
    "phase_guard": "power.blink",
}
BOOM_TICKS = 14
WRECK_TICKS = 90  # 1.5 s of explosions over the sinking wreck
FLY_NEAR = 12.0  # above contact pickup reach (player_radius + charge_radius = 11 px)
FLY_TICKS = 60  # a flyer always lands within a second
HINT_RIGHT = 206  # the hint strip ends left of the power slots (x = 210 at 256 wide)
DOWNED_TICKS = 180
INTRO_SLIDE = 18  # ticks the name card takes to slide in during the boot
BEAM_TICKS = 10
DEFLECT_TICKS = 7
SECTOR_BANNER_TICKS = 90
SECTOR_TITLES = {
    "s2_entry": (2, "SECTOR 2", "COOLING PLANT", "px.jacket.2"),
    "s3_entry": (3, "SECTOR 3", "GRID CORE", "px.core.3"),
}
# Kit attacks drawn with another attack's tell shape (art/pixel/effects.py).
KIT_TELLS = {
    "double_ring": "ring",
    "double_quake": "quake",
    "core_spiral": "spiral",
    "live_wire_twice": "live_wire",
    "charge_twice": "charge",
    "lattice_twice": "lattice",
}
# Heavy walkers kick up dust when a foot comes down: (kind, feet below center, dust count).
FOOTFALLS = {"breaker": (12, 3), "regulator": (20, 5)}  # the Regulator's feet: per chassis
FOOT_DOWN = (2, 6)  # the walk steps where a foot lands (art/pixel/rig.py)


def hover(robot, tick: int) -> int:
    """How high a hovering robot floats above its shadow: a slow bob (Arc Drones only)."""
    if robot.kind != "drone":
        return 0
    return 2 + round(math.sin((tick + robot.id * 17) * 0.09) * 1.5)


def walk_step(gait: Gait | None, kind: str) -> int | None:
    """The walk cycle step for a body, from the distance it walked, or None standing."""
    if gait is None or gait.moved < WALKING:
        return None
    return int(gait.stride / STRIDE.get(kind, 3.0)) % rig.STEPS


def rival_heading(gait: Gait | None, facing_left: bool) -> int:
    """Direction of travel in sprite space, independent of where the boss is facing."""
    if gait is None or gait.moved < WALKING:
        return 0
    x = -gait.dx if facing_left else gait.dx
    return round(math.atan2(gait.dy, x) / (math.tau / 8)) % 8


def robot_image(
    robot,
    tick: int,
    left: bool,
    charging: bool,
    recover: int = DEFAULT.breaker_recover,
    gait: Gait | None = None,
    recoil: int = 0,
) -> pygame.Surface:
    """The approved roster art (art/pixel/robots.py) for a robot in its current state, in
    its sector's colors: stock orange, Cooled teal (sector 2) or Overcharged violet (sector 3).
    Only the shell ramp changes. The danger red of its eyes never changes, though the bright
    rim around some eyes shares the shell's highlight and takes the sector color. Walkers step
    with the distance they walked (`gait`). `recoil` counts down after a shot."""
    step = walk_step(gait, robot.kind)
    if robot.kind == "relay":
        image = robots_art.relay_bot(False, arming=robot.phase == "blink", step=step)
    elif robot.kind == "breaker":
        slamming = robot.phase == "recover" and robot.fire_timer > recover - 14
        image = robots_art.breaker(
            False, raising=robot.phase == "raise", slamming=slamming, step=step
        )
    elif robot.kind == "sweeper":
        image = robots_art.sweeper(step, False, revving=robot.phase == "rev", tick=tick)
    elif robot.kind == "sentry":
        scan = 3 if charging else SCAN[(tick // 12 + robot.id) % len(SCAN)]
        image = robots_art.sentry(False, scan=scan, kick=2 if recoil > RECOIL_TICKS // 2 else 0)
    else:
        image = robots_art.drone(tick // 2, False, step is not None, charging, robot.id)
    image = tier_colors(image, robot.tier)
    return robots_art.flipped(image) if left else image


_HOSTILE_RAMP = ("px.hostile.0", "px.hostile.1", "px.hostile.2", "px.hostile.3")
TIER_RAMPS = {
    2: ("px.conduit.0", "px.conduit.1", "px.jacket.1", "px.jacket.2"),  # not Blink cyan
    3: ("px.core.0", "px.core.1", "px.core.2", "px.core.3"),
}
_TIERED: dict[tuple[int, int], tuple[pygame.Surface, pygame.Surface]] = {}


def tier_colors(image: pygame.Surface, tier: int) -> pygame.Surface:
    """Swap the orange shell ramp for the tier's ramp. Cached per source frame (frames are
    cached surfaces, so the identity check keeps a stale entry from being reused)."""
    if tier == 1:
        return image
    key = (id(image), tier)
    hit = _TIERED.get(key)
    if hit is None or hit[0] is not image:
        swapped = image.copy()
        pixels = pygame.PixelArray(swapped)
        for source, target in zip(_HOSTILE_RAMP, TIER_RAMPS[tier], strict=True):
            pixels.replace(rgb(source), rgb(target))
        pixels.close()
        hit = _TIERED[key] = (image, swapped)
    return hit[1]


RIVAL_FLASH = -1  # flash key for the Regulator (hostile IDs are positive)
RIVAL_GAIT = -1  # and its key among the walk cycles
POSES = {"pressure": "clamp", "spacing": "insulate", "lateral": "oscillate"}


@cache
def _shadow(half: int) -> pygame.Surface:
    shade = pygame.Surface((half * 2, 5), pygame.SRCALPHA)
    pygame.draw.ellipse(shade, rgba("px.outline", 120), (0, 0, half * 2, 5))
    return shade


@cache
def big_text(message: str, token: str) -> pygame.Surface:
    """Twice-size pixel text with its shadow, for boss name cards and banners."""
    image = hud.pixel_font().render(message, False, rgb(token))
    shadow = hud.pixel_font().render(message, False, rgb("px.outline"))
    canvas = pygame.Surface((image.get_width() + 1, image.get_height() + 1), pygame.SRCALPHA)
    canvas.blit(shadow, (1, 1))
    canvas.blit(image, (0, 0))
    return pygame.transform.scale_by(canvas, 2)


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


@cache
def _edge_vignette(size: tuple[int, int], alpha: int, thickness: int) -> pygame.Surface:
    """A thin danger-red perimeter border for player hits and single-cell low battery."""
    w, h = size
    panel = pygame.Surface(size, pygame.SRCALPHA)
    outer = rgba("hostile.danger", alpha)
    inner = rgba("hostile.danger", alpha // 2)
    pygame.draw.rect(panel, outer, (0, 0, w, h), thickness)
    if w > thickness * 2 and h > thickness * 2:
        pygame.draw.rect(
            panel, inner, (thickness, thickness, w - thickness * 2, h - thickness * 2), 1
        )
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
    pool(84, "px.lamp", FLICKER_DIM)
    pool(84, "px.lamp", FLICKER_DIM * Lighting.TINT // 100)
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


@dataclass
class Mote:
    """A slow ambient particle: steam from a vent or dust in lamp light."""

    x: float
    y: float
    vx: float
    vy: float
    life: int
    token: str
    size: int


MAX_MOTES = 120
RIPPLE_TICKS = 18
FLICKER_DIM = 45  # a failing lamp's strength while it stutters


def flickering(tick: int, phase: int) -> bool:
    """A failing lamp stutters off for a few ticks at a time, in bursts now and then."""
    return (tick // 3 + phase * 13) % 97 in (0, 1, 3, 7, 8, 30)


# The Surge stays at least this far (x, y) from the view's edges, clear of the HUD's top
# and bottom rows and of its own sprite height.
SURGE_MARGIN = (40, 34)
LEAD_LIMIT = (VIEW[0] / 2 - SURGE_MARGIN[0], VIEW[1] / 2 - SURGE_MARGIN[1])


class PixelView:
    def __init__(self, run: Run | Campaign) -> None:
        self.room = tiles.render_room(
            run.arena.room, tiles.floor_sectors(run.arena.floor), run.arena.floor
        )
        self.room_data = run.arena.room
        self.room_size = run.arena.size
        self.glow = Glow(VIEW)
        self.lighting = Lighting(VIEW)
        self.cosmetic = random.Random(0)
        self.sparks: list[Spark] = []
        self.flashes: dict[int, int] = {}
        self.muzzle = 0
        self.ghosts: list[tuple[float, float, int]] = []
        self.blinks: list[tuple[float, float, int]] = []
        self.bursts: list[tuple] = []
        self.seen: set[str] = set()  # rooms the minimap has revealed (cosmetic only)
        self.sector = 1
        self.tint = [255.0, 255.0, 255.0]
        self.chains: list[tuple] = []
        self.blasts: list[tuple] = []  # ring effects: x, y, radius, life, power
        self.deflects: list[tuple[float, float, int]] = []  # shield bounce rings: x, y, life
        self.gaits: dict[int, Gait] = {}  # per robot id (-1 the Regulator): walk cycles
        self.frames = 0
        self.motes: list[Mote] = []  # steam and dust, drifting
        self.ripples: list[tuple[int, int, int]] = []  # drips on puddles: x, y, age
        self.flicker = {(e.x, e.y): e.phase for e in self.room.emitters if e.kind == "flicker"}
        self.beams: list[tuple[float, float, int]] = []  # Relay Bot teleports
        self.rival_last = None  # the last living chassis, for its wreck
        self.wreck: tuple | None = None  # image, feet, x, y, ticks left
        self.booms: list[tuple[float, float, int]] = []  # explosions on the wreck
        self.boss_banner: tuple[str, int] | None = None
        self.steps: dict[int, int | None] = {}  # each walker's last walk step, for footfalls
        self.recoils: dict[int, int] = {}  # per robot id: ticks since it fired, counting down
        self.lance_from: tuple[float, float] | None = None  # where a Bolt Lance started
        self.lance_bolt: tuple | None = None  # (start, end, life) after the lance ends
        self.notice: tuple[str, int] | None = None
        self.sector_banner: tuple[str, str, str, int] | None = None
        self.announced_sectors: set[int] = {1}
        self.unlock_flash = 0
        self.hit_vignette = 0
        self.shake = 0
        self.walking = 0
        self.last_player = (run.world.player.x, run.world.player.y)
        self.binds = Keybinds()  # the player's keys, for labels (app.py sets the loaded ones)
        self.coach = Coach(self.binds)  # first-run hints (game/coach.py)
        # Charges absorbed from afar, flying into the Surge: x, y, power, age.
        self.flyers: list[list] = []
        self.reward: list[str] = []  # the base powers a beaten chassis paid a spare of
        self.prev_slot_state: list[tuple[str, bool]] = [("", False), ("", False)]
        self.ready_flash = [0, 0]
        self.screen_shake = True
        self.reduce_flash = False
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
        """The camera. Aiming converts the cursor with this, so it never shakes."""
        return (round(self.camera[0]), round(self.camera[1]))

    def apply_settings(self, settings) -> None:
        """Apply cosmetic comfort settings (screen shake and reduced flashes)."""
        self.screen_shake = bool(settings.screen_shake)
        self.reduce_flash = bool(settings.reduce_flash)

    def jolt(self) -> tuple[int, int]:
        """A slam's screen shake (2 px at most, art direction), applied only when drawing
        the scene, so shots still go exactly where the reticle is."""
        if not self.screen_shake or self.shake <= 0:
            return (0, 0)
        amount = 2 if self.shake > 5 else 1
        return (
            amount * (1 if self.shake % 2 else -1),
            amount * (1 if self.shake % 4 < 2 else -1),
        )

    def _walk(self, world) -> None:
        """Advance every body's walk cycle by how far it moved this tick. A jump (a Relay's
        blink, a warp, a retry) is not a walk, so it resets the stride instead. Heavy feet
        kick up dust as they come down."""
        bodies = [(h.id, h.kind, h.x, h.y) for h in world.hostiles if h.health > 0]
        if world.rival is not None and world.rival.health > 0:
            bodies.append((RIVAL_GAIT, "regulator", world.rival.x, world.rival.y))
        seen = set()
        for key, kind, x, y in bodies:
            seen.add(key)
            gait = self.gaits.get(key)
            if gait is None:
                self.gaits[key] = Gait(x, y)
                continue
            moved = math.hypot(x - gait.x, y - gait.y)
            if moved > 6.0:  # teleported, not walked
                self.gaits[key] = Gait(x, y)
                continue
            gait.stride += moved
            gait.moved = moved
            if moved >= WALKING:
                gait.dx, gait.dy = x - gait.x, y - gait.y
            gait.x, gait.y = x, y
            step = walk_step(gait, kind)
            if kind in FOOTFALLS and step != self.steps.get(key) and step in FOOT_DOWN:
                feet, count = FOOTFALLS[kind]
                if key == RIVAL_GAIT:
                    feet = (
                        RIVAL_FEET.get(world.rival.kind, RIVAL_FEET["linesman"])
                        - regulators_art.GROUND_PAD
                    )
                self._burst(x, y + feet, count, "px.wall.3", 0.5)
            self.steps[key] = step
        for key in list(self.gaits):
            if key not in seen:
                del self.gaits[key]
                self.steps.pop(key, None)

    def _ambience(self, tick: int) -> None:
        """Animate the room's dressing near the camera (art/pixel/dressing.py): vents
        breathe steam, damaged panels spit sparks, puddles catch drips, and dust drifts
        through the lamp light. Cosmetic RNG only."""
        cx, cy = self.camera
        near = pygame.Rect(cx - 32, cy - 32, VIEW[0] + 64, VIEW[1] + 64)
        rng = self.cosmetic
        for emitter in self.room.emitters:
            if not near.collidepoint(emitter.x, emitter.y):
                continue
            beat = (tick + emitter.phase * 37) % 240
            if emitter.kind == "steam" and beat % 6 == 0 and beat < 60:
                self.motes.append(
                    Mote(
                        emitter.x + rng.uniform(-2, 2),
                        emitter.y,
                        rng.uniform(-0.15, 0.15),
                        rng.uniform(-0.5, -0.3),
                        rng.randint(28, 44),
                        "px.wall.3",
                        2,
                    )
                )
            elif emitter.kind == "sparks" and rng.random() < 1 / 150:
                for _ in range(rng.randint(3, 6)):
                    self.sparks.append(
                        Spark(
                            emitter.x,
                            emitter.y,
                            rng.uniform(-1.2, 1.2),
                            rng.uniform(-0.6, 1.4),
                            rng.randint(6, 12),
                            "px.lamp.light",
                        )
                    )
            elif emitter.kind == "drip" and beat == 0:
                self.ripples.append((emitter.x, emitter.y, 0))
        for x, y in self.room.lamps:  # dust motes drifting down through the lamp light
            if near.collidepoint(x, y) and rng.random() < 1 / 40:
                self.motes.append(
                    Mote(
                        x + rng.uniform(-14, 14),
                        y + rng.uniform(4, 16),
                        rng.uniform(-0.08, 0.08),
                        rng.uniform(0.04, 0.12),
                        rng.randint(90, 160),
                        "px.lamp.light",
                        1,
                    )
                )

    def update(self, run: Run | Campaign, cursor: tuple[int, int]) -> None:
        """Advance cosmetic state by one simulation tick. Called once per tick, never per
        rendered frame, so effects and camera behave the same at any display rate."""
        self.after_tick(run)
        self.follow(run, cursor)

    def after_tick(self, run: Run | Campaign) -> None:
        """Effects and animation for the tick that just ran (the camera moves separately,
        before the next input is read)."""
        self.consume(run, run.world.events)
        self._tick_cosmetics()
        self._tick_flyers(run)
        self._tick_slot_ready(run.world)
        self.coach.update(run)
        self._walk(run.world)
        rival = run.world.rival
        self.rival_last = rival if rival and rival.health > 0 else None
        if run.world.outcome == "down":
            self.wreck = self.boss_banner = self.sector_banner = None
            self.hit_vignette = 0
            self.booms.clear()
            self.flyers.clear()
        for wave in run.world.shockwaves:  # dust kicked up along the running ring
            for _ in range(3):
                a = self.cosmetic.uniform(0, math.tau)
                self.sparks.append(
                    Spark(
                        wave.x + math.cos(a) * wave.radius,
                        wave.y + math.sin(a) * wave.radius,
                        math.cos(a) * 0.3,
                        -0.4,
                        self.cosmetic.randint(6, 12),
                        "px.wall.3",
                    )
                )
        self.frames += 1  # the view's own clock: ambience keeps time while the world waits
        self._ambience(self.frames)
        floor = run.arena.floor
        if floor is not None:
            room = floorplay.room_of(floor, run.world.player.x, run.world.player.y)
            if room is not None:
                self.seen.add(room.id)
                self.sector = room.sector
                info = SECTOR_TITLES.get(room.id)
                if info is not None and info[0] not in self.announced_sectors:
                    self.announced_sectors.add(info[0])
                    self.sector_banner = (info[1], info[2], info[3], SECTOR_BANNER_TICKS)
            # Each sector has its own light, eased in as the Surge walks into it.
            target = rgb(f"px.tint.{self.sector}")
            self.tint = [c + (t - c) * 0.04 for c, t in zip(self.tint, target, strict=True)]

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
        # Far from the Regulator, the midpoint would push the Surge off screen: the lead
        # never takes the Surge closer than SURGE_MARGIN to an edge.
        lead_x = max(-LEAD_LIMIT[0], min(LEAD_LIMIT[0], lead_x))
        lead_y = max(-LEAD_LIMIT[1], min(LEAD_LIMIT[1], lead_y))
        target = (player.x + lead_x - VIEW[0] / 2, player.y + lead_y - VIEW[1] / 2)
        if getattr(run, "stage", None) == "ending" and self.boss_banner is not None:
            if self.wreck is None:
                return  # hold the framing through the victory banner
            _, _, wreck_x, wreck_y, _ = self.wreck
            target = (wreck_x - VIEW[0] / 2, wreck_y - VIEW[1] / 2)
            self.camera[0] += (target[0] - self.camera[0]) * 0.18
            self.camera[1] += (target[1] - self.camera[1]) * 0.18
            self._clamp_camera()
            return
        self.camera[0] += (target[0] - self.camera[0]) * 0.18
        self.camera[1] += (target[1] - self.camera[1]) * 0.18
        # The easing lags a dodge or a blink: never let it lag the Surge out of view.
        for axis, at in ((0, player.x), (1, player.y)):
            low, high = at - VIEW[axis] + SURGE_MARGIN[axis], at - SURGE_MARGIN[axis]
            self.camera[axis] = min(max(self.camera[axis], low), high)
        self._clamp_camera()

    # Events ---------------------------------------------------------------------------

    def consume(self, run: Run | Campaign, events: list[Event]) -> None:
        stolen: list[str] = []
        stolen_ids: list[str] = []
        chain_start = None
        blink_start = None
        for event in events:
            if event.kind == "shot":
                self.muzzle = 3
            elif event.kind in ("bolt", "shell", "shards"):
                self.recoils[event.ref] = RECOIL_TICKS
            elif event.kind == "hostile_hit":
                self.flashes[event.ref] = 4
                self._burst(event.x, event.y, 4, "px.spark.light", 1.2)
            elif event.kind == "hostile_destroyed":
                self._burst(event.x, event.y, 14, "px.hostile.3", 1.8)
                self._burst(event.x, event.y, 8, f"power.{event.power or 'spark'}", 1.4)
            elif event.kind == "player_hit":
                self._burst(event.x, event.y, 10, "player.core", 1.6)
                self.shake = max(self.shake, 8)
                self.hit_vignette = 10
            elif event.kind == "rival_hit":
                venting = event.power == "vent"
                damage = max(1, event.ref)
                heavy = damage >= 6
                self.flashes[RIVAL_FLASH] = 5 if venting else 4
                self._burst(
                    event.x,
                    event.y,
                    min(10, 3 + damage),
                    "px.hostile.3",
                    1.2 + (0.4 if heavy else 0.0),
                )
                if heavy:
                    self.shake = max(self.shake, 3)
                if venting:
                    self._burst(event.x, event.y, 10, "px.lamp.light", 2.0)
                    self._burst(event.x, event.y, 6, "power.spark", 1.7)
                    self.blasts.append((event.x, event.y, 18, BLAST_TICKS, "spark"))
                    self.shake = max(self.shake, 4)
            elif event.kind == "rival_destroyed" and run.world.outcome != "down":
                self._burst(event.x, event.y, 30, "px.hostile.3", 2.4)
                self._burst(event.x, event.y, 18, "px.lamp.light", 2.0)
                # The last tick's chassis survives the sim removing it from the room.
                rival = self.rival_last
                if rival is not None:
                    image = self._rival_sprite(rival, run.world.player, run.world.tick)
                    feet = (event.x, event.y + RIVAL_FEET.get(rival.kind, RIVAL_FEET["linesman"]))
                    self.wreck = (image, feet, event.x, event.y, WRECK_TICKS)
                    self.boss_banner = (f"{BY_KIND[rival.kind].name} DOWN", DOWNED_TICKS)
                self.shake = 16
                self.unlock_flash = 14
            elif event.kind == "rival_shielded":
                self._burst(event.x, event.y, 5, "px.wall.4", 1.1)
                self.deflects.append((event.x, event.y, DEFLECT_TICKS))
            elif event.kind == "blink_from":
                blink_start = (event.x, event.y)
                self.blinks.append((event.x, event.y, 16))
                self._burst(event.x, event.y, 6, "power.blink", 1.0)
            elif event.kind == "blink_to":
                self.blinks.append((event.x, event.y, 10))
                self._burst(event.x, event.y, 8, "px.blink.light", 1.4)
            elif event.kind == "rail":  # Magrail: a bolt from the Surge to where it stopped
                player = run.world.player
                self.chains.append(((player.x, player.y), (event.x, event.y), 8, False))
                self.shake = max(self.shake, 3)
            elif event.kind in ("hooked", "slammed"):
                self._burst(event.x, event.y, 8, "power.magnet", 1.4)
            elif event.kind in ("armor_absorb", "armor_up"):
                self._burst(event.x, event.y, 6, "power.bulwark", 1.2)
            elif event.kind == "armor_release":
                self._burst(event.x, event.y, 16, "power.spark", 2.0)
            elif event.kind in ("coil_planted", "fortress_up", "wave_out", "well_open"):
                self._burst(event.x, event.y, 8, "px.bulwark.light", 1.0)
            elif event.kind == "bulwark_up":
                self._burst(event.x, event.y, 10, "power.bulwark", 1.2)
            elif event.kind == "shield_absorb":
                self._burst(event.x, event.y, 4, "px.bulwark.light", 1.0)
            elif event.kind == "shield_reflect":
                self._burst(event.x, event.y, 3, "power.spark", 1.4)
            elif event.kind == "magnet_field":
                self._burst(event.x, event.y, 8, "power.magnet", 1.0)
            elif event.kind == "magnet_end" and event.ref:
                self._burst(event.x, event.y, 16, "px.magnet.light", 1.8)
                self.shake = max(self.shake, 4)
            elif event.kind in ("undertow", "riptide", "rod_planted", "toss", "mirror_up"):
                token = "power.blink" if event.kind in ("undertow", "riptide") else "power.bulwark"
                self._burst(event.x, event.y, 10, token, 1.2)
                if event.kind == "riptide":
                    self.blasts.append(
                        (event.x, event.y, run.tuning.riptide_radius, BLAST_TICKS, "magnet")
                    )
            elif event.kind == "grapple" and blink_start is not None:
                self.chains.append((blink_start, (event.x, event.y), 8, True))
                self._burst(event.x, event.y, 8, "power.magnet", 1.2)
            elif event.kind == "rewound":
                self._burst(event.x, event.y, 14, "px.bulwark.light", 1.2)
                self.blasts.append((event.x, event.y, 19, BLAST_TICKS, "blink"))
            elif event.kind == "mirror_release" and event.ref:
                self._burst(event.x, event.y, 12, "power.magnet", 1.6)
            elif event.kind == "magnet_rejected":
                self._burst(event.x, event.y, 4, "ui.dim", 0.6)
                self.toast("NO ROOM FOR A FIELD", 40)
            elif event.kind == "blink_rejected":
                self._burst(event.x, event.y, 4, "ui.dim", 0.6)
                self.toast(REJECTED.get(event.power, "NO ROOM TO BLINK"), 40)
            elif event.kind == "unlock":
                self._fly(run, event)
                self._burst(event.x, event.y, 24, f"power.{event.power}", 2.2)
                self.unlock_flash = 12
                stolen.append(NAMES.get(event.power, event.power.upper()))
                stolen_ids.append(event.power)
            elif event.kind == "absorb":
                self._fly(run, event)
                self._burst(event.x, event.y, 10, f"power.{event.power}", 1.4)
            elif event.kind == "burst":
                player = run.world.player
                angle = math.atan2(player.aim_y, player.aim_x)
                self.bursts.append((event.x, event.y, angle, bool(event.ref), event.power, 10))
            elif event.kind == "blast":
                self.blasts.append((event.x, event.y, event.ref, BLAST_TICKS, "burst"))
                self._burst(event.x, event.y, 14, "power.burst", 1.8)
                if event.power == "meteor":
                    self.shake = 10
            elif event.kind == "lance":
                self._burst(event.x, event.y, 10, "power.spark", 1.6)
                self.lance_from = (event.x, event.y)
            elif event.kind == "leap":
                self._burst(event.x, event.y + SURGE_FEET, 12, "px.wall.3", 1.4)
            elif event.kind == "chain_from":
                chain_start = (event.x, event.y)
            elif event.kind == "chain" and chain_start is not None:
                self.chains.append((chain_start, (event.x, event.y), 8, False))
            elif event.kind == "evolve":
                self._fly(run, event)
                self.unlock_flash = 12
                self._burst(event.x, event.y, 24, f"power.{event.power}", 2.2)
                name = NAMES.get(event.power, event.power.upper())
                self.toast(f"{name} EVOLVED: {EVOLUTIONS.get(event.power, '')}", 120)
            elif event.kind == "fully_evolved":
                self._fly(run, event)
                self._burst(event.x, event.y, 10, f"power.{event.power}", 1.4)
                self.toast("FULLY EVOLVED", 60)
            elif event.kind == "quake":
                self.shake = 14
                self._burst(event.x, event.y + 10, 30, "px.wall.3", 2.0)
                self._burst(event.x, event.y + 10, 12, "px.coil.3", 1.6)
            elif event.kind == "phase_change":
                self.shake = 14
                self.unlock_flash = 8
                self._burst(event.x, event.y, 26, "px.lamp.light", 2.4)
                self._burst(event.x, event.y, 14, "hostile.danger", 1.8)
            elif event.kind == "charge_impact":
                self.shake = 12
                self._burst(event.x, event.y, 20, "px.wall.3", 2.0)
            elif event.kind == "vent":
                self._burst(event.x, event.y - 6, 12, "px.wall.4", 1.4)
                self.toast("VENTING. HIT IT NOW", 50)
            elif event.kind == "boss_reward":
                # One spare of every stolen base power (sim/floorplay.py), flying from the
                # wreck into the Surge, and named under the DOWN banner.
                self.reward = [p for p in BASE_POWERS if p in run.world.unlocked]
                wreck = self.wreck
                at = (wreck[2], wreck[3]) if wreck else (event.x, event.y)
                for i, power in enumerate(self.reward):
                    # They leave once the explosions settle and the banner shows.
                    stagger = -(WRECK_TICKS - 10) - i * 6
                    self.flyers.append([at[0] + (i - 2) * 6, at[1], power, stagger])
            elif event.kind == "boss_ring":
                self._burst(event.x, event.y, 10, "hostile.danger", 1.2)
            elif event.kind == "summon":
                self._burst(event.x, event.y, 14, "power.burst", 1.4)
            elif event.kind == "slam":
                self.shake = 10
                self._burst(event.x, event.y + 6, 18, "px.wall.3", 1.6)
                self._burst(event.x, event.y + 6, 8, "px.dial.0", 1.2)
            elif event.kind == "room_lock":
                self.toast("LOCKDOWN", 60)
            elif event.kind == "room_clear" and self.boss_banner is None:
                pulled = any(f[3] <= 0 for f in self.flyers)
                self.toast("ROOM CLEAR. CHARGES PULLED IN" if pulled else "ROOM CLEAR", 90)
            elif event.kind == "warp_in":
                self._burst(event.x, event.y, 10, "hostile.danger", 1.4)
            elif event.kind == "secret_hit":
                self._burst(event.x, event.y, 4, "px.wall.3", 1.0)
            elif event.kind == "secret_open":
                self._burst(event.x, event.y, 20, "px.wall.3", 2.0)
                self.toast("A HIDDEN ROOM", 90)
            elif event.kind == "relay_from":
                self.blinks.append((event.x, event.y, 12))
                self.beams.append((event.x, event.y, BEAM_TICKS))  # it beams out
                self._burst(event.x, event.y, 6, "power.blink", 1.0)
            elif event.kind == "relay_blink":
                self.beams.append((event.x, event.y, BEAM_TICKS))  # and beams in
                self._burst(event.x, event.y + 8, 8, "px.blink.light", 1.2)
            elif event.kind == "fizzle":
                self._burst(event.x, event.y, 2, "px.bot.3", 0.6)
        if stolen:
            # A power that found no empty slot waits in the loadout (powers spec section 3).
            slots = run.world.player.slots
            waiting = "" not in slots and any(power not in slots for power in stolen_ids)
            hint = f". {self.binds.label('menu')} TO EQUIP" if waiting else ""
            self.toast(" AND ".join(stolen) + " STOLEN" + hint, 150 if waiting else 120)
        player = run.world.player
        moved = math.dist(self.last_player, (player.x, player.y)) > 0.1
        self.walking = self.walking + 1 if moved else 0
        self.last_player = (player.x, player.y)
        if player.dodging or (player.boost > 0 and run.world.tick % 3 == 0):
            self.ghosts.append((player.x, player.y, 10))  # dodge and Overdrive trails

    def _ripple(self, screen: pygame.Surface, world, cam: tuple[int, int]) -> None:
        """A shockwave lifts the floor tiles it passes over by up to 3 px, with a dark gap
        under each lifted tile, so the ground visibly rolls as the ring runs out."""
        room = self.room.background
        for wave in world.shockwaves:
            reach = wave.radius + 12
            x0, x1 = int((wave.x - reach) // TILE), int((wave.x + reach) // TILE)
            y0, y1 = int((wave.y - reach) // TILE), int((wave.y + reach) // TILE)
            for ty in range(y0, y1 + 1):
                for tx in range(x0, x1 + 1):
                    if self.room_data.is_wall(tx, ty):
                        continue
                    cx, cy = tx * TILE + TILE / 2, ty * TILE + TILE / 2
                    off = abs(math.hypot(cx - wave.x, cy - wave.y) - wave.radius)
                    lift = round(3 * (1 - off / 12)) if off < 12 else 0
                    if lift <= 0:
                        continue
                    sx, sy = tx * TILE - cam[0], ty * TILE - cam[1]
                    screen.fill(rgb("px.outline"), (sx, sy + TILE - lift, TILE, lift))
                    screen.blit(room, (sx, sy - lift), (tx * TILE, ty * TILE, TILE, TILE - lift))
                    screen.fill(rgb("px.wall.4"), (sx, sy - lift, TILE, 1))  # the lifted edge

    def _draw_doors(self, screen: pygame.Surface, run: Run | Campaign, v) -> None:
        """Locked doors: hazard-striped shutters. A locked secret wall looks like cracked wall,
        and the passage behind it stays dark until it opens."""
        floor = run.arena.floor
        if floor is None:
            return
        world = run.world
        locked = set(world.locked)
        secrets = [d for d in floor.doors if d.secret]
        if secrets and secrets[0].id in locked:
            top, bottom = sorted(secrets, key=lambda d: d.rect[1])
            x, y = top.rect[0], top.rect[1] + top.rect[3]
            hidden = (x * TILE, y * TILE, top.rect[2] * TILE, (bottom.rect[1] - y) * TILE)
            sx, sy = v(hidden[0], hidden[1])
            screen.fill(rgb("px.void"), (round(sx), round(sy), hidden[2], hidden[3]))
        for door in floor.doors:
            if door.id not in locked:
                continue
            x, y, w, h = door.rect
            sx, sy = v(x * TILE, y * TILE)
            rect = pygame.Rect(round(sx), round(sy), w * TILE, h * TILE)
            if door.secret:
                effects.cracked_wall(screen, rect, world.secret_hits.get(door.id, 0))
            else:
                effects.shutter(screen, self.glow.layer, rect, (world.tick // 8) % 2 == 0)

    def _minimap(self, screen: pygame.Surface, run: Run | Campaign) -> None:
        """Top right (art direction, HUD layout): a schematic of the 5 x 3 room grid, about
        50 x 22 px. Rooms show once seen, or as an outline once a door to them is known.
        Current room white, cleared grey, the locked room blinking red, a dot for chambers
        (red) and Fuse Boxes (blue). Corridors between shown rooms are 1 px lines."""
        floor = run.arena.floor
        if floor is None:
            return
        world = run.world
        cell_w, cell_h, gap = 8, 5, 3
        cols, rows = GRID
        x0 = screen.get_width() - 4 - (cols * (cell_w + gap) - gap)
        y0 = 4

        def cell(room) -> pygame.Rect:
            cx, cy = room.rect[0] // CELL[0], room.rect[1] // CELL[1]
            return pygame.Rect(x0 + cx * (cell_w + gap), y0 + cy * (cell_h + gap), cell_w, cell_h)

        seen = self.seen
        locked = set(world.locked)
        known = set(seen) | {
            d.other for d in floor.doors if d.room in seen and (not d.secret or d.id not in locked)
        }
        for door in floor.doors:
            if door.room < door.other and door.room in known and door.other in known:
                if door.secret and door.id in locked:
                    continue
                a, b = cell(floor.get(door.room)), cell(floor.get(door.other))
                pygame.draw.line(screen, rgb("px.outline"), a.center, b.center, 3)
                pygame.draw.line(screen, rgb("px.wall.2"), a.center, b.center, 1)
        here = floorplay.room_of(floor, world.player.x, world.player.y)
        for room in floor.rooms:
            if room.id not in known:
                continue
            rect = cell(room)
            screen.fill(rgb("px.outline"), rect.inflate(2, 2))
            if room.id not in seen:
                pygame.draw.rect(screen, rgb("px.floor.3"), rect, 1)
                continue
            token = "px.floor.3" if room.id in world.cleared else "px.wall.3"
            if here is not None and room.id == here.id:
                token = "player.core"
            screen.fill(rgb(token), rect)
            if room.id == world.active_room and (world.tick // 10) % 2 == 0:
                pygame.draw.rect(screen, rgb("hostile.danger"), rect, 1)
            mark = {"chamber": "hostile.danger", "fuse": "power.blink"}.get(room.kind)
            if mark:
                screen.fill(rgb(mark), (rect.centerx - 1, rect.centery - 1, 2, 2))

    def toast(self, message: str, ticks: int) -> None:
        self.notice = (message, ticks)

    def _fly(self, run, event) -> None:
        """A charge absorbed away from the Surge (a room clear pulls in every charge left)
        visibly flies into it, so nothing seems to vanish (pilot playtest, Nov 19)."""
        player = run.world.player
        touch = run.tuning.player_radius + run.tuning.charge_radius + 0.5
        if math.dist((event.x, event.y), (player.x, player.y)) > max(FLY_NEAR, touch):
            self.flyers.append([event.x, event.y, event.power, 0])

    def _tick_flyers(self, run) -> None:
        """Each flyer waits out its stagger, then homes in, quicker as it goes, and lands
        in a small burst."""
        player = run.world.player
        flying = []
        for flyer in self.flyers:
            flyer[3] += 1
            if flyer[3] <= 0:
                flying.append(flyer)
                continue
            pull = min(0.5, 0.04 + flyer[3] * 0.012)
            flyer[0] += (player.x - flyer[0]) * pull
            flyer[1] += (player.y - flyer[1]) * pull
            if self.cosmetic.random() < 0.5:
                self.sparks.append(Spark(flyer[0], flyer[1], 0.0, 0.0, 8, f"power.{flyer[2]}"))
            if math.dist((flyer[0], flyer[1]), (player.x, player.y)) < 4 or flyer[3] > FLY_TICKS:
                self._burst(player.x, player.y, 6, f"power.{flyer[2]}", 1.0)
            else:
                flying.append(flyer)
        self.flyers = flying

    def _tick_slot_ready(self, world) -> None:
        """Flash a HUD slot border briefly the tick its equipped power comes off cooldown."""
        if world.outcome == "down":
            self.ready_flash = [0, 0]
            self.prev_slot_state = [("", False), ("", False)]
            return
        player = world.player
        for i, slot in enumerate(player.slots[:2]):
            cooling = bool(slot) and player.cooldowns.get(COOLDOWN_KEYS[slot], 0) > 0
            prev_slot, prev_cooling = self.prev_slot_state[i]
            if not slot or cooling or slot != prev_slot:
                self.ready_flash[i] = 0
            elif prev_cooling and not cooling:
                self.ready_flash[i] = 6
            self.prev_slot_state[i] = (slot, cooling)

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
        self.recoils = {k: v - 1 for k, v in self.recoils.items() if v > 1}
        self.ghosts = [(x, y, life - 1) for x, y, life in self.ghosts if life > 1]
        self.blinks = [(x, y, life - 1) for x, y, life in self.blinks if life > 1]
        self.beams = [(x, y, life - 1) for x, y, life in self.beams if life > 1]
        self.booms = [(x, y, life - 1) for x, y, life in self.booms if life > 1]
        if self.wreck is not None:
            image, feet, x, y, ticks = self.wreck
            if ticks % 7 == 0:  # chained explosions over the body
                ex = x + self.cosmetic.uniform(-18, 18)
                ey = y + self.cosmetic.uniform(-26, 8)
                self._burst(ex, ey, 10, "px.lamp.light", 1.6)
                self._burst(ex, ey, 6, "hostile.danger", 1.2)
                self.booms.append((ex, ey, BOOM_TICKS))
                self.shake = max(self.shake, 4)
            self.wreck = (image, feet, x, y, ticks - 1) if ticks > 1 else None
        if self.boss_banner is not None:
            name, ticks = self.boss_banner
            self.boss_banner = (name, ticks - 1) if ticks > 1 else None
        for mote in self.motes:
            mote.x += mote.vx
            mote.y += mote.vy
            mote.life -= 1
        self.motes = [m for m in self.motes if m.life > 0][-MAX_MOTES:]
        self.ripples = [(x, y, age + 1) for x, y, age in self.ripples if age < RIPPLE_TICKS]
        self.bursts = [(*b[:5], b[5] - 1) for b in self.bursts if b[5] > 1]
        self.chains = [(a, b, life - 1, cable) for a, b, life, cable in self.chains if life > 1]
        self.blasts = [
            (x, y, r, life - 1, power) for x, y, r, life, power in self.blasts if life > 1
        ]
        self.deflects = [(x, y, life - 1) for x, y, life in self.deflects if life > 1]
        if self.lance_bolt:
            start, end, life = self.lance_bolt
            self.lance_bolt = (start, end, life - 1) if life > 1 else None
        self.unlock_flash = max(0, self.unlock_flash - 1)
        self.hit_vignette = max(0, self.hit_vignette - 1)
        self.shake = max(0, self.shake - 1)
        self.ready_flash = [max(0, ticks - 1) for ticks in self.ready_flash]
        if self.sector_banner is not None:
            title, subtitle, token, ticks = self.sector_banner
            self.sector_banner = (title, subtitle, token, ticks - 1) if ticks > 1 else None
        if self.notice:
            message, ticks = self.notice
            self.notice = (message, ticks - 1) if ticks > 1 else None
        self.muzzle = max(0, self.muzzle - 1)

    # Drawing --------------------------------------------------------------------------

    def draw(self, screen: pygame.Surface, run: Run | Campaign, cursor: tuple[int, int]) -> None:
        world, tuning = run.world, run.tuning
        player = world.player
        base, jolt = self.camera_offset(), self.jolt()
        cam = (base[0] + jolt[0], base[1] + jolt[1])
        tick = world.tick
        t = tick / 60

        def v(x: float, y: float) -> tuple[float, float]:
            return (x - cam[0], y - cam[1])

        screen.blit(self.room.background, (-cam[0], -cam[1]))
        self.glow.clear()
        self.glow.layer.blit(self.room.light, (-cam[0], -cam[1]))

        aim = math.atan2(player.aim_y, player.aim_x)
        facing_left = player.facing < 0

        def shadow(x: float, y: float, half: int) -> None:
            screen.blit(_shadow(half), (round(x - half), round(y - 3)))

        def draw_at_feet(image: pygame.Surface, feet: tuple[float, float]) -> None:
            fx, fy = v(*feet)
            screen.blit(image, (round(fx - image.get_width() / 2), round(fy - image.get_height())))

        self._ripple(screen, world, cam)
        self._draw_doors(screen, run, v)
        for warp in world.warps:
            effects.warp_marker(
                screen, self.glow.layer, v(warp.x, warp.y), 1 - warp.timer / tuning.warp_tell
            )
        for hazard in world.hazards:
            arming = (
                tuning.insulate_hazard_tell if hazard.kind == "insulate" else tuning.lattice_tell
            )
            progress = 1.0 - hazard.arming / arming if hazard.arming > 0 else 1.0
            if hazard.kind == "insulate":
                effects.hazard_tile(screen, self.glow.layer, v(hazard.x, hazard.y), progress)
            else:  # a boss kit's own floor marking: a Lattice cell or falling debris
                effects.kit_hazard(
                    screen,
                    self.glow.layer,
                    v(hazard.x, hazard.y),
                    hazard.size,
                    progress,
                    hazard.kind,
                    hazard.arming == 0,
                    self.frames,
                )

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
        for field in world.fields:  # Magnet fields and what the fused powers place
            self._draw_field(screen, field, tuning, v, tick)
        for device in world.devices:  # Shock Mines
            fuse = device.timer / tuning.shock_mine_fuse if device.timer >= 0 else -1.0
            effects.mine(screen, self.glow.layer, v(device.x, device.y), fuse)
        if player.leap > 0:  # Meteor: where the Surge will come down
            effects.landing_marker(
                screen,
                v(player.leap_x1, player.leap_y1),  # the true circle the blast hits
                tuning.meteor_radius,
                1.0 - player.leap / tuning.meteor_ticks,
            )
        for hostile in world.hostiles:
            if hostile.kind == "relay" and hostile.phase == "blink":
                # On the glow layer too, so the sector light never dims this tell.
                for surface in (screen, self.glow.layer):
                    effects.relay_destination(
                        surface,
                        v(hostile.dest_x, hostile.dest_y),
                        rules.tell_progress(hostile, tuning),
                    )
        for gx, gy, _life in self.blinks:
            effects.blink_ghost(screen, self.glow.layer, v(gx, gy))
        for bx, by, life in self.booms:
            effects.explosion(screen, self.glow.layer, v(bx, by), 1.0 - life / BOOM_TICKS)
        for rx, ry, age in self.ripples:
            effects.ripple(screen, v(rx, ry), age / RIPPLE_TICKS)
        for bx, by, life in self.beams:
            effects.relay_beam(screen, self.glow.layer, v(bx, by), life / BEAM_TICKS)

        for wave in world.shockwaves:
            robots_art.shockwave(screen, v(wave.x, wave.y), wave.radius)
            robots_art.shockwave(self.glow.layer, v(wave.x, wave.y), wave.radius)

        for hostile in world.hostiles:
            feet = (hostile.x, hostile.y + ROBOT_FEET.get(hostile.kind, 6))
            charging = rules.telegraphing(hostile, tuning)
            gait = self.gaits.get(hostile.id)
            walking = gait is not None and gait.moved >= WALKING
            if charging:
                left = hostile.tell_dx < 0
            elif walking and abs(gait.dx) > 0.05:
                left = gait.dx < 0  # face where it walks, never moonwalk
            else:
                left = player.x < hostile.x

            def draw_robot(
                hostile=hostile, feet=feet, charging=charging, left=left, gait=gait
            ) -> None:
                shadow(*v(*feet), round(hostile.radius) + 1)
                image = robot_image(
                    hostile,
                    tick,
                    left,
                    charging,
                    run.tuning.breaker_recover,
                    gait,
                    self.recoils.get(hostile.id, 0),
                )
                if hostile.id in self.flashes and not self.reduce_flash:
                    image = effects.tinted(image, "fx.flash")
                draw_at_feet(image, (feet[0], feet[1] - hover(hostile, tick)))
                if hostile.id in self.flashes and self.reduce_flash:
                    hx, hy = v(hostile.x, hostile.y - hover(hostile, tick))
                    pygame.draw.circle(
                        screen,
                        rgb("px.spark.light"),
                        (round(hx), round(hy)),
                        round(hostile.radius) + 2,
                        1,
                    )

            drawables.append((feet[1], draw_robot))

        for charge in world.charges:
            effects.charge(screen, self.glow.layer, v(charge.x, charge.y), charge.kind, t)
        for fx, fy, power, age in self.flyers:
            if age > 0:
                effects.charge(screen, self.glow.layer, v(fx, fy), power, t)

        rival = world.rival
        if rival is not None and rival.health > 0:
            rival_feet = (rival.x, rival.y + RIVAL_FEET.get(rival.kind, RIVAL_FEET["linesman"]))

            def draw_rival() -> None:
                shadow(*v(rival.x, rival_feet[1] - regulators_art.GROUND_PAD), round(rival.radius))
                image = self._rival_sprite(rival, player, tick)
                draw_at_feet(image, rival_feet)
                if RIVAL_FLASH in self.flashes:
                    if self.reduce_flash:
                        rx, ry = v(rival.x, rival.y)
                        pygame.draw.circle(
                            screen,
                            rgb("px.lamp.light"),
                            (round(rx), round(ry)),
                            round(rival.radius) + 2,
                            1,
                        )
                    else:
                        flash = effects.tinted(image, "fx.flash")
                        flash.set_alpha(self.flashes[RIVAL_FLASH] * 24)
                        draw_at_feet(flash, rival_feet)
                if rival.boot > 0 and (tick // 4) % 3:
                    cx, cy = v(rival.x, rival.y)
                    ring = pygame.Rect(0, 0, 40, 46)
                    ring.center = (round(cx), round(cy) + 2)
                    for surface in (screen, self.glow.layer):
                        pygame.draw.ellipse(surface, rgb("px.hostile.2"), ring, 1)

            drawables.append((rival_feet[1], draw_rival))

        if self.wreck is not None:
            w_image, w_feet, _wx, _wy, w_ticks = self.wreck

            def draw_wreck(image=w_image, feet=w_feet, ticks=w_ticks) -> None:
                if ticks % 4 < 2 or ticks < 20:  # it flickers, then holds as it fades
                    sink = (WRECK_TICKS - ticks) // 8
                    flash_wreck = ticks % 8 == 0 and not self.reduce_flash
                    shown = effects.tinted(image, "fx.flash") if flash_wreck else image
                    fx, fy = v(*feet)
                    clip = pygame.Rect(0, 0, image.get_width(), image.get_height() - sink)
                    screen.blit(
                        shown,
                        (round(fx - image.get_width() / 2), round(fy - image.get_height() + sink)),
                        clip,
                    )

            drawables.append((w_feet[1], draw_wreck))

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
            lift = 0
            if player.leap > 0:  # Meteor: an arc up and down over the ground shadow
                done = 1.0 - player.leap / tuning.meteor_ticks
                lift = round(28 * 4 * done * (1.0 - done))
            draw_at_feet(image, (surge_feet[0], surge_feet[1] - lift))
            if player.lance and player.dodging:
                effects.lance_streak(
                    screen, self.glow.layer, v(player.x, player.y), player.dodge_dx, player.dodge_dy
                )
                if self.lance_from is not None:  # the bolt from where the dash began
                    effects.chain_bolt(
                        screen, self.glow.layer, v(*self.lance_from), v(player.x, player.y)
                    )
                    self.lance_bolt = (self.lance_from, (player.x, player.y), 8)
            elif self.lance_bolt:
                start, end, _life = self.lance_bolt
                effects.chain_bolt(screen, self.glow.layer, v(*start), v(*end))
            else:
                self.lance_from = None
            if player.aura > 0:
                effects.aura(screen, self.glow.layer, v(player.x, player.y), tick)
            if player.shield > 0:
                effects.bubble(
                    screen,
                    self.glow.layer,
                    v(player.x, player.y),
                    tuning.bulwark_radius,
                    player.shield / tuning.bulwark_ticks,
                    tick,
                    BUBBLE_ACCENTS.get(player.shield_kind, ""),
                )
            if player.armor > 0:
                effects.armor_pips(
                    screen, self.glow.layer, v(player.x, player.y), player.armor, tick
                )
            if player.mirror > 0:
                effects.fusion_orbit(
                    screen,
                    self.glow.layer,
                    v(player.x, player.y),
                    tuning.mirror_radius,
                    tick,
                    player.caught,
                )
            hand = v(*aiming.hand(player, tuning))
            hand = (hand[0], hand[1] - lift)  # the caster rises with a Meteor
            caster = pygame.transform.rotate(actors.caster(), -math.degrees(aim))
            screen.blit(
                caster,
                caster.get_rect(
                    center=(round(hand[0] + player.aim_x * 4), round(hand[1] + player.aim_y * 4))
                ),
            )
            if self.muzzle:
                tip = v(*aiming.muzzle(player, tuning))
                for surface in (screen, self.glow.layer):
                    pygame.draw.circle(
                        surface, rgb("player.core"), (round(tip[0]), round(tip[1])), 2
                    )

        decoy = world.decoy
        if decoy is not None:

            def draw_decoy() -> None:
                image = effects.tinted(actors.surge("idle", tick, facing_left), "power.blink")
                fx, fy = v(decoy.x, decoy.y + SURGE_FEET)
                effects.ghost(
                    screen,
                    image,
                    (fx - image.get_width() / 2, fy - image.get_height()),
                    min(165, decoy.ticks * 8),
                )
                effects.bubble(
                    screen,
                    self.glow.layer,
                    v(decoy.x, decoy.y),
                    11,
                    decoy.ticks / tuning.decoy_ticks,
                    tick,
                    "power.blink",
                )

            drawables.append((decoy.y + SURGE_FEET, draw_decoy))

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
                progress = rules.tell_progress(hostile, tuning)
                if hostile.kind == "breaker":  # the slam: a ring shows where it will reach
                    effects.slam_tell(
                        screen,
                        self.glow.layer,
                        v(hostile.x, hostile.y),
                        tuning.wave_reach,
                        progress,
                    )
                else:
                    reach = {"sentry": 120, "sweeper": 80}.get(hostile.kind, 64)
                    effects.aim_tell(
                        screen,
                        self.glow.layer,
                        v(hostile.x, hostile.y),
                        math.atan2(hostile.tell_dy, hostile.tell_dx),
                        progress,
                        reach=reach,
                    )
            token = CORE_GLOW.get(hostile.kind)
            if token:
                core = v(hostile.x, hostile.y - hover(hostile, tick))  # rides the hover bob
                self.glow.layer.fill(rgb(token), (round(core[0]) - 1, round(core[1]), 2, 2))
        if rival is not None and rival.health > 0:
            self._draw_kit(screen, run, rival, v)
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
            if shot.hostile and shot.kind in SHOT_ART:
                image = SHOT_ART[shot.kind]()
                if shot.kind == "needle":
                    image = pygame.transform.rotate(
                        image, -math.degrees(math.atan2(shot.vy, shot.vx))
                    )
                center = tuple(map(round, v(shot.x, shot.y)))
                for surface in (screen, self.glow.layer):
                    surface.blit(image, image.get_rect(center=center))
            elif shot.hostile:
                effects.bolt(screen, self.glow.layer, v(shot.x, shot.y))
            elif shot.kind == "lodestone":
                effects.heavy_spark(screen, self.glow.layer, v(shot.x, shot.y), tick)
            elif shot.kind == "hook":
                effects.hook_shot(
                    screen, self.glow.layer, v(shot.x, shot.y), math.atan2(shot.vy, shot.vx)
                )
            elif shot.kind in ("spark", "reflect"):
                effects.spark_shot(
                    screen, self.glow.layer, v(shot.x, shot.y), math.atan2(shot.vy, shot.vx)
                )
            else:
                effects.player_shot(
                    screen, self.glow.layer, v(shot.x, shot.y), math.atan2(shot.vy, shot.vx)
                )

        for x, y, angle, wide, power, life in self.bursts:
            reach = tuning.burst_wide_range if wide else tuning.burst_range
            cone = tuning.burst_wide_cos if wide else tuning.burst_cos
            vortex = power == "vortex_cone"
            effects.burst_cone(
                screen,
                self.glow.layer,
                v(x, y),
                angle,
                tuning.vortex_range if vortex else reach,
                cone,
                life / 10,
                power == "shock_cone",
                vortex,
            )
        for a, b, _life, cable in self.chains:
            effects.chain_bolt(screen, self.glow.layer, v(*a), v(*b), cable)
        for x, y, radius, life, power in self.blasts:
            effects.blast_ring(screen, self.glow.layer, v(x, y), radius, life / BLAST_TICKS, power)
        for x, y, life in self.deflects:
            effects.deflect_ring(screen, self.glow.layer, v(x, y), life / DEFLECT_TICKS)
        for mote in self.motes:
            mx, my = v(mote.x, mote.y)
            screen.fill(rgb(mote.token), (round(mx), round(my), mote.size, mote.size))
        for spark in self.sparks:
            sx, sy = v(spark.x, spark.y)
            for surface in (screen, self.glow.layer):
                pygame.draw.line(
                    surface, rgb(spark.token), (sx, sy), (sx - spark.vx * 2, sy - spark.vy * 2), 1
                )

        self.lighting.begin()
        for i, (x, y) in enumerate(self.room.lamps):
            pulse = quantize(90 + 10 * math.sin(t * 2 + i))
            phase = self.flicker.get((x, y))
            if phase is not None and flickering(self.frames, phase):
                pulse = FLICKER_DIM
                lx, ly = v(x, y)  # the lens goes dark with its light
                lens = (round(lx) - 3, round(ly) - 2, 6, 3)
                self.glow.layer.fill(rgb("fx.none"), lens)
                screen.fill(rgb("px.bot.1"), lens)
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
            # A tight pool of reflected light keeps the moving armor legible in blackout.
            self.lighting.add(v(rival.x, rival.y - 9), 60, "px.lamp.light", 95)
            if rival.phase > 1:
                self.lighting.add(v(rival.x, rival.y), 28, "px.hostile.2", 30 * rival.phase)
        self.lighting.apply(screen)
        tint = tuple(round(c) for c in self.tint)
        if tint != (255, 255, 255):
            screen.fill(tint, special_flags=pygame.BLEND_RGB_MULT)
        self.glow.apply(screen)
        stage = getattr(run, "stage", None)
        self._draw_vignette(screen, player, world.outcome, stage)

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
                        player.cooldowns.get(COOLDOWN_KEYS[slot], 0) / cooldown_of(slot, tuning),
                    )
                    if slot
                    else 0.0
                    for slot in player.slots
                ),
                rival_health=(max(0, rival.health) / rival.max_health) if rival else None,
                rival_protocol=POSES[rival.protocol] if rival else None,
                rival_name=BY_KIND[rival.kind].name if rival else "REGULATOR",
                rival_phases=max(1, len(BY_KIND[rival.kind].phases)) if rival else 1,
                rival_phase=rival.phase if rival else 1,
                rival_changing=bool(rival and rival.change > 0),
                rival_venting=bool(rival and rival.vent > 0),
                tick=tick,
                keys=(self.binds.short("power_q"), self.binds.short("power_e")),
                ready_flash=(self.ready_flash[0], self.ready_flash[1]),
                reduce_flash=self.reduce_flash,
            ),
        )
        self._minimap(screen, run)
        if rival is not None and rival.health > 0 and rival.boot > 0:
            self._intro_card(screen, rival, tuning)
        sector_visible = (
            self.boss_banner is None
            and self.sector_banner is not None
            and rival is None
            and world.outcome == "playing"
            and stage != "ending"
        )
        if self.boss_banner is not None:
            self._boss_banner(screen)
        elif sector_visible:
            self._sector_banner(screen)
        if self.unlock_flash:
            if self.reduce_flash:
                if self.unlock_flash > 4:
                    pygame.draw.rect(screen, rgb("power.spark"), (0, 0, VIEW[0], VIEW[1]), 2)
            else:
                screen.blit(_flash(VIEW, self.unlock_flash * 8), (0, 0))
        self._coach(screen, run, cam)
        if self.notice:
            message, ticks = self.notice
            if ticks > 8 or ticks % 2:
                if sector_visible:
                    y = 50
                elif rival and BY_KIND[rival.kind].phases:
                    y = 33
                else:
                    y = 26
                hud.text(screen, message, (VIEW[0] // 2, y), "power.spark", "midtop")
        if world.outcome == "down" or (stage is None and world.outcome == "clear"):
            self._banner(screen, world.outcome)
        reticle = effects.reticle()
        screen.blit(reticle, reticle.get_rect(center=cursor))

    def _rival_sprite(self, rival, player, tick: int) -> pygame.Surface:
        needle = math.atan2(player.y - rival.y, player.x - rival.x)
        facing_left = rival.aim_x < 0 if rival.action in ("tell", "dash") else player.x < rival.x
        charging = bosskit.charging(rival)
        if charging or (rival.sig_action == "tell" and rival.sig_name.startswith("charge")):
            facing_left = rival.aim_x < 0
        gait = self.gaits.get(RIVAL_GAIT)
        return regulators_art.regulator(
            POSES[rival.protocol],
            facing_left,
            needle,
            rival.protocol == "lateral" and rival.action == "tell" and (tick // 4) % 2 == 0,
            kind=rival.kind,
            phase=rival.phase,
            step=walk_step(gait, "regulator"),
            heading=rival_heading(gait, facing_left),
            charged=rival.sig_action == "tell" or charging or rival.change > 0,
            vent=rival.vent > 0,
        )

    def advance_defeat(self) -> None:
        """Finish a replay's visual coda after its last recorded input."""
        self._tick_cosmetics()

    def _draw_field(self, screen: pygame.Surface, field, tuning, v, tick: int) -> None:
        glow = self.glow.layer
        at = v(field.x, field.y)
        if field.kind == "magnet":
            left = field.timer / tuning.magnet_ticks
            effects.magnet_field(screen, glow, at, tuning.magnet_radius, left, tick)
        elif field.kind == "coil":
            effects.coil(screen, glow, at, tick)
        elif field.kind == "wave":
            half = tuning.reflector_width / 2
            px, py = -field.ty * half, field.tx * half
            effects.wall_of_force(
                screen, glow, v(field.x + px, field.y + py), v(field.x - px, field.y - py)
            )
        elif field.kind == "fortress":
            effects.dome(screen, glow, at, tuning.fortress_radius, tick)
        elif field.kind == "implosion":
            left = field.timer / tuning.implosion_ticks
            effects.magnet_field(
                screen, glow, at, tuning.implosion_radius, left, tick, "power.burst"
            )
        elif field.kind == "well":
            left = field.timer / tuning.well_ticks
            effects.gravity_well(screen, glow, at, tuning.well_radius, left, tick)
        elif field.kind == "undertow":
            left = field.timer / tuning.undertow_ticks
            effects.magnet_field(
                screen, glow, at, tuning.undertow_radius, left, tick, "power.blink"
            )
        elif field.kind == "rod":
            left = field.timer / tuning.rod_ticks
            effects.magnet_field(screen, glow, at, tuning.rod_radius, left, tick, "power.bulwark")
            effects.coil(screen, glow, at, tick)
        elif field.kind == "toss":
            effects.bubble(screen, glow, at, tuning.toss_radius, 1.0, tick, "power.magnet")
            effects.charge(screen, glow, at, "bulwark", tick / TICK_RATE)

    def _draw_vignette(
        self, screen: pygame.Surface, player, outcome: str, stage: str | None = None
    ) -> None:
        """Danger-red perimeter border on player damage or when down to the last battery cell."""
        if stage == "ending" or outcome != "playing":
            return
        if self.hit_vignette > 0:
            if self.reduce_flash:
                screen.blit(_edge_vignette(screen.get_size(), 48, 2), (0, 0))
            else:
                alpha = (self.hit_vignette * 14 // 8) * 8
                if alpha > 0:
                    screen.blit(_edge_vignette(screen.get_size(), alpha, 4), (0, 0))
            return
        if player.charge == 1:
            if self.reduce_flash:
                screen.blit(_edge_vignette(screen.get_size(), 40, 2), (0, 0))
            else:
                # Slow ~1 Hz breathing pulse (well under the 3 Hz photosensitivity ceiling).
                raw = round(38 + 26 * math.sin(self.frames * 0.12))
                alpha = max(16, (raw // 8) * 8)
                screen.blit(_edge_vignette(screen.get_size(), alpha, 3), (0, 0))

    def _sector_banner(self, screen: pygame.Surface) -> None:
        """Non-blocking arrival card when stepping into Sector 2 or Sector 3."""
        title, subtitle, token, ticks = self.sector_banner
        w = screen.get_width()
        card = pygame.Surface((138, 25), pygame.SRCALPHA)
        card.blit(_dim(card.get_size(), 200), (0, 0))
        card.fill(rgb(token), (0, 0, card.get_width(), 1))
        card.fill(rgb(token), (0, card.get_height() - 1, card.get_width(), 1))
        hud.text(card, title, (card.get_width() // 2, 3), "ui.text", "midtop")
        hud.text(card, subtitle, (card.get_width() // 2, 13), token, "midtop")
        if ticks < 16:
            card.set_alpha(max(0, ticks * 16))
        screen.blit(card, card.get_rect(midtop=(w // 2, 22)))

    def _intro_card(self, screen: pygame.Surface, rival, tuning) -> None:
        """Bring in the chassis name and active protocol during boot, above the power slots.
        Identical across live, fixed and off conditions (D5 revision, Nov 21)."""
        w, h = screen.get_size()
        elapsed = tuning.rival_boot - rival.boot
        slide = min(1.0, elapsed / INTRO_SLIDE)
        x = round(-120 + (w // 2 + 120) * (1 - (1 - slide) ** 3))
        panel = pygame.Rect(0, h - 72, 170, 38)
        panel.centerx = x
        screen.blit(_dim(panel.size, 220), panel)
        pygame.draw.rect(screen, rgb("px.hostile.2"), panel, 1)
        name = big_text(BY_KIND[rival.kind].name, "hostile.danger")
        screen.blit(name, name.get_rect(midtop=(x, panel.y + 2)))
        hud.text(screen, f"SECTOR {self.sector} REGULATOR", (x, panel.y + 18), "ui.dim", "midtop")
        pose = POSES[rival.protocol]
        icon = effects.protocol_icon(pose)
        label = f"{pose.upper()} PROTOCOL"
        label_w = hud.pixel_font().size(label)[0]
        row_x = x - (icon.get_width() + 3 + label_w) // 2
        screen.blit(icon, icon.get_rect(midleft=(row_x, panel.y + 31)))
        hud.text(screen, label, (row_x + icon.get_width() + 3, panel.y + 26), "px.hazard.1")

    def _boss_banner(self, screen: pygame.Surface) -> None:
        name, ticks = self.boss_banner
        if ticks > DOWNED_TICKS - WRECK_TICKS:
            return  # the banner waits for the explosions
        w, h = screen.get_size()
        screen.blit(_banner_panel(w), (0, h // 2 - 17))
        title = big_text(name, "px.lamp.light")
        screen.blit(title, title.get_rect(center=(w // 2, h // 2 - 4)))
        message = (
            "THE GRID IS BACK ONLINE" if name == "GRID CORE DOWN" else "THE GRID HOLDS. FOR NOW"
        )
        hud.text(screen, message, (w // 2, h // 2 + 7), "ui.dim", "midtop")
        if self.reward and name != "GRID CORE DOWN":  # the last chassis ends the run
            self._reward_panel(screen, h // 2 + 19)

    def _reward_panel(self, screen: pygame.Surface, top: int) -> None:
        """Under the DOWN banner: what the chassis paid, as icons with +1, and what it is
        for (pilot playtest, Nov 19: the boss seemed to give nothing)."""
        w = screen.get_width()
        panel = pygame.Rect(0, top, w, 25)
        screen.blit(_dim(panel.size, 200), panel)
        label = "REWARD"
        label_w = hud.pixel_font().size(label)[0] + 6
        span = label_w + len(self.reward) * 22
        x = w // 2 - span // 2
        hud.text(screen, label, (x, top - 2), "px.hazard.1")
        for i, power in enumerate(self.reward):
            cx = x + label_w + i * 22
            icon = effects.charge_icon(power)
            screen.blit(icon, icon.get_rect(midleft=(cx, top + 6)))
            hud.text(screen, "+1", (cx + 9, top - 2), "ui.text")
        message = "SPARE CHARGES PAY FOR FUSE REROLLS"
        hud.text(screen, message, (w // 2, top + 9), "ui.dim", "midtop")

    def _coach(self, screen: pygame.Surface, run, cam: tuple[int, int]) -> None:
        """The first-run hint, bottom center, and an arrow at the screen's edge toward the
        Fuse Box while the hint points there."""
        message = self.coach.hint(run)
        if message is None or self.boss_banner is not None:
            return
        w, h = screen.get_size()
        room = HINT_RIGHT - 2  # from x = 2 to the power slots
        width = hud.pixel_font().size(message)[0] + 8
        if width > room:  # long bound key names: write them short
            message = self.coach.hint(run, short=True) or message
            width = hud.pixel_font().size(message)[0] + 8
        panel = pygame.Rect(0, h - 16, min(width, room), 12)
        panel.centerx = w // 2 - 12
        panel.right = min(panel.right, HINT_RIGHT)
        panel.left = max(panel.left, 2)
        screen.blit(_dim(panel.size, 200), panel)
        token = "px.hazard.1" if (self.frames // 30) % 2 else "ui.text"
        hud.text(screen, message, (panel.centerx, panel.y - 2), token, "midtop")
        target = self.coach.target
        if target is not None:
            self._arrow(screen, (target[0] - cam[0], target[1] - cam[1]))

    def _arrow(self, screen: pygame.Surface, point: tuple[float, float]) -> None:
        """A chevron toward `point` (view pixels): over it when on screen, else at the
        edge in its direction."""
        w, h = screen.get_size()
        cx, cy = w / 2, h / 2
        dx, dy = point[0] - cx, point[1] - cy
        dist = math.hypot(dx, dy) or 1.0
        ux, uy = dx / dist, dy / dist
        margin = 14
        inside = margin <= point[0] <= w - margin and margin <= point[1] <= h - margin
        if inside:
            tip = (point[0], point[1] - 12 - 2 * math.sin(self.frames / 6))
            ux, uy = 0.0, 1.0
        else:
            scale = min(
                (w / 2 - margin) / abs(ux) if ux else math.inf,
                (h / 2 - margin) / abs(uy) if uy else math.inf,
            )
            tip = (cx + ux * scale, cy + uy * scale)
        nx, ny = -uy, ux
        back = (tip[0] - ux * 7, tip[1] - uy * 7)
        points = [tip, (back[0] + nx * 5, back[1] + ny * 5), (back[0] - nx * 5, back[1] - ny * 5)]
        pygame.draw.polygon(screen, rgb("px.outline"), [(x + 1, y + 1) for x, y in points])
        token = "power.blink" if (self.frames // 15) % 2 else "ui.text"
        pygame.draw.polygon(screen, rgb(token), points)

    def _draw_kit(self, screen: pygame.Surface, run, rival, v) -> None:
        """The chassis kit on screen (sim/bosskit.py): each attack's own tell, Live Wire's
        lines while they burn, and the vent window's steam."""
        tuning = run.tuning
        name = rival.sig_name
        center = v(rival.x, rival.y)
        aim = math.atan2(rival.aim_y, rival.aim_x)
        if rival.sig_action == "tell":
            progress = 1.0 - rival.sig_timer / bosskit.current_tell(rival, tuning)
            base = KIT_TELLS.get(name, name)
            if base in ("ring", "quake", "summon", "spiral"):
                effects.signature_tell(
                    screen,
                    self.glow.layer,
                    center,
                    base,
                    progress,
                    reach=tuning.quake_reach,
                    aim=aim,
                    points=[v(x, y) for x, y in rules.summon_points(run.arena)],
                    arms=4 if name == "core_spiral" else 2,
                )
            else:
                effects.kit_tell(
                    screen,
                    self.glow.layer,
                    center,
                    base,
                    progress,
                    aim=aim,
                    lines=[
                        (v(x1, y1), v(x2, y2))
                        for x1, y1, x2, y2 in bosskit.wire_segments(rival, tuning)
                    ],
                    marks=[v(x, y) for x, y in rival.marks],
                    width=rival.radius,
                )
        elif rival.sig_action == "active" and name.startswith("live_wire"):
            for x1, y1, x2, y2 in bosskit.wire_segments(rival, tuning):
                effects.live_wire(screen, self.glow.layer, v(x1, y1), v(x2, y2), self.frames)
        if rival.vent > 0 and self.frames % 5 == 0:  # it vents: steam off its core
            self._burst(rival.x, rival.y - 6, 3, "px.wall.4", 1.0)

    def draw_campaign_ending(
        self, screen: pygame.Surface, run: Campaign, can_return: bool = False
    ) -> None:
        if run.stage == "ending" and self.boss_banner is None:
            self.draw_ending(
                screen,
                run.stats["ticks"] / TICK_RATE,
                sum(run.retries.values()),
                run.stats["shots"],
                run.stats["powers"],
                run.stats["bosses"],
                can_return,
            )

    def draw_ending(
        self,
        screen: pygame.Surface,
        seconds: float,
        retries: int,
        shots: int,
        powers: dict[str, int] | None = None,
        bosses: dict[str, int] | None = None,
        can_return: bool = False,
    ) -> None:
        """The readout: completion time, short circuits, shots and the powers tried. No score
        and no ranking (GDD)."""
        w, h = screen.get_size()
        screen.blit(_dim(screen.get_size(), 235), (0, 0))
        tried = [(name, n) for name, n in (powers or {}).items() if n and name in NAMES]
        two_rows = len(tried) > 10
        hud.text(screen, "SECTOR CLEAR", (w // 2, 4 if two_rows else 12), "ui.text", "midtop")
        hud.text(
            screen,
            "THE GRID IS BACK ONLINE",
            (w // 2, 13 if two_rows else 23),
            "ui.dim",
            "midtop",
        )
        minutes, rest = divmod(int(seconds), 60)
        rows = (
            ("TIME", f"{minutes:02d}:{rest:02d}"),
            ("SHORT CIRCUITS", str(retries)),
            ("SHOTS", str(shots)),
        )
        row_top = 23 if two_rows else 36
        row_step = 9 if two_rows else 11
        for i, (label, value) in enumerate(rows):
            y = row_top + i * row_step
            hud.text(screen, label, (w // 2 - 6, y), "ui.dim", "topright")
            hud.text(screen, value, (w // 2 + 6, y), "ui.text")
        fights = [ticks for _, ticks in sorted((bosses or {}).items())]
        if fights:  # each chassis' fight time, in the order they fell
            times = "  ".join(f"{t // TICK_RATE // 60}:{t // TICK_RATE % 60:02d}" for t in fights)
            hud.text(
                screen,
                f"BOSSES {times}",
                (w // 2, 52 if two_rows else 71),
                "px.hazard.1",
                "midtop",
            )
        hud.text(screen, "POWERS TRIED", (w // 2, 63 if two_rows else 85), "ui.dim", "midtop")
        if not tried:
            hud.text(screen, "GUN AND DODGE ONLY", (w // 2, 100), "px.floor.3", "midtop")
        elif not two_rows:
            stride = min(28, (w - 16) // len(tried))
            self._draw_ending_row(screen, tried, 102, stride)
        else:
            max_items = 22
            if len(tried) > max_items:
                overflow = len(tried) - (max_items - 1)
                entries: list[tuple[str, int] | None] = [*tried[: max_items - 1], None]
            else:
                overflow = 0
                entries = list(tried)
            split = (len(entries) + 1) // 2
            top_row = entries[:split]
            bot_row = entries[split:]
            stride = min(22, (w - 12) // max(len(top_row), len(bot_row)))
            self._draw_ending_row(screen, top_row, 83, stride)
            self._draw_ending_row(screen, bot_row, 107, stride, overflow=overflow)
        footer = "SPACE TITLE   ESC QUIT" if can_return else "ESC TO QUIT"
        hud.text(screen, footer, (w // 2, h - 21), "px.hazard.1", "midtop")
        hud.text(screen, self.stamp, (4, h - 2), "px.floor.3", "bottomleft")

    def _draw_ending_row(
        self,
        screen: pygame.Surface,
        entries: list[tuple[str, int] | None],
        cy: int,
        stride: int,
        overflow: int = 0,
    ) -> None:
        """One centered row of tried-power icons with rarity marks above fused powers."""
        w = screen.get_width()
        start = w // 2 - (len(entries) * stride) // 2 + stride // 2
        for i, entry in enumerate(entries):
            x = start + i * stride
            if entry is None:
                hud.text(screen, f"+{overflow}", (x, cy - 3), "ui.dim", "midtop")
                continue
            name, count = entry
            rarity = rarity_of(name)
            if rarity:
                mark_w = (RARITIES.index(rarity) + 1) * 4 - 1
                hud.rarity_marks(screen, rarity, x - mark_w // 2, cy - 8)
            icon = effects.charge_icon(name)
            screen.blit(icon, icon.get_rect(center=(x, cy)))
            hud.text(screen, str(count), (x, cy + 4), "ui.text", "midtop")

    def _banner(self, screen: pygame.Surface, outcome: str) -> None:
        w, h = screen.get_size()
        key = self.binds.label("retry")
        title, hint = (
            ("SHORT CIRCUIT", f"{key} TO RETRY")
            if outcome == "down"
            else ("SECTOR CLEAR", f"{key} TO RUN IT AGAIN")
        )
        screen.blit(_banner_panel(w), (0, h // 2 - 17))
        hud.text(screen, title, (w // 2, h // 2 - 12), "ui.text", "midtop")
        hud.text(screen, hint, (w // 2, h // 2 + 2), "px.hazard.1", "midtop")
        hud.text(screen, self.stamp, (4, h - 3), "px.floor.3", "bottomleft")
