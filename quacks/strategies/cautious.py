"""Cautious strategy: probability-aware stopping using expected value."""

from __future__ import annotations
from typing import TYPE_CHECKING

from quacks.enums import ChipColor
from quacks.strategies.base import PlayerStrategy

if TYPE_CHECKING:
    from quacks.chips import Chip
    from quacks.game import GameState
    from quacks.player import Player


class CautiousStrategy(PlayerStrategy):
    """Stop drawing when the probability of explosion exceeds a threshold.

    Uses the current bag composition to compute:
      P(explosion | draw next chip) = (whites that would exceed budget) / bag_size

    Stops when this probability exceeds stop_threshold (default 0.25 = 25%).
    """

    def __init__(self, stop_threshold: float = 0.25) -> None:
        self.stop_threshold = stop_threshold

    @property
    def name(self) -> str:
        return f"Cautious(p={self.stop_threshold:.0%})"

    def should_continue_pulling(self, player: "Player", state: "GameState") -> bool:
        cauldron = player.cauldron
        if cauldron.exploded or player.bag.is_empty:
            return False
        p_explode = player.bag.explosion_probability(cauldron.white_sum)
        return p_explode < self.stop_threshold

    def choose_purchases(
        self, player: "Player", state: "GameState", coins: int
    ) -> list["Chip"]:
        """Prioritise ingredients that dilute the white chip danger."""
        from quacks.chips import Chip
        purchases: list[Chip] = []
        remaining = coins
        available = state.market.available_chips(state.round_number)

        # Priority: colours that help survive or score (Green, Blue, Yellow)
        priority_colors = [ChipColor.GREEN, ChipColor.YELLOW, ChipColor.BLUE,
                           ChipColor.RED, ChipColor.PURPLE, ChipColor.BLACK]

        for color in priority_colors:
            if remaining <= 0:
                break
            color_chips = sorted(
                [l for l in available if l.chip.color == color and l.stock > 0],
                key=lambda l: l.chip.value,
                reverse=True,
            )
            for listing in color_chips:
                if listing.cost <= remaining:
                    purchases.append(listing.chip)
                    remaining -= listing.cost
                    break

        return purchases
