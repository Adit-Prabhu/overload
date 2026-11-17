"""Deterministic game rules. Nothing in this package may import pygame.

The simulation steps at a fixed 60 ticks per second with its own seeded RNG. It uses
only arithmetic and math.sqrt (correctly rounded under IEEE 754), never trigonometry or
math.hypot, so the same seed and inputs give the same state on every platform.
"""
