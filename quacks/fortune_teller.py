"""Fortune Teller cards — 24-card deck, 9 drawn per game (one per round).

At game start the 24-card deck is shuffled; the top 9 cards are used for
rounds 1–9. The remaining 15 are set aside.

[VERIFY]: The exact text and count of all 24 cards needs confirmation
against the physical game. The list below is a best-approximation
reconstruction from training knowledge and community sources.
"""

from __future__ import annotations
import random
from dataclasses import dataclass
from enum import Enum, auto
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from quacks.game import GameState


class FortuneEffect(Enum):
    DROPLET_ADVANCE         = auto()  # All players advance droplet N spaces
    FREE_CHIP_DRAW_SAFE     = auto()  # Draw 1 chip free (no explosion risk)
    FREE_CHIP_DRAW_UNSAFE   = auto()  # Draw 1 extra chip (counts toward explosion)
    RAT_MULTIPLIER          = auto()  # Rat stone advances multiplied
    STOP_BONUS_VP           = auto()  # Non-exploded players score +N bonus VP
    EXPLODE_RUBY            = auto()  # Exploded players gain +1 ruby
    FREE_CHIP_FROM_SUPPLY   = auto()  # Each player takes 1 chip from supply free
    FLASK_FREE_REFILL       = auto()  # Flask treated as refilled for all players
    VP_MULTIPLIER           = auto()  # VP scored this round is multiplied
    BONUS_COIN              = auto()  # All players receive extra coins
    BONUS_RUBY              = auto()  # All players receive 1 ruby immediately
    LOOK_AT_BAG_TOP         = auto()  # Each player may look at top N chips of bag
    WINNER_FREE_CHIP        = auto()  # Player with highest scoring marker buys 1 free
    STRONG_INGREDIENT       = auto()  # Ingredient chips are each worth 1 extra space
    NO_FLASK                = auto()  # Flasks may not be used this round
    EXTRA_DROPLET_RUBY      = auto()  # Landing on ruby spaces gives extra ruby
    CATCHUP_COINS           = auto()  # Trailing players get bonus coins
    FREE_UPGRADE            = auto()  # All players may upgrade 1 chip value for free


@dataclass(frozen=True)
class FortuneCard:
    """A single Fortune Teller card."""
    card_id: int
    name: str
    effect: FortuneEffect
    description: str
    magnitude: int = 1


# ---------------------------------------------------------------------------
# The 24 Fortune Teller cards [VERIFY all against physical game]
# ---------------------------------------------------------------------------

FORTUNE_CARDS: list[FortuneCard] = [
    # --- Droplet advance ---
    FortuneCard(1, "Helpful Spirits",
                FortuneEffect.DROPLET_ADVANCE,
                "All players advance their droplet 1 space forward.", 1),
    FortuneCard(2, "Benevolent Spirits",
                FortuneEffect.DROPLET_ADVANCE,
                "All players advance their droplet 2 spaces forward.", 2),

    # --- Free chip draws ---
    FortuneCard(3, "Free Sample",
                FortuneEffect.FREE_CHIP_DRAW_SAFE,
                "Each player draws 1 chip from bag and places it in pot; "
                "this draw cannot cause explosion.", 1),
    FortuneCard(4, "Bold Venture",
                FortuneEffect.FREE_CHIP_DRAW_UNSAFE,
                "Each player must draw 1 extra chip before pulling; "
                "it counts toward explosion.", 1),

    # --- Rat stone ---
    FortuneCard(5, "Plague of Rats",
                FortuneEffect.RAT_MULTIPLIER,
                "Rat stone advances are doubled this round.", 2),
    FortuneCard(6, "Rat King",
                FortuneEffect.RAT_MULTIPLIER,
                "Rat stone advances are tripled this round.", 3),

    # --- Non-explode bonus VP ---
    FortuneCard(7, "Careful Quack",
                FortuneEffect.STOP_BONUS_VP,
                "Players who stop voluntarily score +1 bonus VP.", 1),
    FortuneCard(8, "Master's Touch",
                FortuneEffect.STOP_BONUS_VP,
                "Players who stop voluntarily score +2 bonus VP.", 2),

    # --- Exploded bonus ---
    FortuneCard(9, "Brilliant Failure",
                FortuneEffect.EXPLODE_RUBY,
                "Players whose pot explodes receive 1 additional ruby.", 1),

    # --- Free chip from supply ---
    FortuneCard(10, "Market Day",
                FortuneEffect.FREE_CHIP_FROM_SUPPLY,
                "Each player may take any 1 chip from supply free.", 1),

    # --- Flask refill ---
    FortuneCard(11, "Alchemist's Gift",
                FortuneEffect.FLASK_FREE_REFILL,
                "All players treat their flask as refilled for free this round.", 1),

    # --- VP multiplier ---
    FortuneCard(12, "Grand Market",
                FortuneEffect.VP_MULTIPLIER,
                "All VP scored from the cauldron this round is doubled.", 2),

    # --- Bonus coins ---
    FortuneCard(13, "Windfall",
                FortuneEffect.BONUS_COIN,
                "All players receive 3 bonus coins this round.", 3),
    FortuneCard(14, "Generous Patron",
                FortuneEffect.BONUS_COIN,
                "All players receive 5 bonus coins this round.", 5),

    # --- Bonus ruby ---
    FortuneCard(15, "Lucky Charm",
                FortuneEffect.BONUS_RUBY,
                "All players immediately receive 1 ruby.", 1),

    # --- Peek at bag ---
    FortuneCard(16, "Crystal Ball",
                FortuneEffect.LOOK_AT_BAG_TOP,
                "Each player may look at the top 3 chips of their bag.", 3),

    # --- Leader bonus ---
    FortuneCard(17, "Recognition",
                FortuneEffect.WINNER_FREE_CHIP,
                "The player with the highest scoring marker may take 1 chip "
                "from supply for free.", 1),

    # --- Strong ingredient ---
    FortuneCard(18, "Strong Ingredients",
                FortuneEffect.STRONG_INGREDIENT,
                "All ingredient chips (except white) placed this round "
                "count as 1 space further than their printed value.", 1),

    # --- No flask ---
    FortuneCard(19, "Corked Flask",
                FortuneEffect.NO_FLASK,
                "Flasks may not be used this round.", 1),

    # --- Extra ruby on ruby spaces ---
    FortuneCard(20, "Golden Eye",
                FortuneEffect.EXTRA_DROPLET_RUBY,
                "Whenever a chip lands on a ruby space this round, "
                "the player receives 1 extra ruby.", 1),

    # --- Catch-up coins ---
    FortuneCard(21, "Helping Hand",
                FortuneEffect.CATCHUP_COINS,
                "Each player receives bonus coins equal to half the gap "
                "between their score and the leader's score (rounded down).", 1),

    # --- Free upgrade ---
    FortuneCard(22, "Upgrade",
                FortuneEffect.FREE_UPGRADE,
                "Each player may swap one 1-chip in their bag for a "
                "2-chip of the same color from supply (free).", 1),

    # --- Additional stop bonus ---
    FortuneCard(23, "Prudent Quack",
                FortuneEffect.STOP_BONUS_VP,
                "Players who stop voluntarily score +3 bonus VP.", 3),

    # --- Additional rat card ---
    FortuneCard(24, "Rat Parade",
                FortuneEffect.RAT_MULTIPLIER,
                "Each trailing player places rat stone 2 extra spaces "
                "ahead (in addition to normal catch-up).", 2),
]

assert len(FORTUNE_CARDS) == 24, f"Expected 24 fortune cards, got {len(FORTUNE_CARDS)}"

_CARD_BY_ID: dict[int, FortuneCard] = {c.card_id: c for c in FORTUNE_CARDS}


def make_game_deck(
    rng: random.Random | None = None,
    extra_cards: list[FortuneCard] | None = None,
) -> list[FortuneCard]:
    """Shuffle the fortune deck and return the top 9 for use this game.

    Expansions inject extra cards into the pool before shuffling (the deck
    grows beyond 24 but 9 cards are still drawn). The other cards are set aside.
    """
    deck = list(FORTUNE_CARDS)
    if extra_cards:
        deck.extend(extra_cards)
    (rng or random).shuffle(deck)
    return deck[:9]
