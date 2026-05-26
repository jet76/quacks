"""Abstract base class for player strategies."""

from __future__ import annotations
from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Optional

from quacks.enums import ExplosionChoice

if TYPE_CHECKING:
    from quacks.chips import Chip
    from quacks.game import GameState
    from quacks.player import Player


class PlayerStrategy(ABC):
    """Interface for all player decision logic.

    Every method receives the current player and full game state so
    strategies can be as simple (ignore state) or as complex (full
    look-ahead / Monte Carlo) as desired.
    """

    @property
    def name(self) -> str:
        return self.__class__.__name__

    # ------------------------------------------------------------------
    # Core decision: keep drawing?
    # ------------------------------------------------------------------

    @abstractmethod
    def should_continue_pulling(self, player: "Player", state: "GameState") -> bool:
        """Return True to draw another chip, False to stop voluntarily."""

    # ------------------------------------------------------------------
    # Explosion outcome
    # ------------------------------------------------------------------

    def choose_explosion_outcome(
        self, player: "Player", state: "GameState"
    ) -> ExplosionChoice:
        """When exploded: choose VP or coins. Default: prefer VP early, coins late."""
        # Simple heuristic: prefer VP unless bag is very weak
        bag = player.bag
        total_value = sum(c.value for c in bag.all_chips())
        if total_value < 20 and state.round_number < 7:
            return ExplosionChoice.COINS
        return ExplosionChoice.VP

    # ------------------------------------------------------------------
    # Buying decisions
    # ------------------------------------------------------------------

    @abstractmethod
    def choose_purchases(
        self, player: "Player", state: "GameState", coins: int
    ) -> list["Chip"]:
        """Return list of chips to buy (in purchase order). May be empty."""

    # ------------------------------------------------------------------
    # Ruby spending
    # ------------------------------------------------------------------

    def choose_ruby_spending(
        self, player: "Player", state: "GameState"
    ) -> tuple[int, bool]:
        """Return (droplet_advances, refill_flask).

        Default: save rubies for droplet unless flask was used.
        """
        advances = 0
        refill = False
        rubies = player.rubies

        # Refill flask if used and we have rubies (flask is very valuable)
        if not player.flask_full and rubies >= 2:
            refill = True
            rubies -= 2

        # Advance droplet if we can afford it
        while rubies >= 2:
            advances += 1
            rubies -= 2

        return advances, refill

    # ------------------------------------------------------------------
    # Ingredient-specific decisions
    # ------------------------------------------------------------------

    def use_flask(self, player: "Player", state: "GameState", chip: "Chip") -> bool:
        """Should the flask be used on the just-drawn chip? Default: if it causes explosion."""
        from quacks.enums import ChipColor
        if chip.color == ChipColor.WHITE:
            new_white_sum = player.cauldron.white_sum + chip.value
            return new_white_sum > 7
        return False

    def use_yellow_power(
        self, player: "Player", state: "GameState", white_chip: "Chip"
    ) -> bool:
        """Should the Yellow chip return the preceding white chip? Default: always yes."""
        return True

    def choose_blue_chip(
        self, player: "Player", state: "GameState", peeked: list["Chip"]
    ) -> Optional["Chip"]:
        """Which peeked chip to place (or None to return all)? Default: best non-white."""
        from quacks.enums import ChipColor
        non_white = [c for c in peeked if c.color != ChipColor.WHITE]
        if non_white:
            return max(non_white, key=lambda c: c.value)
        return None  # return all whites to bag

    def choose_purple_upgrade(
        self, player: "Player", state: "GameState", options: list[tuple["Chip", "Chip"]]
    ) -> Optional[tuple["Chip", "Chip"]]:
        """Which purple upgrade to take (or None)? Default: highest value upgrade."""
        if not options:
            return None
        return max(options, key=lambda pair: pair[1].value)

    # ------------------------------------------------------------------
    def choose_free_chip(
        self, player: "Player", state: "GameState", available: list["Chip"]
    ) -> Optional["Chip"]:
        """Choose a free chip (fortune card effect). Default: cheapest color highest value."""
        if not available:
            return None
        from quacks.chips import CHIP_COSTS
        return max(
            available,
            key=lambda c: (CHIP_COSTS.get((c.color, c.value), 0), c.value),
        )

    # ------------------------------------------------------------------
    # Yellow ingredient decisions
    # ------------------------------------------------------------------

    def choose_white_to_return(
        self, player: "Player", state: "GameState", whites: list["Chip"]
    ) -> Optional["Chip"]:
        """Yellow page 2: which white chip in the pot to return to bag.

        Default: return the lowest-value white (minimises future explosion risk).
        """
        if not whites:
            return None
        return min(whites, key=lambda c: c.value)

    def choose_chip_to_return(
        self, player: "Player", state: "GameState", chips: list["Chip"]
    ) -> Optional["Chip"]:
        """Yellow page 3: which chip (any color) in the pot to return to bag.

        Default: return the highest-value white; if no whites, do nothing.
        """
        from quacks.enums import ChipColor
        whites = [c for c in chips if c.color == ChipColor.WHITE]
        if whites:
            return max(whites, key=lambda c: c.value)
        return None

    def choose_chips_to_return(
        self, player: "Player", state: "GameState", chips: list["Chip"], max_n: int
    ) -> list["Chip"]:
        """Yellow page 4: up to max_n chips (any color) to return from pot to bag.

        Default: return highest-value whites up to max_n.
        """
        from quacks.enums import ChipColor
        whites = sorted(
            [c for c in chips if c.color == ChipColor.WHITE],
            key=lambda c: -c.value,
        )
        return whites[:max_n]

    # ------------------------------------------------------------------
    # Black ingredient decisions
    # ------------------------------------------------------------------

    def choose_chip_to_remove(
        self, player: "Player", state: "GameState", peeked: list["Chip"]
    ) -> Optional["Chip"]:
        """Black page 4: which peeked chip to permanently remove from the bag.

        Default: remove the highest-value white chip (bag thinning); otherwise None.
        """
        from quacks.enums import ChipColor
        whites = [c for c in peeked if c.color == ChipColor.WHITE]
        if whites:
            return max(whites, key=lambda c: c.value)
        return None

    def __repr__(self) -> str:
        return f"{self.name}()"
