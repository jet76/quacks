"""Chip data structures for the Quacks of Quedlinburg simulation."""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from quacks.enums import ChipColor

if TYPE_CHECKING:
    from quacks.game import GameState
    from quacks.player import Player


@dataclass(frozen=True)
class Chip:
    """An ingredient chip with a color and value.

    Value determines how many cauldron spaces the chip advances.
    White chips additionally contribute to the explosion counter.
    """
    color: ChipColor
    value: int  # 1, 2, 3, or 4

    def __repr__(self) -> str:
        return f"{self.color.value.capitalize()}({self.value})"

    def __str__(self) -> str:
        return repr(self)


# ---------------------------------------------------------------------------
# Chip catalogue — all chips available in the base game
# ---------------------------------------------------------------------------

# White (Cherry Bombs) — not purchasable; part of starting bag + round-6 addition
WHITE_1 = Chip(ChipColor.WHITE, 1)
WHITE_2 = Chip(ChipColor.WHITE, 2)
WHITE_3 = Chip(ChipColor.WHITE, 3)
WHITE_4 = Chip(ChipColor.WHITE, 4)  # rare / expansion; kept for completeness

# Orange (Pumpkin) — only value 1 available [VERIFY if 2/4 exist]
ORANGE_1 = Chip(ChipColor.ORANGE, 1)

# Green (Garden Spider)
GREEN_1 = Chip(ChipColor.GREEN, 1)
GREEN_2 = Chip(ChipColor.GREEN, 2)
GREEN_4 = Chip(ChipColor.GREEN, 4)

# Blue (Crow Skull)
BLUE_1 = Chip(ChipColor.BLUE, 1)
BLUE_2 = Chip(ChipColor.BLUE, 2)
BLUE_4 = Chip(ChipColor.BLUE, 4)

# Red (Toadstool)
RED_1 = Chip(ChipColor.RED, 1)
RED_2 = Chip(ChipColor.RED, 2)
RED_4 = Chip(ChipColor.RED, 4)

# Yellow (Mandrake Root)
YELLOW_1 = Chip(ChipColor.YELLOW, 1)
YELLOW_2 = Chip(ChipColor.YELLOW, 2)
YELLOW_4 = Chip(ChipColor.YELLOW, 4)

# Purple (Raven's Feather)
PURPLE_1 = Chip(ChipColor.PURPLE, 1)
PURPLE_2 = Chip(ChipColor.PURPLE, 2)
PURPLE_4 = Chip(ChipColor.PURPLE, 4)

# Black (Crow's Eye)
BLACK_1 = Chip(ChipColor.BLACK, 1)
BLACK_2 = Chip(ChipColor.BLACK, 2)
BLACK_4 = Chip(ChipColor.BLACK, 4)


# ---------------------------------------------------------------------------
# Market price catalogue — cost in coins to buy each chip
# ---------------------------------------------------------------------------

# Format: (ChipColor, value) → coins
CHIP_COSTS: dict[tuple[ChipColor, int], int] = {
    (ChipColor.ORANGE, 1): 3,
    (ChipColor.GREEN,  1): 4,
    (ChipColor.GREEN,  2): 8,
    (ChipColor.GREEN,  4): 14,
    (ChipColor.BLUE,   1): 5,
    (ChipColor.BLUE,   2): 10,
    (ChipColor.BLUE,   4): 19,
    (ChipColor.RED,    1): 6,   # [VERIFY: some sources say 7]
    (ChipColor.RED,    2): 10,  # [VERIFY]
    (ChipColor.RED,    4): 16,  # [VERIFY]
    (ChipColor.YELLOW, 1): 8,
    (ChipColor.YELLOW, 2): 12,
    (ChipColor.YELLOW, 4): 18,
    (ChipColor.PURPLE, 1): 9,   # [VERIFY]
    (ChipColor.PURPLE, 2): 13,  # [VERIFY]
    (ChipColor.PURPLE, 4): 18,  # [VERIFY]
    (ChipColor.BLACK,  1): 10,
    (ChipColor.BLACK,  2): 15,  # [VERIFY]
    (ChipColor.BLACK,  4): 22,  # [VERIFY]
}


def chip_cost(chip: Chip) -> int | None:
    """Return the coin cost for a purchasable chip, or None if not purchasable."""
    return CHIP_COSTS.get((chip.color, chip.value))


# ---------------------------------------------------------------------------
# Starting bag composition (per player)
# ---------------------------------------------------------------------------

STARTING_BAG: list[Chip] = [
    WHITE_1, WHITE_1, WHITE_1, WHITE_1,   # 4× White 1
    WHITE_2, WHITE_2,                      # 2× White 2
    WHITE_3,                               # 1× White 3
    ORANGE_1,                              # 1× Orange 1
    GREEN_1,                               # 1× Green 1
]

# Added to each bag at the start of Round 6
ROUND_6_WHITE_ADDITION = WHITE_1
