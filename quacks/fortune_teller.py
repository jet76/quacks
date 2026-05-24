"""Fortune Teller cards — one drawn per round, effects apply to all players.

Cards are shuffled once at game start and drawn in order, one per round.
There are 9 cards (one per round).

[VERIFY]: The exact text of all 9 cards must be confirmed against the physical
game. The implementations below are best-approximation reconstructions.
"""

from __future__ import annotations
from dataclasses import dataclass
from enum import Enum, auto
from typing import TYPE_CHECKING, Callable

if TYPE_CHECKING:
    from quacks.game import GameState


class FortuneEffect(Enum):
    """Categories of fortune teller effects."""
    DROPLET_ADVANCE = auto()       # All players advance droplet N spaces
    RAT_DOUBLE = auto()            # Rat stones worth double this round
    FREE_CHIP_DRAW = auto()        # Each player draws 1 extra chip free (pre-pulling)
    STOP_BONUS_VP = auto()         # Non-exploded players score +1 bonus VP
    EXPLODE_RUBY = auto()          # Exploded players gain 1 extra ruby
    FREE_CHIP_FROM_SUPPLY = auto() # Each player may take 1 chip from supply for free
    FLASK_FREE_REFILL = auto()     # Flask is treated as refilled for free this round
    VP_DOUBLED = auto()            # VP scored this round is doubled
    EXTRA_DRAW_BEFORE = auto()     # Each player gets 1 extra mandatory draw before pulling


@dataclass(frozen=True)
class FortuneCard:
    """A single Fortune Teller card."""
    card_id: int          # 1–9
    name: str
    effect: FortuneEffect
    description: str
    magnitude: int = 1    # e.g. for DROPLET_ADVANCE, how many spaces


# ---------------------------------------------------------------------------
# The 9 Fortune Teller cards [VERIFY exact effects against physical cards]
# ---------------------------------------------------------------------------

FORTUNE_CARDS: list[FortuneCard] = [
    FortuneCard(
        card_id=1,
        name="Helpful Spirits",
        effect=FortuneEffect.DROPLET_ADVANCE,
        description="All players move their droplet 1 space forward in the cauldron.",
        magnitude=1,
    ),
    FortuneCard(
        card_id=2,
        name="Plague of Rats",
        effect=FortuneEffect.RAT_DOUBLE,
        description="Rat stone advances are doubled for this round.",
        magnitude=2,
    ),
    FortuneCard(
        card_id=3,
        name="Free Sample",
        effect=FortuneEffect.FREE_CHIP_DRAW,
        description=(
            "Before pulling begins, each player draws 1 chip from their bag "
            "and places it in their cauldron. This draw cannot cause an explosion."
        ),
        magnitude=1,
    ),
    FortuneCard(
        card_id=4,
        name="Careful Quack",
        effect=FortuneEffect.STOP_BONUS_VP,
        description="Players who stop voluntarily (do not explode) score +1 bonus VP.",
        magnitude=1,
    ),
    FortuneCard(
        card_id=5,
        name="Brilliant Failure",
        effect=FortuneEffect.EXPLODE_RUBY,
        description="Players whose potion explodes receive 1 additional ruby.",
        magnitude=1,
    ),
    FortuneCard(
        card_id=6,
        name="Market Day",
        effect=FortuneEffect.FREE_CHIP_FROM_SUPPLY,
        description="Each player may take any 1 chip from the supply and add it to their bag for free.",
        magnitude=1,
    ),
    FortuneCard(
        card_id=7,
        name="Alchemist's Gift",
        effect=FortuneEffect.FLASK_FREE_REFILL,
        description="All players treat their flask as refilled for free this round.",
        magnitude=1,
    ),
    FortuneCard(
        card_id=8,
        name="Grand Market",
        effect=FortuneEffect.VP_DOUBLED,
        description="All VP scored from the cauldron this round is doubled.",
        magnitude=2,
    ),
    FortuneCard(
        card_id=9,
        name="Bold Venture",
        effect=FortuneEffect.EXTRA_DRAW_BEFORE,
        description=(
            "Before pulling begins, each player must draw 1 extra chip from their bag "
            "and place it in their cauldron (counts toward explosion)."
        ),
        magnitude=1,
    ),
]


def make_shuffled_deck(rng=None) -> list[FortuneCard]:
    """Return a shuffled copy of the 9 Fortune Teller cards."""
    import random
    deck = list(FORTUNE_CARDS)
    (rng or random).shuffle(deck)
    return deck
