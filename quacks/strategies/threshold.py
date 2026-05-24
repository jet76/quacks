"""Threshold strategy: stop when white sum reaches a fixed threshold."""

from __future__ import annotations
from typing import TYPE_CHECKING

from quacks.enums import ChipColor, ExplosionChoice
from quacks.strategies.base import PlayerStrategy

if TYPE_CHECKING:
    from quacks.chips import Chip
    from quacks.game import GameState
    from quacks.player import Player


class ThresholdStrategy(PlayerStrategy):
    """Stop pulling when white chips in pot reach a given sum.

    The default threshold (5) is conservative — you stop before any chance
    of a 3-white explosion. The optimal threshold shifts over the course
    of a game as the bag composition changes.
    """

    def __init__(self, white_threshold: int = 5, buying_priority: list[ChipColor] | None = None) -> None:
        """
        Args:
            white_threshold: Stop when white sum in pot reaches this value.
            buying_priority: Colors to prioritize when buying, in order.
        """
        self.white_threshold = white_threshold
        self.buying_priority = buying_priority or [
            ChipColor.GREEN,
            ChipColor.BLUE,
            ChipColor.RED,
            ChipColor.YELLOW,
            ChipColor.PURPLE,
            ChipColor.BLACK,
        ]

    @property
    def name(self) -> str:
        return f"Threshold(t={self.white_threshold})"

    def should_continue_pulling(self, player: "Player", state: "GameState") -> bool:
        cauldron = player.cauldron
        if cauldron.exploded:
            return False
        return cauldron.white_sum < self.white_threshold

    def choose_purchases(
        self, player: "Player", state: "GameState", coins: int
    ) -> list["Chip"]:
        from quacks.chips import Chip, CHIP_COSTS
        purchases: list[Chip] = []
        remaining = coins
        available = state.market.available_chips(state.round_number)

        for color in self.buying_priority:
            if remaining <= 0:
                break
            # Buy highest-value chip we can afford for this color
            color_chips = sorted(
                [l for l in available if l.chip.color == color and l.stock > 0],
                key=lambda l: l.chip.value,
                reverse=True,
            )
            for listing in color_chips:
                if listing.cost <= remaining:
                    purchases.append(listing.chip)
                    remaining -= listing.cost
                    break  # one chip per color per round for this strategy

        return purchases
