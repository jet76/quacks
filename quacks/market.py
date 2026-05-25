"""The ingredient market (shop) for purchasing chips between rounds."""

from __future__ import annotations
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Optional

from quacks.chips import Chip, CHIP_COSTS, ChipColor
from quacks.enums import IngredientBookPage


# Stock quantities per chip type/value (for N players). [VERIFY exact amounts]
# Format: (ChipColor, value) → quantity in supply
_BASE_STOCK_4_PLAYER: dict[tuple[ChipColor, int], int] = {
    (ChipColor.ORANGE, 1): 8,
    (ChipColor.GREEN,  1): 4, (ChipColor.GREEN,  2): 4, (ChipColor.GREEN,  4): 4,
    (ChipColor.BLUE,   1): 4, (ChipColor.BLUE,   2): 4, (ChipColor.BLUE,   4): 4,
    (ChipColor.RED,    1): 4, (ChipColor.RED,    2): 4, (ChipColor.RED,    4): 4,
    (ChipColor.YELLOW, 1): 4, (ChipColor.YELLOW, 2): 4, (ChipColor.YELLOW, 4): 4,
    (ChipColor.PURPLE, 1): 4, (ChipColor.PURPLE, 2): 4, (ChipColor.PURPLE, 4): 4,
    (ChipColor.BLACK,  1): 4, (ChipColor.BLACK,  2): 4, (ChipColor.BLACK,  4): 4,
}

# Which rounds each ingredient book becomes available
INGREDIENT_AVAILABILITY: dict[ChipColor, int] = {
    ChipColor.ORANGE: 1,
    ChipColor.BLACK:  1,
    ChipColor.GREEN:  1,
    ChipColor.BLUE:   1,
    ChipColor.RED:    1,
    ChipColor.YELLOW: 2,
    ChipColor.PURPLE: 3,
}


@dataclass
class MarketListing:
    chip: Chip
    cost: int
    stock: int
    available_from_round: int


class Market:
    """The ingredient shop where players spend coins to purchase chips.

    Tracks stock for each chip type. In a real game, stock is shared;
    this simulation models it as a single shared pool.

    Ingredient books gate which colors are available each round.
    Players can choose which page (1–4) of each book to use, changing
    the chip's in-game effect. The market sells the same chips regardless
    of book page — book page only affects the chip's pulling-phase effect.

    Expansions can inject extra chip costs, stock quantities, and
    availability rounds via the extra_* parameters.
    """

    def __init__(
        self,
        n_players: int = 4,
        book_pages: dict[ChipColor, int] | None = None,
        extra_costs: dict[tuple[ChipColor, int], int] | None = None,
        extra_stock: dict[tuple[ChipColor, int], int] | None = None,
        extra_availability: dict[ChipColor, int] | None = None,
    ) -> None:
        self.n_players = n_players
        # Active book page per ingredient color (default page 1)
        self.book_pages: dict[ChipColor, int] = {
            color: (book_pages or {}).get(color, 1)
            for color in ChipColor
            if color != ChipColor.WHITE
        }
        # Merge expansion costs into the cost catalogue
        self._costs: dict[tuple[ChipColor, int], int] = dict(CHIP_COSTS)
        if extra_costs:
            self._costs.update(extra_costs)
        # Merge expansion availability
        self._availability: dict[ChipColor, int] = dict(INGREDIENT_AVAILABILITY)
        if extra_availability:
            self._availability.update(extra_availability)
        self._stock: dict[tuple[ChipColor, int], int] = self._initialize_stock(extra_stock)

    def _initialize_stock(
        self,
        extra_stock: dict[tuple[ChipColor, int], int] | None = None,
    ) -> dict[tuple[ChipColor, int], int]:
        base = dict(_BASE_STOCK_4_PLAYER)
        # Scale down for fewer players [VERIFY exact scaling]
        if self.n_players == 2:
            stock = {k: max(2, v - 2) for k, v in base.items()}
        elif self.n_players == 3:
            stock = {k: max(2, v - 1) for k, v in base.items()}
        else:
            stock = base
        if extra_stock:
            for k, v in extra_stock.items():
                stock[k] = stock.get(k, 0) + v
        return stock

    # ------------------------------------------------------------------
    # Availability
    # ------------------------------------------------------------------

    def available_colors(self, round_number: int) -> list[ChipColor]:
        """Colors available for purchase in the given round."""
        return [
            color for color, avail_round in self._availability.items()
            if round_number >= avail_round
        ]

    def available_chips(self, round_number: int) -> list[MarketListing]:
        """All purchasable chip listings for the given round."""
        listings = []
        for color in self.available_colors(round_number):
            for value in (1, 2, 4):
                key = (color, value)
                if key not in self._costs:
                    continue
                stock = self._stock.get(key, 0)
                cost = self._costs[key]
                listings.append(MarketListing(
                    chip=Chip(color, value),
                    cost=cost,
                    stock=stock,
                    available_from_round=self._availability[color],
                ))
        return listings

    def in_stock(self, chip: Chip) -> bool:
        return self._stock.get((chip.color, chip.value), 0) > 0

    def cost(self, chip: Chip) -> Optional[int]:
        return self._costs.get((chip.color, chip.value))

    # ------------------------------------------------------------------
    # Transactions
    # ------------------------------------------------------------------

    def buy(self, chip: Chip, coins: int) -> tuple[bool, str]:
        """Attempt to purchase a chip. Returns (success, reason_if_failed)."""
        key = (chip.color, chip.value)
        price = self._costs.get(key)
        if price is None:
            return False, f"{chip} is not purchasable"
        if price > coins:
            return False, f"Not enough coins ({coins} < {price})"
        if self._stock.get(key, 0) <= 0:
            return False, f"{chip} is out of stock"
        self._stock[key] -= 1
        return True, ""

    def restock(self, chip: Chip, quantity: int = 1) -> None:
        """Return chips to market (e.g. from purple upgrade trade-in)."""
        key = (chip.color, chip.value)
        self._stock[key] = self._stock.get(key, 0) + quantity

    # ------------------------------------------------------------------
    # Purple chip upgrades
    # ------------------------------------------------------------------

    def purple_upgrade(
        self, purple_count: int, bag_chips: list[Chip]
    ) -> list[tuple[Chip, Chip]]:
        """Return list of valid (from_chip, to_chip) upgrades for purple count.

        1 purple: 1-chip → 2-chip same color
        2 purple: 2-chip → 4-chip same color
        3+ purple: 1-chip → 4-chip same color

        The caller is responsible for executing the swap (paying no coins).
        Returns all valid options; player strategy picks one (or none).
        """
        upgrades: list[tuple[Chip, Chip]] = []
        bag_set: set[Chip] = set(bag_chips)
        for chip in bag_set:
            if chip.color == ChipColor.WHITE:
                continue  # whites cannot be upgraded via purple
            from_v = chip.value
            if purple_count >= 3:
                # Can go 1 → 4
                if from_v == 1:
                    target = Chip(chip.color, 4)
                    if self.in_stock(target):
                        upgrades.append((chip, target))
            elif purple_count == 2:
                # Can go 2 → 4
                if from_v == 2:
                    target = Chip(chip.color, 4)
                    if self.in_stock(target):
                        upgrades.append((chip, target))
            elif purple_count == 1:
                # Can go 1 → 2
                if from_v == 1:
                    target = Chip(chip.color, 2)
                    if self.in_stock(target):
                        upgrades.append((chip, target))
        return upgrades

    # ------------------------------------------------------------------
    # Inspection
    # ------------------------------------------------------------------

    def stock_snapshot(self) -> dict:
        return {
            f"{color.value}_{value}": qty
            for (color, value), qty in self._stock.items()
            if qty > 0
        }

    def __repr__(self) -> str:
        return f"Market(n_players={self.n_players}, items_in_stock={sum(self._stock.values())})"
