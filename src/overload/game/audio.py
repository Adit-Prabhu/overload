"""Sound for the game: sound effects from simulation events, and the music stems layered by
where the player is in the campaign.

Audio is presentation only. It reads events and visible state after each tick and never
feeds anything back, so the game plays the same with sound off (`--mute`, and always when
headless). Every sound has a visual twin listed in VISUAL_TWINS
(docs/ART_AND_AUDIO_DIRECTION.md, accessibility).

Music: all stems are 8 bars long and start together on muted channels, then only their
volumes change, on the next bar line, so layers come and go in time with the beat. Music
ducks by 6 dB while a hostile tell sounds, so tells always cut through.
"""

from __future__ import annotations

import pygame

from overload.paths import ASSETS
from overload.sim.state import Event
from overload.sim.tuning import DEFAULT

AUDIO = ASSETS / "audio"
BPM = 124
BAR_MS = 4 * 60_000 / BPM
DUCK_MS = 500
DUCK = 0.5  # -6 dB

# Simulation event -> sound effect.
EVENT_SOUNDS = {
    "shot": "shot",
    "player_hit": "player_hit",
    "dodge": "dodge",
    "player_down": "death",
    "power_spark": "spark",
    "blink_from": "blink_depart",
    "blink_to": "blink_arrive",
    "blink_rejected": "blink_deny",
    "power_arc_trail": "arc_trail",
    "tell": "mite_tell",
    "bolt": "mite_zap",
    "relay_mark": "relay_click",
    "relay_blink": "relay_blink",
    "hostile_destroyed": "enemy_death",
    "rival_tell": "mite_tell",
    "rival_lunge": "lunge",
    "hazard_armed": "hazard_fill",
    "rival_orb": "orb_fire",
    "rival_volley": "mite_zap",
    "rival_hit": "regulator_hit",
    "rival_destroyed": "regulator_defeated",
    "absorb": "pickup",
    "unlock": "unlock",
    "shards": "mite_zap",
    "shell": "orb_fire",
    "raise": "hazard_fill",
    "slam": "lunge",
    "rush": "tread",
    "burst": "lunge",
    "chain": "spark",
    "evolve": "fusion",
    "fully_evolved": "pickup",
    "room_lock": "deny",
    "room_clear": "confirm",
    "warp": "relay_click",
    "warp_in": "relay_blink",
    "secret_hit": "regulator_hit",
    "secret_open": "unlock",
}
# Each sound's visual twin: the game is fully playable muted.
VISUAL_TWINS = {
    "shot": "muzzle flash and the shot streak",
    "player_hit": "hit flicker and a burst on the Surge, one battery cell empties",
    "dodge": "fading ghosts behind the Surge",
    "player_down": "SHORT CIRCUIT banner",
    "power_spark": "the yellow Spark bolt",
    "blink_from": "Blink diamond at the departure point",
    "blink_to": "Blink diamond and burst at the arrival point",
    "blink_rejected": "grey fizzle and NO ROOM TO BLINK",
    "power_arc_trail": "the Arc Trail line",
    "tell": "dotted aim line and filling ring",
    "bolt": "the spiked hostile bolt",
    "relay_mark": "hatched landing diamond",
    "relay_blink": "the Relay jumps, diamond left behind",
    "hostile_destroyed": "short-circuit burst in the color of the power it carried",
    "rival_tell": "dotted aim line and filling ring around the Regulator",
    "rival_lunge": "the Regulator dashes along its aim line",
    "hazard_armed": "hatched hazard tile that fills as it arms",
    "rival_orb": "large orb",
    "rival_volley": "three-bolt fan",
    "rival_hit": "white flash on the Regulator, its bar drops",
    "rival_destroyed": "large burst, the Regulator disappears",
    "absorb": "burst in the power color",
    "unlock": "screen flash and a SPARK STOLEN or BLINK STOLEN notice",
    "protocol_boot": "protocol pose, shield ring and protocol icon",
    "shards": "a fan of three diamond shards",
    "shell": "a slow heavy round shell",
    "raise": "the Breaker raises its fists and a dotted ring fills at the slam's reach",
    "slam": "a dashed shockwave ring runs along the floor",
    "rush": "the Sweeper's wheels spin fast and it shoots forward",
    "burst": "magenta rays fan across the cone, wider when evolved",
    "chain": "a yellow bolt jumps from the hit robot to the next",
    "evolve": "a screen flash and SPARK, BLINK or BURST EVOLVED",
    "fully_evolved": "a burst in the power color and FULLY EVOLVED",
    "room_lock": "hazard-striped shutters close over the doors and LOCKDOWN",
    "room_clear": "the shutters open and ROOM CLEAR",
    "warp": "a closing ring of red dots where a robot will appear",
    "warp_in": "a red burst as the robot appears",
    "secret_hit": "another crack in the wall",
    "secret_open": "the wall breaks and A HIDDEN ROOM",
    "fusion": "FUSED status and the Arc Trail icon in the menu",
    "confirm": "the slot icon changes, or the Fuse Box closes",
    "deny": "a notice naming the supported recipe, or ROUTING POWER while the link is busy",
    "low_health": "two or fewer battery cells left in the HUD",
}
STINGS = {"pressure": "sting_clamp", "spacing": "sting_insulate", "lateral": "sting_oscillate"}
# Hostile tells duck the music: aim tells, hazard arming and a Breaker raising its fists
# (hazard_fill), and warp markers (relay_click).
TELLS = {"mite_tell", "hazard_fill", "relay_click"}
STEMS = ("hum", "pulse", "arc", "lead", "fuse_box")
# Stem levels leave headroom so a full battle mix plus an effect stays out of clipping.
LEVELS = {"hum": 0.42, "pulse": 0.38, "arc": 0.22, "lead": 0.3, "fuse_box": 0.5}
SFX_LEVEL = 0.7
FADE_STEP = 0.08  # per frame, so ducking and layer changes ramp instead of clicking


def boot_sting(world) -> str | None:
    """The protocol sting, on the first tick of the Regulator's boot. The spawn event itself
    is cleared before any tick is shown, so the visible boot timer is the cue. A retry
    restores the boot, so the sting plays again as the fight restarts."""
    rival = world.rival if world is not None else None
    if rival is None or rival.boot != DEFAULT.rival_boot - 1:
        return None
    return STINGS[rival.protocol]


def stems_for(stage: str | None, encounter: int, outcome: str) -> set[str]:
    """Which stems play: the Fuse Box loop between encounters, HUM and PULSE in a fight,
    ARC from encounter 2 and LEAD in encounter 3. Practice plays like encounter 1. While
    the Surge is down only the HUM is left, and the ending keeps the full theme."""
    if stage == "fuse_box":
        return {"fuse_box"}
    if outcome == "down":
        return {"hum"}
    layers = {"hum", "pulse"}
    if encounter >= 2 or stage == "ending":
        layers.add("arc")
    if encounter >= 3 or stage == "ending":
        layers.add("lead")
    return layers


class Audio:
    """Plays nothing when disabled or when no audio device can be opened."""

    def __init__(self, enabled: bool = True) -> None:
        self.enabled = False
        self.sounds: dict[str, pygame.mixer.Sound] = {}
        self.music: dict[str, pygame.mixer.Channel] = {}
        self.targets: set[str] = set()
        self.started = 0
        self.bar = -1
        self.duck_until = 0
        self.volumes: dict[str, float] = {}
        if not enabled:
            return
        try:
            if not pygame.mixer.get_init():
                pygame.mixer.init(frequency=44_100, size=-16, channels=2, buffer=512)
            pygame.mixer.set_num_channels(32)
            pygame.mixer.set_reserved(len(STEMS))  # Sound.play never takes these
            for path in sorted(AUDIO.glob("*.ogg")):
                self.sounds[path.stem] = pygame.mixer.Sound(str(path))
        except (pygame.error, FileNotFoundError):
            return
        self.enabled = True
        self.started = pygame.time.get_ticks()
        for i, stem in enumerate(STEMS):
            sound = self.sounds.get(f"music_{stem}")
            if sound is None:
                continue  # a missing stem is simply silent
            channel = pygame.mixer.Channel(i)
            channel.set_volume(0.0)
            channel.play(sound, loops=-1)
            self.music[stem] = channel
            self.volumes[stem] = 0.0

    def play(self, name: str, volume: float = SFX_LEVEL) -> None:
        if not self.enabled:
            return
        sound = self.sounds.get(f"sfx_{name}") or self.sounds.get(name)
        if sound is None:
            return
        # Sound.play respects the reserved music channels (a forced find_channel does not),
        # and returns None when every effect channel is busy: the effect is simply dropped.
        channel = sound.play()
        if channel is not None:
            channel.set_volume(volume)
        if name in TELLS:
            self.duck_until = pygame.time.get_ticks() + DUCK_MS

    def events(self, events: list[Event], world) -> None:
        """Sound effects for one tick of simulation events."""
        if not self.enabled:
            return
        sting = boot_sting(world)
        if sting:
            self.play(sting, 0.9)
        for event in events:
            name = EVENT_SOUNDS.get(event.kind)
            if name is None:
                continue
            self.play(name, 0.3 if name == "shot" else SFX_LEVEL)
            if event.kind == "player_hit" and 0 < world.player.charge <= 2:
                self.play("low_health", 0.6)

    def update(self, stage: str | None, encounter: int, outcome: str) -> None:
        """Once per rendered frame: pick the layers and apply them on the next bar line."""
        if not self.enabled:
            return
        now = pygame.time.get_ticks()
        bar = int((now - self.started) // BAR_MS)
        if bar != self.bar or not self.targets:  # changes land on the next bar line
            self.targets = stems_for(stage, encounter, outcome)
            self.bar = bar
        duck = DUCK if now < self.duck_until else 1.0
        for stem, channel in self.music.items():
            target = LEVELS[stem] * duck if stem in self.targets else 0.0
            current = self.volumes[stem]
            step = max(-FADE_STEP, min(FADE_STEP, target - current))
            self.volumes[stem] = current + step
            channel.set_volume(self.volumes[stem])
