"""Difficulty presets shared by gameplay and replay."""

from dataclasses import replace

from overload.sim.tuning import DEFAULT

PRESETS = {
    "easy": replace(
        DEFAULT,
        player_max_charge=8,
        drone_health=5,
        relay_health=7,
        breaker_health=13,
        sentry_health=8,
        sweeper_health=3,
        rival_health=34,
        bolt_speed=1.7,
    ),
    "medium": DEFAULT,
    "hard": replace(
        DEFAULT,
        player_max_charge=5,
        drone_health=7,
        relay_health=10,
        breaker_health=19,
        sentry_health=12,
        sweeper_health=5,
        rival_health=48,
        bolt_speed=2.15,
    ),
    "nightmare": replace(
        DEFAULT,
        player_max_charge=4,
        drone_health=9,
        relay_health=12,
        breaker_health=23,
        sentry_health=15,
        sweeper_health=6,
        rival_health=58,
        bolt_speed=2.45,
    ),
}

DIFFICULTIES = tuple(PRESETS)
