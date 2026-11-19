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
    "lance": "arc_trail",  # Bolt Lance
    "power_shock_mine": "orb_fire",
    "power_storm_aura": "spark",
    "blast": "lunge",  # the ring blasts of Shock Mine, Impact Blink, Displacer and Meteor
    "leap": "blink_depart",  # Meteor takes off
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
    "rival_destroyed": "boss_down",  # rolling explosions, then the motif in major
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
    "boss_tell": "boss_charge",
    "boss_ring": "ring_burst",
    "boss_spiral": "spiral",
    "quake": "quake",
    "summon": "summon",
    # Bulwark and Magnet (powers spec section 8).
    "power_bulwark": "bulwark_up",
    "shield_absorb": "bulwark_absorb",
    "shield_reflect": "bulwark_reflect",
    "power_magnet": "magnet_field",
    "magnet_crush": "magnet_crush",
    "magnet_rejected": "blink_deny",
    # The first half of the Bulwark and Magnet pairs reuse fitting cues, like the first
    # nine fused powers (their own cues are a later pass, spec section 8).
    "power_static_guard": "bulwark_up",
    "power_tesla_coil": "summon",
    "power_capacitor_armor": "bulwark_up",
    "armor_release": "ring_burst",
    "power_lodestone": "orb_fire",
    "power_ion_hook": "spark",
    "hooked": "magnet_crush",
    "power_magrail": "live_wire",
    "power_bastion": "bulwark_up",
    "power_reflector_wave": "lunge",
    "power_fortress": "lattice",
    "power_vortex_cone": "magnet_field",
    "power_implosion": "magnet_field",
    "power_gravity_well": "magnet_field",
    "power_phase_guard": "bulwark_up",
    "power_afterimage": "relay_blink",
    "power_rewind": "fuse_rare",
    "power_undertow": "magnet_field",
    "power_grapple": "lunge",
    "power_riptide": "magnet_crush",
    "power_lightning_rod": "summon",
    "power_shield_toss": "lunge",
    "power_mirror_field": "magnet_field",
    "mirror_release": "bulwark_reflect",
    # The boss kits (docs/BOSS_DESIGN.md): each attack its own sound.
    "phase_change": "phase_change",
    "live_wire": "live_wire",
    "volley": "volley",
    "charge": "charge",
    "charge_impact": "charge_impact",
    "spray": "spray",
    "lattice": "lattice",
    "vent": "vent",
    "boss_reward": "unlock",
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
    "lance": "a jagged bolt runs behind the dashing Surge",
    "power_shock_mine": "a spiked charge flies toward the cursor",
    "power_storm_aura": "a ring of turning bolts appears around the Surge",
    "blast": "a magenta ring runs out from the blast",
    "leap": "the Surge rises over its shadow and a landing ring fills",
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
    "rival_destroyed": "the wreck sinks under chained explosions, then NAME DOWN",
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
    "boss_tell": "a filling ring of dots around the boss plus the shape of what is coming",
    "boss_ring": "eight bolts fly out from the Linesman in a ring",
    "boss_spiral": "two or four streams of bolts turn around the Grid Core",
    "quake": "a screen jolt and a wide dashed ring runs out across the floor",
    "summon": "warp markers close in on both sides of the chamber",
    "phase_change": "a jolt, a flash, a burst and the chassis name with its new phase",
    "power_bulwark": "a ring of green dashes closes around the Surge",
    "shield_absorb": "a pale flick where a shot met the bubble",
    "shield_reflect": "a spark flies back out along the shot's path",
    "power_magnet": "an indigo field ring with dashes running in",
    "magnet_crush": "the field slams shut in a burst and a jolt",
    "magnet_rejected": "a grey puff and NO ROOM FOR A FIELD",
    "power_static_guard": "a green bubble with yellow sparks in its ring",
    "power_tesla_coil": "a small green tower appears and starts to crackle",
    "power_capacitor_armor": "three charge cells start to orbit the Surge",
    "armor_release": "a ring of sparks bursts out from the Surge",
    "power_lodestone": "a big slow spark with turning field lines",
    "power_ion_hook": "a barbed spark flies out",
    "hooked": "an indigo burst as the robot is dragged in",
    "power_magrail": "a bolt from the Surge to where the rail stops",
    "power_bastion": "a green bubble with magenta sparks in its ring",
    "power_reflector_wave": "a green bar with a magenta edge rolls forward",
    "power_fortress": "a ring of shield plates around the Surge",
    "power_vortex_cone": "the Burst cone, robots dragged inward",
    "power_implosion": "a field with a magenta rim, dashes running in",
    "power_gravity_well": "a wide field with a magenta rim, dashes running in",
    "power_phase_guard": "a cyan and green bubble appears where the Surge lands",
    "power_afterimage": "a cyan decoy stands at the takeoff point",
    "power_rewind": "the Surge snaps backward in a ring of light",
    "power_undertow": "a cyan rim and inward dashes mark the takeoff point",
    "power_grapple": "a cable trace follows the Surge toward their target",
    "power_riptide": "a ring expands from the takeoff point as robots snap inward",
    "power_lightning_rod": "a rod inside a green field draws bolts inward",
    "power_shield_toss": "a green and indigo shield flies out and back",
    "power_mirror_field": "a broken indigo ring forms around orbiting shots",
    "mirror_release": "the orbiting shots fire outward",
    "live_wire": "Live Wire's dotted lines turn into crackling arcs",
    "volley": "rings of six bolts burst from the marked landing circles",
    "charge": "the chassis runs down the marked lane",
    "charge_impact": "a heavy jolt and debris where the chassis hits the wall",
    "spray": "a fan of slow orbs, then a second fan in its gaps",
    "lattice": "the checkerboard of hatched hazard tiles starts burning",
    "vent": "steam pours off the chassis and VENTING. HIT IT NOW",
    "boss_reward": "a notice of the spare charges won",
    "fusion": "the EVOLVED notice and a burst in the power's color",
    "confirm": "the slot icon changes, or the Fuse Box closes",
    "deny": "a notice saying why, or ROUTING POWER while the link is busy",
    "menu_move": "the menu highlight moves",
    "roll_tick": "the roll highlight steps to the next card",
    "fuse_rare": "the rare card lifts into the reveal with one cross mark",
    "fuse_epic": "the epic card lifts into the reveal with notched corners and two marks",
    "fuse_legendary": "the legendary card lifts into the reveal with rays and an outline pulse",
    "low_health": "two or fewer battery cells left in the HUD",
}
STINGS = {"pressure": "sting_clamp", "spacing": "sting_insulate", "lateral": "sting_oscillate"}
# Hostile tells duck the music: aim tells, hazard arming and a Breaker raising its fists
# (hazard_fill), warp markers (relay_click) and a boss winding up its signature (boss_charge).
TELLS = {"mite_tell", "hazard_fill", "relay_click", "boss_charge"}
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
            if event.kind == "rival_destroyed" and world.outcome == "down":
                continue
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
