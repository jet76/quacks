"""Ingredient effect handlers, organized by book page.

Each ingredient color has up to 4 book pages with different abilities.
Effects are applied at the correct game phase via the game engine hooks.
"""

from quacks.ingredients.registry import get_effect, EFFECT_REGISTRY

__all__ = ["get_effect", "EFFECT_REGISTRY"]
