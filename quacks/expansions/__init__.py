"""Expansion framework for Quacks of Quedlinburg.

An Expansion object bundles everything needed to extend the base game:
  - new_chips:          extra Chip types and their market costs
  - extra_fortune_cards: additional FortuneCard objects added to the 24-card deck
                         before shuffling (total deck size grows)
  - starting_bag_extras: chips added to every player's starting bag
  - book_page_overrides: book-page mappings added/replaced in the market
  - extra_market_stock:  additional stock counts for existing chip types

Pass a list of Expansion objects to Game(..., expansions=[...]) to activate them.
The game engine applies expansions in order before the first round begins.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from quacks.chips import Chip
    from quacks.enums import ChipColor
    from quacks.fortune_teller import FortuneCard


@dataclass
class Expansion:
    """Descriptor for one expansion module.

    All fields default to empty so individual expansions only specify
    what they change.
    """
    name: str

    # Market additions: list of (chip, cost_in_coins)
    new_chips: list[tuple["Chip", int]] = field(default_factory=list)

    # Extra fortune teller cards injected into the shuffle pool
    extra_fortune_cards: list["FortuneCard"] = field(default_factory=list)

    # Extra chips added to every player's starting bag
    starting_bag_extras: list["Chip"] = field(default_factory=list)

    # Override which book page to start on for a given color
    # {ChipColor: page_number}
    book_page_overrides: dict["ChipColor", int] = field(default_factory=dict)

    # Additional market stock for existing chip types {chip: extra_count}
    extra_market_stock: dict["Chip", int] = field(default_factory=dict)

    def __repr__(self) -> str:
        return f"Expansion({self.name!r})"
